#include "bb_util.h"

#include <algorithm>
#include <cstring>

namespace bb {

std::string to_lower_ascii(const std::string& s) {
    std::string out = s;
    for (char& c : out)
        if (c >= 'A' && c <= 'Z')
            c = static_cast<char>(c - 'A' + 'a');
    return out;
}

std::string to_upper_ascii(const std::string& s) {
    std::string out = s;
    for (char& c : out)
        if (c >= 'a' && c <= 'z')
            c = static_cast<char>(c - 'a' + 'A');
    return out;
}

std::string capitalize(const std::string& s) {
    if (s.empty())
        return s;
    std::string out = s;
    char& c = out[0];
    if (c >= 'a' && c <= 'z')
        c = static_cast<char>(c - 'a' + 'A');
    return out;
}

namespace {
inline bool is_ws(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}
} // namespace

std::string ltrim(const std::string& s) {
    size_t i = 0;
    while (i < s.size() && is_ws(s[i]))
        ++i;
    return s.substr(i);
}

std::string rtrim(const std::string& s) {
    size_t i = s.size();
    while (i > 0 && is_ws(s[i - 1]))
        --i;
    return s.substr(0, i);
}

std::string trim(const std::string& s) {
    return rtrim(ltrim(s));
}

std::vector<std::string> split(const std::string& s, const std::string& sep, int maxsplit) {
    std::vector<std::string> parts;
    if (sep.empty()) {
        for (char c : s)
            parts.push_back(std::string(1, c));
        return parts;
    }
    size_t start = 0;
    int made = 0;
    while (true) {
        if (maxsplit >= 0 && made >= maxsplit) {
            parts.push_back(s.substr(start));
            break;
        }
        size_t pos = s.find(sep, start);
        if (pos == std::string::npos) {
            parts.push_back(s.substr(start));
            break;
        }
        parts.push_back(s.substr(start, pos - start));
        start = pos + sep.size();
        ++made;
    }
    return parts;
}

std::string join(const std::vector<std::string>& parts, const std::string& sep) {
    std::string out;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i)
            out += sep;
        out += parts[i];
    }
    return out;
}

bool starts_with(const std::string& s, const std::string& prefix) {
    return s.size() >= prefix.size() && std::memcmp(s.data(), prefix.data(), prefix.size()) == 0;
}

bool ends_with(const std::string& s, const std::string& suffix) {
    return s.size() >= suffix.size() &&
           std::memcmp(s.data() + s.size() - suffix.size(), suffix.data(), suffix.size()) == 0;
}

bool starts_with_ci(const std::string& s, const std::string& prefix) {
    std::string ls = to_lower_ascii(s);
    std::string lp = to_lower_ascii(prefix);
    return starts_with(ls, lp);
}

bool contains_ci(const std::string& haystack, const std::string& needle) {
    return to_lower_ascii(haystack).find(to_lower_ascii(needle)) != std::string::npos;
}

bool is_alpha(const std::string& s) {
    if (s.empty())
        return false;
    for (char c : s) {
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')))
            return false;
    }
    return true;
}

bool is_ascii_digits(const std::string& s) {
    if (s.empty())
        return false;
    for (char c : s) {
        if (c < '0' || c > '9')
            return false;
    }
    return true;
}

std::optional<int64_t> parse_int(const std::string& s) {
    if (s.empty())
        return std::nullopt;
    size_t i = 0;
    bool neg = false;
    if (s[i] == '-' || s[i] == '+') {
        neg = s[i] == '-';
        ++i;
    }
    if (i >= s.size())
        return std::nullopt;
    int64_t v = 0;
    for (; i < s.size(); ++i) {
        if (s[i] < '0' || s[i] > '9')
            return std::nullopt;
        v = v * 10 + (s[i] - '0');
    }
    return neg ? -v : v;
}

std::optional<double> parse_double(const std::string& s) {
    if (s.empty())
        return std::nullopt;
    char* endptr = nullptr;
    double v = std::strtod(s.c_str(), &endptr);
    if (endptr == s.c_str() || *endptr != '\0')
        return std::nullopt;
    return v;
}

void replace_all(std::string& s, const std::string& from, const std::string& to) {
    if (from.empty())
        return;
    size_t pos = 0;
    while ((pos = s.find(from, pos)) != std::string::npos) {
        s.replace(pos, from.size(), to);
        pos += to.size();
    }
}

std::string strip_punctuation(const std::string& s) {
    static const char* punct = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        if (std::strchr(punct, c) == nullptr)
            out.push_back(c);
    }
    return out;
}

