/*
 * bb_llm.h - OpenRouter chat-completion client.
 *
 * Faithful port of boombot/utils/llm.py: walks the configured model chain,
 * follows replacement-slug hints when a model is retired, and salvages a
 * one-line verdict from reasoning traces when a model returns no content.
 */
#ifndef BB_LLM_H
#define BB_LLM_H

#include <string>

namespace bb {

// Maximum length of a salvaged verdict line.
inline constexpr size_t MAX_SALVAGED_VERDICT_CHARS = 400;

inline const char* UNREACHABLE_REPLY =
    "The battle remains undecided. (My battle vision is down right now.)";

// Ask the configured OpenRouter model chain and return the first usable
// answer; UNREACHABLE_REPLY if every model fails.  Never throws.
std::string llm_get_openrouter_response(const std::string& question);

// Pull the final call out of a reasoning trace; empty string if none usable.
std::string llm_salvage_verdict(const std::string& reasoning,
                                const std::string& finish_reason);

} // namespace bb

#endif // BB_LLM_H