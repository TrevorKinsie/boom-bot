"""
Command Bus (write side of CQRS).

Commands represent an intention to mutate state. They are immutable data
transferred to a handler through the command bus. The bus resolves the
registered handler for a command type and executes it, optionally flowing the
command through a configured pipeline of middleware (Chain of Responsibility).

Handlers are registered against the concrete command class they serve and
return an :class:`AbstractCommandResult`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from boombot.casino.shared.exceptions import CommandHandlerResolutionException
from boombot.casino.shared.patterns import AbstractCommand


class AbstractCommandResult:
    """Marker base class for the result produced by a command handler."""

    def __init__(self, success: bool = True) -> None:
        self._success = success

    def is_successful(self) -> bool:
        return self._success


class ICommandHandler(ABC):
    """Port for a handler that processes a single command type."""

    @abstractmethod
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        raise NotImplementedError


class PipelineMiddleware(ABC):
    """Intercepting middleware executed around command handling."""

    @abstractmethod
    def handle(
        self,
        command: AbstractCommand,
        invoke_next: "CommandInvocation",
    ) -> AbstractCommandResult:
        raise NotImplementedError


class CommandInvocation:
    """Composable invocation unit; wraps a handler or a middleware + next."""

    def __init__(
        self,
        handler: ICommandHandler | None = None,
        middleware: PipelineMiddleware | None = None,
        next_invocation: "CommandInvocation | None" = None,
    ) -> None:
        self._handler = handler
        self._middleware = middleware
        self._next = next_invocation

    def execute(self, command: AbstractCommand) -> AbstractCommandResult:
        if self._middleware is not None and self._next is not None:
            return self._middleware.handle(command, self._next)
        if self._handler is not None:
            return self._handler.handle(command)
        raise CommandHandlerResolutionException(
            "Command invocation is neither a handler nor a middleware chain."
        )


class ICommandBus(ABC):
    """Port describing command dispatch."""

    @abstractmethod
    def dispatch(self, command: AbstractCommand) -> AbstractCommandResult:
        raise NotImplementedError


class CommandBus(ICommandBus):
    """Resolves the handler for a command and dispatches through middleware."""

    def __init__(self) -> None:
        self._handlers: dict[Type[AbstractCommand], ICommandHandler] = {}
        self._middleware: list[PipelineMiddleware] = []

    def register_handler(
        self, command_type: Type[AbstractCommand], handler: ICommandHandler
    ) -> "CommandBus":
        self._handlers[command_type] = handler
        return self

    def add_middleware(self, middleware: PipelineMiddleware) -> "CommandBus":
        self._middleware.append(middleware)
        return self

    def dispatch(self, command: AbstractCommand) -> AbstractCommandResult:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise CommandHandlerResolutionException(
                f"No command handler registered for: {type(command).__name__}"
            )

        # Compose the chain from the terminal handler outward, wrapping each
        # layer of middleware so the outermost middleware runs first.
        chain: CommandInvocation = CommandInvocation(handler=handler)
        for middleware in reversed(self._middleware):
            chain = CommandInvocation(middleware=middleware, next_invocation=chain)
        return chain.execute(command)
