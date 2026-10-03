/*
 * bb_zeus.cpp - see bb_zeus.h.
 */
#include "bb_zeus.h"

#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>

namespace bb {

const char* const ZEUS_SYMBOLS[kZeusSymbolsCount] = {
    "\xE2\x9A\xA1",       // lightning bolt
    "\xF0\x9F\xA6\x81",   // lion
    "\xF0\x9F\x8F\xBA",   // amphora
    "\xF0\x9F\xA6\x85",   // eagle
    "\xF0\x9F\x91\x91",   // crown
    "\xF0\x9F\x8D\x92",   // cherry
    "\xF0\x9F\x8D\x8A",   // orange
    "\xF0\x9F\x8D\x87",   // grape
    "\xF0\x9F\xA7\x94\xE2\x80\x8D\xE2\x99\x82\xEF\xB8\x8F", // bearded person
};

ReelGrid::ReelGrid(int rows, int cols, const std::vector<int>& grid_data)
    : rows_(rows), cols_(cols), grid_data_(grid_data) {
    if (rows < 1 || cols < 1)
        throw std::invalid_argument("ReelGrid dimensions must be positive.");
    if (static_cast<int>(grid_data_.size()) != rows * cols)
        throw std::invalid_argument("ReelGrid data size does not match declared dimensions.");
}

std::vector<GridLine> ReelGrid::iterate_lines() const {
    std::vector<GridLine> lines;
    for (int row = 0; row < rows_; ++row) {
        GridLine line{LineType::Row, row, {}};
        for (int col = 0; col < cols_; ++col)
            line.symbols.push_back(symbol(row, col));
        lines.push_back(line);
    }
    for (int col = 0; col < cols_; ++col) {
        GridLine line{LineType::Column, col, {}};
        for (int row = 0; row < rows_; ++row)
            line.symbols.push_back(symbol(row, col));
        lines.push_back(line);
    }
    GridLine primary{LineType::DiagonalPrimary, 0, {}};
    for (int i = 0; i < std::min(rows_, cols_); ++i)
        primary.symbols.push_back(symbol(i, i));
    lines.push_back(primary);
    GridLine secondary{LineType::DiagonalSecondary, 1, {}};
    for (int i = 0; i < std::min(rows_, cols_); ++i)
        secondary.symbols.push_back(symbol(i, cols_ - 1 - i));
    lines.push_back(secondary);
    return lines;
}

void LineEvaluationStrategy::evaluate(const std::vector<int>& symbols, int* matched_symbol,
                                      int* count, bool* is_jackpot) const {
    bool all_zeus = true;
    for (int symbol : symbols) {
        if (symbol != kZeusSymbol) {
            all_zeus = false;
            break;
        }
    }
    if (all_zeus) {
        *matched_symbol = -1;
        *count = 5;
        *is_jackpot = true;
        return;
    }

    std::vector<int> non_zeus;
    for (int symbol : symbols) {
        if (symbol != kZeusSymbol)
            non_zeus.push_back(symbol);
    }
    if (non_zeus.empty()) {
        *matched_symbol = -1;
        *count = 0;
        *is_jackpot = false;
        return;
    }

    std::vector<int> distinct;
    for (int symbol : non_zeus) {
        if (std::find(distinct.begin(), distinct.end(), symbol) == distinct.end())
            distinct.push_back(symbol);
    }
    std::vector<int> frequencies;
    for (int d : distinct)
        frequencies.push_back(
            static_cast<int>(std::count(non_zeus.begin(), non_zeus.end(), d)));

    // Ties resolve to the first-distinct symbol with the maximum count,
    // matching Python: max(set(...), key=...) iterates set insertion order,
    // which in CPython follows first-occurrence order for ints.
    int target = distinct[0];
    int best = frequencies[0];
    for (size_t i = 1; i < distinct.size(); ++i) {
        if (frequencies[i] > best) {
            best = frequencies[i];
            target = distinct[i];
        }
    }

    int target_count = static_cast<int>(std::count(symbols.begin(), symbols.end(), target));
    int zeus_count = static_cast<int>(std::count(symbols.begin(), symbols.end(), kZeusSymbol));
    if (target_count >= 3 && zeus_count <= 1) {
        *matched_symbol = target;
        *count = target_count + zeus_count;
        *is_jackpot = false;
        return;
    }
    *matched_symbol = -1;
    *count = 0;
    *is_jackpot = false;
}

std::vector<WinningLine> GridWinEvaluator::evaluate() const {
    std::vector<WinningLine> winning_lines;
    for (const GridLine& line : grid_->iterate_lines()) {
        int matched_symbol;
        int count;
        bool is_jackpot;
        strategy_->evaluate(line.symbols, &matched_symbol, &count, &is_jackpot);
        if (count >= 3 || is_jackpot) {
            winning_lines.push_back(
                WinningLine{line.line_type, line.line_index, matched_symbol, count, is_jackpot});
        }
    }
    return winning_lines;
}

void PayoutTable::payouts_for(int match_count, bool is_jackpot, int64_t* coins,
                              int* free_spins) const {
    if (is_jackpot) {
        *coins = 5000;
        *free_spins = 0;
    } else if (match_count >= 5) {
        *coins = 200;
        *free_spins = 2;
    } else if (match_count == 4) {
        *coins = 50;
        *free_spins = 1;
    } else if (match_count == 3) {
        *coins = 10;
        *free_spins = 0;
    } else {
        *coins = 0;
        *free_spins = 0;
    }
}

void PayoutCalculator::calculate(const std::vector<WinningLine>& winnings, int64_t* coins,
                                 int* free_spins) const {
    int64_t total_coins = 0;
    int total_free_spins = 0;
    bool jackpot_awarded = false;
    for (const WinningLine& line : winnings) {
        if (line.is_jackpot) {
            if (!jackpot_awarded) {
                total_coins += 5000;
                jackpot_awarded = true;
            }
            continue;
        }
        int64_t line_coins;
        int line_spins;
        table_->payouts_for(line.match_count, false, &line_coins, &line_spins);
        total_coins += line_coins;
        total_free_spins += line_spins;
    }
    *coins = total_coins;
    *free_spins = total_free_spins;
}

} // namespace bb