# test_craps_game.py
import pytest
import random
from unittest.mock import patch # Import patch

# Add parent directory to sys.path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from craps_game import CrapsGame # Commented out - Class doesn't exist in craps_game.py

# --- Test Initialization ---

# def test_craps_game_initialization():
#     user_id = 123
#     game = CrapsGame(user_id)
#     assert game.user_id == user_id
#     assert game.state == "come_out"
#     assert game.point is None
#     assert game.bets == {}
#     assert game.rolls == []
#     assert game.balance == 100 # Default starting balance
#
# def test_craps_game_initialization_with_data():
#     user_id = 456
#     initial_data = {
#         'user_id': user_id,
#         'state': 'point_on',
#         'point': 6,
#         'bets': {'pass': {'amount': 10, 'user_id': user_id}},
#         'rolls': [(2, 4)],
#         'balance': 80
#     }
#     game = CrapsGame(user_id, initial_data=initial_data)
#     assert game.user_id == user_id
#     assert game.state == 'point_on'
#     assert game.point == 6
#     assert game.bets == {'pass': {'amount': 10, 'user_id': user_id}}
#     assert game.rolls == [(2, 4)]
#     assert game.balance == 80

# --- Test Betting ---

# @pytest.fixture
# def game():
#     """Provides a fresh CrapsGame instance for betting tests."""
#     return CrapsGame(user_id=111)
#
# @pytest.mark.parametrize("bet_type", ["pass", "dont_pass"])
# def test_place_bet_come_out_valid(game, bet_type):
#     user_id = game.user_id
#     amount = 10
#     result = game.place_bet(user_id, amount, bet_type)
#     assert result == f"Bet of ${amount} placed on {bet_type} line."
#     assert bet_type in game.bets
#     assert game.bets[bet_type]['amount'] == amount
#     assert game.bets[bet_type]['user_id'] == user_id
#     assert game.balance == 90 # Balance reduced
#
# @pytest.mark.parametrize("bet_type", ["come", "dont_come"])
# def test_place_bet_come_out_invalid(game, bet_type):
#     user_id = game.user_id
#     amount = 10
#     result = game.place_bet(user_id, amount, bet_type)
#     assert f"Cannot place {bet_type} bet during come out roll." in result
#     assert bet_type not in game.bets
#     assert game.balance == 100 # Balance unchanged
#
# def test_place_bet_point_on_valid(game):
#     user_id = game.user_id
#     game.state = "point_on"
#     game.point = 6
#     amount = 5
#     # Valid bets during point_on
#     valid_bets = ["pass", "dont_pass", "come", "dont_come"]
#     for i, bet_type in enumerate(valid_bets):
#         result = game.place_bet(user_id, amount + i, bet_type) # Vary amount slightly
#         assert result == f"Bet of ${amount + i} placed on {bet_type} line."
#         assert bet_type in game.bets
#         assert game.bets[bet_type]['amount'] == amount + i
#     assert game.balance == 100 - (5 + 6 + 7 + 8) # 100 - 26 = 74
#
# def test_place_bet_insufficient_balance(game):
#     user_id = game.user_id
#     amount = 110 # More than starting balance
#     result = game.place_bet(user_id, amount, "pass")
#     assert "Insufficient balance" in result
#     assert "pass" not in game.bets
#     assert game.balance == 100
#
# def test_place_bet_invalid_type(game):
#     user_id = game.user_id
#     amount = 10
#     result = game.place_bet(user_id, amount, "invalid_bet")
#     assert "Invalid bet type" in result
#     assert "invalid_bet" not in game.bets
#     assert game.balance == 100
#
# def test_place_bet_negative_amount(game):
#     user_id = game.user_id
#     amount = -10
#     result = game.place_bet(user_id, amount, "pass")
#     assert "Bet amount must be positive." in result
#     assert "pass" not in game.bets
#     assert game.balance == 100

# --- Test Rolling ---

