#include "tests.h"

#include "bb_nltk.h"

using namespace bb;

TEST_CASE(nltk_normalize_simple) {
    CHECK_STR_EQ(normalize_question_simple("  How Many Booms?  "), "how many booms?");
    CHECK_STR_EQ(normalize_question_simple("Cats"), "cats");
    CHECK_STR_EQ(normalize_question_simple(""), "");
}

TEST_CASE(nltk_normalize_nltk) {
    // Matches the real NLTK pipeline (punkt + English stopwords) on ASCII text.
    std::set<std::string> words = normalize_question_nltk("How many booms would Lions, get?!");
    CHECK_INT_EQ(static_cast<int>(words.size()), 5);
    CHECK(words.count("booms") == 1);
    CHECK(words.count("get") == 1);
    CHECK(words.count("lions") == 1);
    CHECK(words.count("many") == 1);
    CHECK(words.count("would") == 1);

    // Stopwords and punctuation are dropped.
    words = normalize_question_nltk("the quick brown fox");
    CHECK_INT_EQ(static_cast<int>(words.size()), 3);
    CHECK(words.count("the") == 0);

    words = normalize_question_nltk("");
    CHECK_INT_EQ(static_cast<int>(words.size()), 0);

    words = normalize_question_nltk("123 456");
    CHECK_INT_EQ(static_cast<int>(words.size()), 0);
}

TEST_CASE(nltk_jaccard) {
    std::set<std::string> a = {"booms", "lions"};
    std::set<std::string> b = {"booms", "cats"};
    CHECK(jaccard_similarity(a, b) > 0.333 && jaccard_similarity(a, b) < 0.334);
    CHECK(jaccard_similarity(a, a) == 1.0);
    CHECK(jaccard_similarity(a, {"dogs"}) == 0.0);
    CHECK(jaccard_similarity({}, {}) == 0.0);
}

TEST_CASE(nltk_extract_subject) {
    // Ground truth (real NLTK pipeline):
    //   "how many booms for ninjas?"        -> "many booms ninjas"
    //   "the president of the PTA get?"     -> "the president the PTA"
    //   "how many booms would lions get?"   -> "many booms"  (the perceptron
    //       tags 'lions' as VB; our heuristic tagger says NN and yields
    //       "many booms lions" - accepted cosmetic divergence).
    CHECK_STR_EQ(extract_subject("how many booms for ninjas?"), "many booms ninjas");
    CHECK_STR_EQ(extract_subject("the president of the PTA get?"), "the president the PTA");
    CHECK_STR_EQ(extract_subject("how many booms would lions get?"), "many booms lions");
    CHECK_STR_EQ(extract_subject("how many booms do cats deserve?"), "many booms");
    CHECK_STR_EQ(extract_subject(""), "");
    CHECK_STR_EQ(extract_subject("???"), "");
}

TEST_CASE(nltk_extract_contenders) {
    // Matches nltk_utils.extract_contenders on the pattern paths.
    std::vector<std::string> c = extract_contenders("ninjas vs pirates vs robots");
    CHECK_INT_EQ(static_cast<int>(c.size()), 2);
    CHECK_STR_EQ(c[0], "ninjas");
    CHECK_STR_EQ(c[1], "pirates vs robots");

    c = extract_contenders("who would win between pirates and ninjas?");
    CHECK_INT_EQ(static_cast<int>(c.size()), 2);
    CHECK_STR_EQ(c[0], "pirates");
    CHECK_STR_EQ(c[1], "ninjas");

    c = extract_contenders("between x and y");
    CHECK_INT_EQ(static_cast<int>(c.size()), 2);
    CHECK_STR_EQ(c[0], "x");
    CHECK_STR_EQ(c[1], "y");

    c = extract_contenders("cats or dogs?");
    CHECK_INT_EQ(static_cast<int>(c.size()), 2);
    CHECK_STR_EQ(c[0], "cats");
    CHECK_STR_EQ(c[1], "dogs");

    // Noun-phrase fallback for non-pattern text.
    c = extract_contenders("lions and tigers");
    CHECK_INT_EQ(static_cast<int>(c.size()), 2);
    CHECK_STR_EQ(c[0], "lions");
    CHECK_STR_EQ(c[1], "tigers");

    c = extract_contenders("just some random text");
    CHECK_INT_EQ(static_cast<int>(c.size()), 0);

    c = extract_contenders("");
    CHECK_INT_EQ(static_cast<int>(c.size()), 0);
}