import logging
import random
import re # Added import
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Tuple, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Initialize logger
logger = logging.getLogger(__name__)

# --- Constants ---

# Roulette wheel numbers - Standard: 0, 00, 1-36
WHEEL_NUMBERS = [0, '00'] + list(range(1, 37))

# Number colors
NUMBER_COLORS = {
    0: 'green', 
    '00': 'green',
}
# Set colors for 1-36 according to standard roulette wheel
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
for i in range(1, 37):
    NUMBER_COLORS[i] = 'red' if i in RED_NUMBERS else 'black'

# Bet types and standard payout odds
BET_TYPES = {
    'straight': {'description': 'Bet on a single number', 'payout': 35},
    'split': {'description': 'Bet on 2 adjacent numbers', 'payout': 17},
    'street': {'description': 'Bet on 3 numbers in a row', 'payout': 11},
    'corner': {'description': 'Bet on 4 adjacent numbers', 'payout': 8},
    'five': {'description': 'Bet on 0, 00, 1, 2, 3', 'payout': 6},
    'line': {'description': 'Bet on 6 numbers (2 rows)', 'payout': 5},
    'column': {'description': 'Bet on a column of numbers', 'payout': 2},
    'dozen': {'description': 'Bet on 12 consecutive numbers', 'payout': 2},
    'red': {'description': 'Bet on all red numbers', 'payout': 1},
    'black': {'description': 'Bet on all black numbers', 'payout': 1},
    'even': {'description': 'Bet on all even numbers', 'payout': 1},
    'odd': {'description': 'Bet on all odd numbers', 'payout': 1},
    'low': {'description': 'Bet on numbers 1-18', 'payout': 1},
    'high': {'description': 'Bet on numbers 19-36', 'payout': 1},
}

# Adjust for standard roulette wheel
BET_VALID_NUMBERS = {
    'red': RED_NUMBERS,
    'black': [i for i in range(1, 37) if i not in RED_NUMBERS],
    'even': [i for i in range(2, 37, 2)],
    'odd': [i for i in range(1, 37, 2)],
    'low': list(range(1, 19)),
    'high': list(range(19, 37)),
    'first_dozen': list(range(1, 13)),
    'second_dozen': list(range(13, 25)),
    'third_dozen': list(range(25, 37)),
}

# --- Callback Data Constants ---
CALLBACK_SPIN = "roulette_spin"
CALLBACK_SHOW = "roulette_show"
CALLBACK_RESET = "roulette_reset"
CALLBACK_HELP = "roulette_help"
CALLBACK_BET_MENU = "roulette_bet_menu"
CALLBACK_BACK_TO_MAIN = "roulette_back_main"
CALLBACK_BET_TYPE_PREFIX = "roulette_bet_type_"
CALLBACK_BET_NUMBER_PREFIX = "roulette_bet_number_"
CALLBACK_BET_AMOUNT_PREFIX = "roulette_place_bet_"

# --- Helper Functions ---

def escape_markdown_v2(text: str) -> str:
    """Escapes characters for Telegram MarkdownV2."""
    # Escape all characters that need escaping in MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def get_bet_help() -> str:
    """Returns help text for roulette bets, formatted for MarkdownV2."""
    help_text = "🎰 *Roulette Betting Guide* 🎰\n\n"
    help_text += escape_markdown_v2("Our wheel: 0, 00, and 1-36.\n")
    help_text += escape_markdown_v2("Standard casino payouts apply.\n\n")

    help_text += "*Available Bet Types:*\n"
    for bet_type, info in BET_TYPES.items():
        # Escape bet type and description, format payout
        escaped_type = escape_markdown_v2(bet_type.replace('_', ' ').title())
        escaped_desc = escape_markdown_v2(info['description'])
        payout = escape_markdown_v2(f"{info['payout']}:1")
        help_text += f" • `{escaped_type}`: {escaped_desc}\\. Pays {payout}\n" # Escape the period

    help_text += escape_markdown_v2("\n*How to bet:* Use the 'Place Bet' button below.")
    return help_text

