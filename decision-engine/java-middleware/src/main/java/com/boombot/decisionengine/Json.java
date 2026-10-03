package com.boombot.decisionengine;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal, dependency-free JSON support.
 *
 * <p>The Java middleware deliberately avoids a JSON library so the whole
 * decision engine can be built offline with a bare {@code javac} plus the
 * Rust toolchain. This class is intentionally small: it parses exactly the
 * subset of JSON used by the decision protocol (objects, arrays, strings,
 * numbers, booleans, null) and serialises the same subset back.</p>
 */
final class Json {

    private Json() {
    }

    /** Parse a JSON document into Java values (Map / List / String / Long / Double / Boolean / null). */
    static Object parse(String text) {
        Parser parser = new Parser(text);
        Object value = parser.parseValue();
        parser.skipWhitespace();
        if (!parser.atEnd()) {
            throw new IllegalArgumentException("Trailing content after JSON document");
        }
        return value;
    }

    /** Serialise a Java value (Map / List / String / Number / Boolean / null) into JSON text. */
    static String stringify(Object value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof String) {
            return quote((String) value);
        }
        if (value instanceof Boolean || value instanceof Number) {
            return String.valueOf(value);
        }
        if (value instanceof Map) {
            StringBuilder out = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                out.append(quote(String.valueOf(entry.getKey()))).append(':');
                out.append(stringify(entry.getValue()));
            }
            return out.append('}').toString();
        }
        if (value instanceof List) {
            StringBuilder out = new StringBuilder("[");
            boolean first = true;
            for (Object item : (List<?>) value) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                out.append(stringify(item));
            }
            return out.append(']').toString();
        }
        return quote(String.valueOf(value));
    }

    private static String quote(String raw) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.append('"').toString();
    }
}

/** Recursive-descent parser over a single JSON document (package-private). */
final class Parser {
    private final String text;
    private int pos;

    Parser(String text) {
        this.text = text;
    }

    boolean atEnd() {
        return pos >= text.length();
    }

    void skipWhitespace() {
        while (pos < text.length() && Character.isWhitespace(text.charAt(pos))) {
            pos++;
        }
    }

    char peek() {
        if (atEnd()) {
            throw new IllegalArgumentException("Unexpected end of JSON");
        }
        return text.charAt(pos);
    }

    void expect(char expected) {
        if (atEnd() || text.charAt(pos) != expected) {
            throw new IllegalArgumentException("Expected '" + expected + "' at position " + pos);
        }
        pos++;
    }

    Object parseValue() {
        skipWhitespace();
        char c = peek();
        switch (c) {
            case '{' -> {
                return parseObject();
            }
            case '[' -> {
                return parseArray();
            }
            case '"' -> {
                return parseString();
            }
            case 't' -> {
                expectLiteral("true");
                return Boolean.TRUE;
            }
            case 'f' -> {
                expectLiteral("false");
                return Boolean.FALSE;
            }
            case 'n' -> {
                expectLiteral("null");
                return null;
            }
            default -> {
                if (c == '-' || (c >= '0' && c <= '9')) {
                    return parseNumber();
                }
                throw new IllegalArgumentException("Unexpected character '" + c + "' at position " + pos);
            }
        }
    }

    private void expectLiteral(String literal) {
        for (int i = 0; i < literal.length(); i++) {
            expect(literal.charAt(i));
        }
    }

    private Map<String, Object> parseObject() {
        expect('{');
        skipWhitespace();
        Map<String, Object> object = new LinkedHashMap<>();
        if (peek() == '}') {
            pos++;
            return object;
        }
        while (true) {
            skipWhitespace();
            String key = parseString();
            skipWhitespace();
            expect(':');
            object.put(key, parseValue());
            skipWhitespace();
            char c = peek();
            if (c == '}') {
                pos++;
                return object;
            }
            expect(',');
        }
    }



    private List<Object> parseArray() {
        expect('[');
        skipWhitespace();
        List<Object> list = new ArrayList<>();
        if (peek() == ']') {
            pos++;
            return list;
        }
        while (true) {
            list.add(parseValue());
            skipWhitespace();
            char c = peek();
            if (c == ']') {
                pos++;
                return list;
            }
            expect(',');
        }
    }

    private String parseString() {
        expect('"');
        StringBuilder out = new StringBuilder();
        while (true) {
            if (atEnd()) {
                throw new IllegalArgumentException("Unterminated string");
            }
            char c = text.charAt(pos++);
            if (c == '"') {
                return out.toString();
            }
            if (c != '\\') {
                out.append(c);
                continue;
            }
            if (atEnd()) {
                throw new IllegalArgumentException("Unterminated escape sequence");
            }
            char escape = text.charAt(pos++);
            switch (escape) {
                case '"' -> out.append('"');
                case '\\' -> out.append('\\');
                case '/' -> out.append('/');
                case 'b' -> out.append('\b');
                case 'f' -> out.append('\f');
                case 'n' -> out.append('\n');
                case 'r' -> out.append('\r');
                case 't' -> out.append('\t');
                case 'u' -> {
                    if (pos + 4 > text.length()) {
                        throw new IllegalArgumentException("Truncated unicode escape");
                    }
                    String hex = text.substring(pos, pos + 4);
                    out.append((char) Integer.parseInt(hex, 16));
                    pos += 4;
                }
                default -> throw new IllegalArgumentException("Unknown escape '\\" + escape + "'");
            }
        }
    }

    private Object parseNumber() {
        int start = pos;
        if (peek() == '-') {
            pos++;
        }
        while (pos < text.length() && Character.isDigit(text.charAt(pos))) {
            pos++;
        }
        boolean isDouble = false;
        if (pos < text.length() && text.charAt(pos) == '.') {
            isDouble = true;
            pos++;
            while (pos < text.length() && Character.isDigit(text.charAt(pos))) {
                pos++;
            }
        }
        if (pos < text.length() && (text.charAt(pos) == 'e' || text.charAt(pos) == 'E')) {
            isDouble = true;
            pos++;
            if (pos < text.length() && (text.charAt(pos) == '+' || text.charAt(pos) == '-')) {
                pos++;
            }
            while (pos < text.length() && Character.isDigit(text.charAt(pos))) {
                pos++;
            }
        }
        String raw = text.substring(start, pos);
        if (isDouble) {
            return Double.valueOf(raw);
        }
        try {
            return Long.valueOf(raw);
        } catch (NumberFormatException ex) {
            return Double.valueOf(raw);
        }
    }
}
