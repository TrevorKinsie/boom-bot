"""
Wagering Command Handlers.

Each command handler is bound to a concrete command type and delegates to the
:class:`WageringApplicationService` to perform the actual mutation. Handlers
translate the command parameters into a service invocation and wrap the
result in a :class:`WalletCommandResult`.

Handlers are thin: they perform no business logic and hold no state beyond
their dependency on the application service.
"""

from __future__ import annotations

from typing import Any

from boombot.casino.application.bus.command_bus import (
    AbstractCommandResult,
    ICommandHandler,
)
from boombot.casino.shared.patterns import AbstractCommand
from boombot.casino.wagering.application.command.wallet_commands import (
    PlaceCrapsBetCommand,
    PlaceRouletteBetCommand,
    ResetWalletCommand,
    RollCrapsCommand,
    SpinRouletteCommand,
    SpinZeusCommand,
)
from boombot.casino.wagering.application.service.wagering_application_service import (
    WageringApplicationService,
)


class WalletCommandResult(AbstractCommandResult):
    """A command result carrying a textual summary for presentation."""

    def __init__(self, text: str, success: bool = True) -> None:
        super().__init__(success)
        self._text = text

    def get_text(self) -> str:
        return self._text


class AbstractWageringCommandHandler(ICommandHandler):
    """Base handler binding an application service to a command type."""

    def __init__(self, application_service: WageringApplicationService) -> None:
        self._application_service = application_service

    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        raise NotImplementedError


class PlaceRouletteBetCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: PlaceRouletteBetCommand
        text = self._application_service.place_roulette_bet(
            c.get_user_id(), c.get_tenant_id(), c.get_bet_type(), c.get_bet_value(), c.get_amount()
        )
        return WalletCommandResult(text)


class SpinRouletteCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: SpinRouletteCommand
        text = self._application_service.spin_roulette(c.get_tenant_id())
        return WalletCommandResult(text)


class PlaceCrapsBetCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: PlaceCrapsBetCommand
        text = self._application_service.place_craps_bet(
            c.get_user_id(), c.get_tenant_id(), c.get_bet_type(), c.get_amount()
        )
        return WalletCommandResult(text)


class RollCrapsCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: RollCrapsCommand
        text = self._application_service.roll_craps(c.get_tenant_id())
        return WalletCommandResult(text)


class SpinZeusCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: SpinZeusCommand
        text = self._application_service.spin_zeus(c.get_user_id())
        return WalletCommandResult(text)


class ResetWalletCommandHandler(AbstractWageringCommandHandler):
    def handle(self, command: AbstractCommand) -> AbstractCommandResult:
        c = command  # type: ResetWalletCommand
        text = self._application_service.reset_wallet(c.get_user_id())
        return WalletCommandResult(text)