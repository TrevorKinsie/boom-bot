#include "tests.h"

#include "bb_exceptions.h"
#include "bb_json.h"
#include "bb_money.h"

using namespace bb;

TEST_CASE(json_round_trip_compact) {
    Json doc = Json::object();
    doc.set("a", Json(int64_t(1)));
    doc.set("b", Json("text"));
    doc.set("c", Json(true));
    doc.set("d", Json(nullptr));
    Json arr = Json::array();
    arr.push(Json(int64_t(1)));
    arr.push(Json(std::string("two")));
    doc.set("e", arr);
    CHECK_STR_EQ(doc.dump(), "{\"a\": 1, \"b\": \"text\", \"c\": true, \"d\": null, \"e\": [1, \"two\"]}");
}

TEST_CASE(json_indent_matches_python) {
    Json doc = Json::object();
    doc.set("a", Json(int64_t(1)));
    Json arr = Json::array();
    arr.push(Json(int64_t(1)));
    arr.push(Json(int64_t(2)));
    doc.set("b", arr);
    // Python json.dumps({"a": 1, "b": [1, 2]}, indent=4, ensure_ascii=False)
    CHECK_STR_EQ(doc.dump(4),
                 "{\n"
                 "    \"a\": 1,\n"
                 "    \"b\": [\n"
                 "        1,\n"
                 "        2\n"
                 "    ]\n"
                 "}");
    CHECK_STR_EQ(Json::object().dump(4), "{}");
    CHECK_STR_EQ(Json::array().dump(4), "[]");
}

TEST_CASE(json_parses_numbers) {
    CHECK(Json::parse("42").is_number());
    CHECK(Json::parse("42").type() == Json::Type::Int);
    CHECK_INT_EQ(Json::parse("42").as_int(), 42);
    CHECK(Json::parse("42.5").type() == Json::Type::Double);
    CHECK(Json::parse("42.5").as_double() == 42.5);
    CHECK(Json::parse("-3").as_int() == -3);
    CHECK(Json::parse("1e2").as_double() == 100.0);
    CHECK(Json::parse("0").as_int() == 0);
}

TEST_CASE(json_double_formatting) {
    Json one = Json(100.0);
    CHECK_STR_EQ(one.dump(), "100.0");
    Json frac = Json(0.1);
    CHECK_STR_EQ(frac.dump(), "0.1");
    Json negative = Json(-0.0);
    CHECK_STR_EQ(negative.dump(), "-0.0");
}

TEST_CASE(json_string_escaping) {
    Json s = Json(std::string("quote\" back\\ slash\n newline \t tab \x01 control"));
    Json reparsed = Json::parse(s.dump());
    CHECK_STR_EQ(reparsed.as_string(), "quote\" back\\ slash\n newline \t tab \x01 control");
}

TEST_CASE(json_utf8_passthrough) {
    // ensure_ascii=False: emoji and non-ASCII flow through raw.
    Json s = Json(std::string("\xF0\x9F\x92\xA5 \xE2\x9A\xA1 \xE4\xBD\xA0\xE5\xA5\xBD"));
    std::string dumped = s.dump();
    CHECK(dumped.find("\xF0\x9F\x92\xA5") != std::string::npos);
    Json reparsed = Json::parse(dumped);
    CHECK_STR_EQ(reparsed.as_string(), s.as_string());
}

TEST_CASE(json_unicode_escapes) {
    CHECK_STR_EQ(Json::parse("\"\\u4F60\\u597D\"").as_string(), "\xE4\xBD\xA0\xE5\xA5\xBD");
    // Surrogate pair for U+1F4A5 (emoji).
    CHECK_STR_EQ(Json::parse("\"\\uD83D\\uDCA5\"").as_string(), "\xF0\x9F\x92\xA5");
}

TEST_CASE(json_object_access) {
    Json doc = Json::parse("{\"name\": \"k\", \"n\": 7, \"flag\": true}");
    CHECK(doc.has("name"));
    CHECK(!doc.has("missing"));
    CHECK_STR_EQ(doc.get_string("name"), "k");
    CHECK_INT_EQ(doc.get_int("n"), 7);
    CHECK_INT_EQ(doc.get_int("missing", 99), 99);
    CHECK(doc.get_bool("flag"));
    CHECK(doc.find("name") != nullptr);
    CHECK(doc.find("zzz") == nullptr);
}