std::string markdown_escape_v2(const std::string& text) {
    static const char* escape_chars = "_*[]()~`>#+-=|{}.!";
    std::string out;
    out.reserve(text.size());
    for (char c : text) {
        if (std::strchr(escape_chars, c) != nullptr)
            out.push_back('\\');
        out.push_back(c);
    }
    return out;
}

std::string no_word(const std::string& singular, int64_t count) {
    return count == 1 ? singular : singular + "S";
}

std::optional<std::string> find_slug_hint(const std::string& detail) {
    std::string lower = to_lower_ascii(detail);
    static const char* marker = "use this slug instead";
    size_t pos = lower.find(marker);
    if (pos == std::string::npos)
        return std::nullopt;
    size_t i = pos + std::strlen(marker);
    if (i < detail.size() && detail[i] == ':')
        ++i;
    while (i < detail.size() && (detail[i] == ' ' || detail[i] == '\t'))
        ++i;
    size_t start = i;
    while (i < detail.size()) {
        char c = detail[i];
        bool ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                  (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '/' ||
                  c == ':' || c == '-';
        if (!ok)
            break;
        ++i;
    }
    if (i == start)
        return std::nullopt;
    std::string slug = detail.substr(start, i - start);
    while (!slug.empty() && (slug.back() == '.' || slug.back() == ','))
        slug.pop_back();
    if (slug.empty())
        return std::nullopt;
    return slug;
}

namespace {
// Is the 3-byte UTF-8 sequence at position i the em dash U+2014?
inline bool em_dash_at(const std::string& s, size_t i) {
    return i + 2 < s.size() && static_cast<unsigned char>(s[i]) == 0xE2 &&
           static_cast<unsigned char>(s[i + 1]) == 0x80 &&
           static_cast<unsigned char>(s[i + 2]) == 0x94;
}
// Is the 3-byte UTF-8 sequence at position i the right double quote U+201D?
inline bool right_quote_at(const std::string& s, size_t i) {
    return i + 2 < s.size() && static_cast<unsigned char>(s[i]) == 0xE2 &&
           static_cast<unsigned char>(s[i + 1]) == 0x80 &&
           static_cast<unsigned char>(s[i + 2]) == 0x9D;
}
} // namespace

std::string strip_verdict_prefix(const std::string& line) {
    static const char* labels[] = {"final", "answer", "verdict", "response", "output"};
    std::string lower = to_lower_ascii(line);
    size_t i = 0;
    while (i < lower.size() && (lower[i] == ' ' || lower[i] == '\t'))
        ++i;
    bool matched = false;
    size_t content_start = 0;
    for (const char* label : labels) {
        size_t len = std::strlen(label);
        if (lower.compare(i, len, label) != 0)
            continue;
        size_t j = i + len;
        if (std::strcmp(label, "final") == 0) {
            // "final\s+answer" binds as one label when both words are present.
            size_t k = j;
            while (k < lower.size() && (lower[k] == ' ' || lower[k] == '\t'))
                ++k;
            if (lower.compare(k, 6, "answer") == 0)
                j = k + 6;
        }
        size_t k = j;
        while (k < lower.size() && (lower[k] == ' ' || lower[k] == '\t'))
            ++k;
        char sep = k < lower.size() ? lower[k] : '\0';
        if (sep == ':' || sep == '-') {
            matched = true;
            content_start = k + 1;
            break;
        }
        if (em_dash_at(lower, k)) {
            matched = true;
            content_start = k + 3;
            break;
        }
    }
    if (!matched)
        return line;
    return trim(line.substr(content_start));
}

std::string last_sentence(const std::string& text) {
    // LAST_SENTENCE_PATTERN = [^.!?]*[.!?]+[\"'”]?  (findall -> last match)
    std::vector<std::string> sentences;
    size_t i = 0;
    while (i < text.size()) {
        size_t start = i;
        while (i < text.size() && text[i] != '.' && text[i] != '!' && text[i] != '?')
            ++i;
        size_t after_scan = i;
        while (i < text.size() && (text[i] == '.' || text[i] == '!' || text[i] == '?'))
            ++i;
        if (i > after_scan) {
            std::string sentence = text.substr(start, i - start);
            if (i < text.size() && (text[i] == '"' || text[i] == '\''))
                sentence.push_back(text[i++]);
            else if (right_quote_at(text, i)) {
                sentence.append(text, i, 3);
                i += 3;
            }
            sentences.push_back(sentence);
        }
    }
    if (sentences.empty())
        return "";
    return trim(sentences.back());
}

} // namespace bb