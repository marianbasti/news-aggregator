import logging
import json
from typing import Dict, Any, Optional
import re  # Add import for regular expressions

from openai import OpenAI, OpenAIError
from config.settings import settings

logger = logging.getLogger(__name__)

def repair_incomplete_json(possibly_incomplete_json: str) -> str:
    """
    Attempts to repair or truncate incomplete JSON to make it valid.
    
    Args:
        possibly_incomplete_json: A string that might contain incomplete JSON
        
    Returns:
        A valid JSON string or None if repair isn't possible
    """
    # First check if it's already valid
    try:
        json.loads(possibly_incomplete_json)
        return possibly_incomplete_json  # It's already valid
    except json.JSONDecodeError:
        pass  # Continue with repair attempts
    
    # Try to find the last complete JSON object by looking for balanced braces
    # This is a simplified approach and may not work for all cases
    incomplete_json = possibly_incomplete_json.strip()
    
    # Only attempt repair for objects starting with {
    if not incomplete_json.startswith('{'):
        logger.warning(f"Cannot repair JSON that doesn't start with '{{': {incomplete_json[:50]}...")
        return None
        
    # Count opening and closing braces
    depth = 0
    in_string = False
    escaped = False
    valid_until = 0
    
    for i, char in enumerate(incomplete_json):
        if in_string:
            if char == '\\' and not escaped:
                escaped = True
                continue
            elif char == '"' and not escaped:
                in_string = False
            escaped = False
        elif char == '"':
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            # If we've closed all braces, this could be a valid JSON endpoint
            if depth == 0:
                valid_until = i + 1
    
    # If we found a potential valid JSON substring
    if valid_until > 0:
        truncated_json = incomplete_json[:valid_until]
        try:
            # Verify it's actually valid
            json.loads(truncated_json)
            logger.info(f"Successfully repaired incomplete JSON by truncating at position {valid_until}")
            return truncated_json
        except json.JSONDecodeError:
            pass  # The truncated version still isn't valid
    
    # If we reach here, simple truncation didn't work
    logger.warning(f"Could not repair incomplete JSON: {incomplete_json[:50]}...")
    return None

def escape_curly_braces_except_content(template: str) -> str:
    """
    Escapes all curly braces in the template except for the {content} placeholder.
    This prevents .format() from misinterpreting JSON examples or schema braces.
    """
    # Replace all { and } with double braces, then restore {content}
    # Step 1: Replace { with {{ and } with }}
    escaped = template.replace('{', '{{').replace('}', '}}')
    # Step 2: Restore the {content} placeholder
    escaped = escaped.replace('{{content}}', '{content}')
    return escaped

