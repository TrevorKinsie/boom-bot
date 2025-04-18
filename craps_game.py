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
        # Place bets only win if the point phase is active OR if explicitly working on come-out (not implemented yet)
        # Standard rule: Place bets are OFF on come-out unless specified. We'll assume OFF here.
        if point is not None and roll_sum == place_num:
             winnings = bet_amount * PAYOUTS['place'][place_num]

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
    # Assumes data_manager returns a dict like {user_id: {'balance': '100.00', 'craps_bets': {'pass_line': '10.00'}}}
    # Only get players who actually have bets placed for this channel
    players_data = data_manager.get_players_with_bets(channel_id)

    if not players_data and game_state == COME_OUT_PHASE:
         # Check if ANY bets exist across all players for this channel
         # This check might need refinement depending on data_manager implementation
         # Using a hypothetical method here for clarity
         all_players = data_manager.get_all_players_data(channel_id)
         has_any_bets = any(p_data.get('craps_bets') for p_data in all_players.values())
         if not has_any_bets:
              return "No bets placed in the channel. Use bet commands first (e.g., /bet pass_line 10)."


    # --- Roll the Dice ---
    die1, die2, roll_sum = roll_dice()
    roll_desc = f"🎲 Rolled {die1} + {die2} = {roll_sum}."
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
                bet_amount = Decimal(bet_amount_dec)
            except Exception:
                # Log error or handle invalid bet amount data? Skip for now.
                # Use user_mention here too
                player_roll_results.append(f"Error processing bet '{bet_type}' for {user_mention}. Invalid amount: {bet_amount_dec}")
                continue # Skip this invalid bet

            win_amount = Decimal('0')
            lost_bet = False
            pushed_bet = False
            bet_continues = False # Flag if the bet stays active for the next roll

            # --- Come Out Phase Resolution ---
            if game_state == COME_OUT_PHASE:
                if bet_type == 'pass_line':
                    if roll_sum in (7, 11): win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                    elif roll_sum in (2, 3, 12): lost_bet = True
                    else: bet_continues = True # Keep bet for point phase
                elif bet_type == 'dont_pass':
                    if roll_sum in (2, 3): win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                    elif roll_sum in (7, 11): lost_bet = True
                    elif roll_sum == 12: # Push
                        pushed_bet = True
                        balance += bet_amount # Return original bet immediately for push
                        bet_continues = True # Don't Pass bet stays up on push
                    else: bet_continues = True # Keep bet for point phase
                elif bet_type == 'field':
                    win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                    if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True # Field loses if not a winning number
                    # Field is always a one-roll bet, never continues
                elif bet_type.startswith('place_'):
                    # Place bets are off on the come out roll by default
                    bet_continues = True
                    # player_roll_results.append(f"Place {bet_type.split('_')[1]} (${bet_amount}): Off (Come Out).") # Maybe too verbose for summary

            # --- Point Phase Resolution ---
            elif game_state == POINT_PHASE:
                if bet_type == 'pass_line':
                    if roll_sum == point: win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum, point)
                    elif roll_sum == 7: lost_bet = True
                    else: bet_continues = True # Keep rolling
                elif bet_type == 'dont_pass':
                    if roll_sum == 7: win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum, point)
                    elif roll_sum == point: lost_bet = True
                    else: bet_continues = True # Keep rolling
                elif bet_type == 'field':
                    win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum)
                    if win_amount == 0 and roll_sum not in PAYOUTS['field']: lost_bet = True
                    # Field is always a one-roll bet
                elif bet_type.startswith('place_'):
                    place_num = int(bet_type.split('_')[1])
                    if roll_sum == place_num:
                        win_amount = _calculate_winnings(bet_type, bet_amount, roll_sum, point)
                        # Place bets stay up after winning unless taken down
                        bet_continues = True # Keep the bet active
                    elif roll_sum == 7:
                        lost_bet = True # Place bets lose on 7
                    else:
                        bet_continues = True # Keep bet active

            # --- Record Bet Outcome ---
            bet_name = bet_type.replace('_',' ').title()
            if win_amount > 0:
                player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) wins ${win_amount}!")
                balance += bet_amount + win_amount # Return original bet + winnings
                # Decide if winning bet should be removed or kept
                if bet_type in ['pass_line', 'dont_pass'] and game_state == POINT_PHASE and (roll_sum == point or roll_sum == 7):
                    bet_continues = False # Bet resolved, remove
                elif bet_type in ['pass_line', 'dont_pass'] and game_state == COME_OUT_PHASE and roll_sum in (2,3,7,11):
                    bet_continues = False # Bet resolved, remove
                elif bet_type == 'field':
                    bet_continues = False # One roll bet
                elif bet_type.startswith('place_') and win_amount > 0:
                     bet_continues = True # Keep place bet even after win (standard rule)

            elif lost_bet:
                player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) loses.")
                bet_continues = False # Remove losing bets
                # Balance already reduced when bet was placed, no change here.
            elif pushed_bet:
                 player_roll_results.append(f"{user_mention}: {bet_name} (${bet_amount}) pushes.")
                 # Bet continues was already set for DP push on 12
            # else: bet continues if not won/lost/pushed

            if bet_continues:
                 bets_to_keep[bet_type] = bet_amount # Keep the bet for the next roll (store original amount)


        # --- Store Player Updates ---
        new_balance_str = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
        new_bets_dict = {k: str(v) for k, v in bets_to_keep.items() if v > 0} # Store amounts as strings

        # Check if anything actually changed for this player
        if new_balance_str != player_data.get('balance') or new_bets_dict != player_data.get('craps_bets'):
             # Merge with existing player data in case other fields exist (like username)
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

    if game_state == COME_OUT_PHASE:
        if roll_sum in (7, 11):
            state_change_message = "Natural! Pass Line wins. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
        elif roll_sum in (2, 3, 12):
            state_change_message = "Craps! Pass Line loses."
            # Check if anyone had a Don't Pass bet that pushed
            # Check original bets before they were potentially removed in bets_to_keep
            dp_push = any(
                'dont_pass' in p_data.get('craps_bets', {})
                for _, p_data in players_data.items()
            )
            if roll_sum == 12 and dp_push:
                 state_change_message += " Don't Pass pushes on 12."
            elif roll_sum in (2,3):
                 # Check if anyone won on Don't Pass
                 dp_win = any(
                     'dont_pass' in p_data.get('craps_bets', {})
                     for _, p_data in players_data.items()
                 )
                 if dp_win: state_change_message += " Don't Pass wins (on 2, 3)."

            state_change_message += " New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
        else: # Point established
            next_point = roll_sum
            next_game_state = POINT_PHASE
            state_change_message = f"Point is now {next_point}. /roll again!"

    elif game_state == POINT_PHASE:
        if roll_sum == point:
            state_change_message = f"Point ({point}) hit! Pass Line wins. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            # Place bets usually stay working unless player takes them down
        elif roll_sum == 7:
            state_change_message = f"Seven out! Pass Line loses. Don't Pass wins. Place bets lose. New come out roll."
            next_game_state = COME_OUT_PHASE
            next_point = None
            clear_place_bets_on_7_out = True # Mark place bets for removal after player updates
        else:
            state_change_message = f"Rolled {roll_sum}. Still rolling for point {point}. /roll again!"
            # State and point remain the same

    # --- Save Updated Data ---
    # Save player data first
    for update in player_updates:
        # If clearing place bets on 7-out, modify the bets here before saving
        if clear_place_bets_on_7_out:
             update['data']['craps_bets'] = {
                 k: v for k, v in update['data']['craps_bets'].items() if not k.startswith('place_')
             }
        data_manager.save_player_data(channel_id, update['user_id'], update['data'])

    # Save channel data if changed
    if next_game_state != game_state or next_point != point:
        channel_data['craps_state'] = next_game_state
        channel_data['craps_point'] = next_point
        data_manager.save_channel_data(channel_id, channel_data)

    # --- Final Output ---
    if all_player_results:
        results_summary.extend(all_player_results)
    results_summary.append(state_change_message)

    # Optionally add current balance for players involved? Or maybe a separate /balance command is better.
    # Example: Add balances of players who were updated
    # balance_summary = [f"{upd['user_id']} Balance: ${upd['data']['balance']}" for upd in player_updates]
    # if balance_summary: results_summary.extend(balance_summary)

    return "\n".join(results_summary)

