"""
Value Object Tests.

Validates the invariants and arithmetic of the shared monetary value objects.
"""

import pytest
from decimal import Decimal

from boombot.casino.shared.value_objects import Money, AggregateVersion
from boombot.casino.shared.exceptions import NegativeMonetaryAmountException


class TestMoney:
    def test_constructs_and_quantizes(self):
        # Half-up rounding to cents: 10.005 -> 10.01.
        money = Money("10.005")
        assert money.amount() == Decimal("10.01")
        assert money.formatted() == "10.01"
        assert Money("10").amount() == Decimal("10.00")

    def test_rejects_negative_amounts(self):
        with pytest.raises(NegativeMonetaryAmountException):
            Money("-1")

    def test_rejects_non_numeric(self):
        with pytest.raises(NegativeMonetaryAmountException):
            Money("not-a-number")

    def test_zero(self):
        assert Money.zero().is_zero()

    def test_addition(self):
        assert Money("10").add(Money("5")).formatted() == "15.00"

    def test_subtraction(self):
        assert Money("10").subtract(Money("4")).formatted() == "6.00"

    def test_subtraction_rejects_negative_result(self):
        with pytest.raises(NegativeMonetaryAmountException):
            Money("4").subtract(Money("10"))

    def test_multiplication(self):
        assert Money("10").multiply(Decimal("3")).formatted() == "30.00"

    def test_comparisons(self):
        assert Money("5").is_less_than(Money("6"))
        assert Money("7").is_greater_than(Money("6"))
        assert Money("6").is_greater_than_or_equal_to(Money("6"))
        assert Money("5").compare_to(Money("6")) == -1
        assert Money("7").compare_to(Money("6")) == 1

    def test_structural_equality(self):
        assert Money("10") == Money("10.00")
        assert Money("10") != Money("11")
        assert hash(Money("10")) == hash(Money("10.00"))


class TestAggregateVersion:
    def test_initial_zero(self):
        assert AggregateVersion().number() == 0

    def test_next_increments(self):
        assert AggregateVersion(3).next().number() == 4

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            AggregateVersion(-1)