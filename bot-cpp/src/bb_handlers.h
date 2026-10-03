/*
 * bb_handlers.h - ported chat handlers (booms, howmanybooms, photo captions,
 * whowouldwin, friggedthedeposit).
 *
 * The handler functions are pure: they take the message text/args and a
 * DataManager, and return the reply to send.  The polling shell in bb_bot.cpp
 * maps Telegram updates onto them.  Casino (craps/roulette/zeus) and chess
 * arrive in later phases.
 */
#ifndef BB_HANDLERS_H
#define BB_HANDLERS_H

#include <string>
#include <vector>

#include "bb_data.h"

namespace bb {

// /boom [N] - booms or a sassy reply; returns the message text.
std::string handle_boom(const std::vector<std::string>& args);

// Core howmanybooms logic (base_handlers._process_howmanybooms).
// Stores new answers via `dm`; returns the reply message text.
std::string process_howmanybooms(DataManager& dm, const std::string& question_content);

// /howmanybooms [question...] - text-based question.
std::string handle_howmanybooms(DataManager& dm, const std::vector<std::string>& args);

// Photo caption containing "/howmanybooms" (case-insensitive).
std::string handle_photo_caption(DataManager& dm, const std::string& caption);

// /whowouldwin [contenders...] - battle question for the LLM.
std::string handle_whowouldwin(const std::vector<std::string>& args);

// /friggedthedeposit [name] - humorous LLM-generated story.
std::string handle_frigged_deposit(const std::vector<std::string>& args);

} // namespace bb

#endif // BB_HANDLERS_H