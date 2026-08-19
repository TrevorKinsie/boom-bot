#include "bb_telegram.h"

#include <cstdio>

#include "bb_http.h"
#include "bb_json.h"

namespace bb {

namespace {

const char* API_BASE = "https://api.telegram.org/bot";

std::string api_url(const std::string& token, const std::string& method) {
    return std::string(API_BASE) + token + "/" + method;
}

int64_t as_id(const Json& json, const char* key) {
    const Json* v = json.find(key);
    if (!v || !v->is_number())
        return 0;
    return v->as_int();
}

TelegramUser parse_user(const Json& json) {
    TelegramUser u;
    u.id = as_id(json, "id");
    u.first_name = json.get_string("first_name");
    u.last_name = json.get_string("last_name");
    u.username = json.get_string("username");
    return u;
}

TelegramChat parse_chat(const Json& json) {
    TelegramChat c;
    c.id = as_id(json, "id");
    c.type = json.get_string("type");
    c.title = json.get_string("title");
    return c;
}

TelegramMessage parse_message(const Json& json) {
    TelegramMessage m;
    m.message_id = as_id(json, "message_id");
    if (const Json* chat = json.find("chat"))
        m.chat = parse_chat(*chat);
    if (const Json* from = json.find("from"))
        m.from = parse_user(*from);
    m.text = json.get_string("text");
    m.caption = json.get_string("caption");
    if (const Json* photo = json.find("photo"))
        m.has_photo = photo->is_array() && photo->size() > 0;
    if (const Json* reply = json.find("reply_to_message")) {
        m.is_reply = reply->is_object();
        if (m.is_reply)
            m.reply_to_message_id = as_id(*reply, "message_id");
    }
    return m;
}

TelegramCallbackQuery parse_callback(const Json& json) {
    TelegramCallbackQuery q;
    q.id = json.get_string("id");
    if (const Json* from = json.find("from"))
        q.from = parse_user(*from);
    if (const Json* msg = json.find("message")) {
        q.message_message_id = as_id(*msg, "message_id");
        if (const Json* chat = msg->find("chat"))
            q.message_chat_id = as_id(*chat, "id");
    }
    q.data = json.get_string("data");
    return q;
}

} // namespace

TelegramUpdate parse_update(const Json& json) {
    TelegramUpdate u;
    u.update_id = as_id(json, "update_id");
    if (const Json* msg = json.find("message")) {
        u.message = parse_message(*msg);
        u.has_message = true;
    }
    if (const Json* cb = json.find("callback_query")) {
        u.callback = parse_callback(*cb);
        u.has_callback = true;
    }
    return u;
}

int64_t telegram_send_message(const std::string& token, int64_t chat_id,
                              const std::string& text,
                              const std::string& parse_mode,
                              const std::string& reply_markup) {
    if (text.empty())
        return 0;
    Json body = Json::object();
    body.set("chat_id", Json(chat_id));
    body.set("text", Json(text));
    if (!parse_mode.empty())
        body.set("parse_mode", Json(parse_mode));
    if (!reply_markup.empty())
        body.set("reply_markup", Json(reply_markup));
    HttpResponse resp = http_post(api_url(token, "sendMessage"),
                                  {"Content-Type: application/json"},
                                  body.dump(), 30.0);
    if (!resp.ok())
        return 0;
    try {
        Json payload = Json::parse(resp.body);
        const Json* result = payload.find("result");
        if (!result || !result->is_object())
            return 0;
        return as_id(*result, "message_id");
    } catch (const JsonError&) {
        return 0;
    }
}

bool telegram_edit_message_text(const std::string& token, int64_t chat_id,
                                int64_t message_id, const std::string& text,
                                const std::string& reply_markup) {
    Json body = Json::object();
    body.set("chat_id", Json(chat_id));
    body.set("message_id", Json(message_id));
    body.set("text", Json(text));
    if (!reply_markup.empty())
        body.set("reply_markup", Json(reply_markup));
    HttpResponse resp = http_post(api_url(token, "editMessageText"),
                                  {"Content-Type: application/json"},
                                  body.dump(), 30.0);
    return resp.ok();
}

bool telegram_answer_callback_query(const std::string& token,
                                    const std::string& callback_query_id,
                                    const std::string& text) {
    Json body = Json::object();
    body.set("callback_query_id", Json(callback_query_id));
    if (!text.empty())
        body.set("text", Json(text));
    HttpResponse resp = http_post(api_url(token, "answerCallbackQuery"),
                                  {"Content-Type: application/json"},
                                  body.dump(), 30.0);
    return resp.ok();
}

std::string telegram_bot_username(const std::string& token) {
    HttpResponse resp = http_get(api_url(token, "getMe"), {}, 30.0);
    if (!resp.ok())
        return "";
    try {
        Json payload = Json::parse(resp.body);
        const Json* result = payload.find("result");
        if (!result || !result->is_object())
            return "";
        return result->get_string("username");
    } catch (const JsonError&) {
        return "";
    }
}

std::vector<TelegramUpdate> telegram_get_updates(const std::string& token,
                                                 int64_t offset,
                                                 int timeout_seconds) {
    std::vector<TelegramUpdate> out;
    char url[512];
    std::snprintf(url, sizeof(url), "%s/getUpdates?offset=%lld&timeout=%d",
                  api_url(token, "getUpdates").c_str(),
                  static_cast<long long>(offset), timeout_seconds);
    HttpResponse resp = http_get(url, {}, static_cast<double>(timeout_seconds) + 15.0);
    if (!resp.ok())
        return out;
    try {
        Json payload = Json::parse(resp.body);
        const Json* result = payload.find("result");
        if (!result || !result->is_array())
            return out;
        for (const Json& item : result->as_array())
            out.push_back(parse_update(item));
    } catch (const JsonError&) {
    }
    return out;
}

bool parse_command(const std::string& text, const std::string& bot_username,
                   std::string& command, std::vector<std::string>& args) {
    command.clear();
    args.clear();
    size_t token_end = text.find_first_of(" \t\n");
    std::string token = text.substr(0, token_end);
    if (token.empty() || token[0] != '/')
        return false;

    size_t at = token.find('@');
    if (at != std::string::npos) {
        std::string bot_name = token.substr(at + 1);
        if (!bot_username.empty() && bot_name != bot_username)
            return false;
        token = token.substr(0, at);
    }
    if (token.size() < 2)
        return false;
    command = token.substr(1);

    std::string rest = token_end != std::string::npos ? text.substr(token_end) : "";
    size_t i = 0;
    while (i <= rest.size()) {
        while (i < rest.size() && (rest[i] == ' ' || rest[i] == '\t' || rest[i] == '\n'))
            ++i;
        if (i >= rest.size())
            break;
        size_t start = i;
        while (i < rest.size() && rest[i] != ' ' && rest[i] != '\t' && rest[i] != '\n')
            ++i;
        args.push_back(rest.substr(start, i - start));
    }
    return true;
}

} // namespace bb