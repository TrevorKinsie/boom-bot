/*
 * bb_config.h - environment-driven configuration.
 *
 * Mirrors boombot/core/config.py. Reads the environment once at startup;
 * all defaults match the Python side exactly.
 */
#ifndef BB_CONFIG_H
#define BB_CONFIG_H

#include <string>
#include <vector>

namespace bb {
namespace cfg {

extern std::string TELEGRAM_TOKEN;          // TELEGRAM_TOKEN_DEV on Windows

// LLM / OpenRouter configuration.
extern std::string LLM_API_KEY;
extern std::vector<std::string> LLM_MODELS;
extern bool LLM_FOLLOW_MODEL_HINTS;
extern double LLM_TIMEOUT;
extern std::string LLM_REFERER;
extern std::string LLM_APP_NAME;

// Persistent data configuration.
extern std::string DATA_DIR;
extern std::string ANSWERS_FILE;
extern std::string GAME_DATA_FILE;
extern std::string BOOM_COUNT_FILE;

// Enterprise casino microkernel configuration.
extern std::string CASINO_DEFAULT_STORAGE;      // sqlite | json
extern std::string CASINO_EVENT_STORE_JSON_FILE;
extern std::string CASINO_EVENT_STORE_SQLITE_FILE;
extern int64_t CASINO_SNAPSHOT_THRESHOLD;
extern std::string CASINO_STARTING_BALANCE;
extern std::string CASINO_CURRENCY_QUANTIZATION;
extern std::string ZEUS_SPIN_COST;
extern int64_t LEADERBOARD_SIZE;

// JVM decision engine configuration.
extern std::string DECISION_ENGINE_JAR;
extern std::string DECISION_ENGINE_RUST_BIN;
extern std::string DECISION_ENGINE_MODE;        // auto | jvm | reference
extern double DECISION_ENGINE_TIMEOUT_SECONDS;

// Reads the environment (idempotent; call once at startup).
void load_config();

} // namespace cfg
} // namespace bb

#endif // BB_CONFIG_H