import random
from decimal import Decimal, ROUND_HALF_UP

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
    },
    # Hard Ways (Pays X to 1, so payout is X)
    'hard_4': Decimal('7'),  # 2+2
    'hard_6': Decimal('9'),  # 3+3
    'hard_8': Decimal('9'),  # 4+4
    'hard_10': Decimal('7'), # 5+5
    # Horn / Proposition Bets (One Roll Bets, Pays X to 1)
    'any_craps': Decimal('7'), # 2, 3, or 12
    'any_seven': Decimal('4'), # 7
    'two': Decimal('30'),      # Craps 2 (1+1)
    'three': Decimal('15'),    # Craps 3 (1+2 or 2+1)
    'eleven': Decimal('15'),   # Yo-leven (5+6 or 6+5)
    'twelve': Decimal('30'),   # Craps 12 (6+6)
    # Add odds, come, dont_come payouts later
}

def roll_dice() -> tuple[int, int, int]:
    """Rolls two dice and returns their individual values and sum."""
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    return die1, die2, die1 + die2

def _calculate_winnings(bet_type: str, bet_amount: Decimal, die1: int, die2: int, point: int | None = None) -> Decimal:
    """Calculates winnings for a specific bet type based on roll and point.
       Requires individual dice values for Hard Ways.
       Returns winnings ONLY (not original bet).
    """
    winnings = Decimal('0')
    roll_sum = die1 + die2

    # --- Existing Bet Types ---
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
        # Standard rule: Place bets are OFF on come-out unless specified. We'll assume OFF here.
        if point is not None and roll_sum == place_num:
             winnings = bet_amount * PAYOUTS['place'][place_num]

    # --- New Bet Types ---
    elif bet_type.startswith('hard_'):
        hard_num = int(bet_type.split('_')[1])
        # Check if the hard way was rolled
        if roll_sum == hard_num and die1 == die2:
            winnings = bet_amount * PAYOUTS[bet_type]
        # Hard ways lose on 7 or easy way (handled in main loop)
    elif bet_type == 'any_craps':
        if roll_sum in (2, 3, 12):
            winnings = bet_amount * PAYOUTS['any_craps']
    elif bet_type == 'any_seven':
        if roll_sum == 7:
            winnings = bet_amount * PAYOUTS['any_seven']
    elif bet_type == 'two':
        if roll_sum == 2: # (1+1)
             winnings = bet_amount * PAYOUTS['two']
    elif bet_type == 'three':
        if roll_sum == 3: # (1+2 or 2+1)
             winnings = bet_amount * PAYOUTS['three']
    elif bet_type == 'eleven':
        if roll_sum == 11: # (5+6 or 6+5)
             winnings = bet_amount * PAYOUTS['eleven']
    elif bet_type == 'twelve':
        if roll_sum == 12: # (6+6)
             winnings = bet_amount * PAYOUTS['twelve']

    # Round winnings to 2 decimal places (cents)
    return winnings.quantize(Decimal("0.01"), ROUND_HALF_UP)

# TODO: Need functions to handle placing/removing bets, e.g.,
# def place_bet(channel_id, user_id, bet_type, amount, data_manager): ...
# def remove_bet(channel_id, user_id, bet_type, data_manager): ...

