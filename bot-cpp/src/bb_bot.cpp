/*
 * bb_bot.cpp - application shell: long-polling Telegram loop.
 *
 * Mirrors boombot/core/bot.py: boots config + data, registers the command
 * handlers, and polls getUpdates (long polling) forever, replying per update.
 *
 * Casino commands (wallet / leaderboard / resetwallet / roulette /
 * roulettespin / craps / crapsroll / zeus) run through the in-process
 * WageringService; /zeus sends with MarkdownV2 parse mode. Community chess
 * (chess / newgame / move / resign / draw / board) runs against the in-house
 * engine through ChessService.
 */
#include <algorithm>
#include <csignal>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "bb_casino.h"
#include "bb_casino_facade.h"
#include "bb_chess.h"
#include "bb_config.h"
#include "bb_data.h"
#include "bb_event_store.h"
#include "bb_handlers.h"
#include "bb_leaderboard.h"
#include "bb_llm.h"
#include "bb_log.h"
#include "bb_money.h"
#include "bb_telegram.h"
#include "bb_util.h"
#include "bb_wallet.h"

namespace {

volatile sig_atomic_t g_stop = 0;

void on_signal(int) {
    g_stop = 1;
}

std::string bot_username_cache;

// Casino components, mirroring the casino application context: JSON event
// store at CASINO_EVENT_STORE_JSON (default <DATA_DIR>/casino_events.json)
// with snapshots beside it, snapshot threshold from CASINO_SNAPSHOT_THRESHOLD,
// starting balance and zeus cost from config.
struct CasinoContext {
    bb::JsonEventStore store;
    bb::SnapshotPolicy policy;
    bb::WalletRepository repository;
    bb::InMemoryGameSessionStore sessions;
    bb::InProcessEventBus bus;
    bb::WageringService service;
    bb::LeaderboardProjection projection;
    bb::CasinoFacade facade;

    CasinoContext()
        : store(bb::cfg::CASINO_EVENT_STORE_JSON_FILE,
                bb::cfg::CASINO_EVENT_STORE_JSON_FILE + ".snapshots"),
          policy(bb::cfg::CASINO_SNAPSHOT_THRESHOLD > 0 ? bb::cfg::CASINO_SNAPSHOT_THRESHOLD : 50),
          repository(store, policy, bb::Money(bb::cfg::CASINO_STARTING_BALANCE)),
          service(repository, store, sessions, bus,
                  bb::Money(bb::cfg::CASINO_STARTING_BALANCE),
                  bb::Money(bb::cfg::ZEUS_SPIN_COST)),
          facade(service, projection, bus) {
        std::filesystem::create_directories("data");
        std::filesystem::create_directories(store.snapshot_dir());
        bus.subscribe_all(
            [this](const bb::WalletEvent& event) { projection.notify(event); });
    }
};

CasinoContext* g_casino = nullptr;

// Chess: a persistent engine process handled by ChessService; games are
// stored per chat in CHESS_GAMES_FILE alongside the other bot data.
struct ChessContext {
    bb::chess::GameStore store;
    bb::chess::UciClient engine;
    bb::chess::ChessService service;

