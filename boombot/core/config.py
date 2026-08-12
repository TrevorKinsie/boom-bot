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

# Keep imports usable for tests and maintenance commands.  `main()` still
# refuses to start without a token.


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
# Fly mounts the persistent volume at /data. Keep local development next to
# the repository, while allowing BOT_DATA_DIR to override either location.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DATA_DIR = PACKAGE_DIR.parent / "data"
DEFAULT_DATA_DIR = Path("/data") if Path("/data").is_dir() else LOCAL_DATA_DIR
DATA_DIR = Path(os.getenv("BOT_DATA_DIR") or str(DEFAULT_DATA_DIR))
logger.info(f"Using DATA_DIR path: {DATA_DIR}")
logger.info(f"Resolved DATA_DIR: {DATA_DIR.resolve()}")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File paths within the persistent data directory
ANSWERS_FILE = DATA_DIR / "question_answers.json"
GAME_DATA_FILE = DATA_DIR / "game_data.json"
BOOM_COUNT_FILE = DATA_DIR / "boom_count.json"

# --- Chess Challenge Configuration ---
# Chess state is deliberately kept in SQLite so the feature can run alongside
# the existing JSON-backed games without requiring a second database service.
CHESS_DATABASE_FILE = Path(
    os.getenv("CHESS_DATABASE_PATH", str(DATA_DIR / "chess.sqlite3"))
)
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")


def get_chess_error_log_user_ids() -> frozenset[int]:
    """Return Telegram IDs allowed to receive chess diagnostic attachments.

    The value is intentionally read from the environment rather than stored
    in source control. Configure ``CHESS_ERROR_LOG_USER_IDS`` as a
    comma-separated secret, for example ``123,456``.
    """

    raw_value = os.getenv("CHESS_ERROR_LOG_USER_IDS", "")
    allowed_ids: set[int] = set()
    invalid_entries = 0
    for entry in raw_value.split(","):
        value = entry.strip()
        if not value:
            continue
        try:
            telegram_id = int(value)
        except ValueError:
            invalid_entries += 1
            continue
        if telegram_id <= 0:
            invalid_entries += 1
            continue
        allowed_ids.add(telegram_id)

    if invalid_entries:
        logger.warning(
            "CHESS_ERROR_LOG_USER_IDS contains invalid entries count=%s",
            invalid_entries,
        )
    return frozenset(allowed_ids)

try:
    STOCKFISH_HASH_MB = int(os.getenv("STOCKFISH_HASH_MB", "64"))
except ValueError:
    logger.warning("STOCKFISH_HASH_MB is not an integer; falling back to 64 MB.")
    STOCKFISH_HASH_MB = 64

try:
    STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "1"))
except ValueError:
    logger.warning("STOCKFISH_THREADS is not an integer; falling back to 1.")
    STOCKFISH_THREADS = 1

try:
    STOCKFISH_DEPTH = int(os.getenv("STOCKFISH_DEPTH", "12"))
except ValueError:
    logger.warning("STOCKFISH_DEPTH is not an integer; falling back to 12.")
    STOCKFISH_DEPTH = 12

try:
    STOCKFISH_GAME_DEPTH = int(
        os.getenv("STOCKFISH_GAME_DEPTH", str(STOCKFISH_DEPTH))
    )
except ValueError:
    logger.warning(
        "STOCKFISH_GAME_DEPTH is not an integer; falling back to STOCKFISH_DEPTH."
    )
    STOCKFISH_GAME_DEPTH = STOCKFISH_DEPTH

try:
    STOCKFISH_ANALYSIS_DEPTH = int(
        os.getenv("STOCKFISH_ANALYSIS_DEPTH", str(STOCKFISH_DEPTH))
    )
except ValueError:
    logger.warning(
        "STOCKFISH_ANALYSIS_DEPTH is not an integer; falling back to STOCKFISH_DEPTH."
    )
    STOCKFISH_ANALYSIS_DEPTH = STOCKFISH_DEPTH

try:
    CHESS_ANALYSIS_INTERVAL = float(os.getenv("CHESS_ANALYSIS_INTERVAL", "15"))
except ValueError:
    logger.warning("CHESS_ANALYSIS_INTERVAL is not a number; falling back to 15 seconds.")
    CHESS_ANALYSIS_INTERVAL = 15.0
