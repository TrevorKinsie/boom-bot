"""
Craps Business-Rule Specifications and Payout Strategies.

This module encapsulates the domain rules governing the game of Craps as
discrete, composable specification objects and payout strategy objects. Every
business rule is expressed as a predicate over a :class:`CrapsRollContext` so
that the rule set may be unit-tested in isolation, combined with the composite
operators supplied by :class:`boombot.casino.shared.patterns.AbstractSpecification`,
and reused by the resolution layer.

The ``Money`` value object is sourced from the shared casino kernel and is used
exclusively for all monetary computation. All fractional multipliers are
evaluated with :class:`decimal.Decimal` arithmetic and quantized to the currency
scale using ``ROUND_HALF_UP`` in strict accordance with the legacy payout rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from boombot.casino.shared.patterns import AbstractSpecification
from boombot.casino.shared.value_objects import Money
from boombot.casino.shared.exceptions import UnknownBetTypeException


class CrapsRollContext:
    """Immutable value object describing the observable state of a single craps roll.

    A craps roll is fully characterized by the two dice values and the active
    point (``None`` during the come-out phase). This value object is the
    candidate submitted to every craps specification predicate.
    """

    def __init__(self, die1: int, die2: int, point: Optional[int] = None) -> None:
        """Initialize a craps roll context.

        :param die1: The value displayed on the first die.
        :param die2: The value displayed on the second die.
        :param point: The established point during the point phase, or ``None``
            during the come-out phase.
        """
        self._die1 = int(die1)
        self._die2 = int(die2)
        self._point = None if point is None else int(point)

    def get_die1(self) -> int:
        """Return the value of the first die."""
        return self._die1

    def get_die2(self) -> int:
        """Return the value of the second die."""
        return self._die2

    def get_point(self) -> Optional[int]:
        """Return the active point, or ``None`` during the come-out phase."""
        return self._point

    def get_roll_sum(self) -> int:
        """Return the arithmetic sum of the two dice values."""
        return self._die1 + self._die2

    def __repr__(self) -> str:
        return (
            f"CrapsRollContext(die1={self._die1!r}, die2={self._die2!r}, "
            f"point={self._point!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CrapsRollContext):
            return NotImplemented
        return (
            self._die1 == other._die1
            and self._die2 == other._die2
            and self._point == other._point
        )

    def __hash__(self) -> int:
        return hash((self._die1, self._die2, self._point))


class PassLineWinSpecification(AbstractSpecification):
    """Business rule that determines when a Pass Line bet wins.

    A Pass Line wager wins when the come-out roll totals seven or eleven, or —
    once a point is established — when the roll equals the established point.
    """

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, CrapsRollContext):
            return False
        roll_sum = candidate.get_roll_sum()
        point = candidate.get_point()
        if point is None:
            return roll_sum in (7, 11)
        return roll_sum == point


class PassLineLoseSpecification(AbstractSpecification):
    """Business rule that determines when a Pass Line bet loses.

    A Pass Line wager loses when the come-out roll totals two, three, or twelve,
    or — once a point is established — when the roll totals seven.
    """

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, CrapsRollContext):
            return False
        roll_sum = candidate.get_roll_sum()
        point = candidate.get_point()
        if point is None:
            return roll_sum in (2, 3, 12)
        return roll_sum == 7


class DontPassWinSpecification(AbstractSpecification):
    """Business rule that determines when a Don't Pass bet wins.

    A Don't Pass wager wins when the come-out roll totals two or three, or —
    once a point is established — when the roll totals seven. The come-out
    twelve is neither a win nor a loss and is handled by the push rule.
    """

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, CrapsRollContext):
            return False
        roll_sum = candidate.get_roll_sum()
        point = candidate.get_point()
        if point is None:
            return roll_sum in (2, 3)
        return roll_sum == 7


class DontPassPushSpecification(AbstractSpecification):
    """Business rule that identifies a Don't Pass push (bar).

    A Don't Pass wager pushes (ties) when the come-out roll totals twelve.
    """

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, CrapsRollContext):
            return False
        return candidate.get_point() is None and candidate.get_roll_sum() == 12


class FieldWinSpecification(AbstractSpecification):
    """Business rule that determines when a Field bet wins.

    A Field wager wins whenever the roll totals two, three, four, nine, ten,
    eleven, or twelve. The two pays double and the twelve pays triple.
    """

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, CrapsRollContext):
            return False
        return candidate.get_roll_sum() in (2, 3, 4, 9, 10, 11, 12)


class CrapsPayoutMultiplier(Enum):
    """Named payout multipliers for the supported craps wagers.

    Values are expressed as strings that may represent either a whole-number
    multiplier or a fractional ratio (for example ``"9/5"``) that is resolved
    to a :class:`decimal.Decimal` at the point of use.
    """

    PASS_LINE = "1"
    DONT_PASS = "1"
    FIELD = "1"
    FIELD_2 = "2"
    FIELD_12 = "3"
    PLACE_4 = "9/5"
    PLACE_5 = "7/5"
    PLACE_6 = "7/6"
    PLACE_8 = "7/6"
    PLACE_9 = "7/5"
    PLACE_10 = "9/5"
    HARD_4 = "7"
    HARD_6 = "9"
    HARD_8 = "9"
    HARD_10 = "7"
    ANY_CRAPS = "7"
    ANY_SEVEN = "4"
    TWO = "30"
    THREE = "15"
    ELEVEN = "15"
    TWELVE = "30"
    HORN = "30"

    def resolve_to_decimal(self) -> Decimal:
        """Resolve this multiplier to an exact :class:`decimal.Decimal` value.

        Fractional ratios encoded as ``numerator/denominator`` are evaluated
        with exact decimal division.
        """
        raw = self.value
        if "/" in raw:
            numerator, denominator = raw.split("/", maxsplit=1)
            return Decimal(numerator) / Decimal(denominator)
        return Decimal(raw)


class AbstractPayoutStrategy(ABC):
    """Abstract template for craps payout calculation strategies.

    Concrete strategies implement the winning-predicate and the monetary
    computation, returning the winnings only (never the original stake).
    """

    @abstractmethod
    def calculate(self, bet_type: str, bet_amount: Money, context: CrapsRollContext) -> Money:
        """Return the winnings for ``bet_amount``, or ``Money.zero()`` on a loss.

        :param bet_type: The identifier of the wagered bet type.
        :param bet_amount: The monetary amount staked on the wager.
        :param context: The observable state of the current craps roll.
        :return: The winnings (exclusive of the original bet) or zero.
        """
        raise NotImplementedError

    @abstractmethod
    def is_winning(self, bet_type: str, context: CrapsRollContext) -> bool:
        """Return whether the given bet type wins for the roll context."""
        raise NotImplementedError

    def is_not_winning(self, bet_type: str, context: CrapsRollContext) -> bool:
        """Return whether the given bet type does not win for the roll context."""
        return not self.is_winning(bet_type, context)



class CrapsPayoutStrategy(AbstractPayoutStrategy):
    """Concrete payout strategy implementing the legacy craps payout rules.

    For every supported bet type the strategy first determines whether the wager
    wins for the supplied roll context and, if so, returns the winnings computed
    as ``bet_amount * multiplier`` using exact decimal arithmetic. When the
    wager does not win, ``Money.zero()`` is returned.
    """

    _HARD_NUMBERS = {4, 6, 8, 10}
    _PLACE_NUMBERS = {4, 5, 6, 8, 9, 10}
    _ONE_ROLL_HORN_NUMBERS = {2, 3, 11, 12}

    _PLACE_MULTIPLIER_BY_NUMBER = {
        4: CrapsPayoutMultiplier.PLACE_4,
        5: CrapsPayoutMultiplier.PLACE_5,
        6: CrapsPayoutMultiplier.PLACE_6,
        8: CrapsPayoutMultiplier.PLACE_8,
        9: CrapsPayoutMultiplier.PLACE_9,
        10: CrapsPayoutMultiplier.PLACE_10,
    }

    _HARD_MULTIPLIER_BY_NUMBER = {
        4: CrapsPayoutMultiplier.HARD_4,
        6: CrapsPayoutMultiplier.HARD_6,
        8: CrapsPayoutMultiplier.HARD_8,
        10: CrapsPayoutMultiplier.HARD_10,
    }

    def is_winning(self, bet_type: str, context: CrapsRollContext) -> bool:
        """Determine whether ``bet_type`` wins for the supplied roll context."""
        roll_sum = context.get_roll_sum()
        point = context.get_point()

        if bet_type == "pass_line":
            return PassLineWinSpecification().is_satisfied_by(context)
        if bet_type == "dont_pass":
            return DontPassWinSpecification().is_satisfied_by(context)
        if bet_type == "field":
            return FieldWinSpecification().is_satisfied_by(context)
        if bet_type.startswith("place_"):
            number = self._number_suffix(bet_type)
            if number not in self._PLACE_NUMBERS:
                return False
            return point is not None and roll_sum == number
        if bet_type.startswith("hard_"):
            number = self._number_suffix(bet_type)
            if number not in self._HARD_NUMBERS:
                return False
            return roll_sum == number and context.get_die1() == context.get_die2()
        if bet_type == "any_craps":
            return roll_sum in (2, 3, 12)
        if bet_type == "any_seven":
            return roll_sum == 7
        if bet_type == "two":
            return roll_sum == 2
        if bet_type == "three":
            return roll_sum == 3
        if bet_type == "eleven":
            return roll_sum == 11
        if bet_type == "twelve":
            return roll_sum == 12
        if bet_type == "horn":
            return roll_sum in self._ONE_ROLL_HORN_NUMBERS
        return False

    def calculate(self, bet_type: str, bet_amount: Money, context: CrapsRollContext) -> Money:
        """Return winnings for ``bet_amount`` or ``Money.zero()`` on a loss."""
        if not self.is_winning(bet_type, context):
            return Money.zero()
        multiplier = self._payout_multiplier_for(bet_type, context)
        return bet_amount.multiply(multiplier.resolve_to_decimal())



    def _payout_multiplier_for(
        self, bet_type: str, context: CrapsRollContext
    ) -> CrapsPayoutMultiplier:
        """Resolve the applicable multiplier for a winning bet type."""
        roll_sum = context.get_roll_sum()

        if bet_type == "pass_line":
            return CrapsPayoutMultiplier.PASS_LINE
        if bet_type == "dont_pass":
            return CrapsPayoutMultiplier.DONT_PASS
        if bet_type == "field":
            if roll_sum == 2:
                return CrapsPayoutMultiplier.FIELD_2
            if roll_sum == 12:
                return CrapsPayoutMultiplier.FIELD_12
            return CrapsPayoutMultiplier.FIELD
        if bet_type.startswith("place_"):
            number = self._number_suffix(bet_type)
            return self._PLACE_MULTIPLIER_BY_NUMBER[number]
        if bet_type.startswith("hard_"):
            number = self._number_suffix(bet_type)
            return self._HARD_MULTIPLIER_BY_NUMBER[number]
        if bet_type == "any_craps":
            return CrapsPayoutMultiplier.ANY_CRAPS
        if bet_type == "any_seven":
            return CrapsPayoutMultiplier.ANY_SEVEN
        if bet_type == "two":
            return CrapsPayoutMultiplier.TWO
        if bet_type == "three":
            return CrapsPayoutMultiplier.THREE
        if bet_type == "eleven":
            return CrapsPayoutMultiplier.ELEVEN
        if bet_type == "twelve":
            return CrapsPayoutMultiplier.TWELVE
        if bet_type == "horn":
            return CrapsPayoutMultiplier.HORN
        raise ValueError(f"No payout multiplier registered for bet type: {bet_type}")

    @staticmethod
    def _number_suffix(bet_type: str) -> int:
        """Extract the numeric suffix from a ``place_N`` / ``hard_N`` bet type."""
        return int(bet_type.split("_", maxsplit=1)[1])


class CrapsPushStrategy:
    """Strategy that identifies craps wagers which resolve as a push (tie).

    At present only the Don't Pass bar (twelve on the come-out) resolves as a
    push; the wager is returned in full and no winnings are awarded.
    """

    def is_push(self, bet_type: str, context: CrapsRollContext) -> bool:
        """Return whether ``bet_type`` resolves as a push for the roll context."""
        if bet_type != "dont_pass":
            return False
        return DontPassPushSpecification().is_satisfied_by(context)

class CrapsBetValidationStrategy:
    """Strategy that validates the set of supported craps bet identifiers.

    An unsupported bet type is rejected by raising
    :class:`UnknownBetTypeException` with a descriptive message.
    """

    SUPPORTED_BET_TYPES = frozenset(
        {
            "pass_line",
            "dont_pass",
            "field",
            "place_4",
            "place_5",
            "place_6",
            "place_8",
            "place_9",
            "place_10",
            "hard_4",
            "hard_6",
            "hard_8",
            "hard_10",
            "any_craps",
            "any_seven",
            "two",
            "three",
            "eleven",
            "twelve",
            "horn",
        }
    )

    def is_supported(self, bet_type: str) -> bool:
        """Return whether ``bet_type`` is supported.

        Raises :class:`UnknownBetTypeException` when the supplied identifier is
        not a member of the supported bet type set.
        """
        if bet_type not in self.SUPPORTED_BET_TYPES:
            raise UnknownBetTypeException(f"Invalid bet type: {bet_type}")
        return True

    def validate(self, bet_type: str) -> None:
        """Validate that ``bet_type`` is supported, raising otherwise."""
        self.is_supported(bet_type)