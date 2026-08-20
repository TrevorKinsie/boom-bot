#include "tests.h"

#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

#include "bb_config.h"
#include "bb_data.h"
#include "bb_handlers.h"
#include "bb_nltk.h"
#include "bb_replies.h"
#include "bb_util.h"

using namespace bb;

namespace {

bool in_vec(const std::vector<std::string>& v, const std::string& s) {
    return std::find(v.begin(), v.end(), s) != v.end();
}

// All formatted variants a reply could take for a given subject set and
// count-str set (the random pick + optional capitalization make the exact
// variant non-deterministic; membership is the stable invariant).
std::vector<std::string> possible_replies(const std::vector<std::string>& templates,
                                          const std::vector<std::string>& subjects,
                                          int min_count, int max_count) {
    std::vector<std::string> out;
    for (const std::string& tmpl : templates)
        for (const std::string& subject : subjects)
            for (int count = min_count; count <= max_count; ++count)
                out.push_back(format_subject_reply(tmpl, subject, no_word("BOOM", count)));
    return out;
}

std::string tmp_answers_file(const char* label) {
    std::string dir = std::string("/tmp/bb_test_handlers_") + label;
    std::string path = dir + "/question_answers.json";
    std::string cmd = "rm -rf '" + dir + "' && mkdir -p '" + dir + "'";
    if (std::system(cmd.c_str()) != 0)
        throw std::runtime_error("failed to create handler test directory");
    return path;
}

} // namespace

TEST_CASE(handlers_boom_counts) {
    // No args: a random 1..5 boom run.
    std::string reply = handle_boom({});
    CHECK(reply.size() % 4 == 0);
    CHECK(reply.size() >= 4 && reply.size() <= 20);
    CHECK_STR_EQ(reply, booms_for(static_cast<int>(reply.size() / 4)));

    CHECK_STR_EQ(handle_boom({"3"}), booms_for(3));
    CHECK_STR_EQ(handle_boom({"1"}), booms_for(1));
    CHECK_STR_EQ(handle_boom({"5"}), booms_for(5));

    // Above 5: sassy high replies.
    CHECK(in_vec(SASSY_REPLIES_HIGH, handle_boom({"6"})));
    CHECK(in_vec(SASSY_REPLIES_HIGH, handle_boom({"100"})));
    // Below 1: sassy low replies.
    CHECK(in_vec(SASSY_REPLIES_LOW, handle_boom({"0"})));
    CHECK(in_vec(SASSY_REPLIES_LOW, handle_boom({"-3"})));
    // Unparseable: invalid replies (Python int() semantics).
    CHECK(in_vec(SASSY_REPLIES_INVALID, handle_boom({"abc"})));
    CHECK(in_vec(SASSY_REPLIES_INVALID, handle_boom({"3.5"})));
    CHECK(in_vec(SASSY_REPLIES_INVALID, handle_boom({"10x"})));
    CHECK(in_vec(SASSY_REPLIES_INVALID, handle_boom({""})));
}

TEST_CASE(handlers_howmanybooms_empty_question) {
    DataManager dm("", tmp_answers_file("empty"), "");
    std::string reply = process_howmanybooms(dm, "");
    CHECK(in_vec(SASSY_REPLIES_WHAT, reply));
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 0);

    std::string reply2 = process_howmanybooms(dm, "   \t ");
    CHECK(in_vec(SASSY_REPLIES_WHAT, reply2));
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 0);

    // /howmanybooms with no args behaves the same.
    CHECK(in_vec(SASSY_REPLIES_WHAT, handle_howmanybooms(dm, {})));
}

TEST_CASE(handlers_howmanybooms_new_question) {
    DataManager dm("", tmp_answers_file("new"), "");
    const std::string question = "how many booms for cats?";

    std::string reply = process_howmanybooms(dm, question);
    std::vector<std::string> expected =
        possible_replies(QUESTION_REPLY_VARIATIONS, {"many booms cats", "Many booms cats"},
                         1, 5);
    CHECK(in_vec(expected, reply));

    // A new question is stored under its simple-normalized key.
    std::string key = normalize_question_simple(question);
    CHECK(dm.get_answers().has(key));
    const Json& stored = dm.get_answers().at(key);
    CHECK(stored.is_number());
    CHECK(stored.as_int() >= 1 && stored.as_int() <= 5);

    // Asking the same question again matches (Jaccard 1.0) and keeps the count.
    int64_t stored_count = stored.as_int();
    std::string reply2 = process_howmanybooms(dm, question);
    std::vector<std::string> expected2 =
        possible_replies(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS,
                         {"many booms cats", "Many booms cats"},
                         static_cast<int>(stored_count), static_cast<int>(stored_count));
    CHECK(in_vec(expected2, reply2));
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 1);
    CHECK_INT_EQ(dm.get_answers().at(key).as_int(), stored_count);
}

