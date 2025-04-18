import random
from decimal import Decimal, ROUND_HALF_UP  # Use Decimal for currency

# Game states
COME_OUT_PHASE = 1
POINT_PHASE = 2

# Payout Odds (using Decimal for precision)
PAYOUTS = {
    'pass_line': Decimal('1'),
    'dont_pass': Decimal('1'),
    'field': {  # Payout multiplier based on roll
        2: Decimal('2'),
        3: Decimal('1'),
        4: Decimal('1'),
        9: Decimal('1'),
        10: Decimal('1'),
        11: Decimal('1'),
        12: Decimal('3'),
    },
    'place': {  # Payout multiplier based on number
        4: Decimal('9') / Decimal('5'),
        5: Decimal('7') / Decimal('5'),
        6: Decimal('7') / Decimal('6'),
        8: Decimal('7') / Decimal('6'),
        9: Decimal('7') / Decimal('5'),
        10: Decimal('9') / Decimal('5'),
    }
    # Add odds, come, prop, hardway payouts later
}

def roll_dice() -> tuple[int, int, int]:
    """Rolls two dice and returns their individual values and sum."""
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    return die1, die2, die1 + die2

def _calculate_winnings(bet_type: str, bet_amount: Decimal, roll_sum: int, point: int | None = None) -> Decimal:
    """Calculates winnings for a specific bet type based on roll and point. Returns winnings ONLY (not original bet)."""
    winnings = Decimal('0')
    if bet_type == 'pass_line':
        if point is None:  # Come out roll
            if roll_sum in (7, 11): winnings = bet_amount * PAYOUTS['pass_line']
        else:  # Point phase
            if roll_sum == point: winnings = bet_amount * PAYOUTS['pass_line']
    elif bet_type == 'dont_pass':
        if point is None:  # Come out roll
            if roll_sum in (2, 3): winnings = bet_amount * PAYOUTS['dont_pass']
            # 12 is a push, 7/11 lose (handled by loss logic)
        else:  # Point phase
            if roll_sum == 7: winnings = bet_amount * PAYOUTS['dont_pass']
    elif bet_type == 'field':
        if roll_sum in PAYOUTS['field']:
            winnings = bet_amount * PAYOUTS['field'][roll_sum]
    elif bet_type.startswith('place_'):
        place_num = int(bet_type.split('_')[1])
        if roll_sum == place_num:
            winnings = bet_amount * PAYOUTS['place'][place_num]
            
    # Round winnings to 2 decimal places (cents)
    return winnings.quantize(Decimal("0.01"), ROUND_HALF_UP)

