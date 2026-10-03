#include "bb_regex.h"

#include <array>
#include <cstdint>
#include <memory>

namespace bb {

namespace {

char fold_ascii(char c) {
    if (c >= 'A' && c <= 'Z')
        return static_cast<char>(c - 'A' + 'a');
    return c;
}

// --- AST ---

struct Node {
    enum Kind { Seq, Alt, Char, Any, Class, Start, End, Group, Star, Plus, Opt } kind;
    std::vector<Node> children{};           // Seq, Alt, Group
    char ch = 0;                            // Char
    bool negate = false;                    // Class
    std::shared_ptr<std::array<bool, 256>> cls{};  // Class
    bool lazy = false;                      // Star, Plus, Opt
    int group_index = -1;                   // Group
};

struct Parser {
    const std::string& p;
    size_t i = 0;
    int next_group = 1;
    bool ok = true;

    explicit Parser(const std::string& pattern) : p(pattern) {}

    Node parse() {
        Node alt = parse_alt();
        if (i != p.size())
            ok = false;
        return alt;
    }

    Node parse_alt() {
        Node node{Node::Alt};
        node.children.push_back(parse_seq());
        while (i < p.size() && p[i] == '|') {
            ++i;
            node.children.push_back(parse_seq());
        }
        return node;
    }

    Node parse_seq() {
        Node node{Node::Seq};
        while (i < p.size() && p[i] != '|' && p[i] != ')') {
            Node atom = parse_atom();
            // Quantifier?
            if (i < p.size() && (p[i] == '*' || p[i] == '+' || p[i] == '?')) {
                char q = p[i++];
                bool lazy = false;
                if (i < p.size() && p[i] == '?') {
                    lazy = true;
                    ++i;
                }
                Node qn;
                qn.kind = q == '*' ? Node::Star : (q == '+' ? Node::Plus : Node::Opt);
                qn.lazy = lazy;
                qn.children.push_back(std::move(atom));
                node.children.push_back(std::move(qn));
            } else {
                node.children.push_back(std::move(atom));
            }
        }
        return node;
    }

    std::shared_ptr<std::array<bool, 256>> make_class(bool negate,
                                                      const std::vector<std::pair<char, char>>& ranges) {
        auto table = std::make_shared<std::array<bool, 256>>();
        for (const auto& [lo, hi] : ranges)
            for (unsigned char k = static_cast<unsigned char>(lo);
                 k <= static_cast<unsigned char>(hi); ++k)
                (*table)[static_cast<unsigned char>(k)] = true;
        if (negate)
            for (auto& b : *table)
                b = !b;
        return table;
    }

    Node parse_class() {
        // Caller has consumed '['
        Node node{Node::Class};
        bool negate = false;
        if (i < p.size() && p[i] == '^') {
            negate = true;
            ++i;
        }
        std::vector<std::pair<char, char>> ranges;
        bool first = true;
        while (i < p.size() && (p[i] != ']' || first)) {
            first = false;
            char lo, hi;
            if (p[i] == '\\' && i + 1 < p.size()) {
                char e = p[++i];
                switch (e) {
                    case 'd': lo = '0'; hi = '9'; break;
                    case 'w':
                        ranges.emplace_back('a', 'z');
                        ranges.emplace_back('A', 'Z');
                        ranges.emplace_back('0', '9');
                        ranges.emplace_back('_', '_');
                        lo = hi = 1; // marker: re-add below
                        break;
                    case 's': lo = '\t'; hi = '\f'; break;
                    case 'n': lo = hi = '\n'; break;
                    case 't': lo = hi = '\t'; break;
                    case 'r': lo = hi = '\r'; break;
                    default: lo = hi = e; break;
                }
            } else {
                lo = hi = p[i];
            }
            ++i;
            if (p[i] == '-' && i + 1 < p.size() && p[i + 1] != ']') {
                ++i;
                char h = p[i];
                if (h == '\\' && i + 1 < p.size()) {
                    h = p[++i];
                }
                ++i;
                hi = h;
            }
            if (lo == 1 && hi == 1) {
                continue; // '\w' was already expanded into ranges
            }
            ranges.emplace_back(lo, hi);
        }
        if (i < p.size() && p[i] == ']')
            ++i;
        else
            ok = false;
        node.negate = negate;
        node.cls = make_class(negate, ranges);
        return node;
    }

