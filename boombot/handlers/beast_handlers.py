import logging
import random
from telegram import Update
from telegram.ext import ContextTypes

from boombot.utils.nltk_utils import extract_contenders
from boombot.utils.replies import VICTORY_REASONS, BATTLE_OUTCOMES, CLOSE_MATCH_OUTCOMES

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
    
    # Choose a random winner and loser if there are only 2 contenders
    if len(contenders) == 2:
        if random.random() < 0.5:
            winner, loser = contenders
        else:
            loser, winner = contenders
    else:
        # If more than 2 contenders, pick a random winner and a different random loser
        winner = random.choice(contenders)
        remaining = [c for c in contenders if c != winner]
        loser = random.choice(remaining) if remaining else "the rest"
    
    # Determine if this is a close match (20% chance)
    is_close_match = random.random() < 0.2
    
    # Pick a reason for victory
    reason = random.choice(VICTORY_REASONS)
    
    # Choose a response template based on whether it's a close match
    if is_close_match:
        template = random.choice(CLOSE_MATCH_OUTCOMES)
    else:
        template = random.choice(BATTLE_OUTCOMES)
    
    # Format the response
    response = template.format(winner=winner.capitalize(), loser=loser, reason=reason)
    
    # Send the response
    await update.message.reply_text(response)