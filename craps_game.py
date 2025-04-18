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
    """Plays a round of Craps based on the current user state."""
    game_state = user_data.get('craps_state', COME_OUT_PHASE)
    point = user_data.get('craps_point', None)

    die1, die2, roll_sum = roll_dice()
    roll_desc = f"Rolled {die1} + {die2} = {roll_sum}."

    if game_state == COME_OUT_PHASE:
        if roll_sum in (7, 11):
            result = f"{roll_desc} Natural! You win! 🎉 Play again? /craps"
            user_data.pop('craps_state', None) # Reset state
            user_data.pop('craps_point', None)
        elif roll_sum in (2, 3, 12):
            result = f"{roll_desc} Craps! You lose. 😢 Play again? /craps"
            user_data.pop('craps_state', None) # Reset state
            user_data.pop('craps_point', None)
        else:
            point = roll_sum
            user_data['craps_state'] = POINT_PHASE
            user_data['craps_point'] = point
            result = f"{roll_desc} Point is set to {point}. Roll again! /craps"
    
    elif game_state == POINT_PHASE:
        if roll_sum == point:
            result = f"{roll_desc} You hit the point ({point})! You win! 🎉 Play again? /craps"
            user_data.pop('craps_state', None) # Reset state
            user_data.pop('craps_point', None)
        elif roll_sum == 7:
            result = f"{roll_desc} Seven out! You lose. 😢 Point was {point}. Play again? /craps"
            user_data.pop('craps_state', None) # Reset state
            user_data.pop('craps_point', None)
        else:
            result = f"{roll_desc} Still rolling for point {point}. Roll again! /craps"
            # State and point remain the same

    return result
