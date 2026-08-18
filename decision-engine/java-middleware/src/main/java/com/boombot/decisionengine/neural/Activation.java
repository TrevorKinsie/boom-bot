package com.boombot.decisionengine.neural;

/**
 * Activation-function catalogue for the neural engine.
 *
 * <p>Each member is a JavaBean property value of a {@link Layer}: the layer
 * applies {@link #apply(double)} to every pre-activation sum, and {@link
 * #derivative(double)} is used during backpropagation on the post-activation
 * value. {@link #SOFTMAX} is a vector operation handled inside the layer
 * (its per-element derivative is not well defined, so it is only supported on
 * the final layer of a network).</p>
 */
public enum Activation {

    /** Linear pass-through. */
    IDENTITY {
        @Override
        public double apply(double x) {
            return x;
        }

        @Override
        public double derivative(double output) {
            return 1.0;
        }
    },

    /** Logistic sigmoid, well suited to bounded output probabilities. */
    SIGMOID {
        @Override
        public double apply(double x) {
            return 1.0 / (1.0 + Math.exp(-x));
        }

        @Override
        public double derivative(double output) {
            return output * (1.0 - output);
        }
    },

    /** Hyperbolic tangent, useful for hidden layers around zero. */
    TANH {
        @Override
        public double apply(double x) {
            return Math.tanh(x);
        }

        @Override
        public double derivative(double output) {
            return 1.0 - output * output;
        }
    },

    /** Rectified linear unit. */
    RELU {
        @Override
        public double apply(double x) {
            return Math.max(0.0, x);
        }

        @Override
        public double derivative(double output) {
            return output > 0.0 ? 1.0 : 0.0;
        }
    },

    /** Softmax over a layer's pre-activation sums (vector form, see {@link Layer#forward}). */
    SOFTMAX {
        @Override
        public double apply(double x) {
            return x;
        }

        @Override
        public double derivative(double output) {
            return 1.0;
        }
    };

    /** Apply the activation to a single pre-activation sum. */
    public abstract double apply(double x);

    /** Derivative with respect to the post-activation value. */
    public abstract double derivative(double output);
}