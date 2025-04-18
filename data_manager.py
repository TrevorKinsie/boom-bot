import json
import logging
from config import ANSWERS_FILE

logger = logging.getLogger(__name__)

# Store only the count now {normalized_question: count}
question_answers: dict[str, int] = {}

def load_answers():
    """Loads question answers from the JSON file."""
    global question_answers
    if ANSWERS_FILE.exists():
        try:
            with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
                # Ensure loaded values are integers
                loaded_data = json.load(f)
                # Filter out potential non-string keys or non-int values if file was manually edited
                question_answers = {str(k): int(v) for k, v in loaded_data.items() if isinstance(k, str) and isinstance(v, (int, float))}
        except (json.JSONDecodeError, IOError, ValueError, TypeError) as e:
            logger.error(f"Error loading or parsing answers file: {e}")
            question_answers = {} # Reset if file is corrupt or invalid format
    else:
        question_answers = {}


def save_answers():
    """Saves the current question answers to the JSON file."""
    global question_answers
    try:
        with open(ANSWERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(question_answers, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logger.error(f"Error saving answers file: {e}")

def get_answers() -> dict[str, int]:
    """Returns the current question answers dictionary."""
    return question_answers

def update_answer(key: str, value: int):
    """Updates or adds an answer to the dictionary."""
    global question_answers
    question_answers[key] = value
