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
#include <atomic>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <stdexcept>
#include <utility>

namespace bb {
namespace chess {

namespace {
bool valid_uci_token(const std::string& move) {
    if (move.size() != 4 && move.size() != 5)
        return false;
    const auto valid_square = [](char file, char rank) {
        return file >= 'a' && file <= 'h' && rank >= '1' && rank <= '8';
    };
    if (!valid_square(move[0], move[1]) || !valid_square(move[2], move[3]))
        return false;
    return move.size() == 4 || move[4] == 'q' || move[4] == 'r' ||
           move[4] == 'b' || move[4] == 'n';
}
} // namespace

/* ------------------------------------------------------------------ */
/* GameStore                                                          */
/* ------------------------------------------------------------------ */

GameStore::GameStore(const std::string& file) : file_(file) {
}

void GameStore::apply(const Json& doc, Game& game) const {
    const auto string_value = [&doc](const char* key, const std::string& fallback) {
        const Json* value = doc.find(key);
        return value != nullptr && value->is_string() ? value->as_string() : fallback;
    };
    game.fen = string_value("fen", "");
    game.status = string_value("status", "active");
    if (game.status != "active" && game.status != "completed")
        game.status = "active";
    game.winner = string_value("winner", "");
    if (game.winner != "white" && game.winner != "black" && game.winner != "draw")
        game.winner.clear();
    game.community_color = string_value("community_color", "w");
    if (game.community_color != "w" && game.community_color != "b")
        game.community_color = "w";
    int64_t raw_difficulty = doc.get_int("difficulty", 20);
    game.difficulty = static_cast<int>(std::max<int64_t>(0, std::min<int64_t>(20, raw_difficulty)));
    game.starter = string_value("starter", "");
    game.moves.clear();
    if (doc.has("moves") && doc.at("moves").is_array()) {
        for (const Json& m : doc.at("moves").as_array()) {
            if (m.is_string())
                game.moves.push_back(m.as_string());
        }
    }
    game.uci_moves.clear();
    if (doc.has("uci_moves") && doc.at("uci_moves").is_array()) {
        bool valid_history = true;
        for (const Json& m : doc.at("uci_moves").as_array()) {
            if (!m.is_string() || !valid_uci_token(m.as_string())) {
                valid_history = false;
                break;
            }
            game.uci_moves.push_back(m.as_string());
        }
        if (!valid_history)
            game.uci_moves.clear();
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
    Json uci_moves = Json::array();
    for (const std::string& m : game.uci_moves)
        uci_moves.push(m);
    obj.set("uci_moves", uci_moves);
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
    static std::atomic<uint64_t> counter{0};
    std::filesystem::path destination(path);
    std::error_code directory_error;
    if (destination.has_parent_path())
        std::filesystem::create_directories(destination.parent_path(), directory_error);
    if (directory_error)
        return false;

    std::string temporary = path + ".tmp." + std::to_string(static_cast<long long>(getpid())) +
                            "." + std::to_string(counter.fetch_add(1));
    int fd = open(temporary.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0)
        return false;
    size_t written = 0;
    while (written < content.size()) {
        ssize_t n = write(fd, content.data() + written, content.size() - written);
        if (n < 0 && errno == EINTR)
            continue;
        if (n < 0) {
            close(fd);
            unlink(temporary.c_str());
            return false;
        }
        if (n == 0) {
            close(fd);
            unlink(temporary.c_str());
            return false;
        }
        written += static_cast<size_t>(n);
    }
    if (fsync(fd) != 0 || close(fd) != 0) {
        close(fd);
        unlink(temporary.c_str());
        return false;
    }
    if (rename(temporary.c_str(), path.c_str()) != 0) {
        unlink(temporary.c_str());
        return false;
    }
    return true;
}
} // namespace

void GameStore::load() {
    std::string text = read_whole_file(file_);
    doc_ = Json::object();
    if (text.empty())
        return;
    try {
        doc_ = Json::parse(text);
        if (!doc_.is_object())
            throw JsonError("chess store root is not an object");
    } catch (const JsonError&) {
        log::log_warning("chess store unparseable, starting empty: " + file_);
        doc_ = Json::object();
    }
}

bool GameStore::save() {
    if (!write_whole_file(file_, doc_.dump(4))) {
        log::log_warning("chess store write failed: " + file_);
        return false;
    }
    return true;
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
    if (game.fen.empty())
        return std::nullopt;
    return game;
}

bool GameStore::upsert(const Game& game) {
    Json before = doc_;
    doc_.set(std::to_string(game.chat_id), to_json(game));
    if (!save()) {
        doc_ = std::move(before);
        return false;
    }
    return true;
}

/* ------------------------------------------------------------------ */
/* UciClient                                                          */
/* ------------------------------------------------------------------ */

namespace {
// Normalize legacy four- and five-field saves before sending them to UCI.
// Current engine output already includes all six FEN fields.
std::string fen_for_position(const std::string& fen) {
    std::vector<std::string> fields;
    for (const std::string& field : split(trim(fen), " ")) {
        if (!field.empty())
            fields.push_back(field);
    }
    std::string out = join(fields, " ");
    if (fields.size() == 4)
        out += " 0 1";
    else if (fields.size() == 5)
        out += " 1";
    return out;
}

std::string position_command(const std::string& fen,
                             const std::vector<std::string>& history) {
    if (!history.empty())
        return "position startpos moves " + join(history, " ");
    if (trim(fen) == "startpos")
        return "position startpos";
    return "position fen " + fen_for_position(fen);
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
    pending_.clear();

    int flags = fcntl(out_fd_, F_GETFL, 0);
    if (flags < 0 || fcntl(out_fd_, F_SETFL, flags | O_NONBLOCK) < 0) {
        kill();
        throw std::runtime_error("cannot configure chess engine output pipe");
    }
    alive_ = true;
}

void UciClient::ensure_started() {
    std::lock_guard<std::mutex> lock(mu_);
    if (alive_) {
        try {
            write_line("isready");
            Result healthy = read_until("readyok", 5000);
            if (healthy.ok)
                return;
        } catch (...) {
            kill();
        }
    }
    try {
        spawn();
        write_line("uci");
        Result ready = read_until("uciok", 5000);
        if (!ready.ok)
            throw std::runtime_error("chess engine did not answer uci: " + ready.error);
        write_line("isready");
        Result ok = read_until("readyok", 5000);
        if (!ok.ok)
            throw std::runtime_error("chess engine did not become ready: " + ok.error);
    } catch (const std::exception& e) {
        kill();
        throw std::runtime_error("cannot start chess engine '" + path_ +
                                 "': " + e.what());
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
        if (n == 0)
            throw std::runtime_error("chess engine stdin closed");
        written += static_cast<size_t>(n);
    }
}

// Reads until a line starting with `prefix`, returning its tail. The engine
// replies line-by-line; we keep any unread remainder for the next call.
UciClient::Result UciClient::read_until(const std::string& prefix, int timeout_ms) {
    std::string pending = pending_;
    pending_.clear();
    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::milliseconds(std::max(0, timeout_ms));
    const auto failure = [this](const std::string& message) {
        pending_.clear();
        kill();
        Result result;
        result.error = message;
        return result;
    };

    while (true) {
        size_t nl;
        while ((nl = pending.find('\n')) != std::string::npos) {
            std::string line = pending.substr(0, nl);
            pending.erase(0, nl + 1);
            if (starts_with(line, prefix) &&
                (line.size() == prefix.size() || line[prefix.size()] == ' ')) {
                pending_ = pending;
                Result r;
                r.ok = true;
                r.value = trim(line.substr(prefix.size()));
                return r;
            }
        }
        auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
            deadline - std::chrono::steady_clock::now()).count();
        if (remaining <= 0)
            return failure("engine timeout waiting for '" + prefix + "'");
        struct pollfd pfd;
        pfd.fd = out_fd_;
        pfd.events = POLLIN;
        pfd.revents = 0;
        int rc = poll(&pfd, 1, static_cast<int>(std::min<int64_t>(200, remaining)));
        if (rc > 0 && (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)))
            return failure("chess engine pipe closed while waiting for '" + prefix + "'");
        if (rc > 0 && (pfd.revents & POLLIN)) {
            char buf[4096];
            ssize_t n = read(out_fd_, buf, sizeof(buf));
            if (n > 0) {
                pending.append(buf, static_cast<size_t>(n));
            } else if (n == 0) {
                return failure("chess engine closed its output");
            } else if (errno != EINTR && errno != EAGAIN && errno != EWOULDBLOCK) {
                return failure("chess engine output read failed");
            }
        } else if (rc < 0) {
            if (errno == EINTR)
                continue;
            return failure("engine poll failed");
        }
    }
}

UciClient::Result UciClient::san_to_uci(const std::string& fen, const std::string& san,
                                        const std::vector<std::string>& history) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line(position_command(fen, history));
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

UciClient::Result UciClient::uci_to_san(const std::string& fen, const std::string& uci,
                                        const std::vector<std::string>& history) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line(position_command(fen, history));
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

UciClient::Result UciClient::status_of(const std::string& fen,
                                       const std::vector<std::string>& history) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!alive_)
        return {std::string(), false, "engine not started"};
    try {
        write_line(position_command(fen, history));
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
        std::string move = trim(r.value);
        size_t separator = move.find_first_of(" \t");
        if (separator != std::string::npos)
            move.resize(separator);
        if (move.empty() || move == "0000")
            return {std::string(), false, "engine offered no move"};
        return {move, true, ""};
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
        write_line("bb play " + trim(uci));
        Result applied = read_until("info string", 5000);
        return applied.ok && (applied.value == "ok");
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

    try {
        engine_.ensure_started();
    } catch (const std::exception&) {
        return "Unable to start a game right now.";
    }
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
        UciResult san = engine_.uci_to_san(game.fen, best.value, game.uci_moves);
        if (!san.ok)
            return "Unable to start a game right now.";
        if (!engine_.play(best.value))
            return "Unable to start a game right now.";
        UciResult fen = engine_.fen_of();
        if (!fen.ok)
            return "Unable to start a game right now.";
        game.fen = fen.value;
        game.moves.push_back(san.value);
        game.uci_moves.push_back(best.value);
    }

    if (!store_.upsert(game))
        return "Unable to save the new game right now.";

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
    const bool history_complete = game.uci_moves.size() == game.moves.size();
    const std::vector<std::string> history = history_complete
                                                 ? game.uci_moves
                                                 : std::vector<std::string>();
    try {
        engine_.ensure_started();
    } catch (const std::exception&) {
        return "The chess engine is unavailable right now. Please try again.";
    }

    UciResult uci = engine_.san_to_uci(game.fen, san, history);
    if (!uci.ok)
        return "Invalid move or error: " + san;

    UciResult san_after_user = engine_.uci_to_san(game.fen, uci.value, history);
    std::string user_san = san_after_user.ok ? san_after_user.value : san;

    if (!engine_.play(uci.value))
        return "Unable to process the chess move. Please try again.";
    UciResult fen_after_user = engine_.fen_of();
    if (!fen_after_user.ok)
        return "Unable to process the chess move. Please try again.";

    game.fen = fen_after_user.value;
    std::vector<std::string> history_after_user = history;
    if (history_complete)
        history_after_user.push_back(uci.value);

    UciResult st_user = engine_.status_of(game.fen, history_after_user);
    if (!st_user.ok)
        return "Unable to verify the chess position. Please try again.";
    std::string status_value = st_user.value;
    if (starts_with(status_value, "checkmate") || status_value == "stalemate" ||
        status_value == "draw") {
        game.moves.push_back(user_san);
        if (history_complete)
            game.uci_moves = history_after_user;
        else
            game.uci_moves.clear();
        game.status = "completed";
        game.winner = status_winner(status_value);
        if (!store_.upsert(game))
            return "Unable to save the completed game right now.";
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
    UciResult cpu_san_res = engine_.uci_to_san(game.fen, best.value, history_after_user);
    if (!cpu_san_res.ok)
        return "I couldn't validate my move; please try again.";
    std::string cpu_san = cpu_san_res.value;
    if (!engine_.play(best.value))
        return "I couldn't apply my move; please try again.";
    UciResult fen_after_cpu = engine_.fen_of();
    if (!fen_after_cpu.ok)
        return "I couldn't finish my move; please try again.";
    game.moves.push_back(user_san);
    game.fen = fen_after_cpu.value;
    game.moves.push_back(cpu_san);
    if (history_complete) {
        history_after_user.push_back(best.value);
        game.uci_moves = history_after_user;
    } else {
        game.uci_moves.clear();
    }

    UciResult st_cpu = engine_.status_of(game.fen, game.uci_moves);
    if (!st_cpu.ok)
        return "Unable to verify the chess position. Please try again.";
    std::string status_cpu = st_cpu.value;

    std::string reply = "You played " + user_san + ". I played " + cpu_san + ".";
    if (starts_with(status_cpu, "checkmate") || status_cpu == "stalemate" ||
        status_cpu == "draw") {
        game.status = "completed";
        game.winner = status_winner(status_cpu);
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
    if (!store_.upsert(game))
        return "Unable to save the chess move right now. Please try again.";
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
    if (!store_.upsert(game))
        return "Unable to save the resignation right now.";
    return "Game resigned. " + capitalize(game.winner) + " wins!";
}

std::string ChessService::draw(int64_t chat_id) {
    std::optional<Game> existing = store_.find_any(chat_id);
    if (!existing || existing->status != "active")
        return "No active game to draw.";
    Game game = *existing;
    game.status = "completed";
    game.winner = "draw";
    if (!store_.upsert(game))
        return "Unable to save the draw right now.";
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
