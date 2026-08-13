"""
Command Bus Tests.

Validates command dispatch, handler resolution, and middleware chain ordering.
"""

import pytest

from boombot.casino.application.bus.command_bus import (
    AbstractCommandResult,
    CommandBus,
    CommandInvocation,
    ICommandHandler,
    PipelineMiddleware,
)
from boombot.casino.shared.exceptions import CommandHandlerResolutionException
from boombot.casino.shared.patterns import AbstractCommand


class RecordCommand(AbstractCommand):
    def __init__(self, payload: str = "hello") -> None:
        super().__init__()
        self._payload = payload

    def get_payload(self) -> str:
        return self._payload


class RecordCommandResult(AbstractCommandResult):
    def __init__(self, text: str) -> None:
        super().__init__(success=True)
        self._text = text

    def get_text(self) -> str:
        return self._text


class RecordCommandHandler(ICommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        return RecordCommandResult(f"handled:{command.get_payload()}")


class RecordingMiddleware(PipelineMiddleware):
    def __init__(self, name: str, order: list[str]) -> None:
        self._name = name
        self._order = order

    def handle(
        self, command: AbstractCommand, invoke_next: CommandInvocation
    ) -> AbstractCommandResult:
        self._order.append(f"{self._name}:before")
        result = invoke_next.execute(command)
        self._order.append(f"{self._name}:after")
        return result


class TestCommandBus:
    def test_dispatch_resolves_handler(self):
        bus = CommandBus()
        bus.register_handler(RecordCommand, RecordCommandHandler())
        result = bus.dispatch(RecordCommand("world"))
        assert result.get_text() == "handled:world"

    def test_unregistered_command_raises(self):
        bus = CommandBus()
        with pytest.raises(CommandHandlerResolutionException):
            bus.dispatch(RecordCommand())

    def test_middleware_runs_outermost_first(self):
        bus = CommandBus()
        bus.register_handler(RecordCommand, RecordCommandHandler())
        order: list[str] = []
        bus.add_middleware(RecordingMiddleware("one", order))
        bus.add_middleware(RecordingMiddleware("two", order))
        bus.dispatch(RecordCommand())
        assert order == ["one:before", "two:before", "two:after", "one:after"]