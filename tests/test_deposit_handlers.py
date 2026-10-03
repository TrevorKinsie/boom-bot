import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update
from telegram.ext import ContextTypes

from boombot.handlers.deposit_handlers import frigged_deposit_command

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

# --- Tests for frigged_deposit_command ---

@pytest.mark.asyncio
async def test_frigged_deposit_no_args(mock_update, mock_context):
    """Test the command with no arguments (should show usage instructions)."""
    await frigged_deposit_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert "Who frigged the deposit?" in call_args
    assert "Usage: /friggedthedeposit [name]" in call_args
    assert "Example: /friggedthedeposit Kevin" in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.deposit_handlers.get_openrouter_response')
async def test_frigged_deposit_with_name_success(mock_get_openrouter_response, mock_update, mock_context):
    """Test the command with a name, expecting a successful LLM response."""
    test_name = "Kevin"
    mock_context.args = [test_name]
    expected_llm_response = f"{test_name} frigged the deposit by attempting to pay the landlord in glitter."
    mock_get_openrouter_response.return_value = expected_llm_response
    
    await frigged_deposit_command(mock_update, mock_context)
    
    llm_call_args = mock_get_openrouter_response.call_args[0][0]
    assert test_name in llm_call_args 
    assert "frigged the deposit by" in llm_call_args # Check that the prompt is constructed correctly

    mock_update.message.reply_text.assert_awaited_once_with(expected_llm_response)

@pytest.mark.asyncio
@patch('boombot.handlers.deposit_handlers.get_openrouter_response')
@patch('boombot.handlers.deposit_handlers.random.randint')
async def test_frigged_deposit_with_name_llm_error(mock_randint, mock_get_openrouter_response, mock_update, mock_context):
    """Test the command with a name, simulating an error from the LLM."""
    test_name = "Alice"
    mock_context.args = [test_name]
    mock_get_openrouter_response.side_effect = Exception("LLM API is down")
    mock_randint.return_value = 100 # Mocking the random tip amount for deterministic test
    
    await frigged_deposit_command(mock_update, mock_context)
    
    llm_call_args = mock_get_openrouter_response.call_args[0][0]
    assert test_name in llm_call_args

    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.await_args[0][0]
    assert f"I tried to figure out how {test_name} frigged the deposit" in call_args
    assert "it seems the deposit was returned, along with a tip of $100.00 for excellent service." in call_args

@pytest.mark.asyncio
@patch('boombot.handlers.deposit_handlers.get_openrouter_response')
async def test_frigged_deposit_llm_response_does_not_start_with_name(mock_get_openrouter_response, mock_update, mock_context):
    """Test when LLM response doesn't start with the name, it should still send the raw LLM response."""
    test_name = "Bob"
    mock_context.args = [test_name]
    llm_response_without_name = "By putting a trampoline in the living room to test newton's laws of motion, Jeremy Renner frigged the deposit."
    mock_get_openrouter_response.return_value = llm_response_without_name
    
    await frigged_deposit_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once_with(llm_response_without_name)

