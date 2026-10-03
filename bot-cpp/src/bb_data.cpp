#include "bb_data.h"

#include "bb_config.h"
#include "bb_log.h"

#include <atomic>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <unistd.h>

namespace bb {

namespace {

std::string read_file_or_empty(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream)
        return "";
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    return buffer.str();
}

bool write_file(const std::string& path, const std::string& content) {
    static std::atomic<uint64_t> counter{0};
    std::filesystem::path destination(path);
    std::error_code directory_error;
    if (destination.has_parent_path())
        std::filesystem::create_directories(destination.parent_path(), directory_error);
    if (directory_error)
        return false;

    std::string temporary = path + ".tmp." + std::to_string(static_cast<long long>(getpid())) +
                            "." + std::to_string(counter.fetch_add(1));
    std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
    if (!stream)
        return false;
    stream << content;
    stream.flush();
    if (!stream) {
        stream.close();
        std::error_code remove_error;
        std::filesystem::remove(temporary, remove_error);
        return false;
    }
    stream.close();
    if (!stream) {
        std::error_code remove_error;
        std::filesystem::remove(temporary, remove_error);
        return false;
    }

    int fd = open(temporary.c_str(), O_RDONLY);
    if (fd < 0 || fsync(fd) != 0) {
        if (fd >= 0)
            close(fd);
        std::error_code remove_error;
        std::filesystem::remove(temporary, remove_error);
        return false;
    }
    close(fd);
    std::error_code rename_error;
    std::filesystem::rename(temporary, path, rename_error);
    if (rename_error) {
        std::error_code remove_error;
        std::filesystem::remove(temporary, remove_error);
        return false;
    }
    return true;
}
} // namespace

DataManager::DataManager(const std::string& game_data_file,
                         const std::string& answers_file,
                         const std::string& boom_count_file) {
    reset_paths(game_data_file.empty() ? cfg::GAME_DATA_FILE : game_data_file,
                answers_file.empty() ? cfg::ANSWERS_FILE : answers_file,
                boom_count_file.empty() ? cfg::BOOM_COUNT_FILE : boom_count_file);
    load_data();
    load_boom_count();
    load_answers();
}

void DataManager::reset_paths(const std::string& game_data_file,
                              const std::string& answers_file,
                              const std::string& boom_count_file) {
    game_data_file_ = game_data_file;
    answers_file_ = answers_file;
    boom_count_file_ = boom_count_file;
    boom_count_ = 0;
    answers_ = Json::object();
    game_data_ = Json::object();
}

// --- Boom counter ---

int64_t DataManager::load_boom_count() {
    boom_count_ = 0;
    std::string content = read_file_or_empty(boom_count_file_);
    if (content.empty())
        return boom_count_;
    try {
        Json parsed = Json::parse(content);
        boom_count_ = parsed.get_int("boom_count", 0);
    } catch (const JsonError&) {
        BB_ERROR("data", "Error loading boom count file: " + boom_count_file_);
        boom_count_ = 0;
    }
    return boom_count_;
}

void DataManager::reload_all() {
    load_data();
    load_boom_count();
    load_answers();
}

void DataManager::save_boom_count() {
    Json payload = Json::object();
    payload.set("boom_count", Json(boom_count_));
    if (!write_file(boom_count_file_, payload.dump()))
        BB_ERROR("data", "Error saving boom count file: " + boom_count_file_);
}

void DataManager::set_boom_count(int64_t count) {
    boom_count_ = count;
    save_boom_count();
}

void DataManager::increment_boom_count() {
    ++boom_count_;
    save_boom_count();
}

// --- Question/answer map ---

const Json& DataManager::load_answers() {
    answers_ = Json::object();
    std::string content = read_file_or_empty(answers_file_);
    if (content.empty())
        return answers_;
    try {
        answers_ = Json::parse(content);
        if (!answers_.is_object())
            answers_ = Json::object();
    } catch (const JsonError&) {
        BB_ERROR("data", "Error loading or parsing answers file: " + answers_file_);
        answers_ = Json::object();
    }
    return answers_;
}

void DataManager::save_answers() {
    if (!write_file(answers_file_, answers_.dump(4)))
        BB_ERROR("data", "Error saving answers file: " + answers_file_);
}

void DataManager::update_answer(const std::string& key, Json value) {
    answers_.set(key, std::move(value));
    save_answers();
}

// --- Game data ---

Json DataManager::default_channel() {
    Json channel = Json::object();
    channel.set("channel_state", Json::object());
    channel.set("players", Json::object());
    return channel;
}

