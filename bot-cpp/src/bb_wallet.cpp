/*
 * bb_wallet.cpp - see bb_wallet.h.
 */
#include "bb_wallet.h"

#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>

#include "bb_event_store.h"
#include "bb_json.h"
#include "bb_money.h"

namespace bb {

namespace {

constexpr const char* kWalletCreated = "WalletCreatedEvent";
constexpr const char* kFundsDebited = "FundsDebitedEvent";
constexpr const char* kFundsCredited = "FundsCreditedEvent";
constexpr const char* kWalletReset = "WalletResetEvent";
constexpr const char* kFreeSpinAwarded = "FreeSpinAwardedEvent";
constexpr const char* kFreeSpinRedeemed = "FreeSpinRedeemedEvent";
constexpr const char* kWageredRecorded = "WageredRecordedEvent";

} // namespace

Wallet::Wallet(std::string identity) : identity_(std::move(identity)), balance_(Money::zero()),
                                       total_wagered_(Money::zero()),
                                       total_won_(Money::zero()),
                                       biggest_win_(Money::zero()) {}

void Wallet::raise_event(const std::string& type, Json payload) {
    int64_t next = version_.number() + 1;
    WalletEvent event = WalletEvent::create(type, identity_, next, std::move(payload));
    apply(event);
    version_ = AggregateVersion(next);
    uncommitted_.push_back(std::move(event));
}

void Wallet::provision(const Money& starting_balance) {
    Json payload = Json::object();
    payload.set("starting_balance", starting_balance.to_decimal_string());
    raise_event(kWalletCreated, std::move(payload));
}

void Wallet::debit(const Money& amount, const std::string& reason) {
    if (amount.is_zero())
        return;
    if (amount.is_greater_than(balance_)) {
        throw WalletError("Insufficient funds: balance " + balance_.formatted() +
                          " cannot cover debit " + amount.formatted() + ".");
    }
    Json payload = Json::object();
    payload.set("amount", amount.to_decimal_string());
    payload.set("reason", reason);
    raise_event(kFundsDebited, std::move(payload));
}

void Wallet::credit(const Money& amount, const std::string& reason) {
    if (amount.is_zero())
        return;
    Json payload = Json::object();
    payload.set("amount", amount.to_decimal_string());
    payload.set("reason", reason);
    raise_event(kFundsCredited, std::move(payload));
}

void Wallet::reset(const Money& reset_balance) {
    Json payload = Json::object();
    payload.set("reset_balance", reset_balance.to_decimal_string());
    raise_event(kWalletReset, std::move(payload));
}

void Wallet::award_free_spins(int64_t count) {
    if (count <= 0)
        return;
    Json payload = Json::object();
    payload.set("count", count);
    raise_event(kFreeSpinAwarded, std::move(payload));
}

void Wallet::redeem_free_spin() {
    if (free_spins_ <= 0)
        throw WalletError("No free spins are available to redeem.");
    Json payload = Json::object();
    payload.set("count", int64_t(1));
    raise_event(kFreeSpinRedeemed, std::move(payload));
}

void Wallet::record_wager(const Money& wager, const Money& win, const std::string& game) {
    Json payload = Json::object();
    payload.set("wager", wager.to_decimal_string());
    payload.set("win", win.to_decimal_string());
    payload.set("game", game);
    raise_event(kWageredRecorded, std::move(payload));
}

void Wallet::apply(const WalletEvent& event) {
    if (event.event_type == kWalletCreated) {
        balance_ = Money::from_cents(event.starting_balance_cents());
    } else if (event.event_type == kFundsDebited) {
        balance_ = balance_.subtract(Money(event.amount()));
    } else if (event.event_type == kFundsCredited) {
        balance_ = balance_.add(Money(event.amount()));
    } else if (event.event_type == kWalletReset) {
        balance_ = Money::from_cents(event.reset_balance_cents());
    } else if (event.event_type == kFreeSpinAwarded) {
        free_spins_ += event.count();
    } else if (event.event_type == kFreeSpinRedeemed) {
        free_spins_ = std::max<int64_t>(0, free_spins_ - event.count());
    } else if (event.event_type == kWageredRecorded) {
        total_wagered_ = total_wagered_.add(Money::from_cents(event.wager_cents()));
        total_won_ = total_won_.add(Money::from_cents(event.win_cents()));
        games_played_ += 1;
        Money win = Money::from_cents(event.win_cents());
        if (win.is_greater_than(biggest_win_))
            biggest_win_ = win;
    } else {
        throw WalletError("Unhandled wallet event type: " + event.event_type);
    }
}

Json Wallet::to_state_dictionary() const {
    Json state = Json::object();
    state.set("balance", balance_.to_decimal_string());
    state.set("total_wagered", total_wagered_.to_decimal_string());
    state.set("total_won", total_won_.to_decimal_string());
    state.set("biggest_win", biggest_win_.to_decimal_string());
    state.set("free_spins", free_spins_);
    state.set("games_played", games_played_);
    return state;
}

Wallet Wallet::from_state_dictionary(const std::string& identity, const Json& state) {
    Wallet wallet(identity);
    wallet.balance_ = Money(state.get_string("balance", "0"));
    wallet.total_wagered_ = Money(state.get_string("total_wagered", "0"));
    wallet.total_won_ = Money(state.get_string("total_won", "0"));
    wallet.biggest_win_ = Money(state.get_string("biggest_win", "0"));
    wallet.free_spins_ = state.get_int("free_spins", 0);
    wallet.games_played_ = state.get_int("games_played", 0);
    return wallet;
}

Json Wallet::to_snapshot_state() const {
    Json state = to_state_dictionary();
    state.set("version", version_.number());
    return state;
}

Wallet Wallet::from_snapshot_state(const std::string& identity, const Json& snapshot) {
    Wallet wallet = from_state_dictionary(identity, snapshot);
    wallet.version_ = AggregateVersion(snapshot.get_int("version", 0));
    return wallet;
}

void Wallet::commit() { uncommitted_.clear(); }

WalletRepository::WalletRepository(JsonEventStore& store, SnapshotPolicy policy,
                                   const Money& starting_balance)
    : store_(store), policy_(policy), starting_balance_(starting_balance) {}

std::unique_ptr<Wallet> WalletRepository::find(const std::string& user_id) const {
    auto snapshot = store_.load_snapshot(user_id);
    std::unique_ptr<Wallet> wallet;
    std::vector<WalletEvent> replay;
    if (snapshot.has_value()) {
        int64_t snapshot_version = snapshot->first;
        wallet = std::make_unique<Wallet>(
            Wallet::from_snapshot_state(user_id, snapshot->second));
        std::vector<WalletEvent> rest = store_.load(user_id);
        for (const WalletEvent& event : rest) {
            if (event.version > snapshot_version)
                replay.push_back(event);
        }
    } else {
        replay = store_.load(user_id);
    }
    if (replay.empty() && !wallet)
        return nullptr;
    if (wallet) {
        std::sort(replay.begin(), replay.end(),
                  [](const WalletEvent& a, const WalletEvent& b) { return a.version < b.version; });
        for (const WalletEvent& event : replay)
            wallet->apply(event);
        if (!replay.empty())
            wallet->version_ = AggregateVersion(replay.back().version);
        wallet->commit();
    } else {
        // Fresh aggregate from pure event replay.
        std::sort(replay.begin(), replay.end(),
                  [](const WalletEvent& a, const WalletEvent& b) { return a.version < b.version; });
        wallet = std::make_unique<Wallet>(user_id);
        for (const WalletEvent& event : replay)
            wallet->apply(event);
        wallet->version_ = AggregateVersion(replay.back().version);
        wallet->commit();
    }
    return wallet;
}

std::unique_ptr<Wallet> WalletRepository::load_or_provision(const std::string& user_id) {
    std::unique_ptr<Wallet> wallet = find(user_id);
    if (!wallet) {
        wallet = std::make_unique<Wallet>(user_id);
        wallet->provision(starting_balance_);
    }
    return wallet;
}

void WalletRepository::save(Wallet& wallet) {
    const std::vector<WalletEvent>& staged = wallet.uncommitted_events();
    if (staged.empty())
        return;
    int64_t committed = wallet.version().number() - static_cast<int64_t>(staged.size());
    store_.append(wallet.identity(), staged);
    if (policy_.should_take_snapshot(static_cast<int64_t>(staged.size()), committed)) {
        store_.save_snapshot(wallet.identity(), wallet.version().number(),
                             wallet.to_snapshot_state());
    }
    wallet.commit();
}

} // namespace bb