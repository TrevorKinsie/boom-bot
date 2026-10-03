/*
 * bb_data.h - DataManager singleton for all JSON-backed bot data.
 *
 * Mirrors boombot/core/data_manager.py: one in-memory state store for the
 * legacy games (game_data.json), the shared boom counter (boom_count.json)
 * and the howmanybooms answer map (question_answers.json). File writes use
 * Python-compatible 4-space indented JSON with raw UTF-8.
 */
#ifndef BB_DATA_H
#define BB_DATA_H

#include "bb_json.h"

#include <cstdint>
#include <map>
#include <string>

namespace bb {

class DataManager {
public:
    // Default paths come from cfg; a DataManager with explicit paths is used
    // by the self-tests.
    DataManager(const std::string& game_data_file = "",
                const std::string& answers_file = "",
                const std::string& boom_count_file = "");

    void reset_paths(const std::string& game_data_file,
                     const std::string& answers_file,
                     const std::string& boom_count_file);

    // Reload every backing file from disk (boom count, answers, game data).
    void reload_all();

    // --- Boom counter ---
    int64_t load_boom_count();
    void save_boom_count();
    int64_t get_boom_count() const { return boom_count_; }
    void set_boom_count(int64_t count);
    void increment_boom_count();

    // --- Question/answer map ---
    const Json& load_answers();
    void save_answers();
    const Json& get_answers() const { return answers_; }
    void update_answer(const std::string& key, Json value);

    // --- Game data (channels and players) ---
    Json& get_channel_data(const std::string& channel_id);
    void save_channel_data(const std::string& channel_id, const Json& data);
    Json& get_player_data(const std::string& channel_id, const std::string& user_id);
    void save_player_data(const std::string& channel_id, const std::string& user_id,
                          const Json& data);
    // Players in a channel with non-empty bets for the given game ("craps").
    Json get_players_with_bets(const std::string& channel_id, const std::string& game);
    Json get_all_players_data(const std::string& channel_id);

private:
    void load_data();
    void save_data();

    void ensure_channel(const std::string& channel_id);
    static Json default_channel();

    std::string game_data_file_;
    std::string answers_file_;
    std::string boom_count_file_;
    int64_t boom_count_ = 0;
    Json answers_ = Json::object();
    Json game_data_ = Json::object(); // channel_id -> {channel_state, players}
};

// Module-level singleton + legacy free functions.
DataManager& get_data_manager();
void reset_data_manager();

int64_t load_boom_count();
void save_boom_count();
int64_t get_boom_count();
const Json& load_answers();
void save_answers();
const Json& get_answers();
void update_answer(const std::string& key, Json value);

} // namespace bb

#endif // BB_DATA_H