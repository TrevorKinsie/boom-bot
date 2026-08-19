#include "tests.h"

#include "bb_replies.h"

using namespace bb;

TEST_CASE(replies_array_sizes) {
    CHECK_INT_EQ(static_cast<int>(SASSY_REPLIES_HIGH.size()), 20);
    CHECK_INT_EQ(static_cast<int>(SASSY_REPLIES_INVALID.size()), 40);
    CHECK_INT_EQ(static_cast<int>(SASSY_REPLIES_LOW.size()), 20);
    CHECK_INT_EQ(static_cast<int>(QUESTION_REPLY_VARIATIONS.size()), 8);
    CHECK_INT_EQ(static_cast<int>(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS.size()), 8);
    CHECK_INT_EQ(static_cast<int>(SASSY_REPLIES_WHAT.size()), 11);
    CHECK_INT_EQ(static_cast<int>(VICTORY_REASONS.size()), 100);
    CHECK_INT_EQ(static_cast<int>(BATTLE_OUTCOMES.size()), 12);
    CHECK_INT_EQ(static_cast<int>(CLOSE_MATCH_OUTCOMES.size()), 16);
}

TEST_CASE(replies_booms_for) {
    CHECK_STR_EQ(booms_for(0), "");
    CHECK_STR_EQ(booms_for(1), "\xF0\x9F\x92\xA5");
    CHECK_STR_EQ(booms_for(3), "\xF0\x9F\x92\xA5\xF0\x9F\x92\xA5\xF0\x9F\x92\xA5");
}

TEST_CASE(replies_random_choice) {
    // Sanity: choices come from the given pool.
    CHECK(random_choice(SASSY_REPLIES_HIGH).size() > 0);
    bool seen_different = false;
    std::string first = random_choice(QUESTION_REPLY_VARIATIONS);
    for (int i = 0; i < 20 && !seen_different; ++i)
        seen_different = random_choice(QUESTION_REPLY_VARIATIONS) != first;
    CHECK(seen_different);
}

TEST_CASE(replies_format_subject) {
    std::string r = format_subject_reply(QUESTION_REPLY_VARIATIONS[0], "cats", "3 \xF0\x9F\x92\xA5");
    CHECK_STR_EQ(r, "I give cats 3 \xF0\x9F\x92\xA5 \xF0\x9F\x92\xA5");
    CHECK_STR_EQ(format_subject_reply("x {missing}", "a", "b"), "x {missing}");
}

TEST_CASE(replies_format_battle) {
    std::string r = format_battle_reply(BATTLE_OUTCOMES[0], "Lions", "Tigers", "superior strength");
    CHECK_STR_EQ(r, "In an epic battle between Lions and Tigers, Lions would emerge victorious due to their superior strength.");
    r = format_battle_reply(CLOSE_MATCH_OUTCOMES[0], "A", "B", "C");
    CHECK_STR_EQ(r, "In a neck-and-neck battle, A would narrowly defeat B, with C being the deciding factor.");
}