"""Telegram handlers for the full Chess Challenge interaction."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Any

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from boombot.games.chess.game_service import GameService
from boombot.games.chess.image_service import image_service
from boombot.games.chess.menus import (
    DIFFICULTY_LEVELS,
    difficulty_keyboard,
    draw_confirmation_keyboard,
    game_keyboard,
    game_options_keyboard,
    resign_confirmation_keyboard,
    start_keyboard,
)

logger = logging.getLogger(__name__)


def _service(context: ContextTypes.DEFAULT_TYPE) -> GameService:
    return context.application.bot_data["chess_game_service"]


async def _safe_delete(message: Any) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete the originating Telegram message", exc_info=True)


async def _delete_later(bot: Any, chat_id: int, message_id: int) -> None:
    await asyncio.sleep(5 * 60)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        logger.debug("Could not delete transient chess error", exc_info=True)


async def _reply_with_transient_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> None:
    message = update.effective_message
    if not message:
        return
    try:
        sent = await message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=game_keyboard(),
        )
        if update.effective_chat:
            context.application.create_task(
                _delete_later(context.bot, update.effective_chat.id, sent.message_id),
                update=update,
                name="delete-transient-chess-error",
            )
    except Exception:
        logger.exception("Failed to send transient chess error")


def _difficulty_label(level: int) -> str:
    if level <= 1:
        return "Beginner"
    if level <= 5:
        return "Easy"
    if level <= 10:
        return "Medium"
    if level <= 15:
        return "Hard"
    return "Grandmaster"


def _lichess_url(fen: str) -> str:
    return f"https://lichess.org/analysis/{fen.replace(' ', '_')}"


async def _send_board(
    update: Update,
    *,
    fen: str,
    flipped: bool,
    caption: str,
    last_move: tuple[str, str] | None = None,
    cpu_destination: str | None = None,
    reply_markup=None,
) -> None:
    message = update.effective_message
    if not message:
        return
    try:
        board_image = await asyncio.to_thread(
            image_service.generate_board_image,
            fen,
            flipped,
            last_move,
            cpu_destination,
        )
        await message.reply_photo(
            photo=InputFile(BytesIO(board_image), filename="chess-board.png"),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup or game_keyboard(),
        )
    except Exception:
        logger.exception("Chess board rendering failed")
        await message.reply_text(
            f"{caption}\n\n_(Board image unavailable)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup or game_keyboard(),
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_delete(update.effective_message)
    if update.effective_message:
        await update.effective_message.reply_text(
            "Welcome to Chess Challenge! ♚\n\nClick below to start.",
            reply_markup=start_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_delete(update.effective_message)
    if update.effective_message:
        await update.effective_message.reply_text(
            "📖 How to Play\n\n"
            "1. Start a game with /newgame.\n"
            "2. Reply to the board with your move (e.g. e4, Nf3, or O-O).\n"
            "3. Use the buttons for options.\n\n"
            "⚙️ Options: Resign or Draw",
        )


async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_delete(update.effective_message)
    if update.effective_message:
        await update.effective_message.reply_text(
            "🎯 Select difficulty level:",
            reply_markup=difficulty_keyboard(),
        )


async def _start_game_with_difficulty(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    difficulty: int,
) -> None:
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    try:
        result = await _service(context).create_game(
            update.effective_chat.id,
            update.effective_user.id,
            update.effective_user.username,
            difficulty,
            update.effective_user.first_name,
        )
        community_is_black = result["communityColor"] == "b"
        community_color = "Black" if community_is_black else "White"
        stockfish_color = "White" if community_is_black else "Black"
        fen = result["fen"]
        caption = (
            "♟️ *New Game Started!*\n\n"
            f"👥 Community playing as *{community_color}*\n"
            f"🤖 Stockfish playing as *{stockfish_color}*\n\n"
        )
        if result.get("initialCpuMove"):
            caption += f"Stockfish opens with: `{result['initialCpuMove']}`\n_Your turn! Reply with your move._\n\n"
        else:
            caption += "_Community to move first!_\n\n"
        caption += f"🔗 [Analyze on Lichess]({_lichess_url(fen)})"
        await _send_board(
            update,
            fen=fen,
            flipped=community_is_black,
            caption=caption,
        )
    except Exception as exc:
        await _reply_with_transient_error(update, context, f"❌ Error: {exc}")


async def _process_move(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    move_san: str,
) -> None:
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    await _safe_delete(update.effective_message)
    if not move_san.strip():
        await update.effective_message.reply_text(
            "Please specify a move, e.g., /move e4, or reply to the game board with `e4`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    result = await _service(context).make_move(
        update.effective_chat.id,
        update.effective_user.id,
        update.effective_user.username,
        move_san.strip(),
        update.effective_user.first_name,
    )
    if not result.get("success"):
        await _reply_with_transient_error(
            update,
            context,
            f"❌ *Invalid move:* {result.get('message', 'Please try again.')}",
        )
        return

    fen = result.get("fen")
    game = result.get("game") or {}
    if not fen:
        await update.effective_message.reply_text(result.get("message", "Move accepted."))
        return

    community_is_black = bool(result.get("isCommunityBlack", False))
    if "isCommunityBlack" not in result:
        moves = _service(context).database.find_moves(game["id"])
        community_is_black = bool(moves and moves[0]["user_id"] is None)

    parts: list[str] = []
    if result.get("moveNumber"):
        parts.append(f"Move #{result['moveNumber']}")
    if result.get("scoreDelta") is not None and result.get("evalScore") is not None:
        delta = int(result["scoreDelta"])
        emoji = "📈" if delta > 0 else "📉" if delta < 0 else "➖"
        sign = "+" if delta > 0 else ""
        parts.append(f"{emoji} {sign}{delta}")
        parts.append(f"Eval: {result['evalScore']}")

    caption = f"♟️ *Game vs Stockfish ({_difficulty_label(game.get('difficulty', 20))})*\n\n"
    caption += f"👤 You: `{move_san.strip()}`\n"
    if result.get("cpuMove"):
        caption += f"🤖 Stockfish: `{result['cpuMove']}`\n"
    if parts:
        caption += "\n" + " • ".join(parts) + "\n"
    if result.get("message") and "played" not in result["message"]:
        caption += f"\n📊 {result['message']}\n"
    caption += f"\n🔗 [Analyze on Lichess]({_lichess_url(fen)})"

    last_move = None
    if result.get("cpuMoveFrom") and result.get("cpuMoveTo"):
        last_move = (result["cpuMoveFrom"], result["cpuMoveTo"])
    await _send_board(
        update,
        fen=fen,
        flipped=community_is_black,
        caption=caption,
        last_move=last_move,
        cpu_destination=result.get("cpuMoveTo"),
    )


async def move_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _process_move(update, context, " ".join(context.args or []))


async def reply_move_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    reply = message.reply_to_message if message else None
    if not message or not reply or not reply.from_user:
        return
    bot_user = context.application.bot_data.get("chess_bot_user")
    if bot_user is None:
        bot_user = await context.bot.get_me()
        context.application.bot_data["chess_bot_user"] = bot_user
    if reply.from_user.id != bot_user.id:
        return
    await _process_move(update, context, message.text or "")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    try:
        if data.startswith("difficulty_"):
            level = data.removeprefix("difficulty_")
            await _start_game_with_difficulty(update, context, DIFFICULTY_LEVELS.get(level, 20))
        elif data == "newgame_menu":
            await query.message.reply_text("🎯 Select difficulty level:", reply_markup=difficulty_keyboard())
        elif data == "help":
            await query.message.reply_text(
                "📖 How to Play\n\n"
                "1. Start a game with /newgame.\n"
                "2. Reply to the board with your move (e.g. e4, Nf3).\n"
                "3. Use the buttons for options.\n\n"
                "⚙️ Options: Resign or Draw",
            )
        elif data == "game_options":
            await query.edit_message_reply_markup(reply_markup=game_options_keyboard())
        elif data == "back_to_game":
            await query.edit_message_reply_markup(reply_markup=game_keyboard())
        elif data == "back_to_options":
            await query.edit_message_reply_markup(reply_markup=game_options_keyboard())
        elif data == "resign_check":
            await query.message.reply_text("🏳️ Are you sure you want to resign?", reply_markup=resign_confirmation_keyboard())
        elif data == "resign_confirm" and update.effective_chat:
            result = await _service(context).resign_game(update.effective_chat.id)
            await query.message.reply_text(result["message"])
        elif data == "draw_check":
            await query.message.reply_text("🤝 Claim a draw?", reply_markup=draw_confirmation_keyboard())
        elif data == "draw_confirm" and update.effective_chat:
            result = await _service(context).draw_game(update.effective_chat.id)
            await query.message.reply_text(result["message"])
        else:
            await query.answer("Action not recognized.")
            return
        await query.answer()
    except Exception:
        logger.exception("Chess callback error")
        try:
            await query.answer("Error processing action")
        except Exception:
            pass
