import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import setup functions and handlers
from nltk_utils import setup_nltk
from data_manager import load_answers
from handlers import boom_command, booms_command, handle_photo_caption, craps_command  # Added craps_command

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
    application.add_handler(CommandHandler("passline", craps_command))  # Added craps handler

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
