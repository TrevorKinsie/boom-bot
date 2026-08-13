"""
Tests for the Zeus 5x5 reel-slot domain model.

This suite exercises the pure domain logic of the Zeus reel-slot family:
random grid generation, grid dimension validation, jackpot evaluation, the
five-of-a-kind payout path, the Wild-substitution rule of the line
evaluation strategy, and the losing line rule for mixed high symbols.

All assertions on monetary amounts use the ``amount()`` accessor of the
:class:`Money` value object, which returns a :class:`decimal.Decimal`, so the
tests avoid any dependence on formatting concerns.
"""

from boombot.casino.shared.value_objects import Money
from boombot.casino.zeus.domain.reel import (
    DEFAULT_GRID_COLS,
    DEFAULT_GRID_ROWS,
    ZEUS_SYMBOL,
    ZEUS_SYMBOLS,
    GridWinEvaluator,
    LineEvaluationStrategy,
    LineType,
    PayoutCalculator,
    PayoutTable,
    RandomGridFactory,
    ReelGrid,
)


def test_random_grid_factory_generates_valid_grid():
    """A randomly generated grid has the declared dimensions and valid cells."""
    factory = RandomGridFactory()
    grid = factory.generate(DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS)

    assert grid.get_rows() == 5
    assert grid.get_cols() == 5

    for row in range(grid.get_rows()):
        for col in range(grid.get_cols()):
            assert grid.get_symbol(row, col) in ZEUS_SYMBOLS


def test_grid_dimension_mismatch_is_rejected():
    """A grid whose data does not match the declared dimensions is rejected."""
    mismatched_data = [
        [ZEUS_SYMBOL, ZEUS_SYMBOL, ZEUS_SYMBOL],
        [ZEUS_SYMBOL, ZEUS_SYMBOL, ZEUS_SYMBOL],
    ]

    try:
        ReelGrid(rows=2, cols=4, grid_data=mismatched_data)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for mismatched grid dimensions.")


def test_fully_zeus_grid_evaluates_to_jackpot():
    """A grid of all-Zeus symbols yields a jackpot worth 5000 coins."""
    grid_data = [[ZEUS_SYMBOL for _ in range(DEFAULT_GRID_COLS)] for _ in range(DEFAULT_GRID_ROWS)]
    grid = ReelGrid(DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS, grid_data)

    winning_lines = GridWinEvaluator(grid, LineEvaluationStrategy()).evaluate()

    jackpot_lines = [line for line in winning_lines if line.is_jackpot()]
    assert jackpot_lines, "Expected at least one jackpot winning line."

    coins, free_spins = PayoutCalculator(PayoutTable()).calculate(winning_lines)
    assert coins.amount() == Money('5000').amount()
    assert free_spins == 0


def test_five_of_a_kind_row_payout():
    """A five-of-a-kind row pays 200 coins and 2 free spins.

    The remaining rows are arranged as a Latin square over the non-winning
    symbols so that no other row, column, or diagonal forms a win; the only
    winning line is the first row.
    """
    grid_data = [
        ['⚡', '⚡', '⚡', '⚡', '⚡'],
        ['🦁', '🦅', '⚡', '🏺', '👑'],
        ['🏺', '👑', '🦁', '🦅', '⚡'],
        ['🦅', '⚡', '🏺', '👑', '🦁'],
        ['👑', '🦁', '🦅', '⚡', '🏺'],
    ]
    grid = ReelGrid(DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS, grid_data)

    winning_lines = GridWinEvaluator(grid, LineEvaluationStrategy()).evaluate()
    assert winning_lines, "Expected at least the row win."

    row_wins = [
        line
        for line in winning_lines
        if line.get_line_type() == LineType.ROW and line.get_line_index() == 0
    ]
    assert row_wins, "Expected the first row to be a winning line."
    assert row_wins[0].get_match_count() == 5
    assert row_wins[0].get_matched_symbol() == '⚡'

    coins, free_spins = PayoutCalculator(PayoutTable()).calculate(winning_lines)
    assert coins.amount() == Money('200').amount()
    assert free_spins == 2


def test_line_strategy_wild_rule_counts_zeus_towards_match():
    """Three lightning plus one Zeus wild on a line wins with a count of four."""
    strategy = LineEvaluationStrategy()

    matched_symbol, count, is_jackpot = strategy.evaluate(
        ['⚡', '⚡', ZEUS_SYMBOL, '⚡', '🍒']
    )

    assert matched_symbol == '⚡'
    assert count == 4
    assert is_jackpot is False


def test_line_strategy_mixed_high_symbols_does_not_win():
    """Two different high symbols plus a Zeus wild do not form a win.

    Neither high symbol reaches the required count of three, so the line is
    reported as a loss.
    """
    strategy = LineEvaluationStrategy()

    matched_symbol, count, is_jackpot = strategy.evaluate(
        ['⚡', '⚡', '🦁', '🦁', ZEUS_SYMBOL]
    )

    assert matched_symbol is None
    assert count == 0
    assert is_jackpot is False
