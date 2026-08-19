#include "bb_json.h"

#include <cerrno>
#include <charconv>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

namespace bb {

namespace {

struct Parser {
    const char* p;
    const char* end;

    explicit Parser(const std::string& text) : p(text.data()), end(text.data() + text.size()) {}

    [[noreturn]] void fail(const std::string& msg) const {
        throw JsonError(msg + " at offset " + std::to_string(end - p) + " (error at '" +
                        std::string(p, std::min<size_t>(16, static_cast<size_t>(end - p))) +
                        "')");
    }

    void skip_ws() {
        while (p < end && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r'))
            ++p;
    }

    bool eof() const { return p >= end; }

    char peek() const { return eof() ? '\0' : *p; }

    void expect(char c) {
        if (eof() || *p != c)
            fail(std::string("expected '") + c + "'");
        ++p;
    }

    static void append_utf8(std::string& out, uint32_t cp) {
        if (cp < 0x80) {
            out.push_back(static_cast<char>(cp));
        } else if (cp < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else if (cp < 0x10000) {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    uint32_t parse_hex4() {
        if (end - p < 4)
            fail("truncated \\u escape");
        uint32_t v = 0;
        for (int i = 0; i < 4; ++i) {
            char c = *p++;
            v <<= 4;
            if (c >= '0' && c <= '9')
                v |= static_cast<uint32_t>(c - '0');
            else if (c >= 'a' && c <= 'f')
                v |= static_cast<uint32_t>(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F')
                v |= static_cast<uint32_t>(c - 'A' + 10);
            else
                fail("invalid hex digit in \\u escape");
        }
        return v;
    }

    std::string parse_string() {
        expect('"');
        std::string out;
        while (true) {
            if (eof())
                fail("unterminated string");
            char c = *p++;
            if (c == '"')
                break;
            if (static_cast<unsigned char>(c) < 0x20)
                fail("unescaped control character in string");
            if (c == '\\') {
                if (eof())
                    fail("unterminated escape");
                char e = *p++;
                switch (e) {
                    case '"': out.push_back('"'); break;
                    case '\\': out.push_back('\\'); break;
                    case '/': out.push_back('/'); break;
                    case 'b': out.push_back('\b'); break;
                    case 'f': out.push_back('\f'); break;
                    case 'n': out.push_back('\n'); break;
                    case 'r': out.push_back('\r'); break;
                    case 't': out.push_back('\t'); break;
                    case 'u': {
                        uint32_t cp = parse_hex4();
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            // High surrogate: expect a low surrogate pair.
                            if (end - p >= 2 && p[0] == '\\' && p[1] == 'u') {
                                p += 2;
                                uint32_t lo = parse_hex4();
                                if (lo >= 0xDC00 && lo <= 0xDFFF) {
                                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                                } else {
                                    fail("invalid low surrogate");
                                }
                            } else {
                                fail("lone high surrogate");
                            }
                        }
                        append_utf8(out, cp);
                        break;
                    }
                    default: fail(std::string("invalid escape '\\") + e + "'");
                }
            } else {
                out.push_back(c);
            }
        }
        return out;
    }

    Json parse_number() {
        const char* start = p;
        if (peek() == '-')
            ++p;
        bool has_int_digits = false;
        while (p < end && *p >= '0' && *p <= '9') {
            has_int_digits = true;
            ++p;
        }
        bool is_double = false;
        bool has_frac_digits = false;
        if (peek() == '.') {
            is_double = true;
            ++p;
            while (p < end && *p >= '0' && *p <= '9') {
                has_frac_digits = true;
                ++p;
            }
        }
        bool has_exp_digits = false;
        if (peek() == 'e' || peek() == 'E') {
            is_double = true;
            ++p;
            if (peek() == '+' || peek() == '-')
                ++p;
            while (p < end && *p >= '0' && *p <= '9') {
                has_exp_digits = true;
                ++p;
            }
        }
        std::string token(start, p);
        if (token.empty() || token == "-" || !has_int_digits)
            fail("invalid number");
        // JSON forbids leading zeros ("01", "-01").
        size_t first_digit = token[0] == '-' ? 1 : 0;
        if (token.size() > first_digit + 1 && token[first_digit] == '0' &&
            (token[first_digit + 1] >= '0' && token[first_digit + 1] <= '9'))
            fail("leading zero in number");
        // "1." and "1e" are not valid JSON numbers.
        if (is_double && !has_frac_digits && !has_exp_digits)
            fail("invalid number");
        if (is_double) {
            char* endptr = nullptr;
            errno = 0;
            double d = std::strtod(token.c_str(), &endptr);
            if (endptr != token.c_str() + token.size())
                fail("invalid number");
            return Json(d);
        }
        int64_t v = 0;
        auto [ptr, ec] = std::from_chars(token.c_str(), token.c_str() + token.size(), v);
        if (ec == std::errc()) {
            return Json(v);
        }
        // Overflow: fall back to double (JSON numbers are unbounded).
        char* endptr = nullptr;
        double d = std::strtod(token.c_str(), &endptr);
        if (endptr != token.c_str() + token.size())
            fail("invalid number");
        return Json(d);
    }

    Json parse_value() {
        skip_ws();
        if (eof())
            fail("unexpected end of input");
        char c = *p;
        if (c == '"')
            return Json(parse_string());
        if (c == '{') {
            ++p;
            Json obj = Json::object();
            skip_ws();
            if (peek() == '}') {
                ++p;
                return obj;
            }
            while (true) {
                skip_ws();
                if (peek() != '"')
                    fail("expected object key string");
                std::string key = parse_string();
                skip_ws();
                expect(':');
                obj.set(key, parse_value());
                skip_ws();
                if (peek() == ',') {
                    ++p;
                    continue;
                }
                expect('}');
                return obj;
            }
        }
        if (c == '[') {
            ++p;
            Json arr = Json::array();
            skip_ws();
            if (peek() == ']') {
                ++p;
                return arr;
            }
            while (true) {
                arr.push(parse_value());
                skip_ws();
                if (peek() == ',') {
                    ++p;
                    continue;
                }
                expect(']');
                return arr;
            }
        }
        if (c == 't') {
            if (end - p >= 4 && std::memcmp(p, "true", 4) == 0) {
                p += 4;
                return Json(true);
            }
            fail("invalid literal");
        }
        if (c == 'f') {
            if (end - p >= 5 && std::memcmp(p, "false", 5) == 0) {
                p += 5;
                return Json(false);
            }
            fail("invalid literal");
        }
        if (c == 'n') {
            if (end - p >= 4 && std::memcmp(p, "null", 4) == 0) {
                p += 4;
                return Json(nullptr);
            }
            fail("invalid literal");
        }
        if (c == '-' || (c >= '0' && c <= '9'))
            return parse_number();
        fail("unexpected character");
    }
};

void escape_string(std::string& out, const std::string& s) {
    out.push_back('"');
    for (char ch : s) {
        unsigned char c = static_cast<unsigned char>(ch);
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    // Python emits \u00XX for other control characters.
                    const char* hex = "0123456789abcdef";
                    out += "\\u00";
                    out.push_back(hex[(c >> 4) & 0xF]);
                    out.push_back(hex[c & 0xF]);
                } else {
                    out.push_back(static_cast<char>(c));
                }
        }
    }
    out.push_back('"');
}

std::string format_double(double d) {
    char buf[64];
    auto [ptr, ec] = std::to_chars(buf, buf + sizeof(buf), d, std::chars_format::general);
    std::string s(buf, ptr);
    if (ec != std::errc())
        return "0.0";
    // Python repr: integral doubles print with a trailing ".0".
    if (s.find('.') == std::string::npos && s.find('e') == std::string::npos &&
        s.find('E') == std::string::npos) {
        s += ".0";
    }
    return s;
}

void dump_value(const Json& v, std::string& out, int indent, int level) {
    switch (v.type()) {
        case Json::Type::Null:
            out += "null";
            return;
        case Json::Type::Bool:
            out += v.as_bool() ? "true" : "false";
            return;
        case Json::Type::Int:
            out += std::to_string(v.as_int());
            return;
        case Json::Type::Double:
            out += format_double(v.as_double());
            return;
        case Json::Type::Str:
            escape_string(out, v.as_string());
            return;
        case Json::Type::Arr: {
            const auto& arr = v.as_array();
            if (arr.empty()) {
                out += "[]";
                return;
            }
            if (indent < 0) {
                out.push_back('[');
                for (size_t i = 0; i < arr.size(); ++i) {
                    if (i)
                        out += ", ";
                    dump_value(arr[i], out, indent, level);
                }
                out.push_back(']');
            } else {
                out.push_back('[');
                for (size_t i = 0; i < arr.size(); ++i) {
                    out += "\n";
                    out.append(static_cast<size_t>(indent) * (level + 1), ' ');
                    dump_value(arr[i], out, indent, level + 1);
                    if (i + 1 < arr.size())
                        out.push_back(',');
                }
                out += "\n";
                out.append(static_cast<size_t>(indent) * level, ' ');
                out.push_back(']');
            }
            return;
        }
        case Json::Type::Obj: {
            const auto& obj = v.as_object();
            if (obj.empty()) {
                out += "{}";
                return;
            }
            if (indent < 0) {
                out.push_back('{');
                size_t i = 0;
                for (const auto& [key, val] : obj) {
                    if (i++)
                        out += ", ";
                    escape_string(out, key);
                    out += ": ";
                    dump_value(val, out, indent, level);
                }
                out.push_back('}');
            } else {
                out.push_back('{');
                for (const auto& [key, val] : obj) {
                    out += "\n";
                    out.append(static_cast<size_t>(indent) * (level + 1), ' ');
                    escape_string(out, key);
                    out += ": ";
                    dump_value(val, out, indent, level + 1);
                    out.push_back(',');
                }
                // Python does not emit a trailing comma; drop the last one.
                if (out.back() == ',')
                    out.pop_back();
                out += "\n";
                out.append(static_cast<size_t>(indent) * level, ' ');
                out.push_back('}');
            }
            return;
        }
    }
}

} // namespace

Json Json::object() {
    return Json(Type::Obj, false, 0, 0.0, "", {}, {});
}

Json Json::array() {
    return Json(Type::Arr, false, 0, 0.0, "", {}, {});
}

Json Json::parse(const std::string& text) {
    Parser parser(text);
    parser.skip_ws();
    if (parser.eof())
        throw JsonError("empty document");
    Json v = parser.parse_value();
    parser.skip_ws();
    if (!parser.eof())
        parser.fail("trailing content after document");
    return v;
}

bool Json::as_bool() const {
    if (t_ != Type::Bool)
        throw JsonError("not a boolean");
    return b_;
}

int64_t Json::as_int() const {
    if (t_ == Type::Int)
        return i_;
    if (t_ == Type::Double)
        return static_cast<int64_t>(d_);
    throw JsonError("not a number");
}

double Json::as_double() const {
    if (t_ == Type::Int)
        return static_cast<double>(i_);
    if (t_ == Type::Double)
        return d_;
    throw JsonError("not a number");
}

const std::string& Json::as_string() const {
    if (t_ != Type::Str)
        throw JsonError("not a string");
    return s_;
}

const std::vector<Json>& Json::as_array() const {
    if (t_ != Type::Arr)
        throw JsonError("not an array");
    return arr_;
}

const std::map<std::string, Json>& Json::as_object() const {
    if (t_ != Type::Obj)
        throw JsonError("not an object");
    return obj_;
}

size_t Json::size() const {
    if (t_ == Type::Arr)
        return arr_.size();
    if (t_ == Type::Obj)
        return obj_.size();
    if (t_ == Type::Str)
        return s_.size();
    throw JsonError("no size for this type");
}

const Json& Json::at(size_t index) const {
    if (t_ != Type::Arr || index >= arr_.size())
        throw JsonError("array index out of range");
    return arr_[index];
}

bool Json::has(const std::string& key) const {
    return t_ == Type::Obj && obj_.count(key) > 0;
}

const Json& Json::at(const std::string& key) const {
    if (t_ != Type::Obj) {
        static const Json null_json = Json(nullptr);
        return null_json;
    }
    auto it = obj_.find(key);
    if (it == obj_.end()) {
        static const Json null_json = Json(nullptr);
        return null_json;
    }
    return it->second;
}

const Json* Json::find(const std::string& key) const {
    if (t_ != Type::Obj)
        return nullptr;
    auto it = obj_.find(key);
    return it == obj_.end() ? nullptr : &it->second;
}

std::string Json::get_string(const std::string& key, const std::string& dflt) const {
    const Json* v = find(key);
    if (v == nullptr || v->is_null())
        return dflt;
    if (v->is_string())
        return v->as_string();
    return v->dump();
}

int64_t Json::get_int(const std::string& key, int64_t dflt) const {
    const Json* v = find(key);
    if (v == nullptr || v->is_null() || !v->is_number())
        return dflt;
    return v->as_int();
}

double Json::get_double(const std::string& key, double dflt) const {
    const Json* v = find(key);
    if (v == nullptr || v->is_null() || !v->is_number())
        return dflt;
    return v->as_double();
}

bool Json::get_bool(const std::string& key, bool dflt) const {
    const Json* v = find(key);
    if (v == nullptr || v->is_null() || !v->is_bool())
        return dflt;
    return v->as_bool();
}

void Json::set(const std::string& key, Json value) {
    if (t_ != Type::Obj)
        throw JsonError("set() on non-object");
    obj_[key] = std::move(value);
}

void Json::push(Json value) {
    if (t_ != Type::Arr)
        throw JsonError("push() on non-array");
    arr_.push_back(std::move(value));
}

std::string Json::dump(int indent) const {
    std::string out;
    dump_value(*this, out, indent, 0);
    return out;
}

bool Json::operator==(const Json& other) const {
    if (t_ != other.t_)
        return false;
    switch (t_) {
        case Type::Null: return true;
        case Type::Bool: return b_ == other.b_;
        case Type::Int: return i_ == other.i_;
        case Type::Double: return d_ == other.d_;
        case Type::Str: return s_ == other.s_;
        case Type::Arr: return arr_ == other.arr_;
        case Type::Obj: return obj_ == other.obj_;
    }
    return false;
}

} // namespace bb
