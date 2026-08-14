package com.boombot.decisionengine;

/**
 * Raised when an atomic-logic provider cannot render a decision.
 *
 * <p>The decision engine treats this as a degradation signal: when the Rust
 * provider fails (binary missing, timeout, malformed response) the engine
 * transparently falls back to the in-JVM reference provider so a decision is
 * always rendered.</p>
 */
public class AtomicLogicException extends Exception {

    public AtomicLogicException(String message) {
        super(message);
    }

    public AtomicLogicException(String message, Throwable cause) {
        super(message, cause);
    }
}
