"""
One-time script to create necessary MongoDB indexes for the news aggregator.
Run this script to ensure all required indexes are properly created.
"""
import asyncio
import logging
from app.db import connect_to_mongo, close_mongo_connection, get_article_collection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def create_mongodb_indexes():
    """
    Create all necessary indexes for MongoDB collections.
    """
    logger.info("Creating MongoDB indexes...")
    try:
        # Get the articles collection
        collection = await get_article_collection()
        
        # Create a text index on title, content, and llm_key_claim fields
        # This enables full-text search capabilities
        await collection.create_index(
            [
                ("title", "text"), 
                ("content", "text"), 
                ("llm_key_claim", "text")
            ], 
            name="article_text_search_index"
        )
        logger.info("Text search index created for articles collection")
        
        # Create index on publication_date for faster date-based queries
        await collection.create_index(
            [("publication_date", 1)],
            name="publication_date_index"
        )
        
        # Create index on source_name for faster source filtering
        await collection.create_index(
            [("source_name", 1)],
            name="source_name_index"
        )
        
        # Create index on llm_category for faster category filtering
        await collection.create_index(
            [("llm_category", 1)],
            name="category_index"
        )
        
        # Create index on URL for faster retrieval and deduplication
        await collection.create_index(
            [("url", 1)],
            unique=True,
            name="url_unique_index"
        )
        
        logger.info("All MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating MongoDB indexes: {str(e)}", exc_info=True)

async def main():
    """
    Main function that connects to the database, creates indexes, and then closes the connection.
    """
    await connect_to_mongo()
    await create_mongodb_indexes()
    await close_mongo_connection()

# Execute the script
if __name__ == "__main__":
    asyncio.run(main())
