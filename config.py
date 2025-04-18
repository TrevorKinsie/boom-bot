import os
from pathlib import Path
from dotenv import load_dotenv
import logging # Import logging

load_dotenv() # Load environment variables from .env file

# Set up basic logging to see output during startup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# --- Persistent Data Configuration ---
# Define the mount point for Fly.io volumes
# The destination path specified in fly.toml is where the volume is mounted *inside* the container.
# We should use this path directly.
DATA_DIR_PATH = "/data"
logger.info(f"Using fixed DATA_DIR path: {DATA_DIR_PATH}")
DATA_DIR = Path(DATA_DIR_PATH)
# logger.info(f"FLY_VOLUME_PATH environment variable: {fly_volume_path}") # Keep for debugging if needed, but don't use for DATA_DIR
# DATA_DIR = Path(fly_volume_path if fly_volume_path else "./data") # Old logic
logger.info(f"Resolved DATA_DIR: {DATA_DIR.resolve()}") # Log the resolved path being used
DATA_DIR.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

# File paths within the persistent data directory
BASE_DIR = Path(__file__).resolve().parent # Keep BASE_DIR for non-data files if needed
ANSWERS_FILE = DATA_DIR / "question_answers.json"
GAME_DATA_FILE = DATA_DIR / "game_data.json"
BOOM_COUNT_FILE = DATA_DIR / "boom_count.json" # Define boom count file path here
