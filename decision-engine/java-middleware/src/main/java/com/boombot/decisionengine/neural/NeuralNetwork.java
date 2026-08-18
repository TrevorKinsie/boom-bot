package com.boombot.decisionengine.neural;

import java.beans.PropertyChangeEvent;
import java.beans.PropertyChangeListener;
import java.beans.PropertyChangeSupport;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/**
 * The neural engine's {@code NeuralNetwork} bean.
 *
 * <p>Implements the JavaBeans contract end to end: public no-arg constructor,
 * private fields with public getters/setters, bound properties fired through
 * {@link PropertyChangeSupport}, Java serialisation for persistence, and
 * listener propagation - the network registers itself as a
 * {@link PropertyChangeListener} on every composed layer and forwards layer
 * and neuron change events to its own listeners.</p>
 *
 * <p>The network supports deterministic weight initialisation (a bean property
 * {@code seed} drives the RNG, so identical beans train to identical weights),
 * {@link #predict(double[])} for inference, and on-line SGD {@link #train}
 * with backpropagation for learning. A network is a {@link Serializable} graph:
 * {@link #save(File)} / {@link #load(File)} persist and restore it verbatim.</p>
 */
public class NeuralNetwork implements Serializable, PropertyChangeListener {

    private static final long serialVersionUID = 1L;

    private static final long GOLDEN = 0x9E3779B97F4A7C15L;

    private String id;
    private int inputSize;
    private List<Layer> layers;
    private int seed;
    private double learningRate;
    private boolean trained;

    private final PropertyChangeSupport propertyChangeSupport = new PropertyChangeSupport(this);

    /** Bean-friendly no-arg constructor: empty, unconnected network. */
    public NeuralNetwork() {
        this.id = "neural-network";
        this.inputSize = 0;
        this.layers = new ArrayList<>();
        this.seed = 42;
        this.learningRate = 0.05;
        this.trained = false;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        String old = this.id;
        this.id = id;
        propertyChangeSupport.firePropertyChange("id", old, id);
    }

    /** Width of the input feature vector consumed by the first layer. */
    public int getInputSize() {
        return inputSize;
    }

    public void setInputSize(int inputSize) {
        int old = this.inputSize;
        this.inputSize = inputSize;
        propertyChangeSupport.firePropertyChange("inputSize", old, inputSize);
    }

    /** Unmodifiable snapshot of the composed layer beans. */
    public List<Layer> getLayers() {
        return Collections.unmodifiableList(new ArrayList<>(layers));
    }

    /**
     * Bound property {@code layers}. The network subscribes to every new layer
     * so that bound-property events from the layer and its neurons are
     * propagated to this bean's own listeners.
     */
    public void setLayers(List<Layer> layers) {
        for (Layer layer : this.layers) {
            layer.removePropertyChangeListener(this);
        }
        List<Layer> old = this.layers;
        this.layers = new ArrayList<>(layers);
        for (Layer layer : this.layers) {
            layer.addPropertyChangeListener(this);
        }
        propertyChangeSupport.firePropertyChange("layers", old, this.layers);
    }

    public Layer getLayerAt(int index) {
        return layers.get(index);
    }

    public int getLayerCount() {
        return layers.size();
    }

    /** Width of the final layer's output vector (0 while the network is empty). */
    public int getOutputSize() {
        return layers.isEmpty() ? 0 : layers.get(layers.size() - 1).getNeuronCount();
    }

    /** Determinism seed for {@link #initializeDeterministic()}; a bound property. */
    public int getSeed() {
        return seed;
    }

    public void setSeed(int seed) {
        int old = this.seed;
        this.seed = seed;
        propertyChangeSupport.firePropertyChange("seed", old, seed);
    }

    public double getLearningRate() {
        return learningRate;
    }

    public void setLearningRate(double learningRate) {
        double old = this.learningRate;
        this.learningRate = learningRate;
        propertyChangeSupport.firePropertyChange("learningRate", old, learningRate);
    }

    public boolean isTrained() {
        return trained;
    }

    public void setTrained(boolean trained) {
        boolean old = this.trained;
        this.trained = trained;
        propertyChangeSupport.firePropertyChange("trained", old, trained);
    }

