#include "tests.h"

#include "bb_data.h"
#include "bb_json.h"
#include "bb_money.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <unistd.h>

using namespace bb;

namespace {

std::string temp_dir(const char* label) {
    std::string dir = std::string("/tmp/bb_test_") + label;
    std::string cmd = "rm -rf '" + dir + "' && mkdir -p '" + dir + "'";
    (void)system(cmd.c_str());
    return dir;
}

void write_file(const std::string& path, const std::string& content) {
    std::string cmd = "cat > '" + path + "' << 'BBEOF'\n" + content + "\nBBEOF";
    (void)system(cmd.c_str());
}

std::string read_file(const std::string& path) {
    std::ifstream stream(path);
    if (!stream)
        return "";
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    return buffer.str();
}

bool file_exists(const std::string& path) {
    return access(path.c_str(), F_OK) == 0;
}

} // namespace

TEST_CASE(data_manager_boom_count_file_exists) {
    std::string dir = temp_dir("boom_exists");
    std::string file = dir + "/boom_count.json";
    write_file(file, "{\"boom_count\": 42}");
    DataManager dm("", "", file);
    CHECK_INT_EQ(dm.load_boom_count(), 42);
    CHECK_INT_EQ(dm.get_boom_count(), 42);
}

TEST_CASE(data_manager_boom_count_file_not_found) {
    std::string dir = temp_dir("boom_missing");
    DataManager dm("", "", dir + "/none.json");
    CHECK_INT_EQ(dm.load_boom_count(), 0);
    CHECK_INT_EQ(dm.get_boom_count(), 0);
}

TEST_CASE(data_manager_boom_count_invalid_json) {
    std::string dir = temp_dir("boom_invalid");
    std::string file = dir + "/invalid.json";
    write_file(file, "invalid json");
    DataManager dm("", "", file);
    CHECK_INT_EQ(dm.load_boom_count(), 0);
}

TEST_CASE(data_manager_save_boom_count) {
    std::string dir = temp_dir("boom_save");
    std::string file = dir + "/saved.json";
    DataManager dm("", "", file);
    dm.set_boom_count(55);
    CHECK(file_exists(file));
    DataManager reload("", "", file);
    CHECK_INT_EQ(reload.load_boom_count(), 55);
    CHECK_STR_EQ(Json::parse(read_file(file)).dump(), "{\"boom_count\": 55}");
}

TEST_CASE(data_manager_answers_file_exists) {
    std::string dir = temp_dir("answers_exists");
    std::string file = dir + "/answers.json";
    write_file(file, "{\"q1\": \"a1\", \"q2\": \"a2\"}");
    DataManager dm("", file, "");
    const Json& answers = dm.load_answers();
    CHECK(answers.is_object());
    CHECK_INT_EQ(answers.as_object().size(), 2);
    CHECK_STR_EQ(answers.get_string("q1"), "a1");
    CHECK_STR_EQ(answers.get_string("q2"), "a2");
}

TEST_CASE(data_manager_answers_file_not_found) {
    std::string dir = temp_dir("answers_missing");
    DataManager dm("", dir + "/none.json", "");
    const Json& answers = dm.load_answers();
    CHECK(answers.is_object());
    CHECK(answers.as_object().empty());
}

TEST_CASE(data_manager_answers_invalid_json) {
    std::string dir = temp_dir("answers_invalid");
    std::string file = dir + "/invalid.json";
    write_file(file, "invalid json");
    DataManager dm("", file, "");
    CHECK(dm.load_answers().as_object().empty());
}

TEST_CASE(data_manager_save_answers) {
    std::string dir = temp_dir("answers_save");
    std::string file = dir + "/saved.json";
    DataManager dm("", file, "");
    dm.update_answer("hello", Json("world"));
    dm.update_answer("test", Json("data"));
    CHECK(file_exists(file));
    DataManager reload("", file, "");
    const Json& loaded = reload.load_answers();
    CHECK_STR_EQ(loaded.get_string("hello"), "world");
    CHECK_STR_EQ(loaded.get_string("test"), "data");
    CHECK(Json::parse(read_file(file)).has("hello"));
}

TEST_CASE(data_manager_update_answer) {
    std::string dir = temp_dir("answers_update");
    std::string file = dir + "/update.json";
    DataManager dm("", file, "");
    dm.update_answer("new_q", Json(int64_t(4)));
    CHECK_INT_EQ(dm.get_answers().get_int("new_q"), 4);
    DataManager reload("", file, "");
    CHECK_INT_EQ(reload.load_answers().get_int("new_q"), 4);
}

TEST_CASE(data_manager_game_data_round_trip) {
    std::string dir = temp_dir("game_data");
    std::string file = dir + "/game_data.json";
    DataManager dm(file, "", "");

    Json channel_state = Json::object();
    channel_state.set("craps_state", Json(int64_t(1)));
    dm.save_channel_data("-100", channel_state);

    Json player = dm.get_player_data("-100", "u1");
    CHECK_STR_EQ(player.get_string("balance"), "100.00");
    CHECK(player.has("craps_bets"));
    CHECK(player.has("roulette_bets"));
    player.set("balance", Json(std::string("42.50")));
    dm.save_player_data("-100", "u1", player);

    // Reload from disk.
    DataManager reload(file, "", "");
    const Json& state = reload.get_channel_data("-100");
    CHECK_INT_EQ(state.get_int("craps_state"), 1);
    CHECK_STR_EQ(reload.get_player_data("-100", "u1").get_string("balance"), "42.50");

    // A brand-new user in an existing channel gets the defaults.
    CHECK_STR_EQ(reload.get_player_data("-100", "u2").get_string("balance"), "100.00");
}

TEST_CASE(data_manager_players_with_bets) {
    std::string dir = temp_dir("game_bets");
    std::string file = dir + "/game_data.json";
    DataManager dm(file, "", "");

    Json bettor = dm.get_player_data("c1", "a");
    Json bets = Json::object();
    bets.set("pass_line", Json(std::string("10.00")));
    bettor.set("craps_bets", bets);
    dm.save_player_data("c1", "a", bettor);

    Json idle = dm.get_player_data("c1", "b");
    dm.save_player_data("c1", "b", idle);

    Json with_bets = dm.get_players_with_bets("c1", "craps");
    CHECK(with_bets.has("a"));
    CHECK(!with_bets.has("b"));
}

TEST_CASE(data_manager_empty_and_corrupt_game_data) {
    std::string dir = temp_dir("game_empty");
    std::string file = dir + "/game_data.json";
    write_file(file, "");
    DataManager dm(file, "", "");
    CHECK(dm.get_player_data("new-channel", "u").get_string("balance") == "100.00");

    write_file(file, "not json at all");
    DataManager corrupt(file, "", "");
    CHECK(corrupt.get_channel_data("x").is_object());
    CHECK(corrupt.get_player_data("x", "u").get_string("balance") == "100.00");
}

TEST_CASE(data_manager_boom_count_increment) {
    std::string dir = temp_dir("boom_inc");
    std::string file = dir + "/boom.json";
    DataManager dm("", "", file);
    dm.increment_boom_count();
    dm.increment_boom_count();
    CHECK_INT_EQ(dm.get_boom_count(), 2);
    DataManager reload("", "", file);
    CHECK_INT_EQ(reload.load_boom_count(), 2);
}