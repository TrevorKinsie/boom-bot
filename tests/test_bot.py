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
    # Update the patch targets to use the new module paths
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
    # Check if the returned object is an Application instance
    assert isinstance(application, Application)

    # Check if the token is set correctly
    assert application.bot.token == TEST_TOKEN

    # Check if handlers are registered (check types and commands/patterns)
    handler_types = [type(h) for h in application.handlers[0]] # Handlers are in group 0 by default
    command_handlers = {h.callback.__name__: h.commands for h in application.handlers[0] if isinstance(h, CommandHandler)}
    message_handlers = [h for h in application.handlers[0] if isinstance(h, MessageHandler)]
    callback_handlers = [h for h in application.handlers[0] if isinstance(h, CallbackQueryHandler)]

    # Assert handler types exist
    assert CommandHandler in handler_types
    assert MessageHandler in handler_types
    assert CallbackQueryHandler in handler_types

    # Assert specific command handlers
    assert "boom_command" in command_handlers
    assert command_handlers["boom_command"] == frozenset({"boom"})
    assert "booms_command" in command_handlers
    assert command_handlers["booms_command"] == frozenset({"howmanybooms"})
    assert "start_craps_command" in command_handlers
    assert command_handlers["start_craps_command"] == frozenset({"craps"})
    assert "bet_command" in command_handlers
    assert command_handlers["bet_command"] == frozenset({"bet"})
    assert "start_roulette_command" in command_handlers
    assert command_handlers["start_roulette_command"] == frozenset({"roulette"})

    # Assert Zeus handlers
    assert "zeus" in command_handlers
    assert command_handlers["zeus"] == frozenset({"zeus"})

    spin_handler = next((h for h in callback_handlers if h.callback.__name__ == "spin_button"), None)
    assert spin_handler is not None
    assert spin_handler.pattern.pattern == '^spin$'

    # Assert message handler (photo caption)
    assert len(message_handlers) == 1
    message_handler = message_handlers[0]
    assert message_handler.callback.__name__ == "handle_photo_caption"
    # Check the type of the filter using the identified class
    assert isinstance(message_handler.filters, filters._MergedFilter)

    # Assert callback query handlers
    assert len(callback_handlers) == 3
    # Find handlers by pattern or callback name for robustness
    craps_handler = next((h for h in callback_handlers if h.callback.__name__ == "craps_callback_handler"), None)
    roulette_handler = next((h for h in callback_handlers if h.callback.__name__ == "roulette_callback_handler"), None)
    spin_handler = next((h for h in callback_handlers if h.callback.__name__ == "spin_button"), None)

    assert craps_handler is not None
    assert craps_handler.pattern.pattern == '^craps_'

    assert roulette_handler is not None
    assert roulette_handler.pattern.pattern == '^roulette_'

    assert spin_handler is not None
    assert spin_handler.pattern.pattern == '^spin$'

    # Check if NLTK setup was called
    mock_setup_func.assert_called_once()
    mock_load_func.assert_called_once()