    Node parse_atom() {
        if (i >= p.size()) {
            ok = false;
            return Node{Node::Any};
        }
        char c = p[i];
        if (c == '(') {
            ++i;
            Node group{Node::Group};
            bool capturing = true;
            if (i + 1 < p.size() && p[i] == '?' && p[i + 1] == ':') {
                capturing = false;
                i += 2;
            } else if (i + 1 < p.size() && p[i] == '?' && p[i + 1] == 'P') {
                // (?P<name>...) - capturing, ignore the name
                i += 2;
                while (i < p.size() && p[i] != '>')
                    ++i;
                if (i < p.size())
                    ++i;
            } else if (i + 1 < p.size() && p[i] == '?') {
                // Unsupported group syntax ((?i), (?=...) etc.) - treat as error.
                ok = false;
                ++i;
            }
            group.group_index = capturing ? next_group++ : -1;
            group.children.push_back(parse_alt());
            if (i < p.size() && p[i] == ')')
                ++i;
            else
                ok = false;
            return group;
        }
        if (c == '[') {
            ++i;
            return parse_class();
        }
        if (c == '\\') {
            ++i;
            if (i >= p.size()) {
                ok = false;
                return Node{Node::Any};
            }
            char e = p[i++];
            Node node;
            switch (e) {
                case 'd': case 'D': case 'w': case 'W': case 's': case 'S': {
                    node.kind = Node::Class;
                    std::vector<std::pair<char, char>> ranges;
                    bool negate = false;
                    switch (e) {
                        case 'd': ranges.emplace_back('0', '9'); break;
                        case 'D': negate = true; ranges.emplace_back('0', '9'); break;
                        case 'w': {
                            ranges.emplace_back('a', 'z');
                            ranges.emplace_back('A', 'Z');
                            ranges.emplace_back('0', '9');
                            ranges.emplace_back('_', '_');
                            break;
                        }
                        case 'W': {
                            negate = true;
                            ranges.emplace_back('a', 'z');
                            ranges.emplace_back('A', 'Z');
                            ranges.emplace_back('0', '9');
                            ranges.emplace_back('_', '_');
                            break;
                        }
                        case 's': ranges.emplace_back(' ', ' '); ranges.emplace_back('\t', '\t');
                                  ranges.emplace_back('\n', '\n'); ranges.emplace_back('\r', '\r');
                                  ranges.emplace_back('\f', '\f'); ranges.emplace_back('\v', '\v');
                                  break;
                        case 'S': {
                            negate = true;
                            ranges.emplace_back(' ', ' ');
                            ranges.emplace_back('\t', '\t');
                            ranges.emplace_back('\n', '\n');
                            ranges.emplace_back('\r', '\r');
                            ranges.emplace_back('\f', '\f');
                            ranges.emplace_back('\v', '\v');
                            break;
                        }
                    }
                    node.negate = negate;
                    node.cls = make_class(negate, ranges);
                    return node;
                }
                case 'n': node.kind = Node::Char; node.ch = '\n'; return node;
                case 't': node.kind = Node::Char; node.ch = '\t'; return node;
                case 'r': node.kind = Node::Char; node.ch = '\r'; return node;
                case 'f': node.kind = Node::Char; node.ch = '\f'; return node;
                case 'v': node.kind = Node::Char; node.ch = '\v'; return node;
                default: node.kind = Node::Char; node.ch = e; return node;
            }
        }
        if (c == '.') {
            ++i;
            Node node{Node::Any};
            return node;
        }
        if (c == '^') {
            ++i;
            return Node{Node::Start};
        }
        if (c == '$') {
            ++i;
            return Node{Node::End};
        }
        if (c == ')' || c == '|' || c == '*' || c == '+' || c == '?') {
            ok = false;
            ++i;
            return Node{Node::Any};
        }
        ++i;
        Node node{Node::Char};
        node.ch = c;
        return node;
    }
};

// --- Bytecode ---

enum class Op : uint8_t {
    Char, Class, Any, Start, End, Save, Split, Jump, Match,
};

struct Ins {
    Op op;
    char ch = 0;
    int x = 0;
    int y = 0;
    int g = -1;
    bool close = false;             // Save: writing group end (vs start)
    std::shared_ptr<std::array<bool, 256>> cls;
};

struct Compiler {
    std::vector<Ins> ins;

