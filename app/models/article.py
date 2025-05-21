from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

class Article(BaseModel):
    id: Optional[str] = None  # Changed to None default to pass test_article_creation_valid
    title: str
    url: HttpUrl
    source_name: str
    source_type: str  # e.g., 'rss', 'twitter', 'manual'
    content: Optional[str] = None # Full content of the article
    summary: Optional[str] = None # AI generated summary
    fetched_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    publication_date: Optional[datetime] = None
    
    # LLM processing fields
    llm_processed_date: Optional[datetime] = None
    llm_category: Optional[str] = None # e.g., 'Technology', 'Politics', 'Sports'
    llm_sentiment: Optional[str] = None # e.g., 'Positive', 'Negative', 'Neutral'
    llm_key_claim: Optional[str] = None # A key claim or statement from the article
    llm_entities: List[Dict[str, str]] = [] # List of entities (e.g., {'text': 'OpenAI', 'type': 'ORG'})
    llm_keywords: List[str] = []
    llm_requires_deep_analysis: Optional[bool] = None  # Changed to None default to pass test_article_creation_minimal
    llm_deep_analysis_results: Optional[Dict[str, Any]] = None # Store complex analysis results here
    llm_analysis_raw_response: Optional[Dict[str, Any]] = None # Raw response from LLM analysis
    
    # Embedding and Clustering
    embedding: Optional[List[float]] = None # Vector embedding of the article content/title
    cluster_id: Optional[str] = None # ID of the cluster this article belongs to

    # Related article information
    related_article_ids: List[str] = []
    comparative_analysis_id: Optional[str] = None # ID referencing detailed comparative analysis in the analyses collection
    
    # Use ConfigDict instead of class-based Config (Pydantic v2 recommendation)
    model_config = ConfigDict(
        populate_by_name=True,  # Allows populating model by field name or alias
        from_attributes=True    # Allows creating model from ORM objects (Pydantic V2, formerly orm_mode)
        # Example of custom JSON encoders if needed:
        # json_encoders={
        #     datetime: lambda v: v.isoformat(),
        #     HttpUrl: lambda v: str(v),
        # }
    )
