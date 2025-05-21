from fastapi import APIRouter, HTTPException, Query, BackgroundTasks # Added BackgroundTasks
from typing import List, Dict, Any
import logging

from app.services.rss_fetcher import fetch_all_articles
from app.models.article import Article
from app.services import article_service # Adjusted import

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch", response_model=Dict[str, Any], summary="Fetch articles from RSS and save to DB")
async def fetch_and_save_articles_endpoint():
    """
    Fetches articles from all configured RSS feeds and saves them to the database.
    This step no longer includes immediate LLM analysis.
    Returns a summary of the operation including counts of inserted/updated articles.
    """
    try:
        logger.info("API: Initiating article fetch from all RSS feeds.")
        fetched_articles = fetch_all_articles()
        
        if not fetched_articles:
            logger.info("API: No new articles were fetched from RSS feeds.")
            return {"message": "No new articles fetched.", "inserted": 0, "updated": 0, "failed": 0}

        logger.info(f"API: Fetched {len(fetched_articles)} articles. Attempting to save to DB.")
        save_result = await article_service.save_articles(fetched_articles) # Use service object
        
        logger.info(f"API: Save operation completed. Results: {save_result}")
        return {
            "message": "Articles fetched and processed.",
            "fetched_count": len(fetched_articles),
            "inserted_count": save_result.get("inserted", 0),
            "updated_count": save_result.get("updated", 0),
            "failed_count": save_result.get("failed", 0)
            # Removed analyzed_count as it's now a separate step
        }
    except Exception as e:
        logger.error(f"API: Error in fetch_and_save_articles_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch and save articles: {str(e)}")

@router.post("/triage", response_model=Dict[str, Any], summary="Perform LLM triage analysis on new articles")
async def triage_new_articles_endpoint(background_tasks: BackgroundTasks, limit: int = Query(50, ge=1, le=200, description="Max number of articles to triage")):
    """
    Performs LLM-based triage analysis on articles that haven't been analyzed yet.
    The analysis is run as a background task.
    
    This process also identifies and links related articles by analyzing keywords, entities, 
    and content similarity. The articles' 'related_article_ids' field will be updated to contain
    IDs of articles covering the same news story.
    """
    try:
        logger.info(f"API: Initiating LLM triage for up to {limit} new articles in the background.")
        background_tasks.add_task(article_service.triage_new_articles, limit=limit)
        return {
            "message": f"LLM triage process for up to {limit} articles initiated in the background. "
                      f"This process will also identify and link related articles covering the same news stories.",
        }
    except Exception as e:
        logger.error(f"API: Error in triage_new_articles_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initiate LLM triage: {str(e)}")

