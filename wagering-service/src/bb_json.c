#include "bb_json.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------- DOM --- */

bb_jval *bb_json_null(void) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JNULL;
    return v;
}

bb_jval *bb_json_bool(int b) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JBOOL;
    v->u.b = b;
    return v;
}

bb_jval *bb_json_int(long long i) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JINT;
    v->u.i = i;
    return v;
}

bb_jval *bb_json_double(double d) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JDOUBLE;
    v->u.d = d;
    return v;
}

bb_jval *bb_json_str(const char *s) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JSTRING;
    v->u.s = strdup(s);
    return v;
}

/* Parse path: wrap a string the parser already owns (no second copy). */
static bb_jval *bb_json_take_str(char *owned) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    if (v == NULL) {
        free(owned);
        return NULL;
    }
    v->type = BB_JSTRING;
    v->u.s = owned;
    return v;
}

bb_jval *bb_json_object(void) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JOBJECT;
    return v;
}

bb_jval *bb_json_array(void) {
    bb_jval *v = (bb_jval *) calloc(1, sizeof(bb_jval));
    v->type = BB_JARRAY;
    return v;
}

void bb_json_free(bb_jval *v) {
    if (v == NULL) return;
    if (v->type == BB_JSTRING) {
        free(v->u.s);
    } else if (v->type == BB_JARRAY) {
        for (size_t i = 0; i < v->u.arr.n; i++) bb_json_free(v->u.arr.items[i]);
        free(v->u.arr.items);
    } else if (v->type == BB_JOBJECT) {
        for (size_t i = 0; i < v->u.obj.n; i++) {
            free(v->u.obj.items[i].key);
            bb_json_free(v->u.obj.items[i].val);
        }
        free(v->u.obj.items);
    }
    free(v);
}

void bb_json_put(bb_jval *object, const char *key, bb_jval *val) {
    for (size_t i = 0; i < object->u.obj.n; i++) {
        if (strcmp(object->u.obj.items[i].key, key) == 0) {
            bb_json_free(object->u.obj.items[i].val);
            object->u.obj.items[i].val = val;
            return;
        }
    }
    object->u.obj.items = (bb_jpair *) realloc(
            object->u.obj.items, (object->u.obj.n + 1) * sizeof(bb_jpair));
    object->u.obj.items[object->u.obj.n].key = strdup(key);
    object->u.obj.items[object->u.obj.n].val = val;
    object->u.obj.n++;
}

void bb_json_append(bb_jval *array, bb_jval *val) {
    array->u.arr.items = (bb_jval **) realloc(
            array->u.arr.items, (array->u.arr.n + 1) * sizeof(bb_jval *));
    array->u.arr.items[array->u.arr.n++] = val;
}

bb_jval *bb_json_get(const bb_jval *object, const char *key) {
    if (object == NULL || object->type != BB_JOBJECT) return NULL;
    for (size_t i = 0; i < object->u.obj.n; i++) {
        if (strcmp(object->u.obj.items[i].key, key) == 0) {
            return object->u.obj.items[i].val;
        }
    }
    return NULL;
}

bb_jval *bb_json_get_path(const bb_jval *object, const char *k1, const char *k2) {
    return bb_json_get(bb_json_get(object, k1), k2);
}

const char *bb_json_strval(const bb_jval *v, const char *fallback) {
    return (v != NULL && v->type == BB_JSTRING) ? v->u.s : fallback;
}

long long bb_json_intval(const bb_jval *v, long long fallback) {
    if (v == NULL) return fallback;
    if (v->type == BB_JINT) return v->u.i;
    if (v->type == BB_JDOUBLE) return (long long) v->u.d;
    return fallback;
}

int bb_json_boolval(const bb_jval *v, int fallback) {
    return (v != NULL && v->type == BB_JBOOL) ? v->u.b : fallback;
}

/* ------------------------------------------------------------ parser --- */

typedef struct {
    const char *text;
    size_t pos;
    char err[128];
} bb_parser;

static void bb_p_skip_ws(bb_parser *p) {
    while (p->text[p->pos] != '\0' && (unsigned char) p->text[p->pos] <= ' ') {
        p->pos++;
    }
}

static int bb_p_expect(bb_parser *p, char expected) {
    if (p->text[p->pos] != expected) {
        snprintf(p->err, sizeof(p->err), "expected '%c' at position %zu", expected, p->pos);
        return 0;
    }
    p->pos++;
    return 1;
}

static int bb_p_literal(bb_parser *p, const char *lit) {
    size_t n = strlen(lit);
    if (strncmp(p->text + p->pos, lit, n) != 0) {
        snprintf(p->err, sizeof(p->err), "expected literal '%s' at position %zu", lit, p->pos);
        return 0;
    }
    p->pos += n;
    return 1;
}

