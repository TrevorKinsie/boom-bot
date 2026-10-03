package com.boombot.decisionengine.neural;

import java.beans.PropertyChangeListener;
import java.beans.PropertyChangeSupport;
import java.io.Serializable;

/**
 * A single neuron of the neural engine, implemented as a JavaBean.
 *
 * <p>Conforms to the JavaBeans conventions: public no-arg constructor, private
 * fields exposed through public getters/setters, a bound property for every
 * mutable value ({@code id}, {@code bias}, {@code weights}), standard
 * property-change listener management, and Java serialisation support so a
 * whole network of neurons can be persisted as a bean graph.</p>
 *
 * <p>The {@link PropertyChangeSupport} makes every learning step observable:
 * listeners attached to a neuron (directly or via {@link Layer} /
 * {@link NeuralNetwork} propagation) are notified whenever a weight or the
 * bias moves.</p>
 */
public class Neuron implements Serializable {

    private static final long serialVersionUID = 1L;

    private String id;
    private double bias;
    private double[] weights;

    private final PropertyChangeSupport propertyChangeSupport = new PropertyChangeSupport(this);

    /** Bean-friendly no-arg constructor: identity neuron with no inputs. */
    public Neuron() {
        this.id = "neuron";
        this.bias = 0.0;
        this.weights = new double[0];
    }

    /**
     * Full constructor. {@code weights} is defensively copied so the neuron's
     * bean state can never alias a caller-owned array.
     */
    public Neuron(String id, double bias, double[] weights) {
        this();
        this.id = id;
        this.bias = bias;
        this.weights = weights.clone();
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        String old = this.id;
        this.id = id;
        propertyChangeSupport.firePropertyChange("id", old, id);
    }

    public double getBias() {
        return bias;
    }

    public void setBias(double bias) {
        double old = this.bias;
        this.bias = bias;
        propertyChangeSupport.firePropertyChange("bias", old, bias);
    }

    /** Copy of the incoming weight vector. */
    public double[] getWeights() {
        return weights.clone();
    }

    public void setWeights(double[] weights) {
        double[] old = this.weights;
        this.weights = weights.clone();
        propertyChangeSupport.firePropertyChange("weights", old, this.weights);
    }

    /** Number of incoming connections (equals the previous layer's size). */
    public int getWeightCount() {
        return weights.length;
    }

    public double getWeightAt(int index) {
        return weights[index];
    }

    /** Bound property {@code weight}: fires a change event for the updated scalar. */
    public void setWeightAt(int index, double value) {
        double old = weights[index];
        weights[index] = value;
        propertyChangeSupport.firePropertyChange("weight", old, value);
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
}