@router.post("/{article_id}/analyze-deeply", response_model=Article, summary="Perform deep analysis on an article", tags=["Articles"]) # Added tags
async def deep_analyze_article_endpoint(article_id: str):
    """
    Triggers a deep analysis for a specific article using a more powerful LLM.
    The article must exist in the database.
    """
    try:
        logger.info(f"API: Initiating deep analysis for article_id: {article_id}")
        updated_article = await article_service.perform_deep_article_analysis(article_id)
        
        if not updated_article:
            # This case might be hit if article_id is invalid format before DB call, or DB call returns None
            raise HTTPException(status_code=404, detail=f"Article with id {article_id} not found, or analysis could not proceed.")
        
        # Check if the deep analysis field was populated, and if it contains an error marker from the service layer
        if not updated_article.llm_deep_analysis_results or \
           (isinstance(updated_article.llm_deep_analysis_results, dict) and updated_article.llm_deep_analysis_results.get("error")):
            logger.warning(f"API: Deep analysis for article {article_id} may have resulted in an error or no new data. Response: {updated_article.llm_deep_analysis_results}")
            # Decide on response: could be 200 with the article (containing error) or an error status
            # For now, returning the article as the service layer handles storing error details.
            # Consider raising HTTPException(status_code=500, detail=f"Deep analysis for article {article_id} failed or produced no data.") if preferred.

        logger.info(f"API: Deep analysis attempt completed for article_id: {article_id}")
        return updated_article
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error in deep_analyze_article_endpoint for article_id {article_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to perform deep analysis on article {article_id}: {str(e)}")

@router.get("/", response_model=List[Article], summary="Get articles from the database")
async def list_articles_endpoint(
    skip: int = Query(0, ge=0, description="Number of articles to skip for pagination"), 
    limit: int = Query(20, ge=1, le=100, description="Maximum number of articles to return")
):
    """Retrieves a paginated list of articles from the database."""
    try:
        articles = await article_service.list_articles(skip=skip, limit=limit) # Use service object
        if not articles:
            logger.info(f"API: No articles found in DB for skip={skip}, limit={limit}")
        return articles
    except Exception as e:
        logger.error(f"API: Error retrieving articles from DB: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve articles from database.")

@router.get("/{article_id}/related", response_model=List[Article], summary="Get articles related to the same news story")
async def get_related_articles_endpoint(article_id: str):
    """
    Retrieves all articles that are related to the same news story as the specified article.
    These are articles that have been identified as covering the same news event or topic.
    
    The relatedness is determined during the triage process by analyzing:
    - Content similarity (keywords and entities)
    - Publication date proximity
    - Title similarity
    - Category match
    """
    try:
        logger.info(f"API: Getting related articles for article_id: {article_id}")
        related_articles = await article_service.get_related_articles(article_id)
        
        if not related_articles:
            logger.info(f"API: No related articles found for article_id: {article_id}")
            return []
            
        logger.info(f"API: Found {len(related_articles)} related articles for article_id: {article_id}")
        return related_articles
    except Exception as e:
        logger.error(f"API: Error getting related articles for article_id {article_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get related articles: {str(e)}")

@router.post("/{article_id}/comparative-analysis", response_model=Dict[str, Any], summary="Perform comparative analysis on related articles")
async def analyze_related_articles_endpoint(article_id: str, background_tasks: BackgroundTasks, run_in_background: bool = Query(False, description="Run analysis as a background task")):
    """
    Performs a comparative analysis on all articles related to the same news story as the specified article.
    
    This analysis identifies differences in how different sources cover the same story, including:
    - Information gaps between sources
    - Variations in framing and language
    - Differences in focus and emphasis
    - Potential source interests and motivations
    
    Returns the analysis results or, if run in background mode, a status message.
    """
    try:
        logger.info(f"API: Initiating comparative analysis for articles related to article_id: {article_id}")
        
        # First, get related articles to check if we have enough for comparison
        related_articles = await article_service.get_related_articles(article_id)
        
        if not related_articles or len(related_articles) < 2:
            logger.warning(f"API: Not enough related articles found for comparative analysis. Found: {len(related_articles) if related_articles else 0}")
            raise HTTPException(status_code=400, detail="Insufficient related articles for comparison (minimum 2 required)")
        
        # Include the original article in the analysis if it's not already in the related list
        all_article_ids = [str(article.id) for article in related_articles]
        if article_id not in all_article_ids:
            all_article_ids.append(article_id)
            
        logger.info(f"API: Performing comparative analysis on {len(all_article_ids)} articles")
        
        if run_in_background:
            background_tasks.add_task(article_service.perform_comparative_analysis, all_article_ids)
            return {
                "status": "processing",
                "message": f"Comparative analysis of {len(all_article_ids)} related articles has been initiated in the background",
                "article_count": len(all_article_ids)
            }
        else:
            # Run analysis synchronously
            analysis_results = await article_service.perform_comparative_analysis(all_article_ids)
            
            if "error" in analysis_results:
                # Still return a 200 status, but with the error information in the response
                logger.warning(f"API: Comparative analysis completed with errors: {analysis_results['error']}")
                return analysis_results
                
            logger.info(f"API: Comparative analysis completed successfully for {len(all_article_ids)} articles")
            return analysis_results
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"API: Error performing comparative analysis for article_id {article_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to perform comparative analysis: {str(e)}")

@router.get("/{article_id}/comparative-analysis", response_model=Dict[str, Any], summary="Get comparative analysis for an article")
async def get_comparative_analysis_endpoint(article_id: str):
    """
    Retrieves the previously generated comparative analysis associated with this article.
    
    The comparative analysis shows how different sources cover the same news story, including:
    - Core facts agreed upon across all sources
    - Source-specific differences in coverage
    - Information gaps between sources
    - Variations in framing and language
    - Potential source interests and motivations
    
    Returns the analysis results or a 404 if no analysis exists.
    """
    try:
        logger.info(f"API: Getting comparative analysis for article_id: {article_id}")
        
        analysis_results = await article_service.get_comparative_analysis_for_article(article_id)
        
        if not analysis_results:
            # No analysis found for this article
            logger.info(f"API: No comparative analysis found for article_id: {article_id}")
            raise HTTPException(status_code=404, detail="No comparative analysis found for this article")
            
        logger.info(f"API: Found comparative analysis for article_id: {article_id}")
        return analysis_results
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"API: Error retrieving comparative analysis for article_id {article_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve comparative analysis: {str(e)}")
