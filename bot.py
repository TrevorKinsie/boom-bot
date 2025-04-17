import logging
import os
import random
from dotenv import load_dotenv  # Import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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
]

# Define the command handler for /boom
async def boom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a specified (1-5) or random number of explosion emojis, or a sassy reply."""
    boom_count = random.randint(1, 5) # Default to random if no valid number is given

    if context.args: # Check if any arguments were passed with the command
        try:
            requested_count = int(context.args[0])
            if 1 <= requested_count <= 5:
                boom_count = requested_count
            elif requested_count > 5:
                reply = random.choice(SASSY_REPLIES_HIGH) # Use the high list
                await update.message.reply_text(reply)
                return # Stop processing
            else: # requested_count < 1
                reply = random.choice(SASSY_REPLIES_LOW) # Use the low list
                await update.message.reply_text(reply)
                return # Stop processing

        except (IndexError, ValueError):
            # If the argument is not a valid number, send a sassy reply
            reply = random.choice(SASSY_REPLIES_INVALID)
            await update.message.reply_text(reply)
            return # Stop processing

    # If we reach here, either no args were given, or a valid number 1-5 was provided
    booms = "💥" * boom_count
    await update.message.reply_text(booms)

def main() -> None:
    """Start the bot."""
    # Get the bot token from environment variable (loaded from .env)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("boom", boom_command))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
