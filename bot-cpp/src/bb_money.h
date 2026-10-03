/*
 * bb_money.h - fixed-point cents money value object.
 *
 * Mirrors boombot/casino/shared/value_objects.py: exact decimal arithmetic
 * (no floating point), quantized to cents (2dp) with ROUND_HALF_UP, and a
 * non-negative invariant. Amounts are passed around as decimal strings, the
 * same convention the C wagering service uses.
 */
#ifndef BB_MONEY_H
#define BB_MONEY_H

#include <cstdint>
#include <stdexcept>
#include <string>

namespace bb {

// Parse a decimal string into cents (2dp, ROUND_HALF_UP). Throws
// std::invalid_argument on non-numeric input.
int64_t decimal_to_cents(const std::string& text);

// Format cents as a 2dp decimal string ("100.00").
std::string cents_to_decimal(int64_t cents);

class AggregateVersion {
public:
    explicit AggregateVersion(int64_t number = 0) : number_(number) {
        if (number < 0)
            throw std::invalid_argument("AggregateVersion must be non-negative.");
    }
    int64_t number() const { return number_; }
    AggregateVersion next() const { return AggregateVersion(number_ + 1); }
    bool operator==(const AggregateVersion& other) const { return number_ == other.number_; }
    bool operator!=(const AggregateVersion& other) const { return !(*this == other); }

private:
    int64_t number_;
};

class Money {
public:
    // amount may be a decimal string, an integer (whole currency units), or a
    // raw cent count (via from_cents).
    explicit Money(const std::string& amount);
    explicit Money(int64_t whole_units);

    static Money zero() { return Money(int64_t(0)); }
    static Money from_cents(int64_t cents);

    int64_t cents() const { return cents_; }
    bool is_zero() const { return cents_ == 0; }
    bool is_positive() const { return cents_ > 0; }
    bool is_greater_than_or_equal_to(const Money& other) const { return cents_ >= other.cents_; }
    bool is_less_than(const Money& other) const { return cents_ < other.cents_; }
    bool is_greater_than(const Money& other) const { return cents_ > other.cents_; }

    Money add(const Money& other) const { return from_cents(cents_ + other.cents_); }
    // Throws NegativeMonetaryAmountException if the result would be negative.
    Money subtract(const Money& other) const;
    // multiplier is a decimal string or integer (whole units).
    Money multiply(const std::string& multiplier) const;
    Money multiply(int64_t multiplier) const;
    // Exact ratio multiply (craps fractional payouts): cents * num / den with
    // ROUND_HALF_UP, matching Decimal(amount) * (Decimal(num) / Decimal(den)).
    Money multiply_fraction(int64_t numerator, int64_t denominator) const;

    // Java-style comparator: -1, 0, or 1.
    int compare_to(const Money& other) const {
        if (cents_ < other.cents_)
            return -1;
        if (cents_ > other.cents_)
            return 1;
        return 0;
    }

    std::string formatted() const { return cents_to_decimal(cents_); }
    std::string to_decimal_string() const { return cents_to_decimal(cents_); }

    bool operator==(const Money& other) const { return cents_ == other.cents_; }
    bool operator!=(const Money& other) const { return !(*this == other); }

private:
    explicit Money(int64_t cents, bool) : cents_(cents) {}
    int64_t cents_;
};

} // namespace bb

#endif // BB_MONEY_H
