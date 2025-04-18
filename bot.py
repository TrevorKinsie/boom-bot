import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import setup functions and handlers
from nltk_utils import setup_nltk
from data_manager import load_answers
from handlers import (
    boom_command,
    booms_command,
    handle_photo_caption,
    craps_command,      # Renamed from play_craps to handle /roll
    bet_command,        # New unified bet command handler
    showgame_command,   # Renamed from showbets_command
    resetmygame_command,# Renamed from resetbalance_command
    crapshelp_command
    # Old individual bet handlers removed
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
    
    # Updated Craps game handlers
    application.add_handler(CommandHandler("roll", craps_command))       # Handles dice roll for the channel
    application.add_handler(CommandHandler("bet", bet_command))         # Handles placing all bet types
    application.add_handler(CommandHandler("showgame", showgame_command)) # Renamed from showbets
    application.add_handler(CommandHandler("resetmygame", resetmygame_command)) # Renamed from resetbalance
    application.add_handler(CommandHandler("crapshelp", crapshelp_command))
    
    # Remove old individual bet handlers
    # application.add_handler(CommandHandler("passline", passline_command))
    # application.add_handler(CommandHandler("dontpass", dontpass_command))
    # application.add_handler(CommandHandler("field", field_command))
    # application.add_handler(CommandHandler("place", place_command))

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
