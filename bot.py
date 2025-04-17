import logging
import os
import random
import json  # Import json for file handling
from pathlib import Path  # Import Path for easier file path handling
from dotenv import load_dotenv  # Import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters  # Add MessageHandler and filters

load_dotenv()  # Load environment variables from .env file

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Sassy replies for numbers > 5
SASSY_REPLIES_HIGH = [
    "Whoa there, trigger happy! Let's keep it under 6, okay?",
    "Trying to break the universe? Max 5 booms allowed.",
    "Easy, cowboy! That's too much boom even for me. (Max 5)",
    "My circuits can only handle 5 booms at a time. Try again.",
    "Do I look like I'm made of explosions? Keep it 5 or less.",
    "That's a bit excessive, don't you think? Max 5 booms.",
    "Let's not get carried away. 5 booms is the limit.",
    "I admire your enthusiasm, but the limit is 5 booms.",
    "Are you trying to crash Telegram? Stick to 5 booms or fewer.",
    "Nope. Too many. 5 is the magic number.",
    "Save some booms for everyone else! Max 5.",
    "This isn't a Michael Bay movie. Keep it to 5 booms.",
    "I'm a bot, not a bomb factory. 5 is the limit.",
    "Warning: Boom overload detected! Please reduce to 5 or less.",
    "That many booms would disturb the space-time continuum. Max 5.",
    "Sorry, my boom budget only allows for 5 at a time.",
    "Did you mistake me for a nuclear reactor? Max 5 booms please.",
    "My boom capacity maxes out at 5. I don't make the rules.",
    "Your boom ambitions exceed my capabilities. Try 5 or less.",
    "Excessive booming detected! Please limit to 5 per request."
]

# Sassy replies for numbers < 1
SASSY_REPLIES_LOW = [
    "Zero booms? What's the point?",
    "Negative booms? Are you trying to *un*-explode something?",
    "Less than one boom... so, like, a fizzle?",
    "I can't do *less* than one boom. That's just sad.",
    "Did you mean *more* than zero? Try again.",
    "Ah yes, the sound of one hand *not* clapping. No booms for you.",
    "Requesting zero booms? Request denied.",
    "My purpose is to boom. You're asking me *not* to boom?",
    "Think positive! At least one boom, please.",
    "Is this some kind of anti-boom protest? (Min 1)",
    "That's like ordering a pizza with negative toppings. Makes no sense.",
    "I failed math, but even I know that's too low.",
    "Looking for an un-boom? Sorry, wrong bot.",
    "The minimum boom threshold has not been met. Try harder.",
    "Zero is for counting problems, not for booming.",
    "Even a whisper is louder than zero booms.",
    "Sorry, the Department of Booms requires at least one.",
    "ERROR: Insufficient boom quantity detected.",
    "My boom generator doesn't go that low.",
    "I'm a boom bot, not a silence bot. Min 1 please."
]

# Sassy replies for invalid input (not a number)
SASSY_REPLIES_INVALID = [
    "I need a *number*, genius. Try `/boom 3`.",
    "Was that supposed to be a number? Because it wasn't.",
    "Numbers. You know, 1, 2, 3... Use one of those.",
    "My circuits are confused. Please provide a number (1-5).",
    "Error 404: Number not found. Please try again.",
    "Are you speaking human or bot? I need a number!",
    "I can only count booms if you give me a number.",
    "Alphabet soup isn't a number. Try again (1-5).",
    "Did you forget the number? Or did you just type random letters?",
    "To boom or not to boom? That requires a *number*.",
    "That's not a number, that's a keyboard malfunction.",
    "I speak binary, but I still need actual numbers.",
    "Sorry, my number detector is drawing a blank here.",
    "Is that what passes for a number where you're from?",
    "Invalid input detected. Please reboot your brain and try again.",
    "I'm a bot, not a mind reader. Give me a proper number.",
    "Numbers only! This isn't a spelling bee.",
    "Does that look like a number to you? Because it doesn't to me.",
    "My number parser just had a meltdown. Try again with actual digits.",
    "That input is so invalid, it made my CPU hurt.",
    "Did your calculator break? Because that's not a number.",
    "I'm fluent in numbers, but that was gibberish.",
    "Have you considered using actual numbers? Just a thought.",
    "That's about as much a number as I am human.",
    "ERROR: Number.exe has stopped working. Please try again.",
    "I ordered a number but got word salad instead.",
    "My numeric translator is broken, or maybe that's just not a number.",
    "Numbers are like emojis - that wasn't either of them.",
    "Sorry, I don't speak whatever language that was.",
    "Did you fall asleep on your keyboard?",
    "That's a creative way to not type a number.",
    "Interesting input! But I need a number between 1-5.",
    "My AI training didn't cover interpretive number art.",
    "That's a lovely collection of characters. Now try a number.",
    "Loading number recognition... Failed. Invalid input.",
    "In what universe is that a number?",
    "I asked for a number and got... whatever that was.",
    "Mathematical impossibility detected. Please use real numbers.",
    "That's not a number, that's a cry for help.",
    "Even a random number generator would do better than that."
]

