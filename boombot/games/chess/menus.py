"""Inline keyboards for the Chess Challenge Telegram flow."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


DIFFICULTY_LEVELS = {
    "beginner": 1,
    "easy": 5,
    "medium": 10,
    "hard": 15,
    "grandmaster": 20,
}


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("New Game", callback_data="newgame_menu"),
            InlineKeyboardButton("Help", callback_data="help"),
        ]]
    )


def difficulty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👶 Beginner", callback_data="difficulty_beginner")],
        [InlineKeyboardButton("🟢 Easy", callback_data="difficulty_easy")],
        [InlineKeyboardButton("🟡 Medium", callback_data="difficulty_medium")],
        [InlineKeyboardButton("🔴 Hard", callback_data="difficulty_hard")],
        [InlineKeyboardButton("👑 Grandmaster", callback_data="difficulty_grandmaster")],
    ])


def game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Options", callback_data="game_options")],
    ])


def game_options_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏳️ Resign", callback_data="resign_check"),
            InlineKeyboardButton("🤝 Draw", callback_data="draw_check"),
        ],
        [InlineKeyboardButton("« Back", callback_data="back_to_game")],
    ])


def resign_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, Resign", callback_data="resign_confirm"),
            InlineKeyboardButton("No, Cancel", callback_data="back_to_options"),
        ]
    ])


def draw_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, Claim Draw", callback_data="draw_confirm"),
            InlineKeyboardButton("No, Cancel", callback_data="back_to_options"),
        ]
    ])