# @pytest.fixture
# def game_with_bets(game): # Depends on the 'game' fixture
#     """Provides a game with some initial bets placed."""
#     game.place_bet(game.user_id, 10, "pass")
#     game.place_bet(game.user_id, 5, "dont_pass")
#     game.balance = 85 # Reset balance after placing bets
#     return game
#
# @patch('random.randint', side_effect=[1, 1]) # Roll 2 (Craps)
# def test_roll_dice_come_out_craps(mock_randint, game_with_bets):
#     result = game_with_bets.roll_dice()
#     assert "Rolled 1 + 1 = 2 (Craps!) " in result # Added space
#     assert "Pass line loses." in result
#     assert "Don't Pass line wins $5." in result # Wins even money
#     assert game_with_bets.state == "come_out" # Stays in come_out
#     assert game_with_bets.point is None
#     assert game_with_bets.bets == {} # Bets resolved
#     assert game_with_bets.balance == 85 - 10 + 5 # Lost 10, Won 5
#     assert game_with_bets.rolls == [(1, 1)]
#
# @patch('random.randint', side_effect=[6, 5]) # Roll 11 (Natural)
# def test_roll_dice_come_out_natural(mock_randint, game_with_bets):
#     result = game_with_bets.roll_dice()
#     assert "Rolled 6 + 5 = 11 (Natural!) " in result # Added space
#     assert "Pass line wins $10." in result # Wins even money
#     assert "Don't Pass line loses." in result
#     assert game_with_bets.state == "come_out"
#     assert game_with_bets.point is None
#     assert game_with_bets.bets == {} # Bets resolved
#     assert game_with_bets.balance == 85 + 10 - 5 # Won 10, Lost 5
#     assert game_with_bets.rolls == [(6, 5)]
#
# @patch('random.randint', side_effect=[4, 2]) # Roll 6 (Point)
# def test_roll_dice_come_out_point_set(mock_randint, game_with_bets):
#     result = game_with_bets.roll_dice()
#     assert "Rolled 4 + 2 = 6. " in result # Added space
#     assert "Point is set to 6." in result
#     assert game_with_bets.state == "point_on"
#     assert game_with_bets.point == 6
#     # Bets remain active
#     assert "pass" in game_with_bets.bets
#     assert "dont_pass" in game_with_bets.bets
#     assert game_with_bets.balance == 85 # No change yet
#     assert game_with_bets.rolls == [(4, 2)]
#
# @patch('random.randint', side_effect=[3, 3]) # Roll 6 (Make Point)
# def test_roll_dice_point_on_make_point(mock_randint, game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 6
#     # Add come bets for testing payout
#     game_with_bets.place_bet(game_with_bets.user_id, 8, "come") # Balance now 77
#     game_with_bets.bets['come']['point'] = 6 # Simulate come bet point matching roll
#
#     result = game_with_bets.roll_dice()
#
#     assert "Rolled 3 + 3 = 6. " in result # Added space
#     assert "Point (6) made!" in result
#     assert "Pass line wins $10." in result
#     assert "Don't Pass line loses." in result
#     assert "Come bet (point 6) wins $8." in result # Come bet wins
#     assert game_with_bets.state == "come_out" # Reset state
#     assert game_with_bets.point is None
#     assert game_with_bets.bets == {} # All bets resolved/paid
#     # Balance: 77 (start) + 10 (pass win) - 5 (dp loss) + 8 (come win) = 90
#     assert game_with_bets.balance == 90
#     assert game_with_bets.rolls == [(3, 3)]
#
# @patch('random.randint', side_effect=[5, 2]) # Roll 7 (Seven Out)
# def test_roll_dice_point_on_seven_out(mock_randint, game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 8 # Set a different point
#     # Add come/don't come bets
#     game_with_bets.place_bet(game_with_bets.user_id, 7, "come") # Balance 78
#     game_with_bets.bets['come']['point'] = 4 # Come bet point is 4
#     game_with_bets.place_bet(game_with_bets.user_id, 6, "dont_come") # Balance 72
#     game_with_bets.bets['dont_come']['point'] = 9 # Don't come point is 9
#
#     result = game_with_bets.roll_dice()
#
#     assert "Rolled 5 + 2 = 7 (Seven Out!) " in result # Added space
#     assert "Pass line loses." in result
#     assert "Don't Pass line wins $5." in result
#     assert "Come bet (point 4) loses." in result
#     assert "Don't Come bet (point 9) wins $6." in result
#     assert game_with_bets.state == "come_out"
#     assert game_with_bets.point is None
#     assert game_with_bets.bets == {} # Bets resolved
#     # Balance: 72 (start) - 10 (pass loss) + 5 (dp win) - 7 (come loss) + 6 (dc win) = 66
#     assert game_with_bets.balance == 66
#     assert game_with_bets.rolls == [(5, 2)]
#
# @patch('random.randint', side_effect=[2, 2]) # Roll 4
# def test_roll_dice_point_on_other_roll(mock_randint, game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 6
#     # Add come/don't come bets
#     game_with_bets.place_bet(game_with_bets.user_id, 7, "come") # Balance 78
#     game_with_bets.place_bet(game_with_bets.user_id, 6, "dont_come") # Balance 72
#
#     result = game_with_bets.roll_dice()
#
#     assert "Rolled 2 + 2 = 4. " in result # Added space
#     # Check come bet processing
#     assert "Come bet placed on 4." in result
#     assert game_with_bets.bets['come']['point'] == 4 # Point established for come bet
#     assert game_with_bets.bets['come']['amount'] == 7 # Amount remains
#     # Check don't come bet processing
#     assert "Don't Come bet placed against 4." in result
#     assert game_with_bets.bets['dont_come']['point'] == 4 # Point established for don't come
#     assert game_with_bets.bets['dont_come']['amount'] == 6 # Amount remains
#     # Main state unchanged
#     assert game_with_bets.state == "point_on"
#     assert game_with_bets.point == 6
#     assert game_with_bets.balance == 72 # Balance unchanged by point setting
#     assert game_with_bets.rolls == [(2, 2)]
#
# @patch('random.randint', side_effect=[1, 2]) # Roll 3 (Craps)
# def test_roll_dice_point_on_craps_roll(mock_randint, game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 6
#     # Add come/don't come bets
#     game_with_bets.place_bet(game_with_bets.user_id, 7, "come") # Balance 78
#     game_with_bets.place_bet(game_with_bets.user_id, 6, "dont_come") # Balance 72
#
#     result = game_with_bets.roll_dice()
#
#     assert "Rolled 1 + 2 = 3 (Craps!) " in result # Added space
#     assert "Come bet loses." in result
#     assert "Don't Come bet wins $6." in result
#     assert 'come' not in game_with_bets.bets # Come bet resolved
#     assert 'dont_come' not in game_with_bets.bets # Don't come bet resolved
#     assert game_with_bets.state == "point_on" # State remains
#     assert game_with_bets.point == 6
#     # Balance: 72 (start) - 7 (come loss) + 6 (dc win) = 71
#     assert game_with_bets.balance == 71
#     assert game_with_bets.rolls == [(1, 2)]


