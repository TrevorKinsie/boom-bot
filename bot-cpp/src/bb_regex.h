/*
 * bb_regex.h - minimal backtracking regex engine (Python `re` subset).
 *
 * Supported syntax: literals, `.`, `\s \S \w \W \d \D`, `[...]`/`[^...]`,
 * escaped metachars, groups `(...)` and `(?:...)`, alternation `|`,
 * quantifiers `* + ?` with lazy variants `*? +? ??`, anchors `^` and `$`.
 * `.` does not match '\n', `$` matches at end (or before a trailing '\n').
 */
#ifndef BB_REGEX_H
#define BB_REGEX_H

#include <cstddef>
#include <string>
#include <vector>

namespace bb {

struct RegexMatch {
    bool found = false;
    size_t start = 0;
    size_t end = 0;
    std::vector<std::string> groups; // groups[0] = whole match, 1..n = captures
};

// Find the first match anywhere in `text` (Python re.search semantics).
RegexMatch regex_search(const std::string& pattern, const std::string& text,
                        bool icase = false);

// Match anchored at the start of `text` (Python re.match semantics).
RegexMatch regex_match(const std::string& pattern, const std::string& text,
                       bool icase = false);

// All non-overlapping full matches, left to right (Python re.findall).
std::vector<std::string> regex_findall(const std::string& pattern, const std::string& text,
                                       bool icase = false);

} // namespace bb

#endif // BB_REGEX_H