static char *bb_p_string(bb_parser *p) {
    if (!bb_p_expect(p, '"')) return NULL;
    bb_buf out;
    bb_buf_init(&out);
    while (p->text[p->pos] != '\0') {
        char c = p->text[p->pos++];
        if (c == '"') {
            bb_buf_push_c(&out, '\0');
            char *result = (char *) out.data;
            return result;
        }
        if (c != '\\') {
            bb_buf_push_c(&out, c);
            continue;
        }
        char esc = p->text[p->pos++];
        switch (esc) {
            case '"': bb_buf_push_c(&out, '"'); break;
            case '\\': bb_buf_push_c(&out, '\\'); break;
            case '/': bb_buf_push_c(&out, '/'); break;
            case 'b': bb_buf_push_c(&out, '\b'); break;
            case 'f': bb_buf_push_c(&out, '\f'); break;
            case 'n': bb_buf_push_c(&out, '\n'); break;
            case 'r': bb_buf_push_c(&out, '\r'); break;
            case 't': bb_buf_push_c(&out, '\t'); break;
            case 'u': {
                if (p->pos + 4 > strlen(p->text)) {
                    snprintf(p->err, sizeof(p->err), "truncated unicode escape");
                    bb_buf_free(&out);
                    return NULL;
                }
                char hex[5] = {p->text[p->pos], p->text[p->pos + 1],
                               p->text[p->pos + 2], p->text[p->pos + 3], '\0'};
                p->pos += 4;
                char *end = NULL;
                long cp = strtol(hex, &end, 16);
                bb_buf_push_c(&out, (char) cp);
                break;
            }
            default:
                snprintf(p->err, sizeof(p->err), "unknown escape '\\%c'", esc);
                bb_buf_free(&out);
                return NULL;
        }
    }
    snprintf(p->err, sizeof(p->err), "unterminated string");
    bb_buf_free(&out);
    return NULL;
}

static bb_jval *bb_p_number(bb_parser *p) {
    size_t start = p->pos;
    char c = p->text[p->pos];
    if (c == '-') {
        p->pos++;
        if (p->text[p->pos] < '0' || p->text[p->pos] > '9') {
            snprintf(p->err, sizeof(p->err), "malformed number at position %zu", start);
            return NULL;
        }
    }
    int is_double = 0;
    while (p->text[p->pos] >= '0' && p->text[p->pos] <= '9') p->pos++;
    if (p->text[p->pos] == '.') {
        is_double = 1;
        p->pos++;
        while (p->text[p->pos] >= '0' && p->text[p->pos] <= '9') p->pos++;
    }
    if (p->text[p->pos] == 'e' || p->text[p->pos] == 'E') {
        is_double = 1;
        p->pos++;
        if (p->text[p->pos] == '+' || p->text[p->pos] == '-') p->pos++;
        while (p->text[p->pos] >= '0' && p->text[p->pos] <= '9') p->pos++;
    }
    char *raw = strndup(p->text + start, p->pos - start);
    bb_jval *v;
    if (is_double) {
        v = bb_json_double(strtod(raw, NULL));
    } else {
        char *end = NULL;
        long long parsed = strtoll(raw, &end, 10);
        if (end == raw || *end != '\0') {
            v = bb_json_double(strtod(raw, NULL));
        } else {
            v = bb_json_int(parsed);
        }
    }
    free(raw);
    return v;
}

static bb_jval *bb_p_value(bb_parser *p);

static bb_jval *bb_p_object(bb_parser *p) {
    if (!bb_p_expect(p, '{')) return NULL;
    bb_jval *obj = bb_json_object();
    bb_p_skip_ws(p);
    if (p->text[p->pos] == '}') {
        p->pos++;
        return obj;
    }
    while (1) {
        bb_p_skip_ws(p);
        char *key = bb_p_string(p);
        if (key == NULL) {
            bb_json_free(obj);
            return NULL;
        }
        bb_p_skip_ws(p);
        if (!bb_p_expect(p, ':')) {
            free(key);
            bb_json_free(obj);
            return NULL;
        }
        bb_p_skip_ws(p);
        bb_jval *val = bb_p_value(p);
        if (val == NULL) {
            free(key);
            bb_json_free(obj);
            return NULL;
        }
        bb_json_put(obj, key, val);
        free(key);
        bb_p_skip_ws(p);
        char c = p->text[p->pos];
        if (c == '}') {
            p->pos++;
            return obj;
        }
        if (!bb_p_expect(p, ',')) {
            bb_json_free(obj);
            return NULL;
        }
    }
}

static bb_jval *bb_p_array(bb_parser *p) {
    if (!bb_p_expect(p, '[')) return NULL;
    bb_jval *arr = bb_json_array();
    bb_p_skip_ws(p);
    if (p->text[p->pos] == ']') {
        p->pos++;
        return arr;
    }
    while (1) {
        bb_p_skip_ws(p);
        bb_jval *val = bb_p_value(p);
        if (val == NULL) {
            bb_json_free(arr);
            return NULL;
        }
        bb_json_append(arr, val);
        bb_p_skip_ws(p);
        char c = p->text[p->pos];
        if (c == ']') {
            p->pos++;
            return arr;
        }
        if (!bb_p_expect(p, ',')) {
            bb_json_free(arr);
            return NULL;
        }
    }
}