void DataManager::ensure_channel(const std::string& channel_id) {
    const Json* existing = game_data_.find(channel_id);
    if (existing == nullptr || !existing->is_object()) {
        game_data_.set(channel_id, default_channel());
        return;
    }
    Json& channel = const_cast<Json&>(*existing);
    if (!channel.has("channel_state") || !channel.find("channel_state")->is_object())
        channel.set("channel_state", Json::object());
    if (!channel.has("players") || !channel.find("players")->is_object())
        channel.set("players", Json::object());
}

void DataManager::load_data() {
    game_data_ = Json::object();
    std::string content = read_file_or_empty(game_data_file_);
    if (content.empty())
        return;
    try {
        Json parsed = Json::parse(content);
        if (!parsed.is_object() || parsed.as_object().empty())
            return;
        for (const auto& [channel_id, raw] : parsed.as_object()) {
            if (!raw.is_object())
                continue;
            Json channel = default_channel();
            const Json* state = raw.find("channel_state");
            if (state != nullptr && state->is_object())
                channel.set("channel_state", *state);
            const Json* players = raw.find("players");
            if (players != nullptr && players->is_object())
                channel.set("players", *players);
            game_data_.set(channel_id, channel);
        }
    } catch (const JsonError&) {
        BB_ERROR("data", "Error loading game data file " + game_data_file_);
        game_data_ = Json::object();
    }
}

void DataManager::save_data() {
    if (!write_file(game_data_file_, game_data_.dump(4)))
        BB_ERROR("data", "Error saving game data file: " + game_data_file_);
}

Json& DataManager::get_channel_data(const std::string& channel_id) {
    ensure_channel(channel_id);
    return const_cast<Json&>(*game_data_.find(channel_id)->find("channel_state"));
}

void DataManager::save_channel_data(const std::string& channel_id, const Json& data) {
    ensure_channel(channel_id);
    const_cast<Json&>(*game_data_.find(channel_id)->find("channel_state")) = data;
    save_data();
}

Json& DataManager::get_player_data(const std::string& channel_id, const std::string& user_id) {
    ensure_channel(channel_id);
    Json& players = const_cast<Json&>(*game_data_.find(channel_id)->find("players"));
    const Json* existing = players.find(user_id);
    if (existing == nullptr || !existing->is_object()) {
        Json player = Json::object();
        player.set("balance", Json("100.00"));
        player.set("craps_bets", Json::object());
        player.set("roulette_bets", Json::object());
        players.set(user_id, player);
    } else {
        Json& player = const_cast<Json&>(*existing);
        const Json* craps = player.find("craps_bets");
        if (craps == nullptr || !craps->is_object())
            player.set("craps_bets", Json::object());
        const Json* roulette = player.find("roulette_bets");
        if (roulette == nullptr || !roulette->is_object())
            player.set("roulette_bets", Json::object());
    }
    return const_cast<Json&>(*players.find(user_id));
}

void DataManager::save_player_data(const std::string& channel_id, const std::string& user_id,
                                   const Json& data) {
    ensure_channel(channel_id);
    Json& players = const_cast<Json&>(*game_data_.find(channel_id)->find("players"));
    players.set(user_id, data);
    save_data();
}

Json DataManager::get_players_with_bets(const std::string& channel_id, const std::string& game) {
    Json result = Json::object();
    ensure_channel(channel_id);
    const Json& players = *game_data_.find(channel_id)->find("players");
    std::string bet_key = game + "_bets";
    for (const auto& [user_id, player] : players.as_object()) {
        if (!player.is_object())
            continue;
        const Json* bets = player.find(bet_key);
        if (bets != nullptr && bets->is_object() && !bets->as_object().empty())
            result.set(user_id, player);
    }
    return result;
}

Json DataManager::get_all_players_data(const std::string& channel_id) {
    ensure_channel(channel_id);
    return *game_data_.find(channel_id)->find("players");
}

// --- Singleton + legacy free functions ---

DataManager& get_data_manager() {
    static DataManager instance;
    return instance;
}

void reset_data_manager() {
    DataManager& dm = get_data_manager();
    dm.reset_paths(cfg::GAME_DATA_FILE, cfg::ANSWERS_FILE, cfg::BOOM_COUNT_FILE);
    dm.reload_all();
}

int64_t load_boom_count() {
    return get_data_manager().load_boom_count();
}

void save_boom_count() {
    get_data_manager().save_boom_count();
}

int64_t get_boom_count() {
    return get_data_manager().get_boom_count();
}

const Json& load_answers() {
    return get_data_manager().load_answers();
}

void save_answers() {
    get_data_manager().save_answers();
}

const Json& get_answers() {
    return get_data_manager().get_answers();
}

void update_answer(const std::string& key, Json value) {
    get_data_manager().update_answer(key, value);
}

} // namespace bb