# Reply variations for questions
QUESTION_REPLY_VARIATIONS = [
    "I give that {count} BOOMS 💥",
    "That definitely deserves {count} BOOMS 💥",
    "My official rating: {count} BOOMS 💥",
    "Let's go with {count} BOOMS 💥 for that one.",
    "Hmm, I'd say {count} BOOMS 💥",
    "Solid {count} BOOMS 💥 from me.",
    "The boom-o-meter says: {count} BOOMS 💥",
    "Without a doubt, {count} BOOMS 💥",
]

# Reply variations for questions
PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS = [
    "I already told you - that's {count} BOOMS 💥",
    "We've been through this - {count} BOOMS 💥",
    "As I said before, {count} BOOMS 💥",
    "Still {count} BOOMS 💥, just like last time",
    "My answer hasn't changed: {count} BOOMS 💥",
    "Did you forget? It's {count} BOOMS 💥",
    "Pay attention! I said {count} BOOMS 💥",
    "Let me repeat: {count} BOOMS 💥"
]

SASSY_REPLIES_WHAT = [
    "How many uhhhh?",
    "How many booms does what?",
    "I need more context than that, genius.",
    "Are we playing 20 questions? Because you're not winning.",
    "That's like asking 'how high is up?' - be specific!",
    "Um... how many booms for... the void?",
    "I can't rate nothing. Give me something to work with!",
    "The answer is... wait, what are we rating?",
    "Did you forget to finish your question?",
    "My psychic powers are offline. What needs rating?",
    "Sorry, my crystal ball is in the shop. What needs booms?"
]

# --- Persistent Question Answers ---
ANSWERS_FILE = Path("question_answers.json")
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


def normalize_question(text: str) -> str:
    """Normalizes question text for consistent lookups."""
    # Just lowercase and strip whitespace
    return text.lower().strip()


# Load answers when the script starts
load_answers()


# --- Command Handlers ---

# Define the command handler for /boom (remains unchanged)
async def boom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reacts with 💥 if replying, answers questions (persistently), or sends booms/sassy replies."""
    global question_answers  # Ensure we're using the global dict

    # --- 3. Existing logic for non-reply, non-question /boom commands ---
    boom_count = random.randint(1, 5)  # Default to random if no valid number is given

    if context.args:  # Check if any arguments were passed with the command
        try:
            requested_count = int(context.args[0])
            if 1 <= requested_count <= 5:
                boom_count = requested_count
            elif requested_count > 5:
                reply = random.choice(SASSY_REPLIES_HIGH)
                await update.message.reply_text(reply)
                return
            else:  # requested_count < 1
                reply = random.choice(SASSY_REPLIES_LOW)
                await update.message.reply_text(reply)
                return

        except (IndexError, ValueError):
            reply = random.choice(SASSY_REPLIES_INVALID)
            await update.message.reply_text(reply)
            return

    # 3. If we reach here, it wasn't a reply/question & args were valid or absent
    booms = "💥" * boom_count
    await update.message.reply_text(booms)


# --- Helper Function for /howmanybooms Logic ---
async def _process_howmanybooms(update: Update, question_content: str) -> None:
    """Processes the extracted question, finds/generates booms, and replies."""
    global question_answers
    normalized_q = normalize_question(question_content)

    if normalized_q:  # Ensure normalized question is not empty
        if normalized_q in question_answers:
            # Question already answered
            count = question_answers[normalized_q]
            reply_format = random.choice(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS)
            reply_text = reply_format.format(count=count)
            logger.info(f"Found existing answer for question '{normalized_q}': {count} booms")
        else:
            # New question
            logger.info(f"New question detected: '{normalized_q}'")
            question_boom_count = random.randint(1, 5)
            reply_format = random.choice(QUESTION_REPLY_VARIATIONS)
            reply_text = reply_format.format(count=question_boom_count)
            question_answers[normalized_q] = question_boom_count
            save_answers()  # Save the updated dictionary

        await update.message.reply_text(reply_text)
    else:
        # Normalized question became empty (e.g., only whitespace after command)
        reply = random.choice(SASSY_REPLIES_WHAT)
        await update.message.reply_text(reply)


# --- Specific Handlers for /howmanybooms ---

async def booms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /howmanybooms command (text-based)."""
    if context.args:
        question_content = " ".join(context.args)
        logger.info(f"Processing question from text args: '{question_content}'")
        await _process_howmanybooms(update, question_content)
    else:
        # No arguments provided with the text command
        reply = random.choice(SASSY_REPLIES_WHAT)
        await update.message.reply_text(reply)


async def handle_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photo messages with captions containing /howmanybooms."""
    # Filters ensure message and caption exist
    caption = update.message.caption
    command_name = "/howmanybooms"
    # Find command case-insensitively
    command_pos = caption.lower().find(command_name)

    if command_pos != -1:
        # Extract text after the command
        question_content = caption[command_pos + len(command_name):].strip()
        logger.info(f"Processing question from photo caption: '{question_content}'")

        if question_content:
             await _process_howmanybooms(update, question_content)
        else:
            # Command was in caption, but no text followed it
            reply = random.choice(SASSY_REPLIES_WHAT)
            await update.message.reply_text(reply)
    # else: command not found in caption, do nothing for this handler


# --- Main Bot Function ---
def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(token).build()

    # Register handlers
    application.add_handler(CommandHandler("boom", boom_command))
    application.add_handler(CommandHandler("howmanybooms", booms_command))
    # Add the new handler for photo captions
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_caption))

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
