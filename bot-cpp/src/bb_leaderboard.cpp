/*
 * bb_leaderboard.cpp - see bb_leaderboard.h.
 */
#include "bb_leaderboard.h"

#include <algorithm>
#include <string>
#include <vector>

#include "bb_event_store.h"
#include "bb_money.h"

namespace bb {

void LeaderboardProjection::register_name(const std::string& user_id,
                                          const std::string& display_name) {
    display_names_[user_id] = display_name;
    auto it = standings_.find(user_id);
    if (it != standings_.end())
        it->second.display_name = display_name;
}

void LeaderboardProjection::notify(const WalletEvent& event) {
    static const char* kFoldable[] = {
        "WalletCreatedEvent", "FundsDebitedEvent", "FundsCreditedEvent",
        "WalletResetEvent",   "WageredRecordedEvent",
    };
    bool fold = false;
    for (const char* type : kFoldable) {
        if (event.event_type == type) {
            fold = true;
            break;
        }
    }
    if (!fold)
        return;

    const std::string& user_id = event.aggregate_id;
    PlayerStanding current;
    auto it = standings_.find(user_id);
    if (it != standings_.end())
        current = it->second;

    if (event.event_type == "WalletCreatedEvent") {
        current.balance = Money::from_cents(event.starting_balance_cents());
    } else if (event.event_type == "FundsDebitedEvent") {
        current.balance = current.balance.subtract(Money(event.amount()));
    } else if (event.event_type == "FundsCreditedEvent") {
        current.balance = current.balance.add(Money(event.amount()));
    } else if (event.event_type == "WalletResetEvent") {
        current.balance = Money::from_cents(event.reset_balance_cents());
    } else if (event.event_type == "WageredRecordedEvent") {
        current.total_wagered = current.total_wagered.add(Money::from_cents(event.wager_cents()));
        current.total_won = current.total_won.add(Money::from_cents(event.win_cents()));
        current.games_played += 1;
    }

    current.user_id = user_id;
    auto name_it = display_names_.find(user_id);
    current.display_name = name_it == display_names_.end() ? user_id : name_it->second;
    standings_[user_id] = current;
}

std::vector<PlayerStanding> LeaderboardProjection::get_leaderboard(int64_t size) const {
    std::vector<PlayerStanding> ranked;
    ranked.reserve(standings_.size());
    for (const auto& [id, standing] : standings_)
        ranked.push_back(standing);
    std::stable_sort(ranked.begin(), ranked.end(),
                     [](const PlayerStanding& a, const PlayerStanding& b) {
                         return a.balance.cents() > b.balance.cents();
                     });
    if (size < 0 || static_cast<int64_t>(ranked.size()) <= size)
        return ranked;
    ranked.resize(static_cast<size_t>(size));
    return ranked;
}

const PlayerStanding* LeaderboardProjection::get_standing(const std::string& user_id) const {
    auto it = standings_.find(user_id);
    return it == standings_.end() ? nullptr : &it->second;
}

void LeaderboardProjection::clear() {
    standings_.clear();
    display_names_.clear();
}

void InProcessEventBus::subscribe(std::function<bool(const std::string&)> matches,
                                  Observer observer) {
    subscriptions_.push_back(Subscription{std::move(matches), std::move(observer)});
}

void InProcessEventBus::subscribe_all(Observer observer) {
    catch_all_.push_back(std::move(observer));
}

void InProcessEventBus::publish(const WalletEvent& event) {
    for (const Subscription& subscription : subscriptions_) {
        if (subscription.matches(event.event_type))
            subscription.observer(event);
    }
    for (const Observer& observer : catch_all_)
        observer(event);
}

} // namespace bb