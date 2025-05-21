import pytest
import mongomock
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import your FastAPI app and settings
# Adjust the import path based on your project structure if needed
from app.main import app
from config.settings import Settings
from app.db import DBManager, get_db, connect_to_mongo, close_mongo_connection

# Override settings for testing
def get_settings_override():
    return Settings(
        DATABASE_URL="mongodb://localhost:27017/test_news_aggregator", # Use a test DB name
        RSS_FEEDS=["http://test.com/rss1", "http://test.com/rss2"],
        OPENAI_API_KEY="test_openai_api_key", # Use a dummy key
        # OPENAI_API_BASE_URL="http://localhost:1234/v1" # Dummy base URL - Removed
    )

# Fixture to override settings for the duration of a test session
@pytest.fixture(scope="session", autouse=True)
def override_app_settings(session_mocker):
    # This uses pytest-mock's session_mocker to patch settings globally for tests
    # This approach is cleaner if your app directly imports 'settings' from config.settings
    session_mocker.patch("app.db.settings", get_settings_override())
    session_mocker.patch("app.services.rss_fetcher.settings", get_settings_override())
    session_mocker.patch("app.services.llm_service.settings", get_settings_override())
    # Add other modules that import 'settings' directly if necessary

@pytest.fixture(scope="session")
def db_manager_session():
    """Session-scoped fixture to manage DB connection for all tests."""
    # Ensure settings are overridden before connecting
    test_settings = get_settings_override()
    DBManager.client = mongomock.MongoClient(test_settings.DATABASE_URL)
    db_name = test_settings.DATABASE_URL.split("/")[-1]
    DBManager.db = DBManager.client[db_name]
    print(f"Mock MongoDB setup for session at {test_settings.DATABASE_URL}")
    yield DBManager
    print("Mock MongoDB closing for session.")
    if DBManager.client:
        DBManager.client.close()
    DBManager.client = None
    DBManager.db = None


@pytest.fixture
def mock_db(db_manager_session):
    """Provides a mock database instance for a test, ensuring it's clean."""
    db = db_manager_session.db
    # Clean up collections before each test if needed, or manage per-test data
    # For example, to clear the 'articles' collection:
    # db.articles.delete_many({})
    return db

@pytest.fixture
def article_collection(mock_db):
    """Provides a clean 'articles' collection for each test."""
    collection = mock_db.articles
    collection.delete_many({}) # Clear before each test using this fixture
    return collection


# Fixture for an AsyncTestClient, configured for your app
@pytest.fixture(scope="module")
async def async_client(): # Changed scope to module for efficiency
    # Ensure DB is connected using overridden settings before client is created
    # The db_manager_session fixture should handle this if autouse=True or if it's explicitly used
    # by another fixture that this client depends on.
    # For safety, we can explicitly call connect_to_mongo here,
    # but it should use the mocked DBManager.client
    
    # This is tricky because app startup/shutdown events handle DB connection.
    # TestClient/AsyncClient for FastAPI handles lifespan events.

    async with AsyncClient(app=app, base_url="http://test") as client:
        print("AsyncTestClient created")
        yield client
        print("AsyncTestClient closing")

# If you need a synchronous TestClient (e.g., for non-async parts or simpler tests)
@pytest.fixture(scope="module")
def client():
    # This will also trigger startup/shutdown events if app has them
    with TestClient(app) as c:
        yield c

# Example RSS feed data
@pytest.fixture
def mock_rss_feed_data_valid():
    return {
        "http://test.com/rss1": {
            "feed": {"title": "Test Feed 1"},
            "entries": [
                {
                    "title": "Article 1",
                    "link": "http://test.com/article1",
                    "published_parsed": (2023, 1, 1, 12, 0, 0, 0, 1, 0),
                    "summary": "Summary 1"
                },
                {
                    "title": "Article 2",
                    "link": "http://test.com/article2",
                    "published_parsed": (2023, 1, 2, 12, 0, 0, 0, 2, 0),
                    "summary": "Summary 2"
                }
            ]
        },
        "http://test.com/rss2": {
            "feed": {"title": "Test Feed 2"},
            "entries": [
                {
                    "title": "Article 3",
                    "link": "http://test.com/article3",
                    "published_parsed": (2023, 1, 3, 12, 0, 0, 0, 3, 0),
                    "summary": "Summary 3"
                }
            ]
        }
    }

@pytest.fixture
def mock_rss_feed_data_empty():
    return {
        "http://test.com/rss1": {
            "feed": {"title": "Empty Feed"},
            "entries": []
        }
    }

@pytest.fixture
def mock_llm_triage_response_valid():
    return {
        "analysis_text": '{"category": "Technology", "sentiment": "Neutral", "key_claim": "Test key claim", "requires_deep_analysis": "No"}'
    }

@pytest.fixture
def mock_llm_deep_analysis_response_valid():
    return {
        "analysis_text": '{"political_leaning_detected": "Centrist", "bias_indicators": [], "main_arguments": ["Arg1"], "verifiable_claims_count": 1, "cites_sources_within_text": true, "analysis_confidence": "High"}'
    }

