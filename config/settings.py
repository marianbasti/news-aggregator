from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    APP_NAME: str = "News Aggregator"
    DEBUG: bool = False
    DATABASE_URL: str = "mongodb://localhost:27017/news_aggregator"
    RSS_FEEDS: List[str] = [
        "https://www.perfil.com/feed", # Perfil
        "https://www.lanacion.com.ar/arc/outboundfeeds/rss/", # La Nación
        "https://www.clarin.com/rss/lo-ultimo/", # Clarín
        "https://www.infobae.com/arc/outboundfeeds/rss/", # Infobae
        "https://www.cronista.com/rss/", # El Cronista
        "https://www.pagina12.com.ar/rss/portada", # Página 12
        "https://www.ambito.com/rss/pages/home.xml", # Ámbito
        "https://www.laizquierdadiario.com/spip.php?page=backend_portada", # La Izquierda Diario
        "https://derechadiario.com.ar/rss/last-posts", # Derecha Diario
        "https://www.lavoz.com.ar/arc/outboundfeeds/feeds/rss/noticias/", # La Voz
        "https://www.diarioregistrado.com/rss.xml", # Diario Registrado
    ]
    # For later: OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None # e.g., "https://api.openai.com/v1" or local LLM endpoint

    # LLM Model Names
    DEFAULT_LLM_MODEL_NAME: str = "gpt-3.5-turbo"
    TRIAGE_LLM_MODEL_NAME: Optional[str] = None # If None, will use DEFAULT_LLM_MODEL_NAME
    DEEP_ANALYSIS_LLM_MODEL_NAME: str = "gpt-4-turbo-preview"
    
    # Use SettingsConfigDict instead of class-based Config
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8"
    )

settings = Settings()
