package com.boombot.decisionengine;

/**
 * The canonical set of decisions the JVM decision engine can render.
 *
 * <p>Each member maps to one pure atomic primitive in the Rust logic layer.
 * The enum name is the wire identifier used across all three layers of the
 * decision fabric (Python orchestrator, Java middleware, Rust atomic logic).</p>
 */
public enum DecisionKind {

    /** Decide the winning pocket of an American roulette wheel (0..=37; 37 == "00"). */
    ROULETTE_SPIN,

    /** Decide a craps roll as two die faces, each in 1..=6. */
    CRAPS_ROLL,

    /** Decide a Zeus reel grid as a row-major vector of symbol indices. */
    ZEUS_SPIN,

    /** Compute a reproducible fairness hash for a given seed. */
    FAIRNESS_HASH;

    /** Resolve a wire identifier to its enum member, or throw. */
    public static DecisionKind from(String raw) {
        for (DecisionKind kind : values()) {
            if (kind.name().equals(raw)) {
                return kind;
            }
        }
        throw new IllegalArgumentException("Unknown decision kind: " + raw);
    }
}
