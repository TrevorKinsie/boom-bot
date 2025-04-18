import logging
import random
from decimal import Decimal, InvalidOperation  # Import Decimal
from inflect import engine
from telegram import Update
from telegram.ext import ContextTypes

# Import replies
from replies import (
    SASSY_REPLIES_HIGH,
    SASSY_REPLIES_LOW,
    SASSY_REPLIES_INVALID,
    QUESTION_REPLY_VARIATIONS,
    PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS,
    SASSY_REPLIES_WHAT
)

# Import data management functions
import data_manager

# Import NLTK utility functions
from nltk_utils import normalize_question_nltk, normalize_question_simple, extract_subject

# Import Craps game logic and constants
from craps_game import play_craps, COME_OUT_PHASE, POINT_PHASE

logger = logging.getLogger(__name__)
p = engine()  # Initialize inflect engine

# --- Helper Function for Bet Placement ---
def _place_bet(user_data: dict, bet_type: str, bet_amount_str: str) -> tuple[str | None, str]:
    """Helper to validate and place a bet."""
    try:
        bet_amount = Decimal(bet_amount_str)
        if bet_amount <= 0:
            return None, "Bet amount must be positive."
    except InvalidOperation:
        return None, "Invalid bet amount. Please enter a number."

    balance = Decimal(user_data.get('balance', '0'))
    if bet_amount > balance:
        return None, f"Insufficient funds. Your balance is ${balance:.2f}."

    # Initialize bets dict if needed
    if 'craps_bets' not in user_data:
        user_data['craps_bets'] = {}

    # Add or update bet
    user_data['craps_bets'][bet_type] = str(bet_amount)  # Store as string
    user_data['balance'] = str(balance - bet_amount)  # Store as string

    return bet_type, f"Bet of ${bet_amount:.2f} placed on {bet_type.replace('_',' ').title()}. New balance: ${user_data['balance']}."

# --- Command Handlers ---

async def boom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /boom command (simple booms or sassy replies)."""
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

    # If we reach here, args were valid or absent
    booms = "💥" * boom_count
    await update.message.reply_text(booms)


async def _process_howmanybooms(update: Update, question_content: str) -> None:
    """Processes the extracted question, finds/generates booms, and replies.
       Uses NLTK for fuzzy matching and subject extraction. Handles pluralization and capitalization.
    """
    question_answers = data_manager.get_answers()  # Get current answers
    incoming_words = normalize_question_nltk(question_content)
    logger.info(f"Normalized incoming question '{question_content}' to words: {incoming_words}")

    match_found = False
    matched_question_key = None
    highest_similarity = 0.0
    similarity_threshold = 0.7  # Adjust this threshold (0.0 to 1.0) as needed

    # Only attempt matching if normalization yielded significant words
    if incoming_words:
        # Compare against stored questions
        for stored_key, stored_count in question_answers.items():
            stored_words = normalize_question_nltk(stored_key)
            if not stored_words:
                continue  # Skip empty stored questions

            # Calculate Jaccard similarity
            intersection = len(incoming_words.intersection(stored_words))
            union = len(incoming_words.union(stored_words))
            similarity = intersection / union if union > 0 else 0

            logger.debug(f"Comparing incoming {incoming_words} with stored '{stored_key}' ({stored_words}). Similarity: {similarity:.2f}")

            # Check if this is the best match so far above the threshold
            if similarity >= similarity_threshold and similarity > highest_similarity:
                highest_similarity = similarity
                matched_question_key = stored_key
                match_found = True
    elif not question_content.strip():  # Normalization empty AND original input was empty/whitespace
        logger.warning(f"Question content was empty or whitespace.")
        reply = random.choice(SASSY_REPLIES_WHAT)
        await update.message.reply_text(reply)
        return
    # If incoming_words is empty but question_content was not, proceed to treat as new below

    # Extract subject *after* finding potential match or deciding it's new
    # Use original content for subject extraction if normalization failed but input existed
    subject_base = question_content if not incoming_words else question_content  # Or adjust logic as needed
    extracted_subject = extract_subject(subject_base)

    reply_text = ""  # Initialize reply_text
    subject_to_use = extracted_subject  # Default to non-capitalized

    if match_found and matched_question_key:
        # Found a sufficiently similar question
        count = question_answers[matched_question_key]
        count_str = p.no("BOOM", count)
        reply_format = random.choice(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS)

        # Capitalize subject only if the chosen reply format starts with it
        if reply_format.startswith("{subject}"):
            subject_to_use = extracted_subject.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_to_use)
        logger.info(f"Found similar question '{matched_question_key}' (Similarity: {highest_similarity:.2f}) for '{question_content}'. Answer: {count} booms")

    else:  # No similar question found OR normalization yielded nothing but input was present
        # No similar question found, treat as new
        storage_key = normalize_question_simple(question_content)

        if not storage_key:  # This check might be redundant now but kept for safety
            logger.warning(f"Original question '{question_content}' also resulted in empty simple normalized key.")
            reply = random.choice(SASSY_REPLIES_WHAT)
            await update.message.reply_text(reply)
            return

        if not incoming_words:
            logger.info(f"No significant words after NLTK normalization for '{question_content}', but treating as new question with key '{storage_key}'.")
        else:
            logger.info(f"No similar question found for '{question_content}'. Treating as new question with key '{storage_key}'.")

        question_boom_count = random.randint(1, 5)
        count_str = p.no("BOOM", question_boom_count)
        reply_format = random.choice(QUESTION_REPLY_VARIATIONS)

        # Capitalize subject only if the chosen reply format starts with it
        if reply_format.startswith("{subject}"):
            subject_to_use = extracted_subject.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_to_use)
        data_manager.update_answer(storage_key, question_boom_count)  # Update answers dict
        data_manager.save_answers()  # Save updated answers

    # Send the final reply
    await update.message.reply_text(reply_text)


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


async def craps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /roll command for playing a Craps round."""
    user_data = context.user_data
    # Initialize balance if it doesn't exist (redundant but safe)
    if 'balance' not in user_data:
        user_data['balance'] = '100'
        await update.message.reply_text("Welcome to Craps! You start with $100. Use commands like /passline <amount> to bet, then /roll.")
        return

    # Check if any bets are placed before rolling
    if not user_data.get('craps_bets'):
        await update.message.reply_text("No bets placed. Use commands like /passline, /dontpass, /field, /place to bet first.")
        return

    result = play_craps(user_data)
    await update.message.reply_text(result)