TEST_CASE(json_arrays_and_nesting) {
    Json doc = Json::parse("{\"rows\": [[\"a\", \"b\"], [\"c\", \"d\"]]}");
    const Json& rows = doc.at("rows");
    CHECK_INT_EQ(rows.size(), 2);
    CHECK_STR_EQ(rows.at(0).at(1).as_string(), "b");
}

TEST_CASE(json_rejects_malformed) {
    CHECK_THROWS(Json::parse(""), JsonError);
    CHECK_THROWS(Json::parse("{"), JsonError);
    CHECK_THROWS(Json::parse("[1, 2"), JsonError);
    CHECK_THROWS(Json::parse("{\"a\": }"), JsonError);
    CHECK_THROWS(Json::parse("tru"), JsonError);
    CHECK_THROWS(Json::parse("'single'"), JsonError);
    CHECK_THROWS(Json::parse("{} trailing"), JsonError);
    CHECK_THROWS(Json::parse("\"unterminated"), JsonError);
    CHECK_THROWS(Json::parse("01"), JsonError);
}

TEST_CASE(json_equality) {
    CHECK(Json::parse("{\"a\": [1, 2]}") == Json::parse("{\"a\": [1, 2]}"));
    CHECK(Json::parse("{\"a\": [1, 2]}") != Json::parse("{\"a\": [1, 3]}"));
    CHECK(Json(int64_t(5)) == Json(int64_t(5)));
}

TEST_CASE(money_constructs_and_quantizes) {
    Money money("10.005");
    CHECK_INT_EQ(money.cents(), 1001);
    CHECK_STR_EQ(money.formatted(), "10.01");
    CHECK_STR_EQ(Money("10").formatted(), "10.00");
    CHECK_INT_EQ(Money("0.1").cents(), 10);
    CHECK_INT_EQ(Money("0.001").cents(), 0);
    CHECK_INT_EQ(Money("1.0049").cents(), 100);
    CHECK_INT_EQ(Money("1.0050").cents(), 101);
}

TEST_CASE(money_rejects_negative_amounts) {
    CHECK_THROWS(Money("-1"), NegativeMonetaryAmountException);
    CHECK_THROWS(Money("-0.01"), NegativeMonetaryAmountException);
}

TEST_CASE(money_rejects_non_numeric) {
    CHECK_THROWS(Money("not-a-number"), NegativeMonetaryAmountException);
    CHECK_THROWS(Money(""), NegativeMonetaryAmountException);
    CHECK_THROWS(Money("1.2.3"), NegativeMonetaryAmountException);
}

TEST_CASE(money_zero) {
    CHECK(Money::zero().is_zero());
    CHECK(!Money("1").is_zero());
}

TEST_CASE(money_addition) {
    CHECK_STR_EQ(Money("10").add(Money("5")).formatted(), "15.00");
}

TEST_CASE(money_subtraction) {
    CHECK_STR_EQ(Money("10").subtract(Money("4")).formatted(), "6.00");
    CHECK_THROWS(Money("4").subtract(Money("10")), NegativeMonetaryAmountException);
}

TEST_CASE(money_multiplication) {
    CHECK_STR_EQ(Money("10").multiply(int64_t(3)).formatted(), "30.00");
    CHECK_STR_EQ(Money("10").multiply("3").formatted(), "30.00");
    CHECK_STR_EQ(Money("10").multiply("0.5").formatted(), "5.00");
}

TEST_CASE(money_comparisons) {
    CHECK(Money("5").is_less_than(Money("6")));
    CHECK(Money("7").is_greater_than(Money("6")));
    CHECK(Money("6").is_greater_than_or_equal_to(Money("6")));
    CHECK_INT_EQ(Money("5").compare_to(Money("6")), -1);
    CHECK_INT_EQ(Money("7").compare_to(Money("6")), 1);
    CHECK_INT_EQ(Money("6").compare_to(Money("6")), 0);
}

TEST_CASE(money_structural_equality) {
    CHECK(Money("10") == Money("10.00"));
    CHECK(Money("10") != Money("11"));
    CHECK(Money("10").to_decimal_string() == "10.00");
}

TEST_CASE(aggregate_version) {
    CHECK_INT_EQ(AggregateVersion().number(), 0);
    CHECK_INT_EQ(AggregateVersion(3).next().number(), 4);
    CHECK_THROWS(AggregateVersion(-1), std::invalid_argument);
}