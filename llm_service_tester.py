import asyncio
import logging
from app.services.llm_service import LLMService
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_llm():
    llm_service = LLMService()
    
    sample_content = """
    A new study published in Nature today reveals that certain species of deep-sea 
    bacteria can metabolize plastic. This could lead to new bio-remediation 
    strategies for ocean pollution. However, scientists caution that the process is slow 
    and not a silver bullet for the plastic crisis.
    """
    
    triage_prompt = """
    Analyze the following news article content:
    {content}

    Based on this content, provide the following:
    1. Category (e.g., Science, Technology, Politics, Environment, Health, Business, Other).
    2. Sentiment (Positive, Negative, Neutral).
    3. Key Claim (a concise summary of the main assertion or finding).
    4. Requires Deeper Analysis (Yes/No - flag 'Yes' if the topic is complex, controversial, or has significant societal impact).
    5. Main Entities (list of key people, organizations, or entities mentioned).
    6. Keywords (list of 3-5 key terms that best represent the article).

    Return your response as a JSON object with keys: "category", "sentiment", "key_claim", "requires_deep_analysis", "main_entities", "keywords".
    """
    
    logger.info("Testing LLM service with sample content...")
    analysis_result = await llm_service.analyze_content(
        content=sample_content,
        prompt_template=triage_prompt,
        model=settings.DEFAULT_LLM_MODEL_NAME
    )
    
    logger.info(f"Analysis result: {analysis_result}")
    
    if "error" in analysis_result:
        logger.error(f"Error in LLM response: {analysis_result['error']}")
    else:
        logger.info("LLM analysis successful")

if __name__ == "__main__":
    asyncio.run(test_llm())
