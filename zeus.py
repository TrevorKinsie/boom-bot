import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# 🎰 Symbol list (🧔‍♂️ = Zeus wild card)
symbols = ['⚡', '🦁', '🏺', '🦅', '👑', '🇦', '🇰', '🇯', '🧔‍♂️']

# Player wallets: {user_id: {'coins': int, 'free_spins': int}}
wallets = {}

# Generate a 5x5 grid of random symbols
def spin_grid():
    return [[random.choice(symbols) for _ in range(5)] for _ in range(5)]

# Cleanly format the 5x5 grid
def format_grid(grid):
    return '\n'.join([' | '.join(row) for row in grid])

# Initialize a player if they're new
def initialize_user(user_id):
    if user_id not in wallets:
        wallets[user_id] = {'coins': 100, 'free_spins': 0}

# Count how many line matches a player hit (horizontal, vertical, diagonal)
def count_lines(grid):
    match_count = {}

    def count_line(line):
        line_no_zeus = [s for s in line if s != '🧔‍♂️']
        if not line_no_zeus:
            return None, 0
        target = max(set(line_no_zeus), key=line_no_zeus.count)
        total = sum(1 for s in line if s == target or s == '🧔‍♂️')
        return target, total if total >= 3 else 0

    # Rows
    for row in grid:
        symbol, count = count_line(row)
        if count >= 3:
            match_count[symbol] = match_count.get(symbol, 0) + 1

    # Columns
    for col in range(5):
        column = [grid[row][col] for row in range(5)]
        symbol, count = count_line(column)
        if count >= 3:
            match_count[symbol] = match_count.get(symbol, 0) + 1

    # Diagonals
    diag1 = [grid[i][i] for i in range(5)]
    diag2 = [grid[i][4 - i] for i in range(5)]
    for diag in [diag1, diag2]:
        symbol, count = count_line(diag)
        if count >= 3:
            match_count[symbol] = match_count.get(symbol, 0) + 1

    return match_count

async def zeus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    initialize_user(user_id)
    await update.message.reply_text(
        "⚡ Welcome to Zeus!\n\n"
        "You start with 100 coins.\nEach spin costs 10 coins.\n"
        "Use the button below to spin!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎰 Spin", callback_data="spin")]]
        )
    )

# /wallet command
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    initialize_user(user_id)
    coins = wallets[user_id]['coins']
    free_spins = wallets[user_id]['free_spins']
    await update.message.reply_text(
        f"💰 Coins: {coins}\n🎁 Free Spins: {free_spins}"
    )

# 🎰 Handle spin button presses
async def spin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    initialize_user(user_id)
    wallet = wallets[user_id]

    spin_cost = 10

    # Free spin or coin cost
    if wallet['free_spins'] > 0:
        wallet['free_spins'] -= 1
    elif wallet['coins'] >= spin_cost:
        wallet['coins'] -= spin_cost
    else:
        await query.edit_message_text("😞 Not enough coins! Use /wallet to check your balance.")
        return

    # Spin grid and format
    grid = spin_grid()
    result_text = format_grid(grid)

    # Count matches
    matches = count_lines(grid)

    # Win logic
    if not matches:
        message = "No matches this time. Try again!"
        winnings = 0
        bonus_spins = 0
    else:
        best_symbol = max(matches, key=matches.get)
        lines_hit = matches[best_symbol]

        if lines_hit >= 4:
            winnings = 100
            bonus_spins = 5
            message = f"🎉 EPIC! {lines_hit} lines of {best_symbol}!\nYou win {winnings} coins + {bonus_spins} Free Spins!"
        elif lines_hit == 3:
            winnings = 50
            bonus_spins = 2
            message = f"✨ Great! 3 lines of {best_symbol}.\nYou win {winnings} coins + {bonus_spins} Free Spins!"
        else:
            winnings = 20
            bonus_spins = 1
            message = f"✅ You hit a line of {best_symbol}.\nYou win {winnings} coins + {bonus_spins} Free Spin!"

    # Update wallet
    wallet['coins'] += winnings
    wallet['free_spins'] += bonus_spins

    # Show result and spin again button
    await query.edit_message_text(
        f"{result_text}\n\n{message}\n\n💰 Coins: {wallet['coins']} | 🎁 Free Spins: {wallet['free_spins']}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin")]]
        )
    )