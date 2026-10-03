package com.boombot.decisionengine;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Craps decision strategy.
 *
 * <p>The raw atomic result carries the two die faces; this strategy surfaces
 * them alongside their sum so the Python orchestrator can resolve every
 * outstanding wager and advance the table phase without touching randomness.</p>
 */
public final class CrapsStrategy implements DecisionStrategy {

    @Override
    public DecisionKind kind() {
        return DecisionKind.CRAPS_ROLL;
    }

    @Override
    public Map<String, Object> compose(long seed, Map<String, Object> raw) {
        long die1 = DecisionStrategy.longField(raw, "die1", 1);
        long die2 = DecisionStrategy.longField(raw, "die2", 1);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", DecisionKind.CRAPS_ROLL.name());
        payload.put("die1", die1);
        payload.put("die2", die2);
        payload.put("sum", die1 + die2);
        return payload;
    }
}