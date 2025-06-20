import logging
import random
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from inflect import engine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes, CallbackQueryHandler

# Import replies with updated path
from boombot.utils.replies import (
    SASSY_REPLIES_HIGH,
    SASSY_REPLIES_LOW,
    SASSY_REPLIES_INVALID,
    QUESTION_REPLY_VARIATIONS,
    PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS,
    SASSY_REPLIES_WHAT
)

# Import data management functions with updated path
from boombot.core.data_manager import DataManager
import boombot.core.data_manager as data_manager

# Import NLTK utility functions with updated path
from boombot.utils.nltk_utils import normalize_question_nltk, normalize_question_simple, extract_subject

# Import Craps game logic with updated path
from boombot.games.craps.craps_game import play_craps_round, place_bet as place_craps_bet, COME_OUT_PHASE, POINT_PHASE

# Import Roulette game logic with updated path
from boombot.games.roulette.roulette import place_bet, play_roulette_round, get_bet_help

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

    # --- Subject Extraction Modification ---
    # Preprocess question_content to remove leading "for " if present
    processed_question_content = question_content.strip()
    if processed_question_content.lower().startswith("for "):
        processed_question_content = processed_question_content[4:].strip() # Remove "for " and trim whitespace

    # Use the processed content for subject extraction
    extracted_subject = extract_subject(processed_question_content)
    # --- End Modification ---

    reply_text = ""  # Initialize reply_text
    subject_to_use = extracted_subject  # Default to extracted subject

    # --- Handle Empty Subject ---
    is_generic_subject = False
    if not subject_to_use or subject_to_use.isspace():
        subject_to_use = random.choice(["that", "it"])
        is_generic_subject = True
        logger.info(f"No specific subject found for '{question_content}', using generic '{subject_to_use}'.")
    # --- End Handle Empty Subject ---

    if match_found and matched_question_key:
        # Found a sufficiently similar question
        count = question_answers[matched_question_key]
        count_str = p.no("BOOM", count)
        reply_format = random.choice(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS)

        # Capitalize subject only if the chosen reply format starts with it AND it's not generic
        subject_display = subject_to_use
        if reply_format.startswith("{subject}") and not is_generic_subject:
            subject_display = subject_to_use.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_display)
        logger.info(f"Found similar question '{matched_question_key}' (Similarity: {highest_similarity:.2f}) for '{question_content}'. Answer: {count} booms")

    else:  # No similar question found OR normalization yielded nothing but input was present
        # No similar question found, treat as new
        # Use the original, non-preprocessed question_content for the storage key
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

        # Capitalize subject only if the chosen reply format starts with it AND it's not generic
        subject_display = subject_to_use
        if reply_format.startswith("{subject}") and not is_generic_subject:
            subject_display = subject_to_use.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_display)
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

        # --- Modification: Allow empty question content for photos ---
        # Always call _process_howmanybooms, even if question_content is empty.
        # _process_howmanybooms will handle the empty subject case.
        await _process_howmanybooms(update, question_content)
        # --- End Modification ---


# --- Craps Inline Keyboard Setup ---

# Define callback data constants
CALLBACK_ROLL = "craps_roll"
CALLBACK_SHOW = "craps_show"
CALLBACK_RESET = "craps_reset"
CALLBACK_HELP = "craps_help"
CALLBACK_BET_PASS = "craps_bet_pass_line"
CALLBACK_BET_FIELD = "craps_bet_field"
CALLBACK_BET_PLACE_PROMPT = "craps_bet_place_prompt"

# New constants for amount selection
CALLBACK_PLACE_BET_PREFIX = "craps_place_"  # e.g., craps_place_pass_line_5
CALLBACK_BACK_TO_MAIN = "craps_back_main"

