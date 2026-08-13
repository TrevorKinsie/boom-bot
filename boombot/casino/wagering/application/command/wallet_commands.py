"""
Wagering Commands.

Command objects are immutable descriptions of write-side intentions within the
wagering context. They carry the identifiers required to locate the relevant
wallet, tenant (channel), and game state, plus the parameters of the intended
action. Handlers registered against these command types perform the mutation.
"""

from __future__ import annotations

from typing import Any, Optional

from boombot.casino.shared.patterns import AbstractCommand


class AbstractWageringCommand(AbstractCommand):
    """Base class for wagering context commands."""

    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        game: str,
    ) -> None:
        super().__init__()
        self._user_id = user_id
        self._tenant_id = tenant_id
        self._game = game

    def get_user_id(self) -> str:
        return self._user_id

    def get_tenant_id(self) -> str:
        return self._tenant_id

    def get_game(self) -> str:
        return self._game


class PlaceRouletteBetCommand(AbstractWageringCommand):
    """Intent to place a single roulette wager."""

    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        bet_type: str,
        bet_value: Optional[str],
        amount: str,
    ) -> None:
        super().__init__(user_id, tenant_id, game="roulette")
        self._bet_type = bet_type
        self._bet_value = bet_value or ""
        self._amount = amount

    def get_bet_type(self) -> str:
        return self._bet_type

    def get_bet_value(self) -> str:
        return self._bet_value

    def get_amount(self) -> str:
        return self._amount


class SpinRouletteCommand(AbstractWageringCommand):
    """Intent to spin the roulette wheel and resolve all tenant wagers."""

    def __init__(self, user_id: str, tenant_id: str) -> None:
        super().__init__(user_id, tenant_id, game="roulette")


class PlaceCrapsBetCommand(AbstractWageringCommand):
    """Intent to place a single craps wager."""

    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        bet_type: str,
        amount: str,
    ) -> None:
        super().__init__(user_id, tenant_id, game="craps")
        self._bet_type = bet_type
        self._amount = amount

    def get_bet_type(self) -> str:
        return self._bet_type

    def get_amount(self) -> str:
        return self._amount


class RollCrapsCommand(AbstractWageringCommand):
    """Intent to roll the dice and resolve all craps wagers in a tenant."""

    def __init__(self, user_id: str, tenant_id: str) -> None:
        super().__init__(user_id, tenant_id, game="craps")


class SpinZeusCommand(AbstractWageringCommand):
    """Intent to spin the Zeus reel family for a user."""

    def __init__(self, user_id: str, tenant_id: str = "global") -> None:
        super().__init__(user_id, tenant_id, game="zeus")


class ResetWalletCommand(AbstractWageringCommand):
    """Intent to restore a wallet balance and clear active wagers."""

    def __init__(self, user_id: str, tenant_id: str = "global") -> None:
        super().__init__(user_id, tenant_id, game="wallet")