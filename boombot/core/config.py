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

# `openrouter/free` is OpenRouter's free-models router: it picks a currently
# available free model that can serve the request. Pinning individual `:free`
# slugs is what broke the command -- they get rate limited and retired without
# notice, and OpenRouter has been moving them to paid ("This model is
# unavailable for free ... use this slug instead: <paid slug>"). The router
# rides that churn out, so it is the whole default chain.
DEFAULT_LLM_MODELS = ["openrouter/free"]

# Override with a single model (LLM_MODEL) or a comma separated chain (LLM_MODELS).
_llm_models_env = os.getenv("LLM_MODELS") or os.getenv("LLM_MODEL") or ""
LLM_MODELS = [model.strip() for model in _llm_models_env.split(",") if model.strip()]
if not LLM_MODELS:
    LLM_MODELS = list(DEFAULT_LLM_MODELS)
logger.info(f"LLM model chain: {LLM_MODELS}")

# When a model 404s, OpenRouter's error often names its replacement slug. That
# replacement is normally the *paid* version of the model, so following it is
# opt-in -- billing someone's credits should never be a surprise. Only useful
# when LLM_MODELS pins specific models; the default router never needs it.
LLM_FOLLOW_MODEL_HINTS = os.getenv("LLM_FOLLOW_MODEL_HINTS", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

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
