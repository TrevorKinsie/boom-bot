/*
 * bb_zeus.h - Zeus 5x5 reel-slot domain model.
 *
 * Mirrors boombot/casino/zeus/domain/reel.py: symbol vocabulary, line
 * decomposition (5 rows, 5 columns, 2 diagonals), LineEvaluationStrategy
 * (jackpot = all-wild; otherwise most-common non-wild with count >= 3 and at
 * most one wild), and PayoutCalculator (jackpot awarded exactly once per
 * grid; 5+ => 200 coins + 2 free spins; 4 => 50 + 1; 3 => 10 + 0).
 */
#ifndef BB_ZEUS_H
#define BB_ZEUS_H

#include <cstdint>
#include <string>
#include <vector>

namespace bb {

// Symbol indices into ZEUS_SYMBOLS; 8 is the Zeus wild / jackpot symbol.
inline constexpr int kZeusSymbol = 8;
inline constexpr int kZeusSymbolsCount = 9;
extern const char* const ZEUS_SYMBOLS[kZeusSymbolsCount];

// Pay-line geometry family.
enum class LineType { Row, Column, DiagonalPrimary, DiagonalSecondary };

// A single geometric pay-line extracted from a grid.
struct GridLine {
    LineType line_type;
    int line_index;
    std::vector<int> symbols;
};

// A winning pay-line produced by the grid evaluator.
struct WinningLine {
    LineType line_type;
    int line_index;
    // Matched symbol index, or -1 for a jackpot win.
    int matched_symbol;
    // Number of matched positions (wilds included).
    int match_count;
    bool is_jackpot;
};

// Immutable value object wrapping an rows x cols matrix of symbol indices.
class ReelGrid {
public:
    ReelGrid(int rows, int cols, const std::vector<int>& grid_data);
    const std::vector<int>& grid_data() const { return grid_data_; }
    int rows() const { return rows_; }
    int cols() const { return cols_; }
    int symbol(int row, int col) const { return grid_data_[row * cols_ + col]; }
    // Rows, then columns, then primary and secondary diagonals.
    std::vector<GridLine> iterate_lines() const;

private:
    int rows_;
    int cols_;
    std::vector<int> grid_data_;
};

// Pure line evaluation, ported verbatim from the legacy rules.
class LineEvaluationStrategy {
public:
    // Returns (matched_symbol, count, is_jackpot); losing lines are
    // (-1, 0, false).
    void evaluate(const std::vector<int>& symbols, int* matched_symbol, int* count,
                  bool* is_jackpot) const;
};

// Walks every line via iterate_lines and keeps the wins.
class GridWinEvaluator {
public:
    GridWinEvaluator(const ReelGrid& grid, const LineEvaluationStrategy& strategy)
        : grid_(&grid), strategy_(&strategy) {}
    std::vector<WinningLine> evaluate() const;

private:
    const ReelGrid* grid_;
    const LineEvaluationStrategy* strategy_;
};

// Payout table: jackpot 5000/0; >=5 => 200/2; ==4 => 50/1; ==3 => 10/0.
class PayoutTable {
public:
    void payouts_for(int match_count, bool is_jackpot, int64_t* coins, int* free_spins) const;
};

// Sums per-line payouts; the jackpot is a grid-level prize awarded once.
class PayoutCalculator {
public:
    explicit PayoutCalculator(const PayoutTable& table) : table_(&table) {}
    void calculate(const std::vector<WinningLine>& winnings, int64_t* coins,
                   int* free_spins) const;

private:
    const PayoutTable* table_;
};

} // namespace bb

#endif // BB_ZEUS_H