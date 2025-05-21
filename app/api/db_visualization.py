from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import logging
from typing import Dict, Any, List

from app.db import get_db, get_article_collection

router = APIRouter()
logger = logging.getLogger(__name__)

# Set up templates directory
templates_dir = Path(__file__).parent.parent / "templates"
if not templates_dir.exists():
    os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

@router.get("/stats", response_model=Dict[str, Any], summary="Get database statistics")
async def get_db_stats():
    """
    Retrieve basic statistics and information about the MongoDB database.
    """
    try:
        db = await get_db()
        stats = await db.command("dbStats")
        collection_names = await db.list_collection_names()
        collection_stats = {}
        
        for collection_name in collection_names:
            collection_stats[collection_name] = await db.command("collStats", collection_name)
        
        return {
            "database": db.name,
            "stats": stats,
            "collections": collection_names,
            "collection_stats": collection_stats
        }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"error": str(e)}

@router.get("/articles", response_model=Dict[str, Any], summary="Get article collection data")
async def get_articles_data(request: Request, limit: int = Query(20, ge=1, le=200), skip: int = Query(0, ge=0)):
    """
    Retrieve articles data from the database with pagination and dynamic filtering.
    """
    try:
        collection = await get_article_collection()
        
        query_params = request.query_params
        filter_query: Dict[str, Any] = {} # Ensure type for clarity
        
        for key, value in query_params.items():
            if key not in ["limit", "skip"]: # Exclude pagination params from filters
                if key == "llm_requires_deep_analysis":
                    if value.lower() == "true":
                        filter_query[key] = True
                    elif value.lower() == "false":
                        filter_query[key] = False
                    # else: if value is not 'true' or 'false', it's ignored for this key.
                    # Consider raising an error for invalid boolean values if strictness is needed.
                # Example for a numeric field, if one existed:
                # elif key == "some_numeric_field":
                #     try:
                #         filter_query[key] = int(value)
                #     except ValueError:
                #         logger.warning(f"Invalid value for numeric filter {key}: {value}")
                #         # Optionally raise HTTPException for bad request
                else:
                    filter_query[key] = value
        
        total = await collection.count_documents(filter_query)
        articles_cursor = collection.find(filter_query).skip(skip).limit(limit)
        articles = await articles_cursor.to_list(length=limit)
        
        # Convert ObjectId to string for JSON serialization
        for article in articles:
            if "_id" in article:
                article["_id"] = str(article["_id"])
        
        return {
            "total": total,
            "articles": articles,
            "page": skip // limit + 1 if limit > 0 else 1, # Ensure page is at least 1
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
            "limit": limit,
            "active_filters": filter_query # Optional: return active filters
        }
    except Exception as e:
        logger.error(f"Error getting articles data: {e}")
        return {"error": str(e)}

