import requests
import json
from boombot.core.config import LLM_API_KEY
import logging

logger = logging.getLogger(__name__)

def get_openrouter_response(question: str) -> str:
    """Get a response from OpenRouter API for the given question.
    
    Args:
        question: The question or prompt to send to the LLM
        
    Returns:
        The LLM's response as a string
    """
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY not set in environment variables")
        return f"Unable to process: '{question}' - API key not configured"
        
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        data=json.dumps({
            "model": "opengvlab/internvl3-2b:free",
            "messages": [
                {
                    "role": "user",
                    "content": f"Provide a concrete answer to the question in the form of a battle summary in a single line, being extremely dramatic: '{question}'"
                }
            ]
        })
    )
    
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing OpenRouter response: {e}")
        logger.debug(f"Response content: {response.text}")
        return f"The battle remains undecided. (Error processing response)"