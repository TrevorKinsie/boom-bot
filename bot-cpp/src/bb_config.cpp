#include "bb_config.h"

#include "bb_util.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sys/stat.h>

#ifdef _WIN32
#include <direct.h>
#endif

namespace bb {
namespace cfg {

std::string TELEGRAM_TOKEN;
std::string LLM_API_KEY;
std::vector<std::string> LLM_MODELS;
bool LLM_FOLLOW_MODEL_HINTS = false;
double LLM_TIMEOUT = 30.0;
std::string LLM_REFERER;
std::string LLM_APP_NAME = "boom-bot";

std::string DATA_DIR;
std::string ANSWERS_FILE;
std::string GAME_DATA_FILE;
std::string BOOM_COUNT_FILE;

std::string CASINO_DEFAULT_STORAGE = "sqlite";
std::string CASINO_EVENT_STORE_JSON_FILE;
std::string CASINO_EVENT_STORE_SQLITE_FILE;
int64_t CASINO_SNAPSHOT_THRESHOLD = 50;
std::string CASINO_STARTING_BALANCE = "100.00";
std::string CASINO_CURRENCY_QUANTIZATION = "0.01";
std::string ZEUS_SPIN_COST = "10.00";
int64_t LEADERBOARD_SIZE = 10;

std::string DECISION_ENGINE_JAR;
std::string DECISION_ENGINE_RUST_BIN;
std::string DECISION_ENGINE_MODE = "auto";
double DECISION_ENGINE_TIMEOUT_SECONDS = 5.0;

std::string CHESS_ENGINE_PATH;
int64_t CHESS_ENGINE_DEPTH = 14;
std::string CHESS_GAMES_FILE;

namespace {

std::string env_or(const char* name, const std::string& dflt) {
    const char* v = std::getenv(name);
    return (v && *v) ? std::string(v) : dflt;
}

bool env_true(const char* name) {
    std::string v = to_lower_ascii(trim(env_or(name, "")));
    return v == "1" || v == "true" || v == "yes" || v == "on";
}

double env_double(const char* name, double dflt) {
    std::string v = trim(env_or(name, ""));
    if (v.empty())
        return dflt;
    auto parsed = parse_double(v);
    return parsed.has_value() ? *parsed : dflt;
}

int64_t env_int(const char* name, int64_t dflt) {
    std::string v = trim(env_or(name, ""));
    if (v.empty())
        return dflt;
    auto parsed = parse_int(v);
    return parsed.has_value() ? *parsed : dflt;
}

bool dir_exists(const std::string& path) {
    struct stat st {};
    return stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
}

std::string resolve_data_dir() {
    // Python: DEFAULT_DATA_DIR = /data if it is a directory, else <repo>/data.
    std::string explicit_dir = trim(env_or("BOT_DATA_DIR", ""));
    if (!explicit_dir.empty())
        return explicit_dir;
    if (dir_exists("/data"))
        return "/data";
    return "./data";
}

void ensure_dir(const std::string& path) {
#ifdef _WIN32
    _mkdir(path.c_str());
#else
    mkdir(path.c_str(), 0755);
#endif
}

} // namespace

void load_config() {
#ifdef _WIN32
    TELEGRAM_TOKEN = env_or("TELEGRAM_TOKEN_DEV", "");
#else
    TELEGRAM_TOKEN = env_or("TELEGRAM_TOKEN", "");
#endif

    LLM_API_KEY = env_or("LLM_API_KEY", "");
    // LLM_MODELS takes precedence over LLM_MODEL, matching Python.
    std::string chain = env_or("LLM_MODELS", "");
    if (chain.empty())
        chain = env_or("LLM_MODEL", "");
    LLM_MODELS.clear();
    for (const std::string& part : split(chain, ",")) {
        std::string model = trim(part);
        if (!model.empty())
            LLM_MODELS.push_back(model);
    }
    if (LLM_MODELS.empty())
        LLM_MODELS.push_back("openrouter/free");
    LLM_FOLLOW_MODEL_HINTS = env_true("LLM_FOLLOW_MODEL_HINTS");
    LLM_TIMEOUT = env_double("LLM_TIMEOUT", 30.0);
    LLM_REFERER = env_or("LLM_REFERER", "");
    LLM_APP_NAME = env_or("LLM_APP_NAME", "boom-bot");

    DATA_DIR = resolve_data_dir();
    ensure_dir(DATA_DIR);
    ANSWERS_FILE = DATA_DIR + "/question_answers.json";
    GAME_DATA_FILE = DATA_DIR + "/game_data.json";
    BOOM_COUNT_FILE = DATA_DIR + "/boom_count.json";

    CASINO_DEFAULT_STORAGE = to_lower_ascii(env_or("CASINO_STORAGE", "sqlite"));
    CASINO_EVENT_STORE_JSON_FILE = env_or("CASINO_EVENT_STORE_JSON", DATA_DIR + "/casino_events.json");
    CASINO_EVENT_STORE_SQLITE_FILE = env_or("CASINO_EVENT_STORE_SQLITE", DATA_DIR + "/casino.sqlite3");
    CASINO_SNAPSHOT_THRESHOLD = env_int("CASINO_SNAPSHOT_THRESHOLD", 50);
    CASINO_STARTING_BALANCE = env_or("CASINO_STARTING_BALANCE", "100.00");
    CASINO_CURRENCY_QUANTIZATION = env_or("CASINO_CURRENCY_QUANTIZATION", "0.01");
    ZEUS_SPIN_COST = env_or("ZEUS_SPIN_COST", "10.00");
    LEADERBOARD_SIZE = env_int("LEADERBOARD_SIZE", 10);

    DECISION_ENGINE_JAR = env_or("DECISION_ENGINE_JAR", "decision-engine/build/jvm-decision-engine.jar");
    DECISION_ENGINE_RUST_BIN = env_or("DECISION_ENGINE_RUST_BIN", "decision-engine/build/atomic_cli");
    DECISION_ENGINE_MODE = to_lower_ascii(env_or("DECISION_ENGINE_MODE", "auto"));
    if (DECISION_ENGINE_MODE != "auto" && DECISION_ENGINE_MODE != "jvm" &&
        DECISION_ENGINE_MODE != "reference") {
        DECISION_ENGINE_MODE = "auto";
    }
    DECISION_ENGINE_TIMEOUT_SECONDS = env_double("DECISION_ENGINE_TIMEOUT_SECONDS", 5.0);

    CHESS_ENGINE_PATH = env_or("CHESS_ENGINE_PATH", "../chess-objc/build/chess-objc");
    CHESS_ENGINE_DEPTH = std::max<int64_t>(1, env_int("CHESS_ENGINE_DEPTH", 14));
    CHESS_GAMES_FILE = env_or("CHESS_GAMES_FILE", DATA_DIR + "/chess_games.json");
}

} // namespace cfg
} // namespace bb