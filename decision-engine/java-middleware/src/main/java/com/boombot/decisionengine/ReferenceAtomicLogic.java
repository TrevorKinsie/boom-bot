package com.boombot.decisionengine;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * In-JVM reference atomic-logic provider.
 *
 * <p>This provider is the availability guarantee behind the decision engine's
 * "always render a decision" contract. It produces identically-shaped raw
 * results to the Rust provider using a seed-seeded {@link java.util.Random},
 * so decisions can be rendered with the same odds regardless of which
 * provider is engaged. The house edge is defined by the payout tables, not by
 * the engine.</p>
 */
public final class ReferenceAtomicLogic implements AtomicLogicPort {

    @Override
    public Map<String, Object> invoke(DecisionKind kind, long seed, Map<String, Object> params)
            throws AtomicLogicException {
        Random rng = new Random(seed);
        switch (kind) {
            case ROULETTE_SPIN: {
                long index = rng.nextInt(38);
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("value", index);
                return result;
            }
            case CRAPS_ROLL: {
                long die1 = rng.nextInt(6) + 1;
                long die2 = rng.nextInt(6) + 1;
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("die1", die1);
                result.put("die2", die2);
                return result;
            }
            case ZEUS_SPIN: {
                int cells = 25;
                List<Object> symbols = new ArrayList<>(cells);
                for (int i = 0; i < cells; i++) {
                    symbols.add((long) rng.nextInt(9));
                }
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("value", (long) cells);
                result.put("symbols", symbols);
                return result;
            }
            case FAIRNESS_HASH: {
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("hash", Long.toHexString(rng.nextLong()));
                return result;
            }
            default:
                throw new AtomicLogicException("Unsupported decision kind: " + kind);
        }
    }

    @Override
    public String providerName() {
        return "java";
    }
}