static bb_jval *bb_p_value(bb_parser *p) {
    bb_p_skip_ws(p);
    if (p->text[p->pos] == '\0') {
        snprintf(p->err, sizeof(p->err), "unexpected end of input");
        return NULL;
    }
    char c = p->text[p->pos];
    switch (c) {
        case '{': return bb_p_object(p);
        case '[': return bb_p_array(p);
        case '"': {
            char *s = bb_p_string(p);
            return s == NULL ? NULL : bb_json_take_str(s);
        }
        case 't': return bb_p_literal(p, "true") ? bb_json_bool(1) : NULL;
        case 'f': return bb_p_literal(p, "false") ? bb_json_bool(0) : NULL;
        case 'n': return bb_p_literal(p, "null") ? bb_json_null() : NULL;
        default:
            if (c == '-' || (c >= '0' && c <= '9')) return bb_p_number(p);
            snprintf(p->err, sizeof(p->err), "unexpected character '%c' at position %zu",
                     c, p->pos);
            return NULL;
    }
}

bb_jval *bb_json_parse_err(const char *text, char *err, size_t errcap) {
    bb_parser p = {text, 0, {0}};
    bb_p_skip_ws(&p);
    bb_jval *v = bb_p_value(&p);
    if (v == NULL) {
        if (errcap > 0 && err != NULL) {
            snprintf(err, errcap, "%s", p.err[0] ? p.err : "parse error");
        }
        return NULL;
    }
    bb_p_skip_ws(&p);
    if (p.text[p.pos] != '\0') {
        bb_json_free(v);
        if (errcap > 0 && err != NULL) {
            snprintf(err, errcap, "trailing content after JSON document");
        }
        return NULL;
    }
    return v;
}

bb_jval *bb_json_parse(const char *text) {
    return bb_json_parse_err(text, NULL, 0);
}

/* --------------------------------------------------------- serializer --- */

static void bb_s_string(bb_buf *out, const char *raw) {
    bb_buf_push_c(out, '"');
    for (const char *it = raw; *it != '\0'; it++) {
        unsigned char c = (unsigned char) *it;
        switch (c) {
            case '"': bb_buf_push_str(out, "\\\""); break;
            case '\\': bb_buf_push_str(out, "\\\\"); break;
            case '\b': bb_buf_push_str(out, "\\b"); break;
            case '\f': bb_buf_push_str(out, "\\f"); break;
            case '\n': bb_buf_push_str(out, "\\n"); break;
            case '\r': bb_buf_push_str(out, "\\r"); break;
            case '\t': bb_buf_push_str(out, "\\t"); break;
            default:
                if (c < 0x20) {
                    char esc[16];
                    snprintf(esc, sizeof(esc), "\\u%04x", c);
                    bb_buf_push_str(out, esc);
                } else {
                    bb_buf_push_c(out, (char) c);
                }
        }
    }
    bb_buf_push_c(out, '"');
}

static void bb_s_value(const bb_jval *v, bb_buf *out);

static void bb_s_object(const bb_jval *obj, bb_buf *out) {
    bb_buf_push_c(out, '{');
    for (size_t i = 0; i < obj->u.obj.n; i++) {
        if (i > 0) bb_buf_push_c(out, ',');
        bb_s_string(out, obj->u.obj.items[i].key);
        bb_buf_push_c(out, ':');
        bb_s_value(obj->u.obj.items[i].val, out);
    }
    bb_buf_push_c(out, '}');
}

static void bb_s_array(const bb_jval *arr, bb_buf *out) {
    bb_buf_push_c(out, '[');
    for (size_t i = 0; i < arr->u.arr.n; i++) {
        if (i > 0) bb_buf_push_c(out, ',');
        bb_s_value(arr->u.arr.items[i], out);
    }
    bb_buf_push_c(out, ']');
}

static void bb_s_value(const bb_jval *v, bb_buf *out) {
    switch (v->type) {
        case BB_JNULL: bb_buf_push_str(out, "null"); break;
        case BB_JBOOL: bb_buf_push_str(out, v->u.b ? "true" : "false"); break;
        case BB_JINT: {
            char tmp[40];
            snprintf(tmp, sizeof(tmp), "%" PRId64, (int64_t) v->u.i);
            bb_buf_push_str(out, tmp);
            break;
        }
        case BB_JDOUBLE: {
            char tmp[64];
            snprintf(tmp, sizeof(tmp), "%.17g", v->u.d);
            bb_buf_push_str(out, tmp);
            break;
        }
        case BB_JSTRING: bb_s_string(out, v->u.s); break;
        case BB_JARRAY: bb_s_array(v, out); break;
        case BB_JOBJECT: bb_s_object(v, out); break;
    }
}

void bb_json_serialize(const bb_jval *v, bb_buf *out) {
    bb_s_value(v, out);
}

char *bb_json_to_string(const bb_jval *v) {
    bb_buf out;
    bb_buf_init(&out);
    bb_json_serialize(v, &out);
    bb_buf_push_c(&out, '\0');
    return (char *) out.data;
}