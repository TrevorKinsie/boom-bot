import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update
from telegram.ext import ContextTypes

from boombot.handlers.beast_handlers import whowouldwin_command
from boombot.utils.replies import VICTORY_REASONS, BATTLE_OUTCOMES, CLOSE_MATCH_OUTCOMES

# --- Fixtures for testing ---

@pytest.fixture
def mock_update():
    """Creates a mock Update object with nested mocks."""
    update = MagicMock(spec=Update)
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    """Creates a mock ContextTypes object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context

# --- Tests for whowouldwin_command ---

@pytest.mark.asyncio
async def test_whowouldwin_no_args(mock_update, mock_context):
    """Test the command with no arguments (should show usage instructions)."""
    await whowouldwin_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    # Check that the help text is sent
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Usage:" in call_args
    assert "/whowouldwin" in call_args
    assert "Examples:" in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=[])
async def test_whowouldwin_no_contenders_found(mock_extract_contenders, mock_update, mock_context):
    """Test when no contenders can be extracted from the input."""
    mock_context.args = ["some", "invalid", "input"]
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("some invalid input")
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "I couldn't identify who's fighting" in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["lions", "tigers"])
@patch('boombot.handlers.beast_handlers.random.random', return_value=0.3)  # First contender wins
@patch('boombot.handlers.beast_handlers.random.choice')
async def test_whowouldwin_two_contenders_first_wins(mock_random_choice, mock_random, mock_extract_contenders, 
                                                    mock_update, mock_context):
    """Test with two contenders where the first one wins."""
    mock_context.args = ["lions", "vs", "tigers"]
    mock_random_choice.side_effect = ["superior strength", "In an epic battle between {winner} and {loser}, {winner} would emerge victorious due to their {reason}."]
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("lions vs tigers")
    mock_random_choice.assert_any_call(VICTORY_REASONS)
    mock_random_choice.assert_any_call(BATTLE_OUTCOMES)
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Lions" in call_args
    assert "tigers" in call_args
    assert "superior strength" in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["lions", "tigers"])
@patch('boombot.handlers.beast_handlers.random.random', return_value=0.7)  # Second contender wins
@patch('boombot.handlers.beast_handlers.random.choice')
async def test_whowouldwin_two_contenders_second_wins(mock_random_choice, mock_random, mock_extract_contenders, 
                                                     mock_update, mock_context):
    """Test with two contenders where the second one wins."""
    mock_context.args = ["lions", "vs", "tigers"]
    mock_random_choice.side_effect = ["tactical superiority", "No contest - {winner} would demolish {loser} thanks to their {reason}."]
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("lions vs tigers")
    mock_random_choice.assert_any_call(VICTORY_REASONS)
    mock_random_choice.assert_any_call(BATTLE_OUTCOMES)
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Tigers" in call_args
    assert "lions" in call_args
    assert "tactical superiority" in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["ninjas", "pirates", "robots"])
@patch('boombot.handlers.beast_handlers.random.random', return_value=0.1)  # Close match
@patch('boombot.handlers.beast_handlers.random.choice')
async def test_whowouldwin_multiple_contenders(mock_random_choice, mock_random, mock_extract_contenders, 
                                              mock_update, mock_context):
    """Test with more than two contenders."""
    mock_context.args = ["ninjas", "vs", "pirates", "vs", "robots"]
    # First random.choice selects "ninjas" as winner, second selects "pirates" as loser,
    # third selects reason, fourth selects template
    mock_random_choice.side_effect = ["ninjas", "pirates", "ancient powers", 
                                     "It's a close one, but {winner} edges out {loser} thanks to slightly better {reason}."]
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("ninjas vs pirates vs robots")
    
    # Check that random.choice was called with the right arguments
    assert mock_random_choice.call_count == 4
    winners_call = mock_random_choice.mock_calls[0][1][0]
    assert set(winners_call) == {"ninjas", "pirates", "robots"}
    
    remaining_call = mock_random_choice.mock_calls[1][1][0]
    # The remaining list should have exactly 2 items (3 contenders - 1 winner)
    assert len(remaining_call) == 2
    # The remaining list should not contain the winner
    assert "ninjas" not in remaining_call
    
    mock_random_choice.assert_any_call(VICTORY_REASONS)
    mock_random_choice.assert_any_call(CLOSE_MATCH_OUTCOMES)
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Ninjas" in call_args
    assert "pirates" in call_args
    assert "ancient powers" in call_args
    assert "edges out" in call_args  # From the CLOSE_MATCH_OUTCOMES template

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["cats", "dogs"])
@patch('boombot.handlers.beast_handlers.random.random', return_value=0.9)  # Second contender wins, not close match
@patch('boombot.handlers.beast_handlers.random.choice')
async def test_whowouldwin_not_close_match(mock_random_choice, mock_random, mock_extract_contenders, 
                                          mock_update, mock_context):
    """Test where the match is not considered close."""
    mock_context.args = ["cats", "or", "dogs"]
    mock_random_choice.side_effect = ["higher intelligence", 
                                     "{winner} vs {loser}? {winner} takes this one with {reason}."]
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("cats or dogs")
    mock_random_choice.assert_any_call(VICTORY_REASONS)
    mock_random_choice.assert_any_call(BATTLE_OUTCOMES)  # Should use regular outcomes, not close match
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Dogs vs cats?" in call_args
    assert "higher intelligence" in call_args