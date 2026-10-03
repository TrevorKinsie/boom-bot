#ifndef BB_JSON_H
#define BB_JSON_H

#include <stddef.h>
#include <stdint.h>

#include "bb_util.h"

/*
 * bb_json: minimal dependency-free JSON support, the C port of the JVM
 * decision engine's Json.java. Parses exactly the subset used by the
 * wagering protocol (objects, arrays, strings, numbers, booleans, null)
 * and serialises the same subset back.
 */

typedef enum {
    BB_JNULL,
    BB_JBOOL,
    BB_JINT,
    BB_JDOUBLE,
    BB_JSTRING,
    BB_JARRAY,
    BB_JOBJECT
} bb_jtype;

typedef struct bb_jval bb_jval;
typedef struct bb_jpair bb_jpair;

struct bb_jpair {
    char *key;
    bb_jval *val;
};

struct bb_jval {
    bb_jtype type;
    union {
        int b;              /* bool */
        long long i;        /* int (64-bit) */
        double d;           /* double */
        char *s;            /* string, owned */
        struct {
            bb_jval **items;
            size_t n;
        } arr;
        struct {
            bb_jpair *items;
            size_t n;
        } obj;
    } u;
};

/* Parse a JSON document into a DOM tree; NULL on malformed input. */
bb_jval *bb_json_parse(const char *text);
/* Parse the same, reporting an error string in err[0..errcap) on failure. */
bb_jval *bb_json_parse_err(const char *text, char *err, size_t errcap);
void bb_json_free(bb_jval *v);

/* Constructors (all take ownership of their arguments). */
bb_jval *bb_json_null(void);
bb_jval *bb_json_bool(int b);
bb_jval *bb_json_int(long long i);
bb_jval *bb_json_double(double d);
bb_jval *bb_json_str(const char *s);
bb_jval *bb_json_object(void);
bb_jval *bb_json_array(void);

/* Object / array mutation (container takes ownership of `val`). */
void bb_json_put(bb_jval *object, const char *key, bb_jval *val);
void bb_json_append(bb_jval *array, bb_jval *val);

/* Accessors (non-mutating, null-safe). */
bb_jval *bb_json_get(const bb_jval *object, const char *key);
bb_jval *bb_json_get_path(const bb_jval *object, const char *k1, const char *k2);
const char *bb_json_strval(const bb_jval *v, const char *fallback);
long long bb_json_intval(const bb_jval *v, long long fallback);
int bb_json_boolval(const bb_jval *v, int fallback);

/* Serialise into a growable buffer (no trailing NUL) or a malloc'd string. */
void bb_json_serialize(const bb_jval *v, bb_buf *out);
char *bb_json_to_string(const bb_jval *v); /* caller frees */

#endif /* BB_JSON_H */