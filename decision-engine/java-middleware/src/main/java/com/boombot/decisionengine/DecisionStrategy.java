package com.boombot.decisionengine;

import java.util.Map;

/**
 * Strategy responsible for composing a raw atomic result into a decision
 * payload for a single game family.
 *
 * <p>Decoupling the composition from the provider keeps the game rules (the
 * "business logic" of a decision) in the JVM, while the arithmetic randomness
 * is delegated down to the Rust atomic layer.</p>
 */
public interface DecisionStrategy {

    /** The decision kind this strategy renders. */
    DecisionKind kind();

    /**
     * Translate a raw atomic result into the final decision payload.
     *
     * @param seed the numeric seed that produced the raw result
     * @param raw the raw result map from an {@link AtomicLogicPort}
     * @return the decision payload consumed by the Python orchestrator
     */
    Map<String, Object> compose(long seed, Map<String, Object> raw);

    /** Read a long field from a raw result map, or return the default. */
    static long longField(Map<String, Object> raw, String key, long fallback) {
        Object value = raw.get(key);
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        return fallback;
    }
}