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
# Add roulette handler imports
from roulette_handlers import start_roulette_command, roulette_callback_handler
from config import TELEGRAM_TOKEN # Corrected import name

load_dotenv()  # Load environment variables from .env file

# --- Logging Setup ---
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger() # Get root logger
logger.setLevel(logging.INFO) # Set root logger level

# Remove existing handlers from the root logger to prevent duplicates
if logger.hasHandlers():
    logger.handlers.clear()

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

# --- Application Setup ---
def create_application(token: str) -> Application:
    """Builds and configures the Telegram bot application."""
    # Perform setup when creating the application
    setup_nltk()
    load_answers()

    application = Application.builder().token(token).build()

    # Register handlers from the handlers module
    application.add_handler(CommandHandler("boom", boom_command))
    application.add_handler(CommandHandler("howmanybooms", booms_command))
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_caption))

    # --- Craps Game Handlers (Inline Keyboard) ---
    application.add_handler(CommandHandler("craps", start_craps_command))
    application.add_handler(CallbackQueryHandler(craps_callback_handler, pattern='^craps_')) # Pattern matches our callback data
    application.add_handler(CommandHandler("bet", bet_command))
    
    # --- Roulette Game Handlers ---
    application.add_handler(CommandHandler("roulette", start_roulette_command))
    application.add_handler(CallbackQueryHandler(roulette_callback_handler, pattern='^roulette_'))

    return application

# --- Main Bot Function ---
def main() -> None:
    """Start the bot."""
    # token = os.environ.get("TELEGRAM_BOT_TOKEN") # Get token from config instead
    if not TELEGRAM_TOKEN: # Use corrected token name
        logger.error("TELEGRAM_TOKEN not set in config.py or environment.")
        return

    application = create_application(TELEGRAM_TOKEN) # Use corrected token name

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
