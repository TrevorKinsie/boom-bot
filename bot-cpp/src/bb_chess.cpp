/*
 * bb_chess.cpp - implementation of the chess service against the engine.
 *
 * Game flow per user move: re-sync the engine board from the stored fen,
 * validate the SAN (the engine rejects illegal/ambiguous moves), replay it,
 * ask the engine for a reply at a depth derived from the chosen difficulty,
 * then persist the new fen. End-of-game states (mate/stalemate/draw) come
 * from the engine's "bb status" so the bot never re-implements the rules.
 */
#include "bb_chess.h"

#include "bb_config.h"
#include "bb_log.h"
#include "bb_util.h"

#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

namespace bb {
namespace chess {

/* ------------------------------------------------------------------ */
/* GameStore                                                          */
/* ------------------------------------------------------------------ */

GameStore::GameStore(const std::string& file) : file_(file) {
}

void GameStore::apply(const Json& doc, Game& game) const {
    game.fen = doc.get_string("fen");
    game.status = doc.get_string("status", "active");
    game.winner = doc.get_string("winner");
    game.community_color = doc.get_string("community_color", "w");
    game.difficulty = static_cast<int>(doc.get_int("difficulty", 20));
    game.starter = doc.get_string("starter");
    game.moves.clear();
    if (doc.has("moves") && doc.at("moves").is_array()) {
        for (const Json& m : doc.at("moves").as_array())
            game.moves.push_back(m.as_string());
    }
}

Json GameStore::to_json(const Game& game) const {
    Json obj = Json::object();
    obj.set("fen", game.fen);
    obj.set("status", game.status);
    obj.set("winner", game.winner);
    obj.set("community_color", game.community_color);
    obj.set("difficulty", static_cast<int64_t>(game.difficulty));
    obj.set("starter", game.starter);
    Json moves = Json::array();
    for (const std::string& m : game.moves)
        moves.push(m);
    obj.set("moves", moves);
    return obj;
}

namespace {
std::string read_whole_file(const std::string& path) {
    int fd = open(path.c_str(), O_RDONLY);
    if (fd < 0)
        return "";
    std::string out;
    char buf[4096];
    while (true) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0)
            break;
        out.append(buf, static_cast<size_t>(n));
    }
    close(fd);
    return out;
}

bool write_whole_file(const std::string& path, const std::string& content) {
    int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0)
        return false;
    size_t written = 0;
    while (written < content.size()) {
        ssize_t n = write(fd, content.data() + written, content.size() - written);
        if (n < 0) {
            close(fd);
            return false;
        }
        written += static_cast<size_t>(n);
    }
    return close(fd) == 0;
}
} // namespace

void GameStore::load() {
    std::string text = read_whole_file(file_);
    doc_ = Json::object();
    if (text.empty())
        return;
    try {
        doc_ = Json::parse(text);
    } catch (const JsonError&) {
        log::log_warning("chess store unparseable, starting empty: " + file_);
        doc_ = Json::object();
    }
}

void GameStore::save() {
    if (!write_whole_file(file_, doc_.dump(4)))
        log::log_warning("chess store write failed: " + file_);
}

std::optional<Game> GameStore::find_active(int64_t chat_id) const {
    std::optional<Game> game = find_any(chat_id);
    if (game && game->status == "active")
        return game;
    return std::nullopt;
}

std::optional<Game> GameStore::find_any(int64_t chat_id) const {
    const Json* found = doc_.find(std::to_string(chat_id));
    if (found == nullptr || !found->is_object())
        return std::nullopt;
    Game game;
    game.chat_id = chat_id;
    apply(*found, game);
    return game;
}

void GameStore::upsert(const Game& game) {
    doc_.set(std::to_string(game.chat_id), to_json(game));
    save();
}

/* ------------------------------------------------------------------ */
/* UciClient                                                          */
/* ------------------------------------------------------------------ */

