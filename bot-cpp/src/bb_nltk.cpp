#include "bb_nltk.h"

#include <algorithm>

#include "bb_regex.h"
#include "bb_util.h"

namespace bb {

namespace {

// The real NLTK English stopword list (nltk.corpus.stopwords, 198 words).
const std::set<std::string>& stop_words() {
    static const std::set<std::string> words = {
        "a", "about", "above", "after", "again", "against", "ain", "all", "am",
        "an", "and", "any", "are", "aren", "aren't", "as", "at", "be", "because",
        "been", "before", "being", "below", "between", "both", "but", "by", "can",
        "couldn", "couldn't", "d", "did", "didn", "didn't", "do", "does", "doesn",
        "doesn't", "doing", "don", "don't", "down", "during", "each", "few", "for",
        "from", "further", "had", "hadn", "hadn't", "has", "hasn", "hasn't", "have",
        "haven", "haven't", "having", "he", "he'd", "he'll", "her", "here",
        "hers", "herself", "he's", "him", "himself", "his", "how", "i", "i'd",
        "if", "i'll", "i'm", "in", "into", "is", "isn", "isn't", "it", "it'd",
        "it'll", "it's", "its", "itself", "i've", "just", "ll", "m", "ma", "me",
        "mightn", "mightn't", "more", "most", "mustn", "mustn't", "my", "myself",
        "needn", "needn't", "no", "nor", "not", "now", "o", "of", "off", "on",
        "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
        "own", "re", "s", "same", "shan", "shan't", "she", "she'd", "she'll",
        "she's", "should", "shouldn", "shouldn't", "should've", "so", "some",
        "such", "t", "than", "that", "that'll", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "they'd", "they'll",
        "they're", "they've", "this", "those", "through", "to", "too", "under",
        "until", "up", "ve", "very", "was", "wasn", "wasn't", "we", "we'd",
        "we'll", "we're", "were", "weren", "weren't", "we've", "what", "when",
        "where", "which", "while", "who", "whom", "why", "will", "with", "won",
        "won't", "wouldn", "wouldn't", "y", "you", "you'd", "you'll", "your",
        "you're", "yours", "yourself", "yourselves", "you've",
    };
    return words;
}

bool is_word_char(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}

bool is_ascii_alpha(const std::string& s) {
    return std::all_of(s.begin(), s.end(), [](char c) {
        return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
    });
}

// Approximation of nltk.word_tokenize: maximal runs of word characters.
std::vector<std::string> tokenize(const std::string& text) {
    std::vector<std::string> tokens;
    size_t i = 0;
    while (i < text.size()) {
        if (!is_word_char(text[i])) {
            ++i;
            continue;
        }
        size_t j = i;
        while (j < text.size() && is_word_char(text[j]))
            ++j;
        tokens.push_back(text.substr(i, j - i));
        i = j;
    }
    return tokens;
}

// Heuristic POS tagger approximating NLTK's averaged perceptron tagger for
// the tags the extractors care about (DT, JJ, NN/NNS/NNP, VB, MD).
std::string tag(const std::string& word) {
    static const std::set<std::string> determiners = {
        "a", "an", "the", "this", "that", "these", "those", "my", "your", "our",
        "their", "his", "her", "its", "some", "any", "no", "every", "each",
    };
    static const std::set<std::string> modals = {
        "would", "can", "could", "should", "will", "may", "might", "must",
        "shall",
    };
    static const std::set<std::string> verbs = {
        "is", "are", "was", "were", "be", "been", "am", "do", "does", "did",
        "doing", "get", "gets", "got", "deserve", "deserves", "want", "wants",
        "need", "needs", "have", "has", "had", "having", "win",
    };
    static const std::set<std::string> adjectives = {
        "many", "few", "more", "most", "little", "big", "small", "new", "old",
        "good", "great", "better", "best", "bad", "fast", "slow", "high", "low",
        "red", "blue", "green", "strong", "weak", "smart", "loud", "quiet",
    };
    static const std::set<std::string> wh_words = {
        "how", "what", "when", "where", "which", "who", "whom", "why",
    };
    static const std::set<std::string> adverbs = {
        "just", "very", "really", "also", "still", "already", "not", "only",
        "then", "there", "here",
    };
    static const std::set<std::string> prepositions = {
        "of", "for", "in", "on", "at", "with", "without", "from", "to", "by",
        "about", "over", "under", "into", "through", "after", "before",
        "between", "against", "during", "within", "upon", "via",
    };
    if (determiners.count(word) > 0)
        return "DT";
    if (modals.count(word) > 0)
        return "MD";
    if (verbs.count(word) > 0)
        return "VB";
    if (adjectives.count(word) > 0)
        return "JJ";
    if (wh_words.count(word) > 0)
        return "WRB";
    if (prepositions.count(word) > 0)
        return "IN";
    if (adverbs.count(word) > 0)
        return "RB";
    if (!word.empty() && word[0] >= 'A' && word[0] <= 'Z')
        return "NNP";
    if (!word.empty() && word.back() == 's' && word.size() > 1)
        return "NNS";
    return "NN";
}

std::string strip_trailing_question_marks(std::string s) {
    while (!s.empty() && s.back() == '?')
        s.pop_back();
    return s;
}

} // namespace

std::string normalize_question_simple(const std::string& text) {
    return trim(to_lower_ascii(text));
}

std::set<std::string> normalize_question_nltk(const std::string& text) {
    std::set<std::string> result;
    if (text.empty())
        return result;
    std::string lowered = to_lower_ascii(text);
    for (std::string& tok : tokenize(lowered)) {
        if (!is_ascii_alpha(tok) || stop_words().count(tok) > 0)
            continue;
        result.insert(tok);
    }
    return result;
}

double jaccard_similarity(const std::set<std::string>& a, const std::set<std::string>& b) {
    if (a.empty() && b.empty())
        return 0.0;
    size_t inter = 0;
    for (const std::string& w : a) {
        if (b.count(w) > 0)
            ++inter;
    }
    size_t uni = a.size() + b.size() - inter;
    return uni == 0 ? 0.0 : static_cast<double>(inter) / static_cast<double>(uni);
}

std::string extract_subject(const std::string& text) {
    std::vector<std::string> tokens = tokenize(text);
    std::vector<std::pair<std::string, std::string>> tagged;
    tagged.reserve(tokens.size());
    for (const std::string& w : tokens)
        tagged.emplace_back(w, tag(w));

    std::vector<std::string> subject_words;
    bool in_subject = false;
    // Simple heuristic: find the first sequence of Determiner (DT),
    // Adjective (JJ), Noun (NN/NNS/NNP/NNPS).  (Mirrors nltk_utils.py.)
    for (const auto& [word, t] : tagged) {
        if (t.rfind("DT", 0) == 0 || t.rfind("JJ", 0) == 0 || t.rfind("NN", 0) == 0) {
            subject_words.push_back(word);
            in_subject = true;
        } else if (in_subject && (t.rfind("VB", 0) == 0 ||
                                  word == "is" || word == "are" || word == "does" ||
                                  word == "do" || word == "get" || word == "deserves")) {
            break; // Stop after the main noun phrase, before the verb
        } else if (in_subject && !(t.rfind("DT", 0) == 0 || t.rfind("JJ", 0) == 0 ||
                                   t.rfind("NN", 0) == 0)) {
            if (word == "?" || word == "." || t == ":" || t == ",")
                break;
            // Otherwise, might be part of a complex noun phrase, continue.
        }
    }

    std::string subject = trim(join(subject_words, " "));
    // Remove leading 'how many booms does/do/is/are' etc. if captured.
    static const std::vector<std::string> common_prefixes = {
        "how many booms does ", "how many booms do ", "how many booms is ",
        "how many booms are ", "how many booms ",
    };
    std::string lowered = to_lower_ascii(subject);
    for (const std::string& prefix : common_prefixes) {
        if (lowered.rfind(prefix, 0) == 0) {
            subject = trim(subject.substr(prefix.size()));
            break;
        }
    }

    // Fallback if extraction is empty or very short.
    if (subject.empty())
        return strip_trailing_question_marks(trim(text));
    return subject;
}

std::vector<std::string> extract_contenders(const std::string& text_in) {
    std::string text = trim(to_lower_ascii(text_in));

    const char* vs_pattern = R"((.*?)\s+(?:vs\.?|versus)\s+(.*?)(?:\?|$|\.))";
    const char* between_pattern = R"(between\s+(.*?)\s+and\s+(.*?)(?:\?|$|\.))";
    const char* or_pattern = R"((.*?)\s+or\s+(.*?)(?:\?|$|\.))";

    RegexMatch m = regex_search(vs_pattern, text);
    if (m.found)
        return {trim(m.groups[1]), trim(m.groups[2])};

    m = regex_search(between_pattern, text);
    if (m.found)
        return {trim(m.groups[1]), trim(m.groups[2])};

    m = regex_search(or_pattern, text);
    if (m.found)
        return {trim(m.groups[1]), trim(m.groups[2])};

    // No pattern matched: look for noun sequences.
    {
        std::vector<std::string> contenders;
        std::vector<std::string> current;
        for (const std::string& tok : tokenize(text)) {
            if (tok == "vs" || tok == "versus" || tok == "and" || tok == "or" ||
                tok == "between" || tok == "against") {
                if (!current.empty()) {
                    contenders.push_back(join(current, " "));
                    current.clear();
                }
                continue;
            }
            std::string t = tag(tok);
            if (t.rfind("NN", 0) == 0 || t.rfind("JJ", 0) == 0) {
                current.push_back(tok);
            } else if (!current.empty()) {
                contenders.push_back(join(current, " "));
                current.clear();
            }
        }
        if (!current.empty())
            contenders.push_back(join(current, " "));
        std::vector<std::string> unique;
        std::set<std::string> seen;
        for (const std::string& c : contenders) {
            if (seen.count(c) == 0) {
                seen.insert(c);
                unique.push_back(c);
            }
        }
        if (unique.size() >= 2)
            return unique;
    }

    // Fallback: split by common separators.
    for (const char* sep : {" vs ", " versus ", " and ", " or ", " against "}) {
        std::string sep_str = sep;
        size_t at = text.find(sep_str);
        if (at == std::string::npos)
            continue;
        std::vector<std::string> parts;
        while (at != std::string::npos) {
            std::string piece = trim(text.substr(0, at));
            if (!piece.empty())
                parts.push_back(piece);
            text = text.substr(at + sep_str.size());
            at = text.find(sep_str);
        }
        std::string piece = trim(text);
        if (!piece.empty())
            parts.push_back(piece);
        if (parts.size() >= 2)
            return parts;
    }

    return {};
}

} // namespace bb