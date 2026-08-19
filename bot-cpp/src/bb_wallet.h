/*
 * bb_wallet.h - event-sourced Wallet aggregate + repository.
 *
 * Mirrors boombot/casino/wagering/domain/model/wallet.py and
 * wagering/infrastructure/persistence/wallet_repository.py: every mutation
 * raises a domain event; state is a fold of applied events; snapshot state is
 * the state dictionary plus a "version" key.
 */
#ifndef BB_WALLET_H
#define BB_WALLET_H

#include <cstdint>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "bb_event_store.h"
#include "bb_json.h"
#include "bb_money.h"

namespace bb {

// Raised for wallet invariant violations, e.g. overdrawing debits.
class WalletError : public std::runtime_error {
public:
    explicit WalletError(const std::string& msg) : std::runtime_error(msg) {}
};

// Event-sourced wallet aggregate.
class Wallet {
public:
    explicit Wallet(std::string identity);

    const std::string& identity() const { return identity_; }
    AggregateVersion version() const { return version_; }
    Money balance() const { return balance_; }
    Money total_wagered() const { return total_wagered_; }
    Money total_won() const { return total_won_; }
    Money biggest_win() const { return biggest_win_; }
    int64_t free_spins() const { return free_spins_; }
    int64_t games_played() const { return games_played_; }

    bool has_uncommitted_events() const { return !uncommitted_.empty(); }
    const std::vector<WalletEvent>& uncommitted_events() const { return uncommitted_; }

    // --- Command / mutation operations ---
    void provision(const Money& starting_balance);
    // No-op for a zero amount; throws WalletError on overdraw.
    void debit(const Money& amount, const std::string& reason);
    // No-op for a zero amount.
    void credit(const Money& amount, const std::string& reason);
    void reset(const Money& reset_balance);
    // No-op for count <= 0.
    void award_free_spins(int64_t count);
    // Throws WalletError when no free spins are available.
    void redeem_free_spin();
    void record_wager(const Money& wager, const Money& win, const std::string& game);

    // --- Event application (write-model fold) ---
    void apply(const WalletEvent& event);

    // --- Snapshot / serialization ---
    Json to_state_dictionary() const;
    static Wallet from_state_dictionary(const std::string& identity, const Json& state);
    // State dictionary + "version" key.
    Json to_snapshot_state() const;
    static Wallet from_snapshot_state(const std::string& identity, const Json& snapshot);

    // Clear staged events; called after persisted.
    void commit();

private:
    void raise_event(const std::string& type, Json payload);

    friend class WalletRepository;

    std::string identity_;
    AggregateVersion version_;
    Money balance_;
    Money total_wagered_;
    Money total_won_;
    Money biggest_win_;
    int64_t free_spins_ = 0;
    int64_t games_played_ = 0;
    std::vector<WalletEvent> uncommitted_;
};

// Loads/saves Wallet aggregates through the JSON event store, replaying
// snapshot + events and staging the uncommitted batch.
class WalletRepository {
public:
    WalletRepository(JsonEventStore& store, SnapshotPolicy policy,
                     const Money& starting_balance);
    const Money& starting_balance() const { return starting_balance_; }

    // Load from snapshot + event replay, or null when absent.
    std::unique_ptr<Wallet> find(const std::string& user_id) const;
    // find(), or a freshly provisioned wallet with a staged WalletCreatedEvent.
    std::unique_ptr<Wallet> load_or_provision(const std::string& user_id);
    // Append staged events, snapshot per policy, then commit the aggregate.
    void save(Wallet& wallet);

private:
    JsonEventStore& store_;
    SnapshotPolicy policy_;
    Money starting_balance_;
};

// Load a wallet from snapshot + log replay. Shared by the facade and the
// service so both observe the same repository semantics.
inline std::unique_ptr<Wallet> load_wallet(JsonEventStore& store, const SnapshotPolicy& policy,
                                           const Money& starting, const std::string& user_id) {
    WalletRepository repository(store, policy, starting);
    return repository.load_or_provision(user_id);
}

} // namespace bb

#endif // BB_WALLET_H