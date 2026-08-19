/*
 * bb_casino.cpp - see bb_casino.h.
 */
#include "bb_casino.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "bb_event_store.h"
#include "bb_money.h"
#include "bb_wallet.h"
#include "bb_zeus.h"

namespace bb {

namespace {

constexpr int kComeOutPhase = 1;
constexpr int kPointPhase = 2;

constexpr int kRedNumbers[] = {1,  3,  5,  7,  9,  12, 14, 16, 18,
                               19, 21, 23, 25, 27, 30, 32, 34, 36};

bool is_red(int number) {
    for (int n : kRedNumbers) {
        if (n == number)
            return true;
    }
    return false;
}

bool is_even_money_win(const std::string& bet_type, const RouletteResult& result) {
    if (bet_type == "red")
        return !result.is_double_zero && result.number != 0 && is_red(result.number);
    if (bet_type == "black")
        return !result.is_double_zero && result.number != 0 && !is_red(result.number);
    if (bet_type == "even")
        return !result.is_double_zero && result.number != 0 && result.number % 2 == 0;
    if (bet_type == "odd")
        return !result.is_double_zero && result.number != 0 && result.number % 2 != 0;
    if (bet_type == "low")
        return !result.is_double_zero && result.number >= 1 && result.number <= 18;
    if (bet_type == "high")
        return !result.is_double_zero && result.number >= 19 && result.number <= 36;
    if (bet_type == "first_dozen")
        return !result.is_double_zero && result.number >= 1 && result.number <= 12;
    if (bet_type == "second_dozen")
        return !result.is_double_zero && result.number >= 13 && result.number <= 24;
    if (bet_type == "third_dozen")
        return !result.is_double_zero && result.number >= 25 && result.number <= 36;
    return false;
}

// Multiplier per even-money / dozen bet; straight pays 35x.
int roulette_multiplier(const std::string& bet_type) {
    if (bet_type == "straight")
        return 35;
    if (bet_type == "first_dozen" || bet_type == "second_dozen" ||
        bet_type == "third_dozen")
        return 2;
    return 1;
}

bool is_supported_roulette(const std::string& bet_type) {
    return bet_type == "straight" || bet_type == "red" || bet_type == "black" ||
           bet_type == "even" || bet_type == "odd" || bet_type == "low" ||
           bet_type == "high" || bet_type == "first_dozen" ||
           bet_type == "second_dozen" || bet_type == "third_dozen";
}

bool is_supported_craps(const std::string& bet_type) {
    static const char* types[] = {"pass_line", "dont_pass",  "field",
                                  "place_4",   "place_5",    "place_6",
                                  "place_8",   "place_9",    "place_10",
                                  "hard_4",    "hard_6",     "hard_8",
                                  "hard_10",   "any_craps",  "any_seven",
                                  "two",       "three",      "eleven",
                                  "twelve",    "horn"};
    for (const char* t : types) {
        if (bet_type == t)
            return true;
    }
    return false;
}

int craps_number_suffix(const std::string& bet_type) {
    // bet_type.split("_", 1)[1]
    size_t pos = bet_type.find('_');
    return std::stoi(bet_type.substr(pos + 1));
}

int craps_multiplier_num(const std::string& bet_type, int roll_sum, int* denominator) {
    // Returns the fractional multiplier as (num, den); whole numbers use den 1.
    if (bet_type == "pass_line" || bet_type == "dont_pass") {
        *denominator = 1;
        return 1;
    }
    if (bet_type == "field") {
        *denominator = 1;
        if (roll_sum == 2)
            return 2;
        if (roll_sum == 12)
            return 3;
        return 1;
    }
    if (bet_type.rfind("place_", 0) == 0) {
        int number = craps_number_suffix(bet_type);
        switch (number) {
        case 4:
        case 10:
            *denominator = 5;
            return 9;
        case 5:
        case 9:
            *denominator = 5;
            return 7;
        case 6:
        case 8:
            *denominator = 6;
            return 7;
        default:
            break;
        }
        *denominator = 1;
        return 0;
    }
    if (bet_type.rfind("hard_", 0) == 0) {
        int number = craps_number_suffix(bet_type);
        *denominator = 1;
        if (number == 4 || number == 10)
            return 7;
        return 9;
    }
    if (bet_type == "any_craps") {
        *denominator = 1;
        return 7;
    }
    if (bet_type == "any_seven") {
        *denominator = 1;
        return 4;
    }
    if (bet_type == "two" || bet_type == "twelve" || bet_type == "horn") {
        *denominator = 1;
        return 30;
    }
    if (bet_type == "three" || bet_type == "eleven") {
        *denominator = 1;
        return 15;
    }
    *denominator = 1;
    return 0;
}

} // namespace

GameSession& InMemoryGameSessionStore::get_channel_session(const std::string& channel_id) {
    auto it = sessions_.find(channel_id);
    if (it == sessions_.end()) {
        it = sessions_.emplace(channel_id, GameSession::fresh()).first;
    }
    return it->second;
}

void InMemoryGameSessionStore::save_channel_session(const std::string& channel_id,
                                                    const GameSession& session) {
    sessions_[channel_id] = session;
}

WageringService::WageringService(WalletRepository& repository, JsonEventStore& store,
                                 InMemoryGameSessionStore& session_store,
                                 InProcessEventBus& event_bus,
                                 const Money& starting_balance, const Money& zeus_spin_cost)
    : repository_(repository), store_(store), session_store_(session_store),
      event_bus_(&event_bus), starting_balance_(starting_balance),
      zeus_spin_cost_(zeus_spin_cost) {
    roulette_pocket = []() {
        static thread_local std::mt19937 rng(
            std::random_device{}() ^ static_cast<unsigned>(std::chrono::steady_clock::now().time_since_epoch().count()));
        return static_cast<int>(rng() % 38); // 0..36, 37 == "00"
    };
    craps_roll = [](int* die1, int* die2) {
        static thread_local std::mt19937 rng(
            std::random_device{}() ^ static_cast<unsigned>(std::chrono::steady_clock::now().time_since_epoch().count()));
        *die1 = static_cast<int>(rng() % 6) + 1;
        *die2 = static_cast<int>(rng() % 6) + 1;
    };
    zeus_grid = [](int rows, int cols) {
        static thread_local std::mt19937 rng(
            std::random_device{}() ^ static_cast<unsigned>(std::chrono::steady_clock::now().time_since_epoch().count()));
        std::vector<int> grid;
        grid.reserve(static_cast<size_t>(rows * cols));
        for (int i = 0; i < rows * cols; ++i)
            grid.push_back(static_cast<int>(rng() % kZeusSymbolsCount));
        return grid;
    };
}

Wallet& WageringService::get_wallet(const std::string& user_id) {
    Wallet* wallet = wallet_cache_[user_id].get();
    if (!wallet) {
        auto loaded = repository_.load_or_provision(user_id);
        wallet = loaded.get();
        wallet_cache_[user_id] = std::move(loaded);
        if (wallet->has_uncommitted_events())
            flush(*wallet);
    }
    return *wallet;
}

Money WageringService::get_balance(const std::string& user_id) {
    return get_wallet(user_id).balance();
}

std::string WageringService::get_balance_text(const std::string& user_id) {
    Wallet& wallet = get_wallet(user_id);
    return "Wallet\nBalance: " + wallet.balance().formatted() +
           "\nFree spins: " + std::to_string(wallet.free_spins()) +
           "\nTotal won: " + wallet.total_won().formatted() +
           "\nTotal wagered: " + wallet.total_wagered().formatted();
}

void WageringService::flush(Wallet& wallet) {
    // Copy before save(): save() commits the aggregate and clears the
    // uncommitted queue, which would invalidate a reference to it.
    std::vector<WalletEvent> staged = wallet.uncommitted_events();
    if (staged.empty())
        return;
    repository_.save(wallet);
    for (const WalletEvent& event : staged)
        event_bus_->publish(event);
}

Money WageringService::parse_amount(const std::string& amount_str) {
    try {
        Money amount = Money(amount_str);
        if (amount.is_zero())
            throw CasinoError("Bet amount must be positive.");
        return amount;
    } catch (const CasinoError&) {
        throw;
    } catch (const std::exception&) {
        throw CasinoError("Invalid bet amount: " + amount_str);
    }
}

void WageringService::require_balance(Wallet& wallet, const Money& amount) {
    if (amount.is_greater_than(wallet.balance())) {
        throw CasinoError("Insufficient balance " + wallet.balance().formatted() +
                          " for wager " + amount.formatted() + ".");
    }
}

std::string WageringService::place_roulette_bet(const std::string& user_id,
                                                const std::string& tenant_id,
                                                const std::string& bet_type,
                                                const std::string& bet_value,
                                                const std::string& amount_str) {
    if (!is_supported_roulette(bet_type))
        throw CasinoError("Invalid bet type: " + bet_type);
    if (bet_type == "straight" && bet_value.empty())
        throw CasinoError("A straight bet requires a number.");
    Money amount = parse_amount(amount_str);
    Wallet& wallet = get_wallet(user_id);
    require_balance(wallet, amount);

    GameSession& session = session_store_.get_channel_session(tenant_id);
    std::string bet_key = bet_type;
    if (!bet_value.empty())
        bet_key = "straight__" + bet_value;
    std::map<std::string, std::string>& user_bets = session.roulette_bets[user_id];
    auto it = user_bets.find(bet_key);
    Money accumulated = it == user_bets.end() ? Money::zero() : Money(it->second);
    user_bets[bet_key] = accumulated.add(amount).to_decimal_string();
    session_store_.save_channel_session(tenant_id, session);

    wallet.debit(amount, "roulette");
    flush(wallet);
    return "Placed " + amount.formatted() + " on " + bet_key + ".";
}

static bool roulette_win(const std::string& bet_type, const RouletteResult& result) {
    if (bet_type == "straight")
        return false; // handled by caller with bet_value
    return is_even_money_win(bet_type, result);
}

std::string WageringService::spin_roulette(const std::string& tenant_id) {
    GameSession& session = session_store_.get_channel_session(tenant_id);
    if (session.roulette_bets.empty())
        return "No bets placed for this roulette spin.";

    int pocket = roulette_pocket();
    RouletteResult result;
    result.is_double_zero = pocket == 37;
    result.number = pocket == 37 ? 0 : pocket;
    std::string summary = "The wheel landed on pocket " + result.rendered() + ".";

    for (auto& [user_id, user_bets] : session.roulette_bets) {
        Wallet& wallet = get_wallet(user_id);
        for (auto& [bet_key, amount_str] : user_bets) {
            Money amount = Money(amount_str);
            std::string bet_type = bet_key;
            std::string bet_value;
            if (bet_key.rfind("straight__", 0) == 0) {
                bet_type = "straight";
                bet_value = bet_key.substr(10);
            }
            bool wins;
            if (bet_type == "straight") {
                wins = result.matches(bet_value);
            } else {
                wins = roulette_win(bet_type, result);
            }
            if (wins) {
                Money winnings = amount.multiply(roulette_multiplier(bet_type));
                wallet.credit(winnings, "roulette");
                wallet.record_wager(amount, winnings, "roulette");
                summary += "\nPlayer " + user_id + " wins " + winnings.formatted() + ".";
            } else {
                wallet.record_wager(amount, Money::zero(), "roulette");
            }
        }
        flush(wallet);
    }
    session.roulette_bets.clear();
    session_store_.save_channel_session(tenant_id, session);
    return summary;
}

std::string WageringService::place_craps_bet(const std::string& user_id,
                                             const std::string& tenant_id,
                                             const std::string& bet_type,
                                             const std::string& amount_str) {
    if (!is_supported_craps(bet_type))
        throw CasinoError("Invalid bet type: " + bet_type);
    Money amount = parse_amount(amount_str);
    Wallet& wallet = get_wallet(user_id);
    require_balance(wallet, amount);

    GameSession& session = session_store_.get_channel_session(tenant_id);
    if (session.craps_state == kPointPhase &&
        (bet_type == "pass_line" || bet_type == "dont_pass")) {
        std::string display = bet_type;
        for (size_t i = 0; i < display.size(); ++i) {
            if (display[i] == '_')
                display[i] = ' ';
        }
        throw CasinoError("Cannot place " + display + " when a point is established.");
    }
    std::map<std::string, std::string>& user_bets = session.craps_bets[user_id];
    auto it = user_bets.find(bet_type);
    Money accumulated = it == user_bets.end() ? Money::zero() : Money(it->second);
    user_bets[bet_type] = accumulated.add(amount).to_decimal_string();
    session_store_.save_channel_session(tenant_id, session);

    wallet.debit(amount, "craps");
    flush(wallet);
    return "Placed " + amount.formatted() + " on " + bet_type + ".";
}

bool WageringService::craps_is_winning(const std::string& bet_type, int roll_sum,
                                       const std::optional<int>& point, int die1, int die2) {
    if (bet_type == "pass_line") {
        if (!point)
            return roll_sum == 7 || roll_sum == 11;
        return roll_sum == *point;
    }
    if (bet_type == "dont_pass") {
        if (!point)
            return roll_sum == 2 || roll_sum == 3;
        return roll_sum == 7;
    }
    if (bet_type == "field")
        return roll_sum == 2 || roll_sum == 3 || roll_sum == 4 || roll_sum == 9 ||
               roll_sum == 10 || roll_sum == 11 || roll_sum == 12;
    if (bet_type.rfind("place_", 0) == 0) {
        int number = craps_number_suffix(bet_type);
        static const int place_numbers[] = {4, 5, 6, 8, 9, 10};
        bool valid = false;
        for (int n : place_numbers) {
            if (n == number)
                valid = true;
        }
        if (!valid)
            return false;
        return point.has_value() && roll_sum == number;
    }
    if (bet_type.rfind("hard_", 0) == 0) {
        int number = craps_number_suffix(bet_type);
        static const int hard_numbers[] = {4, 6, 8, 10};
        bool valid = false;
        for (int n : hard_numbers) {
            if (n == number)
                valid = true;
        }
        if (!valid)
            return false;
        return roll_sum == number && die1 == die2;
    }
    if (bet_type == "any_craps")
        return roll_sum == 2 || roll_sum == 3 || roll_sum == 12;
    if (bet_type == "any_seven")
        return roll_sum == 7;
    if (bet_type == "two")
        return roll_sum == 2;
    if (bet_type == "three")
        return roll_sum == 3;
    if (bet_type == "eleven")
        return roll_sum == 11;
    if (bet_type == "twelve")
        return roll_sum == 12;
    if (bet_type == "horn")
        return roll_sum == 2 || roll_sum == 3 || roll_sum == 11 || roll_sum == 12;
    return false;
}

bool WageringService::craps_is_push(const std::string& bet_type, int roll_sum,
                                    const std::optional<int>& point) {
    if (bet_type != "dont_pass")
        return false;
    return !point.has_value() && roll_sum == 12;
}

void WageringService::advance_craps_phase(int roll_sum, const std::optional<int>& point,
                                          int* next_state, std::optional<int>* next_point) {
    if (!point) {
        if (roll_sum == 4 || roll_sum == 5 || roll_sum == 6 || roll_sum == 8 ||
            roll_sum == 9 || roll_sum == 10) {
            *next_state = kPointPhase;
            *next_point = roll_sum;
            return;
        }
        *next_state = kComeOutPhase;
        *next_point = std::nullopt;
        return;
    }
    if (roll_sum == *point || roll_sum == 7) {
        *next_state = kComeOutPhase;
        *next_point = std::nullopt;
        return;
    }
    *next_state = kPointPhase;
    *next_point = point;
}

std::string WageringService::roll_craps(const std::string& tenant_id) {
    GameSession& session = session_store_.get_channel_session(tenant_id);
    if (session.craps_bets.empty())
        return "No bets placed for this craps roll.";

    int die1, die2;
    craps_roll(&die1, &die2);
    int roll_sum = die1 + die2;
    std::optional<int> point = session.craps_point;
    std::string summary =
        "Rolled " + std::to_string(die1) + " + " + std::to_string(die2) + " = " +
        std::to_string(roll_sum) + ".";

    for (auto& [user_id, user_bets] : session.craps_bets) {
        Wallet& wallet = get_wallet(user_id);
        for (auto& [bet_type, amount_str] : user_bets) {
            Money amount = Money(amount_str);
            CrapsResolution resolution = resolve_craps_bet(bet_type, amount, roll_sum, point, die1, die2);
            if (resolution.kind == CrapsResolution::Kind::Win) {
                wallet.credit(resolution.winnings, "craps");
                wallet.record_wager(amount, resolution.winnings, "craps");
                summary += "\nPlayer " + user_id + " wins " +
                           resolution.winnings.formatted() + " on " + bet_type + ".";
            } else if (resolution.kind == CrapsResolution::Kind::Push) {
                wallet.credit(amount, "craps");
                wallet.record_wager(amount, Money::zero(), "craps");
                summary += "\nPlayer " + user_id + " pushes on " + bet_type + ".";
            } else {
                wallet.record_wager(amount, Money::zero(), "craps");
                summary += "\nPlayer " + user_id + " loses " + bet_type + ".";
            }
        }
        flush(wallet);
    }
    session.craps_bets.clear();
    advance_craps_phase(roll_sum, point, &session.craps_state, &session.craps_point);
    session_store_.save_channel_session(tenant_id, session);
    return summary;
}

std::string WageringService::spin_zeus(const std::string& user_id) {
    Wallet& wallet = get_wallet(user_id);
    Money wager = Money::zero();
    if (wallet.free_spins() > 0) {
        wallet.redeem_free_spin();
    } else {
        require_balance(wallet, zeus_spin_cost_);
        wallet.debit(zeus_spin_cost_, "zeus");
        wager = zeus_spin_cost_;
    }
    int rows = 5, cols = 5;
    std::vector<int> grid_data = zeus_grid(rows, cols);
    ReelGrid grid(rows, cols, grid_data);
    LineEvaluationStrategy strategy;
    GridWinEvaluator evaluator(grid, strategy);
    std::vector<WinningLine> winnings = evaluator.evaluate();
    PayoutTable table;
    PayoutCalculator calculator(table);
    int64_t coins;
    int free_spins;
    calculator.calculate(winnings, &coins, &free_spins);
    // Coins are whole currency units, not cents (Python: Money(Decimal("50"))).
    Money coin_money = Money(std::to_string(coins));
    wallet.record_wager(wager, coin_money, "zeus");
    if (coins > 0)
        wallet.credit(coin_money, "zeus");
    if (free_spins > 0)
        wallet.award_free_spins(free_spins);
    flush(wallet);

    std::string rows_text;
    for (int r = 0; r < rows; ++r) {
        if (r > 0)
            rows_text += "\n";
        for (int c = 0; c < cols; ++c) {
            if (c > 0)
                rows_text += " | ";
            rows_text += ZEUS_SYMBOLS[grid.symbol(r, c)];
        }
    }
    std::string message = "```\n" + rows_text + "\n```";
    if (coin_money.is_positive()) {
        message += "\nWon " + coin_money.formatted() + " coins and " +
                   std::to_string(free_spins) + " free spins.";
    } else {
        message += "\nNo winning lines this spin.";
    }
    message += "\nBalance: " + wallet.balance().formatted() + " | Free spins: " +
               std::to_string(wallet.free_spins());
    return message;
}

std::string WageringService::reset_wallet(const std::string& user_id) {
    Wallet& wallet = get_wallet(user_id);
    wallet.reset(starting_balance_);
    flush(wallet);
    return "Balance reset to " + starting_balance_.formatted() + ".";
}

CrapsResolution resolve_craps_bet(const std::string& bet_type, const Money& amount,
                                  int roll_sum, const std::optional<int>& point, int die1,
                                  int die2) {
    if (WageringService::craps_is_push(bet_type, roll_sum, point)) {
        return CrapsResolution{CrapsResolution::Kind::Push, Money::zero()};
    }
    if (!WageringService::craps_is_winning(bet_type, roll_sum, point, die1, die2)) {
        return CrapsResolution{CrapsResolution::Kind::Loss, Money::zero()};
    }
    int denominator;
    int numerator = craps_multiplier_num(bet_type, roll_sum, &denominator);
    Money winnings = amount.multiply_fraction(numerator, denominator);
    return CrapsResolution{CrapsResolution::Kind::Win, winnings};
}

} // namespace bb