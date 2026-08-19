#include "tests.h"

#include <string>

#include "bb_llm.h"

using namespace bb;

TEST_CASE(llm_salvage_verdict_basics) {
    // Truncated traces have no verdict to take.
    CHECK_STR_EQ(llm_salvage_verdict("thinking thinking thinking", "length"), "");
    CHECK_STR_EQ(llm_salvage_verdict("thinking", ""), "");
    CHECK_STR_EQ(llm_salvage_verdict("", "stop"), "");
    CHECK_STR_EQ(llm_salvage_verdict("   \n\t  \n", "stop"), "");
}

TEST_CASE(llm_salvage_verdict_last_line) {
    const std::string reasoning =
        "Let me think about this matchup.\n"
        "Lions have claws and teamwork.\n"
        "**Verdict: Lions win decisively.**";
    // Lines are taken from the end; the last one wins verbatim.
    CHECK_STR_EQ(llm_salvage_verdict(reasoning, "stop"),
                 "Lions win decisively.");
}

TEST_CASE(llm_salvage_verdict_decoration_stripping) {
    // "**Verdict: ...**" - stars, label, quotes all stripped.
    CHECK_STR_EQ(llm_salvage_verdict("**Verdict: Cats win.**", "stop"), "Cats win.");
    CHECK_STR_EQ(llm_salvage_verdict("**Final Answer: 42**", "stop"), "42");
    CHECK_STR_EQ(llm_salvage_verdict("Answer: Tigers.", "end_turn"), "Tigers.");
    CHECK_STR_EQ(llm_salvage_verdict("verdict \xE2\x80\x94 robots", "stop"), "robots");
    CHECK_STR_EQ(llm_salvage_verdict("response: \xE2\x80\x9Cninjas.\xE2\x80\x9D", "stop"),
                 "ninjas.");
}

TEST_CASE(llm_salvage_verdict_not_a_verdict) {
    // No separator means the prefix is not a label, so nothing strips.
    CHECK_STR_EQ(llm_salvage_verdict("verdict is uncertain", "stop"), "verdict is uncertain");
    // Label mid-line is untouched.
    CHECK_STR_EQ(llm_salvage_verdict("I think the verdict: lions.", "stop"),
                 "I think the verdict: lions.");
    // A wall of text without a complete sentence has no verdict.
    std::string wall(500, 'a');
    CHECK_STR_EQ(llm_salvage_verdict(wall, "stop"), "");
}

TEST_CASE(llm_salvage_verdict_long_trace_takes_last_sentence) {
    // The last candidate line is a 400+ wall; keep its last complete sentence
    // (the final findall match, Python re semantics).
    std::string reasoning =
        std::string(480, 'a') + "\n" +
        std::string(480, 'x') + "T. T T T. Winners win.";
    std::string verdict = llm_salvage_verdict(reasoning, "stop");
    CHECK_STR_EQ(verdict, "Winners win.");

    // ...but a wall whose final "sentence" is itself too long has no verdict.
    std::string wall_reasoning = std::string(480, 'x') + " Def. " + std::string(500, 'y') + ".";
    CHECK_STR_EQ(llm_salvage_verdict(wall_reasoning, "stop"), "");
}

TEST_CASE(llm_salvage_verdict_em_dash_prefix) {
    // The Python pattern's separator allows the em dash; keep it faithful.
    CHECK_STR_EQ(llm_salvage_verdict("**Verdict: pirates win.**", "stop"), "pirates win.");
    CHECK_STR_EQ(llm_salvage_verdict("Final answer - hedgehogs.", "stop"), "hedgehogs.");
}