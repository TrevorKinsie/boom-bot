package com.boombot.decisionengine;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Decision-engine entry point.
 *
 * <p>Runs a long-lived JSON-lines loop on stdin/stdout, mirroring the
 * UCI-style engine invocation used elsewhere in boom-bot (the Stockfish subprocess).
 * For each request line it dispatches to the {@link DecisionEngine} and echoes a
 * single response line, keeping the protocol trivially testable.</p>
 */
public final class Main {

    private Main() {
    }

    public static void main(String[] args) throws IOException {
        String rustBin = System.getenv("DECISION_ENGINE_RUST_BIN");
        long timeoutMillis = parseTimeoutEnv();

        AtomicLogicPort primary;
        if (rustBin != null && !rustBin.isBlank() && new File(rustBin).canExecute()) {
            primary = new RustAtomicLogic(rustBin, timeoutMillis);
        } else {
            primary = new ReferenceAtomicLogic();
        }

        DecisionEngine engine = new DecisionEngine(primary, new ReferenceAtomicLogic());

        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        String line;
        while ((line = reader.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }
            try {
                Object parsed = Json.parse(line);
                if (!(parsed instanceof Map)) {
                    throw new IllegalArgumentException("Request must be a JSON object");
                }
                @SuppressWarnings("unchecked")
                Map<String, Object> request = (Map<String, Object>) parsed;
                System.out.println(Json.stringify(engine.decide(request)));
            } catch (Exception ex) {
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("error", ex.getMessage());
                System.out.println(Json.stringify(error));
            }
            System.out.flush();
        }
    }

    private static long parseTimeoutEnv() {
        String raw = System.getenv("DECISION_ENGINE_TIMEOUT_SECONDS");
        try {
            return (long) (Double.parseDouble(raw) * 1000);
        } catch (RuntimeException ex) {
            return 5000L;
        }
    }
}