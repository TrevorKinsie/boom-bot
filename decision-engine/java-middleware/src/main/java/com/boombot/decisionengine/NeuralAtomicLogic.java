package com.boombot.decisionengine;

import com.boombot.decisionengine.neural.Activation;
import com.boombot.decisionengine.neural.Layer;
import com.boombot.decisionengine.neural.NeuralNetwork;

import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Atomic-logic provider rendered by the JavaBeans neural engine.
 *
 * <p>The provider is the decision fabric's optional neural path: it turns a
 * numeric seed into a deterministic feature vector, runs it through a
 * {@link NeuralNetwork} bean graph (deterministically initialised, so the
 * engine renders the same outcome for the same seed on every boot), and maps
 * the output activations onto the raw result shape of each game family
 * identical to the shapes produced by the Rust and reference providers.</p>
 *
 * <p>An optional trained model may be supplied as a serialised
 * {@link NeuralNetwork} bean (see <code>DECISION_ENGINE_NEURAL_MODEL</code>);
 * the model drives whichever decision kind matches its output width, while
 * every other kind keeps its deterministically initialised built-in network.
 * The provider is opt-in and never changes the house edge: the edge is defined
 * by the payout tables, not by the decision engine.</p>
 */
public final class NeuralAtomicLogic implements AtomicLogicPort {

    /** Width of the seed-derived feature vector (a bean property of every network). */
    public static final int FEATURE_COUNT = 64;

    /** Width of the shared hidden layer of the built-in networks. */
    public static final int HIDDEN_NEURONS = 32;

    /** Determinism seed of the built-in networks; every deployment renders identical weights. */
    public static final int BUILTIN_SEED = 0x5EED;

    /** Cell count of a Zeus reel grid. */
    private static final int ZEUS_CELLS = 25;

    /** Symbol count of a Zeus reel cell. */
    private static final int ZEUS_SYMBOLS = 9;

    /**
     * Aggregation trials for the built-in, untrained networks. A single
     * argmax over a random-weight softmax head is measurably biased; summing
     * the argmaxes of independently salted passes modulo the outcome count
     * convolves the per-trial distributions toward uniform (the same uniform
     * odds the Rust and reference providers guarantee by construction).
     */
    private static final int TRIALS = 4;

    private static final long GOLDEN = 0x9E3779B97F4A7C15L;

    private final NeuralNetwork model;
    private final Map<DecisionKind, NeuralNetwork> builtin = new LinkedHashMap<>();

    /** Constructs the provider with deterministic built-in networks only. */
    public NeuralAtomicLogic() {
        this.model = null;
    }

    /**
     * Constructs the provider with an optional trained model.
     *
     * @param modelFile serialised {@link NeuralNetwork} bean graph
     * @throws AtomicLogicException when the model cannot be loaded
     */
    public NeuralAtomicLogic(File modelFile) throws AtomicLogicException {
        if (modelFile == null || !modelFile.isFile()) {
            throw new AtomicLogicException("Neural model file not found: " + modelFile);
        }
        try {
            this.model = NeuralNetwork.load(modelFile);
        } catch (Exception ex) {
            throw new AtomicLogicException("Cannot load neural model " + modelFile, ex);
        }
    }

    @Override
    public Map<String, Object> invoke(DecisionKind kind, long seed, Map<String, Object> params)
            throws AtomicLogicException {
        NeuralNetwork network = networkFor(kind);
        int trials = network == model ? 1 : TRIALS;
        switch (kind) {
            case ROULETTE_SPIN: {
                long index = outcomeIndex(network, seed, kindSalt(kind), trials, 38);
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("value", index);
                return result;
            }
            case CRAPS_ROLL: {
                long index = outcomeIndex(network, seed, kindSalt(kind), trials, 36);
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("die1", 1 + index / 6);
                result.put("die2", 1 + index % 6);
                return result;
            }
            case ZEUS_SPIN: {
                List<Object> symbols = new ArrayList<>(ZEUS_CELLS);
                for (int cell = 0; cell < ZEUS_CELLS; cell++) {
                    long cellSalt = cellSalt(kindSalt(kind), cell);
                    symbols.add(outcomeIndex(network, seed, cellSalt, trials, ZEUS_SYMBOLS));
                }
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("value", (long) ZEUS_CELLS);
                result.put("symbols", symbols);
                return result;
            }
            case FAIRNESS_HASH: {
                double[] output = network.predict(features(seed, kindSalt(kind)));
                long bits = bitsFrom(output);
                for (int t = 1; t < trials; t++) {
                    bits ^= bitsFrom(network.predict(features(seed, trialSalt(kindSalt(kind), t))));
                }
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("hash", Long.toHexString(bits));
                return result;
            }
            default:
                throw new AtomicLogicException("Unsupported decision kind: " + kind);
        }
    }

