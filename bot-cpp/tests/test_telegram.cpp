#include "tests.h"

#include <string>
#include <vector>

#include "bb_json.h"
#include "bb_telegram.h"

using namespace bb;

TEST_CASE(telegram_parse_update_message) {
    const char* json =
        R"({"update_id": 42,
            "message": {
              "message_id": 7,
              "from": {"id": 123, "is_bot": false, "first_name": "Kevin",
                       "last_name": "Smith", "username": "kevins"},
              "chat": {"id": -1001, "type": "supergroup", "title": "The Zone"},
              "date": 1700000000,
              "text": "/boom 3"
            }})";
    TelegramUpdate u = parse_update(Json::parse(json));
    CHECK_INT_EQ(u.update_id, 42);
    CHECK(u.has_message);
    CHECK(!u.has_callback);
    CHECK_INT_EQ(u.message.message_id, 7);
    CHECK_INT_EQ(u.message.from.id, 123);
    CHECK_STR_EQ(u.message.from.first_name, "Kevin");
    CHECK_STR_EQ(u.message.from.full_name(), "Kevin Smith");
    CHECK_STR_EQ(u.message.from.username, "kevins");
    CHECK_INT_EQ(u.message.chat.id, -1001);
    CHECK_STR_EQ(u.message.chat.type, "supergroup");
    CHECK_STR_EQ(u.message.chat.title, "The Zone");
    CHECK_STR_EQ(u.message.text, "/boom 3");
    CHECK(!u.message.has_photo);
    CHECK(!u.message.is_reply);
}

TEST_CASE(telegram_parse_update_photo_and_reply) {
    const char* json =
        R"({"update_id": 43,
            "message": {
              "message_id": 8,
              "from": {"id": 9, "is_bot": false, "first_name": "Bob"},
              "chat": {"id": -1002, "type": "group"},
              "caption": "Photo /howmanybooms for cats",
              "photo": [{"file_id": "f1", "width": 10, "height": 10}],
              "reply_to_message": {"message_id": 3, "chat": {"id": -1002}}
            }})";
    TelegramUpdate u = parse_update(Json::parse(json));
    CHECK(u.has_message);
    CHECK_INT_EQ(u.message.message_id, 8);
    CHECK(u.message.has_photo);
    CHECK_STR_EQ(u.message.caption, "Photo /howmanybooms for cats");
    CHECK(u.message.is_reply);
    CHECK_INT_EQ(u.message.reply_to_message_id, 3);
}

TEST_CASE(telegram_parse_update_callback) {
    const char* json =
        R"({"update_id": 44,
            "callback_query": {
              "id": "cb-1",
              "from": {"id": 55, "is_bot": false, "first_name": "Alice"},
              "message": {"message_id": 9,
                          "chat": {"id": -1003, "type": "supergroup"}},
              "data": "craps_roll"
            }})";
    TelegramUpdate u = parse_update(Json::parse(json));
    CHECK(!u.has_message);
    CHECK(u.has_callback);
    CHECK_STR_EQ(u.callback.id, "cb-1");
    CHECK_INT_EQ(u.callback.from.id, 55);
    CHECK_INT_EQ(u.callback.message_chat_id, -1003);
    CHECK_INT_EQ(u.callback.message_message_id, 9);
    CHECK_STR_EQ(u.callback.data, "craps_roll");
}

TEST_CASE(telegram_parse_update_edge_cases) {
    TelegramUpdate u = parse_update(Json::object());
    CHECK_INT_EQ(u.update_id, 0);
    CHECK(!u.has_message);
    CHECK(!u.has_callback);

    TelegramUpdate v = parse_update(Json::parse(R"({"update_id": 1, "message": {}})"));
    CHECK_INT_EQ(v.update_id, 1);
    CHECK(v.has_message);
    CHECK_INT_EQ(v.message.message_id, 0);
    CHECK_STR_EQ(v.message.text, "");
    CHECK(!v.message.has_photo);
}

TEST_CASE(telegram_parse_command) {
    std::string command;
    std::vector<std::string> args;

    CHECK(parse_command("/boom 3", "boom_bot", command, args));
    CHECK_STR_EQ(command, "boom");
    CHECK_INT_EQ(static_cast<int>(args.size()), 1);
    CHECK_STR_EQ(args[0], "3");

    CHECK(parse_command("/boom", "boom_bot", command, args));
    CHECK_STR_EQ(command, "boom");
    CHECK_INT_EQ(static_cast<int>(args.size()), 0);

    CHECK(parse_command("/howmanybooms how many booms for cats?", "boom_bot", command, args));
    CHECK_STR_EQ(command, "howmanybooms");
    CHECK_INT_EQ(static_cast<int>(args.size()), 5);
    CHECK_STR_EQ(args[4], "cats?");

    // Bot username suffixed commands.
    CHECK(parse_command("/boom@boom_bot 5", "boom_bot", command, args));
    CHECK_STR_EQ(command, "boom");
    CHECK_STR_EQ(args[0], "5");
    CHECK(!parse_command("/boom@other_bot 5", "boom_bot", command, args));
    // When the bot username is unknown, the @ suffix is ignored.
    CHECK(parse_command("/boom@whatever 5", "", command, args));
    CHECK_STR_EQ(command, "boom");

    // Non-commands.
    CHECK(!parse_command("hello /boom", "boom_bot", command, args));
    CHECK(!parse_command("", "boom_bot", command, args));
    CHECK(!parse_command("/", "boom_bot", command, args));
    CHECK(!parse_command("not a command", "boom_bot", command, args));
}

TEST_CASE(telegram_parse_command_whitespace) {
    std::string command;
    std::vector<std::string> args;

    CHECK(parse_command("/boom\t3", "b", command, args));
    CHECK_STR_EQ(command, "boom");
    CHECK_STR_EQ(args[0], "3");

    CHECK(parse_command("/boom  5  ", "b", command, args));
    CHECK_INT_EQ(static_cast<int>(args.size()), 1);

    CHECK(parse_command("/boom\na b", "b", command, args));
    CHECK_INT_EQ(static_cast<int>(args.size()), 2);
}