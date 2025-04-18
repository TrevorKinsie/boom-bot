import random
from telegram.ext import ContextTypes

# Game states
COME_OUT_PHASE = 1
POINT_PHASE = 2

def roll_dice() -> tuple[int, int, int]:
    """Rolls two dice and returns their individual values and sum."""
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    return die1, die2, die1 + die2

def play_craps(user_data: dict) -> str:
    """Plays a round of Craps based on the current user state, including betting."""
    game_state = user_data.get('craps_state', COME_OUT_PHASE)
    point = user_data.get('craps_point', None)
    bet = user_data.get('craps_bet', 0) # Get the current bet amount
    balance = user_data.get('balance', 0) # Get user balance

    # Ensure there's a bet placed if starting a new round
    if game_state == COME_OUT_PHASE and bet <= 0:
        return "You need to place a bet first! Use /passline <amount>"
    
    # Check if balance was sufficient when the bet was placed (handled externally)
    # For simplicity here, we assume the bet was validly placed.

    die1, die2, roll_sum = roll_dice()
    roll_desc = f"Rolled {die1} + {die2} = {roll_sum}."

    if game_state == COME_OUT_PHASE:
        if roll_sum in (7, 11):
            winnings = bet * 1 # Pass line pays 1:1
            user_data['balance'] = balance + winnings + bet # Return original bet + winnings
            result = f"{roll_desc} Natural! You win ${winnings}! 🎉 Your balance: ${user_data['balance']}. Play again? /passline <amount>"
            user_data.pop('craps_state', None)
            user_data.pop('craps_point', None)
            user_data.pop('craps_bet', None) # Clear bet after round ends
        elif roll_sum in (2, 3, 12):
            # Bet was already deducted when placed, so just update balance display if needed
            result = f"{roll_desc} Craps! You lose your ${bet} bet. 😢 Your balance: ${balance}. Play again? /passline <amount>"
            user_data.pop('craps_state', None)
            user_data.pop('craps_point', None)
            user_data.pop('craps_bet', None) # Clear bet after round ends
        else:
            point = roll_sum
            user_data['craps_state'] = POINT_PHASE
            user_data['craps_point'] = point
            # Bet stays on the table
            result = f"{roll_desc} Point is set to {point}. Your ${bet} bet rides. Roll again! /roll" # Changed command suggestion

    elif game_state == POINT_PHASE:
        if roll_sum == point:
            winnings = bet * 1 # Pass line pays 1:1
            user_data['balance'] = balance + winnings + bet # Return original bet + winnings
            result = f"{roll_desc} You hit the point ({point})! You win ${winnings}! 🎉 Your balance: ${user_data['balance']}. Play again? /passline <amount>"
            user_data.pop('craps_state', None)
            user_data.pop('craps_point', None)
            user_data.pop('craps_bet', None) # Clear bet after round ends
        elif roll_sum == 7:
            # Bet was already deducted when placed
            result = f"{roll_desc} Seven out! You lose your ${bet} bet. 😢 Point was {point}. Your balance: ${balance}. Play again? /passline <amount>"
            user_data.pop('craps_state', None)
            user_data.pop('craps_point', None)
            user_data.pop('craps_bet', None) # Clear bet after round ends
        else:
            # Bet stays on the table
            result = f"{roll_desc} Still rolling for point {point}. Your ${bet} bet rides. Roll again! /roll" # Changed command suggestion
            # State, point, and bet remain the same
            pass # Added pass to fix indentation error

    return result
