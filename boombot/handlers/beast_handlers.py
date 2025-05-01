import logging
import random
from telegram import Update
from telegram.ext import ContextTypes

from boombot.utils.nltk_utils import extract_contenders
from boombot.utils.llm import get_openrouter_response

logger = logging.getLogger(__name__)

async def whowouldwin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /whowouldwin command by determining a winner between contenders."""
    # Extract the query text after the command
    if not update.message:
        logger.warning("Received /whowouldwin but update.message is None")
        return
    
    input_text = ""
    if context.args:
        input_text = " ".join(context.args)
    
    # If no input provided, send usage instructions
    if not input_text.strip():
        await update.message.reply_text(
            "Usage: /whowouldwin [contenders]\n"
            "Examples:\n"
            "- /whowouldwin lions vs tigers\n"
            "- /whowouldwin between pirates and ninjas\n"
            "- /whowouldwin cats or dogs"
        )
        return
    
    logger.info(f"Processing whowouldwin request: '{input_text}'")
    
    # Use NLTK to extract the contenders from the input
    contenders = extract_contenders(input_text)
    
    # If we couldn't identify contenders, let the user know
    if not contenders or len(contenders) < 2:
        await update.message.reply_text(
            "I couldn't identify who's fighting! Please specify two or more contenders.\n"
            "Examples:\n"
            "- /whowouldwin lions vs tigers\n"
            "- /whowouldwin between pirates and ninjas\n"
            "- /whowouldwin cats or dogs"
        )
        return
    
    # Construct the battle question for the LLM
    battle_question = f"Who would win in a battle between {' vs '.join(contenders)}?"
    
    # Get response from the LLM
    try:
        response = get_openrouter_response(battle_question)
        logger.info(f"LLM response for battle: {response}")
    except Exception as e:
        logger.error(f"Error getting LLM response: {e}")
        response = f"A battle between {' and '.join(contenders)} would be legendary, but I'm having trouble accessing my battle vision right now."
    
    # Send the response
    await update.message.reply_text(response)