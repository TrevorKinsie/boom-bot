/*
 * bb_leaderboard.h - in-process event bus + leaderboard read-model.
 *
 * Mirrors boombot/casino/application/event/event_bus.py and
 * reporting/infrastructure/leaderboard_projection.py: wallet events are
 * folded into in-memory standings; display names are registered by the
 * presentation layer.
 */
#ifndef BB_LEADERBOARD_H
#define BB_LEADERBOARD_H

#include <functional>
#include <map>
#include <string>
#include <vector>

#include "bb_event_store.h"
#include "bb_money.h"

namespace bb {

// One player standing on the leaderboard.
struct PlayerStanding {
    PlayerStanding() : balance(Money::zero()), total_won(Money::zero()),
                       total_wagered(Money::zero()) {}
    std::string user_id;
    std::string display_name;
    Money balance;
    Money total_won;
    Money total_wagered;
    int64_t games_played = 0;
};

// Folds wallet events into in-memory standings (mirrors LeaderboardProjection).
class LeaderboardProjection {
public:
    void register_name(const std::string& user_id, const std::string& display_name);
    void notify(const WalletEvent& event);
    // Ranked by balance descending (stable; ties keep standing order).
    std::vector<PlayerStanding> get_leaderboard(int64_t size) const;
    const PlayerStanding* get_standing(const std::string& user_id) const;
    void clear();

private:
    std::map<std::string, PlayerStanding> standings_;
    std::map<std::string, std::string> display_names_;
};

// Synchronous in-process publisher/subscriber (mirrors InProcessEventBus).
class InProcessEventBus {
public:
    using Observer = std::function<void(const WalletEvent&)>;

    void subscribe(std::function<bool(const std::string&)> matches, Observer observer);
    // Observe every published event.
    void subscribe_all(Observer observer);
    void publish(const WalletEvent& event);

private:
    struct Subscription {
        std::function<bool(const std::string&)> matches;
        Observer observer;
    };
    std::vector<Subscription> subscriptions_;
    std::vector<Observer> catch_all_;
};

} // namespace bb

#endif // BB_LEADERBOARD_H