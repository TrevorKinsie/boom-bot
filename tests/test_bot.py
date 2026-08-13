# test_bot.py
import pytest
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from unittest.mock import patch, MagicMock, AsyncMock

# Import from the new package structure
from boombot.core.bot import create_application

# Use a dummy token for testing
TEST_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


@pytest.fixture
def mock_nltk_setup():
    """Fixture to mock NLTK setup functions."""
    with patch('boombot.core.bot.setup_nltk') as mock_setup, \
         patch('boombot.core.bot.load_answers') as mock_load:
        yield mock_setup, mock_load


# --- Test Cases ---

def test_create_application(mock_nltk_setup):
    """Tests if the create_application function builds the app correctly."""
    # Arrange
    mock_setup_func, mock_load_func = mock_nltk_setup

    # Act
    application = create_application(TEST_TOKEN)

    # Assert
    assert isinstance(application, Application)
    assert application.bot.token == TEST_TOKEN

    handler_types = [type(h) for h in application.handlers[0]]
    command_handlers = {h.callback.__name__: h.commands for h in application.handlers[0] if isinstance(h, CommandHandler)}
    message_handlers = [h for h in application.handlers[0] if isinstance(h, MessageHandler)]
    callback_handlers = [h for h in application.handlers[0] if isinstance(h, CallbackQueryHandler)]

    # Assert handler types exist
    assert CommandHandler in handler_types
    assert MessageHandler in handler_types
    assert CallbackQueryHandler in handler_types

    # --- Legacy core commands ---
    assert "boom_command" in command_handlers
    assert command_handlers["boom_command"] == frozenset({"boom"})
    assert "booms_command" in command_handlers
    assert command_handlers["booms_command"] == frozenset({"howmanybooms"})

    # --- Beast Wars / deposit ---
    assert "whowouldwin_command" in command_handlers
    assert command_handlers["whowouldwin_command"] == frozenset({"whowouldwin"})
    assert "frigged_deposit_command" in command_handlers
    assert command_handlers["frigged_deposit_command"] == frozenset({"friggedthedeposit"})

    # --- Enterprise Casino command surface ---
    assert "wallet_command" in command_handlers
    assert command_handlers["wallet_command"] == frozenset({"wallet"})
    assert "leaderboard_command" in command_handlers
    assert command_handlers["leaderboard_command"] == frozenset({"leaderboard"})
    assert "reset_wallet_command" in command_handlers
    assert command_handlers["reset_wallet_command"] == frozenset({"resetwallet"})
    assert "roulette_command" in command_handlers
    assert command_handlers["roulette_command"] == frozenset({"roulette"})
    assert "roulette_spin_command" in command_handlers
    assert command_handlers["roulette_spin_command"] == frozenset({"roulettespin"})
    assert "craps_command" in command_handlers
    assert command_handlers["craps_command"] == frozenset({"craps"})
    assert "craps_roll_command" in command_handlers
    assert command_handlers["craps_roll_command"] == frozenset({"crapsroll"})
    assert "zeus_command" in command_handlers
    assert command_handlers["zeus_command"] == frozenset({"zeus"})

    # --- Chess Challenge commands ---
    assert command_handlers["start_command"] == frozenset({"start"})
    assert command_handlers["help_command"] == frozenset({"help"})
    assert command_handlers["new_game_command"] == frozenset({"newgame"})
    assert command_handlers["move_command"] == frozenset({"move"})

    # --- Chess callback handler remains registered ---
    chess_callback_handler = next(
        h for h in callback_handlers if h.callback.__name__ == "callback_query_handler"
    )
    assert chess_callback_handler.pattern.pattern.startswith("^(difficulty_")

    # --- Message handlers (photo captions plus chess move replies) ---
    message_handler = next(
        h for h in message_handlers if h.callback.__name__ == "handle_photo_caption"
    )
    assert message_handler.callback.__name__ == "handle_photo_caption"
    assert isinstance(message_handler.filters, filters._MergedFilter)
    chess_reply_handler = next(
        h for h in message_handlers if h.callback.__name__ == "reply_move_handler"
    )
    assert isinstance(chess_reply_handler.filters, filters._MergedFilter)

    # The casino platform container is wired into bot_data for lifecycle cleanup.
    assert "casino_container" in application.bot_data

    # Check if NLTK setup was called
    mock_setup_func.assert_called_once()
    mock_load_func.assert_called_once()
