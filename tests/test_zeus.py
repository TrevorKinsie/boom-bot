import pytest
from unittest.mock import AsyncMock, MagicMock
from zeus import zeus, wallet, spin_button, wallets

@pytest.fixture
def mock_update_context():
    """Fixture to mock Update and Context objects."""
    mock_update = MagicMock()
    mock_context = MagicMock()
    mock_update.effective_user.id = 12345
    mock_update.message.reply_text = AsyncMock()
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.from_user.id = 12345
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()
    return mock_update, mock_context

@pytest.mark.asyncio
async def test_zeus_command(mock_update_context):
    """Test the /zeus command."""
    mock_update, mock_context = mock_update_context

    # Act
    await zeus(mock_update, mock_context)

    # Assert
    mock_update.message.reply_text.assert_called_once_with(
        "⚡ Welcome to Zeus!\n\n"
        "You start with 100 coins.\nEach spin costs 10 coins.\n"
        "Use the button below to spin!",
        reply_markup=MagicMock()
    )
    assert 12345 in wallets
    assert wallets[12345]['coins'] == 100
    assert wallets[12345]['free_spins'] == 0