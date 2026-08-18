#include "bb_money.h"

#include <stdio.h>
#include <string.h>

static int digit_val(char c) {
    return (c >= '0' && c <= '9') ? c - '0' : -1;
}

int bb_money_parse(const char *text, bb_money *out) {
    if (text == NULL || *text == '\0') return 0;
    const char *p = text;
    int negative = 0;
    if (*p == '-') {
        negative = 1;
        p++;
    } else if (*p == '+') {
        p++;
    }
    if (*p == '\0') return 0;

    /* Accrue every digit in scale-10 magnitude, remembering how many digits
       follow the decimal point; convert to cents at the end. */
    long long mag = 0;
    int frac_digits = 0; /* digits seen after the dot (0 = none) */
    int after_dot = 0;
    int seen_digit = 0;

    while (*p != '\0') {
        if (*p == '.') {
            if (after_dot) return 0; /* second dot */
            after_dot = 1;
            p++;
            continue;
        }
        int d = digit_val(*p);
        if (d < 0) return 0;
        seen_digit = 1;
        if (after_dot) {
            if (frac_digits >= 2) return 0; /* quantisation: only 2 decimals */
            frac_digits++;
        }
        if (mag > (BB_MONEY_MAX - d) / 10) return 0; /* overflow */
        mag = mag * 10 + d;
        p++;
    }
    if (!seen_digit) return 0;

    long long cents = mag;
    if (frac_digits == 0) {
        if (mag > BB_MONEY_MAX / BB_MONEY_SCALE) return 0; /* overflow */
        cents = mag * BB_MONEY_SCALE;
    } else if (frac_digits == 1) {
        if (mag > BB_MONEY_MAX / 10) return 0; /* overflow */
        cents = mag * 10;
    }
    /* frac_digits == 2: mag already holds cents */
    if (negative) cents = -cents;
    *out = cents;
    return 1;
}

void bb_money_fmt(bb_money value, char *out) {
    int neg = value < 0;
    unsigned long long mag = neg ? (unsigned long long) (-(value + 1)) + 1 : (unsigned long long) value;
    snprintf(out, 32, "%s%llu.%02llu", neg ? "-" : "",
             mag / 100, mag % 100);
}

int bb_money_format(bb_money value, char *out, size_t out_size) {
    char tmp[32];
    bb_money_fmt(value, tmp);
    size_t n = strlen(tmp);
    if (out_size <= n) return -1;
    memcpy(out, tmp, n + 1);
    return (int) n;
}

int bb_money_add(bb_money a, bb_money b, bb_money *out) {
    if ((b > 0 && a > BB_MONEY_MAX - b) || (b < 0 && a < -BB_MONEY_MAX - b)) {
        return 0;
    }
    *out = a + b;
    return 1;
}

/* Money is non-negative in the domain model: subtracting below zero fails. */
int bb_money_sub(bb_money a, bb_money b, bb_money *out) {
    if ((b < 0 && a > BB_MONEY_MAX + b) || (b > 0 && a < b)) {
        return 0;
    }
    *out = a - b;
    return 1;
}

int bb_money_scale(bb_money a, long long factor, bb_money *out) {
    if (factor == 0) {
        *out = 0;
        return 1;
    }
    long long mag = factor < 0 ? -factor : factor;
    long long absa = a < 0 ? -a : a; /* a is bounded by BB_MONEY_MAX, never INT64_MIN */
    if (mag != 0 && absa > BB_MONEY_MAX / mag) {
        return 0;
    }
    *out = a * (factor < 0 ? -mag : mag);
    return 1;
}