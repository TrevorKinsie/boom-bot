import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from zeus import zeus, wallet, spin_button, wallets
from unittest.mock import AsyncMock, MagicMock, patch, ANY # Import ANY
from zeus import zeus, wallet, spin_button, wallets, spin_grid, count_lines

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
@pytest.mark.asyncio
async def test_zeus_command(mock_update_context):
    """Test the /zeus command."""
    mock_update, mock_context = mock_update_context

    # Act
    await zeus(mock_update, mock_context)
    await zeus(mock_update, mock_context)

    # Assert
    mock_update.message.reply_text.assert_called_once()

    # Extract the actual arguments passed to reply_text
    args, kwargs = mock_update.message.reply_text.call_args

    # Check the message text
    assert args[0] == (
        "⚡ Welcome to Zeus!\n\n"
        "You start with 100 coins.\nEach spin costs 10 coins.\n"
        "Use the button below to spin!"
    )

    # Check the reply_markup structure
    reply_markup = kwargs['reply_markup']
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert len(reply_markup.inline_keyboard) == 1
    assert len(reply_markup.inline_keyboard[0]) == 1
    button = reply_markup.inline_keyboard[0][0]
    assert button.text == "🎰 Spin"
    assert button.callback_data == "spin"

    # Check wallet initialization
        "Use the button below to spin!",
        reply_markup=ANY # Use ANY to match any reply_markup
    )
    assert 12345 in wallets
    assert wallets[12345]['coins'] == 100
    assert wallets[12345]['free_spins'] == 0

@pytest.mark.asyncio
async def test_wallet_command(mock_update_context):
    """Test the /wallet command."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 50, 'free_spins': 2}

    # Act
    await wallet(mock_update, mock_context)

    # Assert
    mock_update.message.reply_text.assert_called_once_with(
        "💰 Coins: 50\n🎁 Free Spins: 2"
    )

@pytest.mark.asyncio
async def test_spin_button_no_coins(mock_update_context):
    """Test the spin button when the user has no coins or free spins."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 0, 'free_spins': 0}

    # Act
    await spin_button(mock_update, mock_context)

    # Assert
    mock_update.callback_query.edit_message_text.assert_called_once_with(
        "😞 Not enough coins! Use /wallet to check your balance."
    )

@pytest.mark.asyncio
async def test_spin_button_with_coins(mock_update_context):
    """Test the spin button when the user has enough coins."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 20, 'free_spins': 0}

    # Mock spin_grid and count_lines
    with patch('zeus.spin_grid', return_value=[['⚡', '⚡', '⚡', '⚡', '⚡']] * 5), \
         patch('zeus.count_lines', return_value={'⚡': 5}):
        await spin_button(mock_update, mock_context)

    # Assert
    mock_update.callback_query.edit_message_text.assert_called_once()
    assert wallets[12345]['coins'] > 20  # Coins should increase after a win
    assert wallets[12345]['free_spins'] > 0  # Free spins should increase after a win