    int here() const { return static_cast<int>(ins.size()); }
    void emit(Op op) { ins.push_back(Ins{op, 0, 0, 0, -1, false, {}}); }

    void compile(const Node& node) {
        switch (node.kind) {
            case Node::Seq:
                for (const Node& child : node.children)
                    compile(child);
                break;
            case Node::Alt: {
                if (node.children.size() == 1) {
                    compile(node.children[0]);
                    break;
                }
                // children[0]: SPLIT(body0, rest); body0; JMP done
                int split0 = here();
                emit(Op::Split);
                int body0 = here();
                compile(node.children[0]);
                int jump0 = here();
                emit(Op::Jump);
                int rest0 = here();
                std::vector<int> splits, body_ins, jumps;
                size_t k = 1;
                for (; k + 1 < node.children.size(); ++k) {
                    // SPLIT(bodyK, restK+1); bodyK; JMP done
                    splits.push_back(here());
                    emit(Op::Split);
                    body_ins.push_back(here());
                    compile(node.children[k]);
                    jumps.push_back(here());
                    emit(Op::Jump);
                }
                int last_start = here();
                compile(node.children[k]); // last branch falls through to done
                int done = here();
                ins[static_cast<size_t>(split0)].x = body0;
                ins[static_cast<size_t>(split0)].y = rest0;
                ins[static_cast<size_t>(jump0)].x = done;
                for (size_t j = 0; j < splits.size(); ++j) {
                    ins[static_cast<size_t>(splits[j])].x = body_ins[j];
                    ins[static_cast<size_t>(splits[j])].y =
                        j + 1 < splits.size() ? splits[j + 1] : last_start;
                }
                for (size_t j = 0; j < jumps.size(); ++j)
                    ins[static_cast<size_t>(jumps[j])].x = done;
                break;
            }
            case Node::Char: {
                Ins i;
                i.op = Op::Char;
                i.ch = node.ch;
                ins.push_back(i);
                break;
            }
            case Node::Class: {
                Ins i;
                i.op = Op::Class;
                i.cls = node.cls;
                ins.push_back(i);
                break;
            }
            case Node::Any:
                emit(Op::Any);
                break;
            case Node::Start:
                emit(Op::Start);
                break;
            case Node::End:
                emit(Op::End);
                break;
            case Node::Group: {
                if (node.group_index > 0) {
                    Ins s1;
                    s1.op = Op::Save;
                    s1.g = node.group_index;
                    s1.close = false;
                    ins.push_back(s1);
                }
                for (const Node& child : node.children)
                    compile(child);
                if (node.group_index > 0) {
                    Ins s2;
                    s2.op = Op::Save;
                    s2.g = node.group_index;
                    s2.close = true;
                    ins.push_back(s2);
                }
                break;
            }
            case Node::Star:
            case Node::Plus:
            case Node::Opt: {
                const Node& body = node.children[0];
                if (node.kind == Node::Plus) {
                    int body_start = here();
                    compile(body);
                    int split = here();
                    emit(Op::Split);
                    int loop_start = here();
                    compile(body);
                    int jump = here();
                    emit(Op::Jump);
                    int done = here();
                    if (node.lazy) {
                        ins[static_cast<size_t>(split)].x = done;
                        ins[static_cast<size_t>(split)].y = loop_start;
                    } else {
                        ins[static_cast<size_t>(split)].x = loop_start;
                        ins[static_cast<size_t>(split)].y = done;
                    }
                    ins[static_cast<size_t>(jump)].x = split;
                    (void)body_start;
                } else if (node.kind == Node::Opt) {
                    int split = here();
                    emit(Op::Split);
                    int body_start = here();
                    compile(body);
                    int done = here();
                    if (node.lazy) {
                        ins[static_cast<size_t>(split)].x = done;
                        ins[static_cast<size_t>(split)].y = body_start;
                    } else {
                        ins[static_cast<size_t>(split)].x = body_start;
                        ins[static_cast<size_t>(split)].y = done;
                    }
                } else {
                    int split = here();
                    emit(Op::Split);
                    int body_start = here();
                    compile(body);
                    int jump = here();
                    emit(Op::Jump);
                    int done = here();
                    if (node.lazy) {
                        ins[static_cast<size_t>(split)].x = done;
                        ins[static_cast<size_t>(split)].y = body_start;
                    } else {
                        ins[static_cast<size_t>(split)].x = body_start;
                        ins[static_cast<size_t>(split)].y = done;
                    }
                    ins[static_cast<size_t>(jump)].x = split;
                }
                break;
            }
        }
    }
};

struct Compiled {
    std::vector<Ins> ins;
    int group_count = 0;

