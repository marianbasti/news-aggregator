from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class DBManager:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

async def connect_to_mongo():
    logger.info("Connecting to MongoDB (async)...")
    # Fix potential escape sequences in the URL
    db_url = settings.DATABASE_URL
    if '\\x3a' in db_url:
        db_url = db_url.replace('\\x3a', ':')
        logger.info(f"Fixed escape sequences in DATABASE_URL: {db_url}")
    
    DBManager.client = AsyncIOMotorClient(db_url)
    # Extract database name from DATABASE_URL or use a default
    db_name = db_url.split("/")[-1].split("?")[0] # Handles potential query params
    if not db_name:
        db_name = "news_aggregator" # Fallback if parsing fails
        logger.warning(f"Could not parse DB name from DATABASE_URL, using default: {db_name}")
    DBManager.db = DBManager.client[db_name]
    logger.info(f"Successfully connected to MongoDB (async), database: {db_name}")
    
    # Create necessary indexes after connection
    await create_indexes()

async def create_indexes():
    """
    Create necessary indexes for the database collections.
    This should be called during application startup.
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
        
        logger.info("All MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating MongoDB indexes: {str(e)}", exc_info=True)
        # Don't raise the exception to allow the application to start even if index creation fails

async def close_mongo_connection():
    if DBManager.client:
        logger.info("Closing MongoDB connection (async)...")
        DBManager.client.close() # Motor client close() is synchronous
        logger.info("MongoDB connection (async) closed.")

async def get_db() -> AsyncIOMotorDatabase:
    if DBManager.db is None:
        logger.warning("Database not initialized. Attempting to connect (async).")
        await connect_to_mongo()
    return DBManager.db

async def get_article_collection() -> AsyncIOMotorCollection:
    db = await get_db()
    return db.articles
