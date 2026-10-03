/*
 * tests.h - minimal self-test harness (mirrors wagering-service-tests).
 */
#ifndef BB_TESTS_H
#define BB_TESTS_H

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace bbtest {

struct Stats {
    int checks = 0;
    int failures = 0;
    int cases = 0;
};


inline Stats& stats_singleton() {
    static Stats stats;
    return stats;
}

#define BB_TEST_STATS() bbtest::stats_singleton()

inline std::vector<std::pair<const char*, void (*)()>>& case_registry() {
    static std::vector<std::pair<const char*, void (*)()>>* cases =
        new std::vector<std::pair<const char*, void (*)()>>();
    return *cases;
}

inline void register_case(const char* name, void (*fn)()) {
    case_registry().emplace_back(name, fn);
}

inline int run_all() {
    Stats& g_stats = stats_singleton();
    for (auto& [name, fn] : case_registry()) {
        int failures_before = g_stats.failures;
        fn();
        bool ok = g_stats.failures == failures_before;
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
        if (ok)
            ++g_stats.cases;
    }
    std::printf("%d checks, %d failures\n", g_stats.checks, g_stats.failures);
    return g_stats.failures == 0 ? 0 : 1;
}

template <typename Ex>
bool throws_impl(void (*fn)()) {
    try {
        fn();
        return false;
    } catch (const Ex&) {
        return true;
    } catch (...) {
        return false;
    }
}

template <typename Ex, typename Fn>
bool throws_fn(Fn fn) {
    try {
        fn();
        return false;
    } catch (const Ex&) {
        return true;
    } catch (...) {
        return false;
    }
}

} // namespace bbtest

#define TEST_CASE(name) \
    static void name(); \
    static bool name##_registered = (bbtest::register_case(#name, &name), true); \
    static void name()

#define CHECK(cond)                                                        \
    do {                                                                   \
        ++bbtest::stats_singleton().checks;                                          \
        if (!(cond)) {                                                     \
            ++bbtest::stats_singleton().failures;                                    \
            std::printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
        }                                                                  \
    } while (0)

#define CHECK_STR_EQ(a, b)                                                     \
    do {                                                                       \
        ++bbtest::stats_singleton().checks;                                              \
        std::string _a = (a);                                                  \
        std::string _b = (b);                                                  \
        if (_a != _b) {                                                        \
            ++bbtest::stats_singleton().failures;                                        \
            std::printf("  FAIL %s:%d: %s != %s\n    got:      '%s'\n    wanted:  '%s'\n", \
                        __FILE__, __LINE__, #a, #b, _a.c_str(), _b.c_str());   \
        }                                                                      \
    } while (0)

#define CHECK_INT_EQ(a, b)                                                     \
    do {                                                                       \
        ++bbtest::stats_singleton().checks;                                              \
        long long _a = (a);                                                    \
        long long _b = (b);                                                    \
        if (_a != _b) {                                                        \
            ++bbtest::stats_singleton().failures;                                        \
            std::printf("  FAIL %s:%d: %s != %s (%lld != %lld)\n",             \
                        __FILE__, __LINE__, #a, #b, _a, _b);                   \
        }                                                                      \
    } while (0)

#define CHECK_THROWS(expr, Ex)                                                 \
    do {                                                                       \
        ++bbtest::stats_singleton().checks;                                              \
        bool _threw = bbtest::throws_fn<Ex>([&]() { (void)(expr); });          \
        if (!_threw) {                                                         \
            ++bbtest::stats_singleton().failures;                                        \
            std::printf("  FAIL %s:%d: expected %s from %s\n", __FILE__,       \
                        __LINE__, #Ex, #expr);                                 \
        }                                                                      \
    } while (0)

#define CHECK_NOT_THROWS(expr)                                                 \
    do {                                                                       \
        ++bbtest::stats_singleton().checks;                                              \
        bool _threw = false;                                                   \
        try {                                                                  \
            (void)(expr);                                                      \
        } catch (const std::exception& e) {                                    \
            _threw = true;                                                     \
            std::printf("  FAIL %s:%d: %s threw: %s\n", __FILE__, __LINE__,    \
                        #expr, e.what());                                      \
        } catch (...) {                                                        \
            _threw = true;                                                     \
            std::printf("  FAIL %s:%d: %s threw (non-std)\n", __FILE__,        \
                        __LINE__, #expr);                                      \
        }                                                                      \
        if (_threw)                                                            \
            ++bbtest::stats_singleton().failures;                                        \
    } while (0)

#endif // BB_TESTS_H