#ifndef BB_MONEY_H
#define BB_MONEY_H

#include <stddef.h>
#include <stdint.h>

/*
 * bb_money: fixed-point money for the wagering service.
 *
 * The Python platform quantises Money to CASINO_CURRENCY_QUANTIZATION=0.01
 * (2 decimal places). The C port keeps the same semantics with a 64-bit
 * integer of cents: exact decimal arithmetic, non-negative balances, and
 * explicit overflow checks on every operation. The usable range is
 * +/- ~92.2 * 10^15 units, far beyond any wallet in the system.
 */

#define BB_MONEY_SCALE 100LL        /* 2 decimal places */
#define BB_MONEY_MAX ((int64_t) 0x3FFFFFFFFFFFFFFFLL) /* ~4.6e18 cents */

typedef int64_t bb_money;

/* Parse a decimal string ("10", "10.5", "10.50", "-0.01") into cents. */
int bb_money_parse(const char *text, bb_money *out); /* 1 ok, 0 invalid/overflow */
/* Format cents into a caller buffer ("10.50"); returns the length. */
int bb_money_format(bb_money value, char *out, size_t out_size);
void bb_money_fmt(bb_money value, char *out /* 32 bytes */);

int bb_money_add(bb_money a, bb_money b, bb_money *out); /* 0 on overflow */
int bb_money_sub(bb_money a, bb_money b, bb_money *out); /* 0 on underflow/overflow */
int bb_money_scale(bb_money a, long long factor, bb_money *out); /* multiply */

#endif /* BB_MONEY_H */