async def passline_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /passline command to place a bet for Craps."""
    user_data = context.user_data
    # Initialize balance if it doesn't exist
    if 'balance' not in user_data:
        user_data['balance'] = '100'  # Starting balance as string

    game_state = user_data.get('craps_state', COME_OUT_PHASE)

    if game_state == POINT_PHASE:
        await update.message.reply_text("Cannot place Pass Line bet when point is established. Use /roll or other bets.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /passline <amount>")
        return

    bet_type, message = _place_bet(user_data, 'pass_line', context.args[0])

    if bet_type:
        message += " Roll the dice! /roll"

    await update.message.reply_text(message)


async def dontpass_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /dontpass command."""
    user_data = context.user_data
    if 'balance' not in user_data:
        user_data['balance'] = '100'
    game_state = user_data.get('craps_state', COME_OUT_PHASE)

    if game_state == POINT_PHASE:
        await update.message.reply_text("Cannot place Don't Pass bet when point is established. Use /roll or other bets.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /dontpass <amount>")
        return

    bet_type, message = _place_bet(user_data, 'dont_pass', context.args[0])

    if bet_type:
        message += " Roll the dice! /roll"

    await update.message.reply_text(message)


async def field_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /field command."""
    user_data = context.user_data
    if 'balance' not in user_data:
        user_data['balance'] = '100'

    if not context.args:
        await update.message.reply_text("Usage: /field <amount>")
        return

    bet_type, message = _place_bet(user_data, 'field', context.args[0])

    if bet_type:
        message += " Bet resolves on next /roll."

    await update.message.reply_text(message)


async def place_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /place command."""
    user_data = context.user_data
    if 'balance' not in user_data:
        user_data['balance'] = '100'
    game_state = user_data.get('craps_state', COME_OUT_PHASE)

    if game_state == COME_OUT_PHASE:
        await update.message.reply_text("Cannot place Place Bets during Come Out roll. Wait for a point.")
        return

    valid_place_numbers = {4, 5, 6, 8, 9, 10}
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /place <number> <amount> (e.g., /place 6 10)")
        return

    try:
        number = int(context.args[0])
        if number not in valid_place_numbers:
            await update.message.reply_text(f"Invalid number for Place Bet. Choose from: {', '.join(map(str, sorted(valid_place_numbers)))}.")
            return
    except ValueError:
        await update.message.reply_text("Invalid number. Usage: /place <number> <amount>")
        return

    bet_type_key = f"place_{number}"
    bet_type, message = _place_bet(user_data, bet_type_key, context.args[1])

    if bet_type:
        message += " Bet is active. Use /roll."

    await update.message.reply_text(message)


