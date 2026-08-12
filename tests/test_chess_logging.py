"""Regression tests for correlated chess failures and Telegram diagnostics."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import chess
import pytest

from boombot.core.config import get_chess_error_log_user_ids
from boombot.games.chess.request_logging import chess_request
from boombot.handlers.chess_handlers import (
    _reply_with_transient_error,
    move_command,
)


@pytest.fixture(autouse=True)
def configured_chess_error_log_users(monkeypatch):
    monkeypatch.setenv("CHESS_ERROR_LOG_USER_IDS", "111111,222222")


def _telegram_context(*, service=None):
    message = MagicMock()
    message.message_id = 77
    message.reply_to_message = None
    message.text = "/move e4"
    message.delete = AsyncMock()
    message.reply_text = AsyncMock(return_value=None)
    message.reply_document = AsyncMock()

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=111111, username="kevin", first_name="Kevin"),
        effective_message=message,
        callback_query=None,
    )
    application = SimpleNamespace(
        bot_data={"chess_game_service": service},
        create_task=MagicMock(),
    )
    context = SimpleNamespace(
        application=application,
        bot=MagicMock(),
        args=["e4"],
    )
    return update, context, message


def _document_text(message) -> str:
    document = message.reply_document.await_args.kwargs["document"]
    content = getattr(document, "input_file_content", b"")
    if isinstance(content, str):
        return content
    return content.decode("utf-8")


@pytest.mark.asyncio
async def test_failed_chess_message_sends_full_correlated_log_to_initiator():
    service = SimpleNamespace(
        make_move=AsyncMock(side_effect=RuntimeError("engine exploded")),
    )
    update, context, message = _telegram_context(service=service)

    await move_command(update, context)

    message.reply_text.assert_awaited_once()
    message.reply_document.assert_awaited_once()
    document = message.reply_document.await_args.kwargs["document"]
    assert document.filename.startswith("chess-error-")
    assert "Chess diagnostic log" in _document_text(message)
    assert "operation=move" in _document_text(message)
    assert "engine exploded" in _document_text(message)
    assert "Chess move service raised an exception" in _document_text(message)
    assert "diagnostic log is attached" in message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_failed_chess_result_also_sends_diagnostic_log():
    service = SimpleNamespace(
        make_move=AsyncMock(
            return_value={
                "success": False,
                "failureCode": "invalid_move",
                "message": "Invalid move or error: e9",
            }
        ),
    )
    update, context, message = _telegram_context(service=service)
    context.args = ["e9"]

    await move_command(update, context)

    message.reply_document.assert_awaited_once()
    log_text = _document_text(message)
    assert "failure_code=invalid_move" in log_text
    assert "Invalid move or error: e9" in log_text


@pytest.mark.asyncio
async def test_board_fallback_failure_is_reported_after_text_fallback():
    service = SimpleNamespace(
        make_move=AsyncMock(
            return_value={
                "success": True,
                "fen": chess.Board().fen(),
                "game": {"id": "game-1", "difficulty": 10, "status": "active"},
                "isCommunityBlack": False,
                "moveNumber": 1,
                "message": "You played e4. I played e5.",
                "cpuMove": "e5",
                "scoreDelta": 0,
                "evalScore": 0,
                "cpuMoveFrom": "e7",
                "cpuMoveTo": "e5",
            }
        ),
    )
    update, context, message = _telegram_context(service=service)

    with patch(
        "boombot.handlers.chess_handlers.image_service.generate_board_image",
        side_effect=RuntimeError("renderer exploded"),
    ):
        await move_command(update, context)

    message.reply_text.assert_awaited_once()
    message.reply_document.assert_awaited_once()
    assert "renderer exploded" in _document_text(message)


@pytest.mark.asyncio
async def test_diagnostic_log_is_not_sent_to_a_non_initiating_user():
    update, context, message = _telegram_context()

    with chess_request(
        "test_failure",
        chat_id=123,
        initiator_user_id=111111,
        message_id=77,
        source="message",
    ):
        update.effective_user = SimpleNamespace(
            id=999,
            username="different-user",
            first_name="Different",
        )
        await _reply_with_transient_error(update, context, "failure")

    message.reply_text.assert_awaited_once()
    message.reply_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_diagnostic_log_is_not_sent_to_a_non_allowlisted_initiator():
    service = SimpleNamespace(
        make_move=AsyncMock(side_effect=RuntimeError("engine exploded")),
    )
    update, context, message = _telegram_context(service=service)
    update.effective_user = SimpleNamespace(
        id=999999,
        username="unallowlisted",
        first_name="Unallowlisted",
    )

    await move_command(update, context)

    message.reply_text.assert_awaited_once()
    assert "diagnostic log" not in message.reply_text.await_args.args[0].lower()
    message.reply_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_log_captures_async_and_threaded_chess_records():
    logger = logging.getLogger("boombot.games.chess.test")

    with chess_request(
        "capture_test",
        chat_id=1,
        initiator_user_id=2,
        message_id=3,
        source="message",
    ) as request:
        logger.info("before engine call")
        await asyncio.to_thread(logger.warning, "inside engine thread")
        request.mark_failed("test failure")
        rendered = request.render()

    assert f"request_id={request.request_id}" in rendered
    assert "before engine call" in rendered
    assert "inside engine thread" in rendered
    assert "failure_summary=test failure" in rendered


def test_request_log_redacts_configured_credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:super-secret-token")
    logger = logging.getLogger("boombot.games.chess.test")

    with chess_request("redaction_test") as request:
        logger.error(
            "upstream error authorization: Bearer 123456:super-secret-token "
            "token=123456:super-secret-token"
        )
        rendered = request.render()

    assert "super-secret-token" not in rendered
    assert "<redacted>" in rendered


def test_chess_error_log_allowlist_ignores_invalid_entries(monkeypatch):
    monkeypatch.setenv("CHESS_ERROR_LOG_USER_IDS", "111111,not-an-id,-2,222222")

    assert get_chess_error_log_user_ids() == frozenset({111111, 222222})


def test_chess_error_log_allowlist_is_empty_when_secret_is_unset(monkeypatch):
    monkeypatch.delenv("CHESS_ERROR_LOG_USER_IDS", raising=False)

    assert get_chess_error_log_user_ids() == frozenset()
