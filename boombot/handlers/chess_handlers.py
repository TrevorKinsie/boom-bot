"""Telegram handlers for the full Chess Challenge interaction."""

from __future__ import annotations

import asyncio
from functools import wraps
import logging
from io import BytesIO
from typing import Any

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from boombot.core.config import get_chess_error_log_user_ids
from boombot.games.chess.game_service import GameService
from boombot.games.chess.image_service import image_service
from boombot.games.chess.request_logging import (
    ChessRequestLog,
    chess_request,
    current_chess_request,
)
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


def _request_metadata(update: Update) -> dict[str, int | str | None]:
    """Extract only stable Telegram identifiers for request correlation."""

    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    return {
        "chat_id": chat.id if chat else None,
        "initiator_user_id": user.id if user else None,
        "message_id": message.message_id if message else None,
        "source": "callback_query" if update.callback_query else "message",
    }


def _chess_entrypoint(operation: str):
    """Give every Telegram entrypoint a request log and failure report."""

    def decorator(handler):
        @wraps(handler)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # A callback can call another chess helper, so preserve one buffer
            # for the complete interaction rather than nesting reports.
            if current_chess_request() is not None:
                return await handler(update, context, *args, **kwargs)

            metadata = _request_metadata(update)
            with chess_request(operation, **metadata) as request:
                try:
                    result = await handler(update, context, *args, **kwargs)
                    if request.failed and not request.report_attempted:
                        await _send_full_diagnostic_log(update, request)
                    return result
                except Exception as exc:
                    logger.exception(
                        "Unhandled chess handler failure operation=%s "
                        "chat_id=%s user_id=%s message_id=%s",
                        operation,
                        metadata["chat_id"],
                        metadata["initiator_user_id"],
                        metadata["message_id"],
                    )
                    await _reply_with_transient_error(
                        update,
                        context,
                        f"❌ Chess {operation} failed. A diagnostic log is attached.",
                        error=exc,
                    )
                    return None

        return wrapped

    return decorator


def _service(context: ContextTypes.DEFAULT_TYPE) -> GameService:
    return context.application.bot_data["chess_game_service"]


async def _safe_delete(message: Any) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        logger.warning(
            "Could not delete the originating chess message message_id=%s",
            getattr(message, "message_id", None),
            exc_info=True,
        )


async def _delete_later(bot: Any, chat_id: int, message_id: int) -> None:
    await asyncio.sleep(5 * 60)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        logger.warning(
            "Could not delete transient chess error chat_id=%s message_id=%s",
            chat_id,
            message_id,
            exc_info=True,
        )


def _is_request_initiator(update: Update, request: ChessRequestLog) -> bool:
    user = update.effective_user
    if not user or request.initiator_user_id is None or user.id != request.initiator_user_id:
        return False
    allowed_ids = get_chess_error_log_user_ids()
    if request.initiator_user_id not in allowed_ids:
        logger.warning(
            "Skipping chess diagnostic-log delivery because request initiator is "
            "not allowlisted request_id=%s user_id=%s allowlist_size=%s",
            request.request_id,
            request.initiator_user_id,
            len(allowed_ids),
        )
        return False
    return True


async def _reply_with_transient_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    error: BaseException | None = None,
) -> None:
    message = update.effective_message
    if not message:
        logger.error(
            "Cannot send chess failure response because effective_message is missing "
            "text=%r",
            text,
        )
        return

    request = current_chess_request()
    diagnostic_allowed = bool(request and _is_request_initiator(update, request))
    if request:
        request.mark_failed(
            f"{type(error).__name__}: {error}" if error else text,
        )
        logger.error(
            "Chess request failed request_id=%s error_type=%s user_message=%r",
            request.request_id,
            type(error).__name__ if error else "operation_failure",
            text,
        )
    else:
        logger.error(
            "Chess request failed without a request context error_type=%s "
            "user_message=%r",
            type(error).__name__ if error else "operation_failure",
            text,
        )

    if diagnostic_allowed and request:
        user_text = f"{text}\nRequest ID: `{request.request_id}`"
    else:
        user_text = text.replace(" A diagnostic log is attached.", ".")
        user_text = user_text.replace("A diagnostic log is attached.", "")
    sent = None
    try:
        sent = await message.reply_text(
            user_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=game_keyboard(),
        )
        if update.effective_chat and getattr(sent, "message_id", None):
            context.application.create_task(
                _delete_later(context.bot, update.effective_chat.id, sent.message_id),
                update=update,
                name="delete-transient-chess-error",
            )
    except Exception:
        logger.exception(
            "Failed to send transient chess error response chat_id=%s user_id=%s",
            update.effective_chat.id if update.effective_chat else None,
            update.effective_user.id if update.effective_user else None,
        )

    if request:
        await _send_full_diagnostic_log(
            update,
            request,
            recipient_allowed=diagnostic_allowed,
        )
    else:
        logger.warning("No full chess diagnostic log available for failure response")