namespace {
// The engine's bbToFen emits only placement/stm/castle/ep, but UCI's
// "position fen" needs the full six fields; append the missing counters so
// the engine's own tokenizer does not swallow the "moves" keyword.
std::string fen_for_position(const std::string& fen) {
    std::string out = trim(fen);
    if (split(out, " ").size() < 5)
        out += " 0 1";
    return out;
}
} // namespace

UciClient::UciClient(const std::string& engine_path) : path_(engine_path) {
}

UciClient::~UciClient() {
    kill();
}

void UciClient::kill() {
    if (pid_ > 0) {
        int status = 0;
        ::kill(pid_, SIGTERM);
        for (int i = 0; i < 50 && waitpid(pid_, &status, WNOHANG) == 0; i++) {
            usleep(100 * 1000);
        }
        if (waitpid(pid_, &status, WNOHANG) == 0)
            ::kill(pid_, SIGKILL);
        waitpid(pid_, &status, 0);
    }
    if (in_fd_ >= 0)
        close(in_fd_);
    if (out_fd_ >= 0)
        close(out_fd_);
    in_fd_ = -1;
    out_fd_ = -1;
    pid_ = -1;
    alive_ = false;
}

void UciClient::spawn() {
    int stdin_pipe[2] = {-1, -1};
    int stdout_pipe[2] = {-1, -1};
    if (pipe(stdin_pipe) != 0 || pipe(stdout_pipe) != 0) {
        if (stdin_pipe[0] >= 0) {
            close(stdin_pipe[0]);
            close(stdin_pipe[1]);
        }
        if (stdout_pipe[0] >= 0) {
            close(stdout_pipe[0]);
            close(stdout_pipe[1]);
        }
        throw std::runtime_error("pipe() failed while spawning chess engine");
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(stdin_pipe[0]);
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);
        close(stdout_pipe[1]);
        throw std::runtime_error("fork() failed while spawning chess engine");
    }
    if (pid == 0) {
        dup2(stdin_pipe[0], STDIN_FILENO);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0)
            dup2(devnull, STDERR_FILENO);
        close(stdin_pipe[0]);
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);
        close(stdout_pipe[1]);
        execl(path_.c_str(), path_.c_str(), (char*)nullptr);
        _exit(127);
    }

    close(stdin_pipe[0]);
    close(stdout_pipe[1]);
    in_fd_ = stdin_pipe[1];
    out_fd_ = stdout_pipe[0];
    pid_ = pid;

    int flags = fcntl(out_fd_, F_GETFL, 0);
    fcntl(out_fd_, F_SETFL, flags | O_NONBLOCK);
    alive_ = true;
}

void UciClient::ensure_started() {
    std::lock_guard<std::mutex> lock(mu_);
    if (alive_)
        return;
    try {
        spawn();
    } catch (const std::exception& e) {
        throw std::runtime_error("cannot start chess engine '" + path_ +
                                 "': " + e.what());
    }
    write_line("uci");
    Result ready = read_until("uciok", 5000);
    if (!ready.ok) {
        kill();
        throw std::runtime_error("chess engine did not answer uci: " + ready.error);
    }
    write_line("isready");
    Result ok = read_until("readyok", 5000);
    if (!ok.ok) {
        kill();
        throw std::runtime_error("chess engine did not become ready: " + ok.error);
    }
}

void UciClient::write_line(const std::string& line) {
    std::string payload = line + "\n";
    size_t written = 0;
    while (written < payload.size()) {
        ssize_t n = write(in_fd_, payload.data() + written, payload.size() - written);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            throw std::runtime_error("chess engine stdin write failed");
        }
        written += static_cast<size_t>(n);
    }
}

