"""
Bet Resolution Value Objects and Strategies.

This module defines the outcome taxonomy for a resolved wager, the immutable
:class:`BetResolution` value object, and the strategy hierarchy responsible for
translating a roll context into a concrete bet resolution. The craps resolution
strategy composes the payout and push strategies defined in the specifications
package to produce a win, loss, or push outcome for any supported bet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional

from boombot.casino.shared.value_objects import AbstractValueObject, Money
from boombot.casino.wagering.domain.specification.craps_specifications import (
    CrapsPayoutStrategy,
    CrapsPushStrategy,
    CrapsRollContext,
)


class BetOutcomeKind(Enum):
    """The enumerated taxonomy of possible bet resolutions."""

    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"


class BetResolution(AbstractValueObject):
    """Immutable value object describing the outcome of a single wager.

    A bet resolution captures the staked amount, the outcome kind, and the
    winnings awarded (which is zero for both losses and pushes).
    """

    def __init__(
        self,
        bet_type: str,
        bet_amount: Money,
        kind: BetOutcomeKind,
        winnings: Money,
    ) -> None:
        """Initialize a bet resolution.

        :param bet_type: The identifier of the wagered bet type.
        :param bet_amount: The monetary amount staked on the wager.
        :param kind: The outcome kind of the resolution.
        :param winnings: The winnings awarded (exclusive of the original bet).
        """
        self._bet_type = bet_type
        self._bet_amount = bet_amount
        self._kind = kind
        self._winnings = winnings

    def get_bet_type(self) -> str:
        """Return the identifier of the wagered bet type."""
        return self._bet_type

    def get_bet_amount(self) -> Money:
        """Return the monetary amount staked on the wager."""
        return self._bet_amount

    def get_kind(self) -> BetOutcomeKind:
        """Return the outcome kind of the resolution."""
        return self._kind

    def get_winnings(self) -> Money:
        """Return the winnings awarded by this resolution."""
        return self._winnings

    def to_display_string(self) -> str:
        """Return a human-readable summary suitable for presentation.

        :return: A string describing the bet type, outcome, and winnings.
        """
        return (
            f"{self._bet_type} ({self._kind.value}): "
            f"winnings {self._winnings.formatted()}"
        )

    def _equality_components(self) -> tuple[Any, ...]:
        return (self._bet_type, self._bet_amount, self._kind, self._winnings)


class AbstractBetResolutionStrategy(ABC):
    """Abstract template for bet resolution strategies.

    Concrete resolution strategies translate a game context into a
    :class:`BetResolution` and expose the payout strategies they compose.
    """

    @abstractmethod
    def resolve(self, context: Any) -> BetResolution:
        """Produce a :class:`BetResolution` for the supplied game context."""
        raise NotImplementedError

    @abstractmethod
    def payouts(self) -> List[Any]:
        """Return the payout strategies composed by this resolution strategy."""
        raise NotImplementedError


class BetResolutionFactory:
    """Factory for constructing :class:`BetResolution` instances.

    Each factory method captures a single outcome kind and centralises the
    construction of well-formed resolution value objects.
    """

    @staticmethod
    def create_win(bet_type: str, bet_amount: Money, winnings: Money) -> BetResolution:
        """Create a winning bet resolution."""
        return BetResolution(bet_type, bet_amount, BetOutcomeKind.WIN, winnings)

    @staticmethod
    def create_loss(bet_type: str, bet_amount: Money) -> BetResolution:
        """Create a losing bet resolution with zero winnings."""
        return BetResolution(bet_type, bet_amount, BetOutcomeKind.LOSS, Money.zero())

    @staticmethod
    def create_push(bet_type: str, bet_amount: Money) -> BetResolution:
        """Create a pushed bet resolution with zero winnings."""
        return BetResolution(bet_type, bet_amount, BetOutcomeKind.PUSH, Money.zero())


class CrapsBetResolutionStrategy(AbstractBetResolutionStrategy):
    """Concrete resolution strategy for craps wagers.

    The strategy composes a :class:`CrapsPayoutStrategy` and a
    :class:`CrapsPushStrategy` to classify a roll context as a win, a loss, or a
    push for the configured bet.
    """

    def __init__(
        self,
        bet_type: str,
        bet_amount: Money,
        payout_strategy: Optional[CrapsPayoutStrategy] = None,
        push_strategy: Optional[CrapsPushStrategy] = None,
    ) -> None:
        """Initialize a craps resolution strategy.

        :param bet_type: The identifier of the wagered bet type.
        :param bet_amount: The monetary amount staked on the wager.
        :param payout_strategy: The payout strategy to use; a default instance
            is created when omitted.
        :param push_strategy: The push strategy to use; a default instance is
            created when omitted.
        """
        self._bet_type = bet_type
        self._bet_amount = bet_amount
        self._payout_strategy = payout_strategy or CrapsPayoutStrategy()
        self._push_strategy = push_strategy or CrapsPushStrategy()

    def resolve(self, context: CrapsRollContext) -> BetResolution:
        """Produce the :class:`BetResolution` for the supplied roll context.

        :param context: The observable state of the current craps roll.
        :return: The resolved bet outcome for the configured wager.
        """
        if self._push_strategy.is_push(self._bet_type, context):
            return BetResolutionFactory.create_push(self._bet_type, self._bet_amount)

        winnings = self._payout_strategy.calculate(
            self._bet_type, self._bet_amount, context
        )
        if winnings.is_zero():
            return BetResolutionFactory.create_loss(self._bet_type, self._bet_amount)
        return BetResolutionFactory.create_win(
            self._bet_type, self._bet_amount, winnings
        )

    def payouts(self) -> List[Any]:
        """Return the composed payout and push strategies."""
        return [self._payout_strategy, self._push_strategy]