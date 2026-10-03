/*
 * bb_util.h - dependency-free string and text helpers.
 *
 * Hand-rolled equivalents of the Python stdlib/regex behaviors the bot
 * relies on: case folding, splitting, punctuation stripping, MarkdownV2
 * escaping, and the three hand-rolled "regexes" from boombot/utils/llm.py
 * and boombot/utils/nltk_utils.py.
 */
#ifndef BB_UTIL_H
#define BB_UTIL_H

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace bb {

std::string to_lower_ascii(const std::string& s);
std::string to_upper_ascii(const std::string& s);

// Python str.capitalize(): first character to upper, rest untouched.
std::string capitalize(const std::string& s);

// Python str.strip() whitespace set.
std::string trim(const std::string& s);
std::string ltrim(const std::string& s);
std::string rtrim(const std::string& s);

// Python str.split(sep). Splits on every occurrence; empty fields preserved.
// With maxsplit < 0 no limit; otherwise at most maxsplit splits are made.
std::vector<std::string> split(const std::string& s, const std::string& sep, int maxsplit = -1);

std::string join(const std::vector<std::string>& parts, const std::string& sep);

bool starts_with(const std::string& s, const std::string& prefix);
bool ends_with(const std::string& s, const std::string& suffix);
bool starts_with_ci(const std::string& s, const std::string& prefix);
bool contains_ci(const std::string& haystack, const std::string& needle);

// Python str.isalpha() (ASCII approximation) and isdigit.
bool is_alpha(const std::string& s);
bool is_ascii_digits(const std::string& s);

std::optional<int64_t> parse_int(const std::string& s);
std::optional<double> parse_double(const std::string& s);

void replace_all(std::string& s, const std::string& from, const std::string& to);

// Python str.translate removing string.punctuation.
std::string strip_punctuation(const std::string& s);

// Telegram MarkdownV2 escaping (escape_chars = _*[]()~`>#+-=|{}.!).
std::string markdown_escape_v2(const std::string& text);

// Pluralize a single uppercase word the way inflect's p.no("BOOM", n) does.
std::string no_word(const std::string& singular, int64_t count);

// --- Hand-rolled regex equivalents from llm.py ---
// SLUG_HINT_PATTERN = r"use this slug instead:?\s*([\w./:-]+)"
// Returns the suggested replacement slug, or nullopt.
std::optional<std::string> find_slug_hint(const std::string& detail);

// VERDICT_PREFIX_PATTERN = r"^(?:final\s+answer|final|answer|verdict|response|output)\s*[:\-—]\s*"
// Strips the leading label from a verdict line, if present.
std::string strip_verdict_prefix(const std::string& line);

// LAST_SENTENCE_PATTERN = r"[^.!?]*[.!?]+[\"'”]?"
// Returns the last complete sentence, or empty when none exists.
std::string last_sentence(const std::string& text);

} // namespace bb

#endif // BB_UTIL_H
