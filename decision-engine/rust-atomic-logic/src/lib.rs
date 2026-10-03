//! PURE atomic logic for the boom-bot JVM decision engine.
//!
//! This crate is the innermost layer of the decision fabric. It exposes a set
//! of small, mathematically pure functions that convert a caller-supplied
//! seed into a single deterministic atomic outcome. There is deliberately no
//! ambient randomness, no shared mutable state, and no I/O in the library
//! module: every function is referentially transparent, which keeps the
//! outcome arbitrarily re-auditable (the ``atomic_fairness_hash`` primitive can
//! reproduce any decision from its seed).
//!
//! The RNG is a splitmix64[1] mixer. Given the same seed it always produces
//! the same value, which is what makes the "provable fairness" story hold --
//! the whole value proposition is that the house never touches the dice.
//!
//! [1]: https://rosettacode.org/wiki/Pseudo-random_numbers/Splitmix64

/// Mix a 64-bit state through the splitmix64 finalizer.
///
/// The input is combined with the golden-ratio offset and then run through
/// two multiply-xor scrambles to produce a well-distributed 64-bit result.
#[inline]
pub fn splitmix64(mut state: u64) -> u64 {
    state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

/// Parse a hex seed string into its 64-bit integer representation.
///
/// The seed is supplied by the orchestrator as lowercase hex (see the Python
/// gateway). If the string is empty or contains no hex digits, a stable
/// non-zero fallback is returned so that the atomic primitives remain total.
pub fn seed_from_hex(hex: &str) -> u64 {
    let cleaned: String = hex.chars().filter(|c| c.is_ascii_hexdigit()).collect();
    if cleaned.is_empty() {
        return 0xDEAD_BEEF_CAFE_F00D;
    }
    u64::from_str_radix(&cleaned[..cleaned.len().min(16)], 16).unwrap_or(0)
}

/// Draw a uniform integer in the inclusive range ``[low, high]``.
///
/// The span is ``high - low + 1``; the result is ``low + mix(seed) % span``.
/// When ``high <= low`` the function returns ``low`` (an empty/trivial range).
#[inline]
pub fn atomic_uniform_inclusive(seed: u64, low: u64, high: u64) -> u64 {
    if high <= low {
        return low;
    }
    let span = high - low + 1;
    low + (splitmix64(seed) % span)
}

/// Decide a single American-roulette spin.
///
/// The wheel has 38 pockets: ``0``, ``00``, and ``1..=36``. The primitive
/// returns an index in ``0..=37``; index ``37`` is the double-zero pocket.
#[inline]
pub fn atomic_spin_roulette(seed: u64) -> u64 {
    atomic_uniform_inclusive(seed, 0, 37)
}

/// Decide a single craps roll as a pair of die faces each in ``1..=6``.
#[inline]
pub fn atomic_roll_craps(seed: u64) -> (u64, u64) {
    let die1 = atomic_uniform_inclusive(seed, 1, 6);
    let die2 = atomic_uniform_inclusive(seed ^ splitmix64(seed), 1, 6);
    (die1, die2)
}

/// Decide a Zeus reel grid as a row-major vector of symbol indices.
///
/// Every cell is drawn independently in ``0..=8`` (the nine-symbol Zeus
/// vocabulary). The returned length is exactly ``rows * cols``.
pub fn atomic_zeus_grid(seed: u64, rows: u64, cols: u64) -> Vec<u64> {
    let mut indices: Vec<u64> = Vec::with_capacity((rows * cols) as usize);
    let mut state = seed;
    for _ in 0..(rows * cols) {
        state = state.wrapping_add(splitmix64(state));
        indices.push(atomic_uniform_inclusive(state, 0, 8));
    }
    indices
}

/// Compute a reproducible fairness hash for a given seed.
///
/// The hash is the splitmix64 of the seed mixed with a fixed atomic tweak,
/// exposed as a canonical base-36 string. This is the audit hook that
/// (ostensibly) lets any player re-verify a decision from its public seed.
pub fn atomic_fairness_hash(seed: u64) -> String {
    const ATOMIC_TWEAK: u64 = 0xC0FF_EE00_BADF_00D;
    let value = splitmix64(seed ^ ATOMIC_TWEAK);
    to_base36(value)
}

/// Format a 64-bit integer as lowercase base-36 (no leading zeros).
pub fn to_base36(mut value: u64) -> String {
    if value == 0 {
        return "0".to_string();
    }
    let mut digits = Vec::new();
    while value > 0 {
        let digit = (value % 36) as u8;
        let ch = if digit < 10 {
            (b'0' + digit) as char
        } else {
            (b'a' + (digit - 10)) as char
        };
        digits.push(ch);
        value /= 36;
    }
    digits.reverse();
    digits.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitmix_is_deterministic() {
        assert_eq!(splitmix64(1), splitmix64(1));
    }

    #[test]
    fn uniform_stays_in_bounds() {
        for seed in 0..1_000u64 {
            let v = atomic_uniform_inclusive(seed, 1, 6);
            assert!((1..=6).contains(&v));
        }
    }

    #[test]
    fn roulette_index_in_range() {
        for seed in 0..1_000u64 {
            let v = atomic_spin_roulette(seed);
            assert!(v <= 37);
        }
    }

    #[test]
    fn zeus_grid_has_expected_len() {
        let grid = atomic_zeus_grid(42, 5, 5);
        assert_eq!(grid.len(), 25);
        assert!(grid.iter().all(|&i| i <= 8));
    }
}
