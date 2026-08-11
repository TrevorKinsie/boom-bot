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


# --- LLM Configuration ---
LLM_API_KEY = os.getenv("LLM_API_KEY")

# Models are tried in order until one returns a usable answer. Free-tier models
# on OpenRouter get rate limited and retired without notice, so keep a fallback
# chain instead of pinning a single model.
DEFAULT_LLM_MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-001",
]

# Override with a single model (LLM_MODEL) or a comma separated chain (LLM_MODELS).
_llm_models_env = os.getenv("LLM_MODELS") or os.getenv("LLM_MODEL") or ""
LLM_MODELS = [model.strip() for model in _llm_models_env.split(",") if model.strip()]
if not LLM_MODELS:
    LLM_MODELS = list(DEFAULT_LLM_MODELS)
logger.info(f"LLM model chain: {LLM_MODELS}")

try:
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
except ValueError:
    logger.warning("LLM_TIMEOUT is not a number, falling back to 30 seconds.")
    LLM_TIMEOUT = 30.0

# Optional attribution headers OpenRouter uses for its app leaderboard.
LLM_REFERER = os.getenv("LLM_REFERER")
LLM_APP_NAME = os.getenv("LLM_APP_NAME", "boom-bot")

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
