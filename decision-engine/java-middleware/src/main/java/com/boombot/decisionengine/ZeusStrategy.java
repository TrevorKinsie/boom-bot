package com.boombot.decisionengine;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Zeus decision strategy.
 *
 * <p>The raw atomic result carries a row-major vector of symbol indices; this
 * strategy wraps them with the grid dimensions so the orchestrator can rebuild
 * an immutable {@code ReelGrid} on the Python side without ever touching a RNG.</p>
 */
public final class ZeusStrategy implements DecisionStrategy {

    @Override
    public DecisionKind kind() {
        return DecisionKind.ZEUS_SPIN;
    }

    @Override
    public Map<String, Object> compose(long seed, Map<String, Object> raw) {
        List<Object> symbols = raw.get("symbols") instanceof List
                ? (List<Object>) raw.get("symbols")
                : List.of();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", DecisionKind.ZEUS_SPIN.name());
        payload.put("rows", 5);
        payload.put("cols", 5);
        payload.put("symbols", symbols);
        return payload;
    }
}