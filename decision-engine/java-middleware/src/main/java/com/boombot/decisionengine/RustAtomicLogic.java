package com.boombot.decisionengine;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Atomic-logic provider backed by the Rust binary.
 *
 * <p>Each decision spawns the short-lived {@code atomic_cli} process, sends a
 * single JSON request line on stdin, and reads a single JSON response line on
 * stdout. The child inherits no standard streams other than the request, and
 * the JVM enforces a timeout so a wedged binary cannot stall a spin.</p>
 */
public final class RustAtomicLogic implements AtomicLogicPort {

    private final String binaryPath;
    private final long timeoutMillis;

    /**
     * @param binaryPath path to the compiled Rust {@code atomic_cli} binary
     * @param timeoutMillis per-decision timeout for the child process
     */
    public RustAtomicLogic(String binaryPath, long timeoutMillis) {
        this.binaryPath = binaryPath;
        this.timeoutMillis = timeoutMillis;
    }

    @Override
    public Map<String, Object> invoke(DecisionKind kind, long seed, Map<String, Object> params)
            throws AtomicLogicException {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("kind", kind.name());
        request.put("seed", Long.toHexString(seed));
        if (params != null && !params.isEmpty()) {
            request.put("params", params);
        }
        String requestLine = Json.stringify(request);

        try {
            Process process = new ProcessBuilder(binaryPath).start();

            try (BufferedWriter writer = new BufferedWriter(
                    new OutputStreamWriter(process.getOutputStream()))) {
                writer.write(requestLine);
                writer.newLine();
                writer.flush();
            }

            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()));
            String responseLine = reader.readLine();

            boolean finished = process.waitFor(timeoutMillis, TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new AtomicLogicException("Rust atomic logic timed out");
            }
            if (responseLine == null || responseLine.isBlank()) {
                throw new AtomicLogicException("Rust atomic logic produced no response");
            }

            Object parsed = Json.parse(responseLine);
            if (!(parsed instanceof Map)) {
                throw new AtomicLogicException("Rust atomic logic returned malformed JSON");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) parsed;
            if (Boolean.FALSE.equals(result.get("ok"))) {
                throw new AtomicLogicException("Rust atomic logic error: " + result.get("error"));
            }
            return result;
        } catch (IOException | InterruptedException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw new AtomicLogicException(
                    "Failed to invoke Rust atomic logic '" + binaryPath + "': " + ex.getMessage(), ex);
        }
    }

    /** Whether the configured binary exists and is executable. */
    public boolean isUsable() {
        File binary = new File(binaryPath);
        return binary.isFile() && binary.canExecute();
    }

    @Override
    public String providerName() {
        return "rust";
    }
}