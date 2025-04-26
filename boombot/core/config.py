import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import platform

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


if platform.system() == "Windows":
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_DEV")
    logger.info("Running on Windows, using TELEGRAM_TOKEN_DEV.")
else:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    logger.info(f"Running on {platform.system()}, using TELEGRAM_TOKEN.")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# --- Persistent Data Configuration ---
# Use a directory within the package instead of /data for local development
PACKAGE_DIR = Path(__file__).resolve().parent.parent  # Points to the boombot package directory
DATA_DIR_PATH = os.path.join(PACKAGE_DIR.parent, "data")  # Create a data directory next to the boombot package
logger.info(f"Using DATA_DIR path: {DATA_DIR_PATH}")
DATA_DIR = Path(DATA_DIR_PATH)
logger.info(f"Resolved DATA_DIR: {DATA_DIR.resolve()}") 
DATA_DIR.mkdir(parents=True, exist_ok=True) 

# File paths within the persistent data directory
ANSWERS_FILE = DATA_DIR / "question_answers.json"
GAME_DATA_FILE = DATA_DIR / "game_data.json"
BOOM_COUNT_FILE = DATA_DIR / "boom_count.json"