def place_bet(channel_id: str, user_id: str, user_name: str, bet_type: str, bet_value: Union[str, int], amount_str: str, data_manager) -> str:
    """Places a bet for the user, returns MarkdownV2 formatted message."""
    try:
        # Get player data
        player_data = data_manager.get_player_data(channel_id, user_id)
        
        # Parse amount
        if amount_str.lower() == 'all':
            amount = Decimal(player_data.get('balance', '0'))
        else:
            amount = Decimal(amount_str).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
        # Validate amount
        balance = Decimal(player_data.get('balance', '0'))
        if amount <= 0:
            return escape_markdown_v2("❌ Bet amount must be positive.")
        if amount > balance:
            balance_str = escape_markdown_v2(f"${balance:.2f}")
            amount_str_esc = escape_markdown_v2(f"${amount:.2f}")
            return f"❌ Insufficient balance\\. You have {balance_str}, but tried to bet {amount_str_esc}\\."
            
        # Check if bet type is valid
        if bet_type not in BET_TYPES and bet_type not in ['straight', 'first_dozen', 'second_dozen', 'third_dozen']:
            return escape_markdown_v2(f"❌ Invalid bet type: {bet_type}")
            
        # For straight bets, validate the number
        if bet_type == 'straight':
            if isinstance(bet_value, str) and bet_value == '00':
                bet_num = bet_value
            else:
                try:
                    bet_num = int(bet_value)
                    if bet_num not in range(0, 37):
                        return escape_markdown_v2(f"❌ Invalid number for straight bet: {bet_value}. Must be 0, 00, or 1-36.")
                except (ValueError, TypeError):
                    return escape_markdown_v2(f"❌ Invalid number for straight bet: {bet_value}")
        
        # Create or update roulette_bets dict if needed
        if 'roulette_bets' not in player_data:
            player_data['roulette_bets'] = {}
            
        # Format the bet key based on type and value
        if bet_type == 'straight':
            bet_key = f"{bet_type}_{bet_value}"
        else:
            bet_key = bet_type
            
        # Add the bet
        player_data['roulette_bets'][bet_key] = str(amount)
        
        # Deduct from balance
        player_data['balance'] = str(balance - amount)
        
        # Save player data
        data_manager.save_player_data(channel_id, user_id, player_data)
        
        # Return success message (escaped)
        amount_esc = escape_markdown_v2(f"${amount:.2f}")
        if bet_type == 'straight':
            bet_value_esc = escape_markdown_v2(str(bet_value))
            return f"✅ Bet placed: {amount_esc} on number {bet_value_esc}\\."
        else:
            bet_type_esc = escape_markdown_v2(bet_type.replace('_', ' '))
            return f"✅ Bet placed: {amount_esc} on {bet_type_esc}\\."
            
    except InvalidOperation:
        return escape_markdown_v2(f"❌ Invalid bet amount: {amount_str}")
    except Exception as e:
        logger.error(f"Error placing roulette bet: {e}")
        return escape_markdown_v2("❌ An error occurred placing your bet.")