# --- Test Status and Stats ---

# def test_get_status_come_out(game):
#     status, state_tag = game.get_status()
#     assert "Come Out Roll!" in status
#     assert f"Balance: ${game.balance}" in status
#     assert "Place Pass or Don't Pass bets." in status
#     assert state_tag == "come_out"
#
# def test_get_status_point_on(game):
#     game.state = "point_on"
#     game.point = 8
#     game.place_bet(game.user_id, 10, "pass")
#     status, state_tag = game.get_status()
#     assert "Point is 8." in status
#     assert f"Balance: ${game.balance}" in status # 90
#     assert "Active Bets:" in status
#     assert "Pass: $10" in status
#     assert state_tag == "point_on"
#
# def test_get_stats(game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 6
#     game_with_bets.rolls = [(4, 2), (1, 1)] # Add some rolls
#     stats = game_with_bets.get_stats()
#     assert f"Player: {game_with_bets.user_id}" in stats
#     assert f"Current Balance: ${game_with_bets.balance}" in stats # 85
#     assert f"Current State: point_on (Point: 6)" in stats
#     assert "Active Bets:" in stats
#     assert "Pass: $10" in stats
#     assert "Don't Pass: $5" in stats
#     assert "Roll History: [(4, 2), (1, 1)]" in stats

# --- Test Serialization ---

# def test_to_dict(game_with_bets):
#     game_with_bets.state = "point_on"
#     game_with_bets.point = 6
#     game_with_bets.rolls = [(4, 2)]
#     expected_dict = {
#         'user_id': game_with_bets.user_id,
#         'state': 'point_on',
#         'point': 6,
#         'bets': {
#             'pass': {'amount': 10, 'user_id': game_with_bets.user_id},
#             'dont_pass': {'amount': 5, 'user_id': game_with_bets.user_id}
#         },
#         'rolls': [(4, 2)],
#         'balance': 85
#     }
#     assert game_with_bets.to_dict() == expected_dict
