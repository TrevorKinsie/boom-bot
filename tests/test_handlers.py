# test_handlers.py
import pytest
import random
from unittest.mock import AsyncMock, MagicMock, patch, call
from telegram import Update, User, Message, Chat, PhotoSize, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

# Import from the new package structure
from boombot.core.data_manager import DataManager
from boombot.handlers.base_handlers import (
    boom_command,
    _process_howmanybooms,
    booms_command,
    handle_photo_caption,
    start_craps_command,
    craps_callback_handler,
    bet_command,
    game_data_manager,
    get_craps_keyboard,
    get_bet_amount_keyboard,
    CALLBACK_ROLL, CALLBACK_SHOW, CALLBACK_RESET, CALLBACK_HELP,
    CALLBACK_BET_PASS, CALLBACK_BET_FIELD, CALLBACK_BET_PLACE_PROMPT,
    CALLBACK_PLACE_BET_PREFIX, CALLBACK_BACK_TO_MAIN,
    SASSY_REPLIES_HIGH,
    SASSY_REPLIES_LOW,
    SASSY_REPLIES_INVALID,
    SASSY_REPLIES_WHAT,
    QUESTION_REPLY_VARIATIONS,
    PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS
)
from decimal import Decimal

# --- Fixtures for Telegram Objects ---

@pytest.fixture
def mock_update():
    """Creates a mock Update object with nested mocks."""
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 67890
    update.effective_user.first_name = "TestUser"
    update.message = MagicMock(spec=Message)
    update.message.message_id = 111
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()
    update.message.caption = None
    update.message.photo = []
    update.callback_query = None  # Initialize callback_query
    return update

