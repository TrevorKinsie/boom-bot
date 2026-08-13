"""
Zeus 5x5 Reel-Slot Domain Model.

This module encapsulates the pure, framework-free domain logic for the Zeus
5x5 reel-slot family. It is intentionally over-abstracted and enterprise
styled: it models the reel machine as a set of immutable value objects, an
enumerable symbol vocabulary, a pluggable grid generation strategy, and a
payout computation pipeline.

The domain is organised around the following responsibilities:

* :class:`ReelSymbol` and :class:`LineType` enumerate the vocabulary of the
  machine (the symbols that can land on a reel) and the geometry of pay-lines
  (the lines along which matches are evaluated).
* :class:`ReelGrid` is an immutable value object representing a fully spun
  grid of symbols.
* :class:`WinningLine` is an immutable value object describing a single
  winning pay-line.
* :class:`AbstractGridFactory` and :class:`RandomGridFactory` are responsible
  for producing newly spun grids.
* :class:`GridWinEvaluator` and :class:`LineEvaluationStrategy` are
  responsible for detecting winning lines across the grid.
* :class:`PayoutTable` and :class:`PayoutCalculator` are responsible for
  translating winning lines into monetary rewards and free spins.

The evaluation rules mirror the legacy Zeus slots game exactly: a line is
either a jackpot (all five positions are the Zeus wild), a ``3``/``4``/``5``
of a kind of a single non-Wild symbol possibly augmented by at most one Wild,
or not a win at all.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import namedtuple
from decimal import Decimal
from enum import Enum
from typing import Iterator, List, Optional, Sequence, Tuple

from boombot.casino.shared.value_objects import Money

# ---------------------------------------------------------------------------
# Domain constants.
# ---------------------------------------------------------------------------

#: The Zeus wild / jackpot symbol. When every position of a line is this
#: symbol the line is a jackpot.
ZEUS_SYMBOL: str = '🧔♂️'

#: The complete vocabulary of symbols that may appear on a reel.
ZEUS_SYMBOLS: List[str] = ['⚡', '🦁', '🏺', '🦅', '👑', '🍒', '🍊', '🍇', '🧔♂️']

#: The default number of rows of a Zeus reel grid.
DEFAULT_GRID_ROWS: int = 5

#: The default number of columns of a Zeus reel grid.
DEFAULT_GRID_COLS: int = 5


# ---------------------------------------------------------------------------
# Enumerations.
# ---------------------------------------------------------------------------

class ReelSymbol(Enum):
    """Enumerate the symbols that may appear on a Zeus reel.

    Each member maps a human-understandable name to the emoji glyph that is
    stored within a :class:`ReelGrid`. The :class:`ZEUS` member is special:
    it acts as the wild / jackpot symbol for every pay-line evaluation.
    """

    LIGHTNING: str = '⚡'
    LION: str = '🦁'
    AMPHORA: str = '🏺'
    EAGLE: str = '🦅'
    CROWN: str = '👑'
    CHERRY: str = '🍒'
    ORANGE: str = '🍊'
    GRAPE: str = '🍇'
    ZEUS: str = ZEUS_SYMBOL

    @classmethod
    def symbol_value(cls, symbol: str) -> 'ReelSymbol':
        """Return the :class:`ReelSymbol` whose emoji glyph equals ``symbol``.

        This classmethod provides a reverse lookup from the raw emoji string
        stored inside a grid back to the corresponding enumerated member.

        Args:
            symbol: The raw emoji glyph found within a grid cell.

        Returns:
            The :class:`ReelSymbol` member whose value equals ``symbol``.

        Raises:
            ValueError: If ``symbol`` does not correspond to any known reel
                symbol.
        """
        return cls(symbol)


class LineType(Enum):
    """Enumerate the geometric orientations of a pay-line within a grid.

    A 5x5 grid exposes 5 rows, 5 columns, and 2 diagonals, for a total of 12
    distinct pay-lines.
    """

    ROW: str = 'ROW'
    COLUMN: str = 'COLUMN'
    DIAGONAL_PRIMARY: str = 'DIAGONAL_PRIMARY'
    DIAGONAL_SECONDARY: str = 'DIAGONAL_SECONDARY'


# ---------------------------------------------------------------------------
# Pay-line value objects.
# ---------------------------------------------------------------------------

#: A named tuple describing a single geometric pay-line extracted from a grid.
#:
#: Attributes:
#:     line_type: The :class:`LineType` family of the line.
#:     line_index: The zero-based index of the line within its family.
#:     symbols: An immutable tuple of the symbols occupying the line.
GridLine = namedtuple('GridLine', ['line_type', 'line_index', 'symbols'])


class WinningLine:
    """An immutable value object describing a single winning pay-line.

    A ``WinningLine`` is produced by the :class:`GridWinEvaluator` whenever a
    pay-line satisfies the machine's win criteria (a count of at least three,
    or a jackpot). It carries the geometric identity of the line together with
    the outcome of the evaluation.

    Attributes:
        line_type: The :class:`LineType` family of the winning line.
        line_index: The zero-based index of the line within its family.
        matched_symbol: The symbol that produced the win, or ``None`` for a
            jackpot win.
        match_count: The number of matched positions (Wilds included).
        is_jackpot: ``True`` when the line is a jackpot win.
    """

    __slots__ = ('_line_type', '_line_index', '_matched_symbol', '_match_count', '_is_jackpot')

    def __init__(
        self,
        line_type: LineType,
        line_index: int,
        matched_symbol: Optional[str],
        match_count: int,
        is_jackpot: bool,
    ) -> None:
        """Initialise a new immutable winning line.

        Args:
            line_type: The :class:`LineType` family of the winning line.
            line_index: The zero-based index of the line within its family.
            matched_symbol: The symbol that produced the win, or ``None`` for
                a jackpot win.
            match_count: The number of matched positions (Wilds included).
            is_jackpot: ``True`` when the line is a jackpot win.
        """
        self._line_type = line_type
        self._line_index = line_index
        self._matched_symbol = matched_symbol
        self._match_count = match_count
        self._is_jackpot = is_jackpot

    def get_line_type(self) -> LineType:
        """Return the :class:`LineType` family of this winning line."""
        return self._line_type

    def get_line_index(self) -> int:
        """Return the zero-based index of this winning line within its family."""
        return self._line_index

    def get_matched_symbol(self) -> Optional[str]:
        """Return the symbol that produced the win, or ``None`` for a jackpot."""
        return self._matched_symbol

    def get_match_count(self) -> int:
        """Return the number of matched positions (Wilds included)."""
        return self._match_count

    def is_jackpot(self) -> bool:
        """Return ``True`` when this line is a jackpot win."""
        return self._is_jackpot

    def __repr__(self) -> str:
        return (
            f"WinningLine(line_type={self._line_type}, line_index={self._line_index}, "
            f"matched_symbol={self._matched_symbol!r}, match_count={self._match_count}, "
            f"is_jackpot={self._is_jackpot})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WinningLine):
            return NotImplemented
        return (
            self._line_type == other._line_type
            and self._line_index == other._line_index
            and self._matched_symbol == other._matched_symbol
            and self._match_count == other._match_count
            and self._is_jackpot == other._is_jackpot
        )

    def __hash__(self) -> int:
        return hash((self._line_type, self._line_index, self._matched_symbol, self._match_count, self._is_jackpot))


# ---------------------------------------------------------------------------
# Grid value object.
# ---------------------------------------------------------------------------

class ReelGrid:
    """An immutable value object representing a fully spun 5x5 reel grid.

    A ``ReelGrid`` is constructed from a rectangular ``rows`` x ``cols``
    matrix of raw emoji symbols. The supplied ``grid_data`` is validated to
    match the declared dimensions and is then stored as an immutable tuple of
    tuples so that no caller can mutate the state of the machine after a spin.

    The grid exposes accessors for individual cells and whole rows, as well as
    :meth:`iterate_lines`, which decomposes the grid into its constituent
    pay-lines (rows, columns, and both diagonals).
    """

    __slots__ = ('_rows', '_cols', '_grid_data')

    def __init__(self, rows: int, cols: int, grid_data: List[List[str]]) -> None:
        """Initialise a new immutable reel grid.

        Args:
            rows: The number of rows in the grid.
            cols: The number of columns in the grid.
            grid_data: A list of ``rows`` lists, each containing exactly
                ``cols`` raw emoji symbols.

        Raises:
            ValueError: If ``grid_data`` does not match the declared ``rows``
                and ``cols`` dimensions, or if any row has a differing length.
        """
        if rows < 1 or cols < 1:
            raise ValueError("ReelGrid dimensions must be positive.")
        if len(grid_data) != rows:
            raise ValueError(
                f"ReelGrid declared {rows} rows but received {len(grid_data)}."
            )
        for row_index, row in enumerate(grid_data):
            if len(row) != cols:
                raise ValueError(
                    f"ReelGrid declared {cols} columns but row {row_index} has "
                    f"{len(row)} entries."
                )
        # Freeze the grid into an immutable tuple-of-tuples to preserve the
        # value-object invariant that the machine state never mutates.
        self._rows = rows
        self._cols = cols
        self._grid_data = tuple(tuple(row) for row in grid_data)

    def get_rows(self) -> int:
        """Return the number of rows in the grid."""
        return self._rows

    def get_cols(self) -> int:
        """Return the number of columns in the grid."""
        return self._cols

    def get_symbol(self, row: int, col: int) -> str:
        """Return the raw symbol at the given zero-based ``row`` and ``col``.

        Args:
            row: The zero-based row index of the desired cell.
            col: The zero-based column index of the desired cell.

        Returns:
            The raw emoji symbol stored at that cell.

        Raises:
            IndexError: If the requested cell is outside the grid bounds.
        """
        return self._grid_data[row][col]

    def get_all_rows(self) -> Tuple[Tuple[str, ...], ...]:
        """Return the immutable tuple-of-tuples backing this grid.

        The returned structure is the frozen internal representation; callers
        cannot mutate the grid through it.
        """
        return self._grid_data

    def iterate_lines(self) -> Iterator[GridLine]:
        """Yield every pay-line of the grid as a :class:`GridLine`.

        The grid is decomposed into its rows, then its columns, then its two
        diagonals. Each yielded :class:`GridLine` carries its geometric family,
        its zero-based index within that family, and the ordered tuple of
        symbols occupying the line.

        Yields:
            :class:`GridLine` named tuples for every row, column, primary
            diagonal, and secondary diagonal.
        """
        # Rows.
        for row_index in range(self._rows):
            yield GridLine(LineType.ROW, row_index, self._grid_data[row_index])

        # Columns.
        for col_index in range(self._cols):
            column = tuple(self._grid_data[row][col_index] for row in range(self._rows))
            yield GridLine(LineType.COLUMN, col_index, column)

        # Primary diagonal (top-left to bottom-right).
        primary = tuple(self._grid_data[i][i] for i in range(min(self._rows, self._cols)))
        yield GridLine(LineType.DIAGONAL_PRIMARY, 0, primary)

        # Secondary diagonal (top-right to bottom-left).
        secondary = tuple(
            self._grid_data[i][self._cols - 1 - i]
            for i in range(min(self._rows, self._cols))
        )
        yield GridLine(LineType.DIAGONAL_SECONDARY, 1, secondary)

    def __repr__(self) -> str:
        return f"ReelGrid(rows={self._rows}, cols={self._cols})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReelGrid):
            return NotImplemented
        return self._grid_data == other._grid_data

    def __hash__(self) -> int:
        return hash(self._grid_data)


# ---------------------------------------------------------------------------
# Grid factories.
# ---------------------------------------------------------------------------

class AbstractGridFactory(ABC):
    """Abstract strategy for producing newly spun reel grids.

    Subclasses decide how the symbols of a freshly spun grid are generated.
    This abstraction allows the domain to be exercised with deterministic
    grids in tests while a truly random implementation is used in production.
    """

    @abstractmethod
    def generate(self, rows: int, cols: int) -> ReelGrid:
        """Generate a new :class:`ReelGrid` of the given dimensions.

        Args:
            rows: The number of rows in the grid to generate.
            cols: The number of columns in the grid to generate.

        Returns:
            A newly generated :class:`ReelGrid`.
        """
        raise NotImplementedError


class RandomGridFactory(AbstractGridFactory):
    """A grid factory that fills every cell with a uniformly random symbol.

    Each cell of the generated grid is drawn independently from
    :data:`ZEUS_SYMBOLS` using :func:`random.choice`. The resulting grid is
    returned as an immutable :class:`ReelGrid`.
    """

    def generate(self, rows: int, cols: int) -> ReelGrid:
        """Generate a random :class:`ReelGrid` of the given dimensions.

        Args:
            rows: The number of rows in the grid to generate.
            cols: The number of columns in the grid to generate.

        Returns:
            A random :class:`ReelGrid` whose cells are drawn uniformly from
            :data:`ZEUS_SYMBOLS`.
        """
        grid_data: List[List[str]] = [
            [random.choice(ZEUS_SYMBOLS) for _ in range(cols)] for _ in range(rows)
        ]
        return ReelGrid(rows, cols, grid_data)


# ---------------------------------------------------------------------------
# Win evaluation.
# ---------------------------------------------------------------------------

class LineEvaluationStrategy:
    """Evaluate a single pay-line and report whether it is a win.

    The evaluation logic is ported verbatim from the legacy Zeus slots game:

    * If every position of the line is the Zeus wild, the line is a jackpot
      and is reported as ``(None, 5, True)``.
    * Otherwise the most common non-Zeus symbol is identified. The line wins
      only when that symbol occurs at least three times AND the line contains
      at most one Zeus wild. The matched count is the sum of the target count
      and the Zeus count. In every other case the line is reported as a loss
      ``(None, 0, False)``.
    """

    def evaluate(self, symbols: Sequence[str]) -> Tuple[Optional[str], int, bool]:
        """Evaluate a single pay-line of symbols.

        Args:
            symbols: An ordered sequence of raw emoji symbols forming a
                pay-line.

        Returns:
            A tuple ``(matched_symbol, count, is_jackpot)`` where
            ``matched_symbol`` is the winning symbol (or ``None`` for a
            jackpot), ``count`` is the number of matched positions, and
            ``is_jackpot`` indicates a jackpot win. Losing lines report
            ``(None, 0, False)``.
        """
        if all(symbol == ZEUS_SYMBOL for symbol in symbols):
            return None, 5, True

        non_zeus_symbols = [symbol for symbol in symbols if symbol != ZEUS_SYMBOL]
        if not non_zeus_symbols:
            return None, 0, False

        target_symbol = max(set(non_zeus_symbols), key=non_zeus_symbols.count)
        target_count = sum(1 for symbol in symbols if symbol == target_symbol)
        zeus_count = sum(1 for symbol in symbols if symbol == ZEUS_SYMBOL)

        if target_count >= 3 and zeus_count <= 1:
            return target_symbol, target_count + zeus_count, False

        return None, 0, False


class GridWinEvaluator:
    """Evaluate every pay-line of a grid and collect the winning lines.

    The evaluator walks every row, column, and diagonal exposed by
    :meth:`ReelGrid.iterate_lines`, delegates line-level evaluation to a
    :class:`LineEvaluationStrategy`, and retains only those lines that satisfy
    the machine's win criteria (a match count of at least three, or a
    jackpot).
    """

    def __init__(self, grid: ReelGrid, strategy: LineEvaluationStrategy) -> None:
        """Initialise a grid evaluator bound to a specific grid.

        Args:
            grid: The :class:`ReelGrid` to evaluate.
            strategy: The :class:`LineEvaluationStrategy` used to evaluate each
                individual pay-line.
        """
        self._grid = grid
        self._strategy = strategy

    def evaluate(self) -> List[WinningLine]:
        """Evaluate every pay-line of the bound grid.

        Returns:
            A list of :class:`WinningLine` objects for every pay-line that
            constitutes a win. Losing lines are excluded from the result.
        """
        winning_lines: List[WinningLine] = []
        for grid_line in self._grid.iterate_lines():
            matched_symbol, count, is_jackpot = self._strategy.evaluate(grid_line.symbols)
            if count >= 3 or is_jackpot:
                winning_lines.append(
                    WinningLine(
                        line_type=grid_line.line_type,
                        line_index=grid_line.line_index,
                        matched_symbol=matched_symbol,
                        match_count=count,
                        is_jackpot=is_jackpot,
                    )
                )
        return winning_lines


# ---------------------------------------------------------------------------
# Payout computation.
# ---------------------------------------------------------------------------

class PayoutTable:
    """Translate a single winning line into coins and free spins.

    The payout mapping mirrors the legacy Zeus slots game:

    * A jackpot pays ``5000`` coins and no free spins.
    * A count of five or more pays ``200`` coins and ``2`` free spins.
    * A count of exactly four pays ``50`` coins and ``1`` free spin.
    * A count of exactly three pays ``10`` coins and no free spins.
    * Any other outcome pays nothing.
    """

    def payouts_for(
        self,
        symbol: Optional[str],
        count: int,
        is_jackpot: bool,
    ) -> Tuple[int, int]:
        """Return the coins and free spins awarded for a single line.

        Args:
            symbol: The matched symbol, or ``None`` for a jackpot.
            count: The number of matched positions on the line.
            is_jackpot: Whether the line is a jackpot win.

        Returns:
            A tuple ``(coins, free_spins)`` awarded for this line.
        """
        if is_jackpot:
            return 5000, 0
        if count >= 5:
            return 200, 2
        if count == 4:
            return 50, 1
        if count == 3:
            return 10, 0
        return 0, 0


class PayoutCalculator:
    """Aggregate the payouts for a collection of winning lines.

    The calculator iterates over every :class:`WinningLine`, looks up the
    per-line payout via a :class:`PayoutTable`, and cumulatively sums the coin
    and free-spin rewards. Overlapping lines (for example, a cell that
    participates in both a row and a column win) are each counted in full,
    matching the legacy behaviour in which every matching line was summed.

    The one exception is the jackpot: a jackpot is a grid-level event and is
    awarded exactly once regardless of how many pay-lines individually
    evaluate to a jackpot. This keeps a fully-Wild grid worth ``5000`` coins
    rather than an unbounded sum of per-line jackpot awards.
    """

    def __init__(self, payout_table: PayoutTable) -> None:
        """Initialise a payout calculator with a payout table.

        Args:
            payout_table: The :class:`PayoutTable` used to resolve per-line
                payouts.
        """
        self._payout_table = payout_table

    def calculate(self, winnings: List[WinningLine]) -> Tuple[Money, int]:
        """Aggregate the payouts for the given winning lines.

        Args:
            winnings: A collection of :class:`WinningLine` objects to resolve.

        Returns:
            A tuple ``(coins, free_spins)`` where ``coins`` is a
            :class:`Money` value object aggregating the total coin reward and
            ``free_spins`` is the total number of free spins awarded.
        """
        total_coins = Decimal('0')
        total_free_spins = 0
        jackpot_awarded = False

        for winning_line in winnings:
            if winning_line.is_jackpot():
                # A jackpot is a grid-level prize awarded exactly once.
                if not jackpot_awarded:
                    total_coins += Decimal('5000')
                    jackpot_awarded = True
                continue

            coins, free_spins = self._payout_table.payouts_for(
                symbol=winning_line.get_matched_symbol(),
                count=winning_line.get_match_count(),
                is_jackpot=winning_line.is_jackpot(),
            )
            total_coins += Decimal(str(coins))
            total_free_spins += free_spins

        return Money(total_coins), total_free_spins