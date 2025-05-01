import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update
from telegram.ext import ContextTypes

from boombot.handlers.beast_handlers import whowouldwin_command
from boombot.utils.replies import VICTORY_REASONS, BATTLE_OUTCOMES, CLOSE_MATCH_OUTCOMES
from boombot.utils.llm import get_openrouter_response

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
@patch('boombot.handlers.beast_handlers.get_openrouter_response')
async def test_whowouldwin_two_contenders_first_wins(mock_get_openrouter_response, mock_extract_contenders, 
                                                    mock_update, mock_context):
    """Test with two contenders where the first one wins."""
    mock_context.args = ["lions", "vs", "tigers"]
    mock_get_openrouter_response.return_value = "The fierce battle between lions and tigers was a spectacle of raw strength and agility. The lion, with its majestic roar and formidable size, seemed to possess an almost divine power, while the tiger, with its stealth and cunning, demonstrated remarkable adaptability. In the end, it was the lion that triumphed, showcasing unparalleled dominance and sheer strength, leaving the tiger in awe. The lion emerged victorious, its pride and power a testament to nature's grandeur."
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("lions vs tigers")
    mock_get_openrouter_response.assert_called_once_with("Who would win in a battle between lions vs tigers?")
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "lion" in call_args.lower()
    assert "tiger" in call_args.lower()

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["lions", "tigers"])
@patch('boombot.handlers.beast_handlers.get_openrouter_response')
async def test_whowouldwin_two_contenders_second_wins(mock_get_openrouter_response, mock_extract_contenders,
                                                     mock_update, mock_context):
    """Test with two contenders where the second one wins."""
    mock_context.args = ["lions", "vs", "tigers"]
    mock_get_openrouter_response.return_value = "The lion, with its majestic might and regal presence, would decisively emerge victorious, crushing the tiger in the fierce encounter, showcasing unparalleled dominance and strength."
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("lions vs tigers")
    mock_get_openrouter_response.assert_called_once_with("Who would win in a battle between lions vs tigers?")
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "lion" in call_args.lower()
    assert "tiger" in call_args.lower()

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["ninjas", "pirates", "robots"])
@patch('boombot.handlers.beast_handlers.get_openrouter_response')
async def test_whowouldwin_multiple_contenders(mock_get_openrouter_response, mock_extract_contenders, 
                                              mock_update, mock_context):
    """Test with more than two contenders."""
    mock_context.args = ["ninjas", "vs", "pirates", "vs", "robots"]
    mock_get_openrouter_response.return_value = "In a dramatic clash, ninjas, with their agility and deadly skills, would emerge victorious, followed closely by a fierce battle between pirates and robots, each uniting their unique strengths to outmaneuver each other until the robots, with their advanced technology and strategic prowess, claim the ultimate victory over the agile ninjas and the cunning pirates."
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("ninjas vs pirates vs robots")
    mock_get_openrouter_response.assert_called_once_with("Who would win in a battle between ninjas vs pirates vs robots?")
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "ninjas" in call_args.lower()
    assert "pirates" in call_args.lower()
    assert "robots" in call_args.lower()

@pytest.mark.asyncio
@patch('boombot.handlers.beast_handlers.extract_contenders', return_value=["cats", "dogs"])
@patch('boombot.handlers.beast_handlers.get_openrouter_response')
async def test_whowouldwin_not_close_match(mock_get_openrouter_response, mock_extract_contenders,
                                          mock_update, mock_context):
    """Test where the match is not considered close."""
    mock_context.args = ["cats", "or", "dogs"]
    mock_get_openrouter_response.return_value = "In a fierce battle of cats vs dogs, the feline warriors, with their sharp claws and agile paws, would emerge victorious. The canine pack, with their powerful bodies and sharp teeth, would struggle against their feline counterparts' agility, ultimately succumbing to their superior speed and stealth. The felines, with their cunning and quick thinking, would outmaneuver the dogs, securing the victory in a dazzling display of ferocious might and relentless persistence."
    
    await whowouldwin_command(mock_update, mock_context)
    
    mock_extract_contenders.assert_called_once_with("cats or dogs")
    mock_get_openrouter_response.assert_called_once_with("Who would win in a battle between cats vs dogs?")
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "cats" in call_args.lower()
    assert "dogs" in call_args.lower()