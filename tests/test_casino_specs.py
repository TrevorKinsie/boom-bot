"""Pure unit tests for the craps and roulette specification and strategy objects.

These tests verify the business-rule specifications and payout strategies
against the exact legacy winnings expectations. All monetary assertions compare
the ``Money`` results via their ``.formatted()`` representation.
"""

from __future__ import annotations

import pytest

from boombot.casino.shared.exceptions import UnknownBetTypeException
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.domain.specification.craps_specifications import (
    CrapsBetValidationStrategy,
    CrapsPayoutStrategy,
    CrapsPushStrategy,
    CrapsRollContext,
)
from boombot.casino.wagering.domain.specification.payout_strategy import (
    BetOutcomeKind,
    CrapsBetResolutionStrategy,
)
from boombot.casino.wagering.domain.specification.roulette_specifications import (
    RoulettePayoutStrategy,
    RouletteResult,
)


def _assert_money(actual: Money, expected: str) -> None:
    """Assert that a ``Money`` instance formats to the expected string."""
    assert actual.formatted() == expected


class TestCrapsPayoutStrategy:
    """Verifies the legacy craps payout winnings for a bet amount of ten."""

    def setup_method(self) -> None:
        self.strategy = CrapsPayoutStrategy()
        self.ten = Money("10")

    def test_pass_line_wins_on_come_out_seven(self) -> None:
        context = CrapsRollContext(4, 3, point=None)
        _assert_money(self.strategy.calculate("pass_line", self.ten, context), "10.00")

    def test_pass_line_wins_when_point_is_made(self) -> None:
        context = CrapsRollContext(3, 4, point=7)
        _assert_money(self.strategy.calculate("pass_line", self.ten, context), "10.00")

    def test_dont_pass_wins_on_come_out_two(self) -> None:
        context = CrapsRollContext(1, 1, point=None)
        _assert_money(self.strategy.calculate("dont_pass", self.ten, context), "10.00")

    def test_dont_pass_wins_on_seven_with_point(self) -> None:
        context = CrapsRollContext(3, 4, point=5)
        _assert_money(self.strategy.calculate("dont_pass", self.ten, context), "10.00")

    def test_field_wins_even_money_on_four(self) -> None:
        context = CrapsRollContext(2, 2, point=None)
        _assert_money(self.strategy.calculate("field", self.ten, context), "10.00")

    def test_field_pays_double_on_two(self) -> None:
        context = CrapsRollContext(1, 1, point=None)
        _assert_money(self.strategy.calculate("field", self.ten, context), "20.00")

    def test_field_pays_triple_on_twelve(self) -> None:
        context = CrapsRollContext(6, 6, point=None)
        _assert_money(self.strategy.calculate("field", self.ten, context), "30.00")

    def test_place_4_pays_nine_to_five(self) -> None:
        context = CrapsRollContext(2, 2, point=4)
        _assert_money(self.strategy.calculate("place_4", self.ten, context), "18.00")

    def test_hard_4_pays_seven_to_one(self) -> None:
        context = CrapsRollContext(2, 2, point=None)
        _assert_money(self.strategy.calculate("hard_4", self.ten, context), "70.00")

    def test_any_craps_pays_seven_to_one(self) -> None:
        context = CrapsRollContext(1, 1, point=None)
        _assert_money(self.strategy.calculate("any_craps", self.ten, context), "70.00")

    def test_any_seven_pays_four_to_one(self) -> None:
        context = CrapsRollContext(3, 4, point=None)
        _assert_money(self.strategy.calculate("any_seven", self.ten, context), "40.00")

    def test_two_pays_thirty_to_one(self) -> None:
        context = CrapsRollContext(1, 1, point=None)
        _assert_money(self.strategy.calculate("two", self.ten, context), "300.00")

    def test_three_pays_fifteen_to_one(self) -> None:
        context = CrapsRollContext(1, 2, point=None)
        _assert_money(self.strategy.calculate("three", self.ten, context), "150.00")

    def test_eleven_pays_fifteen_to_one(self) -> None:
        context = CrapsRollContext(5, 6, point=None)
        _assert_money(self.strategy.calculate("eleven", self.ten, context), "150.00")

    def test_twelve_pays_thirty_to_one(self) -> None:
        context = CrapsRollContext(6, 6, point=None)
        _assert_money(self.strategy.calculate("twelve", self.ten, context), "300.00")

    def test_losing_bet_returns_zero(self) -> None:
        context = CrapsRollContext(2, 2, point=None)
        _assert_money(self.strategy.calculate("pass_line", self.ten, context), "0.00")


