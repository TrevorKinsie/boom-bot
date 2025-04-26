import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from boombot.games.zeus.zeus import zeus, wallet, spin_button, wallets, spin_grid, count_lines

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
    mock_update.message.reply_text.assert_called_once()

    args, kwargs = mock_update.message.reply_text.call_args

    # Updated text based on your latest zeus.py
    assert args[0] == (
        "⚡ Welcome to Zeus Slots (HARDCORE Edition)!\n\n"
        "You start with 100 coins.\nEach spin costs 10 coins.\n"
        "Try your luck!"
    )

    reply_markup = kwargs['reply_markup']
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert len(reply_markup.inline_keyboard) == 1
    assert len(reply_markup.inline_keyboard[0]) == 1
    button = reply_markup.inline_keyboard[0][0]
    assert button.text == "🎰 Spin"
    assert button.callback_data == "spin"

    assert 12345 in wallets
    assert wallets[12345]['coins'] == 100
    assert wallets[12345]['free_spins'] == 0

@pytest.mark.asyncio
async def test_wallet_command(mock_update_context):
    """Test the /wallet command."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 50, 'free_spins': 2}

    await wallet(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with(
        "💰 Coins: 50\n🎁 Free Spins: 2"
    )

@pytest.mark.asyncio
async def test_spin_button_no_coins(mock_update_context):
    """Test the spin button when the user has no coins or free spins."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 0, 'free_spins': 0}

    await spin_button(mock_update, mock_context)

    mock_update.callback_query.edit_message_text.assert_called_once_with(
        "😞 Not enough coins! Use /wallet to check your balance."
    )

@pytest.mark.asyncio
async def test_spin_button_with_coins(mock_update_context):
    """Test the spin button when the user has enough coins."""
    mock_update, mock_context = mock_update_context
    wallets[12345] = {'coins': 20, 'free_spins': 0}

    # Mock a winning grid
    winning_grid = [
        ['⚡', '⚡', '⚡', '⚡', '⚡'],
        ['⚡', '⚡', '⚡', '⚡', '⚡'],
        ['⚡', '⚡', '⚡', '⚡', '⚡'],
        ['⚡', '⚡', '⚡', '⚡', '⚡'],
        ['⚡', '⚡', '⚡', '⚡', '⚡']
    ]
    
    matches = [('⚡', 5)]  # Adjust to match the real count_lines output style

    with patch('boombot.games.zeus.zeus.spin_grid', return_value=winning_grid), \
         patch('boombot.games.zeus.zeus.spin_grid', return_value=matches):
        await spin_button(mock_update, mock_context)

    mock_update.callback_query.edit_message_text.assert_called_once()

    # After a 5 of a kind win, coins should have increased
    assert wallets[12345]['coins'] > 20
    assert wallets[12345]['free_spins'] > 0
