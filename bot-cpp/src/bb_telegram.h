/*
 * bb_telegram.h - minimal Telegram Bot API client (long-polling).
 *
 * Mirrors the surface used by the Python port (python-telegram-bot):
 * getUpdates long polling, sendMessage, editMessageText,
 * answerCallbackQuery and getMe.  HTTPS goes through bb_http (curl
 * subprocess); request/response bodies are JSON via bb_json.
 */
#ifndef BB_TELEGRAM_H
#define BB_TELEGRAM_H

#include <cstdint>
#include <string>
#include <vector>

namespace bb {

struct TelegramUser {
    int64_t id = 0;
    std::string first_name;
    std::string last_name;
    std::string username;

    std::string full_name() const {
        if (!last_name.empty())
            return first_name + " " + last_name;
        return first_name;
    }
};

struct TelegramChat {
    int64_t id = 0;
    std::string type;   // private | group | supergroup | channel
    std::string title;  // groups/channels only
};

struct TelegramMessage {
    int64_t message_id = 0;
    TelegramChat chat;
    TelegramUser from;
    std::string text;       // TEXT messages and command text
    std::string caption;    // media captions
    bool has_photo = false;
    bool is_reply = false;
    int64_t reply_to_message_id = 0;
};

struct TelegramCallbackQuery {
    std::string id;
    TelegramUser from;
    int64_t message_chat_id = 0;
    int64_t message_message_id = 0;
    std::string data;
};

struct TelegramUpdate {
    int64_t update_id = 0;
    bool has_message = false;
    TelegramMessage message;
    bool has_callback = false;
    TelegramCallbackQuery callback;
};

// Parse a single update object from JSON (never throws on malformed input).
TelegramUpdate parse_update(const class Json& json);

// Send message: returns Telegram message_id on success, 0 on failure.
int64_t telegram_send_message(const std::string& token, int64_t chat_id,
                              const std::string& text,
                              const std::string& parse_mode = "",
                              const std::string& reply_markup = "");

// Edit an existing message (used by inline-keyboard flows).
bool telegram_edit_message_text(const std::string& token, int64_t chat_id,
                                int64_t message_id, const std::string& text,
                                const std::string& reply_markup = "");

// Acknowledge a callback query (empty text = plain acknowledgement).
bool telegram_answer_callback_query(const std::string& token,
                                    const std::string& callback_query_id,
                                    const std::string& text = "");

// Returns the bot's own username (no '@'), or empty on failure.
std::string telegram_bot_username(const std::string& token);

// Long-poll getUpdates. Returns updates with update_id > offset, and sets
// `next_offset` to the id to pass next time.
std::vector<TelegramUpdate> telegram_get_updates(const std::string& token,
                                                 int64_t offset,
                                                 int timeout_seconds);

// python-telegram-bot COMMAND semantics: the first token must begin with '/';
// a trailing "@username" only matches when it equals the bot's own username
// (ignored when bot_username is empty).  Returns false when the text is not a
// command for this bot.  Args are whitespace-split Python str.split() style.
bool parse_command(const std::string& text, const std::string& bot_username,
                   std::string& command, std::vector<std::string>& args);

} // namespace bb

#endif // BB_TELEGRAM_H