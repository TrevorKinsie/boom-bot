import logging
import random
from telegram import Update
from telegram.ext import ContextTypes

from boombot.utils.llm import get_openrouter_response

logger = logging.getLogger(__name__)

async def frigged_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /friggedthedeposit command by generating a humorous story."""
    if not update.message:
        logger.warning("Received /friggedthedeposit but update.message is None")
        return

    name_provided = ""
    if context.args:
        name_provided = " ".join(context.args).strip()

    if not name_provided:
        await update.message.reply_text(
            "Who frigged the deposit? Tell me their name!\\n"
            "Usage: /friggedthedeposit [name]\\n"
            "Example: /friggedthedeposit Kevin"
        )
        return

    logger.info(f"Processing /friggedthedeposit request for: '{name_provided}'")

    # The get_openrouter_response function wraps the question with:
    # "Provide a concrete answer to the question in the form of a battle summary in a single line, being extremely dramatic: '{question}'"
    # Our 'llm_question' should guide the LLM to the desired output format, leveraging the "extremely dramatic" part for humor.
    llm_question = (
        f"Generate a short, funny, hip, modern, or comically minor reason why '{name_provided}' "
        f"lost the security deposit on a rental property. This is for an inside joke about 'frigging the deposit'. "
        f"The answer should be a single, funny, non-corny sentence, ideally starting with '{name_provided} frigged the deposit by...'. "
        f"Make it creative, absurd, and dramatic. "
        f"For example: '{name_provided} frigged the deposit by entering a gun-free zone with a gun.'"
        f" or '{name_provided} frigged the deposit by swimming in the septic tank.'"
    )

    try:
        response = get_openrouter_response(llm_question)
        logger.info(f"LLM response for {name_provided} (/friggedthedeposit): {response}")
        
        # Check if the response starts appropriately, if not, prepend.
        # This is a simple check; the LLM should ideally follow the prompt's structure.
        if not response.lower().startswith(name_provided.lower()):
            # A more sophisticated check might be needed if the LLM is very creative.
            # For now, we'll assume the LLM tries to include the name prominently.
            # If the LLM often misses the "starts with name..." part, we might prepend:
            # response = f"{name_provided} frigged the deposit in a most spectacular fashion! {response}" 
            # However, the current llm.py prompt asks for a "battle summary", which might make it less likely to follow strictly.
            # Let's rely on the prompt to guide the LLM first.
            pass

    except Exception as e:
        logger.error(f"Error getting LLM response for /friggedthedeposit: {e}")
        # Ensure 'random' is imported at the top of your file (e.g., import random)
        tip_amount = random.randint(10, 200)
        formatted_tip = f"${tip_amount:.2f}"
        response = f"I tried to figure out how {name_provided} frigged the deposit, but it seems the deposit was returned, along with a tip of {formatted_tip} for excellent service."

    await update.message.reply_text(response)