# This function now represents the action of rolling the dice for a specific channel
# It needs access to a data manager to get/set channel and player states.
def play_craps_round(channel_id: str, data_manager) -> str:
    """
    Plays one round (a single dice roll) of Craps for a given channel.
    Resolves bets for all players in the channel based on the roll.
    Updates channel game state and player balances/bets via the data_manager.

    Args:
        channel_id: The identifier for the channel/group game.
        data_manager: An object responsible for loading/saving game data.
                      Expected methods:
                      - get_channel_data(channel_id) -> dict (with 'craps_state', 'craps_point')
                      - save_channel_data(channel_id, data)
                      - get_players_with_bets(channel_id) -> dict {user_id: player_data}
                          (player_data contains 'balance', 'craps_bets', 'display_name')
                      - save_player_data(channel_id, user_id, data)
                      - get_all_players_data(channel_id) -> dict {user_id: player_data} # Hypothetical

    Returns:
        A string summarizing the roll results and game state changes.
    """
    # --- Get Channel State ---
    # Assume data_manager handles default state creation if channel_id is new
    channel_data = data_manager.get_channel_data(channel_id)

    game_state = channel_data.get('craps_state', COME_OUT_PHASE)
    point = channel_data.get('craps_point', None)

    # --- Get Player Data ---
    # Get ALL players for the channel first to check if any exist
    all_players_in_channel = data_manager.get_all_players_data(channel_id)
    # Removed the early return for no players, as we might need to roll even without players?
    # Let's keep the check for active bets as the primary gatekeeper for now.

    # Now get players specifically with active bets
    players_with_active_bets = data_manager.get_players_with_bets(channel_id)

    # *** Check for active bets BEFORE rolling ***
    # If no players have active bets, return immediately.
    # This prevents unnecessary rolls and state changes when no one is playing.
    if not players_with_active_bets:
         # Use a more specific message matching the test expectation
         return "No bets placed in the channel. Use /bet to place bets."
         # Original message: "No active bets placed in the channel. Use bet commands first (e.g., /bet pass_line 10)."

    # Use the filtered list for processing bets
    players_data = players_with_active_bets

    # --- Roll the Dice ---
    die1, die2, roll_sum = roll_dice()
    roll_desc = f"🎲 Rolled {die1} + {die2} = {roll_sum}."
    if die1 == die2 and roll_sum in [4, 6, 8, 10]:
        roll_desc += f" (Hard {roll_sum})"
    elif roll_sum in [4, 6, 8, 10]:
        roll_desc += f" (Easy {roll_sum})"

    results_summary = [roll_desc]
    if point:
        results_summary.append(f"Point is {point}.")

    # --- Resolve Bets for Each Player ---
    player_updates = [] # Store updates {user_id, data} to save later
    all_player_results = [] # Store text results for each player

    # Use items() to iterate through player IDs and their data
    for user_id, player_data in players_data.items():
        bets = player_data.get('craps_bets', {})
        if not bets: continue # Skip players with no active bets for this roll

        # --- Get display name ---
        # Use 'display_name' if stored, otherwise fallback to user_id
        user_mention = player_data.get('display_name', f'Player {user_id}')

        balance = Decimal(player_data.get('balance', '0'))
        player_roll_results = [] # Text results for this specific player
        bets_to_keep = {} # Bets this player keeps for the next roll
        original_balance = balance # Track changes for update efficiency

        current_bets = dict(bets) # Iterate over a copy
        for bet_type, bet_amount_dec in current_bets.items():
            # Ensure bet_amount is Decimal, handling potential string storage
            try:
                bet_amount = Decimal(bet_amount)
            except Exception:
                # Log error or handle invalid bet amount data? Skip for now.
                # Use user_mention here too
                player_roll_results.append(f"Error processing bet '{bet_type}' for {user_mention}. Invalid amount: {bet_amount_dec}")
                continue # Skip this invalid bet

            win_amount = Decimal('0')
            lost_bet = False
            pushed_bet = False
            bet_continues = False # Flag if the bet stays active for the next roll
            horn_handled = False # Flag to bypass generic win/loss logic for Horn

            # --- Horn Bet Logic ---
            if bet_type == 'horn':
                horn_handled = True # Mark horn bet to skip generic processing below
                bet_continues = False # Horn is always one-roll
                # Check for divisibility by 4, though place_bet should enforce it
                if bet_amount % 4 != 0:
                     player_roll_results.append(f"Error: Horn bet (${bet_amount}) for {user_mention} is not divisible by 4. Bet ignored.")
                     continue # Skip processing this invalid bet state

                portion_bet = (bet_amount / 4).quantize(Decimal("0.01"), ROUND_HALF_UP)
                winning_number = None
                payout_multiplier = Decimal('0')

                if roll_sum == 2:
                    winning_number = 2
                    payout_multiplier = PAYOUTS['two']
                elif roll_sum == 3:
                    winning_number = 3
                    payout_multiplier = PAYOUTS['three']
                elif roll_sum == 11:
                    winning_number = 11
                    payout_multiplier = PAYOUTS['eleven']
                elif roll_sum == 12:
                    winning_number = 12
                    payout_multiplier = PAYOUTS['twelve']

                if winning_number is not None:
                    win_amount_horn = (portion_bet * payout_multiplier).quantize(Decimal("0.01"), ROUND_HALF_UP)
                    balance += portion_bet + win_amount_horn # Return winning portion + winnings
                    lost_portion = bet_amount - portion_bet
                    player_roll_results.append(f"{user_mention}: Horn (${bet_amount}) wins ${win_amount_horn} on {winning_number}! (Lost ${lost_portion:.2f})")
                    # win_amount is kept at 0 here, balance is updated directly
                else:
                    lost_bet = True # Will be handled by generic loss logic below
                    player_roll_results.append(f"{user_mention}: Horn (${bet_amount}) loses.")
                    # Balance already reduced when bet was placed

            # --- Existing Bet Type Logic (excluding Horn) ---
            elif not horn_handled: # Process other bets if not Horn
                # Calculate potential winnings first (requires dice values)
                # This call remains for non-horn bets
                win_amount = _calculate_winnings(bet_type, bet_amount, die1, die2, point)

                # --- Come Out Phase Resolution ---
                if game_state == COME_OUT_PHASE:
                    if bet_type == 'pass_line':
                        if roll_sum in (2, 3, 12): lost_bet = True
                        elif win_amount == 0: bet_continues = True # Point established
                    elif bet_type == 'dont_pass':
                        if roll_sum in (7, 11): lost_bet = True
                        elif roll_sum == 12: # Push
                            pushed_bet = True
                            balance += bet_amount # Return original bet immediately for push
                            bet_continues = True # Don't Pass bet stays up on push
                        elif win_amount == 0: bet_continues = True # Point established
                    elif bet_type == 'field':
                        if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True
                    elif bet_type.startswith('place_'):
                        bet_continues = True
                    elif bet_type.startswith('hard_'):
                        hard_num = int(bet_type.split('_')[1])
                        if roll_sum == 7 or (roll_sum == hard_num and die1 != die2): # Lose on 7 or easy way
                            lost_bet = True
                        elif win_amount == 0: # Neither win nor loss, bet continues
                            bet_continues = True
                    elif bet_type in ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve']:
                        if win_amount == 0: lost_bet = True # One-roll bets lose if they don't win

                # --- Point Phase Resolution ---
                elif game_state == POINT_PHASE:
                    if bet_type == 'pass_line':
                        if roll_sum == 7: lost_bet = True
                        elif win_amount == 0: bet_continues = True # Keep rolling
                    elif bet_type == 'dont_pass':
                        if roll_sum == point: lost_bet = True
                        elif win_amount == 0: bet_continues = True # Keep rolling
                    elif bet_type == 'field':
                        if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True
                    elif bet_type.startswith('place_'):
                        place_num = int(bet_type.split('_')[1])
                        if roll_sum == 7:
                            lost_bet = True # Place bets lose on 7
                        elif win_amount == 0: # Neither win nor 7-out
                            bet_continues = True # Keep bet active
                    elif bet_type.startswith('hard_'):
                        hard_num = int(bet_type.split('_')[1])
                        if roll_sum == 7 or (roll_sum == hard_num and die1 != die2): # Lose on 7 or easy way
                            lost_bet = True
                        elif win_amount == 0: # Neither win nor loss, bet continues
                            bet_continues = True
                    elif bet_type in ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve']:
                        if win_amount == 0: lost_bet = True # One-roll bets lose if they don't win

            # --- Record Bet Outcome (Generic, skipped if horn_handled and won) ---
            bet_name = bet_type.replace('_',' ').title()
            # Horn win message is handled inside its specific block
            if not horn_handled or lost_bet: # Only process generic outcomes if not a winning Horn bet
                if win_amount > 0: # This block now only applies to non-Horn wins
                    player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) wins ${win_amount}!")
                    balance += bet_amount + win_amount # Return original bet + winnings

                    # Decide if winning bet should be removed or kept based on type
                    if bet_type in ['pass_line', 'dont_pass'] and game_state == POINT_PHASE and (roll_sum == point or roll_sum == 7):
                        bet_continues = False # Line bet resolved
                    elif bet_type in ['pass_line', 'dont_pass'] and game_state == COME_OUT_PHASE and roll_sum in (2,3,7,11):
                         bet_continues = False # Line bet resolved
                    elif bet_type == 'field' or bet_type in ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve']:
                        bet_continues = False # One roll bets are always removed after resolving
                    elif bet_type.startswith('place_') and win_amount > 0:
                         bet_continues = True # Keep place bet even after win (standard rule)
                    elif bet_type.startswith('hard_') and win_amount > 0:
                         bet_continues = True # Keep hard way bet after win (standard rule, can be taken down)

                elif lost_bet: # Handles losses for Horn and other bets
                    # Horn loss message is added in its block, others here
                    if not horn_handled: # Avoid duplicate loss message for Horn
                         player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) loses.")
                    bet_continues = False # Remove losing bets
                elif pushed_bet: # Only applies to DP 12 push currently
                     player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) pushes.")
                     # bet_continues was already set to True for DP push on 12

            if bet_continues: # Applies to all bet types if they continue
                 bets_to_keep[bet_type] = bet_amount # Keep the bet for the next roll (store original amount)

        # --- Store Player Updates ---
        new_balance_str = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
        new_bets_dict = {k: str(v) for k, v in bets_to_keep.items() if v > 0} # Store amounts as strings

        if new_balance_str != player_data.get('balance') or new_bets_dict != player_data.get('craps_bets'):
             updated_player_data = player_data.copy()
             updated_player_data['balance'] = new_balance_str
             updated_player_data['craps_bets'] = new_bets_dict
             player_updates.append({'user_id': user_id, 'data': updated_player_data})

        if player_roll_results:
            all_player_results.extend(player_roll_results)

    # --- Update Game State ---
    next_game_state = game_state
    next_point = point
    state_change_message = ""
    clear_place_bets_on_7_out = False
    clear_hardway_bets_on_7_out = False
    # Flag to indicate if the round ended (point hit, 7-out, or craps/natural on come-out)
    round_ended = False

    if game_state == COME_OUT_PHASE:
        if roll_sum in (7, 11):
            state_change_message = "Natural! Pass Line wins. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            round_ended = True # Round ends on natural
        elif roll_sum in (2, 3, 12):
            # ... (craps logic as before) ...
            state_change_message += " New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            round_ended = True # Round ends on craps
        else: # Point established
            next_point = roll_sum
            next_game_state = POINT_PHASE
            # IMPORTANT: Only set the state change message, don't resolve bets yet
            state_change_message = f"Point is now {next_point}. /roll again!"
            # round_ended remains False, bets continue

    elif game_state == POINT_PHASE:
        if roll_sum == point:
            state_change_message = f"Point ({point}) hit! Pass Line wins. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            round_ended = True # Round ends on point hit
        elif roll_sum == 7:
            state_change_message = f"Seven out! Pass Line loses. Don't Pass wins. Place and Hard Way bets lose. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            clear_place_bets_on_7_out = True
            clear_hardway_bets_on_7_out = True
            round_ended = True # Round ends on 7-out
        else:
            # Point not hit, 7 not rolled, continue rolling
            state_change_message = f"Rolled {roll_sum}. Still rolling for point {point}. /roll again!"
            # round_ended remains False

    # --- Resolve Bets for Each Player (Adjusted Logic) ---
    player_updates = [] # Store updates {user_id, data} to save later
    all_player_results = [] # Store text results for each player

    for user_id, player_data in players_data.items():
        # ... (get user_mention, balance, etc. as before) ...
        bets = player_data.get('craps_bets', {})
        if not bets: continue

        user_mention = player_data.get('display_name', f'Player {user_id}')
        balance = Decimal(player_data.get('balance', '0'))
        player_roll_results = []
        bets_to_keep = {} # Bets this player keeps for the next roll
        original_balance = balance

        current_bets = dict(bets)
        for bet_type, bet_amount_dec in current_bets.items():
            # ... (try/except for bet_amount as before) ...
            try:
                bet_amount = Decimal(bet_amount_dec)
            except Exception:
                player_roll_results.append(f"Error processing bet '{bet_type}' for {user_mention}. Invalid amount: {bet_amount_dec}")
                continue

            win_amount = Decimal('0')
            lost_bet = False
            pushed_bet = False
            bet_continues = False
            horn_handled = False # Reset for each bet

            # --- Horn Bet Logic (as before) ---
            if bet_type == 'horn':
                # ... (horn logic as before) ...
                pass # Placeholder

            # --- Other Bet Type Logic (Modified for round_ended) ---
            elif not horn_handled:
                win_amount = _calculate_winnings(bet_type, bet_amount, die1, die2, point)

                # Determine bet outcome based *only* on the current roll and state
                # The decision to keep the bet depends on whether the round ended
                if game_state == COME_OUT_PHASE:
                    if bet_type == 'pass_line':
                        if roll_sum in (2, 3, 12): lost_bet = True
                        elif roll_sum in (7, 11): pass # Win handled below
                        else: bet_continues = True # Point established
                    elif bet_type == 'dont_pass':
                        if roll_sum in (7, 11): lost_bet = True
                        elif roll_sum == 12: pushed_bet = True; bet_continues = True # Push
                        elif roll_sum in (2, 3): pass # Win handled below
                        else: bet_continues = True # Point established
                    # ... (other come-out phase bet logic as before, setting lost_bet or bet_continues) ...
                    elif bet_type == 'field':
                        if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True
                        # Field bets are one-roll, so bet_continues is False unless won (handled below)
                    elif bet_type.startswith('place_'):
                        bet_continues = True # Place bets are off but stay on table
                    elif bet_type.startswith('hard_'):
                        hard_num = int(bet_type.split('_')[1])
                        if roll_sum == 7 or (roll_sum == hard_num and die1 != die2):
                            lost_bet = True
                        elif win_amount > 0: pass # Win handled below
                        else: bet_continues = True # Neither win nor loss
                    elif bet_type in ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve']:
                        if win_amount == 0: lost_bet = True
                        # One-roll bets, bet_continues is False

                elif game_state == POINT_PHASE:
                    if bet_type == 'pass_line':
                        if roll_sum == 7: lost_bet = True
                        elif roll_sum == point: pass # Win handled below
                        else: bet_continues = True # Keep rolling
                    elif bet_type == 'dont_pass':
                        if roll_sum == point: lost_bet = True
                        elif roll_sum == 7: pass # Win handled below
                        else: bet_continues = True # Keep rolling
                    # ... (other point phase bet logic as before, setting lost_bet or bet_continues) ...
                    elif bet_type == 'field':
                        if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True
                    elif bet_type.startswith('place_'):
                        place_num = int(bet_type.split('_')[1])
                        if roll_sum == 7: lost_bet = True
                        elif roll_sum == place_num: pass # Win handled below
                        else: bet_continues = True
                    elif bet_type.startswith('hard_'):
                        hard_num = int(bet_type.split('_')[1])
                        if roll_sum == 7 or (roll_sum == hard_num and die1 != die2):
                            lost_bet = True
                        elif win_amount > 0: pass # Win handled below
                        else: bet_continues = True
                    elif bet_type in ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve']:
                        if win_amount == 0: lost_bet = True

            # --- Record Bet Outcome (Generic, adjusted for round_ended) ---
            bet_name = bet_type.replace('_',' ').title()
            if not horn_handled or lost_bet:
                if win_amount > 0:
                    player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) wins ${win_amount}!")
                    balance += bet_amount + win_amount

                    # Decide if bet continues based on type AND if the round ended
                    if round_ended:
                        bet_continues = False # All bets resolve if round ended
                    else:
                        # If round continues, decide based on bet type
                        if bet_type in ['pass_line', 'dont_pass']:
                            bet_continues = True # Line bets always continue until resolved
                        elif bet_type.startswith('place_') or bet_type.startswith('hard_'):
                            bet_continues = True # Place/Hard ways stay up unless 7-out
                        else:
                            bet_continues = False # Field/Prop bets are one-roll

                elif lost_bet:
                    if not horn_handled:
                         player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) loses.")
                    bet_continues = False # Losing bets are always removed
                elif pushed_bet:
                     player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) pushes.")
                     # bet_continues was already set for DP push

            # If the round ended, override bet_continues to False for Place/Hardway bets that didn't lose on 7-out
            if round_ended and not lost_bet and not pushed_bet:
                # Exception: Line bets might have won but round ends, they are removed
                # Place/Hardway bets that didn't lose on 7-out are technically removed too
                # Let's simplify: if round ended, no bets continue unless explicitly pushed (DP 12)
                if not pushed_bet:
                    bet_continues = False

            # Special handling for 7-out clearing specific bets
            if clear_place_bets_on_7_out and bet_type.startswith('place_'):
                bet_continues = False
            if clear_hardway_bets_on_7_out and bet_type.startswith('hard_'):
                bet_continues = False

            if bet_continues:
                 bets_to_keep[bet_type] = bet_amount

        # --- Store Player Updates (as before) ---
        # ... (store updates logic as before) ...
        new_balance_str = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
        new_bets_dict = {k: str(v) for k, v in bets_to_keep.items() if v > 0}

        if new_balance_str != player_data.get('balance') or new_bets_dict != player_data.get('craps_bets'):
             updated_player_data = player_data.copy()
             updated_player_data['balance'] = new_balance_str
             updated_player_data['craps_bets'] = new_bets_dict
             player_updates.append({'user_id': user_id, 'data': updated_player_data})

        if player_roll_results:
            all_player_results.extend(player_roll_results)

    # --- Save Updated Data (No changes needed here) ---
    # ... (save player data logic as before) ...
    for update in player_updates:
        # No need to clear bets here anymore, handled by bet_continues logic
        data_manager.save_player_data(channel_id, update['user_id'], update['data'])

    # ... (save channel data logic as before) ...
    if next_game_state != game_state or next_point != point:
        channel_data['craps_state'] = next_game_state
        channel_data['craps_point'] = next_point
        data_manager.save_channel_data(channel_id, channel_data)

    # --- Construct Final Message ---
    if all_player_results:
        results_summary.extend(all_player_results)
    results_summary.append(state_change_message)

    return "\n".join(results_summary)

