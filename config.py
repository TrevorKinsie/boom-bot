import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# --- Persistent Data Configuration ---
# Define the mount point for Fly.io volumes
# If FLY_VOLUME_PATH is set (by Fly.io), use it, otherwise default to a local 'data' folder for development
DATA_DIR = Path(os.getenv("FLY_VOLUME_PATH", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

# File paths within the persistent data directory
BASE_DIR = Path(__file__).resolve().parent # Keep BASE_DIR for non-data files if needed
ANSWERS_FILE = DATA_DIR / "question_answers.json"
GAME_DATA_FILE = DATA_DIR / "game_data.json"
BOOM_COUNT_FILE = DATA_DIR / "boom_count.json" # Define boom count file path here