    @Override
    public String providerName() {
        return "neural";
    }

    /**
     * The network serving a decision kind: the loaded model whenever its
     * output width matches the kind's outcome space, otherwise a lazily
     * built deterministically initialised network shared by all callers.
     */
    private NeuralNetwork networkFor(DecisionKind kind) {
        int outputSize = outputSize(kind);
        if (model != null && model.getOutputSize() == outputSize) {
            return model;
        }
        return builtin.computeIfAbsent(kind, k -> builtinNetwork(kind, outputSize));
    }

    /** Deterministic seed-derived feature vector; a pure function of the seed. */
    private static double[] features(long seed, long salt) {
        double[] features = new double[FEATURE_COUNT];
        for (int i = 0; i < FEATURE_COUNT; i++) {
            long mixed = splitmix64(seed ^ salt ^ (GOLDEN * (i + 1)));
            long top = mixed >>> 11;
            double unit = top * 0x1.0p-53;
            features[i] = unit * 2.0 - 1.0;
        }
        return features;
    }

    private static NeuralNetwork builtinNetwork(DecisionKind kind, int outputSize) {
        Activation outputActivation = kind == DecisionKind.FAIRNESS_HASH
                ? Activation.SIGMOID : Activation.SOFTMAX;
        NeuralNetwork network = new NeuralNetwork();
        network.setId("neural:" + kind.name().toLowerCase());
        network.setInputSize(FEATURE_COUNT);
        network.setSeed(BUILTIN_SEED ^ outputSize * 0x9E3779B1);
        network.setLayers(List.of(
                Layer.create("hidden", HIDDEN_NEURONS, FEATURE_COUNT, Activation.RELU),
                Layer.create("output", outputSize, HIDDEN_NEURONS, outputActivation)));
        network.initializeDeterministic();
        return network;
    }

    private static int outputSize(DecisionKind kind) {
        switch (kind) {
            case ROULETTE_SPIN:
                return 38;
            case CRAPS_ROLL:
                return 36;
            case ZEUS_SPIN:
                return ZEUS_SYMBOLS;
            case FAIRNESS_HASH:
                return Long.SIZE;
            default:
                throw new IllegalArgumentException("Unsupported decision kind: " + kind);
        }
    }

    private static long kindSalt(DecisionKind kind) {
        return 0xFEDCBA9876543210L ^ (kind.ordinal() * GOLDEN);
    }

    private static long trialSalt(long kindSalt, int trial) {
        return splitmix64(kindSalt ^ (trial * GOLDEN));
    }

    private static long cellSalt(long kindSalt, int cell) {
        return splitmix64(kindSalt ^ (cell * GOLDEN));
    }

    /** Index into an outcome space of {@code width}: argmax aggregated over independently salted passes. */
    private static long outcomeIndex(NeuralNetwork network, long seed, long salt, int trials, int width) {
        long index = 0;
        for (int t = 0; t < trials; t++) {
            double[] output = network.predict(features(seed, t == 0 ? salt : trialSalt(salt, t)));
            index += argmax(output);
        }
        return index % width;
    }

    private static long bitsFrom(double[] output) {
        long bits = 0L;
        for (int i = 0; i < Math.min(Long.SIZE, output.length); i++) {
            if (output[i] > 0.5) {
                bits |= 1L << i;
            }
        }
        return bits;
    }

    private static int argmax(double[] values) {
        int index = 0;
        for (int i = 1; i < values.length; i++) {
            if (values[i] > values[index]) {
                index = i;
            }
        }
        return index;
    }

    private static long splitmix64(long x) {
        x += GOLDEN;
        long z = x;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }
}