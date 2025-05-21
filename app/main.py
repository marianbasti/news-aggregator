from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import uvicorn

# Configure basic logging once
# Ensure the format is set for better readability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import DB connection functions
from app.api import articles  # Absolute import from 'app' package
from app.api import db_visualization  # Import the new DB visualization router
from app.db import connect_to_mongo, close_mongo_connection, create_indexes # Added create_indexes import

# Define a lifespan context manager to replace on_event handlers
@asynccontextmanager
async def lifespan(app):
    # Startup logic
    logger.info("Application is starting up...")
    await connect_to_mongo()  # Connect to DB asynchronously (this also creates indexes)
    # Future: Initialize database connections, load ML models, etc.
    
    yield  # App runs here
    
    # Shutdown logic
    logger.info("Application is shutting down...")
    await close_mongo_connection()  # Close DB connection asynchronously
    # Future: Close database connections, cleanup resources, etc.

# Create FastAPI app with the lifespan manager
app = FastAPI(
    title="News Aggregator API",
    version="0.1.0",
    description="API for discovering, analyzing, and presenting news from various sources.",
    lifespan=lifespan
)

@app.get("/health", tags=["System"])
async def health_check():
    """Provides a basic health check for the application."""
    return {"status": "healthy", "message": "News Aggregator API is running."}

# Include routers from the api module
app.include_router(articles.router, prefix="/api/articles", tags=["Articles"])
logger.info("Articles API router included at prefix /api/articles")

# Include the DB visualization router
app.include_router(db_visualization.router, prefix="/api/db", tags=["Database"])
logger.info("DB Visualization API router included at prefix /api/db")


if __name__ == "__main__":
    # This block allows running the app directly using:
    # python app/main.py
    #
    # For development, Uvicorn's auto-reload feature is very helpful.
    # It's generally recommended to run Uvicorn from the command line in the project root:
    # source .venv/bin/activate
    # uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    #
    # The programmatic approach below is for convenience.
    logger.info("Attempting to start Uvicorn server programmatically for development...")
    uvicorn.run(
        "app.main:app",  # Path to the FastAPI app instance as a string
        host="0.0.0.0",
        port=8000,
        reload=True,      # Enable auto-reload (watches for file changes)
        log_level="info"  # Set Uvicorn's own log level
    )