def place_bet(channel_id: str, user_id: str, user_name: str, bet_type: str, amount_str: str, data_manager) -> str:
    """
    Places a bet for a user in a specific channel.
    Handles balance checks and updates player data via data_manager.
    Assumes data_manager.get_player_data returns player data or initializes it.
    Also updates the user's display name in the stored data.
    """
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            return "Bet amount must be positive."
        amount = amount.quantize(Decimal("0.01"), ROUND_HALF_UP)
        if amount == 0:
             return "Bet amount is too small."

        # Horn bet amount must be divisible by 4
        # Use Decimal for modulo check with currency
        if bet_type == 'horn' and amount % Decimal('4') != 0:
            # Find the nearest lower multiple of 4
            suggested_amount = (amount // Decimal('4')) * Decimal('4')
            if suggested_amount <= 0:
                 # Suggest a minimum valid bet like $4.00 or $0.04 depending on currency scale
                 min_horn_bet = Decimal('4.00') if amount >= 1 else Decimal('0.04')
                 return f"Horn bet amount must be at least ${min_horn_bet:.2f} and divisible by 4."
            else:
                 return f"Horn bet amount must be divisible by 4 (e.g., ${suggested_amount:.2f})."

    except Exception:
        return "Invalid bet amount."

    valid_bet_types = ['pass_line', 'dont_pass', 'field'] + [f'place_{n}' for n in [4,5,6,8,9,10]] + \
                      [f'hard_{n}' for n in [4,6,8,10]] + ['any_craps', 'any_seven', 'two', 'three', 'eleven', 'twelve'] + \
                      ['horn'] # Added horn
    if bet_type not in valid_bet_types:
        # Provide a slightly better formatted list
        valid_types_str = ", ".join(sorted(valid_bet_types)[:-1]) + " or " + sorted(valid_bet_types)[-1]
        return f"Invalid bet type: '{bet_type}'. Valid types: {valid_types_str}"

    player_data = data_manager.get_player_data(channel_id, user_id)
    if player_data is None:
        player_data = {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name}
    else:
        player_data['display_name'] = user_name

    balance = Decimal(player_data.get('balance', '0'))
    bets = player_data.get('craps_bets', {})
    if not isinstance(bets, dict):
        bets = {}

    if amount > balance:
        return f"{user_name}, insufficient balance. You have ${balance:.2f}, need ${amount:.2f}."

    channel_data = data_manager.get_channel_data(channel_id)
    game_state = channel_data.get('craps_state', COME_OUT_PHASE)
    point = channel_data.get('craps_point', None)

    if game_state == POINT_PHASE:
        if bet_type in ['pass_line', 'dont_pass']:
             return f"Cannot place {bet_type.replace('_',' ').title()} bet when point is {point}."

    current_bet_amount = Decimal(bets.get(bet_type, '0'))
    new_bet_amount = current_bet_amount + amount

    balance -= amount
    bets[bet_type] = str(new_bet_amount)

    player_data['balance'] = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
    player_data['craps_bets'] = bets
    data_manager.save_player_data(channel_id, user_id, player_data)

    return f"{user_name} placed ${amount:.2f} on {bet_type.replace('_',' ').title()}. Total on {bet_type}: ${new_bet_amount:.2f}. New balance: ${balance:.2f}"