def play_roulette_round(channel_id: str, data_manager) -> str:
    """Spins the roulette wheel and processes all bets, returns MarkdownV2 formatted message."""
    # Get the channel data with all players
    channel_data = data_manager.get_channel_data(channel_id)
    players_data = channel_data.get('players', {})
    
    # Spin the wheel (get a random number)
    result = random.choice(WHEEL_NUMBERS)
    
    # Determine result characteristics
    result_icon = "❓" # Default icon
    if result == 0 or result == '00':
        result_color = 'green'
        result_is_even = False
        result_icon = "🟩"
    else:
        result_color = NUMBER_COLORS[result]
        result_is_even = (result % 2 == 0)
        result_icon = "🟥" if result_color == 'red' else "⬛️"
        
    # Initialize results message (escaped)
    if result == '00':
        message = f"🎰 *Roulette Result: {result_icon} 00 \\(green\\)* 🎰\n\n" # Escape parentheses
    else:
        result_color_esc = escape_markdown_v2(result_color)
        message = f"🎰 *Roulette Result: {result_icon} {result} \\({result_color_esc}\\)* 🎰\n\n" # Escape parentheses
    
    # Process each player's bets
    winners = []
    
    for user_id, player_data in players_data.items():
        if 'roulette_bets' not in player_data or not player_data['roulette_bets']:
            continue
            
        display_name = escape_markdown_v2(player_data.get('display_name', f"User_{user_id}")) # Escape display name
        balance = Decimal(player_data.get('balance', '0'))
        bets = player_data['roulette_bets']
        wins = []
        total_winnings = Decimal('0')
        
        # Process each bet
        for bet_key, amount_str in list(bets.items()):
            try:
                amount = Decimal(amount_str)
                bet_parts = bet_key.split('_', 1)
                bet_type = bet_parts[0]
                
                # Handle different bet types
                won = False
                winnings = Decimal('0') # Initialize winnings here
                
                if bet_type == 'straight':
                    # Single number bet
                    bet_number = bet_parts[1]
                    if bet_number == '00' and result == '00':
                        won = True
                    elif bet_number.isdigit() and int(bet_number) == result:
                        won = True
                        
                    if won:
                        winnings = amount * BET_TYPES['straight']['payout']
                        winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                        bet_number_esc = escape_markdown_v2(str(bet_number))
                        wins.append(f"{winnings_str} on straight {bet_number_esc}")
                        total_winnings += winnings
                
                elif bet_type == 'red' and result != 0 and result != '00' and result_color == 'red':
                    winnings = amount * BET_TYPES['red']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on red")
                    total_winnings += winnings
                    
                elif bet_type == 'black' and result != 0 and result != '00' and result_color == 'black':
                    winnings = amount * BET_TYPES['black']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on black")
                    total_winnings += winnings
                    
                elif bet_type == 'even' and result != 0 and result != '00' and result_is_even:
                    winnings = amount * BET_TYPES['even']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on even")
                    total_winnings += winnings
                    
                elif bet_type == 'odd' and result != 0 and result != '00' and not result_is_even:
                    winnings = amount * BET_TYPES['odd']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on odd")
                    total_winnings += winnings
                    
                elif bet_type == 'low' and result != 0 and result != '00' and 1 <= result <= 18:
                    winnings = amount * BET_TYPES['low']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on low \\(1\\-18\\)") # Escape parentheses and hyphen
                    total_winnings += winnings
                    
                elif bet_type == 'high' and result != 0 and result != '00' and 19 <= result <= 36:
                    winnings = amount * BET_TYPES['high']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on high \\(19\\-36\\)") # Escape parentheses and hyphen
                    total_winnings += winnings
                
                elif bet_type == 'first_dozen' and result != 0 and result != '00' and 1 <= result <= 12:
                    winnings = amount * BET_TYPES['dozen']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on first dozen")
                    total_winnings += winnings
                    
                elif bet_type == 'second_dozen' and result != 0 and result != '00' and 13 <= result <= 24:
                    winnings = amount * BET_TYPES['dozen']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on second dozen")
                    total_winnings += winnings
                    
                elif bet_type == 'third_dozen' and result != 0 and result != '00' and 25 <= result <= 36:
                    winnings = amount * BET_TYPES['dozen']['payout']
                    winnings_str = escape_markdown_v2(f"${winnings:.2f}")
                    wins.append(f"{winnings_str} on third dozen")
                    total_winnings += winnings
                    
            except (ValueError, InvalidOperation) as e:
                logger.error(f"Error processing bet {bet_key} with amount {amount_str}: {e}")
        
        # Update player balance with winnings
        new_balance = balance + total_winnings
        player_data['balance'] = str(new_balance)
        
        # Clear bets
        player_data['roulette_bets'] = {}
        
        # Save updated player data
        data_manager.save_player_data(channel_id, user_id, player_data)
        
        # Add to winners list if they won anything
        if wins:
            # Pass the already escaped display name
            winners.append((display_name, wins, total_winnings))
    
    # Add winners to message (escape total winnings)
    if winners:
        message += "*Winners:*\n"
        for name, wins_list, total in winners:
            total_str = escape_markdown_v2(f"${total:.2f}")
            # Name is already escaped
            message += f"🏆 {name} won *{total_str}*\\! 💰\n" # Escape exclamation mark
            for win in wins_list:
                # Win strings are already escaped
                message += f"   • ✨ {win}\n"
    else:
        message += escape_markdown_v2("🤷 No winners this round. Better luck next time! 🍀\n")
        
    return message

# --- Inline Keyboard Functions ---

