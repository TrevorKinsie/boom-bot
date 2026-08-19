#include "bb_llm.h"

#include <string>
#include <vector>

#include "bb_config.h"
#include "bb_http.h"
#include "bb_json.h"
#include "bb_log.h"
#include "bb_util.h"

using bb::log::log_info;
using bb::log::log_warning;
using bb::log::log_error;

namespace bb {

namespace {

const char* OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

// Reasoning models otherwise spend the whole token budget thinking, leaving
// `content` empty. `enabled: false` turns thinking off where the model
// supports it; `exclude: true` keeps the trace out of the response for the
// models where it cannot be turned off.
const int MAX_TOKENS = 800;

const char* SYSTEM_PROMPT =
    "You are a ringside announcer for absurd hypothetical matchups. "
    "Always name a concrete winner. Never refuse, never hedge, never ask for "
    "clarification, never explain that the fight is hypothetical -- just call "
    "the fight. Reply with the battle summary line and nothing else -- no "
    "preamble, no reasoning, no notes about how you decided.";

std::vector<std::string> build_headers() {
    std::vector<std::string> headers;
    headers.push_back("Authorization: Bearer " + cfg::LLM_API_KEY);
    headers.push_back("Content-Type: application/json");
    if (!cfg::LLM_REFERER.empty())
        headers.push_back("HTTP-Referer: " + cfg::LLM_REFERER);
    if (!cfg::LLM_APP_NAME.empty())
        headers.push_back("X-Title: " + cfg::LLM_APP_NAME);
    return headers;
}

// Normalise a message field to non-empty text, if it holds any.
std::string as_text(const Json& value) {
    if (value.is_array()) {
        // Some providers return content as a list of typed parts.
        std::string joined;
        for (const Json& part : value.as_array())
            if (part.is_object())
                joined += part.get_string("text");
        return trim(joined);
    }
    if (value.is_string())
        return trim(value.as_string());
    return "";
}

// Is the 3-byte UTF-8 sequence at position i the right/left double quote
// U+201D / U+201C?
bool right_quote_at(const std::string& s, size_t i) {
    return i + 2 < s.size() && static_cast<unsigned char>(s[i]) == 0xE2 &&
           static_cast<unsigned char>(s[i + 1]) == 0x80 &&
           static_cast<unsigned char>(s[i + 2]) == 0x9D;
}

bool left_quote_at(const std::string& s, size_t i) {
    return i + 2 < s.size() && static_cast<unsigned char>(s[i]) == 0xE2 &&
           static_cast<unsigned char>(s[i + 1]) == 0x80 &&
           static_cast<unsigned char>(s[i + 2]) == 0x9C;
}

// Python str.strip("*") - strip all leading/trailing asterisks.
std::string strip_stars(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && s[b] == '*')
        ++b;
    while (e > b && s[e - 1] == '*')
        --e;
    return s.substr(b, e - b);
}

// Python str.strip("\"'“”") - strip quotes (UTF-8 aware for U+201C/U+201D).
std::string strip_quotes(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e) {
        if (s[b] == '\'' || s[b] == '"') {
            ++b;
        } else if (right_quote_at(s, b) || left_quote_at(s, b)) {
            b += 3;
        } else {
            break;
        }
    }
    while (e > b) {
        if (s[e - 1] == '\'' || s[e - 1] == '"') {
            --e;
        } else if (e >= 3 && (right_quote_at(s, e - 3) || left_quote_at(s, e - 3))) {
            e -= 3;
        } else {
            break;
        }
    }
    return s.substr(b, e - b);
}

// Pull the final call out of a reasoning trace, or give up.  `reasoning` is
// the model's private deliberation, never an answer, so it must not be
// forwarded as-is.  A trace that ran to completion does normally end on the
// verdict it settled on, so take that last line and nothing else.  A truncated
// trace stopped mid-thought and has no verdict to take.
std::string salvage_verdict_impl(const std::string& reasoning,
                                 const std::string& finish_reason) {
    if (finish_reason != "stop" && finish_reason != "end_turn")
        return "";

    std::vector<std::string> lines;
    for (const std::string& line : split(reasoning, "\n")) {
        std::string stripped = trim(line);
        if (!stripped.empty())
            lines.push_back(stripped);
    }
    if (lines.empty())
        return "";

    std::string candidate = lines.back();
    if (candidate.size() > MAX_SALVAGED_VERDICT_CHARS) {
        // A trailing wall of text: keep only the last complete sentence, which
        // is where the trace lands on its answer.
        candidate = last_sentence(candidate);
    }

    // Strip the decoration before the label, so "**Verdict: ...**" is matched.
    candidate = trim(candidate);
    candidate = strip_stars(candidate);
    candidate = strip_quotes(candidate);
    candidate = trim(candidate);
    candidate = strip_verdict_prefix(candidate);
    candidate = trim(strip_quotes(strip_stars(trim(candidate))));
    if (candidate.empty() || candidate.size() > MAX_SALVAGED_VERDICT_CHARS)
        return "";
    return candidate;
}

