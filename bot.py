import logging
import os
from dotenv import load_dotenv
# Add CallbackQueryHandler, MessageHandler, and filters imports
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Import setup functions and handlers
from nltk_utils import setup_nltk
from data_manager import load_answers
from handlers import (
    boom_command,
    booms_command,
    handle_photo_caption, # This handler needs MessageHandler
    # Craps commands replaced by inline keyboard
    start_craps_command, # New command to show the keyboard
    craps_callback_handler, # New handler for button presses
    bet_command        # Keep bet command
    # Old handlers removed:
    # craps_command,
    # showgame_command,
    # resetmygame_command,
    # crapshelp_command
)

load_dotenv()  # Load environment variables from .env file

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Setup ---
setup_nltk()
load_answers()

# --- Main Bot Function ---
def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(token).build()

    # Register handlers from the handlers module
    application.add_handler(CommandHandler("boom", boom_command))
    application.add_handler(CommandHandler("howmanybooms", booms_command))
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_caption))

    # --- Craps Game Handlers (Inline Keyboard) ---
    # Command to initiate the Craps game interface
    application.add_handler(CommandHandler("craps", start_craps_command))

    # Handler for button presses (callbacks)
    application.add_handler(CallbackQueryHandler(craps_callback_handler, pattern='^craps_')) # Pattern matches our callback data

    # Keep the bet command handler
    application.add_handler(CommandHandler("bet", bet_command))

    # Remove the handler for receiving bet amounts via text
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet_amount))

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
