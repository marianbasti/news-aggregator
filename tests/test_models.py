import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from app.models.article import Article # Adjust import if your structure differs


def test_article_creation_valid():
    """Test successful creation of an Article with all required fields and valid types."""
    now = datetime.now(timezone.utc)
    article_data = {
        "title": "Test Title",
        "url": "http://example.com/article1",
        "source_name": "Example Source",
        "source_type": "rss",  # Adding required source_type field
        "publication_date": now - timedelta(days=1),
        "summary": "This is a test summary.",
        "content": "This is the full text of the test article.",
        "llm_category": "Technology",
        "llm_sentiment": "Neutral",
        "llm_key_claim": "Test claim.",
        "llm_requires_deep_analysis": False,
        "llm_analysis_raw_response": {"raw": "data"},
        "llm_deep_analysis_results": {"deep": "analysis"},
        "related_article_ids": []  # Adding the new related_article_ids field
    }
    article = Article(**article_data)

    assert article.title == article_data["title"]
    assert str(article.url) == article_data["url"]
    assert article.source_name == article_data["source_name"]
    assert article.publication_date == article_data["publication_date"]
    assert article.summary == article_data["summary"]
    assert article.content == article_data["content"]
    
    # Check fetched_date is set and timezone-aware
    assert article.fetched_date is not None
    assert article.fetched_date.tzinfo == timezone.utc
    # Check it's recent (e.g., within the last few seconds)
    assert (now - article.fetched_date).total_seconds() < 5 

    # Check LLM fields
    assert article.llm_category == article_data["llm_category"]
    assert article.llm_sentiment == article_data["llm_sentiment"]
    assert article.llm_key_claim == article_data["llm_key_claim"]
    assert article.llm_requires_deep_analysis == article_data["llm_requires_deep_analysis"]
    assert article.llm_analysis_raw_response == article_data["llm_analysis_raw_response"]
    assert article.llm_deep_analysis_results == article_data["llm_deep_analysis_results"]

    # ID should be None by default unless provided
    assert article.id is None

def test_article_creation_minimal():
    """Test successful creation with only absolutely required fields."""
    article_data = {
        "title": "Minimal Test Title",
        "url": "http://minimal.example.com/",
        "source_name": "Minimal Source",
        "source_type": "manual"  # Adding required source_type field
    }
    article = Article(**article_data)
    assert article.title == article_data["title"]
    assert str(article.url) == article_data["url"]
    assert article.source_name == article_data["source_name"]
    
    # Optional fields should be None or their defaults
    assert article.publication_date is None
    assert article.summary is None
    assert article.content is None
    assert article.llm_category is None
    assert article.llm_sentiment is None
    assert article.llm_key_claim is None
    assert article.llm_requires_deep_analysis is None
    assert article.llm_analysis_raw_response is None
    assert article.llm_deep_analysis_results is None

    assert article.fetched_date is not None
    assert article.fetched_date.tzinfo == timezone.utc

def test_article_invalid_url():
    """Test Pydantic validation for an invalid URL."""
    with pytest.raises(ValidationError) as excinfo:
        Article(
            title="Invalid URL Test",
            url="not-a-valid-url", # Invalid URL
            source_name="Test Source",
            source_type="rss"
        )
    assert "url" in str(excinfo.value).lower() # Check that the error message mentions 'url'
    # More specific error checking if needed:
    # assert any(e['type'] == 'url_type' for e in excinfo.value.errors())

def test_article_publication_date_handling():
    """Test that publication_date can be None or a datetime object."""
    now = datetime.now(timezone.utc)
    
    # With publication_date
    article1 = Article(
        title="Date Test 1", 
        url="http://example.com/date1", 
        source_name="Date Source",
        source_type="rss",
        publication_date=now
    )
    assert article1.publication_date == now

    # Without publication_date (should be None)
    article2 = Article(
        title="Date Test 2", 
        url="http://example.com/date2", 
        source_name="Date Source",
        source_type="rss"
    )
    assert article2.publication_date is None

def test_article_fetched_date_default_timezone_aware():
    """Test that fetched_date is automatically set and is timezone-aware (UTC)."""
    article = Article(
        title="Fetched Date Test", 
        url="http://example.com/fetched", 
        source_name="Fetched Source",
        source_type="manual"
    )
    assert article.fetched_date is not None
    assert article.fetched_date.tzinfo == timezone.utc
    # Check it's very recent
    assert (datetime.now(timezone.utc) - article.fetched_date).total_seconds() < 2

