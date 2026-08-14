package com.boombot.decisionengine;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The JVM decision engine -- the middleware core of the decision fabric.
 *
 * <p>The engine is the single translator between the Python orchestrator and
 * the Rust atomic-logic layer. For a given request it:</p>
 *
 * <ol>
 *   <li>normalises the request into a {@link DecisionKind} and a numeric seed,</li>
 *   <li>selects the {@link DecisionStrategy} for the game family,</li>
 *   <li>asks the primary atomic provider (the Rust binary) for the raw result,</li>
 *   <li>transparently degrades to the in-JVM reference provider if the Rust
 *       binary is missing, slow, or malformed, and</li>
 *   <li>composes and returns the final decision payload.</li>
 * </ol>
 *
 * <p>The middleware intentionally holds zero game arithmetic: it knows which
 * strategy to run and how to normalise the result, but the actual randomness
 * is delegated down to the pure atomic layer.</p>
 */
public final class DecisionEngine {

    private final AtomicLogicPort primary;
    private final AtomicLogicPort fallback;

    /** @param primary the preferred atomic provider (typically the Rust binary) */
    public DecisionEngine(AtomicLogicPort primary, AtomicLogicPort fallback) {
        this.primary = primary;
        this.fallback = fallback;
    }

    /**
     * Render a decision for a JSON request map.
     *
     * @param requestJson map with {@code id}, {@code kind}, {@code seed} and
     *                    optional {@code params}
     * @return the response map consumed by the Python orchestrator
     */
    public Map<String, Object> decide(Map<String, Object> requestJson) {
        String id = stringField(requestJson, "id", "");
        String kindRaw = stringField(requestJson, "kind", "");
        String seedHex = stringField(requestJson, "seed", "");
        long seed = parseSeed(seedHex);
        DecisionKind kind = DecisionKind.from(kindRaw);
        Map<String, Object> params = mapField(requestJson, "params");
        DecisionStrategy strategy = strategyFor(kind);

        String atomicProvider;
        Map<String, Object> raw;
        long started = System.nanoTime();
        AtomicLogicPort provider = primary;
        try {
            raw = primary.invoke(kind, seed, params);
        } catch (AtomicLogicException ex) {
            try {
                raw = fallback.invoke(kind, seed, params);
            } catch (AtomicLogicException fallbackEx) {
                // The reference provider is total for every known kind; reaching
                // this line means the request kind was never registered.
                throw new IllegalArgumentException(
                        "No atomic provider could render kind " + kind, fallbackEx);
            }
            provider = fallback;
        }
        long elapsedMs = (System.nanoTime() - started) / 1_000_000;
        atomicProvider = provider.providerName();

        Map<String, Object> decision = strategy.compose(seed, raw);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("id", id);
        response.put("engine", "jvm");
        response.put("atomic", atomicProvider);
        response.put("latencyMs", elapsedMs);
        response.put("seed", seedHex);
        response.put("decision", decision);
        return response;
    }

    private static DecisionStrategy strategyFor(DecisionKind kind) {
        switch (kind) {
            case ROULETTE_SPIN:
                return new RouletteStrategy();
            case CRAPS_ROLL:
                return new CrapsStrategy();
            case ZEUS_SPIN:
                return new ZeusStrategy();
            case FAIRNESS_HASH:
                return new FairnessStrategy();
            default:
                throw new IllegalArgumentException("Unsupported decision kind: " + kind);
        }
    }

    private static long parseSeed(String seedHex) {
        if (seedHex == null || seedHex.isBlank()) {
            return 0;
        }
        try {
            return Long.parseUnsignedLong(seedHex, 16);
        } catch (NumberFormatException ex) {
            return seedHex.hashCode() & 0x7fffffffL;
        }
    }

    private static String stringField(Map<String, Object> map, String key, String fallback) {
        Object value = map.get(key);
        return value instanceof String ? (String) value : fallback;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapField(Map<String, Object> map, String key) {
        Object value = map.get(key);
        return value instanceof Map ? (Map<String, Object>) value : Map.of();
    }
}