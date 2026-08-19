/*
 * bb_nltk.h - question normalization and subject/contender extraction,
 * ported from boombot/utils/nltk_utils.py.
 *
 * The Python original uses NLTK (stopwords corpus, punkt tokenizer,
 * averaged_perceptron_tagger).  This port embeds the real NLTK English
 * stopword list and approximates punkt/pos_tag with a lightweight
 * tokenizer and heuristic tagger.  See bb_nltk.cpp for details.
 */
#ifndef BB_NLTK_H
#define BB_NLTK_H

#include <set>
#include <string>
#include <vector>

namespace bb {

// Original simple normalization for storage keys (Python str.lower().strip();
// ASCII-only case folding in this port).
std::string normalize_question_simple(const std::string& text);

// NLTK-style normalization: lowercase, drop punctuation, tokenize, keep
// alphabetic tokens that are not English stopwords.
std::set<std::string> normalize_question_nltk(const std::string& text);

// Jaccard similarity between two normalized word sets (0..1).
double jaccard_similarity(const std::set<std::string>& a, const std::set<std::string>& b);

// Extract the likely subject (first noun phrase) from a question.
std::string extract_subject(const std::string& text);

// Extract contenders from "X vs Y", "between X and Y" or "X or Y" text.
std::vector<std::string> extract_contenders(const std::string& text);

} // namespace bb

#endif // BB_NLTK_H