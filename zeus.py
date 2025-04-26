import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

symbols = ['⚡', '🦁', '🏺', '🦅', '👑', '🇦', '🇰', '🇯', '🧔‍♂️']

wallets = {}

# Spin a 5x5 grid
def spin_grid():
    return [[random.choice(symbols) for _ in range(5)] for _ in range(5)]

# Format grid
def format_grid(grid):
    return '\n'.join([' | '.join(row) for row in grid])

# Initialize player
def initialize_user(user_id):
    if user_id not in wallets:
        wallets[user_id] = {'coins': 100, 'free_spins': 0}

# Count winning lines
def count_lines(grid):
    matches = []

    def evaluate_line(line):
        if all(symbol == '🧔‍♂️' for symbol in line):
            return 'jackpot', 5
        
        non_zeus = [s for s in line if s != '🧔‍♂️']
        if not non_zeus:
            return None, 0

        target = max(set(non_zeus), key=non_zeus.count)
        count_target = sum(1 for s in line if s == target)
        count_zeus = line.count('🧔‍♂️')

        # Rules: max 1 Zeus allowed
        if count_target >= 3 and count_zeus <= 1:
            return target, count_target + count_zeus
        else:
            return None, 0

    # Check rows
    for row in grid:
        symbol, count = evaluate_line(row)
        if count >= 3:
            matches.append((symbol, count))

    # Check columns
    for col in range(5):
        column = [grid[row][col] for row in range(5)]
        symbol, count = evaluate_line(column)
        if count >= 3:
            matches.append((symbol, count))

    # Check diagonals
    diag1 = [grid[i][i] for i in range(5)]
    diag2 = [grid[i][4-i] for i in range(5)]
    for diag in [diag1, diag2]:
        symbol, count = evaluate_line(diag)
        if count >= 3:
            matches.append((symbol, count))

    return matches

# /start command
async def zeus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    initialize_user(user_id)
    await update.message.reply_text(
        "⚡ Welcome to Zeus Slots (HARDCORE Edition)!\n\n"
        "You start with 100 coins.\nEach spin costs 10 coins.\n"
        "Try your luck!",
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

# Spin button
async def spin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    initialize_user(user_id)
    wallet = wallets[user_id]

    spin_cost = 10

    if wallet['free_spins'] > 0:
        wallet['free_spins'] -= 1
    elif wallet['coins'] >= spin_cost:
        wallet['coins'] -= spin_cost
    else:
        await query.edit_message_text("😞 Not enough coins! Use /wallet to check your balance.")
        return

    grid = spin_grid()
    result_text = format_grid(grid)
    matches = count_lines(grid)

    winnings = 0
    bonus_spins = 0
    message_lines = []
    jackpot = False

    if matches:
        for symbol, count in matches:
            if symbol == 'jackpot':
                winnings += 5000
                message_lines.append("🧔‍♂️ ZOOOOOS!!! JACKPOT!!! +5000 coins!")
                jackpot = True
            elif count == 5:
                winnings += 200
                bonus_spins += 2
                message_lines.append(f"🎯 5 of a kind ({symbol})! +200 coins +2 Free Spins!")
            elif count == 4:
                winnings += 50
                bonus_spins += 1
                message_lines.append(f"✅ 4 of a kind ({symbol})! +50 coins +1 Free Spin!")
            elif count == 3:
                winnings += 10
                message_lines.append(f"✔️ 3 of a kind ({symbol})! +10 coins.")
    else:
        message_lines.append("No matches this time. Try again!")

    wallet['coins'] += winnings
    wallet['free_spins'] += bonus_spins

    final_message = "\n".join(message_lines)

    await query.edit_message_text(
        f"{result_text}\n\n{final_message}\n\n💰 Coins: {wallet['coins']} | 🎁 Free Spins: {wallet['free_spins']}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin")]]
        )
    )