@router.get("/dashboard", response_class=HTMLResponse, summary="Database visualization dashboard")
async def get_dashboard(request: Request, raw_page: int = Query(1, ge=1), raw_limit: int = Query(20, ge=1, le=100)):
    """
    Provides a web interface for visualizing database contents.
    """
    try:
        db = await get_db()
        collection = await get_article_collection()
        
        # Get basic stats
        stats = await db.command("dbStats")
        total_articles = await collection.count_documents({})

        # --- Analysis stats ---
        triaged_count = await collection.count_documents({"llm_category": {"$ne": None}})
        requires_deep_count = await collection.count_documents({"llm_requires_deep_analysis": True})
        deep_analysis_done_count = await collection.count_documents({"llm_deep_analysis_results": {"$ne": None}})
        not_analyzed_count = await collection.count_documents({"llm_category": None})

        # For pie chart: status distribution
        analysis_status_distribution = {
            "Triaged (LLM)": triaged_count,
            "Requires Deep Analysis": requires_deep_count,
            "Deep Analysis Done": deep_analysis_done_count,
            "Not Analyzed": not_analyzed_count
        }

        # Get some sample articles
        articles_cursor = collection.find({}).limit(10)
        articles_sample = await articles_cursor.to_list(length=10)
        for article in articles_sample:
            if "_id" in article:
                article["_id"] = str(article["_id"])

        # Get paginated articles for raw view
        total_raw_articles = await collection.count_documents({})
        raw_skip = (raw_page - 1) * raw_limit
        all_articles_cursor = collection.find({}).skip(raw_skip).limit(raw_limit)
        all_articles_list = await all_articles_cursor.to_list(length=raw_limit)
        for article in all_articles_list:
            if "_id" in article:
                article["_id"] = str(article["_id"])
        raw_total_pages = (total_raw_articles + raw_limit - 1) // raw_limit
        
        # Get category distribution if available
        categories = {}
        category_pipeline = [
            {"$match": {"llm_category": {"$ne": None}}},
            {"$group": {"_id": "$llm_category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        category_results_cursor = collection.aggregate(category_pipeline)
        category_results = await category_results_cursor.to_list(length=None)
        for result in category_results:
            categories[result["_id"]] = result["count"]
        
        # Get source distribution
        source_pipeline = [
            {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        source_results_cursor = collection.aggregate(source_pipeline)
        source_results = await source_results_cursor.to_list(length=None)
        sources = {}
        for result in source_results:
            sources[result["_id"]] = result["count"]
            
        # 1. Get sentiment distribution
        sentiments = {}
        sentiment_pipeline = [
            {"$match": {"llm_sentiment": {"$ne": None}}},
            {"$group": {"_id": "$llm_sentiment", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        sentiment_results_cursor = collection.aggregate(sentiment_pipeline)
        sentiment_results = await sentiment_results_cursor.to_list(length=None)
        for result in sentiment_results:
            sentiments[result["_id"]] = result["count"]
            
        # 2. Get publication date timeline
        timeline = {}
        timeline_pipeline = [
            {"$match": {"publication_date": {"$ne": None}}},
            {
                "$project": {
                    "date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d", 
                            "date": "$publication_date"
                        }
                    }
                }
            },
            {"$group": {"_id": "$date", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        timeline_results_cursor = collection.aggregate(timeline_pipeline)
        timeline_results = await timeline_results_cursor.to_list(length=None)
        for result in timeline_results:
            timeline[result["_id"]] = result["count"]
            
        # 3. Get deep analysis counts
        deep_analysis_count = await collection.count_documents(
            {"llm_deep_analysis_results": {"$ne": None}}
        )
        
        # 4. Extract key claims for analysis
        key_claims = {}
        key_claims_pipeline = [
            {"$match": {"llm_key_claim": {"$ne": None}}},
            {"$group": {"_id": "$llm_key_claim", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}  # Top 10 key claims
        ]
        key_claims_results_cursor = collection.aggregate(key_claims_pipeline)
        key_claims_results = await key_claims_results_cursor.to_list(length=None)
        for result in key_claims_results:
            key_claims[result["_id"]] = result["count"]
        
        # 5. Calculate source reliability metrics
        # We'll use the ratio of articles requiring deep analysis as a proxy for reliability
        sources_reliability = {}
        for source in sources.keys(): # sources is already populated from a previous aggregation
            total_source_articles = await collection.count_documents({"source_name": source})
            complex_articles = await collection.count_documents({
                "source_name": source, 
                "llm_requires_deep_analysis": True
            })
            if total_source_articles > 0:
                reliability_score = 1 - (complex_articles / total_source_articles)
                sources_reliability[source] = round(reliability_score * 100)  # As percentage
        
        # 6. Get deep analysis requirements distribution
        deep_analysis_required = {}
        deep_analysis_pipeline = [
            {"$match": {"llm_requires_deep_analysis": {"$ne": None}}},
            {"$group": {"_id": "$llm_requires_deep_analysis", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}}
        ]
        deep_analysis_results_cursor = collection.aggregate(deep_analysis_pipeline)
        deep_analysis_results = await deep_analysis_results_cursor.to_list(length=None)
        for result in deep_analysis_results:
            label = "Requires Deep Analysis" if result["_id"] else "Standard Analysis"
            deep_analysis_required[label] = result["count"]
        
        return templates.TemplateResponse(
            "db_dashboard.html",
            {
                "request": request,
                "db_name": db.name,
                "total_articles": total_articles,
                "storage_size_mb": round(stats["storageSize"] / (1024 * 1024), 2),
                "data_size_mb": round(stats["dataSize"] / (1024 * 1024), 2),
                "articles": articles_sample[:5],  # First 5 articles for recent articles view
                "all_articles_for_raw_view": all_articles_list, # Only current page for raw table view
                "raw_page": raw_page,
                "raw_limit": raw_limit,
                "raw_total_pages": raw_total_pages,
                "raw_total_articles": total_raw_articles,
                "categories": categories,
                "sources": sources,
                # New data for visualizations
                "sentiments": sentiments,
                "timeline": timeline,
                "deep_analysis_count": deep_analysis_count,
                "key_claims": key_claims,
                "sources_reliability": sources_reliability,
                "deep_analysis_required": deep_analysis_required,
                # New analysis stats
                "triaged_count": triaged_count,
                "requires_deep_count": requires_deep_count,
                "deep_analysis_done_count": deep_analysis_done_count,
                "not_analyzed_count": not_analyzed_count,
                "analysis_status_distribution": analysis_status_distribution
            }
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return f"<h1>Error rendering dashboard</h1><p>{str(e)}</p>"

@router.get("/sentiment", response_model=Dict[str, Any], summary="Get sentiment distribution data")
async def get_sentiment_data():
    """
    Retrieve sentiment distribution data from the articles.
    """
    try:
        collection = await get_article_collection()
        
        # Get sentiment distribution
        sentiment_pipeline = [
            {"$match": {"llm_sentiment": {"$ne": None}}},
            {"$group": {"_id": "$llm_sentiment", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        sentiment_results_cursor = collection.aggregate(sentiment_pipeline)
        sentiment_results = await sentiment_results_cursor.to_list(length=None)
        
        sentiments = {}
        for result in sentiment_results:
            sentiments[result["_id"]] = result["count"]
            
        return {
            "sentiments": sentiments,
            "total": sum(sentiments.values()) if sentiments else 0
        }
    except Exception as e:
        logger.error(f"Error getting sentiment data: {e}")
        return {"error": str(e)}

@router.get("/timeline", response_model=Dict[str, Any], summary="Get publication timeline data")
async def get_timeline_data(days: int = 30):
    """
    Retrieve publication date timeline data for the specified number of days.
    """
    try:
        collection = await get_article_collection()
        
        # Get publication timeline
        timeline_pipeline = [
            {"$match": {"publication_date": {"$ne": None}}},
            {
                "$project": {
                    "date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d", 
                            "date": "$publication_date"
                        }
                    }
                }
            },
            {"$group": {"_id": "$date", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
            {"$limit": days}
        ]
        timeline_results_cursor = collection.aggregate(timeline_pipeline)
        timeline_results = await timeline_results_cursor.to_list(length=None)
        
        timeline = {}
        for result in timeline_results:
            timeline[result["_id"]] = result["count"]
            
        return {
            "timeline": timeline,
            "days": days
        }
    except Exception as e:
        logger.error(f"Error getting timeline data: {e}")
        return {"error": str(e)}

@router.get("/key-claims", response_model=Dict[str, Any], summary="Get key claims data")
async def get_key_claims_data(limit: int = 10):
    """
    Retrieve the most common key claims from articles.
    """
    try:
        collection = await get_article_collection()
        
        # Extract key claims
        key_claims_pipeline = [
            {"$match": {"llm_key_claim": {"$ne": None}}},
            {"$group": {"_id": "$llm_key_claim", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        key_claims_results_cursor = collection.aggregate(key_claims_pipeline)
        key_claims_results = await key_claims_results_cursor.to_list(length=None)
        
        key_claims = {}
        for result in key_claims_results:
            key_claims[result["_id"]] = result["count"]
            
        return {
            "key_claims": key_claims,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting key claims data: {e}")
        return {"error": str(e)}

@router.get("/deep-analysis", response_model=Dict[str, Any], summary="Get deep analysis data")
async def get_deep_analysis_data():
    """
    Retrieve statistics about articles requiring deep analysis.
    """
    try:
        collection = await get_article_collection()
        
        # Get total counts
        total_articles = await collection.count_documents({})
        deep_analysis_count = await collection.count_documents({"llm_deep_analysis_results": {"$ne": None}})
        
        # Get deep analysis requirements distribution
        deep_analysis_pipeline = [
            {"$match": {"llm_requires_deep_analysis": {"$ne": None}}},
            {"$group": {"_id": "$llm_requires_deep_analysis", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}}
        ]
        deep_analysis_results_cursor = collection.aggregate(deep_analysis_pipeline)
        deep_analysis_results = await deep_analysis_results_cursor.to_list(length=None)
        
        deep_analysis_required = {}
        for result in deep_analysis_results:
            label = "Requires Deep Analysis" if result["_id"] else "Standard Analysis"
            deep_analysis_required[label] = result["count"]
            
        # Get source reliability metrics
        sources_reliability = {}
        source_pipeline = [
            {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}  # Top 10 sources
        ]
        source_results_cursor = collection.aggregate(source_pipeline)
        source_results = await source_results_cursor.to_list(length=None)
        
        for result in source_results:
            source = result["_id"]
            total_source_articles = result["count"]
            complex_articles = await collection.count_documents({
                "source_name": source, 
                "llm_requires_deep_analysis": True
            })
            if total_source_articles > 0:
                reliability_score = 1 - (complex_articles / total_source_articles)
                sources_reliability[source] = round(reliability_score * 100)  # As percentage
        
        return {
            "total_articles": total_articles,
            "deep_analysis_complete": deep_analysis_count,
            "deep_analysis_distribution": deep_analysis_required,
            "sources_reliability": sources_reliability
        }
    except Exception as e:
        logger.error(f"Error getting deep analysis data: {e}")
        return {"error": str(e)}

@router.get("/articles_by_sentiment/{sentiment_label}", response_model=Dict[str, Any], summary="Get articles by sentiment label")
async def get_articles_by_sentiment(sentiment_label: str):
    """
    Retrieve articles from the database filtered by a specific sentiment label.
    Projects only title, url, and source_name.
    """
    try:
        collection = await get_article_collection()
        query = {"llm_sentiment": sentiment_label}
        projection = {"title": 1, "url": 1, "source_name": 1, "_id": 0}
        
        articles_cursor = collection.find(query, projection)
        articles = await articles_cursor.to_list(length=None) # Get all matching articles
        
        return {"articles": articles}
    except Exception as e:
        logger.error(f"Error getting articles by sentiment '{sentiment_label}': {e}")
        return {"error": "Database error"}
