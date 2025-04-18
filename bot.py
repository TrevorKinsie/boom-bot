import logging
import os
from dotenv import load_dotenv
# Add CallbackQueryHandler, MessageHandler, and filters imports
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import logging.handlers # Import handlers

# Import setup functions and handlers
from nltk_utils import setup_nltk
from data_manager import load_answers
from handlers import (
    boom_command,
    booms_command,
    handle_photo_caption,
    # Craps commands replaced by inline keyboard
    start_craps_command,
    craps_callback_handler,
    bet_command
)

load_dotenv()  # Load environment variables from .env file

# --- Logging Setup ---
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger() # Get root logger
logger.setLevel(logging.INFO) # Set root logger level

# Console Handler (INFO level)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler("logs/error.log")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.ERROR)
logger.addHandler(file_handler)

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
    application.add_handler(CommandHandler("craps", start_craps_command))
    application.add_handler(CallbackQueryHandler(craps_callback_handler, pattern='^craps_')) # Pattern matches our callback data
    application.add_handler(CommandHandler("bet", bet_command))

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