def play_craps(user_data: dict) -> str:
    """Plays a round of Craps, resolving various bets."""
    game_state = user_data.get('craps_state', COME_OUT_PHASE)
    point = user_data.get('craps_point', None)
    bets = user_data.get('craps_bets', {})
    balance = Decimal(user_data.get('balance', '0'))  # Use Decimal

    if not bets and game_state == COME_OUT_PHASE:
         return "Place your bets first! Use commands like /passline, /dontpass, /field."

    die1, die2, roll_sum = roll_dice()
    roll_desc = f"Rolled {die1} + {die2} = {roll_sum}."
    results_summary = [roll_desc]
    total_winnings = Decimal('0')
    bets_to_remove = []
    bets_to_keep = {}  # Bets that survive this roll

    # --- Resolve Bets Based on Roll ---
    current_bets = dict(bets)  # Iterate over a copy
    for bet_type, bet_amount_dec in current_bets.items():
        bet_amount = Decimal(bet_amount_dec)  # Ensure Decimal
        win_amount = Decimal('0')
        lost_bet = False

        # --- Come Out Phase Resolution ---
        if game_state == COME_OUT_PHASE:
            if bet_type == 'pass_line':
                if roll_sum in (7, 11): win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                elif roll_sum in (2, 3, 12): lost_bet = True
                else: bets_to_keep[bet_type] = bet_amount  # Keep bet for point phase
            elif bet_type == 'dont_pass':
                if roll_sum in (2, 3): win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                elif roll_sum in (7, 11): lost_bet = True
                elif roll_sum == 12:  # Push
                    results_summary.append(f"Don't Pass (${bet_amount}): Push on 12.")
                    bets_to_keep[bet_type] = bet_amount  # Keep bet
                    balance += bet_amount  # Return original bet immediately for push
                else: bets_to_keep[bet_type] = bet_amount  # Keep bet for point phase
            elif bet_type == 'field':
                win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                if win_amount == 0: lost_bet = True  # Field loses if no win
                # Field is always a one-roll bet, don't add to bets_to_keep
            elif bet_type.startswith('place_'):
                 # Place bets are off on the come out roll by default
                 bets_to_keep[bet_type] = bet_amount
                 results_summary.append(f"Place {bet_type.split('_')[1]} (${bet_amount}): Off (Come Out).")

        # --- Point Phase Resolution ---
        elif game_state == POINT_PHASE:
            if bet_type == 'pass_line':
                if roll_sum == point: win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum, point)
                elif roll_sum == 7: lost_bet = True
                else: bets_to_keep[bet_type] = bet_amount  # Keep rolling
            elif bet_type == 'dont_pass':
                if roll_sum == 7: win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum, point)
                elif roll_sum == point: lost_bet = True
                else: bets_to_keep[bet_type] = bet_amount  # Keep rolling
            elif bet_type == 'field':
                win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                if win_amount == 0: lost_bet = True
                # Field is always a one-roll bet
            elif bet_type.startswith('place_'):
                place_num = int(bet_type.split('_')[1])
                if roll_sum == place_num:
                    win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                    # Place bets stay up after winning unless taken down
                    bets_to_keep[bet_type] = bet_amount
                elif roll_sum == 7:
                    lost_bet = True  # Place bets lose on 7
                else:
                    bets_to_keep[bet_type] = bet_amount  # Keep bet active

        # --- Update Balance and Summary ---
        if win_amount > 0:
            results_summary.append(f"{bet_type.replace('_',' ').title()} (${bet_amount}): Wins ${win_amount}!")
            balance += bet_amount + win_amount  # Return original bet + winnings
            total_winnings += win_amount
            # Decide if winning bet should be removed (e.g., Pass Line on win)
            if bet_type in ['pass_line', 'dont_pass'] and game_state == POINT_PHASE and (roll_sum == point or roll_sum == 7):
                 pass  # Bet is resolved, don't keep
            elif bet_type in ['pass_line', 'dont_pass'] and game_state == COME_OUT_PHASE and roll_sum in (2,3,7,11):
                 pass  # Bet is resolved, don't keep
            elif bet_type == 'field':
                 pass  # One roll bet
            elif bet_type.startswith('place_') and win_amount > 0:
                 pass  # Keep place bet even after win (standard casino rule)
            else:
                 if bet_type not in bets_to_keep:  # If not already marked to keep
                      bets_to_remove.append(bet_type)  # Mark for removal if won and not kept above

        elif lost_bet:
            results_summary.append(f"{bet_type.replace('_',' ').title()} (${bet_amount}): Loses.")
            # Balance already reduced when bet was placed
            bets_to_remove.append(bet_type)  # Remove losing bets
        # else: bet continues (already added to bets_to_keep) or pushed (handled above)

    # --- Update Game State ---
    final_message = ""
    user_data['craps_bets'] = bets_to_keep  # Update active bets

    if game_state == COME_OUT_PHASE:
        if roll_sum in (7, 11):
            final_message = "Natural! Pass Line wins. New come out roll."
            user_data['craps_state'] = COME_OUT_PHASE
            user_data.pop('craps_point', None)
        elif roll_sum in (2, 3, 12):
            final_message = "Craps! Pass Line loses."
            if 12 in roll_sum and 'dont_pass' in bets_to_keep:  # Handle DP push message
                 final_message += " (Don't Pass pushes on 12)."
            else:
                 final_message += " Don't Pass wins (on 2, 3)."
            final_message += " New come out roll."
            user_data['craps_state'] = COME_OUT_PHASE
            user_data.pop('craps_point', None)
        else:  # Point established
            point = roll_sum
            user_data['craps_state'] = POINT_PHASE
            user_data['craps_point'] = point
            final_message = f"Point is {point}. Roll again!"

    elif game_state == POINT_PHASE:
        if roll_sum == point:
            final_message = f"Point ({point}) hit! Pass Line wins. New come out roll."
            user_data['craps_state'] = COME_OUT_PHASE
            user_data.pop('craps_point', None)
            # Place bets usually stay working unless player takes them down
        elif roll_sum == 7:
            final_message = f"Seven out! Pass Line loses. Don't Pass wins. Place bets lose. New come out roll."
            user_data['craps_state'] = COME_OUT_PHASE
            user_data.pop('craps_point', None)
            # Remove place bets on 7-out (already handled by lost_bet logic)
            user_data['craps_bets'] = {k:v for k,v in user_data['craps_bets'].items() if not k.startswith('place_')}  # Clear place bets specifically
        else:
            final_message = f"Rolled {roll_sum}. Still rolling for point {point}."
            # State and point remain the same

    # --- Final Output ---
    user_data['balance'] = str(balance)  # Store balance as string
    results_summary.append(final_message)
    results_summary.append(f"Balance: ${balance:.2f}")

    # Clean up bets dictionary (remove zero amounts if any crept in)
    user_data['craps_bets'] = {k: v for k, v in user_data['craps_bets'].items() if Decimal(v) > 0}

    return "\n".join(results_summary)