def get_craps_keyboard(channel_id: str) -> InlineKeyboardMarkup:
    """Generates the Inline Keyboard for the Craps game."""
    channel_data = game_data_manager.get_channel_data(channel_id)
    game_state = channel_data.get('craps_state', COME_OUT_PHASE)

    pass_line_button = InlineKeyboardButton("💰 Bet Pass Line", callback_data=CALLBACK_BET_PASS)
    keyboard = [
        [
            InlineKeyboardButton("🎲 Roll Dice", callback_data=CALLBACK_ROLL),
            InlineKeyboardButton("📊 Show Game", callback_data=CALLBACK_SHOW),
        ],
        [
            pass_line_button,
            InlineKeyboardButton("💰 Bet Field", callback_data=CALLBACK_BET_FIELD),
        ],
        [
            InlineKeyboardButton("🔄 Reset My Game", callback_data=CALLBACK_RESET),
            InlineKeyboardButton("❓ Help", callback_data=CALLBACK_HELP),
        ],
        [
            InlineKeyboardButton("More Bets (/bet cmd)", callback_data=CALLBACK_BET_PLACE_PROMPT)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bet_amount_keyboard(bet_type: str, balance: Decimal) -> InlineKeyboardMarkup:
    """Generates the keyboard for selecting a bet amount."""
    buttons = []
    amounts = [Decimal('1'), Decimal('5'), Decimal('10'), Decimal('25'), Decimal('50'), Decimal('100')]
    valid_amounts = [a for a in amounts if a <= balance and a > 0]

    row = []
    for amount in valid_amounts:
        amount_str = str(amount.to_integral_value()) if amount == amount.to_integral_value() else str(amount)
        callback_data = f"{CALLBACK_PLACE_BET_PREFIX}{bet_type}_{amount_str}"
        row.append(InlineKeyboardButton(f"${amount:.2f}", callback_data=callback_data))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if balance > 0 and balance not in valid_amounts:
        all_in_callback = f"{CALLBACK_PLACE_BET_PREFIX}{bet_type}_all"
        buttons.append([InlineKeyboardButton(f"All In (${balance:.2f})", callback_data=all_in_callback)])

    buttons.append([InlineKeyboardButton("<< Back", callback_data=CALLBACK_BACK_TO_MAIN)])

    return InlineKeyboardMarkup(buttons)

async def start_craps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the initial Craps game message with the inline keyboard."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Start Craps command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or f"User_{user_id}"

    game_data_manager.get_player_data(channel_id, user_id)

    keyboard = get_craps_keyboard(channel_id)
    await update.message.reply_text(
        f"🎲 Welcome to Craps, {user_name}! Use the buttons below.",
        reply_markup=keyboard
    )

# --- Craps Callback Handler Helpers ---

async def _handle_craps_roll(channel_id: str, user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """Handles the logic for the ROLL callback."""
    result = play_craps_round(channel_id, game_data_manager)
    new_text = f"{result}\n\n---\n{user_name}, what's next?"
    keyboard = get_craps_keyboard(channel_id)
    return new_text, keyboard

async def _handle_craps_show(channel_id: str, user_id: str, user_name: str, chat_title: str | None) -> str:
    """Handles the logic for the SHOW callback."""
    result = await get_showgame_text(channel_id, user_id, user_name, chat_title)
    return f"{result}\n\n---\n{user_name}, what's next?"

async def _handle_craps_reset(channel_id: str, user_id: str, user_name: str) -> str:
    """Handles the logic for the RESET callback."""
    result = await do_resetmygame(channel_id, user_id, user_name)
    return f"{result}\n\n---\n{user_name}, what's next?"

async def _handle_craps_help(query: CallbackQuery) -> None:
    """Handles the logic for the HELP callback."""
    help_text = get_craps_help_text()
    await query.message.reply_text(help_text, parse_mode='MarkdownV2')

async def _handle_craps_bet_pass(channel_id: str, user_name: str) -> tuple[str | None, InlineKeyboardMarkup | None, bool, str | None]:
    """Handles the logic for the BET_PASS callback."""
    channel_data = game_data_manager.get_channel_data(channel_id)
    game_state = channel_data.get('craps_state', COME_OUT_PHASE)
    if game_state == POINT_PHASE:
        new_text = f"Cannot place Pass Line bet when point is established.\n\n---\n{user_name}, what's next?"
        keyboard = get_craps_keyboard(channel_id)
        return new_text, keyboard, False, None
    else:
        return None, None, True, 'pass_line'

async def _handle_craps_bet_field() -> tuple[str | None, InlineKeyboardMarkup | None, bool, str | None]:
    """Handles the logic for the BET_FIELD callback."""
    return None, None, True, 'field'

async def _handle_craps_place_bet(callback_data: str, channel_id: str, user_id: str, user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """Handles the logic for placing a bet via amount buttons."""
    try:
        full_bet_part = callback_data[len(CALLBACK_PLACE_BET_PREFIX):]
        last_underscore_index = full_bet_part.rfind('_')

        if last_underscore_index == -1:
            raise ValueError("Invalid callback format: no underscore found after prefix.")

        bet_type = full_bet_part[:last_underscore_index]
        amount_part = full_bet_part[last_underscore_index + 1:]

        player_data = game_data_manager.get_player_data(channel_id, user_id)
        balance = Decimal(player_data.get('balance', '0'))

        if amount_part.lower() == 'all':
            amount_to_bet = balance
            amount_str_for_func = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
        else:
            amount_to_bet = Decimal(amount_part)
            amount_str_for_func = amount_part

        if amount_to_bet <= 0:
            result_message = "Bet amount must be positive."
        elif amount_to_bet > balance:
            result_message = f"Insufficient balance. You have ${balance:.2f}, need ${amount_to_bet:.2f}."
        else:
            result_message = place_craps_bet(channel_id, user_id, user_name, bet_type, amount_str_for_func, game_data_manager)

        new_text = f"{result_message}\n\n---\n{user_name}, what's next?"
        keyboard = get_craps_keyboard(channel_id)

    except (IndexError, ValueError, InvalidOperation) as e:
        logger.error(f"Error parsing place bet callback '{callback_data}': {e}")
        new_text = f"Error processing bet amount. Please try again.\n\n---\n{user_name}, what's next?"
        keyboard = get_craps_keyboard(channel_id)

    return new_text, keyboard

async def _handle_craps_back_main(user_name: str, channel_id: str) -> tuple[str, InlineKeyboardMarkup]:
    """Handles the logic for the BACK_TO_MAIN callback."""
    new_text = f"{user_name}, what's next?"
    keyboard = get_craps_keyboard(channel_id)
    return new_text, keyboard

async def _handle_craps_bet_place_prompt(user_name: str, channel_id: str) -> tuple[str, InlineKeyboardMarkup]:
    """Handles the logic for the BET_PLACE_PROMPT callback."""
    bet_info = (
        "Place bets (4,5,6,8,9,10), Hard ways (4,6,8,10), and others require the `/bet` command.\n"
        "Usage: `/bet <type> <amount>`\n"
        "Example: `/bet place_6 12` or `/bet hard_8 5`\n"
        "Use `/crapshelp` for more details."
    )
    new_text = f"{bet_info}\n\n---\n{user_name}, what's next?"
    keyboard = get_craps_keyboard(channel_id)
    return new_text, keyboard

async def _handle_craps_show_amount_keyboard(bet_type_for_amount: str, channel_id: str, user_id: str, user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """Handles the logic for showing the bet amount selection keyboard."""
    player_data = game_data_manager.get_player_data(channel_id, user_id)
    balance = Decimal(player_data.get('balance', '0'))
    if balance <= 0:
        new_text = f"You have no balance to bet with!\n\n---\n{user_name}, what's next?"
        keyboard = get_craps_keyboard(channel_id)
    else:
        amount_keyboard = get_bet_amount_keyboard(bet_type_for_amount, balance)
        bet_name = bet_type_for_amount.replace('_', ' ').title()
        new_text = f"Select amount for {bet_name}: (Balance: ${balance:.2f})"
        keyboard = amount_keyboard
    return new_text, keyboard

async def _edit_or_send_craps_message(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, new_text: str, keyboard: InlineKeyboardMarkup, channel_id: str) -> None:
    """Edits the existing message or sends a new one if editing fails."""
    if query.message:
        try:
            # Check if message content and keyboard are identical to avoid unnecessary API calls
            if query.message.text == new_text and query.message.reply_markup == keyboard:
                logger.debug("Skipping message edit: content and keyboard are identical.")
            else:
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=keyboard
                )
        except Exception as e:
            # Specifically check for the "Message is not modified" error
            if "Message is not modified" not in str(e):
                logger.error(f"Failed to edit craps message: {e}")
                # Fallback: Try sending a new message if editing failed for other reasons
                try:
                    await context.bot.send_message(chat_id=channel_id, text=new_text, reply_markup=keyboard)
                except Exception as e2:
                    logger.error(f"Failed to send fallback craps message: {e2}")
    else:
        logger.warning("Cannot edit message, query.message is None.")
        # Fallback: Try sending a new message if the original message context is lost
        try:
            await context.bot.send_message(chat_id=channel_id, text=new_text, reply_markup=keyboard)
        except Exception as e2:
            logger.error(f"Failed to send fallback craps message when query.message was None: {e2}")

# --- Craps Callback Handler ---

async def craps_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button presses from the Craps inline keyboard by dispatching to helpers."""
    query = update.callback_query
    if not query or not query.message or not query.from_user or not query.data:
        logger.warning("Craps callback received without query, message, user, or data.")
        return

    await query.answer()  # Acknowledge the button press

    channel_id = str(query.message.chat.id)
    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name or f"User_{user_id}"
    callback_data = query.data
    chat_title = query.message.chat.title  # Get chat title

    # Default values
    new_text = f"{user_name}, what's next?" # Default text
    keyboard = get_craps_keyboard(channel_id) # Default keyboard
    edit_message = True
    show_amount_keyboard = False
    bet_type_for_amount = None

    # Dispatch based on callback data
    if callback_data == CALLBACK_ROLL:
        new_text, keyboard = await _handle_craps_roll(channel_id, user_name)
    elif callback_data == CALLBACK_SHOW:
        new_text = await _handle_craps_show(channel_id, user_id, user_name, chat_title)
        # Keyboard remains the default main keyboard
    elif callback_data == CALLBACK_RESET:
        new_text = await _handle_craps_reset(channel_id, user_id, user_name)
        # Keyboard remains the default main keyboard
    elif callback_data == CALLBACK_HELP:
        await _handle_craps_help(query)
        edit_message = False # Help sends a new message
    elif callback_data == CALLBACK_BET_PASS:
        new_text_maybe, keyboard_maybe, show_amount_keyboard, bet_type_for_amount = await _handle_craps_bet_pass(channel_id, user_name)
        if new_text_maybe: new_text = new_text_maybe
        if keyboard_maybe: keyboard = keyboard_maybe
    elif callback_data == CALLBACK_BET_FIELD:
        _, _, show_amount_keyboard, bet_type_for_amount = await _handle_craps_bet_field()
    elif callback_data.startswith(CALLBACK_PLACE_BET_PREFIX):
        new_text, keyboard = await _handle_craps_place_bet(callback_data, channel_id, user_id, user_name)
    elif callback_data == CALLBACK_BACK_TO_MAIN:
        new_text, keyboard = await _handle_craps_back_main(user_name, channel_id)
    elif callback_data == CALLBACK_BET_PLACE_PROMPT:
        new_text, keyboard = await _handle_craps_bet_place_prompt(user_name, channel_id)
    else:
        logger.warning(f"Unknown craps callback data received: {callback_data}")
        edit_message = False # Don't edit if callback is unknown

    # Handle showing the amount keyboard if triggered
    if show_amount_keyboard and bet_type_for_amount:
        new_text, keyboard = await _handle_craps_show_amount_keyboard(bet_type_for_amount, channel_id, user_id, user_name)

    # Edit the message if required
    if edit_message:
        await _edit_or_send_craps_message(query, context, new_text, keyboard, channel_id)

async def bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /bet command for placing various Craps bets."""
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("Bet command received without message, chat, or user info.")
        return

    channel_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or f"User_{user_id}"

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /bet <bet_type> <amount>\n"
            "Example: /bet pass_line 10\n"
            "Use the 'Place Bet (Info)' button or /crapshelp for valid types."
        )
        return

    bet_type = context.args[0].lower()
    amount_str = context.args[1]

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
    elif bet_type == 'place':
        await update.message.reply_text("Usage: /bet place <number> <amount>")
        return

    # Call place_craps_bet synchronously (it's not async)
    message = place_craps_bet(channel_id, user_id, user_name, bet_type, amount_str, game_data_manager)
    await update.message.reply_text(message)

async def do_resetmygame(channel_id: str, user_id: str, user_name: str) -> str:
    """Resets the user's Craps balance and bets. Returns status message."""
    start_balance = '100.00'
    player_data = game_data_manager.get_player_data(channel_id, user_id)
    player_data['balance'] = start_balance
    player_data['craps_bets'] = {}
    player_data['display_name'] = user_name
    game_data_manager.save_player_data(channel_id, user_id, player_data)
    return f"Your balance has been reset to ${Decimal(start_balance):.2f}. Your bets are cleared."

# Modify signature to accept channel_name
async def get_showgame_text(channel_id: str, user_id: str, user_name: str, channel_name: str | None) -> str:
    """Generates the text for showing the current game state and user status."""
    channel_data = game_data_manager.get_channel_data(channel_id)
    player_data = game_data_manager.get_player_data(channel_id, user_id)

    if player_data.get('display_name') != user_name:
        player_data['display_name'] = user_name
        game_data_manager.save_player_data(channel_id, user_id, player_data)

    balance = Decimal(player_data.get('balance', '100.00'))
    bets = player_data.get('craps_bets', {})
    point = channel_data.get('craps_point', None)
    state = channel_data.get('craps_state', COME_OUT_PHASE)

    # Use channel_name if available, otherwise use channel_id
    game_title = channel_name if channel_name else f"Channel {channel_id}"
    reply_lines = [f"--- Craps Game: {game_title} ---"]
    if point:
        reply_lines.append(f"Point is: {point}")
    else:
        reply_lines.append("Phase: Come Out Roll")

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
                reply_lines.append(f"- {bet_type.replace('_',' ').title()}: Invalid Amount ({amount})")

    return "\n".join(reply_lines)

def get_craps_help_text() -> str:
    """Returns the Craps help text (MarkdownV2 formatted)."""
    # Double-escape backslashes for MarkdownV2
    help_text = """
🎲 **Craps Rules & Bot Commands** 🎲

*Basic Gameplay:*
- The first roll is the "Come Out" roll\\
- If you roll a 7 or 11 \\(Natural\\), Pass Line bets win, Don't Pass loses\\. New Come Out roll\\
- If you roll a 2, 3, or 12 \\(Craps\\), Pass Line bets lose\\. Don't Pass wins on 2 or 3, pushes \\(ties\\) on 12\\. New Come Out roll\\
- If you roll any other number \\(4, 5, 6, 8, 9, 10\\), that number becomes the "Point"\\

*Point Phase:*
- The goal is to roll the Point number again *before* rolling a 7\\
- If the Point is rolled, Pass Line bets win, Don't Pass loses\\. Game resets to Come Out roll\\
- If a 7 is rolled \\("Seven Out"\\), Pass Line bets lose, Don't Pass wins\\. Game resets to Come Out roll\\
- Other rolls don't resolve Pass/Don't Pass, you keep rolling\\

*Bet Types Implemented:*
- `pass_line`: Wins on Natural or Point hit, loses on Craps or Seven Out\\
- `dont_pass`: Wins on Craps \\(2,3\\), pushes on 12, loses on Natural\\. Wins on Seven Out, loses if Point hit\\
- `field`: One roll bet\\. Wins if 2, 3, 4, 9, 10, 11 rolled\\. Pays double on 2, triple on 12\\. Loses on 5, 6, 7, 8\\
- `place_X`: Bet that number X \\(4,5,6,8,9,10\\) will roll before a 7\\. Only active during Point Phase\\. Loses on 7\\
- `hard_X`: Bet that X \\(4,6,8,10\\) will roll as doubles \\(e\\.g\\., 2\\+2 for hard 4\\) before a 7 or the "easy" way \\(e\\.g\\., 1\\+3 for easy 4\\)\\
- `any_craps`: One roll bet\\. Wins if 2, 3, or 12 rolled\\
- `any_seven`: One roll bet\\. Wins if 7 rolled\\
- `two`/`three`/`eleven`/`twelve`: One roll bet on specific number\\. High payouts\\
- `horn`: One roll bet split 4 ways on 2, 3, 11, 12\\. Wins if any hit, pays based on number rolled\\. Must be divisible by 4\\

*Bot Interaction:*
- Use the buttons below the Craps message\\
- `/bet <type> <amount>`: Use this command separately to place bets\\. Example: `/bet field 5`
- `/craps`: Starts a new Craps game interface if needed\\

\\(More bet types may be added later\\!\\)
"""
    return help_text
