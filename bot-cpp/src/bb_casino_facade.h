/*
 * bb_casino_facade.h - casino command facade for the Telegram shell.
 *
 * Mirrors boombot/casino/infrastructure/telegram/casino_telegram_facade.py:
 * usage strings, wallet/leaderboard formatting, and error-to-reply mapping.
 * The zeus reply is sent with MarkdownV2; the fence block is preserved raw
 * while the trailing lines are escaped (the Python facade sends the raw text,
 * which Telegram rejects; this makes /zeus actually deliverable).
 */
#ifndef BB_CASINO_FACADE_H
#define BB_CASINO_FACADE_H

#include <string>
#include <vector>

#include "bb_casino.h"
#include "bb_event_store.h"
#include "bb_leaderboard.h"
#include "bb_wallet.h"

namespace bb {

class CasinoFacade {
public:
    CasinoFacade(WageringService& service, LeaderboardProjection& projection,
                 InProcessEventBus& bus)
        : service_(&service), projection_(&projection), bus_(&bus) {}

    WageringService& service() { return *service_; }
    LeaderboardProjection& projection() { return *projection_; }

    // Register the display name for later leaderboard use.
    void register_identity(const std::string& user_id, const std::string& display_name);

    std::string wallet_command(const std::string& user_id);
    std::string leaderboard_command();
    std::string reset_wallet_command(const std::string& user_id);

    // args excludes the command word.
    std::string roulette_command(const std::string& user_id, const std::string& tenant_id,
                                 const std::vector<std::string>& args);
    std::string roulette_spin_command(const std::string& tenant_id);
    std::string craps_command(const std::string& user_id, const std::string& tenant_id,
                              const std::vector<std::string>& args);
    std::string craps_roll_command(const std::string& tenant_id);

    // Returns (text, parse_mode_markdown_v2).
    std::pair<std::string, bool> zeus_command(const std::string& user_id);

private:
    WageringService* service_;
    LeaderboardProjection* projection_;
    InProcessEventBus* bus_;
};

// Escape all MarkdownV2 specials outside the ``` code fence of a zeus reply.
std::string zeus_markdown_v2(const std::string& text);

} // namespace bb

#endif // BB_CASINO_FACADE_H