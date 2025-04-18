import logging
import random
from decimal import Decimal, InvalidOperation
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

# Import data management functions and class
import data_manager
from data_manager import DataManager

# Import NLTK utility functions
from nltk_utils import normalize_question_nltk, normalize_question_simple, extract_subject

# Import Craps game logic and constants
from craps_game import play_craps_round, place_bet as place_craps_bet, COME_OUT_PHASE, POINT_PHASE

logger = logging.getLogger(__name__)
p = engine()  # Initialize inflect engine

# --- Instantiate DataManager ---
# Create a single instance to manage all game data
game_data_manager = DataManager()

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


# --- Updated Craps Handlers ---

async def craps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /roll command for playing a Craps round in the current channel."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Craps command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)

    # Check if the user exists in the channel data, implicitly initializes if not via get_player_data
    player_data = game_data_manager.get_player_data(channel_id, user_id)
    if player_data.get('balance') == '100.00' and not player_data.get('craps_bets'):
         # Check if it's the initial state for this specific user
         # This check might need refinement if balance can be exactly 100 later
         await update.message.reply_text(f"Welcome {update.effective_user.first_name}! You start with $100. Use commands like /bet pass_line 10 to bet, then /roll.")
         # Don't return here, let play_craps_round handle the "no bets" message if applicable

    # play_craps_round now handles checking for bets and game logic
    result = play_craps_round(channel_id, game_data_manager)
    await update.message.reply_text(result)

async def bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /bet command for placing various Craps bets."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Bet command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    # Get user's name to pass to the bet function
    user_name = update.effective_user.first_name or f"User_{user_id}" # Fallback if first_name is not available

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /bet <bet_type> <amount>\nExample: /bet pass_line 10\nValid types: pass_line, dont_pass, field, place_4, place_5, place_6, place_8, place_9, place_10")
        return

    bet_type = context.args[0].lower()
    amount_str = context.args[1]

    # Special handling for place bets needing a number
    if bet_type == 'place' and len(context.args) == 3:
        try:
            place_num = int(context.args[1])
            if place_num in [4, 5, 6, 8, 9, 10]:
                bet_type = f"place_{place_num}"
                amount_str = context.args[2]
            else:
                 await update.message.reply_text("Invalid number for Place Bet. Use 4, 5, 6, 8, 9, or 10.")
                 return
        except ValueError:
             await update.message.reply_text("Invalid number for Place Bet.")
             return
        except IndexError:
             await update.message.reply_text("Usage: /bet place <number> <amount>")
             return
    elif bet_type == 'place': # Incorrect usage without number/amount
         await update.message.reply_text("Usage: /bet place <number> <amount>")
         return

    # Call the unified place_bet function from craps_game
    # Corrected argument order: channel_id, user_id, user_name, bet_type, amount_str, data_manager
    message = place_craps_bet(channel_id, user_id, user_name, bet_type, amount_str, game_data_manager)

    await update.message.reply_text(message)

async def resetmygame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets the calling user's Craps balance and bets within the current channel."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Reset command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or f"User_{user_id}" # Get username
    start_balance = '100.00'  # Default starting balance as string

    # Get current data (or initialize if new)
    player_data = game_data_manager.get_player_data(channel_id, user_id)

    # Reset user-specific fields and update display name
    player_data['balance'] = start_balance
    player_data['craps_bets'] = {}
    player_data['display_name'] = user_name # Ensure display name is stored/updated
    # Do NOT reset channel state (point, game_state) here

    # Save the updated data for this user
    game_data_manager.save_player_data(channel_id, user_id, player_data)

    await update.message.reply_text(f"Your balance has been reset to ${Decimal(start_balance):.2f}. Your bets in this channel are cleared. Good luck!")

async def showgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows current Craps game state for the channel and the user's balance/bets."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Showgame command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or f"User_{user_id}" # Get username

    # Get channel and player data
    channel_data = game_data_manager.get_channel_data(channel_id)
    player_data = game_data_manager.get_player_data(channel_id, user_id)

    # Update display name in data when showing game info
    if player_data.get('display_name') != user_name:
        player_data['display_name'] = user_name
        game_data_manager.save_player_data(channel_id, user_id, player_data)


    balance = Decimal(player_data.get('balance', '100.00')) # Default if somehow missing after get
    bets = player_data.get('craps_bets', {})
    point = channel_data.get('craps_point', None)
    state = channel_data.get('craps_state', COME_OUT_PHASE)

    reply_lines = [f"--- Craps Game: Channel {channel_id} ---"]
    if point:
        reply_lines.append(f"Point is: {point}")
    else:
        reply_lines.append("Phase: Come Out Roll")

    # Use the fetched/updated user_name
    reply_lines.append(f"\n--- Your Status ({user_name}) ---")
    reply_lines.append(f"Balance: ${balance:.2f}")

    if not bets:
        reply_lines.append("Your Active Bets: None")
    else:
        reply_lines.append("Your Active Bets:")
        for bet_type, amount in bets.items():
            try:
                amount_dec = Decimal(amount)
                reply_lines.append(f"- {bet_type.replace('_',' ').title()}: ${amount_dec:.2f}")
            except InvalidOperation:
                 reply_lines.append(f"- {bet_type.replace('_',' ').title()}: Invalid Amount ({amount})") # Log error?

    await update.message.reply_text("\n".join(reply_lines))

async def crapshelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides help text for Craps rules and commands using MarkdownV2 with minimal formatting."""
    help_text = """
🎲 **Craps Rules & Bot Commands** 🎲

*Basic Gameplay:*
\.\.\. (Rules remain the same) \.\.\.

*Bet Types Implemented:*
\- Pass Line \(pass\_line\)
\- Don't Pass \(dont\_pass\)
\- Field \(field\)
\- Place Bets \(place\_4, place\_5, place\_6, place\_8, place\_9, place\_10\)
\(See previous help or rules online for details on each bet\)

*Bot Commands:*

\- `/roll`: Roll the dice for the channel\. You must have an active bet\.
\- `/bet <type> <amount>`: Place a bet\. 
    \- Examples:
        \- `/bet pass_line 10`
        \- `/bet field 5`
        \- `/bet place_6 12` \(or `/bet place 6 12`\)
    \- Valid types: `pass_line`, `dont_pass`, `field`, `place_4`, `place_5`, `place_6`, `place_8`, `place_9`, `place_10`\.
    \- Note: `pass_line` and `dont_pass` only allowed on Come Out roll\. `place_*` bets only allowed when Point is established\.
\- `/showgame`: Show channel game state and your balance/bets\.
\- `/resetmygame`: Reset your balance to $100 and clear your bets in this channel\.
\- `/crapshelp`: Show this help message\.

\(More bet types may be added later\!\)
"""
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')