@pytest.fixture
def mock_context():
    """Creates a mock ContextTypes object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.answer_callback_query = AsyncMock()
    context.bot.set_message_reaction = AsyncMock()
    context.args = []
    context.user_data = {}
    return context

@pytest.fixture
def mock_callback_query(mock_update):  # Depends on mock_update
    """Creates a mock CallbackQuery object and attaches it to the update."""
    callback_query = MagicMock(spec=CallbackQuery)
    callback_query.id = "callback_123"
    callback_query.data = ""
    callback_query.from_user = MagicMock(spec=User)
    callback_query.from_user.id = mock_update.effective_user.id
    callback_query.from_user.first_name = mock_update.effective_user.first_name
    callback_query.message = MagicMock(spec=Message)
    callback_query.message.message_id = mock_update.message.message_id
    callback_query.message.chat = mock_update.effective_chat
    callback_query.message.reply_text = AsyncMock()
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    mock_update.callback_query = callback_query
    return callback_query

# --- Tests for boom_command ---

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.random.randint', return_value=3)
async def test_boom_no_args_sends_random_booms(mock_randint, mock_update, mock_context):
    await boom_command(mock_update, mock_context)
    mock_randint.assert_called_once_with(1, 5)
    mock_update.message.reply_text.assert_awaited_once_with("💥💥💥")

@pytest.mark.asyncio
@pytest.mark.parametrize("num_booms", [1, 5])
async def test_boom_valid_args_sends_specific_booms(num_booms, mock_update, mock_context):
    mock_context.args = [str(num_booms)]
    await boom_command(mock_update, mock_context)
    expected_booms = "💥" * num_booms
    mock_update.message.reply_text.assert_awaited_once_with(expected_booms)

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.random.choice', return_value="Test Sassy High")
async def test_boom_high_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    mock_context.args = ["7"]
    await boom_command(mock_update, mock_context)
    mock_choice.assert_called_once_with(SASSY_REPLIES_HIGH)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy High")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.random.choice', return_value="Test Sassy Low")
async def test_boom_low_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    mock_context.args = ["0"]
    await boom_command(mock_update, mock_context)
    mock_choice.assert_called_once_with(SASSY_REPLIES_LOW)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy Low")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.random.choice', return_value="Test Sassy Invalid")
async def test_boom_invalid_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    mock_context.args = ["hello"]
    await boom_command(mock_update, mock_context)
    mock_choice.assert_called_once_with(SASSY_REPLIES_INVALID)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy Invalid")

# --- Tests for _process_howmanybooms (internal logic) ---

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.data_manager.get_answers')
@patch('boombot.handlers.base_handlers.normalize_question_nltk')
@patch('boombot.handlers.base_handlers.extract_subject', return_value="subject")
@patch('boombot.handlers.base_handlers.random.choice', return_value="{subject} got {count_str}")
@patch('boombot.handlers.base_handlers.p.no', return_value="5 BOOMS")
async def test_process_howmanybooms_found_match(mock_p_no, mock_random_choice, mock_extract_subject, mock_normalize_nltk, mock_get_answers, mock_update):
    question = "how many booms for this thing"
    normalized_question_words = {"how", "mani", "boom", "thing"}
    stored_key = "how many booms are there for the thing"
    stored_count = 5
    stored_answers = {stored_key: stored_count}
    normalized_stored_words = {"how", "mani", "boom", "there", "thing"}  # Assume normalization

    mock_get_answers.return_value = stored_answers
    mock_normalize_nltk.side_effect = [normalized_question_words, normalized_stored_words]

    await _process_howmanybooms(mock_update, question)

    mock_normalize_nltk.assert_has_calls([call(question), call(stored_key)])
    mock_extract_subject.assert_called_once_with(question)
    mock_p_no.assert_called_once_with("BOOM", stored_count)
    mock_random_choice.assert_called_once_with(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS)
    mock_update.message.reply_text.assert_awaited_once_with("Subject got 5 BOOMS")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.data_manager.get_answers', return_value={})  # No existing answers
@patch('boombot.handlers.base_handlers.data_manager.update_answer')
@patch('boombot.handlers.base_handlers.data_manager.save_answers')
@patch('boombot.handlers.base_handlers.normalize_question_nltk', return_value={"new", "quest"})
@patch('boombot.handlers.base_handlers.normalize_question_simple', return_value="new question simple")
@patch('boombot.handlers.base_handlers.extract_subject', return_value="new subject")
@patch('boombot.handlers.base_handlers.random.randint', return_value=3)
@patch('boombot.handlers.base_handlers.random.choice', return_value="About {subject}, I'd say {count_str}")
@patch('boombot.handlers.base_handlers.p.no', return_value="3 BOOMS")
async def test_process_howmanybooms_new_question(mock_p_no, mock_random_choice, mock_randint, mock_extract_subject, mock_normalize_simple, mock_normalize_nltk, mock_save_answers, mock_update_answer, mock_get_answers, mock_update):
    question = "what about a new question"
    normalized_words = {"new", "quest"}

    mock_normalize_nltk.return_value = normalized_words

    await _process_howmanybooms(mock_update, question)

    mock_get_answers.assert_called_once()
    mock_normalize_nltk.assert_called_once_with(question)
    mock_normalize_simple.assert_called_once_with(question)  # Used as storage key
    mock_extract_subject.assert_called_once_with(question)
    mock_randint.assert_called_once_with(1, 5)
    mock_p_no.assert_called_once_with("BOOM", 3)
    mock_random_choice.assert_called_once_with(QUESTION_REPLY_VARIATIONS)
    mock_update_answer.assert_called_once_with("new question simple", 3)
    mock_save_answers.assert_called_once()
    mock_update.message.reply_text.assert_awaited_once_with("About new subject, I'd say 3 BOOMS")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.random.choice', return_value="What?")
async def test_process_howmanybooms_empty_question(mock_random_choice, mock_update):
    await _process_howmanybooms(mock_update, "   ")  # Whitespace only
    mock_random_choice.assert_called_once_with(SASSY_REPLIES_WHAT)
    mock_update.message.reply_text.assert_awaited_once_with("What?")

# --- Tests for booms_command (simple wrapper) ---

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers._process_howmanybooms', new_callable=AsyncMock)
async def test_booms_command_with_args(mock_process, mock_update, mock_context):
    mock_context.args = ["some", "question"]
    await booms_command(mock_update, mock_context)
    mock_process.assert_awaited_once_with(mock_update, "some question")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers._process_howmanybooms', new_callable=AsyncMock)
@patch('boombot.handlers.base_handlers.random.choice', return_value="What?")
async def test_booms_command_no_args(mock_random_choice, mock_process, mock_update, mock_context):
    mock_context.args = []
    await booms_command(mock_update, mock_context)
    mock_process.assert_not_awaited()
    mock_random_choice.assert_called_once_with(SASSY_REPLIES_WHAT)
    mock_update.message.reply_text.assert_awaited_once_with("What?")

# --- Tests for handle_photo_caption ---

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers._process_howmanybooms', new_callable=AsyncMock)
async def test_handle_photo_caption_with_command_and_text(mock_process, mock_update, mock_context):
    mock_update.message.caption = "Some text /howmanybooms for the photo?"
    mock_update.message.photo = [MagicMock(spec=PhotoSize)]
    await handle_photo_caption(mock_update, mock_context)
    mock_process.assert_awaited_once_with(mock_update, "for the photo?")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers._process_howmanybooms', new_callable=AsyncMock)
async def test_handle_photo_caption_with_command_no_text(mock_process, mock_update, mock_context):
    mock_update.message.caption = "/howmanybooms   "
    mock_update.message.photo = [MagicMock(spec=PhotoSize)]
    await handle_photo_caption(mock_update, mock_context)
    # Expect an empty string when no text follows the command
    mock_process.assert_awaited_once_with(mock_update, "")

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers._process_howmanybooms', new_callable=AsyncMock)
async def test_handle_photo_caption_no_command(mock_process, mock_update, mock_context):
    mock_update.message.caption = "Just a photo caption"
    mock_update.message.photo = [MagicMock(spec=PhotoSize)]
    await handle_photo_caption(mock_update, mock_context)
    mock_process.assert_not_awaited()
    mock_update.message.reply_text.assert_not_called()  # Should not reply if command not present

# --- Tests for Craps Game Handlers ---

@pytest.fixture(autouse=True)
def mock_game_data_manager():
    # Use the imported DataManager for the spec
    with patch('boombot.handlers.base_handlers.game_data_manager', spec=DataManager) as mock_manager:
        mock_manager.get_channel_data.return_value = {'craps_state': 1, 'craps_point': None}
        mock_manager.get_player_data.return_value = {'balance': '100.00', 'craps_bets': {}}
        mock_manager.get_players_with_bets.return_value = {}
        mock_manager.get_all_players_data.return_value = {}
        yield mock_manager

@pytest.fixture
def mock_play_craps_round():
    with patch('boombot.handlers.base_handlers.play_craps_round', new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "🎲 Rolled 5 + 2 = 7. Point is None. Player 67890 wins $10 on Pass Line."
        yield mock_func

@pytest.fixture
def mock_place_craps_bet():
    # Use regular patch for synchronous function
    with patch('boombot.handlers.base_handlers.place_craps_bet') as mock_func:
        mock_func.return_value = "TestUser placed $10.00 on Pass Line. New balance: $90.00"
        yield mock_func

def assert_keyboard_equals(actual_keyboard, expected_buttons):
    assert isinstance(actual_keyboard, InlineKeyboardMarkup)
    assert len(actual_keyboard.inline_keyboard) == len(expected_buttons)
    for r_idx, row in enumerate(actual_keyboard.inline_keyboard):
        assert len(row) == len(expected_buttons[r_idx])
        for b_idx, button in enumerate(row):
            assert isinstance(button, InlineKeyboardButton)
            assert button.text == expected_buttons[r_idx][b_idx]['text']
            assert button.callback_data == expected_buttons[r_idx][b_idx]['callback_data']

@pytest.mark.asyncio
async def test_start_craps_command(mock_game_data_manager, mock_update, mock_context):
    channel_id = str(mock_update.effective_chat.id)
    user_id = str(mock_update.effective_user.id)
    user_name = mock_update.effective_user.first_name

    await start_craps_command(mock_update, mock_context)

    mock_game_data_manager.get_player_data.assert_called_once_with(channel_id, user_id)

    expected_keyboard_buttons = [
        [{'text': '🎲 Roll Dice', 'callback_data': CALLBACK_ROLL}, {'text': '📊 Show Game', 'callback_data': CALLBACK_SHOW}],
        [{'text': '💰 Bet Pass Line', 'callback_data': CALLBACK_BET_PASS}, {'text': '💰 Bet Field', 'callback_data': CALLBACK_BET_FIELD}],
        [{'text': '🔄 Reset My Game', 'callback_data': CALLBACK_RESET}, {'text': '❓ Help', 'callback_data': CALLBACK_HELP}],
        [{'text': 'More Bets (/bet cmd)', 'callback_data': CALLBACK_BET_PLACE_PROMPT}]
    ]
    mock_update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = mock_update.message.reply_text.await_args
    assert call_args[0] == f"🎲 Welcome to Craps, {user_name}! Use the buttons below."
    assert 'reply_markup' in call_kwargs
    assert_keyboard_equals(call_kwargs['reply_markup'], expected_keyboard_buttons)

@pytest.mark.asyncio
async def test_craps_callback_roll(mock_play_craps_round, mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_name = mock_callback_query.from_user.first_name
    mock_callback_query.data = CALLBACK_ROLL

    roll_result_str = "🎲 Rolled 3 + 4 = 7. Seven Out!"
    mock_play_craps_round.return_value = roll_result_str

    with patch('boombot.handlers.base_handlers._handle_craps_roll', new_callable=AsyncMock) as mock_internal_roll:
        mock_internal_roll.return_value = (f"{roll_result_str}\n\n---\n{user_name}, what's next?", get_craps_keyboard(channel_id))

        await craps_callback_handler(mock_update, mock_context)

        mock_callback_query.answer.assert_awaited_once()
        mock_internal_roll.assert_awaited_once_with(channel_id, user_name)

        expected_text, expected_keyboard = mock_internal_roll.return_value
        mock_callback_query.edit_message_text.assert_awaited_once_with(
            text=expected_text,
            reply_markup=expected_keyboard
        )
        mock_play_craps_round.assert_not_called()

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.get_showgame_text', new_callable=AsyncMock, return_value="Current Game Status...")
async def test_craps_callback_show(mock_get_showgame, mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_id = str(mock_callback_query.from_user.id)
    user_name = mock_callback_query.from_user.first_name
    chat_title = mock_callback_query.message.chat.title
    mock_callback_query.data = CALLBACK_SHOW

    await craps_callback_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    mock_get_showgame.assert_awaited_once_with(channel_id, user_id, user_name, chat_title)

    expected_text = f"Current Game Status...\n\n---\n{user_name}, what's next?"
    expected_keyboard = get_craps_keyboard(channel_id)

    mock_callback_query.edit_message_text.assert_awaited_once_with(
        text=expected_text,
        reply_markup=expected_keyboard
    )

@pytest.mark.asyncio
@patch('boombot.handlers.base_handlers.do_resetmygame', new_callable=AsyncMock, return_value="Your game data reset.")
async def test_craps_callback_reset(mock_do_reset, mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_id = str(mock_callback_query.from_user.id)
    user_name = mock_callback_query.from_user.first_name
    mock_callback_query.data = CALLBACK_RESET

    await craps_callback_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    mock_do_reset.assert_awaited_once_with(channel_id, user_id, user_name)

    expected_text = f"Your game data reset.\n\n---\n{user_name}, what's next?"
    expected_keyboard = get_craps_keyboard(channel_id)

    mock_callback_query.edit_message_text.assert_awaited_once_with(
        text=expected_text,
        reply_markup=expected_keyboard
    )

@pytest.mark.asyncio
async def test_craps_callback_bet_pass_come_out(mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_id = str(mock_callback_query.from_user.id)
    user_name = mock_callback_query.from_user.first_name
    mock_callback_query.data = CALLBACK_BET_PASS

    mock_game_data_manager.get_channel_data.return_value = {'craps_state': 1, 'craps_point': None}
    player_data = {'balance': '100.00', 'craps_bets': {}}
    mock_game_data_manager.get_player_data.return_value = player_data

    await craps_callback_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    expected_text = f"Select amount for Pass Line: (Balance: ${player_data['balance']})"
    expected_keyboard = get_bet_amount_keyboard("pass_line", Decimal(player_data['balance']))

    mock_callback_query.edit_message_text.assert_awaited_once_with(
        text=expected_text,
        reply_markup=expected_keyboard
    )

@pytest.mark.asyncio
async def test_craps_callback_bet_pass_point_on(mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_name = mock_callback_query.from_user.first_name # Use name from callback
    mock_callback_query.data = CALLBACK_BET_PASS

    mock_game_data_manager.get_channel_data.return_value = {'craps_state': 2, 'craps_point': 6} # Point is ON

    await craps_callback_handler(mock_update, mock_context)

    # Assert that the message text was edited with the error
    expected_text = f"Cannot place Pass Line bet when point is established.\n\n---\n{user_name}, what's next?"
    expected_keyboard = get_craps_keyboard(channel_id)
    mock_callback_query.edit_message_text.assert_awaited_once_with(
        text=expected_text,
        reply_markup=expected_keyboard
    )
    # Ensure answer was called only once (the initial acknowledgement)
    mock_callback_query.answer.assert_awaited_once()
    # Check that the initial answer call had no arguments
    call_args, call_kwargs = mock_callback_query.answer.await_args
    assert call_args == ()
    assert call_kwargs == {}

@pytest.mark.asyncio
async def test_craps_callback_place_bet_button(mock_place_craps_bet, mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_id = str(mock_callback_query.from_user.id)
    user_name = mock_callback_query.from_user.first_name
    bet_type = "pass_line"
    amount = "10"
    mock_callback_query.data = f"{CALLBACK_PLACE_BET_PREFIX}{bet_type}_{amount}"

    place_bet_result = f"{user_name} placed ${Decimal(amount):.2f} on Pass Line."
    mock_place_craps_bet.return_value = place_bet_result

    with patch('boombot.handlers.base_handlers._handle_craps_place_bet', new_callable=AsyncMock) as mock_internal_place:
        mock_internal_place.return_value = (f"{place_bet_result}\n\n---\n{user_name}, what's next?", get_craps_keyboard(channel_id))

        await craps_callback_handler(mock_update, mock_context)

        mock_callback_query.answer.assert_awaited_once()
        mock_internal_place.assert_awaited_once_with(mock_callback_query.data, channel_id, user_id, user_name)

        expected_text, expected_keyboard = mock_internal_place.return_value
        mock_callback_query.edit_message_text.assert_awaited_once_with(
            text=expected_text,
            reply_markup=expected_keyboard
        )
        mock_place_craps_bet.assert_not_called()

@pytest.mark.asyncio
async def test_craps_callback_back_main(mock_game_data_manager, mock_update, mock_context, mock_callback_query):
    channel_id = str(mock_callback_query.message.chat.id)
    user_name = mock_callback_query.from_user.first_name
    mock_callback_query.data = CALLBACK_BACK_TO_MAIN

    await craps_callback_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    expected_text = f"{user_name}, what's next?"
    expected_keyboard = get_craps_keyboard(channel_id)

    mock_callback_query.edit_message_text.assert_awaited_once_with(
        text=expected_text,
        reply_markup=expected_keyboard
    )

# --- Tests for bet_command ---

@pytest.mark.asyncio
async def test_bet_command_insufficient_args(mock_update, mock_context):
    mock_context.args = ["place_6"]
    await bet_command(mock_update, mock_context)
    expected_usage = (
        "Usage: /bet <bet_type> <amount>\n"
        "Example: /bet pass_line 10\n"
        "Use the 'Place Bet (Info)' button or /crapshelp for valid types."
    )
    mock_update.message.reply_text.assert_awaited_once_with(expected_usage)

@pytest.mark.asyncio
async def test_bet_command_place_without_number(mock_update, mock_context):
    mock_context.args = ["place", "10"]
    await bet_command(mock_update, mock_context)
    expected_usage = "Usage: /bet place <number> <amount>"
    mock_update.message.reply_text.assert_awaited_once_with(expected_usage)

@pytest.mark.asyncio
async def test_bet_command_place_with_number(mock_place_craps_bet, mock_game_data_manager, mock_update, mock_context):
    channel_id = str(mock_update.effective_chat.id)
    user_id = str(mock_update.effective_user.id)
    user_name = mock_update.effective_user.first_name
    mock_context.args = ["place", "8", "15"]
    expected_bet_type = "place_8"
    amount_str = "15"

    expected_result_str = f"{user_name} placed ${Decimal(amount_str):.2f} on Place 8."
    # Configure the synchronous mock return value
    mock_place_craps_bet.return_value = expected_result_str

    await bet_command(mock_update, mock_context)

    # Assert place_craps_bet was called correctly (synchronously)
    mock_place_craps_bet.assert_called_once_with(channel_id, user_id, user_name, expected_bet_type, amount_str, mock_game_data_manager)

    # Assert reply_text was awaited with the string result
    mock_update.message.reply_text.assert_awaited_once_with(expected_result_str)


@pytest.mark.asyncio
async def test_bet_command_standard_bet(mock_place_craps_bet, mock_game_data_manager, mock_update, mock_context):
    channel_id = str(mock_update.effective_chat.id)
    user_id = str(mock_update.effective_user.id)
    user_name = mock_update.effective_user.first_name
    bet_type = "field"
    amount_str = "5"
    mock_context.args = [bet_type, amount_str]

    expected_result_str = f"{user_name} placed ${Decimal(amount_str):.2f} on Field."
    # Configure the synchronous mock return value
    mock_place_craps_bet.return_value = expected_result_str

    await bet_command(mock_update, mock_context)

    # Assert place_craps_bet call (synchronously)
    mock_place_craps_bet.assert_called_once_with(channel_id, user_id, user_name, bet_type, amount_str, mock_game_data_manager)

    # Assert reply_text await
    mock_update.message.reply_text.assert_awaited_once_with(expected_result_str)
