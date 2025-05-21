import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone
import logging

from app.models.article import Article
from config.settings import settings

logger = logging.getLogger(__name__)

def fetch_articles_from_feed(feed_url: str) -> List[Article]:
    """Fetches and parses articles from a single RSS feed URL."""
    parsed_feed = feedparser.parse(feed_url)
    articles: List[Article] = []

    source_name = parsed_feed.feed.get("title", "Unknown Source")

    for entry in parsed_feed.entries:
        try:
            # Attempt to parse publication date
            pub_date_parsed = entry.get("published_parsed")
            if pub_date_parsed:
                publication_date = datetime(*pub_date_parsed[:6], tzinfo=timezone.utc)
            else:
                publication_date = datetime.now(timezone.utc) # Fallback if no date

            article = Article(
                title=entry.title,
                url=entry.link,
                source_name=source_name,
                source_type="rss", # Adding the required source_type field
                publication_date=publication_date,
                summary=entry.get("summary"),
                # full_text might require fetching the actual page, skip for now
            )
            articles.append(article)
        except Exception as e:
            logger.error(f"Error parsing entry from {feed_url}: {entry.get('title')} - {e}")
    return articles

def fetch_all_articles() -> List[Article]:
    """Fetches articles from all configured RSS feeds."""
    all_articles: List[Article] = []
    for feed_url in settings.RSS_FEEDS:
        logger.info(f"Fetching articles from: {feed_url}")
        try:
            articles_from_feed = fetch_articles_from_feed(feed_url)
            all_articles.extend(articles_from_feed)
            logger.info(f"Fetched {len(articles_from_feed)} articles from {feed_url}")
        except Exception as e:
            logger.error(f"Failed to fetch or parse feed {feed_url}: {e}")
    return all_articles

# Remove test code that's not needed in production
