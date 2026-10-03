#include "bb_money.h"

#include "bb_exceptions.h"

#include <stdexcept>

namespace bb {

int64_t decimal_to_cents(const std::string& text) {
    // Python semantics: Decimal(str) then quantize(0.01, ROUND_HALF_UP).
    // Exact digit parsing, never through a binary float. Only the third
    // decimal digit participates in the half-up decision; digits beyond it
    // are ignored (no cascading rounding). Returns a signed cent value;
    // callers enforce the non-negative invariant.
    const std::string& s = text;
    size_t i = 0;
    bool neg = false;
    if (i < s.size() && (s[i] == '-' || s[i] == '+')) {
        neg = s[i] == '-';
        ++i;
    }
    if (i >= s.size())
        throw std::invalid_argument("not a number");
    int64_t int_part = 0;
    bool saw_digit = false;
    while (i < s.size() && s[i] >= '0' && s[i] <= '9') {
        int_part = int_part * 10 + (s[i] - '0');
        saw_digit = true;
        ++i;
    }
    if (!saw_digit)
        throw std::invalid_argument("not a number");
    int64_t frac = 0;      // cents value from the first two fraction digits
    int frac_digits = 0;
    int third_digit = 0;
    if (i < s.size() && s[i] == '.') {
        ++i;
        while (i < s.size() && s[i] >= '0' && s[i] <= '9') {
            char c = s[i++];
            if (frac_digits < 2) {
                frac = frac * 10 + (c - '0');
                ++frac_digits;
            } else if (frac_digits == 2) {
                third_digit = c - '0';
                ++frac_digits;
            }
            // Digits beyond the third decimal are ignored.
        }
        while (frac_digits < 2) {
            frac *= 10;
            ++frac_digits;
        }
    }
    if (i < s.size())
        throw std::invalid_argument("not a number");
    int64_t cents = int_part * 100 + frac;
    if (frac_digits == 3 && third_digit >= 5)
        ++cents;
    return neg ? -cents : cents;
}

std::string cents_to_decimal(int64_t cents) {
    bool neg = cents < 0;
    int64_t v = neg ? -cents : cents;
    char buf[32];
    int n = 0;
    do {
        buf[n++] = static_cast<char>('0' + v % 10);
        v /= 10;
    } while (v > 0);
    std::string out;
    if (neg)
        out.push_back('-');
    for (int i = n - 1; i >= 0; --i)
        out.push_back(buf[i]);
    // Pad to at least three digits ("7" -> "007" -> "0.07") before inserting
    // the decimal point two places from the end.
    while (out.size() < 3)
        out.insert(0, 1, '0');
    out.insert(out.size() - 2, ".");
    return out;
}

Money::Money(const std::string& amount) {
    if (amount.empty())
        throw NegativeMonetaryAmountException("Cannot construct Money from None.");
    int64_t cents;
    try {
        cents = decimal_to_cents(amount);
    } catch (const std::invalid_argument&) {
        throw NegativeMonetaryAmountException(
            "Cannot construct Money from non-numeric value: " + amount);
    }
    if (cents < 0)
        throw NegativeMonetaryAmountException(
            "Cannot construct Money from negative value: " + amount);
    cents_ = cents;
}

Money::Money(int64_t whole_units) : cents_(whole_units * 100) {
    if (whole_units < 0)
        throw NegativeMonetaryAmountException(
            "Cannot construct Money from negative value: " + std::to_string(whole_units));
}

Money Money::from_cents(int64_t cents) {
    if (cents < 0)
        throw NegativeMonetaryAmountException("Cannot construct Money from negative value.");
    return Money(cents, true);
}

Money Money::subtract(const Money& other) const {
    int64_t result = cents_ - other.cents_;
    if (result < 0)
        throw NegativeMonetaryAmountException("Cannot construct Money from negative value.");
    return from_cents(result);
}

Money Money::multiply(const std::string& multiplier) const {
    int64_t multiplier_cents;
    try {
        multiplier_cents = decimal_to_cents(multiplier);
    } catch (const std::invalid_argument&) {
        throw NegativeMonetaryAmountException(
            "Cannot construct Money from non-numeric multiplier: " + multiplier);
    }
    // result = cents_ * (multiplier_cents / 100) with half-up rounding.
    int64_t num = cents_ * multiplier_cents;
    bool neg = num < 0;
    int64_t abs_num = neg ? -num : num;
    int64_t rounded = (abs_num + 50) / 100;
    int64_t result = neg ? -rounded : rounded;
    if (result < 0)
        throw NegativeMonetaryAmountException("Cannot construct Money from negative value.");
    return from_cents(result);
}

Money Money::multiply(int64_t multiplier) const {
    int64_t result = cents_ * multiplier;
    if (result < 0)
        throw NegativeMonetaryAmountException("Cannot construct Money from negative value.");
    return from_cents(result);
}

Money Money::multiply_fraction(int64_t numerator, int64_t denominator) const {
    if (denominator <= 0)
        throw NegativeMonetaryAmountException(
            "Cannot construct Money with non-positive denominator: " +
            std::to_string(denominator));
    int64_t num = cents_ * numerator;
    bool neg = num < 0;
    int64_t abs_num = neg ? -num : num;
    int64_t rounded = (abs_num + denominator / 2) / denominator;
    int64_t result = neg ? -rounded : rounded;
    if (result < 0)
        throw NegativeMonetaryAmountException("Cannot construct Money from negative value.");
    return from_cents(result);
}

} // namespace bb