// Reads until a line starting with `prefix`, returning its tail. The engine
// replies line-by-line; we keep any unread remainder for the next call.
UciClient::Result UciClient::read_until(const std::string& prefix, int timeout_ms) {
    std::string pending = pending_;
    pending_.clear();
    int waited = 0;

    while (true) {
        size_t nl = pending.find('\n');
        while (nl != std::string::npos) {
            std::string line = pending.substr(0, nl);
            pending.erase(0, nl + 1);
            if (starts_with(line, prefix)) {
                pending_ = pending;
                Result r;
                r.ok = true;
                r.value = trim(line.substr(prefix.size()));
                return r;
            }
        }
        if (waited >= timeout_ms) {
            Result r;
            r.error = "engine timeout waiting for '" + prefix + "'";
            return r;
        }
        struct pollfd pfd;
        pfd.fd = out_fd_;
        pfd.events = POLLIN;
        pfd.revents = 0;
        int rc = poll(&pfd, 1, 200);
        waited += 200;
        if (rc > 0 && (pfd.revents & POLLIN)) {
            char buf[4096];
            ssize_t n = read(out_fd_, buf, sizeof(buf));
            if (n > 0) {
                pending.append(buf, static_cast<size_t>(n));
            } else if (n == 0) {
                Result r;
                r.error = "chess engine closed its output";
                return r;
            }
        } else if (rc < 0) {
            Result r;
            r.error = "engine poll failed";
            return r;
        }
    }
}

UciClient::Result UciClient::san_to_uci(const std::string& fen, const std::string& san) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("position fen " + fen_for_position(fen));
        write_line("bb san2uci " + san);
        Result r = read_until("info string", 5000);
        if (!r.ok)
            return r;
        if (starts_with(r.value, "uci "))
            return {trim(r.value.substr(4)), true, ""};
        if (starts_with(r.value, "error "))
            return {std::string(), false, trim(r.value.substr(6))};
        return {std::string(), false, "unexpected engine reply"};
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

UciClient::Result UciClient::uci_to_san(const std::string& fen, const std::string& uci) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("position fen " + fen_for_position(fen));
        write_line("bb uci2san " + uci);
        Result r = read_until("info string", 5000);
        if (!r.ok)
            return r;
        if (starts_with(r.value, "san "))
            return {trim(r.value.substr(4)), true, ""};
        if (starts_with(r.value, "error "))
            return {std::string(), false, trim(r.value.substr(6))};
        return {std::string(), false, "unexpected engine reply"};
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

UciClient::Result UciClient::status_of(const std::string& fen) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("position fen " + fen_for_position(fen));
        write_line("bb status");
        Result r = read_until("info string", 5000);
        if (!r.ok)
            return r;
        if (starts_with(r.value, "status "))
            return {trim(r.value.substr(7)), true, ""};
        return {std::string(), false, "unexpected engine reply"};
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

UciClient::Result UciClient::fen_of() {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("bb fen");
        Result r = read_until("info string", 5000);
        if (!r.ok)
            return r;
        if (starts_with(r.value, "fen "))
            return {trim(r.value.substr(4)), true, ""};
        return {std::string(), false, "unexpected engine reply"};
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

UciClient::Result UciClient::best_move(int depth) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("go depth " + std::to_string(std::max(1, depth)));
        Result r = read_until("bestmove", 120000);
        if (!r.ok)
            return r;
        if (r.value.empty() || r.value == "0000")
            return {std::string(), false, "engine offered no move"};
        return {trim(r.value), true, ""};
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

UciClient::Result UciClient::start_fen() {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line("position startpos");
        return fen_of_locked();
    } catch (const std::exception& e) {
        return {std::string(), false, e.what()};
    }
}

