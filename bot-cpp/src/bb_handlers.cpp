#include "bb_handlers.h"

#include <algorithm>
#include <cstdint>
#include <random>
#include <set>
#include <string>
#include <vector>

#include "bb_llm.h"
#include "bb_log.h"
#include "bb_nltk.h"
#include "bb_replies.h"
#include "bb_util.h"

using bb::log::log_info;
using bb::log::log_warning;

namespace bb {

namespace {

const std::vector<std::string>& replies_high() { return SASSY_REPLIES_HIGH; }
const std::vector<std::string>& replies_invalid() { return SASSY_REPLIES_INVALID; }
const std::vector<std::string>& replies_low() { return SASSY_REPLIES_LOW; }
const std::vector<std::string>& replies_what() { return SASSY_REPLIES_WHAT; }
const std::vector<std::string>& question_variations() { return QUESTION_REPLY_VARIATIONS; }
const std::vector<std::string>& previous_variations() { return PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS; }

// Python random.randint(a, b) - inclusive on both ends.
int randint(int a, int b) {
    static thread_local std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<int> dist(a, b);
    return dist(rng);
}

const double SIMILARITY_THRESHOLD = 0.7;

// base_handlers._process_howmanybooms subject handling.
struct SubjectInfo {
    std::string subject;
    bool generic = false;
};

SubjectInfo pick_subject(const std::string& question_content) {
    std::string processed = trim(question_content);
    if (starts_with_ci(processed, "for "))
        processed = trim(processed.substr(4));

    std::string subject = extract_subject(processed);
    if (subject.empty() || trim(subject).empty()) {
        return {random_choice(std::vector<std::string>{"that", "it"}), true};
    }
    return {subject, false};
}

bool format_starts_with_subject(const std::string& tmpl) {
    return starts_with(tmpl, "{subject}");
}

} // namespace

std::string handle_boom(const std::vector<std::string>& args) {
    int boom_count = randint(1, 5);
    if (!args.empty()) {
        std::optional<int64_t> parsed = parse_int(args[0]);
        if (!parsed) {
            return random_choice(replies_invalid());
        }
        int64_t requested = *parsed;
        if (requested >= 1 && requested <= 5) {
            boom_count = static_cast<int>(requested);
        } else if (requested > 5) {
            return random_choice(replies_high());
        } else { // requested < 1
            return random_choice(replies_low());
        }
    }
    return booms_for(boom_count);
}

std::string process_howmanybooms(DataManager& dm, const std::string& question_content) {
    const Json& question_answers = dm.get_answers();
    std::set<std::string> incoming_words = normalize_question_nltk(question_content);
    log_info("Normalized incoming question '" + question_content + "' to words: " +
             join(std::vector<std::string>(incoming_words.begin(), incoming_words.end()), " "));

    bool match_found = false;
    std::string matched_question_key;
    double highest_similarity = 0.0;

    if (!incoming_words.empty()) {
        for (const auto& [stored_key, stored_value] : question_answers.as_object()) {
            std::set<std::string> stored_words = normalize_question_nltk(stored_key);
            if (stored_words.empty())
                continue;
            double similarity = jaccard_similarity(incoming_words, stored_words);
            if (similarity >= SIMILARITY_THRESHOLD && similarity > highest_similarity) {
                highest_similarity = similarity;
                matched_question_key = stored_key;
                match_found = true;
            }
        }
    } else if (trim(question_content).empty()) {
        log_warning("Question content was empty or whitespace.");
        return random_choice(replies_what());
    }

    SubjectInfo subject = pick_subject(question_content);
    std::string reply_text;

    if (match_found && !matched_question_key.empty()) {
        int64_t count = 0;
        const Json& stored = question_answers.at(matched_question_key);
        if (stored.is_number())
            count = stored.as_int();
        std::string count_str = no_word("BOOM", count);
        const std::string& tmpl = random_choice(previous_variations());

        std::string subject_display = subject.subject;
        if (format_starts_with_subject(tmpl) && !subject.generic)
            subject_display = capitalize(subject.subject);

        reply_text = format_subject_reply(tmpl, subject_display, count_str);
        log_info("Found similar question '" + matched_question_key + "' (Similarity: " +
                 std::to_string(highest_similarity) + ") for '" + question_content +
                 "'. Answer: " + std::to_string(count) + " booms");
    } else {
        std::string storage_key = normalize_question_simple(question_content);
        if (storage_key.empty()) {
            log_warning("Original question '" + question_content +
                        "' also resulted in empty simple normalized key.");
            return random_choice(replies_what());
        }

        if (!incoming_words.empty())
            log_info("No similar question found for '" + question_content +
                     "'. Treating as new question with key '" + storage_key + "'.");
        else
            log_info("No significant words after NLTK normalization for '" +
                     question_content + "', but treating as new question with key '" +
                     storage_key + "'.");

        int question_boom_count = randint(1, 5);
        std::string count_str = no_word("BOOM", question_boom_count);
        const std::string& tmpl = random_choice(question_variations());

        std::string subject_display = subject.subject;
        if (format_starts_with_subject(tmpl) && !subject.generic)
            subject_display = capitalize(subject.subject);

        reply_text = format_subject_reply(tmpl, subject_display, count_str);
        dm.update_answer(storage_key, Json(question_boom_count));
        dm.save_answers();
    }

    return reply_text;
}

std::string handle_howmanybooms(DataManager& dm, const std::vector<std::string>& args) {
    if (!args.empty()) {
        std::string question_content = join(args, " ");
        log_info("Processing question from text args: '" + question_content + "'");
        return process_howmanybooms(dm, question_content);
    }
    return random_choice(replies_what());
}

std::string handle_photo_caption(DataManager& dm, const std::string& caption) {
    std::string lower = to_lower_ascii(caption);
    const std::string command_name = "/howmanybooms";
    size_t command_pos = lower.find(command_name);
    if (command_pos == std::string::npos)
        return "";
    std::string question_content = trim(caption.substr(command_pos + command_name.size()));
    log_info("Processing question from photo caption: '" + question_content + "'");
    return process_howmanybooms(dm, question_content);
}

std::string handle_whowouldwin(const std::vector<std::string>& args) {
    std::string input_text = trim(join(args, " "));
    if (input_text.empty()) {
        return "Usage: /whowouldwin [contenders]\n"
               "Examples:\n"
               "- /whowouldwin lions vs tigers\n"
               "- /whowouldwin between pirates and ninjas\n"
               "- /whowouldwin cats or dogs";
    }

    log_info("Processing whowouldwin request: '" + input_text + "'");
    std::vector<std::string> contenders = extract_contenders(input_text);

    if (contenders.size() < 2) {
        return "I couldn't identify who's fighting! Please specify two or more contenders.\n"
               "Examples:\n"
               "- /whowouldwin lions vs tigers\n"
               "- /whowouldwin between pirates and ninjas\n"
               "- /whowouldwin cats or dogs";
    }

    std::string battle_question =
        "Who would win in a battle between " + join(contenders, " vs ") + "?";
    log_info("Constructed battle question: '" + battle_question + "'");

    std::string response = llm_get_openrouter_response(battle_question);
    log_info("LLM response for battle: " + response);
    return response;
}

std::string handle_frigged_deposit(const std::vector<std::string>& args) {
    std::string name_provided = trim(join(args, " "));
    if (name_provided.empty()) {
        // The Python source spell-checks this usage message with literal
        // backslash-n sequences; preserved verbatim.
        return "Who frigged the deposit? Tell me their name!\\n"
               "Usage: /friggedthedeposit [name]\\n"
               "Example: /friggedthedeposit Kevin";
    }

    log_info("Processing /friggedthedeposit request for: '" + name_provided + "'");

    std::string llm_question =
        "Generate a short, funny, hip, modern, or comically minor reason why '" +
        name_provided + "' lost the security deposit on a rental property. This is for an "
        "inside joke about 'frigging the deposit'. The answer should be a single, funny, "
        "non-corny sentence, ideally starting with '" + name_provided +
        " frigged the deposit by...'. Make it creative, absurd, and dramatic. "
        "For example: '" + name_provided +
        " frigged the deposit by entering a gun-free zone with a gun.'"
        " or '" + name_provided + " frigged the deposit by swimming in the septic tank.'";

    std::string response = llm_get_openrouter_response(llm_question);
    log_info("LLM response for " + name_provided + " (/friggedthedeposit): " + response);
    return response;
}

} // namespace bb