// Pull the assistant text out of a chat completion payload, if there is any.
std::string extract_text(const Json& payload) {
    const Json* choices = payload.find("choices");
    if (!choices || !choices->is_array() || choices->size() == 0)
        return "";
    const Json& first = choices->as_array()[0];
    if (!first.is_object())
        return "";
    const Json* message = first.find("message");
    if (!message || !message->is_object())
        return "";
    const std::string finish_reason = first.get_string("finish_reason");

    std::string content = "";
    if (const Json* c = message->find("content"))
        content = as_text(*c);
    if (!content.empty())
        return content;

    // Reasoning models sometimes leave `content` empty and put everything in
    // `reasoning`. Salvage the verdict off the end of it if there is one;
    // otherwise treat the model as having said nothing and move down the chain.
    std::string reasoning = "";
    if (const Json* r = message->find("reasoning"))
        reasoning = as_text(*r);
    if (!reasoning.empty()) {
        std::string verdict = salvage_verdict_impl(reasoning, finish_reason);
        if (!verdict.empty()) {
            log_info("Model returned no content; salvaged the verdict from its "
                     "reasoning trace.");
            return verdict;
        }
        log_warning("Discarding a reasoning trace with no usable verdict "
                    "(finish_reason='" + finish_reason + "')");
        return "";
    }

    log_warning("Empty completion (finish_reason='" + finish_reason + "')");
    return "";
}

// Ask a single model.  Returns the answer (empty on failure) and a
// replacement-model hint (only when OpenRouter's error names another slug).
struct CompletionResult {
    std::string answer;
    std::string replacement;
};

CompletionResult complete(const std::string& model, const std::string& question) {
    Json body = Json::object();
    body.set("model", Json(model));
    Json messages = Json::array();
    Json system = Json::object();
    system.set("role", Json("system"));
    system.set("content", Json(SYSTEM_PROMPT));
    Json user = Json::object();
    user.set("role", Json("user"));
    user.set("content", Json("Provide a concrete answer to the question in the "
                             "form of a battle summary in a single line, being "
                             "extremely dramatic: '" + question + "'"));
    messages.push(std::move(system));
    messages.push(std::move(user));
    body.set("messages", std::move(messages));
    body.set("temperature", Json(0.9));
    body.set("max_tokens", Json(MAX_TOKENS));
    Json reasoning = Json::object();
    reasoning.set("enabled", Json(false));
    reasoning.set("exclude", Json(true));
    body.set("reasoning", std::move(reasoning));

    HttpResponse resp = http_post(OPENROUTER_URL, build_headers(), body.dump(),
                                  cfg::LLM_TIMEOUT);

    Json payload;
    if (resp.ok()) {
        try {
            payload = Json::parse(resp.body);
        } catch (const JsonError&) {
            log_warning("OpenRouter returned non-JSON for model '" + model +
                        "' (HTTP " + std::to_string(resp.status) + "): " +
                        resp.body.substr(0, 500));
            return {};
        }
    } else {
        // Non-HTTP failure (curl error / timeout).
        log_warning("OpenRouter request failed for model '" + model + "': " +
                    resp.error);
        return {};
    }
    if (!payload.is_object()) {
        log_warning("Unexpected OpenRouter payload for model '" + model + "'");
        return {};
    }

    // OpenRouter reports model/rate-limit problems as an `error` object, which
    // previously surfaced only as a KeyError on 'choices' with no explanation.
    const Json* error = payload.find("error");
    if (error || resp.status != 200) {
        std::string detail;
        if (error && error->is_object())
            detail = error->get_string("message");
        else if (error && error->is_string())
            detail = error->as_string();
        if (detail.empty() && !resp.body.empty())
            detail = resp.body.substr(0, 500);
        log_warning("OpenRouter error for model '" + model + "' (HTTP " +
                    std::to_string(resp.status) + "): " + detail);
        std::string slug;
        if (std::optional<std::string> hint = find_slug_hint(detail))
            slug = *hint;
        return {std::string(), slug == model ? std::string() : slug};
    }

    return {extract_text(payload), std::string()};
}

} // namespace

std::string llm_salvage_verdict(const std::string& reasoning,
                                const std::string& finish_reason) {
    return salvage_verdict_impl(reasoning, finish_reason);
}

std::string llm_get_openrouter_response(const std::string& question) {
    if (cfg::LLM_API_KEY.empty()) {
        log_error("LLM_API_KEY not set in environment variables");
        return "Unable to process: '" + question + "' - API key not configured";
    }

    std::vector<std::string> pending = cfg::LLM_MODELS;
    std::vector<std::string> tried;

    while (!pending.empty()) {
        std::string model = pending.front();
        pending.erase(pending.begin());
        bool already_tried = false;
        for (const std::string& t : tried)
            if (t == model)
                already_tried = true;
        if (already_tried)
            continue;
        tried.push_back(model);

        CompletionResult r = complete(model, question);
        if (!r.answer.empty()) {
            log_info("Battle verdict came from model '" + model + "'");
            return r.answer;
        }

        // A retired model usually points at its own replacement, so try that
        // before falling further down the configured chain.
        if (!r.replacement.empty()) {
            bool queued = false;
            for (const std::string& t : tried)
                if (t == r.replacement)
                    queued = true;
            if (cfg::LLM_FOLLOW_MODEL_HINTS && !queued) {
                log_info("OpenRouter suggested '" + r.replacement + "' in "
                         "place of '" + model + "'; trying that next.");
                pending.insert(pending.begin(), r.replacement);
            } else if (!cfg::LLM_FOLLOW_MODEL_HINTS) {
                log_info("OpenRouter suggests '" + r.replacement + "' in place "
                         "of '" + model + "'. Set LLM_FOLLOW_MODEL_HINTS=true to "
                         "follow suggestions like this automatically -- note the "
                         "replacement is usually the paid model.");
            }
        }

        if (!pending.empty())
            log_warning("Model '" + model + "' gave no usable answer, trying "
                        "the next one.");
        else
            log_warning("Model '" + model + "' gave no usable answer.");
    }

    log_error("Every configured model failed for question: '" + question + "'");
    return UNREACHABLE_REPLY;
}

} // namespace bb