class TestRoulettePayoutStrategy:
    """Verifies the standard roulette payout multiples."""

    def setup_method(self) -> None:
        self.strategy = RoulettePayoutStrategy()
        self.ten = Money("10")

    def test_straight_wins_pay_thirty_five_to_one(self) -> None:
        result = RouletteResult(7)
        winnings = self.strategy.calculate_winnings("straight", 7, self.ten, result)
        _assert_money(winnings, "350.00")

    def test_red_wins_pay_even_money(self) -> None:
        result = RouletteResult(1)
        winnings = self.strategy.calculate_winnings("red", "", self.ten, result)
        _assert_money(winnings, "10.00")

    def test_even_wins_pay_even_money(self) -> None:
        result = RouletteResult(2)
        winnings = self.strategy.calculate_winnings("even", "", self.ten, result)
        _assert_money(winnings, "10.00")

    def test_straight_miss_returns_zero(self) -> None:
        result = RouletteResult(5)
        winnings = self.strategy.calculate_winnings("straight", 7, self.ten, result)
        _assert_money(winnings, "0.00")


class TestCrapsBetValidationStrategy:
    """Verifies the craps bet type validation strategy."""

    def setup_method(self) -> None:
        self.strategy = CrapsBetValidationStrategy()

    def test_supported_bet_type_is_accepted(self) -> None:
        assert self.strategy.is_supported("pass_line") is True

    def test_unsupported_bet_type_is_rejected(self) -> None:
        with pytest.raises(UnknownBetTypeException) as exc_info:
            self.strategy.is_supported("bogus")
        assert str(exc_info.value) == "Invalid bet type: bogus"


class TestCrapsPushStrategy:
    """Verifies the don't-pass push (bar) rule."""

    def setup_method(self) -> None:
        self.strategy = CrapsPushStrategy()

    def test_dont_pass_pushes_on_twelve(self) -> None:
        context = CrapsRollContext(6, 6, point=None)
        assert self.strategy.is_push("dont_pass", context) is True

    def test_dont_pass_does_not_push_on_two(self) -> None:
        context = CrapsRollContext(1, 1, point=None)
        assert self.strategy.is_push("dont_pass", context) is False


class TestCrapsBetResolutionStrategy:
    """Verifies the resolution strategy produces the correct outcome kinds."""

    def test_win_resolution(self) -> None:
        strategy = CrapsBetResolutionStrategy("pass_line", Money("10"))
        resolution = strategy.resolve(CrapsRollContext(4, 3, point=None))
        assert resolution.get_kind() is BetOutcomeKind.WIN
        _assert_money(resolution.get_winnings(), "10.00")

    def test_loss_resolution(self) -> None:
        strategy = CrapsBetResolutionStrategy("pass_line", Money("10"))
        resolution = strategy.resolve(CrapsRollContext(2, 2, point=None))
        assert resolution.get_kind() is BetOutcomeKind.LOSS
        _assert_money(resolution.get_winnings(), "0.00")

    def test_push_resolution(self) -> None:
        strategy = CrapsBetResolutionStrategy("dont_pass", Money("10"))
        resolution = strategy.resolve(CrapsRollContext(6, 6, point=None))
        assert resolution.get_kind() is BetOutcomeKind.PUSH
        _assert_money(resolution.get_winnings(), "0.00")