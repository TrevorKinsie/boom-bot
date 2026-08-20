/*
 * bb_chess.h - community chess against the in-house Objective-C engine.
 *
 * Replaces boombot/games/chess (formerly a Stockfish wrapper). The engine is
 * a UCI subprocess exposed through bb_chess::UciClient; requests are
 * serialized with a process-wide mutex because the long-poll loop is
 * single-threaded. Game records live in a JSON file (bb::Json) keyed by chat
 * id. SAN parsing/formatting and end-of-game detection are done by the engine
 * itself through the "bb" UCI extensions (bb san2uci / bb uci2san / bb fen /
 * bb status).
 */
#ifndef BB_CHESS_H
#define BB_CHESS_H

#include "bb_json.h"

#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace bb {
namespace chess {

// One chat's community game. fen and status are the engine's own strings.
struct Game {
    int64_t chat_id = 0;
    std::string fen;               // current position, engine format
    std::string status = "active"; // active | completed
    std::string winner;            // white | black | draw
    std::string community_color;   // "w" or "b" (community = the chat)
    int difficulty = 20;           // 0..20
    std::string starter;           // Telegram display name
    std::vector<std::string> moves; // SAN of every played move
};

// Persistent JSON-backed store of chess games (one file, mirrors cfg).
class GameStore {
public:
    explicit GameStore(const std::string& file);

    void load();
    void save();

    std::optional<Game> find_active(int64_t chat_id) const;
    std::optional<Game> find_any(int64_t chat_id) const;
    void upsert(const Game& game);

private:
    void apply(const Json& doc, Game& game) const;
    Json to_json(const Game& game) const;

    std::string file_;
    Json doc_ = Json::object(); // chat_id -> game object
};

// A synchronous client for one persistent engine process.
class UciClient {
public:
    explicit UciClient(const std::string& engine_path);
    ~UciClient();

    UciClient(const UciClient&) = delete;
    UciClient& operator=(const UciClient&) = delete;

    struct Result {
        std::string value; // uci | san | fen | status | bestmove
        bool ok = false;
        std::string error;
        explicit operator bool() const { return ok; }
    };

    // Starts (or restarts) the engine and waits for isready. Throws
    // std::runtime_error when the binary cannot be spawned.
    void ensure_started();

    // Round-trip a position. Each op re-sets the engine board first.
    Result san_to_uci(const std::string& fen, const std::string& san);
    Result uci_to_san(const std::string& fen, const std::string& uci);
    Result status_of(const std::string& fen);
    Result fen_of();                       // current engine board as a fen
    Result best_move(int depth);           // current engine board, depth >= 1
    Result start_fen();                    // reset the board to the start
                                           // position and read the fen back
    // Apply a UCI move to the current engine board (used after san_to_uci).
    bool play(const std::string& uci);

private:
    void spawn();
    void kill();
    void write_line(const std::string& line);
    // Reads lines until one starts with `prefix`; returns its tail. Returns
    // empty with error set on EOF/timeout.
    Result read_until(const std::string& prefix, int timeout_ms);
    // Lock-free "bb fen" query; the caller must hold mu_.
    Result fen_of_locked();

    std::string path_;
    int in_fd_ = -1;   // engine stdin (we write)
    int out_fd_ = -1;  // engine stdout (we read)
    pid_t pid_ = -1;
    bool alive_ = false;
    std::string pending_; // partial output not yet consumed
    std::mutex mu_;
};

// High-level per-chat gameplay against the engine.
class ChessService {
public:
    ChessService(UciClient& engine, GameStore& store);

    std::string start(int64_t chat_id, const std::string& display_name,
                      int difficulty);
    std::string move(int64_t chat_id, const std::string& move_san);
    std::string resign(int64_t chat_id);
    std::string draw(int64_t chat_id);
    std::string board(int64_t chat_id) const;

private:
    std::string render_board(const std::string& fen) const;
    int depth_for(int difficulty) const;

    UciClient& engine_;
    GameStore& store_;
};

} // namespace chess
} // namespace bb

#endif // BB_CHESS_H