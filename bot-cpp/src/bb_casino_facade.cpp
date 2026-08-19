/*
 * bb_casino_facade.cpp - see bb_casino_facade.h.
 */
#include "bb_casino_facade.h"

#include <cctype>
#include <string>
#include <utility>
#include <vector>

#include "bb_casino.h"
#include "bb_leaderboard.h"
#include "bb_util.h"
#include "bb_wallet.h"

namespace bb {

void CasinoFacade::register_identity(const std::string& user_id,
                                     const std::string& display_name) {
    projection_->register_name(user_id, display_name);
}

std::string CasinoFacade::wallet_command(const std::string& user_id) {
    return service_->get_balance_text(user_id);
}

std::string CasinoFacade::leaderboard_command() {
    std::vector<PlayerStanding> ranking = projection_->get_leaderboard(10);
    if (ranking.empty())
        return "No players have any coins yet.";
    std::string text = "Leaderboard";
    for (size_t i = 0; i < ranking.size(); ++i) {
        text += "\n" + std::to_string(i + 1) + ". " + ranking[i].display_name +
                " - " + ranking[i].balance.formatted();
    }
    return text;
}

std::string CasinoFacade::reset_wallet_command(const std::string& user_id) {
    try {
        return service_->reset_wallet(user_id);
    } catch (const CasinoError& e) {
        return e.what();
    }
}

std::string CasinoFacade::roulette_command(const std::string& user_id,
                                           const std::string& tenant_id,
                                           const std::vector<std::string>& args) {
    if (args.size() < 2) {
        return "Usage: /roulette <type> [number] <amount>\n"
               "e.g. /roulette red 10, /roulette straight 7 10";
    }
    std::string bet_type;
    for (char c : args[0])
        bet_type.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    std::string bet_value;
    std::string amount;
    if (bet_type == "straight") {
        if (args.size() != 3)
            return "Usage: /roulette straight <number> <amount>";
        bet_value = args[1];
        amount = args[2];
    } else {
        amount = args[1];
    }
    try {
        return service_->place_roulette_bet(user_id, tenant_id, bet_type, bet_value, amount);
    } catch (const CasinoError& e) {
        return e.what();
    }
}

std::string CasinoFacade::roulette_spin_command(const std::string& tenant_id) {
    try {
        return service_->spin_roulette(tenant_id);
    } catch (const CasinoError& e) {
        return e.what();
    }
}

std::string CasinoFacade::craps_command(const std::string& user_id,
                                        const std::string& tenant_id,
                                        const std::vector<std::string>& args) {
    if (args.size() < 2) {
        return "Usage: /craps <type> <amount>\n"
               "e.g. /craps pass_line 10, /craps any_seven 5";
    }
    try {
        std::string bet_type;
        for (char c : args[0])
            bet_type.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
        return service_->place_craps_bet(user_id, tenant_id, bet_type, args[1]);
    } catch (const CasinoError& e) {
        return e.what();
    }
}

std::string CasinoFacade::craps_roll_command(const std::string& tenant_id) {
    try {
        return service_->roll_craps(tenant_id);
    } catch (const CasinoError& e) {
        return e.what();
    }
}

std::pair<std::string, bool> CasinoFacade::zeus_command(const std::string& user_id) {
    try {
        return std::make_pair(zeus_markdown_v2(service_->spin_zeus(user_id)), true);
    } catch (const CasinoError& e) {
        return std::make_pair(e.what(), false);
    }
}

std::string zeus_markdown_v2(const std::string& text) {
    // Text is "```\n<grid>\n```\n<rest>". Escape the rest, keep the fence raw.
    size_t fence_close = text.find("```\n", 3);
    if (fence_close == std::string::npos)
        return markdown_escape_v2(text);
    std::string fence = text.substr(0, fence_close + 3);
    std::string rest = text.substr(fence_close + 4);
    return fence + "\n" + markdown_escape_v2(rest);
}

} // namespace bb