async def resetbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets the user's Craps balance and game state."""
    user_data = context.user_data
    start_balance = '100'  # Default starting balance
    user_data['balance'] = start_balance
    user_data['craps_bets'] = {}
    user_data['craps_state'] = COME_OUT_PHASE
    user_data.pop('craps_point', None)

    await update.message.reply_text(f"Your balance has been reset to ${Decimal(start_balance):.2f}. All bets cleared. Good luck!")


async def showbets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows current Craps bets and balance."""
    user_data = context.user_data
    balance = Decimal(user_data.get('balance', '100'))  # Default to 100 if not set
    bets = user_data.get('craps_bets', {})
    point = user_data.get('craps_point', None)
    state = user_data.get('craps_state', COME_OUT_PHASE)

    reply_lines = [f"Current Balance: ${balance:.2f}"]
    if point:
        reply_lines.append(f"Point is: {point}")
    else:
        reply_lines.append("Phase: Come Out Roll")

    if not bets:
        reply_lines.append("No active bets.")
    else:
        reply_lines.append("Active Bets:")
        for bet_type, amount in bets.items():
            reply_lines.append(f"- {bet_type.replace('_',' ').title()}: ${Decimal(amount):.2f}")

    await update.message.reply_text("\n".join(reply_lines))


async def crapshelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides help text for Craps rules and commands using MarkdownV2 with minimal formatting."""
    # Escaped special characters for MarkdownV2: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    # Minimal formatting: Only main title bold, some italics, escaped chars.
    help_text = """
🎲 **Craps Rules & Bot Commands** 🎲

*Basic Gameplay:*
The game starts with the "Come Out" roll\. The shooter \(you\!\) rolls the dice\.
\- 7 or 11 \(Natural\): Pass Line bets win\.
\- 2, 3, or 12 \(Craps\): Pass Line bets lose\.
\- Any other number \(4, 5, 6, 8, 9, 10\): This number becomes the "Point"\.

If a Point is established, the shooter keeps rolling until:
\- The Point is rolled again: Pass Line bets win\.
\- A 7 is rolled \("Seven Out"\): Pass Line bets lose\.

A new Come Out roll begins after a win or loss on the Pass Line\.

*Bet Types Implemented:*

\- Pass Line: \(`/passline <amount>`\)
    \- Bet _with_ the shooter\.
    \- Place only on Come Out roll\.
    \- Wins on 7, 11 on Come Out\.
    \- Loses on 2, 3, 12 on Come Out\.
    \- Wins if Point is rolled before 7\.
    \- Loses if 7 is rolled before Point\.
    \- Pays 1:1\.

\- Don't Pass: \(`/dontpass <amount>`\)
    \- Bet _against_ the shooter\.
    \- Place only on Come Out roll\.
    \- Loses on 7, 11 on Come Out\.
    \- Wins on 2, 3 on Come Out \(12 is a Push/Tie\)\.
    \- Wins if 7 is rolled before Point\.
    \- Loses if Point is rolled before 7\.
    \- Pays 1:1\.

\- Field: \(`/field <amount>`\)
    \- One\-roll bet\.
    \- Place anytime\.
    \- Wins if next roll is 2, 3, 4, 9, 10, 11, or 12\.
    \- Loses on 5, 6, 7, 8\.
    \- Pays 1:1 on 3, 4, 9, 10, 11\.
    \- Pays 2:1 on 2\.
    \- Pays 3:1 on 12\.

\- Place Bets: \(`/place <number> <amount>`\)
    \- Bet that a specific number \(4, 5, 6, 8, 9, 10\) will be rolled _before_ a 7\.
    \- Place only when a Point is established\.
    \- Bets are typically "working" \(active\) unless it's a Come Out roll\.
    \- Lose if a 7 is rolled\.
    \- Payouts vary: 9:5 \(4, 10\), 7:5 \(5, 9\), 7:6 \(6, 8\)\.

*Bot Commands:*

\- `/roll`: Roll the dice\. You must have an active bet\.
\- `/passline <amount>`: Place a Pass Line bet \(Come Out roll only\)\.
\- `/dontpass <amount>`: Place a Don't Pass bet \(Come Out roll only\)\.
\- `/field <amount>`: Place a Field bet \(anytime\)\.
\- `/place <num> <amount>`: Place a bet on number 4, 5, 6, 8, 9, or 10 \(Point phase only\)\.
\- `/showbets`: Show your current balance and active bets\.
\- `/crapshelp`: Show this help message\.

\(More bet types may be added later\!\)
"""
    # Using MarkdownV2 with minimal formatting
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')