def get_roulette_main_keyboard() -> InlineKeyboardMarkup:
    """Creates the main roulette game keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🎰 Spin Wheel", callback_data=CALLBACK_SPIN),
            InlineKeyboardButton("📊 Show Game", callback_data=CALLBACK_SHOW),
        ],
        [
            InlineKeyboardButton("💰 Place Bet", callback_data=CALLBACK_BET_MENU),
            InlineKeyboardButton("❓ Help", callback_data=CALLBACK_HELP),
        ],
        [
            InlineKeyboardButton("🔄 Reset My Game", callback_data=CALLBACK_RESET),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bet_type_keyboard() -> InlineKeyboardMarkup:
    """Creates the keyboard for selecting bet types."""
    keyboard = []
    
    # Add bet type buttons in groups
    keyboard.append([
        InlineKeyboardButton("Single Number", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}straight"),
    ])
    keyboard.append([
        InlineKeyboardButton("Red", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}red"),
        InlineKeyboardButton("Black", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}black"),
    ])
    keyboard.append([
        InlineKeyboardButton("Even", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}even"),
        InlineKeyboardButton("Odd", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}odd"),
    ])
    keyboard.append([
        InlineKeyboardButton("1-18", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}low"),
        InlineKeyboardButton("19-36", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}high"),
    ])
    keyboard.append([
        InlineKeyboardButton("1st Dozen", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}first_dozen"),
        InlineKeyboardButton("2nd Dozen", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}second_dozen"),
        InlineKeyboardButton("3rd Dozen", callback_data=f"{CALLBACK_BET_TYPE_PREFIX}third_dozen"),
    ])
    
    # Add Back button
    keyboard.append([
        InlineKeyboardButton("<< Back", callback_data=CALLBACK_BACK_TO_MAIN),
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_number_selection_keyboard() -> InlineKeyboardMarkup:
    """Creates the keyboard for selecting a number for straight bets."""
    keyboard = []
    
    # Special buttons for 0 and 00
    keyboard.append([
        InlineKeyboardButton("0", callback_data=f"{CALLBACK_BET_NUMBER_PREFIX}0"),
        InlineKeyboardButton("00", callback_data=f"{CALLBACK_BET_NUMBER_PREFIX}00"),
    ])
    
    # Add number buttons in rows of 6 (matching roulette table layout)
    for row_start in range(1, 37, 3):
        row = []
        for i in range(row_start, min(row_start + 3, 37)):
            row.append(InlineKeyboardButton(f"{i}", callback_data=f"{CALLBACK_BET_NUMBER_PREFIX}{i}"))
        keyboard.append(row)
    
    # Add Back button
    keyboard.append([
        InlineKeyboardButton("<< Back to Bet Types", callback_data=CALLBACK_BET_MENU),
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_bet_amount_keyboard(bet_type: str, bet_value: str, balance: Decimal) -> InlineKeyboardMarkup:
    """Creates the keyboard for selecting bet amounts."""
    buttons = []
    amounts = [Decimal('1'), Decimal('5'), Decimal('10'), Decimal('25'), Decimal('50'), Decimal('100')]
    valid_amounts = [a for a in amounts if a <= balance and a > 0]

    row = []
    for amount in valid_amounts:
        amount_str = str(amount.to_integral_value()) if amount == amount.to_integral_value() else str(amount)
        
        # For straight bets, include the number in the callback
        if bet_type == 'straight':
            callback_data = f"{CALLBACK_BET_AMOUNT_PREFIX}{bet_type}_{bet_value}_{amount_str}"
        else:
            callback_data = f"{CALLBACK_BET_AMOUNT_PREFIX}{bet_type}_{amount_str}"
            
        row.append(InlineKeyboardButton(f"${amount:.2f}", callback_data=callback_data))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if balance > 0 and balance not in valid_amounts:
        # All-in option
        if bet_type == 'straight':
            all_in_callback = f"{CALLBACK_BET_AMOUNT_PREFIX}{bet_type}_{bet_value}_all"
        else:
            all_in_callback = f"{CALLBACK_BET_AMOUNT_PREFIX}{bet_type}_all"
            
        buttons.append([InlineKeyboardButton(f"All In (${balance:.2f})", callback_data=all_in_callback)])

    # Back button
    if bet_type == 'straight':
        back_data = f"{CALLBACK_BET_TYPE_PREFIX}straight"  # Back to number selection
    else:
        back_data = CALLBACK_BET_MENU  # Back to bet type selection
        
    buttons.append([InlineKeyboardButton("<< Back", callback_data=back_data)])

    return InlineKeyboardMarkup(buttons)

# --- Status and Help Functions ---

def get_roulette_status(channel_id: str, user_id: str, user_name: str, channel_name: str, data_manager) -> str:
    """Generates status text showing player's balance and active bets, formatted for MarkdownV2."""
    player_data = data_manager.get_player_data(channel_id, user_id)
    escaped_user_name = escape_markdown_v2(user_name)
    
    # Update display name if needed
    if player_data.get('display_name') != user_name:
        player_data['display_name'] = user_name # Store raw name
        data_manager.save_player_data(channel_id, user_id, player_data)
        
    balance = Decimal(player_data.get('balance', '100.00'))
    bets = player_data.get('roulette_bets', {})
    
    # Build status message (escape relevant parts)
    game_title = escape_markdown_v2(channel_name if channel_name else f"Channel {channel_id}")
    status_lines = [f"\\-\\-\\- 🎡 *Roulette Game: {game_title}* 🎡 \\-\\-\\-"] # Escape hyphens
    status_lines.append(f"\n\\-\\-\\- ✨ *Your Status \\({escaped_user_name}\\)* ✨ \\-\\-\\-") # Escape hyphens and parentheses
    balance_str = escape_markdown_v2(f"${balance:.2f}")
    status_lines.append(f"💰 *Balance:* {balance_str}")
    
    if not bets:
        status_lines.append("🤷 *Your Active Bets:* None")
    else:
        status_lines.append("📝 *Your Active Bets:*")
        for bet_key, amount in bets.items():
            try:
                amount_dec = Decimal(amount)
                amount_str_esc = escape_markdown_v2(f"${amount_dec:.2f}")
                # Format bet type nicely and escape
                formatted_bet = bet_key.replace('_', ' ').replace('straight ', 'Straight: ')
                if 'dozen' in formatted_bet:
                    formatted_bet = formatted_bet.replace(' dozen', ' Dozen')
                formatted_bet_esc = escape_markdown_v2(formatted_bet.title())
                status_lines.append(f"  • {formatted_bet_esc}: {amount_str_esc}")
            except InvalidOperation:
                formatted_bet = bet_key.replace('_', ' ').replace('straight ', 'Straight: ')
                formatted_bet_esc = escape_markdown_v2(formatted_bet.title())
                amount_esc = escape_markdown_v2(f"Invalid Amount ({amount})") # Escape parentheses
                status_lines.append(f"  • {formatted_bet_esc}: {amount_esc}")
                
    return "\n".join(status_lines)

