# test_craps_game.py
import pytest
import random
from unittest.mock import patch
from decimal import Decimal
from craps_game import roll_dice, _calculate_winnings, play_craps_round, place_bet
from data_manager import DataManager

# --- Test Rolling ---

@patch('random.randint', side_effect=[1, 1])
def test_roll_dice(mock_randint):
    die1, die2, roll_sum = roll_dice()
    assert die1 == 1
    assert die2 == 1
    assert roll_sum == 2

# --- Test Winnings Calculation ---

@pytest.mark.parametrize("bet_type, bet_amount, die1, die2, point, expected_winnings", [
    ('pass_line', Decimal('10'), 3, 4, None, Decimal('0')),
    ('pass_line', Decimal('10'), 3, 4, 7, Decimal('10')),
    ('dont_pass', Decimal('10'), 1, 1, None, Decimal('10')),
    ('dont_pass', Decimal('10'), 3, 4, 7, Decimal('10')),
    ('field', Decimal('10'), 2, 2, None, Decimal('0')),
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

@pytest.fixture
def data_manager():
    return DataManager()

def test_play_craps_round_no_bets(data_manager):
    channel_id = "test_channel"
    result = play_craps_round(channel_id, data_manager)
    assert "No bets placed in the channel" in result

def test_play_craps_round_with_bets(data_manager):
    channel_id = "test_channel"
    user_id = "test_user"
    user_name = "Test User"
    data_manager.save_player_data(channel_id, user_id, {
        'balance': '100.00',
        'craps_bets': {'pass_line': '10.00'},
        'display_name': user_name
    })
    result = play_craps_round(channel_id, data_manager)
    assert "Rolled" in result
    assert "Pass Line" in result

# --- Test Placing Bets ---

def test_place_bet_valid(data_manager):
    channel_id = "test_channel"
    user_id = "test_user"
    user_name = "Test User"
    result = place_bet(channel_id, user_id, user_name, 'pass_line', '10.00', data_manager)
    assert "placed $10.00 on Pass Line" in result

def test_place_bet_invalid_amount(data_manager):
    channel_id = "test_channel"
    user_id = "test_user"
    user_name = "Test User"
    result = place_bet(channel_id, user_id, user_name, 'pass_line', '-10.00', data_manager)
    assert "Bet amount must be positive" in result

def test_place_bet_invalid_type(data_manager):
    channel_id = "test_channel"
    user_id = "test_user"
    user_name = "Test User"
    result = place_bet(channel_id, user_id, user_name, 'invalid_bet', '10.00', data_manager)
    assert "Invalid bet type" in result
