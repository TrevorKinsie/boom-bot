"""
Wagering Bus Handler Registration.

Central registration of every wagering command handler against its command
type. Separating registration from the composition root keeps the wiring
declarative and easy to audit.
"""

from __future__ import annotations

from boombot.casino.application.bus.command_bus import CommandBus
from boombot.casino.wagering.application.command.wallet_command_handlers import (
    PlaceCrapsBetCommandHandler,
    PlaceRouletteBetCommandHandler,
    ResetWalletCommandHandler,
    RollCrapsCommandHandler,
    SpinRouletteCommandHandler,
    SpinZeusCommandHandler,
)
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


def register_all_wagering_handlers(
    command_bus: CommandBus, application_service: WageringApplicationService
) -> CommandBus:
    """Register every wagering command handler on the supplied command bus."""
    command_bus.register_handler(
        PlaceRouletteBetCommand, PlaceRouletteBetCommandHandler(application_service)
    )
    command_bus.register_handler(
        SpinRouletteCommand, SpinRouletteCommandHandler(application_service)
    )
    command_bus.register_handler(
        PlaceCrapsBetCommand, PlaceCrapsBetCommandHandler(application_service)
    )
    command_bus.register_handler(
        RollCrapsCommand, RollCrapsCommandHandler(application_service)
    )
    command_bus.register_handler(
        SpinZeusCommand, SpinZeusCommandHandler(application_service)
    )
    command_bus.register_handler(
        ResetWalletCommand, ResetWalletCommandHandler(application_service)
    )
    return command_bus