#include "tests.h"

#include "bb_util.h"

using namespace bb;

TEST_CASE(util_case_folding) {
    CHECK_STR_EQ(to_lower_ascii("HeLLo Wörld"), "hello wörld");
    CHECK_STR_EQ(to_upper_ascii("abc"), "ABC");
    CHECK_STR_EQ(to_lower_ascii(""), "");
}

TEST_CASE(util_trim) {
    CHECK_STR_EQ(trim("  hello \n\t"), "hello");
    CHECK_STR_EQ(ltrim("  hi"), "hi");
    CHECK_STR_EQ(rtrim("hi  "), "hi");
    CHECK_STR_EQ(trim(""), "");
    CHECK_STR_EQ(trim("   "), "");
}

TEST_CASE(util_split_and_join) {
    std::vector<std::string> parts = split("a,b,,c", ",");
    CHECK_INT_EQ(parts.size(), 4);
    CHECK_STR_EQ(parts[0], "a");
    CHECK_STR_EQ(parts[2], "");
    CHECK_STR_EQ(join({"x", "y"}, " + "), "x + y");
    // maxsplit=1 for the straight__ bet key split.
    parts = split("straight__00", "__", 1);
    CHECK_INT_EQ(parts.size(), 2);
    CHECK_STR_EQ(parts[0], "straight");
    CHECK_STR_EQ(parts[1], "00");
    // No separator present: single element.
    parts = split("plain", "__", 1);
    CHECK_INT_EQ(parts.size(), 1);
    CHECK_STR_EQ(parts[0], "plain");
}

TEST_CASE(util_prefix_suffix) {
    CHECK(starts_with("hello", "he"));
    CHECK(!starts_with("hello", "lo"));
    CHECK(ends_with("hello", "lo"));
    CHECK(starts_with_ci("FINAL answer: x", "final"));
    CHECK(contains_ci("The Wheel landed on 7.", "WHEEL"));
}

TEST_CASE(util_alpha_and_numbers) {
    CHECK(is_alpha("hello"));
    CHECK(!is_alpha("hello1"));
    CHECK(!is_alpha(""));
    CHECK(is_ascii_digits("123"));
    CHECK(!is_ascii_digits("12a"));
    CHECK(parse_int("42").value() == 42);
    CHECK(parse_int("-7").value() == -7);
    CHECK(!parse_int("x").has_value());
    CHECK(!parse_int("").has_value());
    CHECK(parse_double("3.5").value() == 3.5);
    CHECK(!parse_double("3.5x").has_value());
}

TEST_CASE(util_strip_punctuation) {
    // string.punctuation removal, as in normalize_question_nltk.
    CHECK_STR_EQ(strip_punctuation("Hello, world!"), "Hello world");
    CHECK_STR_EQ(strip_punctuation("how many booms does my cat deserve?"),
                 "how many booms does my cat deserve");
    CHECK_STR_EQ(strip_punctuation(""), "");
}

TEST_CASE(util_markdown_escape) {
    CHECK_STR_EQ(markdown_escape_v2("a.b!c-d"), "a\\.b\\!c\\-d");
    CHECK_STR_EQ(markdown_escape_v2("plain text"), "plain text");
    CHECK_STR_EQ(markdown_escape_v2("(paren) [bracket]"), "\\(paren\\) \\[bracket\\]");
}

TEST_CASE(util_no_word) {
    CHECK_STR_EQ(no_word("BOOM", 1), "BOOM");
    CHECK_STR_EQ(no_word("BOOM", 2), "BOOMS");
    CHECK_STR_EQ(no_word("BOOM", 5), "BOOMS");
}

TEST_CASE(util_slug_hint) {
    auto hint = find_slug_hint(
        "This model is unavailable for free. The paid version is available now - "
        "use this slug instead: deepseek/deepseek-chat-v3-0324");
    CHECK(hint.has_value());
    CHECK_STR_EQ(*hint, "deepseek/deepseek-chat-v3-0324");
    // Trailing punctuation is stripped.
    hint = find_slug_hint("use this slug instead: model/name.");
    CHECK(hint.has_value());
    CHECK_STR_EQ(*hint, "model/name");
    // No marker: no hint.
    hint = find_slug_hint("No endpoints found for openrouter/free");
    CHECK(!hint.has_value());
}

TEST_CASE(util_verdict_prefix) {
    CHECK_STR_EQ(strip_verdict_prefix("Verdict: The lion wins"), "The lion wins");
    CHECK_STR_EQ(strip_verdict_prefix("**Verdict: The lion wins**"), "**Verdict: The lion wins**");
    CHECK_STR_EQ(strip_verdict_prefix("Final answer: Lions, by a mile"), "Lions, by a mile");
    CHECK_STR_EQ(strip_verdict_prefix("Final Answer - tigers"), "tigers");
    CHECK_STR_EQ(strip_verdict_prefix("ANSWER - tigers"), "tigers");
    CHECK_STR_EQ(strip_verdict_prefix("Response: x"), "x");
    CHECK_STR_EQ(strip_verdict_prefix("Output: x"), "x");
    CHECK_STR_EQ(strip_verdict_prefix("The lions win"), "The lions win");
}

TEST_CASE(util_last_sentence) {
    CHECK_STR_EQ(last_sentence("First sentence. Second one!"), "Second one!");
    CHECK_STR_EQ(last_sentence("Just one sentence here."), "Just one sentence here.");
    CHECK_STR_EQ(last_sentence("No terminators at all"), "");
    CHECK_STR_EQ(last_sentence("a? b."), "b.");
    CHECK_STR_EQ(last_sentence("Quoted.\" More."), "More.");
}

TEST_CASE(util_verdict_salvage_flow) {
    // Mirrors the llm.py salvage pipeline end to end.
    std::string reasoning = "The user wants a dramatic verdict.\n"
                            "**Final answer: The tigers win in 3 rounds.**";
    std::string line = reasoning;
    std::vector<std::string> lines;
    for (const std::string& l : split(line, "\n")) {
        std::string t = trim(l);
        if (!t.empty())
            lines.push_back(t);
    }
    CHECK_INT_EQ(lines.size(), 2);
    std::string candidate = lines.back();
    candidate = trim(candidate);
    // strip("*") both sides then quotes, as Python does.
    while (!candidate.empty() && candidate.front() == '*')
        candidate.erase(0, 1);
    while (!candidate.empty() && candidate.back() == '*')
        candidate.pop_back();
    candidate = strip_verdict_prefix(candidate);
    candidate = trim(candidate);
    CHECK_STR_EQ(candidate, "The tigers win in 3 rounds.");
}