    ChessContext()
        : store(bb::cfg::CHESS_GAMES_FILE),
          engine(bb::cfg::CHESS_ENGINE_PATH),
          service(engine, store) {
        store.load();
    }
};

ChessContext* g_chess = nullptr;

void handle_chess_command(const bb::TelegramMessage& msg,
                          const std::string& command,
                          const std::vector<std::string>& args) {
    std::string display_name = msg.from.full_name();
    if (display_name.empty() && !msg.from.username.empty())
        display_name = msg.from.username;
    if (display_name.empty())
        display_name = "Player";

    std::string reply;
    if (command == "chess" || command == "newgame") {
        int difficulty = 20;
        if (!args.empty()) {
            auto parsed = bb::parse_int(args[0]);
            if (parsed.has_value() && *parsed >= 0 && *parsed <= 20)
                difficulty = static_cast<int>(*parsed);
        }
        reply = g_chess->service.start(msg.chat.id, display_name, difficulty);
    } else if (command == "move") {
        std::string san = bb::join(args, " ");
        reply = g_chess->service.move(msg.chat.id, san);
    } else if (command == "resign") {
        reply = g_chess->service.resign(msg.chat.id);
    } else if (command == "draw") {
        reply = g_chess->service.draw(msg.chat.id);
    } else {
        return;
    }

    if (!reply.empty())
        bb::telegram_send_message(bb::cfg::TELEGRAM_TOKEN, msg.chat.id, reply);
}

void handle_casino_command(const bb::TelegramMessage& msg,
                           const std::string& command,
                           const std::vector<std::string>& args) {
    std::string user_id = std::to_string(msg.from.id);
    std::string tenant_id = std::to_string(msg.chat.id);
    std::string display_name = msg.from.full_name();
    if (display_name.empty() && !msg.from.username.empty())
        display_name = msg.from.username;
    g_casino->facade.register_identity(user_id, display_name);

    std::string reply;
    bool markdown = false;
    if (command == "wallet") {
        reply = g_casino->facade.wallet_command(user_id);
    } else if (command == "leaderboard") {
        reply = g_casino->facade.leaderboard_command();
    } else if (command == "resetwallet") {
        reply = g_casino->facade.reset_wallet_command(user_id);
    } else if (command == "roulette") {
        reply = g_casino->facade.roulette_command(user_id, tenant_id, args);
    } else if (command == "roulettespin") {
        reply = g_casino->facade.roulette_spin_command(tenant_id);
    } else if (command == "craps") {
        reply = g_casino->facade.craps_command(user_id, tenant_id, args);
    } else if (command == "crapsroll") {
        reply = g_casino->facade.craps_roll_command(tenant_id);
    } else if (command == "zeus") {
        auto [text, is_markdown] = g_casino->facade.zeus_command(user_id);
        reply = text;
        markdown = is_markdown;
    } else {
        return;
    }

    if (!reply.empty())
        bb::telegram_send_message(bb::cfg::TELEGRAM_TOKEN, msg.chat.id, reply,
                                  markdown ? "MarkdownV2" : "");
}

void handle_message(const bb::TelegramMessage& msg, bb::DataManager& dm) {
    std::string text = msg.text;
    if (text.empty() && !msg.caption.empty()) {
        // Photo captions may carry the howmanybooms question.
        std::string reply = bb::handle_photo_caption(dm, msg.caption);
        if (!reply.empty())
            bb::telegram_send_message(bb::cfg::TELEGRAM_TOKEN, msg.chat.id, reply);
        return;
    }
    if (text.empty())
        return;

    std::string command;
    std::vector<std::string> args;
    if (!bb::parse_command(text, bot_username_cache, command, args)) {
        // A bare message (not a command) in a chat with an active game is a
        // move in SAN: reply-to-board "e4" was the python-era convention.
        if (g_chess != nullptr && g_chess->store.find_active(msg.chat.id)) {
            std::string maybe_san = bb::trim(text);
            if (!maybe_san.empty() && maybe_san[0] != '/') {
                std::string reply = g_chess->service.move(msg.chat.id, maybe_san);
                if (!reply.empty())
                    bb::telegram_send_message(bb::cfg::TELEGRAM_TOKEN,
                                              msg.chat.id, reply);
            }
        }
        return;
    }

    std::string reply;
    if (command == "boom") {
        reply = bb::handle_boom(args);
    } else if (command == "howmanybooms") {
        reply = bb::handle_howmanybooms(dm, args);
    } else if (command == "whowouldwin") {
        reply = bb::handle_whowouldwin(args);
    } else if (command == "friggedthedeposit") {
        reply = bb::handle_frigged_deposit(args);
    } else if (g_casino != nullptr &&
               (command == "wallet" || command == "leaderboard" ||
                command == "resetwallet" || command == "roulette" ||
                command == "roulettespin" || command == "craps" ||
                command == "crapsroll" || command == "zeus")) {
        handle_casino_command(msg, command, args);
        return;
    } else if (command == "board") {
        if (g_chess != nullptr)
            reply = g_chess->service.board(msg.chat.id);
    } else if (g_chess != nullptr &&
               (command == "chess" || command == "newgame" ||
                command == "move" || command == "resign" ||
                command == "draw")) {
        handle_chess_command(msg, command, args);
        return;
    } else {
        return;
    }

    if (!reply.empty())
        bb::telegram_send_message(bb::cfg::TELEGRAM_TOKEN, msg.chat.id, reply);
}

} // namespace

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;
    bb::cfg::load_config();
    if (bb::cfg::TELEGRAM_TOKEN.empty()) {
        std::cerr << "TELEGRAM_TOKEN is not set; refusing to start." << std::endl;
        return 1;
    }

    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
    std::signal(SIGPIPE, SIG_IGN);

    bb::DataManager dm;
    dm.reload_all();

    CasinoContext casino;
    g_casino = &casino;

    ChessContext chess;
    g_chess = &chess;

    bot_username_cache = bb::telegram_bot_username(bb::cfg::TELEGRAM_TOKEN);
    bb::log::log_info("Bot ready (username='" + bot_username_cache + "').");

    // A webhook left on the token (from any experiment or other framework)
    // makes Telegram reject every getUpdates with HTTP 409, which would leave
    // the poller running but mute forever. Clear it before polling.
    if (bb::telegram_delete_webhook(bb::cfg::TELEGRAM_TOKEN))
        bb::log::log_info("Webhook cleared; long polling active.");
    else
        bb::log::log_warning(
            "Could not clear webhook; getUpdates may be rejected (HTTP 409).");

    int64_t offset = 0;
    int empty_poll_backoff = 0;
    while (!g_stop) {
        std::vector<bb::TelegramUpdate> updates =
            bb::telegram_get_updates(bb::cfg::TELEGRAM_TOKEN, offset, 30);
        if (updates.empty()) {
            int seconds = 1 << std::min(empty_poll_backoff, 2);
            std::this_thread::sleep_for(std::chrono::seconds(seconds));
            empty_poll_backoff = std::min(empty_poll_backoff + 1, 2);
        } else {
            empty_poll_backoff = 0;
        }
        for (const bb::TelegramUpdate& update : updates) {
            if (update.has_message) {
                try {
                    handle_message(update.message, dm);
                } catch (const std::exception& e) {
                    bb::log::log_warning(std::string("handler error: ") + e.what());
                }
            }
            if (update.update_id >= offset)
                offset = update.update_id + 1;
        }
    }
    bb::log::log_info("Shutting down.");
    return 0;
}
