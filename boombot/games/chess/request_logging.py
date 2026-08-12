"""Correlated, in-memory diagnostic logs for one chess interaction.

The bot's normal file handler only records errors and does not preserve the
INFO/DEBUG trail that explains what happened immediately before a failure.
This module keeps a small request-scoped copy of every ``boombot`` log record.
The context variable propagates through ``asyncio`` tasks and
``asyncio.to_thread`` calls, so database, renderer, and Stockfish messages all
land in the same report without passing a logger object through every method.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
import re
import threading
import time
import uuid


_logger = logging.getLogger(__name__)
_current_request: ContextVar["ChessRequestLog | None"] = ContextVar(
    "chess_request_log",
    default=None,
)


def _one_line(value: object) -> str:
    """Make metadata safe to put in a single diagnostic-log line."""

    return str(value).replace("\r", "\\r").replace("\n", "\\n")


def _redact_secrets(text: str) -> str:
    """Remove configured credentials if an exception ever echoes one."""

    redacted = text
    for env_name in (
        "TELEGRAM_TOKEN",
        "TELEGRAM_TOKEN_DEV",
        "LLM_API_KEY",
    ):
        secret = os.getenv(env_name)
        if secret and len(secret) >= 4:
            redacted = redacted.replace(secret, "<redacted>")
    # Also cover common key/value forms when a secret is present only in a
    # library-generated message rather than in the current environment.
    return re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,]+",
        r"\1<redacted>",
        redacted,
    )


@dataclass
class ChessRequestLog:
    """All log records and metadata associated with one Telegram update."""

    operation: str
    chat_id: int | None = None
    initiator_user_id: int | None = None
    message_id: int | None = None
    source: str | None = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    _started_monotonic: float = field(
        default_factory=time.monotonic,
        init=False,
        repr=False,
    )
    _records: list[str] = field(default_factory=list, init=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    failed: bool = field(default=False, init=False)
    failure_summary: str | None = field(default=None, init=False)
    report_attempted: bool = field(default=False, init=False)
    report_delivered: bool = field(default=False, init=False)

    def capture(self, formatted_record: str) -> None:
        """Append one already-formatted record from any participating thread."""

        with self._lock:
            self._records.append(formatted_record)

    def mark_failed(self, summary: str) -> None:
        self.failed = True
        self.failure_summary = _redact_secrets(_one_line(summary))

    @property
    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def render(self, *, status: str = "failure") -> str:
        """Return the complete diagnostic snapshot captured so far."""

        duration_ms = (time.monotonic() - self._started_monotonic) * 1000
        with self._lock:
            records = list(self._records)

        metadata = [
            "Chess diagnostic log",
            f"request_id={self.request_id}",
            f"operation={_one_line(self.operation)}",
            f"status={_one_line(status)}",
            f"started_at={self.started_at.isoformat()}",
            f"duration_ms={duration_ms:.1f}",
            f"chat_id={self.chat_id}",
            f"initiator_user_id={self.initiator_user_id}",
            f"message_id={self.message_id}",
            f"source={_one_line(self.source)}",
            f"failed={self.failed}",
            f"failure_summary={_one_line(self.failure_summary) if self.failure_summary else ''}",
            f"report_attempted={self.report_attempted}",
            f"report_delivered={self.report_delivered}",
            f"captured_records={len(records)}",
            "",
        ]
        if not records:
            records.append("No log records were captured before the failure.")
        return "\n".join(metadata + records) + "\n"


class _ChessRequestCaptureHandler(logging.Handler):
    """Copy records into the active request without replacing app logging."""

    _is_chess_request_capture_handler = True

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        request = _current_request.get()
        if request is None:
            return
        try:
            formatted = _redact_secrets(self.format(record))
            request.capture(
                f"[request_id={request.request_id}] {formatted}",
            )
        except Exception:  # noqa: BLE001 - capture must never break real logging
            # Diagnostic capture must never turn a chess operation into a
            # second failure or interfere with the application's real handlers.
            self.handleError(record)


def _install_capture_handler() -> None:
    """Install one package-level capture handler, surviving root reconfigures."""

    package_logger = logging.getLogger("boombot")
    # Let chess DEBUG records reach this handler while the application's root
    # handlers can continue filtering normal console/file output at INFO.
    package_logger.setLevel(logging.DEBUG)
    if any(
        getattr(handler, "_is_chess_request_capture_handler", False)
        for handler in package_logger.handlers
    ):
        return
    package_logger.addHandler(_ChessRequestCaptureHandler())


def current_chess_request() -> ChessRequestLog | None:
    """Return the request active in this task/thread, if there is one."""

    return _current_request.get()


@contextmanager
def chess_request(
    operation: str,
    *,
    chat_id: int | None = None,
    initiator_user_id: int | None = None,
    message_id: int | None = None,
    source: str | None = None,
) -> Iterator[ChessRequestLog]:
    """Capture all package logs emitted while one chess operation runs."""

    request = ChessRequestLog(
        operation=operation,
        chat_id=chat_id,
        initiator_user_id=initiator_user_id,
        message_id=message_id,
        source=source,
    )
    token = _current_request.set(request)
    _logger.info(
        "Chess request started request_id=%s operation=%s chat_id=%s "
        "initiator_user_id=%s message_id=%s source=%s",
        request.request_id,
        operation,
        chat_id,
        initiator_user_id,
        message_id,
        source,
    )
    try:
        yield request
    finally:
        duration_ms = (time.monotonic() - request._started_monotonic) * 1000
        _logger.info(
            "Chess request finished request_id=%s operation=%s duration_ms=%.1f "
            "failed=%s captured_records=%s",
            request.request_id,
            operation,
            duration_ms,
            request.failed,
            request.record_count,
        )
        _current_request.reset(token)


_install_capture_handler()