TEST_CASE(handlers_howmanybooms_similar_question_matches) {
    DataManager dm("", tmp_answers_file("similar"), "");
    // Seed with a stored question.
    std::string stored_q = "how many booms would lions get?";
    std::string key = normalize_question_simple(stored_q);
    dm.update_answer(key, Json(3));
    dm.save_answers();

    // A similar wording passes the 0.7 Jaccard threshold.
    std::string reply = process_howmanybooms(dm, "how many booms do lions get?");
    // "do" stops the subject phrase (like "do cats deserve?" -> "many booms").
    std::vector<std::string> expected =
        possible_replies(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS,
                         {"many booms", "Many booms"}, 3, 3);
    CHECK(in_vec(expected, reply));
    // No new answer stored.
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 1);
}

TEST_CASE(handlers_howmanybooms_generic_subject) {
    DataManager dm("", tmp_answers_file("generic"), "");
    // Question whose subject extraction comes up empty.
    std::string reply = process_howmanybooms(dm, "???");
    std::vector<std::string> expected =
        possible_replies(QUESTION_REPLY_VARIATIONS, {"that", "it"}, 1, 5);
    CHECK(in_vec(expected, reply));
}

TEST_CASE(handlers_photo_caption) {
    DataManager dm("", tmp_answers_file("photo"), "");
    // No command in the caption: no reply, no storage.
    CHECK_STR_EQ(handle_photo_caption(dm, "just a picture of a cat"), "");
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 0);

    // Case-insensitive command detection, question text after it.
    std::string reply = handle_photo_caption(dm, "cats /HowManyBooms for ninjas");
    std::vector<std::string> expected =
        possible_replies(QUESTION_REPLY_VARIATIONS,
                         {"ninjas", "Ninjas"}, 1, 5);
    CHECK(in_vec(expected, reply));
    CHECK(dm.get_answers().has(normalize_question_simple("for ninjas")));

    // Empty question content: the Python flow answers with a sassy WHAT reply
    // (the empty/whitespace branch), not with a generic-subject answer.
    std::string reply2 = handle_photo_caption(dm, "look at this /howmanybooms");
    CHECK(in_vec(SASSY_REPLIES_WHAT, reply2));
    CHECK_INT_EQ(static_cast<int>(dm.get_answers().size()), 1);
}

TEST_CASE(handlers_whowouldwin) {
    // No input: usage text.
    std::string usage = handle_whowouldwin({});
    CHECK(usage.find("Usage: /whowouldwin") != std::string::npos);
    CHECK(usage.find("lions vs tigers") != std::string::npos);

    // Too few contenders: instruction text.
    std::string none = handle_whowouldwin({"just", "lions"});
    CHECK(none.find("I couldn't identify who's fighting!") != std::string::npos);

    // Valid contenders: LLM path. With no API key configured the LLM layer
    // returns its deterministic fallback, so this stays offline.
    std::string saved_key = cfg::LLM_API_KEY;
    cfg::LLM_API_KEY = "";
    std::string reply = handle_whowouldwin({"lions", "vs", "tigers"});
    CHECK(reply.find("Unable to process:") != std::string::npos);
    CHECK(reply.find("Who would win in a battle between lions vs tigers?") !=
          std::string::npos);
    cfg::LLM_API_KEY = saved_key;
}

TEST_CASE(handlers_frigged_deposit) {
    std::string usage = handle_frigged_deposit({});
    // The Python source contains literal backslash-n sequences; preserved.
    CHECK(usage.find("Who frigged the deposit? Tell me their name!\\n") !=
          std::string::npos);

    std::string saved_key = cfg::LLM_API_KEY;
    cfg::LLM_API_KEY = "";
    std::string reply = handle_frigged_deposit({"Kevin"});
    CHECK(reply.find("Unable to process:") != std::string::npos);
    CHECK(reply.find("Kevin") != std::string::npos);
    cfg::LLM_API_KEY = saved_key;
}
