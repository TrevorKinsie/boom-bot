package com.boombot.decisionengine;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Fairness-hash decision strategy.
 *
 * <p>Surfaces the raw provider fairness hash (a base-36 / hex string) as the
 * final decision payload. This is the audit hook that lets a player re-verify
 * a rendered decision from its public seed.</p>
 */
public final class FairnessStrategy implements DecisionStrategy {

    @Override
    public DecisionKind kind() {
        return DecisionKind.FAIRNESS_HASH;
    }

    @Override
    public Map<String, Object> compose(long seed, Map<String, Object> raw) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", DecisionKind.FAIRNESS_HASH.name());
        payload.put("hash", String.valueOf(raw.get("hash")));
        return payload;
    }
}