async def _send_full_diagnostic_log(
    update: Update,
    request: ChessRequestLog,
    *,
    recipient_allowed: bool | None = None,
) -> None:
    """Deliver one complete report only to the user who opened the request."""

    message = update.effective_message
    if not message:
        logger.error(
            "Cannot deliver chess diagnostic log because effective_message is missing "
            "request_id=%s",
            request.request_id,
        )
        request.report_attempted = True
        return

    if request.report_attempted:
        logger.debug(
            "Skipping duplicate chess diagnostic-log delivery request_id=%s",
            request.request_id,
        )
        return
    request.report_attempted = True

    if recipient_allowed is None:
        recipient_allowed = _is_request_initiator(update, request)
    if not recipient_allowed:
        logger.warning(
            "Skipping chess diagnostic-log delivery after recipient eligibility "
            "check request_id=%s current_user_id=%s initiator_user_id=%s",
            request.request_id,
            update.effective_user.id if update.effective_user else None,
            request.initiator_user_id,
        )
        return

    logger.error(
        "Sending full chess diagnostic log to request initiator request_id=%s "
        "record_count=%s",
        request.request_id,
        request.record_count,
    )
    log_bytes = request.render().encode("utf-8", errors="replace")
    try:
        await message.reply_document(
            document=InputFile(
                BytesIO(log_bytes),
                filename=f"chess-error-{request.request_id}.log",
            ),
            caption=(
                f"Chess diagnostic log for failed request "
                f"`{request.request_id}`."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(
            "Full chess diagnostic log delivered request_id=%s bytes=%s",
            request.request_id,
            len(log_bytes),
        )
        request.report_delivered = True
    except Exception:
        logger.exception(
            "Failed to deliver full chess diagnostic log request_id=%s "
            "chat_id=%s user_id=%s",
            request.request_id,
            update.effective_chat.id if update.effective_chat else None,
            update.effective_user.id if update.effective_user else None,
        )


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
        request = current_chess_request()
        if request:
            request.mark_failed("Chess board rendering or photo delivery failed")
        logger.exception(
            "Chess board rendering or photo delivery failed fen=%r flipped=%s "
            "last_move=%r cpu_destination=%r",
            fen,
            flipped,
            last_move,
            cpu_destination,
        )
        try:
            await message.reply_text(
                f"{caption}\n\n_(Board image unavailable)_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup or game_keyboard(),
            )
            logger.warning("Chess board fallback text delivered fen=%r", fen)
        except Exception:
            logger.exception("Chess board fallback text delivery also failed fen=%r", fen)
            raise


@_chess_entrypoint("start")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(
        "Handling chess start command chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    await _safe_delete(update.effective_message)
    if update.effective_message:
        await update.effective_message.reply_text(
            "Welcome to Chess Challenge! ♚\n\nClick below to start.",
            reply_markup=start_keyboard(),
        )


@_chess_entrypoint("help")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(
        "Handling chess help command chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    await _safe_delete(update.effective_message)
    if update.effective_message:
        await update.effective_message.reply_text(
            "📖 How to Play\n\n"
            "1. Start a game with /newgame.\n"
            "2. Reply to the board with your move (e.g. e4, Nf3, or O-O).\n"
            "3. Use the buttons for options.\n\n"
            "⚙️ Options: Resign or Draw",
        )


@_chess_entrypoint("newgame")
async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(
        "Handling chess new-game menu chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
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
        logger.warning(
            "Cannot start chess game because Telegram context is incomplete "
            "chat=%s user=%s message=%s",
            bool(update.effective_chat),
            bool(update.effective_user),
            bool(update.effective_message),
        )
        return
    logger.info(
        "Starting chess game chat_id=%s user_id=%s difficulty=%s",
        update.effective_chat.id,
        update.effective_user.id,
        difficulty,
    )
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
        logger.exception(
            "Chess game start failed chat_id=%s user_id=%s difficulty=%s",
            update.effective_chat.id,
            update.effective_user.id,
            difficulty,
        )
        await _reply_with_transient_error(
            update,
            context,
            "❌ Could not start the chess game. A diagnostic log is attached.",
            error=exc,
        )


async def _process_move(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    move_san: str,
) -> None:
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        logger.warning(
            "Cannot process chess move because Telegram context is incomplete "
            "chat=%s user=%s message=%s move=%r",
            bool(update.effective_chat),
            bool(update.effective_user),
            bool(update.effective_message),
            move_san,
        )
        return
    logger.info(
        "Processing chess move chat_id=%s user_id=%s move=%r",
        update.effective_chat.id,
        update.effective_user.id,
        move_san,
    )
    await _safe_delete(update.effective_message)
    if not move_san.strip():
        await _reply_with_transient_error(
            update,
            context,
            "Please specify a move, e.g., /move e4, or reply to the game board with `e4`.",
        )
        return

    try:
        result = await _service(context).make_move(
            update.effective_chat.id,
            update.effective_user.id,
            update.effective_user.username,
            move_san.strip(),
            update.effective_user.first_name,
        )
    except Exception as exc:
        logger.exception(
            "Chess move service raised an exception chat_id=%s user_id=%s move=%r",
            update.effective_chat.id,
            update.effective_user.id,
            move_san,
        )
        await _reply_with_transient_error(
            update,
            context,
            "❌ Could not process that chess move. A diagnostic log is attached.",
            error=exc,
        )
        return
    if not result.get("success"):
        logger.warning(
            "Chess move operation returned failure chat_id=%s user_id=%s move=%r "
            "failure_code=%s message=%r",
            update.effective_chat.id,
            update.effective_user.id,
            move_san,
            result.get("failureCode"),
            result.get("message"),
        )
        await _reply_with_transient_error(
            update,
            context,
            f"❌ *Chess move failed:* {result.get('message', 'Please try again.')}",
        )
        return

    logger.info(
        "Chess move accepted chat_id=%s user_id=%s move=%r game_id=%s "
        "cpu_move=%r status=%s",
        update.effective_chat.id,
        update.effective_user.id,
        move_san,
        (result.get("game") or {}).get("id"),
        result.get("cpuMove"),
        (result.get("game") or {}).get("status"),
    )

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


@_chess_entrypoint("move")
async def move_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Handling chess /move command args=%r", context.args or [])
    await _process_move(update, context, " ".join(context.args or []))


@_chess_entrypoint("reply_move")
async def reply_move_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    reply = message.reply_to_message if message else None
    if not message or not reply or not reply.from_user:
        logger.debug("Ignoring chess reply candidate without a usable replied-to message")
        return
    bot_user = context.application.bot_data.get("chess_bot_user")
    if bot_user is None:
        bot_user = await context.bot.get_me()
        context.application.bot_data["chess_bot_user"] = bot_user
    if reply.from_user.id != bot_user.id:
        logger.debug(
            "Ignoring reply candidate because it was not sent by the chess bot "
            "reply_author_id=%s bot_user_id=%s",
            reply.from_user.id,
            bot_user.id,
        )
        return
    logger.info(
        "Handling chess board reply move chat_id=%s user_id=%s message_id=%s move=%r",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
        message.message_id,
        message.text or "",
    )
    await _process_move(update, context, message.text or "")


@_chess_entrypoint("callback")
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        logger.warning("Chess callback received without callback query data")
        return
    data = query.data
    logger.info(
        "Handling chess callback data=%r chat_id=%s user_id=%s message_id=%s",
        data,
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
        update.effective_message.message_id if update.effective_message else None,
    )
    try:
        if data.startswith("difficulty_"):
            level = data.removeprefix("difficulty_")
            logger.info("Chess difficulty selected callback_level=%r resolved_level=%s", level, DIFFICULTY_LEVELS.get(level, 20))
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
            logger.info(
                "Chess resign action completed chat_id=%s success=%s message=%r",
                update.effective_chat.id,
                result.get("success"),
                result.get("message"),
            )
            if result.get("success"):
                await query.message.reply_text(result["message"])
            else:
                await _reply_with_transient_error(
                    update,
                    context,
                    f"❌ {result.get('message', 'Could not resign the game.')}",
                )
        elif data == "draw_check":
            await query.message.reply_text("🤝 Claim a draw?", reply_markup=draw_confirmation_keyboard())
        elif data == "draw_confirm" and update.effective_chat:
            result = await _service(context).draw_game(update.effective_chat.id)
            logger.info(
                "Chess draw action completed chat_id=%s success=%s message=%r",
                update.effective_chat.id,
                result.get("success"),
                result.get("message"),
            )
            if result.get("success"):
                await query.message.reply_text(result["message"])
            else:
                await _reply_with_transient_error(
                    update,
                    context,
                    f"❌ {result.get('message', 'Could not end the game.')}",
                )
        else:
            logger.warning("Unknown chess callback data=%r", data)
            await query.answer("Action not recognized.")
            return
        await query.answer()
    except Exception as exc:
        logger.exception(
            "Chess callback error data=%r chat_id=%s user_id=%s",
            data,
            update.effective_chat.id if update.effective_chat else None,
            update.effective_user.id if update.effective_user else None,
        )
        await _reply_with_transient_error(
            update,
            context,
            "❌ Error processing that chess action. A diagnostic log is attached.",
            error=exc,
        )
        try:
            await query.answer("Error processing action")
        except Exception:
            logger.exception("Failed to acknowledge failed chess callback data=%r", data)
