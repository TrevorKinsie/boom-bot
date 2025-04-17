# test_bot.py
import pytest
import random
from unittest.mock import AsyncMock, MagicMock, patch

# Make sure sassy lists are importable if bot.py is run directly
# In a real package structure, you'd import directly from the module
try:
    from bot import (
        boom_command,
        SASSY_REPLIES_HIGH,
        SASSY_REPLIES_LOW,
        SASSY_REPLIES_INVALID,
    )
except ImportError:
    # This is a fallback if running pytest from a different structure
    # It assumes bot.py is in the same directory
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from bot import (
        boom_command,
        SASSY_REPLIES_HIGH,
        SASSY_REPLIES_LOW,
        SASSY_REPLIES_INVALID,
    )

# --- Mocks for Telegram Objects ---

@pytest.fixture
def mock_update():
    """Creates a mock Update object."""
    update = MagicMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.message = MagicMock()
    update.message.message_id = 67890
    update.message.reply_to_message = None # Default: not a reply
    update.message.reply_text = AsyncMock() # Mock the reply method
    return update

@pytest.fixture
def mock_context():
    """Creates a mock ContextTypes object."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.set_message_reaction = AsyncMock() # Mock the reaction method
    context.args = [] # Default: no arguments
    return context

# --- Test Cases ---

@pytest.mark.asyncio
@patch('bot.random.randint', return_value=3) # Mock random number generation
async def test_boom_no_args_sends_random_booms(mock_randint, mock_update, mock_context):
    """Test /boom with no args sends 1-5 booms."""
    # Arrange: No args (default in fixture)

    # Act
    await boom_command(mock_update, mock_context)

    # Assert
    mock_randint.assert_called_once_with(1, 5)
    mock_update.message.reply_text.assert_awaited_once_with("💥💥💥")
    mock_context.bot.set_message_reaction.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize("num_booms", [1, 2, 3, 4, 5])
async def test_boom_valid_args_sends_specific_booms(num_booms, mock_update, mock_context):
    """Test /boom with valid numeric args (1-5)."""
    # Arrange
    mock_context.args = [str(num_booms)]

    # Act
    await boom_command(mock_update, mock_context)

    # Assert
    expected_booms = "💥" * num_booms
    mock_update.message.reply_text.assert_awaited_once_with(expected_booms)
    mock_context.bot.set_message_reaction.assert_not_called()

@pytest.mark.asyncio
@patch('bot.random.choice', return_value="Test Sassy High") # Mock random choice
async def test_boom_high_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    """Test /boom with numeric arg > 5."""
    # Arrange
    mock_context.args = ["7"]

    # Act
    await boom_command(mock_update, mock_context)

    # Assert
    mock_choice.assert_called_once_with(SASSY_REPLIES_HIGH)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy High")
    mock_context.bot.set_message_reaction.assert_not_called()

@pytest.mark.asyncio
@patch('bot.random.choice', return_value="Test Sassy Low") # Mock random choice
async def test_boom_low_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    """Test /boom with numeric arg < 1."""
    # Arrange
    mock_context.args = ["0"]

    # Act
    await boom_command(mock_update, mock_context)

    # Assert
    mock_choice.assert_called_once_with(SASSY_REPLIES_LOW)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy Low")
    mock_context.bot.set_message_reaction.assert_not_called()


@pytest.mark.asyncio
@patch('bot.random.choice', return_value="Test Sassy Invalid") # Mock random choice
async def test_boom_invalid_args_sends_sassy_reply(mock_choice, mock_update, mock_context):
    """Test /boom with non-numeric arg."""
    # Arrange
    mock_context.args = ["hello"]

    # Act
    await boom_command(mock_update, mock_context)

    # Assert
    mock_choice.assert_called_once_with(SASSY_REPLIES_INVALID)
    mock_update.message.reply_text.assert_awaited_once_with("Test Sassy Invalid")
    mock_context.bot.set_message_reaction.assert_not_called()