// Applies a UCI move to the engine's current board (used right after a
// san_to_uci/uci_to_san set the position). Callers must not hold the lock.
bool UciClient::play(const std::string& uci) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return false;
    try {
        Result fen = fen_of_locked();
        if (!fen.ok)
            return false;
        write_line("position fen " + fen_for_position(fen.value) + " moves " + uci);
        // The position command must execute before the next query; the next
        // query's own "position fen ..." resync makes ordering implicit.
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

// Lock-free internals (the caller holds mu_).
UciClient::Result UciClient::fen_of_locked() {
    write_line("bb fen");
    Result r = read_until("info string", 5000);
    if (!r.ok)
        return r;
    if (starts_with(r.value, "fen "))
        return {trim(r.value.substr(4)), true, ""};
    return {std::string(), false, "unexpected engine reply"};
}

using UciResult = UciClient::Result;

/* ------------------------------------------------------------------ */
/* ChessService                                                       */
/* ------------------------------------------------------------------ */

namespace {
std::string status_winner(const std::string& status) {
    if (starts_with(status, "checkmate ")) {
        std::string w = trim(status.substr(10));
        if (w == "white" || w == "black")
            return w;
    }
    return "draw";
}

int difficulty_depth(int difficulty, int base_depth) {
    int d = std::max(0, std::min(20, difficulty));
    int depth = (d * base_depth + 10) / 20;
    return std::max(1, std::min(base_depth, depth));
}
} // namespace

ChessService::ChessService(UciClient& engine, GameStore& store)
    : engine_(engine), store_(store) {
}

int ChessService::depth_for(int difficulty) const {
    return difficulty_depth(difficulty, bb::cfg::CHESS_ENGINE_DEPTH);
}

std::string ChessService::start(int64_t chat_id, const std::string& display_name,
                                int difficulty) {
    if (store_.find_active(chat_id))
        return "A game is already active in this chat! /resign to end it.";

    engine_.ensure_started();
    UciResult start_fen = engine_.start_fen();
    if (!start_fen.ok)
        return "Unable to start a game right now.";

    Game game;
    game.chat_id = chat_id;
    game.starter = display_name;
    game.difficulty = std::max(0, std::min(20, difficulty));
    game.community_color = (rand() % 2 == 0) ? "w" : "b";
    game.fen = start_fen.value;

    if (game.community_color == "b") {
        UciResult best = engine_.best_move(depth_for(game.difficulty));
        if (!best.ok)
            return "Unable to start a game right now.";
        UciResult san = engine_.uci_to_san(game.fen, best.value);
        if (!san.ok)
            return "Unable to start a game right now.";
        engine_.play(best.value);
        UciResult fen = engine_.fen_of();
        if (fen.ok)
            game.fen = fen.value;
        game.moves.push_back(san.value);
    }

    store_.upsert(game);

    std::string reply = "New chess game started! Difficulty " +
                        std::to_string(game.difficulty) + " (search depth " +
                        std::to_string(depth_for(game.difficulty)) + ").\n";
    reply += "The community plays " +
             (game.community_color == "w" ? std::string("White")
                                          : std::string("Black")) +
             ".\n";
    if (game.community_color == "b" && !game.moves.empty())
        reply += "I moved first: " + game.moves[0] + ".\n";
    reply += "\n" + render_board(game.fen);
    reply += "\nSend /move <SAN> (e.g. /move Nf3) or reply with your move.";
    return reply;
}

std::string ChessService::move(int64_t chat_id, const std::string& move_san) {
    std::string san = trim(move_san);
    if (san.empty())
        return "Tell me the move: /move <SAN> (e.g. /move e4).";

    std::optional<Game> existing = store_.find_active(chat_id);
    if (!existing)
        return "No active game in this chat. /newgame to start.";

    Game game = *existing;
    engine_.ensure_started();

    UciResult uci = engine_.san_to_uci(game.fen, san);
    if (!uci.ok)
        return "Invalid move or error: " + san;

    UciResult san_after_user = engine_.uci_to_san(game.fen, uci.value);
    std::string user_san = san_after_user.ok ? san_after_user.value : san;

    if (!engine_.play(uci.value))
        return "Unable to process the chess move. Please try again.";
    UciResult fen_after_user = engine_.fen_of();
    if (!fen_after_user.ok)
        return "Unable to process the chess move. Please try again.";

    game.moves.push_back(user_san);
    game.fen = fen_after_user.value;
    store_.upsert(game);

    UciResult st_user = engine_.status_of(game.fen);
    std::string status_value = st_user.ok ? st_user.value : "active";
    if (starts_with(status_value, "checkmate") || status_value == "stalemate" ||
        status_value == "draw") {
        game.status = "completed";
        game.winner = status_winner(status_value);
        store_.upsert(game);
        std::string outcome = (game.winner == "draw")
                                  ? "Game Over! Draw."
                                  : "Game Over! " + capitalize(game.winner) +
                                        " wins!";
        if (status_value == "stalemate")
            outcome += " (stalemate)";
        return outcome + "\n\n" + render_board(game.fen);
    }

    UciResult best = engine_.best_move(depth_for(game.difficulty));
    if (!best.ok)
        return "I couldn't find a move; try again.";
    UciResult cpu_san_res = engine_.uci_to_san(game.fen, best.value);
    std::string cpu_san = cpu_san_res.ok ? cpu_san_res.value : best.value;
    engine_.play(best.value);
    UciResult fen_after_cpu = engine_.fen_of();
    if (fen_after_cpu.ok)
        game.fen = fen_after_cpu.value;
    game.moves.push_back(cpu_san);
    store_.upsert(game);

    UciResult st_cpu = engine_.status_of(game.fen);
    std::string status_cpu = st_cpu.ok ? st_cpu.value : "active";

    std::string reply = "You played " + user_san + ". I played " + cpu_san + ".";
    if (starts_with(status_cpu, "checkmate") || status_cpu == "stalemate" ||
        status_cpu == "draw") {
        game.status = "completed";
        game.winner = status_winner(status_cpu);
        store_.upsert(game);
        std::string outcome = (game.winner == "draw")
                                  ? "Game Over! Draw."
                                  : "Game Over! " + capitalize(game.winner) +
                                        " wins!";
        if (status_cpu == "stalemate")
            outcome += " (stalemate)";
        reply = outcome + "\n\n" + reply;
    } else if (status_cpu == "check") {
        reply += " Check!";
    }
    reply += "\n\n" + render_board(game.fen);
    return reply;
}

std::string ChessService::resign(int64_t chat_id) {
    std::optional<Game> existing = store_.find_any(chat_id);
    if (!existing || existing->status != "active")
        return "No active game to resign.";
    Game game = *existing;
    game.status = "completed";
    game.winner = (game.community_color == "w") ? "black" : "white";
    store_.upsert(game);
    return "Game resigned. " + capitalize(game.winner) + " wins!";
}

std::string ChessService::draw(int64_t chat_id) {
    std::optional<Game> existing = store_.find_any(chat_id);
    if (!existing || existing->status != "active")
        return "No active game to draw.";
    Game game = *existing;
    game.status = "completed";
    game.winner = "draw";
    store_.upsert(game);
    return "Game ended in a draw by agreement.";
}

std::string ChessService::board(int64_t chat_id) const {
    std::optional<Game> game = store_.find_any(chat_id);
    if (!game)
        return "No chess game in this chat. /newgame to start.";
    std::string reply = render_board(game->fen);
    reply += "\nStatus: " + game->status;
    if (game->status == "completed" && !game->winner.empty())
        reply += ", winner " + game->winner;
    if (!game->moves.empty())
        reply += "\nMoves: " + join(game->moves, " ");
    return reply;
}

std::string ChessService::render_board(const std::string& fen) const {
    // FEN placement is ranks 8..1 left to right.
    std::vector<std::string> ranks = split(split(fen, " ", 1)[0], "/");
    std::string out;
    for (int ri = 0; ri < 8 && ri < static_cast<int>(ranks.size()); ri++) {
        int human_rank = 8 - ri;
        out += std::to_string(human_rank) + " ";
        for (char c : ranks[static_cast<size_t>(ri)]) {
            if (c >= '1' && c <= '8') {
                for (char d = '1'; d <= c; d++)
                    out += ".";
            } else {
                bool upper = (c >= 'A' && c <= 'Z');
                out += upper ? c : static_cast<char>(c - 'a' + 'A');
            }
            out += " ";
        }
        out += "\n";
    }
    out += "  a b c d e f g h";
    return out;
}

} // namespace chess
} // namespace bb