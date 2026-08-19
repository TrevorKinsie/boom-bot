/*
 * bb_casino.h - unified wagering application service.
 *
 * Mirrors boombot/casino/wagering/application/service/wagering_application_service.py:
 * balance queries, roulette / craps wagering flows, Zeus spins, and wallet
 * reset. Every user-facing string is emitted verbatim. Outcomes are produced
 * by overridable decision hooks (scriptable in tests; random in production).
 */
#ifndef BB_CASINO_H
#define BB_CASINO_H

#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "bb_event_store.h"
#include "bb_leaderboard.h"
#include "bb_money.h"
#include "bb_wallet.h"
#include "bb_zeus.h"

namespace bb {

// Raised for user-facing casino errors; the message is the reply text.
class CasinoError : public std::runtime_error {
public:
    explicit CasinoError(const std::string& msg) : std::runtime_error(msg) {}
};

// Per-channel game session: outstanding wagers and craps table state.
struct GameSession {
    // roulette_bets: user_id -> place_roulette_bet key -> amount string
    std::map<std::string, std::map<std::string, std::string>> roulette_bets;
    // craps_bets: user_id -> bet type -> amount string
    std::map<std::string, std::map<std::string, std::string>> craps_bets;
    int craps_state = 1; // 1 = come-out, 2 = point
    std::optional<int> craps_point;

    static GameSession fresh() { return GameSession{}; }
};

// In-memory session store (single process), mirroring InMemoryGameSessionStore.
class InMemoryGameSessionStore {
public:
    GameSession& get_channel_session(const std::string& channel_id);
    void save_channel_session(const std::string& channel_id, const GameSession& session);

private:
    std::map<std::string, GameSession> sessions_;
};

// Unified wagering application service.
class WageringService {
public:
    WageringService(WalletRepository& repository, JsonEventStore& store,
                    InMemoryGameSessionStore& session_store,
                    InProcessEventBus& event_bus,
                    const Money& starting_balance = Money(std::string("100.00")),
                    const Money& zeus_spin_cost = Money(std::string("10.00")));

    // Decision hooks. Roulette pockets are 0..36 plus 37 which renders "00".
    std::function<int()> roulette_pocket;
    std::function<void(int* die1, int* die2)> craps_roll;
    // Grid symbol indices, 0..8 (8 = Zeus wild), rows*cols entries.
    std::function<std::vector<int>(int rows, int cols)> zeus_grid;

    Wallet& get_wallet(const std::string& user_id);
    WalletRepository& repository() { return repository_; }
    JsonEventStore& event_store() { return store_; }

    // --- Queries ---
    Money get_balance(const std::string& user_id);
    std::string get_balance_text(const std::string& user_id);

    // --- Roulette ---
    // Throws CasinoError with the exact Python message on invalid input.
    std::string place_roulette_bet(const std::string& user_id, const std::string& tenant_id,
                                   const std::string& bet_type, const std::string& bet_value,
                                   const std::string& amount_str);
    std::string spin_roulette(const std::string& tenant_id);

    // --- Craps ---
    std::string place_craps_bet(const std::string& user_id, const std::string& tenant_id,
                                const std::string& bet_type, const std::string& amount_str);
    std::string roll_craps(const std::string& tenant_id);

    // --- Zeus ---
    std::string spin_zeus(const std::string& user_id);

    // --- Reset ---
    std::string reset_wallet(const std::string& user_id);

    // --- Cluster state (visible to the facade) ---
    static void advance_craps_phase(int roll_sum, const std::optional<int>& point,
                                    int* next_state, std::optional<int>* next_point);

    // Craps rules, shared with tests for resolution verification.
    static bool craps_is_winning(const std::string& bet_type, int roll_sum,
                                 const std::optional<int>& point, int die1, int die2);
    static bool craps_is_push(const std::string& bet_type, int roll_sum,
                              const std::optional<int>& point);

private:
    void flush(Wallet& wallet);
    Money parse_amount(const std::string& amount_str);
    void require_balance(Wallet& wallet, const Money& amount);

    WalletRepository& repository_;
    JsonEventStore& store_;
    InMemoryGameSessionStore& session_store_;
    InProcessEventBus* event_bus_;
    Money starting_balance_;
    Money zeus_spin_cost_;
    std::map<std::string, std::unique_ptr<Wallet>> wallet_cache_;
};

// Opaque outcome of a craps bet resolution (mirrors BetResolution).
struct CrapsResolution {
    enum class Kind { Win, Loss, Push } kind = Kind::Loss;
    Money winnings = Money::zero();
};

// Resolve one craps bet against a roll context (reference rules).
CrapsResolution resolve_craps_bet(const std::string& bet_type, const Money& amount,
                                  int roll_sum, const std::optional<int>& point, int die1,
                                  int die2);

// Roulette outcome value: int pockets 0..36 plus "00".
struct RouletteResult {
    int number = 0;  // 0..36
    bool is_double_zero = false;
    std::string rendered() const { return is_double_zero ? "00" : std::to_string(number); }
    bool matches(const std::string& pocket) const {
        return is_double_zero ? pocket == "00" : pocket == std::to_string(number);
    }
};

} // namespace bb

#endif // BB_CASINO_H