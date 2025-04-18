import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# File paths
BASE_DIR = Path(__file__).resolve().parent
ANSWERS_FILE = BASE_DIR / "question_answers.json"
GAME_DATA_FILE = BASE_DIR / "game_data.json" # Added for game state
