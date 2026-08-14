package com.boombot.decisionengine;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Roulette decision strategy.
 *
 * <p>The raw atomic result carries a wheel index ``0..=37`` where ``37`` is
 * the American double-zero pocket. This strategy performs the final business
 * normalisation: the digits pocket {@code "00"} is represented as such, and
 * every other index is surfaced as its plain integer pocket.</p>
 */
public final class RouletteStrategy implements DecisionStrategy {

    @Override
    public DecisionKind kind() {
        return DecisionKind.ROULETTE_SPIN;
    }

    @Override
    public Map<String, Object> compose(long seed, Map<String, Object> raw) {
        long index = DecisionStrategy.longField(raw, "value", 0);
        Object pocket = index == 37 ? "00" : index;
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", DecisionKind.ROULETTE_SPIN.name());
        payload.put("pocket", pocket);
        payload.put("label", String.valueOf(pocket));
        return payload;
    }
}