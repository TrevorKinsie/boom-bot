"""
Command Pipeline Middleware.

The write pipeline is a chain of interceptors that execute around the
terminal command handler. Each middleware implements :class:`PipelineMiddleware`
and is responsible for one cross-cutting concern:

* :class:`IdempotencyMiddleware` - deduplicates commands by command identifier.
* :class:`AuditTrailMiddleware` - records every dispatched command.
* :class:`RetryMiddleware` - retries transient persistence failures.
* :class:`TenantBindingMiddleware` - binds the tenant context for the command.

Middleware order is preserved as registered on the command bus.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from boombot.casino.application.bus.command_bus import (
    AbstractCommandResult,
    CommandInvocation,
    PipelineMiddleware,
)
from boombot.casino.multitenancy.tenant import TenantContext, TenantId
from boombot.casino.shared.exceptions import CasinoException
from boombot.casino.shared.patterns import AbstractCommand

logger = logging.getLogger(__name__)


class AbstractCommandContextMiddleware(PipelineMiddleware):
    """Base middleware that can inspect the command being processed."""

    def handle(
        self,
        command: AbstractCommand,
        invoke_next: CommandInvocation,
    ) -> AbstractCommandResult:
        self.before_command(command)
        try:
            result = invoke_next.execute(command)
        finally:
            self.after_command(command)
        return result

    def before_command(self, command: AbstractCommand) -> None:
        pass

    def after_command(self, command: AbstractCommand) -> None:
        pass


class AuditTrailMiddleware(AbstractCommandContextMiddleware):
    """Logs every command execution with duration and outcome."""

    def before_command(self, command: AbstractCommand) -> None:
        command_metadata = getattr(command, "get_command_id", None)
        command_id = command_metadata() if callable(command_metadata) else None
        self._started_at = time.monotonic()
        logger.info(
            "AUDIT BEGIN command=%s command_id=%s",
            type(command).__name__,
            command_id,
        )

    def after_command(self, command: AbstractCommand) -> None:
        elapsed_ms = (time.monotonic() - self._started_at) * 1000.0
        logger.info(
            "AUDIT END command=%s elapsed_ms=%.1f",
            type(command).__name__,
            elapsed_ms,
        )


class IdempotencyMiddleware(AbstractCommandContextMiddleware):
    """Skips commands whose identifier has already been processed."""

    def __init__(self) -> None:
        self._processed_command_ids: set[str] = set()

    def handle(
        self,
        command: AbstractCommand,
        invoke_next: CommandInvocation,
    ) -> AbstractCommandResult:
        command_id = self._extract_command_id(command)
        if command_id is not None and command_id in self._processed_command_ids:
            logger.warning("Idempotency guard rejected duplicate command id %s", command_id)
            return AbstractCommandResult(success=True)
        result = invoke_next.execute(command)
        if command_id is not None:
            self._processed_command_ids.add(command_id)
        return result

    @staticmethod
    def _extract_command_id(command: AbstractCommand) -> str | None:
        accessor = getattr(command, "get_command_id", None)
        if callable(accessor):
            return accessor()
        return None


class RetryMiddleware(AbstractCommandContextMiddleware):
    """Retries a command a bounded number of times on persistence failures."""

    def __init__(self, max_attempts: int = 3, retry_delay_seconds: float = 0.05) -> None:
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    def handle(
        self,
        command: AbstractCommand,
        invoke_next: CommandInvocation,
    ) -> AbstractCommandResult:
        last_exception: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return invoke_next.execute(command)
            except CasinoException as exc:
                last_exception = exc
                if not self._is_retryable(exc):
                    raise
                if attempt < self._max_attempts:
                    time.sleep(self._retry_delay_seconds * attempt)
        raise last_exception  # type: ignore[misc]

    @staticmethod
    def _is_retryable(exception: CasinoException) -> bool:
        from boombot.casino.shared.exceptions import PersistenceException

        return isinstance(exception, PersistenceException)


class TenantBindingMiddleware(AbstractCommandContextMiddleware):
    """Binds the command's tenant identifier into the thread-local context."""

    def before_command(self, command: AbstractCommand) -> None:
        tenant_identifier = getattr(command, "_tenant_id", None)
        if tenant_identifier is not None:
            TenantContext.set_current(TenantId(str(tenant_identifier)))

    def after_command(self, command: AbstractCommand) -> None:
        TenantContext.set_current(None)