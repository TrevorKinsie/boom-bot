package com.boombot.mmo;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A tiny, dependency-free JSON model: parser + writer.
 *
 * The model uses native Java values: {@link Map}&lt;String,Object&gt;,
 * {@link List}&lt;Object&gt;, {@link String}, {@link Long}, {@link Double},
 * {@link Boolean}, and {@code null}. Integers parse to {@link Long}, other
 * numbers to {@link Double}.
 *
 * <p>This is not a full RFC 8259 implementation but it is lossless and correct
 * for the payloads this service handles, including the Python event-store
 * schema it must stay byte-compatible with.
 */
public final class Json {

    private Json() {}

    // ------------------------------------------------------------------
    // Parsing
    // ------------------------------------------------------------------

    public static Object parse(String text) {
        return new Parser(text).parse();
    }

    private static final class Parser {
        private final String s;
        private int i;

        Parser(String s) {
            this.s = s;
        }

        Object parse() {
            skipWs();
            Object value = value();
            skipWs();
            if (i < s.length()) {
                throw new IllegalArgumentException("Trailing JSON content at char " + i);
            }
            return value;
        }

        private Object value() {
            skipWs();
            if (i >= s.length()) {
                throw new IllegalArgumentException("Unexpected end of JSON");
            }
            char c = s.charAt(i);
            switch (c) {
                case '{': return object();
                case '[': return array();
                case '"': return string();
                case 't': expect("true"); return Boolean.TRUE;
                case 'f': expect("false"); return Boolean.FALSE;
                case 'n': expect("null"); return null;
                default: return number();
            }
        }

        private Map<String, Object> object() {
            expectChar('{');
            Map<String, Object> map = new LinkedHashMap<>();
            skipWs();
            if (peek() == '}') {
                i++;
                return map;
            }
            while (true) {
                skipWs();
                String key = string();
                skipWs();
                expectChar(':');
                map.put(key, value());
                skipWs();
                char c = peek();
                if (c == ',') {
                    i++;
                } else if (c == '}') {
                    i++;
                    return map;
                } else {
                    throw new IllegalArgumentException("Expected ',' or '}' at char " + i);
                }
            }
        }

        private List<Object> array() {
            expectChar('[');
            List<Object> list = new ArrayList<>();
            skipWs();
            if (peek() == ']') {
                i++;
                return list;
            }
            while (true) {
                list.add(value());
                skipWs();
                char c = peek();
                if (c == ',') {
                    i++;
                } else if (c == ']') {
                    i++;
                    return list;
                } else {
                    throw new IllegalArgumentException("Expected ',' or ']' at char " + i);
                }
            }
        }
private String string() {
            expectChar('"');
            StringBuilder out = new StringBuilder();
            while (i < s.length()) {
                char c = s.charAt(i++);
                if (c == '"') {
                    return out.toString();
                }
                if (c != '\\') {
                    out.append(c);
                    continue;
                }
                if (i >= s.length()) {
                    throw new IllegalArgumentException("Unterminated escape");
                }
                char e = s.charAt(i++);
                switch (e) {
                    case '"': out.append('"'); break;
                    case '\\': out.append('\\'); break;
                    case '/': out.append('/'); break;
                    case 'b': out.append('\b'); break;
                    case 'n': out.append('\n'); break;
                    case 'r': out.append('\r'); break;
                    case 't': out.append('\t'); break;
                    case 'f': out.append('\f'); break;
                    case 'u': out.append(unicode()); break;
                    default: throw new IllegalArgumentException("Bad escape \\" + e);
                }
            }
            throw new IllegalArgumentException("Unterminated string");
        }

        private char unicode() {
            if (i + 4 > s.length()) {
                throw new IllegalArgumentException("Bad unicode escape");
            }
            int cp = Integer.parseInt(s.substring(i, i + 4), 16);
            i += 4;
            return (char) cp;
        }

        private Object number() {
            int start = i;
            while (i < s.length()) {
                char c = s.charAt(i);
                if (c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E'
                        || Character.isDigit(c)) {
                    i++;
                } else {
                    break;
                }
            }
            String token = s.substring(start, i);
            if (token.isEmpty()) {
                throw new IllegalArgumentException("Expected value at char " + i);
            }
            if (token.indexOf('.') >= 0 || token.indexOf('e') >= 0 || token.indexOf('E') >= 0) {
                return Double.parseDouble(token);
            }
            return Long.parseLong(token);
        }

        private char peek() {
            if (i >= s.length()) {
                throw new IllegalArgumentException("Unexpected end of JSON");
            }
            return s.charAt(i);
        }
private void expectChar(char c) {
            skipWs();
            if (i >= s.length() || s.charAt(i) != c) {
                throw new IllegalArgumentException("Expected '" + c + "' at char " + i);
            }
            i++;
        }

        private void expect(String lit) {
            if (!s.startsWith(lit, i)) {
                throw new IllegalArgumentException("Expected " + lit + " at char " + i);
            }
            i += lit.length();
        }

        private void skipWs() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
                i++;
            }
        }
    }

    // ------------------------------------------------------------------
    // Writing
    // ------------------------------------------------------------------

    public static String write(Object value) {
        StringBuilder out = new StringBuilder();
        writeValue(out, value);
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    private static void writeValue(StringBuilder out, Object value) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof String str) {
            writeString(out, str);
        } else if (value instanceof Boolean b) {
            out.append(b.booleanValue() ? "true" : "false");
        } else if (value instanceof Double d) {
            writeNumber(out, d.doubleValue());
        } else if (value instanceof Float f) {
            writeNumber(out, f.doubleValue());
        } else if (value instanceof Number n) {
            out.append(n.toString());
        } else if (value instanceof Map) {
            Map<Object, Object> map = (Map<Object, Object>) value;
            out.append('{');
            boolean first = true;
            for (Map.Entry<Object, Object> e : map.entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeString(out, String.valueOf(e.getKey()));
                out.append(':');
                writeValue(out, e.getValue());
            }
            out.append('}');
        } else if (value instanceof Iterable) {
            out.append('[');
            boolean first = true;
            for (Object item : (Iterable<Object>) value) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeValue(out, item);
            }
            out.append(']');
        } else {
            throw new IllegalArgumentException("Cannot serialize: " + value.getClass());
        }
    }
private static void writeNumber(StringBuilder out, double d) {
        if (d == Math.rint(d) && !Double.isInfinite(d) && Math.abs(d) < 1e15) {
            out.append((long) d);
        } else {
            out.append(Double.toString(d));
        }
    }

    private static void writeString(StringBuilder out, String s) {
        out.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                case '\b': out.append("\\b"); break;
                case '\f': out.append("\\f"); break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        out.append('"');
    }
}