"""
Roulette Business-Rule Specifications and Payout Strategy.

This module encapsulates the domain rules governing the game of Roulette as
discrete, composable specification objects and a payout strategy object. Each
business rule is expressed as a predicate over a :class:`RouletteResult` so that
the rule set may be unit-tested in isolation and reused by the resolution layer.

All monetary computation is performed with the shared ``Money`` value object and
exact :class:`decimal.Decimal` arithmetic. The payout multipliers reflect the
standard American roulette schedule as implemented by the legacy system.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Union

from boombot.casino.shared.patterns import AbstractSpecification
from boombot.casino.shared.value_objects import Money


#: The canonical set of red pockets on an American roulette wheel.
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]


class RouletteResult:
    """Immutable value object describing the outcome of a single roulette spin.

    The pocket is represented as an integer for all numbered pockets or as the
    string ``"00"`` for the double-zero pocket.
    """

    def __init__(self, number: Union[int, str]) -> None:
        """Initialize a roulette result.

        :param number: The winning pocket, expressed as an ``int`` for numbered
            pockets or the string ``"00"`` for double-zero.
        """
        self._number = number

    def get_number(self) -> Union[int, str]:
        """Return the winning pocket of this roulette result."""
        return self._number

    def __repr__(self) -> str:
        return f"RouletteResult(number={self._number!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouletteResult):
            return NotImplemented
        return self._number == other._number

    def __hash__(self) -> int:
        return hash(self._number)


class RouletteBetType(Enum):
    """The enumeration of supported roulette bet types."""

    STRAIGHT = "straight"
    SPLIT = "split"
    STREET = "street"
    CORNER = "corner"
    FIVE = "five"
    LINE = "line"
    COLUMN = "column"
    DOZEN = "dozen"
    RED = "red"
    BLACK = "black"
    EVEN = "even"
    ODD = "odd"
    LOW = "low"
    HIGH = "high"


class RouletteColorSpecification(AbstractSpecification):
    """Business rule that determines when a color bet wins.

    The zero pockets (``0`` and ``"00"``) are green; the numbers enumerated in
    :data:`RED_NUMBERS` are red; all remaining numbered pockets are black.
    """

    _GREEN_POCKETS = frozenset({0, "00"})

    def __init__(self, target_color: str) -> None:
        """Initialize with the target color.

        :param target_color: One of ``"red"``, ``"black"``, or ``"green"``.
        """
        self._target_color = target_color

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, RouletteResult):
            return False
        number = candidate.get_number()
        return self._resolve_color(number) == self._target_color

    @classmethod
    def _resolve_color(cls, number: Union[int, str]) -> str:
        """Resolve the color of a pocket."""
        if number in cls._GREEN_POCKETS:
            return "green"
        if number in RED_NUMBERS:
            return "red"
        return "black"


class RouletteParitySpecification(AbstractSpecification):
    """Business rule that determines when an even or odd bet wins.

    The zero pockets (``0`` and ``"00"``) are neither even nor odd and therefore
    never satisfy either parity predicate.
    """

    def __init__(self, target_parity: str) -> None:
        """Initialize with the target parity.

        :param target_parity: One of ``"even"`` or ``"odd"``.
        """
        self._target_parity = target_parity

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, RouletteResult):
            return False
        number = candidate.get_number()
        if not isinstance(number, int):
            return False
        if self._target_parity == "even":
            return number != 0 and number % 2 == 0
        if self._target_parity == "odd":
            return number % 2 != 0
        return False


class RouletteRangeSpecification(AbstractSpecification):
    """Business rule that determines when a range-based bet wins.

    Supports the low (1-18), high (19-36), and each of the three dozen ranges.
    """

    _RANGES = {
        "low": range(1, 19),
        "high": range(19, 37),
        "first_dozen": range(1, 13),
        "second_dozen": range(13, 25),
        "third_dozen": range(25, 37),
    }

    def __init__(self, target_range: str) -> None:
        """Initialize with the target range identifier."""
        self._target_range = target_range

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, RouletteResult):
            return False
        number = candidate.get_number()
        if not isinstance(number, int):
            return False
        bounded_range = self._RANGES.get(self._target_range)
        if bounded_range is None:
            return False
        return number in bounded_range


class RouletteStraightNumberSpecification(AbstractSpecification):
    """Business rule that determines when a straight number bet wins.

    The wager is satisfied only when the result pocket exactly equals the target
    number.
    """

    def __init__(self, target_number: Union[int, str]) -> None:
        """Initialize with the target pocket.

        :param target_number: The wagered pocket as an ``int`` or ``"00"``.
        """
        self._target_number = target_number

    def is_satisfied_by(self, candidate: Any) -> bool:
        if not isinstance(candidate, RouletteResult):
            return False
        return candidate.get_number() == self._target_number


class RoulettePayoutMultiplier(Enum):
    """Standard payouts for the supported roulette bet types.

    Values are expressed as even-money style multiplier strings (for example a
    straight bet pays ``35`` times the wager).
    """

    STRAIGHT = "35"
    SPLIT = "17"
    STREET = "11"
    CORNER = "8"
    FIVE = "6"
    LINE = "5"
    COLUMN = "2"
    DOZEN = "2"
    EVEN_MONEY = "1"

    def resolve_to_decimal(self) -> Decimal:
        """Return this multiplier as an exact :class:`decimal.Decimal`."""
        return Decimal(self.value)


class RoulettePayoutStrategy:
    """Concrete payout strategy implementing the standard roulette payout rules.

    The strategy resolves the applicable multiplier for any supported bet type
    and determines, for straight and even-money wagers, whether a given result
    constitutes a win. Winnings are computed as ``bet_amount * multiplier`` and
    ``Money.zero()`` is returned for a losing wager.
    """

    _MULTIPLIER_BY_BET_TYPE = {
        RouletteBetType.STRAIGHT: RoulettePayoutMultiplier.STRAIGHT,
        RouletteBetType.SPLIT: RoulettePayoutMultiplier.SPLIT,
        RouletteBetType.STREET: RoulettePayoutMultiplier.STREET,
        RouletteBetType.CORNER: RoulettePayoutMultiplier.CORNER,
        RouletteBetType.FIVE: RoulettePayoutMultiplier.FIVE,
        RouletteBetType.LINE: RoulettePayoutMultiplier.LINE,
        RouletteBetType.COLUMN: RoulettePayoutMultiplier.COLUMN,
        RouletteBetType.DOZEN: RoulettePayoutMultiplier.DOZEN,
        RouletteBetType.RED: RoulettePayoutMultiplier.EVEN_MONEY,
        RouletteBetType.BLACK: RoulettePayoutMultiplier.EVEN_MONEY,
        RouletteBetType.EVEN: RoulettePayoutMultiplier.EVEN_MONEY,
        RouletteBetType.ODD: RoulettePayoutMultiplier.EVEN_MONEY,
        RouletteBetType.LOW: RoulettePayoutMultiplier.EVEN_MONEY,
        RouletteBetType.HIGH: RoulettePayoutMultiplier.EVEN_MONEY,
    }

    def multiplier_for(self, bet_type: str) -> Decimal:
        """Return the payout multiplier for ``bet_type``.

        :param bet_type: The identifier of the wagered bet type.
        :return: The applicable multiplier as a :class:`decimal.Decimal`.
        """
        resolved = RouletteBetType(bet_type)
        multiplier = self._MULTIPLIER_BY_BET_TYPE[resolved]
        return multiplier.resolve_to_decimal()

    def determines_win(
        self,
        bet_type: str,
        bet_value: Union[int, str, None],
        result: RouletteResult,
    ) -> bool:
        """Determine whether ``result`` constitutes a win for ``bet_type``.

        :param bet_type: The identifier of the wagered bet type.
        :param bet_value: The specific pocket for a straight wager (an ``int``
            or the string ``"00"``), or ``None`` for even-money wagers.
        :param result: The outcome of the roulette spin.
        :return: ``True`` when the wager wins, otherwise ``False``.
        """
        resolved = RouletteBetType(bet_type)

        if resolved is RouletteBetType.STRAIGHT:
            return RouletteStraightNumberSpecification(bet_value).is_satisfied_by(result)
        if resolved is RouletteBetType.RED:
            return RouletteColorSpecification("red").is_satisfied_by(result)
        if resolved is RouletteBetType.BLACK:
            return RouletteColorSpecification("black").is_satisfied_by(result)
        if resolved is RouletteBetType.EVEN:
            return RouletteParitySpecification("even").is_satisfied_by(result)
        if resolved is RouletteBetType.ODD:
            return RouletteParitySpecification("odd").is_satisfied_by(result)
        if resolved is RouletteBetType.LOW:
            return RouletteRangeSpecification("low").is_satisfied_by(result)
        if resolved is RouletteBetType.HIGH:
            return RouletteRangeSpecification("high").is_satisfied_by(result)
        return self._determines_structured_win(resolved, bet_value, result)

    def calculate_winnings(
        self,
        bet_type: str,
        bet_value: Union[int, str, None],
        bet_amount: Money,
        result: RouletteResult,
    ) -> Money:
        """Return the winnings for ``bet_amount`` or ``Money.zero()`` on a loss.

        :param bet_type: The identifier of the wagered bet type.
        :param bet_value: The specific pocket for relevant bets, or ``None``.
        :param bet_amount: The monetary amount staked on the wager.
        :param result: The outcome of the roulette spin.
        :return: The winnings (exclusive of the original bet) or zero.
        """
        if not self.determines_win(bet_type, bet_value, result):
            return Money.zero()
        multiplier = self.multiplier_for(bet_type)
        return bet_amount.multiply(multiplier)

    def _determines_structured_win(
        self,
        bet_type: RouletteBetType,
        bet_value: Union[int, str, None],
        result: RouletteResult,
    ) -> bool:
        """Evaluate structured bets (split, street, corner, line, column, dozen).

        These wagers require a positional collection of covered pockets encoded
        by ``bet_value``; when such information is absent the wager is treated
        as unresolved and does not win.
        """
        if bet_value is None or bet_value == "":
            return False
        if isinstance(bet_value, str):
            return False
        covered_numbers = bet_value
        if not isinstance(covered_numbers, (list, tuple, set)):
            return False
        return result.get_number() in covered_numbers