    // Number of capturing groups (max group index).
    void count_groups(const Node& node) {
        if (node.kind == Node::Group)
            group_count = std::max(group_count, node.group_index);
        for (const Node& child : node.children)
            count_groups(child);
    }
};

bool class_hit(const Ins& i, unsigned char c, bool icase) {
    if ((*i.cls)[c])
        return true;
    if (icase && c >= 'A' && c <= 'Z')
        return (*i.cls)[static_cast<unsigned char>(c - 'A' + 'a')];
    return false;
}

// Recursive backtracking matcher. `arr` holds group start/end positions:
// arr[2*g] = start, arr[2*g+1] = end (or -1 if unset).
bool run(const Compiled& c, size_t pc, size_t pos, const std::string& text, bool icase,
         std::vector<int>& arr, int budget) {
    if (budget <= 0)
        return false;
    for (;;) {
        if (pc >= c.ins.size())
            return false;
        const Ins& in = c.ins[pc];
        switch (in.op) {
            case Op::Char: {
                if (pos >= text.size())
                    return false;
                char t = text[pos];
                if (t != in.ch && !(icase && fold_ascii(t) == fold_ascii(in.ch)))
                    return false;
                ++pos;
                ++pc;
                break;
            }
            case Op::Any: {
                if (pos >= text.size() || text[pos] == '\n')
                    return false;
                ++pos;
                ++pc;
                break;
            }
            case Op::Class: {
                if (pos >= text.size())
                    return false;
                unsigned char b = static_cast<unsigned char>(text[pos]);
                // Python regexes match whole UTF-8 characters. If the class
                // contains a 3-byte sequence lead byte (0xE0-0xEF) *and* both
                // continuation bytes, consume the full sequence at once;
                // otherwise fall back to single-byte matching.
                if (b >= 0xE0 && b <= 0xEF && pos + 2 < text.size()) {
                    unsigned char c1 = static_cast<unsigned char>(text[pos + 1]);
                    unsigned char c2 = static_cast<unsigned char>(text[pos + 2]);
                    if (c1 >= 0x80 && c1 <= 0xBF && c2 >= 0x80 && c2 <= 0xBF &&
                        (*in.cls)[b] && (*in.cls)[c1] && (*in.cls)[c2]) {
                        pos += 3;
                        ++pc;
                        break;
                    }
                }
                if (!class_hit(in, b, icase))
                    return false;
                ++pos;
                ++pc;
                break;
            }
            case Op::Start: {
                if (pos != 0)
                    return false;
                ++pc;
                break;
            }
            case Op::End: {
                if (!(pos == text.size() || (pos + 1 == text.size() && text[pos] == '\n')))
                    return false;
                ++pc;
                break;
            }
            case Op::Save: {
                size_t slot = static_cast<size_t>(2 * in.g + (in.close ? 1 : 0));
                int old = arr[slot];
                arr[slot] = static_cast<int>(pos);
                if (run(c, pc + 1, pos, text, icase, arr, budget - 1))
                    return true;
                arr[slot] = old;
                return false;
            }
            case Op::Split: {
                if (run(c, static_cast<size_t>(in.x), pos, text, icase, arr, budget - 1))
                    return true;
                return run(c, static_cast<size_t>(in.y), pos, text, icase, arr, budget - 1);
            }
            case Op::Jump:
                pc = static_cast<size_t>(in.x);
                break;
            case Op::Match:
                return true;
        }
    }
}

Compiled compile(const std::string& pattern, bool& ok) {
    Compiled c;
    Parser parser(pattern);
    Node ast = parser.parse();
    ok = parser.ok;
    if (!ok)
        return c;
    c.count_groups(ast);
    Compiler cc;
    Ins start_save;
    start_save.op = Op::Save;
    start_save.g = 0;
    start_save.close = false;
    cc.ins.push_back(start_save);
    cc.compile(ast);
    Ins end_save;
    end_save.op = Op::Save;
    end_save.g = 0;
    end_save.close = true;
    cc.ins.push_back(end_save);
    cc.emit(Op::Match);
    c.ins = std::move(cc.ins);
    return c;
}

RegexMatch do_search(const Compiled& c, const std::string& text, bool icase) {
    RegexMatch result;
    for (size_t start = 0; start <= text.size(); ++start) {
        std::vector<int> arr(2 * (c.group_count + 1), -1);
        if (run(c, 0, start, text, icase, arr, 1000000)) {
            result.found = true;
            size_t g0_start = static_cast<size_t>(std::max(0, arr[0]));
            int g0_end_raw = arr[1];
            result.start = g0_start;
            result.end = g0_end_raw < 0 ? text.size() : static_cast<size_t>(g0_end_raw);
            result.groups.push_back(text.substr(result.start, result.end - result.start));
            for (int g = 1; g <= c.group_count; ++g) {
                int s = arr[static_cast<size_t>(2 * g)];
                int e = arr[static_cast<size_t>(2 * g + 1)];
                if (s < 0 || e < 0)
                    result.groups.emplace_back();
                else
                    result.groups.push_back(text.substr(static_cast<size_t>(s),
                                                        static_cast<size_t>(e - s)));
            }
            return result;
        }
        // Optimization: if the pattern is anchored at '^', don't scan further.
        // (ins[0] is a Save for group 0; find the first non-Save instruction.)
        if (start == 0) {
            size_t first = 0;
            while (first < c.ins.size() && c.ins[first].op == Op::Save)
                ++first;
            if (first < c.ins.size() && c.ins[first].op == Op::Start)
                break;
        }
    }
    return result;
}

} // namespace

RegexMatch regex_search(const std::string& pattern, const std::string& text, bool icase) {
    bool ok = false;
    Compiled c = compile(pattern, ok);
    if (!ok)
        return RegexMatch{};
    return do_search(c, text, icase);
}

RegexMatch regex_match(const std::string& pattern, const std::string& text, bool icase) {
    bool ok = false;
    Compiled c = compile(pattern, ok);
    if (!ok)
        return RegexMatch{};
    RegexMatch result;
    std::vector<int> arr(2 * (c.group_count + 1), -1);
    if (run(c, 0, 0, text, icase, arr, 1000000)) {
        result.found = true;
        int e = arr[1];
        result.start = 0;
        result.end = e < 0 ? text.size() : static_cast<size_t>(e);
        result.groups.push_back(text.substr(0, result.end - result.start));
        for (int g = 1; g <= c.group_count; ++g) {
            int s = arr[static_cast<size_t>(2 * g)];
            int en = arr[static_cast<size_t>(2 * g + 1)];
            if (s < 0 || en < 0)
                result.groups.emplace_back();
            else
                result.groups.push_back(text.substr(static_cast<size_t>(s),
                                                    static_cast<size_t>(en - s)));
        }
    }
    return result;
}

std::vector<std::string> regex_findall(const std::string& pattern, const std::string& text,
                                       bool icase) {
    std::vector<std::string> out;
    bool ok = false;
    Compiled c = compile(pattern, ok);
    if (!ok)
        return out;
    size_t from = 0;
    while (from <= text.size()) {
        RegexMatch m = do_search(c, text.substr(from), icase);
        if (!m.found)
            break;
        out.push_back(m.groups[0]);
        size_t consumed = m.end > m.start ? m.end - m.start : 1;
        from += consumed;
    }
    return out;
}

} // namespace bb