def reset_player_roulette(channel_id: str, user_id: str, user_name: str, data_manager) -> str:
    """Resets a player's roulette balance and bets, returns MarkdownV2 formatted message."""
    start_balance = '100.00'
    player_data = data_manager.get_player_data(channel_id, user_id)
    player_data['balance'] = start_balance
    player_data['roulette_bets'] = {}
    player_data['display_name'] = user_name # Store raw name
    data_manager.save_player_data(channel_id, user_id, player_data)
    
    balance_str = escape_markdown_v2(f"${Decimal(start_balance):.2f}")
    return f"✅ Your balance has been reset to *{balance_str}*\\. Your bets are cleared\\. ✨" # Escape periods

def get_roulette_help_text() -> str:
    """Returns detailed help text for roulette game, formatted for MarkdownV2."""
    # Escape all necessary characters for MarkdownV2
    help_text = """
🎰 *Roulette Rules & Betting Guide* 🎰

*The Wheel:*
Standard American roulette wheel with 0 \\(Green\\), 00 \\(Green\\), and numbers 1\\-36 \\(Red/Black\\)\\.

*How to Play:*
1\\. Place your bets using the `Place Bet` button\\.
2\\. Click `Spin Wheel` when you're ready\\.
3\\. Watch the ball land and see if you've won\\!

*Bet Types & Payouts:*
 • *Straight* \\(Single Number\\): Bet on one exact number \\(Pays 35:1\\)
 • *Red/Black*: Bet on the color \\(Pays 1:1\\)
 • *Even/Odd*: Bet on even or odd numbers \\(Pays 1:1\\)
 • *Low/High*: Bet on 1\\-18 \\(Low\\) or 19\\-36 \\(High\\) \\(Pays 1:1\\)
 • *Dozens*: Bet on First \\(1\\-12\\), Second \\(13\\-24\\), or Third \\(25\\-36\\) dozen \\(Pays 2:1\\)

*Important Notes:*
 • 0 and 00 are green\\.
 • 0 and 00 do *not* count for Red/Black, Even/Odd, or Low/High bets\\.

*Reset:*
Use the `Reset My Game` button to clear your bets and start fresh with \\$100\\.00\\.

🍀 Good Luck\\! 🍀
"""
    return help_text