class LLMService:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        # Fix for escaped URL characters
        base_url_from_settings = settings.OPENAI_BASE_URL
        if base_url_from_settings and '\\x3a' in base_url_from_settings:
            # Replace escaped colon with actual colon
            base_url_from_settings = base_url_from_settings.replace('\\x3a', ':')
            logger.info(f"Fixed escaped characters in base URL: {base_url_from_settings}")
            
        self.base_url = base_url or base_url_from_settings
        
        logger.debug(f"Initializing LLMService with base_url: {self.base_url}")
        
        if not self.api_key:
            logger.warning("OpenAI API key is not configured. LLM functionalities will be disabled.")
            self.client = None
        else:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"LLMService initialized. Using API base: {self.client.base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                self.client = None

    async def analyze_content(
        self, 
        content: str, 
        prompt_template: str,
        model: Optional[str] = None,
        max_tokens: int = 5000,
        temperature: float = 0.3,
        json_schema: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyzes the given content using an LLM based on the provided prompt template.

        Args:
            content: The text content to analyze (e.g., article summary or full text).
            prompt_template: A string template for the prompt. Must include a {content} placeholder.
            model: The LLM model to use.
            max_tokens: Maximum number of tokens for the response.
            temperature: Sampling temperature for the LLM.
            json_schema: Optional JSON schema to validate and format the LLM's response.

        Returns:
            A dictionary containing the structured analysis from the LLM, or None if an error occurs.
        """
        if not self.client:
            logger.error("LLM client not initialized. Cannot analyze content.")
            return None
        
        # Ensure prompt_template is a string and contains {content}
        if not isinstance(prompt_template, str) or "{content}" not in prompt_template:
            logger.error("Prompt template must be a string and include a '{content}' placeholder.")
            return None

        # Escape curly braces except for {content}
        prompt_template = escape_curly_braces_except_content(prompt_template)

        try:
            formatted_prompt = prompt_template.format(content=content)
        except KeyError as e:
            logger.error(f"Error formatting prompt template: {e}. This likely means the template contains unescaped curly braces that look like placeholders. Double curly braces {{{{ }}}} should be used for literal braces in template.")
            return {"analysis_text": "", "error": f"Prompt template formatting error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error formatting prompt template: {e}", exc_info=True)
            return {"analysis_text": "", "error": f"Prompt template error: {str(e)}"}
        
        # Determine the model to use
        # If a model is passed directly to this function, use it.
        # Otherwise, fall back to the default model from settings.
        target_model = settings.DEFAULT_LLM_MODEL_NAME

        try:
            logger.debug(f"Sending request to LLM. Model: {target_model}, Prompt: {formatted_prompt[:200]}...") # Log snippet
            
            # Prepare the messages for the LLM
            messages = [
                {"role": "system", "content": "You are an AI assistant performing detailed content analysis. Respond with a valid JSON object based on the user's instructions."},
                {"role": "user", "content": formatted_prompt}
            ]
            
            # Prepare the request parameters
            request_params = {
                "model": target_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            # Add response_format based on the parameters
            if json_schema:
                # Use the tools/function calling API with JSON schema for more control
                logger.debug(f"Using JSON schema for response formatting: {json_schema}")
                
                # Define a function that will return data conforming to our schema
                function_def = {
                    "name": "format_article_analysis",
                    "description": "Format the analysis of an article according to the specified schema",
                    "parameters": json_schema
                }
                
                # Configure the request to use the function calling API
                # This forces the LLM to return data that conforms to our schema
                request_params["tools"] = [{"type": "function", "function": function_def}]
                request_params["tool_choice"] = {"type": "function", "function": {"name": "format_article_analysis"}}
                
                # Add max_tokens parameter if not already set to ensure we get complete responses
                if "max_tokens" not in request_params or request_params["max_tokens"] < 1000:
                    # Ensure we have enough tokens for a complete response based on the schema complexity
                    schema_complexity = len(json.dumps(json_schema))
                    # Scale tokens based on schema size with a minimum of 1000
                    request_params["max_tokens"] = max(1000, min(4000, schema_complexity * 3))
                    logger.debug(f"Adjusted max_tokens to {request_params['max_tokens']} based on schema complexity")
                
                logger.debug("Using function calling API for structured JSON output")
            else:
                # Use the simpler response_format for basic JSON responses
                request_params["response_format"] = {"type": "json_object"}
                logger.debug("Using standard JSON response format")
                
            # Make the API call
            response = self.client.chat.completions.create(**request_params)
            
            # Initialize analysis_text to None
            analysis_text = None
            
            # Check if we got a valid response object
            if response is None or not hasattr(response, 'choices') or not response.choices:
                logger.warning("LLM returned an invalid or empty response structure")
            # Process the response based on whether we used tools API or simple response_format
            elif json_schema and hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                # Extract the function call result from tools API
                tool_call = response.choices[0].message.tool_calls[0]
                analysis_text = tool_call.function.arguments
                logger.info(f"LLM analysis via JSON schema tool: '{analysis_text}'")
                
                # Check if the returned JSON is complete and valid
                try:
                    json.loads(analysis_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"Received truncated or invalid JSON from LLM: {e}")
                    analysis_text = None  # Reset to trigger the default response below
            else:
                # Extract standard response
                if hasattr(response.choices[0].message, 'content'):
                    analysis_text = response.choices[0].message.content
                    logger.info(f"LLM analysis raw response: '{analysis_text}'")
                else:
                    logger.warning("Response message missing expected 'content' field")
            
            # Log the length if we have a response
            if analysis_text:
                logger.info(f"LLM analysis received successfully. Length: {len(analysis_text)}")
            
            # If the response is empty or None, create a default JSON string
            if not analysis_text or analysis_text.strip() == "":
                logger.warning("LLM returned an empty response, providing default JSON")
                default_json = json.dumps({
                    "category": "Uncategorized",
                    "sentiment": "Neutral",
                    "key_claim": "No key claim detected",
                    "requires_deep_analysis": "no",
                    "keywords": [],
                    "main_entities": [],
                    "error": "Empty LLM response"
                })
                return {"analysis_text": default_json}
            
            # Validate JSON before returning it
            if json_schema:
                try:
                    # Try to parse the JSON to ensure it's valid and complete
                    parsed_json = json.loads(analysis_text)
                    # Return the validated JSON
                    return {"analysis_text": analysis_text}
                except json.JSONDecodeError as e:
                    logger.warning(f"Received potentially incomplete JSON: {e}")
                    
                    # Try to repair the JSON
                    repaired_json = repair_incomplete_json(analysis_text)
                    if repaired_json:
                        logger.info("Successfully repaired incomplete JSON response")
                        return {"analysis_text": repaired_json}
                    
                    # If repair failed, return a default response
                    logger.error(f"Invalid JSON in LLM response and repair failed: {e}")
                    default_json = json.dumps({
                        "category": "Uncategorized",
                        "sentiment": "Neutral",
                        "key_claim": "JSON parsing error",
                        "requires_deep_analysis": "no",
                        "keywords": [],
                        "main_entities": [],
                        "error": f"Invalid JSON response: {str(e)}"
                    })
                    return {"analysis_text": default_json}
            
            # Return the normal response if we have content
            return {"analysis_text": analysis_text}

        except OpenAIError as e:
            logger.error(f"OpenAI API error during content analysis: {e}", exc_info=True)
            # Check if this is a function calling validation error
            error_msg = str(e).lower()
            if json_schema and ("schema" in error_msg or "validation" in error_msg or "function" in error_msg):
                return {
                    "analysis_text": "", 
                    "error": f"JSON schema validation error: {str(e)}",
                    "schema_error": True
                }
            return {"analysis_text": "", "error": f"OpenAI API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error during content analysis: {e}", exc_info=True)
            return {"analysis_text": "", "error": f"Unexpected error: {str(e)}"}

# Example usage (for testing, not part of the service itself)
async def example_main():
    if not settings.OPENAI_API_KEY:
        print("Skipping LLM service example: OPENAI_API_KEY not set.")
        return

    llm_service = LLMService()
    if not llm_service.client:
        print("LLM client could not be initialized.")
        return

    sample_content = (
        "A new study published in Nature today reveals that certain species of deep-sea "
        "bacteria can metabolize plastic. This could lead to new bio-remediation "
        "strategies for ocean pollution. However, scientists caution that the process is slow "
        "and not a silver bullet for the plastic crisis."
    )
    
    # Prompt for initial triage and categorization
    triage_prompt = """
    Analyze the following news article content:
    {content}

    Based on this content, provide the following:
    1. Category (e.g., Science, Technology, Politics, Environment, Health, Business, Other).
    2. Sentiment (Positive, Negative, Neutral).
    3. Key Claim (a concise summary of the main assertion or finding).
    4. Requires Deeper Analysis (Yes/No - flag 'Yes' if the topic is complex, controversial, or has significant societal impact).
    5. Keywords (3-5 specific, descriptive keywords related to the article topic).

    Return your response as a JSON object with keys: "category", "sentiment", "key_claim", "requires_deep_analysis", "keywords".
    """
    
    # JSON schema for controlled response format
    triage_schema = {
        "type": "object",
        "required": ["category", "sentiment", "key_claim", "requires_deep_analysis", "keywords"],
        "properties": {
            "category": {
                "type": "string",
                "description": "The main category of the article",
                "enum": ["Science/Technology", "Politics", "Environment", "Health", "Business", "Sports", "Other"]
            },
            "sentiment": {
                "type": "string",
                "description": "The nuanced sentiment or tone of the article",
                "enum": [
                    "Optimistic",       # Positive outlook on future developments
                    "Encouraging",      # Presents positive developments
                    "Celebratory",      # Commemorating achievements or milestones
                    "Critical",         # Points out flaws or concerns
                    "Cautionary",       # Warning about potential risks
                    "Alarming",         # Raising serious concerns about danger or threats
                    "Factual",          # Primarily fact-based reporting without obvious bias
                    "Analytical",       # In-depth analysis with balanced perspective
                    "Balanced",         # Deliberately presents multiple viewpoints
                    "Controversial",    # Contains polarizing content or perspectives
                    "Sensationalist",   # Exaggerated or dramatic presentation
                    "Mixed"             # Contains multiple sentiment elements
                ]
            },
            "key_claim": {
                "type": "string",
                "description": "A concise summary of the main assertion or finding"
            },
            "requires_deep_analysis": {
                "type": "string",
                "description": "Flag if the topic is complex, controversial, or needs further verification",
                "enum": ["Yes", "No"]
            },
            "keywords": {
                "type": "array",
                "description": "3-5 specific, descriptive keywords related to the article topic",
                "items": {
                    "type": "string"
                },
                "minItems": 3,
                "maxItems": 5
            }
        }
    }
    
    # First, try without schema
    print(f"Analyzing content with basic triage prompt...")
    basic_result = await llm_service.analyze_content(sample_content, triage_prompt)
    
    if basic_result:
        print("Basic Analysis Result:")
        print(basic_result)
    else:
        print("Basic analysis failed.")
    
    # Then try with schema
    print(f"\nAnalyzing content with JSON schema...")
    schema_result = await llm_service.analyze_content(
        content=sample_content, 
        prompt_template=triage_prompt,
        json_schema=triage_schema
    )
    
    if schema_result:
        print("Schema-Based Analysis Result:")
        print(schema_result)
    else:
        print("Schema-based analysis failed.")

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_main())
