package com.boombot.decisionengine;

import java.util.Map;

/**
 * Port describing an atomic-logic provider.
 *
 * <p>A provider turns a {@link DecisionKind}, a numeric seed, and an optional
 * parameter map into a raw atomic result. The raw result shape is shared by
 * every provider implementation so that decision strategies can compose the
 * same payload regardless of whether the value came from the Rust binary or
 * from the in-JVM reference implementation.</p>
 */
public interface AtomicLogicPort {

    /**
     * Render a raw atomic result for the given kind, seed and parameters.
     *
     * @param kind the decision kind to render
     * @param seed the numeric seed that fully determines the outcome
     * @param params optional kind-specific parameters (never null)
     * @return a raw result map (e.g. {@code {"value":17}})
     * @throws AtomicLogicException when the provider cannot render a result
     */
    Map<String, Object> invoke(DecisionKind kind, long seed, Map<String, Object> params)
            throws AtomicLogicException;

    /**
     * The canonical provider identifier reported in decision metadata.
     * Returns {@code "rust"} for the native binary and {@code "java"} for the
     * in-JVM reference implementation.
     */
    String providerName();
}
