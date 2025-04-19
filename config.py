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
DATA_DIR_PATH = "/data"
logger.info(f"Using fixed DATA_DIR path: {DATA_DIR_PATH}")
DATA_DIR = Path(DATA_DIR_PATH)
logger.info(f"Resolved DATA_DIR: {DATA_DIR.resolve()}") 
DATA_DIR.mkdir(parents=True, exist_ok=True) 

# File paths within the persistent data directory
BASE_DIR = Path(__file__).resolve().parent 
ANSWERS_FILE = DATA_DIR / "question_answers.json"
GAME_DATA_FILE = DATA_DIR / "game_data.json"
BOOM_COUNT_FILE = DATA_DIR / "boom_count.json" 
