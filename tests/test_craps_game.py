# test_craps_game.py
import pytest
import random
from unittest.mock import patch
from decimal import Decimal
from craps_game import roll_dice, _calculate_winnings, play_craps_round, place_bet
from data_manager import DataManager
import craps_game # Import the module itself to access game_state

# --- Test Rolling ---

@patch('random.randint', side_effect=[1, 1])
def test_roll_dice(mock_randint):
    die1, die2, roll_sum = roll_dice()
    assert die1 == 1
    assert die2 == 1
    assert roll_sum == 2

# --- Test Winnings Calculation ---

@pytest.mark.parametrize("bet_type, bet_amount, die1, die2, point, expected_winnings", [
    # Come out roll 7 (3+4), Pass Line wins 1:1
    ('pass_line', Decimal('10'), 3, 4, None, Decimal('10')), # Corrected expected winnings from 0 to 10
    ('pass_line', Decimal('10'), 3, 4, 7, Decimal('10')),
    ('dont_pass', Decimal('10'), 1, 1, None, Decimal('10')),
    ('dont_pass', Decimal('10'), 3, 4, 7, Decimal('10')),
    # Roll 4 (2+2), Field bet wins 1:1
    ('field', Decimal('10'), 2, 2, None, Decimal('10')), # Corrected expected winnings from 0 to 10
    ('field', Decimal('10'), 1, 1, None, Decimal('20')),
    ('place_4', Decimal('10'), 2, 2, 4, Decimal('18')),
    ('hard_4', Decimal('10'), 2, 2, None, Decimal('70')),
    ('any_craps', Decimal('10'), 1, 1, None, Decimal('70')),
    ('any_seven', Decimal('10'), 3, 4, None, Decimal('40')),
    ('two', Decimal('10'), 1, 1, None, Decimal('300')),
    ('three', Decimal('10'), 1, 2, None, Decimal('150')),
    ('eleven', Decimal('10'), 5, 6, None, Decimal('150')),
    ('twelve', Decimal('10'), 6, 6, None, Decimal('300')),
])
def test_calculate_winnings(bet_type, bet_amount, die1, die2, point, expected_winnings):
    winnings = _calculate_winnings(bet_type, bet_amount, die1, die2, point)
    assert winnings == expected_winnings

# --- Test Playing a Round ---

@pytest.fixture(scope="function") # Ensure a new instance for each test function
def data_manager():
    dm = DataManager()
    # Clear data before test run as well for extra safety
    dm.data.clear()
    yield dm # Test runs here
    # Explicitly clear data after test
    dm.data.clear()

def test_play_craps_round_no_bets(data_manager):
    channel_id = "test_channel_no_bets" # Use unique channel ID
    # Ensure clean state (though the function should handle this now)
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.COME_OUT_PHASE, 'craps_point': None})
    result = play_craps_round(channel_id, data_manager)
    # Updated expected message based on the change in craps_game.py
    assert "No bets placed in the channel. Use /bet to place bets." in result

# Use patch to control the dice roll for predictable outcome
@patch('craps_game.roll_dice', return_value=(3, 2, 5)) # Force a roll of 5
def test_play_craps_round_with_bets(mock_roll, data_manager):
    channel_id = "test_channel_with_bets" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"

    # *** Explicitly set initial state for this test ***
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.COME_OUT_PHASE, 'craps_point': None})

    data_manager.save_player_data(channel_id, user_id, {
        'balance': '100.00',
        'craps_bets': {'pass_line': '10.00'},
        'display_name': user_name
    })
    result = play_craps_round(channel_id, data_manager)
    # Assert that the point is set to 5 and the message indicates this
    assert "Rolled 3 + 2 = 5" in result
    # Check the state change message specifically
    assert "Point is now 5. /roll again!" in result
    # Check that the bet wasn't resolved yet (it shouldn't be mentioned as winning/losing)
    assert "Pass Line" not in result # Pass Line bet doesn't resolve on point establishment
    # Verify point was stored via data_manager
    channel_data = data_manager.get_channel_data(channel_id)
    assert channel_data.get('craps_point') == 5
    assert channel_data.get('craps_state') == craps_game.POINT_PHASE

# --- Test Placing Bets ---

def test_place_bet_valid(data_manager):
    channel_id = "test_channel_place_valid" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"

    # *** Explicitly set initial state for this test (Come Out Phase) ***
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.COME_OUT_PHASE, 'craps_point': None})

    result = place_bet(channel_id, user_id, user_name, 'pass_line', '10.00', data_manager)
    assert "placed $10.00 on Pass Line" in result
    # Verify balance and bet storage
    player_data = data_manager.get_player_data(channel_id, user_id)
    assert player_data['balance'] == '90.00'
    assert player_data['craps_bets'] == {'pass_line': '10.00'}

def test_place_bet_invalid_amount(data_manager):
    channel_id = "test_channel_place_invalid_amount" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"
    # Ensure clean state
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.COME_OUT_PHASE, 'craps_point': None})
    data_manager.save_player_data(channel_id, user_id, {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name})

    result = place_bet(channel_id, user_id, user_name, 'pass_line', '-10.00', data_manager)
    assert "Bet amount must be positive" in result
    # Verify balance didn't change
    player_data = data_manager.get_player_data(channel_id, user_id)
    assert player_data['balance'] == '100.00'

def test_place_bet_invalid_type(data_manager):
    channel_id = "test_channel_place_invalid_type" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"
    # Ensure clean state
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.COME_OUT_PHASE, 'craps_point': None})
    data_manager.save_player_data(channel_id, user_id, {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name})

    result = place_bet(channel_id, user_id, user_name, 'invalid_bet', '10.00', data_manager)
    assert "Invalid bet type" in result
     # Verify balance didn't change
    player_data = data_manager.get_player_data(channel_id, user_id)
    assert player_data['balance'] == '100.00'

# Add a test for placing bet during point phase
def test_place_bet_during_point_phase_invalid(data_manager):
    channel_id = "test_channel_place_point_invalid" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"

    # *** Set state to POINT_PHASE with point = 8 ***
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.POINT_PHASE, 'craps_point': 8})
    data_manager.save_player_data(channel_id, user_id, {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name})

    result = place_bet(channel_id, user_id, user_name, 'pass_line', '10.00', data_manager)
    assert "Cannot place Pass Line bet when point is 8" in result
     # Verify balance didn't change
    player_data = data_manager.get_player_data(channel_id, user_id)
    assert player_data['balance'] == '100.00'

def test_place_bet_during_point_phase_valid(data_manager):
    channel_id = "test_channel_place_point_valid" # Use unique channel ID
    user_id = "test_user"
    user_name = "Test User"

    # *** Set state to POINT_PHASE with point = 6 ***
    data_manager.save_channel_data(channel_id, {'craps_state': craps_game.POINT_PHASE, 'craps_point': 6})
    data_manager.save_player_data(channel_id, user_id, {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name})

    # Placing a Place bet IS valid during point phase
    result = place_bet(channel_id, user_id, user_name, 'place_6', '12.00', data_manager)
    assert "placed $12.00 on Place 6" in result
    # Verify balance and bet storage
    player_data = data_manager.get_player_data(channel_id, user_id)
    assert player_data['balance'] == '88.00'
    assert player_data['craps_bets'] == {'place_6': '12.00'}