# Example of how a bet placement function might look (lives here or in handlers/data_manager)
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
        # Round bet amount to 2 decimal places
        amount = amount.quantize(Decimal("0.01"), ROUND_HALF_UP)
        if amount == 0: # Handle case where input rounds down to zero
             return "Bet amount is too small."
    except Exception:
        return "Invalid bet amount."

    # Validate bet_type (basic example)
    valid_bet_types = ['pass_line', 'dont_pass', 'field'] + [f'place_{n}' for n in [4,5,6,8,9,10]]
    if bet_type not in valid_bet_types:
        return f"Invalid bet type: {bet_type}. Valid types: {', '.join(valid_bet_types)}"

    # Assume get_player_data initializes if needed, or returns None/empty dict
    player_data = data_manager.get_player_data(channel_id, user_id)
    # Ensure player_data is a dict, initialize if first interaction
    if player_data is None:
        # Initialize with display name if it's the first time
        player_data = {'balance': '100.00', 'craps_bets': {}, 'display_name': user_name}
    else:
        # Update display name in case it changed
        player_data['display_name'] = user_name


    balance = Decimal(player_data.get('balance', '0'))
    # Ensure bets is a dict, handle potential None or non-dict values
    bets = player_data.get('craps_bets', {})
    if not isinstance(bets, dict):
        bets = {} # Reset if data is corrupted

    # Check sufficient balance
    if amount > balance:
        # Use the provided user_name here for consistency
        return f"{user_name}, insufficient balance. You have ${balance:.2f}, need ${amount:.2f}."

    # Check game state restrictions (e.g., cannot bet Pass Line during Point Phase)
    channel_data = data_manager.get_channel_data(channel_id)
    game_state = channel_data.get('craps_state', COME_OUT_PHASE)
    point = channel_data.get('craps_point', None)

    if game_state == POINT_PHASE:
        if bet_type in ['pass_line', 'dont_pass']:
             return f"Cannot place {bet_type.replace('_',' ').title()} bet when point is {point}."
    # Add more restrictions as needed (e.g., max odds bets, cannot place Place 4 if point is 4 etc.)

    # Add or update bet amount (ensure Decimal)
    current_bet_amount = Decimal(bets.get(bet_type, '0'))
    new_bet_amount = current_bet_amount + amount # Allow adding to existing bets

    # Update balance and bets
    balance -= amount # Deduct bet amount
    bets[bet_type] = str(new_bet_amount) # Store as string

    player_data['balance'] = str(balance.quantize(Decimal("0.01"), ROUND_HALF_UP))
    player_data['craps_bets'] = bets
    # player_data['display_name'] was already updated above
    data_manager.save_player_data(channel_id, user_id, player_data)

    # Use the provided user_name for the confirmation message
    return f"{user_name} placed ${amount:.2f} on {bet_type.replace('_',' ').title()}. Total on {bet_type}: ${new_bet_amount:.2f}. New balance: ${balance:.2f}"
