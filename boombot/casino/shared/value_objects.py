"""
Immutable Value Objects.

Value objects are the fundamental building blocks of the casino domain model.
They are immutable, compare by structural equality, and encapsulate all
validation rules associated with the concept they represent (for example, a
monetary amount may never be negative).

This module is dependency-free and framework-free by design.
"""

from __future__ import annotations

from abc import ABC
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from boombot.core.config import CASINO_CURRENCY_QUANTIZATION
from boombot.casino.shared.exceptions import NegativeMonetaryAmountException


class AbstractValueObject(ABC):
    """Base class for all immutable domain value objects.

    Provides structural equality, hashing, and a stable representation for
    subclasses. Subclasses must define all their state in ``__init__`` and
    must never expose mutating operations.
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._equality_components() == other._equality_components()

    def __hash__(self) -> int:
        return hash(self._equality_components())

    def _equality_components(self) -> tuple[Any, ...]:
        """Return the tuple of fields that define structural equality."""
        return tuple(self.__dict__.values())

    def __repr__(self) -> str:
        fields = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{self.__class__.__name__}({fields})"


class Money(AbstractValueObject):
    """An immutable, validated monetary amount.

    All money within the casino platform is represented as a ``Money`` value
    object backed by :class:`decimal.Decimal` to guarantee exact decimal
    arithmetic without floating point error. Amounts are quantized to the
    configured currency scale (cents by default) using banker's rounding.

    A negative monetary amount is a domain invariant violation and raises
    :class:`NegativeMonetaryAmountException`.
    """

    __slots__ = ("_amount",)

    def __init__(self, amount: Decimal | str | int | float) -> None:
        try:
            normalized = Decimal(str(amount))
        except (InvalidOperation, ValueError) as exc:
            raise NegativeMonetaryAmountException(
                f"Cannot construct Money from invalid value: {amount!r}"
            ) from exc
        if normalized.is_nan():
            raise NegativeMonetaryAmountException(
                f"Cannot construct Money from NaN value: {amount!r}"
            )
        scale = Decimal(CASINO_CURRENCY_QUANTIZATION)
        self._amount = normalized.quantize(scale, rounding=ROUND_HALF_UP)
        if self._amount < Decimal("0"):
            raise NegativeMonetaryAmountException(
                f"Cannot construct Money from negative value: {amount!r}"
            )

    @classmethod
    def zero(cls) -> "Money":
        """Return a canonical zero-valued ``Money`` instance."""
        return cls(Decimal("0"))

    def amount(self) -> Decimal:
        """Return the underlying :class:`decimal.Decimal` amount."""
        return self._amount

    def is_zero(self) -> bool:
        return self._amount == Decimal("0")

    def is_positive(self) -> bool:
        return self._amount > Decimal("0")

    def is_greater_than_or_equal_to(self, other: "Money") -> bool:
        return self._amount >= other._amount

    def is_less_than(self, other: "Money") -> bool:
        return self._amount < other._amount

    def is_greater_than(self, other: "Money") -> bool:
        return self._amount > other._amount

    def add(self, other: "Money") -> "Money":
        """Return a new ``Money`` equal to the sum of this and ``other``."""
        return Money(self._amount + other._amount)

    def subtract(self, other: "Money") -> "Money":
        """Return a new ``Money`` equal to this minus ``other``.

        Raises :class:`NegativeMonetaryAmountException` if the result would be
        negative, preserving the non-negative money invariant.
        """
        return Money(self._amount - other._amount)

    def multiply(self, multiplier: Decimal | str | int | float) -> "Money":
        """Return a new ``Money`` equal to this scaled by ``multiplier``."""
        return Money(self._amount * Decimal(str(multiplier)))

    def compare_to(self, other: "Money") -> int:
        """Java-style comparator: negative, zero, or positive ordering."""
        if self._amount < other._amount:
            return -1
        if self._amount > other._amount:
            return 1
        return 0

    def formatted(self) -> str:
        """Return the amount formatted as a currency string (e.g. ``100.00``)."""
        return f"{self._amount:.2f}"

    def to_decimal_string(self) -> str:
        """Return a stable string representation suitable for persistence."""
        return str(self._amount)

    def _equality_components(self) -> tuple[Any, ...]:
        return (self._amount,)


class AggregateVersion(AbstractValueObject):
    """An optimistic-locking version token for event-sourced aggregates.

    Each aggregate instance carries a monotonically increasing version that is
    incremented with every applied domain event. The version guards against
    conflicting concurrent writes within the same process.
    """

    __slots__ = ("_number",)

    def __init__(self, number: int = 0) -> None:
        if number < 0:
            raise ValueError("AggregateVersion must be non-negative.")
        self._number = int(number)

    def number(self) -> int:
        return self._number

    def next(self) -> "AggregateVersion":
        return AggregateVersion(self._number + 1)

    def _equality_components(self) -> tuple[Any, ...]:
        return (self._number,)
