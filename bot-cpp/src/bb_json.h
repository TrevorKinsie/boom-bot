/*
 * bb_json.h - minimal JSON DOM, dependency-free.
 *
 * Mirrors the JSON needs of the Python port: parse arbitrary JSON documents,
 * serialize with Python-compatible formatting (compact ", "/": " separators,
 * or 4-space indentation), raw UTF-8 passthrough (ensure_ascii=False).
 */
#ifndef BB_JSON_H
#define BB_JSON_H

#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace bb {

class JsonError : public std::runtime_error {
public:
    explicit JsonError(const std::string& msg) : std::runtime_error(msg) {}
};

class Json {
public:
    enum class Type { Null, Bool, Int, Double, Str, Arr, Obj };

    Json() : t_(Type::Null), b_(false), i_(0), d_(0.0) {}
    Json(std::nullptr_t) : t_(Type::Null), b_(false), i_(0), d_(0.0) {}
    Json(bool v) : t_(Type::Bool), b_(v), i_(0), d_(0.0) {}
    Json(int v) : t_(Type::Int), b_(false), i_(v), d_(0.0) {}
    Json(int64_t v) : t_(Type::Int), b_(false), i_(v), d_(0.0) {}
    Json(double v) : t_(Type::Double), b_(false), i_(0), d_(v) {}
    Json(const char* v) : t_(Type::Str), b_(false), i_(0), d_(0.0), s_(v) {}
    Json(std::string v) : t_(Type::Str), b_(false), i_(0), d_(0.0), s_(std::move(v)) {}

    static Json object();
    static Json array();
    static Json parse(const std::string& text);

    Type type() const { return t_; }
    bool is_null() const { return t_ == Type::Null; }
    bool is_bool() const { return t_ == Type::Bool; }
    bool is_number() const { return t_ == Type::Int || t_ == Type::Double; }
    bool is_string() const { return t_ == Type::Str; }
    bool is_array() const { return t_ == Type::Arr; }
    bool is_object() const { return t_ == Type::Obj; }

    bool as_bool() const;
    int64_t as_int() const;
    double as_double() const;
    const std::string& as_string() const;
    const std::vector<Json>& as_array() const;
    const std::map<std::string, Json>& as_object() const;

    size_t size() const;
    const Json& at(size_t index) const;
    bool has(const std::string& key) const;
    const Json& at(const std::string& key) const;
    const Json* find(const std::string& key) const;

    // Typed lookups with defaults.
    std::string get_string(const std::string& key, const std::string& dflt = "") const;
    int64_t get_int(const std::string& key, int64_t dflt = 0) const;
    double get_double(const std::string& key, double dflt = 0.0) const;
    bool get_bool(const std::string& key, bool dflt = false) const;

    // Mutators.
    void set(const std::string& key, Json value);
    void push(Json value);

    // Serialization. indent < 0: compact Python style; indent >= 0: that many
    // spaces per level (Python's json.dumps(indent=N) uses 4 in this app).
    std::string dump(int indent = -1) const;

    bool operator==(const Json& other) const;
    bool operator!=(const Json& other) const { return !(*this == other); }

private:
    Json(Type t, bool b, int64_t i, double d, std::string s,
         std::vector<Json> arr, std::map<std::string, Json> obj)
        : t_(t), b_(b), i_(i), d_(d), s_(std::move(s)), arr_(std::move(arr)),
          obj_(std::move(obj)) {}

    Type t_;
    bool b_;
    int64_t i_;
    double d_;
    std::string s_;
    std::vector<Json> arr_;
    std::map<std::string, Json> obj_;
};

} // namespace bb

#endif // BB_JSON_H