    /**
     * Initialise every composed neuron with seeded Gaussian weights (He for
     * ReLU layers, Xavier otherwise) and zero biases. Fully deterministic: the
     * same network bean seeded the same way yields the same weights.
     */
    public NeuralNetwork initializeDeterministic() {
        for (int k = 0; k < layers.size(); k++) {
            Layer layer = layers.get(k);
            Random rng = new Random(seed ^ (GOLDEN * (k + 1)));
            Activation activation = layer.getActivation();
            double stddev = activation == Activation.RELU
                    ? Math.sqrt(2.0 / layer.getInputSize())
                    : Math.sqrt(1.0 / layer.getInputSize());
            for (Neuron neuron : layer.getNeurons()) {
                double[] weights = new double[layer.getInputSize()];
                for (int j = 0; j < weights.length; j++) {
                    weights[j] = rng.nextGaussian() * stddev;
                }
                neuron.setBias(0.0);
                neuron.setWeights(weights);
            }
        }
        setTrained(false);
        return this;
    }

    /**
     * Run the network's feed-forward pass on a feature vector. The vector
     * length must equal {@link #getInputSize()}.
     */
    public double[] predict(double[] input) {
        if (input.length != inputSize) {
            throw new IllegalArgumentException(
                    "Network " + id + " expects " + inputSize + " inputs, got " + input.length);
        }
        double[] activations = input;
        for (Layer layer : layers) {
            activations = layer.forward(activations);
        }
        return activations;
    }

    /** Gradient-descent step for every layer once all deltas are known. */
    public void updateWeights() {
        for (Layer layer : layers) {
            layer.updateWeights(learningRate);
        }
    }

    /**
     * Train the network on sample/target pairs with on-line stochastic
     * gradient descent. Deltas are propagated backward through the whole
     * graph before any weight moves, so every step uses pre-update weights.
     * Every gradient step flows through the beans' bound properties, so
     * observers see each weight update as a change event. The network must be
     * initialised with {@link #initializeDeterministic()} (or restored from a
     * saved bean graph) beforehand.
     */
    public NeuralNetwork train(List<double[]> inputs, List<double[]> targets, int epochs) {
        if (inputs.size() != targets.size()) {
            throw new IllegalArgumentException("inputs and targets must be paired");
        }
        if (inputs.isEmpty()) {
            throw new IllegalArgumentException("cannot train on an empty dataset");
        }
        for (Layer layer : layers) {
            if (layer.getNeuronCount() == 0) {
                throw new IllegalArgumentException(
                        "layers are empty; call initializeDeterministic() before training");
            }
            if (layer.getNeuronAt(0).getWeightCount() != layer.getInputSize()) {
                throw new IllegalArgumentException(
                        "layers are uninitialised; call initializeDeterministic() before training");
            }
        }
        for (int epoch = 0; epoch < epochs; epoch++) {
            for (int i = 0; i < inputs.size(); i++) {
                double[] output = predict(inputs.get(i));
                Layer last = layers.get(layers.size() - 1);
                double[] deltas = last.outputDeltas(targets.get(i));
                for (int k = layers.size() - 2; k >= 0; k--) {
                    deltas = layers.get(k).computeDeltas(deltas, layers.get(k + 1));
                }
                updateWeights();
            }
        }
        setTrained(true);
        return this;
    }

    @Override
    public void propertyChange(PropertyChangeEvent event) {
        propertyChangeSupport.firePropertyChange(event);
    }

    public void addPropertyChangeListener(PropertyChangeListener listener) {
        propertyChangeSupport.addPropertyChangeListener(listener);
    }

    public void removePropertyChangeListener(PropertyChangeListener listener) {
        propertyChangeSupport.removePropertyChangeListener(listener);
    }

    public PropertyChangeListener[] getPropertyChangeListeners() {
        return propertyChangeSupport.getPropertyChangeListeners();
    }

    /** Persist the whole bean graph through Java serialisation. */
    public void save(File file) throws IOException {
        try (ObjectOutputStream out = new ObjectOutputStream(new FileOutputStream(file))) {
            out.writeObject(this);
        }
    }

    /** Restore a previously saved network bean graph. */
    public static NeuralNetwork load(File file) throws IOException, ClassNotFoundException {
        try (ObjectInputStream in = new ObjectInputStream(new FileInputStream(file))) {
            Object value = in.readObject();
            if (!(value instanceof NeuralNetwork)) {
                throw new IOException("Not a NeuralNetwork bean: " + value.getClass().getName());
            }
            return (NeuralNetwork) value;
        }
    }
}