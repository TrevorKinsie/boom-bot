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
        if (neuralEnabled()) {
            primary = buildNeuralProvider();
        } else if (rustBin != null && !rustBin.isBlank() && new File(rustBin).canExecute()) {
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

    /** {@code DECISION_ENGINE_NEURAL}=1|true|yes|on selects the JavaBeans neural provider. */
    private static boolean neuralEnabled() {
        String raw = System.getenv("DECISION_ENGINE_NEURAL");
        if (raw == null) {
            return false;
        }
        switch (raw.trim().toLowerCase()) {
            case "1":
            case "true":
            case "yes":
            case "on":
                return true;
            default:
                return false;
        }
    }

    /** Build the neural provider, optionally from a serialised {@code NeuralNetwork} model. */
    private static AtomicLogicPort buildNeuralProvider() {
        String modelPath = System.getenv("DECISION_ENGINE_NEURAL_MODEL");
        if (modelPath != null && !modelPath.isBlank()) {
            File modelFile = new File(modelPath);
            if (modelFile.isFile()) {
                try {
                    return new NeuralAtomicLogic(modelFile);
                } catch (AtomicLogicException ex) {
                    System.err.println("[warn] neural model unusable (" + ex.getMessage()
                            + "); falling back to built-in networks.");
                }
            } else {
                System.err.println("[warn] neural model not found at " + modelPath
                        + "; using built-in networks.");
            }
        }
        return new NeuralAtomicLogic();
    }
}