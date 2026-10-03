#include "tests.h"

#include "bb_regex.h"

using namespace bb;

namespace {

struct Case {
    std::string pat;
    std::string txt;
    bool icase;
    std::string full;
    std::string g1;
    std::string g2;
};

void check_case(const Case& c) {
    RegexMatch m = regex_search(c.pat, c.txt, c.icase);
    bool want_found = c.full == "~" || !c.full.empty();
    CHECK_INT_EQ(static_cast<int>(m.found), static_cast<int>(want_found));
    if (!want_found)
        return;
    CHECK_STR_EQ(m.groups[0], c.full == "~" ? std::string() : c.full);
    if (m.groups.size() > 1)
        CHECK_STR_EQ(m.groups[1], c.g1);
    if (m.groups.size() > 2)
        CHECK_STR_EQ(m.groups[2], c.g2);
}

} // namespace

TEST_CASE(regex_beast_vs_pattern) {
    // Ported from boombot: beast_handlers.py EXTRACT_VS_PATTERN.
    const char* pat = R"((.*?)\s+(?:vs\.?|versus)\s+(.*?)(?:\?|$|\.))";
    check_case({pat, "lions vs tigers", false, "lions vs tigers", "lions", "tigers"});
    check_case({pat, "lion vs. tiger?", false, "lion vs. tiger?", "lion", "tiger"});
    check_case({pat, "ninjas vs pirates vs robots", false, "ninjas vs pirates vs robots",
                "ninjas", "pirates vs robots"});
    check_case({pat, "ninjas versus pirates", false, "ninjas versus pirates", "ninjas", "pirates"});
    check_case({pat, "just some text", false, "", "", ""});
}

TEST_CASE(regex_between_and_or_patterns) {
    check_case({R"(between\s+(.*?)\s+and\s+(.*?)(?:\?|$|\.))",
                "between pirates and ninjas", false,
                "between pirates and ninjas", "pirates", "ninjas"});
    check_case({R"(between x and y and z)", "between x and y and z", false,
                "between x and y and z", "x", "y and z"});
    const char* or_pat = R"((.*?)\s+or\s+(.*?)(?:\?|$|\.))";
    check_case({or_pat, "cats or dogs", false, "cats or dogs", "cats", "dogs"});
    check_case({or_pat, "cats or dogs?", false, "cats or dogs?", "cats", "dogs"});
}

TEST_CASE(regex_slug_hint_pattern) {
    // Ported from boombot: llm.py SLUG_HINT_PATTERN.
    const char* pat = R"(use this slug instead:?\s*([\w./:-]+))";
    check_case({pat, "use this slug instead: deepseek/deepseek-chat-v3-0324", false,
                "use this slug instead: deepseek/deepseek-chat-v3-0324",
                "deepseek/deepseek-chat-v3-0324", ""});
    check_case({pat, "use this slug instead: foo_bar-v2.1", false,
                "use this slug instead: foo_bar-v2.1", "foo_bar-v2.1", ""});
    check_case({pat, "no slug here", false, "", "", ""});
}

TEST_CASE(regex_verdict_prefix_pattern) {
    // Ported from boombot: llm.py VERDICT_PREFIX_PATTERN (re.IGNORECASE).
    const char* pat = R"(^(?:final\s+answer|final|answer|verdict|response|output)\s*[:\-—]\s*)";
    check_case({pat, "Final Answer: the cats win", true, "Final Answer: ", "", ""});
    check_case({pat, "final answer - cats", true, "final answer - ", "", ""});
    check_case({pat, "VERDICT: cats win", true, "VERDICT: ", "", ""});
    check_case({pat, "response — cats win", true, "response — ", "", ""});
    check_case({pat, "just some text", false, "", "", ""});
    check_case({pat, "final answer - cats", false, "final answer - ", "", ""});
}

TEST_CASE(regex_last_sentence_pattern) {
    // Ported from boombot: llm.py LAST_SENTENCE_PATTERN.
    const char* pat = R"([^.!?]*[.!?]+["'”]?)";
    check_case({pat, "First sentence. Second one!", false, "First sentence.", "", ""});
    check_case({pat, "Why not?", false, "Why not?", "", ""});
    check_case({pat, std::string("He said \"hi\" then left."), false,
                std::string("He said \"hi\" then left."), "", ""});
}

TEST_CASE(regex_quantifiers_and_groups) {
    check_case({R"(a*b)", "aaab", false, "aaab", "", ""});
    check_case({R"(a*?)", "aaab", false, "~", "", ""});
    check_case({R"((cat|dog)+)", "catdogcat", false, "catdogcat", "cat", ""});
    check_case({R"(colou?r)", "color", false, "color", "", ""});
    check_case({R"(colou?r)", "colour", false, "colour", "", ""});
    check_case({R"(^start)", "start of line", false, "start", "", ""});
    check_case({R"(^start)", "not at start", false, "", "", ""});
    check_case({R"(end$)", "the end", false, "end", "", ""});
}

TEST_CASE(regex_classes_and_anchors) {
    check_case({R"([abc]+)", "zz cab foo", false, "cab", "", ""});
    check_case({R"([^a-z]+)", "abc123XYZ", false, "123XYZ", "", ""});
    check_case({R"(\d+)", "there are 42 things", false, "42", "", ""});
    check_case({R"([\w.-]+@[\w.-]+)", "mail me at a.b-c@x.y_z.io now", false,
                "a.b-c@x.y_z.io", "", ""});
    check_case({R"(\.|^$)", "a.b", false, ".", "", ""});
}

TEST_CASE(regex_icase) {
    check_case({R"(hello)", "Say HELLO there", true, "HELLO", "", ""});
    check_case({R"(hello)", "Say HELLO there", false, "", "", ""});
}