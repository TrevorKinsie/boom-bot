package com.boombot.mmo;

/** A gatherable resource node: a tree (logs) or rock (ore). */
public final class Resource {
    public enum Type { TREE, ROCK }

    public final String id;
    public final Type type;
    public final double x;
    public final double y;
    public final long maxAmount;
    public long amount;
    /** Epoch millis at which a depleted node respawns; 0 while alive. */
    public long restoreAtMillis;

    Resource(String id, Type type, double x, double y, long maxAmount) {
        this.id = id;
        this.type = type;
        this.x = x;
        this.y = y;
        this.maxAmount = maxAmount;
        this.amount = maxAmount;
    }

    public boolean alive() {
        return amount > 0;
    }
}