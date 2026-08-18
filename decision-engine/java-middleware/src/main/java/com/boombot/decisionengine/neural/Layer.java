package com.boombot.decisionengine.neural;

import java.beans.PropertyChangeListener;
import java.beans.PropertyChangeSupport;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * A fully connected layer of {@link Neuron} beans, itself a JavaBean.
 *
 * <p>Exposes the standard bean ceremony ({@code id}, {@code neurons},
 * {@code activation}) plus the two computational passes of the neural engine:
 * {@link #forward(double[])} propagates activations for inference, {@link
 * #backward(double[], Layer, double)} propagates errors and nudges the
 * composed neuron beans. The transient {@code activations} bound property
 * fires after every forward pass, so observing the engine is a matter of
 * attaching a {@link PropertyChangeListener}.</p>
 */
public class Layer implements Serializable {

    private static final long serialVersionUID = 1L;

    private String id;
    private List<Neuron> neurons;
    private Activation activation;

    private transient double[] inputs;
    private transient double[] sums;
    private transient double[] outputs;
    private transient double[] deltas;

    private final PropertyChangeSupport propertyChangeSupport = new PropertyChangeSupport(this);

    /** Bean-friendly no-arg constructor: empty identity layer. */
    public Layer() {
        this.id = "layer";
        this.neurons = new ArrayList<>();
        this.activation = Activation.IDENTITY;
    }

    /** Factory for an empty (uninitialised) layer of the given shape. */
    public static Layer create(String id, int neuronCount, int inputSize, Activation activation) {
        Layer layer = new Layer();
        layer.id = id;
        layer.activation = activation;
        for (int i = 0; i < neuronCount; i++) {
            layer.neurons.add(new Neuron(id + "[" + i + "]", 0.0, new double[inputSize]));
        }
        return layer;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        String old = this.id;
        this.id = id;
        propertyChangeSupport.firePropertyChange("id", old, id);
    }

    /** Unmodifiable snapshot of the composed neuron beans. */
    public List<Neuron> getNeurons() {
        return Collections.unmodifiableList(new ArrayList<>(neurons));
    }

    /** Bound property {@code neurons}: fires whenever the composition changes. */
    public void setNeurons(List<Neuron> neurons) {
        List<Neuron> old = this.neurons;
        this.neurons = new ArrayList<>(neurons);
        propertyChangeSupport.firePropertyChange("neurons", old, this.neurons);
    }

    public Neuron getNeuronAt(int index) {
        return neurons.get(index);
    }

    public int getNeuronCount() {
        return neurons.size();
    }

    /** Mutator for incremental composition (also fires the {@code neurons} bound property). */
    public void addNeuron(Neuron neuron) {
        neurons.add(neuron);
        propertyChangeSupport.firePropertyChange("neurons", neurons.size() - 1, neurons.size());
    }

    public Activation getActivation() {
        return activation;
    }

    public void setActivation(Activation activation) {
        Activation old = this.activation;
        this.activation = activation;
        propertyChangeSupport.firePropertyChange("activation", old, activation);
    }

    /** Incoming width: the previous layer's output size for every composed neuron. */
    public int getInputSize() {
        return neurons.isEmpty() ? 0 : neurons.get(0).getWeightCount();
    }

    /** Latest output activations (bound property {@code activations}); null before the first pass. */
    public double[] getActivations() {
        return outputs == null ? null : outputs.clone();
    }

    /** Latest backpropagation deltas (bound property {@code deltas}); null before the first pass. */
    public double[] getDeltas() {
        return deltas == null ? null : deltas.clone();
    }

    /** Latest raw inputs received by this layer; null before the first pass. */
    public double[] getInputs() {
        return inputs == null ? null : inputs.clone();
    }

    /**
     * Forward pass: compute pre-activation sums from the inputs and materialise
     * the layer's activations. Fires the {@code activations} bound property when
     * listeners are attached.
     */
    public double[] forward(double[] in) {
        if (in.length != getInputSize()) {
            throw new IllegalArgumentException(
                    "Layer " + id + " expects " + getInputSize() + " inputs, got " + in.length);
        }
        this.inputs = in.clone();
        this.sums = new double[neurons.size()];
        this.outputs = new double[neurons.size()];
        for (int i = 0; i < neurons.size(); i++) {
            Neuron neuron = neurons.get(i);
            double sum = neuron.getBias();
            for (int j = 0; j < in.length; j++) {
                sum += in[j] * neuron.getWeightAt(j);
            }
            sums[i] = sum;
        }
        if (activation == Activation.SOFTMAX) {
            outputs = softmax(sums);
        } else {
            for (int i = 0; i < neurons.size(); i++) {
                outputs[i] = activation.apply(sums[i]);
            }
        }
        if (propertyChangeSupport.hasListeners("activations")) {
            propertyChangeSupport.firePropertyChange("activations", null, outputs.clone());
        }
        return outputs.clone();
    }

    /**
     * Output-layer error pass: deltas for a softmax + cross-entropy head are
     * {@code output - target}; any other activation uses mean-squared-error
     * with the activation derivative.
     */
    public double[] outputDeltas(double[] target) {
        if (target.length != neurons.size()) {
            throw new IllegalArgumentException(
                    "Layer " + id + " expects " + neurons.size() + " targets, got " + target.length);
        }
        double[] result = new double[neurons.size()];
        for (int i = 0; i < neurons.size(); i++) {
            if (activation == Activation.SOFTMAX) {
                result[i] = outputs[i] - target[i];
            } else {
                result[i] = (outputs[i] - target[i]) * activation.derivative(outputs[i]);
            }
        }
        this.deltas = result;
        fireDeltas();
        return result;
    }

    /**
     * Hidden-layer error pass: backpropagate {@code next}'s deltas through
     * {@code next}'s weights onto this layer. Pure error propagation — weight
     * updates happen afterwards via {@link #updateWeights(double)} once every
     * layer's deltas have been computed against the pre-update weights.
     */
    public double[] computeDeltas(double[] nextDeltas, Layer next) {
        int nextNeurons = next.getNeuronCount();
        int count = neurons.size();
        double[] result = new double[count];
        for (int i = 0; i < count; i++) {
            double sum = 0.0;
            for (int j = 0; j < nextNeurons; j++) {
                sum += next.getNeuronAt(j).getWeightAt(i) * nextDeltas[j];
            }
            result[i] = sum * activation.derivative(outputs[i]);
        }
        this.deltas = result;
        fireDeltas();
        return result;
    }

    /** Gradient-descent step for this layer from its current deltas. */
    public void updateWeights(double learningRate) {
        for (int i = 0; i < neurons.size(); i++) {
            Neuron neuron = neurons.get(i);
            double delta = deltas[i];
            neuron.setBias(neuron.getBias() - learningRate * delta);
            for (int j = 0; j < inputs.length; j++) {
                neuron.setWeightAt(j, neuron.getWeightAt(j) - learningRate * delta * inputs[j]);
            }
        }
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

    private void fireDeltas() {
        if (propertyChangeSupport.hasListeners("deltas")) {
            propertyChangeSupport.firePropertyChange("deltas", null, deltas.clone());
        }
    }

    private static double[] softmax(double[] sums) {
        double max = Double.NEGATIVE_INFINITY;
        for (double sum : sums) {
            max = Math.max(max, sum);
        }
        double[] exps = new double[sums.length];
        double total = 0.0;
        for (int i = 0; i < sums.length; i++) {
            exps[i] = Math.exp(sums[i] - max);
            total += exps[i];
        }
        for (int i = 0; i < exps.length; i++) {
            exps[i] /= total;
        }
        return exps;
    }
}