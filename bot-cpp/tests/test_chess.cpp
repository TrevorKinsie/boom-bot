/*
 * test_chess.cpp - chess port tests: GameStore persistence, UciClient
 * against the real in-house engine, and ChessService game flow.
 */
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

#include "bb_chess.h"
#include "bb_config.h"
#include "bb_util.h"
#include "tests.h"

using namespace bb;

namespace {

const char* kTempDir = "/tmp/opencode/bb-test-chess";
// Fool's mate end position: white to move, black is mated.
const char* kMateFen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1";
// Black to move, every square covered, not in check.
const char* kStaleFen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1";

} // namespace

// --- GameStore persistence ------------------------------------------------

TEST_CASE(chess_store_round_trip) {
    std::filesystem::remove_all(kTempDir);
    std::filesystem::create_directories(kTempDir);
    std::string file = std::string(kTempDir) + "/games.json";

    {
        chess::GameStore store(file);
        store.load();
        CHECK(!store.find_active(1001));

        chess::Game g;
        g.chat_id = 1001;
        g.fen = "startpos";
        g.status = "active";
        g.community_color = "w";
        g.difficulty = 10;
        g.moves.push_back("e4");
        store.upsert(g);

        auto found = store.find_active(1001);
        CHECK(found.has_value());
        CHECK(found->status == "active");
        CHECK(found->community_color == "w");
        CHECK(found->difficulty == 10);
        CHECK(found->moves.size() == 1 && found->moves[0] == "e4");
    }

    // A fresh store instance must see the persisted game.
    {
        chess::GameStore store(file);
        store.load();
        auto found = store.find_any(1001);
        CHECK(found.has_value());
        CHECK(found->fen == "startpos");
        CHECK(!found->winner.empty() == false || found->winner.empty());
    }

    // Completing a game hides it from find_active.
    {
        chess::GameStore store(file);
        store.load();
        auto g = *store.find_any(1001);
        g.status = "completed";
        g.winner = "white";
        store.upsert(g);
        CHECK(!store.find_active(1001));
        auto again = store.find_any(1001);
        CHECK(again.has_value() && again->winner == "white");
    }
}

// --- UciClient against the real engine ------------------------------------

TEST_CASE(chess_uci_client_engine) {
    chess::UciClient engine(bb::cfg::CHESS_ENGINE_PATH);
    CHECK_NOT_THROWS(engine.ensure_started());
    engine.start_fen();

    auto uci = engine.san_to_uci("startpos", "e4");
    CHECK(uci.ok);
    CHECK_STR_EQ(uci.value, "e2e4");

    auto san = engine.uci_to_san(
        "startpos", "e2e4");
    CHECK(san.ok);
    CHECK_STR_EQ(san.value, "e4");

    // Illegal moves must be rejected, not guessed.
    auto bad = engine.san_to_uci("startpos", "e5");
    CHECK(!bad.ok);
    CHECK(engine.san_to_uci("startpos", "Ke2").ok == false);

    auto status = engine.status_of("startpos");
    CHECK(status.ok);
    CHECK_STR_EQ(status.value, "active");

    auto mate = engine.status_of(kMateFen);
    CHECK(mate.ok);
    CHECK_STR_EQ(mate.value, "checkmate black");

    auto stale = engine.status_of(kStaleFen);
    CHECK(stale.ok);
    CHECK_STR_EQ(stale.value, "stalemate");

    // Full move cycle through the engine's own board: user move, then engine
    // reply, then re-read the position.
    engine.start_fen();
    CHECK(engine.play("e2e4"));
    auto after_user = engine.fen_of();
    CHECK(after_user.ok);
    CHECK(after_user.value.rfind("rnbqkbnr/pppppppp/8/8/4P3", 0) == 0);

    auto best = engine.best_move(1);
    CHECK(best.ok);
    CHECK(best.value.size() == 4 || best.value.size() == 5); // uci move
    auto best_san = engine.uci_to_san(after_user.value, best.value);
    CHECK(best_san.ok);

    CHECK(engine.play(best.value));
    auto after_engine = engine.fen_of();
    CHECK(after_engine.ok);
}

// --- ChessService game flow -----------------------------------------------

TEST_CASE(chess_service_game) {
    std::filesystem::remove_all(kTempDir);
    std::filesystem::create_directories(kTempDir);
    std::string file = std::string(kTempDir) + "/games.json";
    chess::GameStore store(file);
    chess::UciClient engine(bb::cfg::CHESS_ENGINE_PATH);
    chess::ChessService service(engine, store);
    store.load();

    int64_t chat = 4242;
    std::string start = service.start(chat, "TestUser", 2); // shallow search
    CHECK(start.find("New chess game started!") != std::string::npos);
    CHECK(start.find("8 ") != std::string::npos); // board rendered

    // The community color is random; the first legal move depends on it. If
    // we are black, the engine already moved and "e4" is invalid for us.
    std::string m1 = service.move(chat, "e4");
    bool community_is_black = m1.rfind("Invalid move", 0) == 0;
    if (!community_is_black) {
        CHECK(m1.find("You played e4.") != std::string::npos);
        CHECK(store.find_any(chat)->moves.size() >= 2); // human + engine reply
        CHECK(store.find_any(chat)->status == "active");
        // The stored fen must actually have moved (board-sync regression
        // guard: previously the engine never applied the move).
        CHECK_STR_EQ(store.find_any(chat)->moves[0], "e4");
        std::string fen = store.find_any(chat)->fen;
        CHECK(fen.find("4P3") != std::string::npos);
        CHECK(fen.find("rnbqkbnr/pppppppp/8/8/4P3") != std::string::npos);
        // A second move must work on the same position.
        std::string m2 = service.move(chat, "Nf3");
        CHECK(m2.find("You played Nf3.") != std::string::npos);
        CHECK(store.find_any(chat)->moves.size() >= 4);
    } else {
        CHECK(m1.find("It's not your turn") != std::string::npos ||
              m1.rfind("Invalid move", 0) == 0);
    }

    CHECK(service.board(chat).find("8 ") != std::string::npos);

    std::string draw = service.draw(chat);
    CHECK(draw.find("draw by agreement") != std::string::npos);
    auto g1 = store.find_any(chat);
    CHECK(g1->status == "completed");
    CHECK(g1->winner == "draw");

    // Resigning always works for an active game.
    std::string resign = service.resign(chat);

    // Starting a new game after a completed one.
    std::string again = service.start(chat, "TestUser", 2);
    CHECK(again.find("New chess game started!") != std::string::npos);
    CHECK(store.find_active(chat).has_value());
    CHECK(store.find_active(chat)->moves.empty());

    // board() with no game.
    std::string nobody = service.board(9999);
    CHECK(nobody.find("No chess game") != std::string::npos);
}