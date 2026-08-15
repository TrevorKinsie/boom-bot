package com.boombot.mmo;

import java.util.LinkedHashMap;
import java.util.Map;

/** A single persistent player character in the MMO world. */
public final class Player {
    public static final double MAX_HP = 100.0;

    public final String id;
    public String name;
    public String token;

    public double x;
    public double y;
    public double tx;
    public double ty;
    public boolean moving;

    public double hp;
    public double miningXp;
    public double woodcuttingXp;

    /** item id -> quantity carried on the character. */
    public final Map<String, Long> inventory = new LinkedHashMap<>();
    /** item id -> quantity stored at the bank. */
    public final Map<String, Long> bank = new LinkedHashMap<>();
    /** loose coins carried (not yet banked into the shared wallet). */
    public long goldCents;

    public String gatheringResourceId;
    public double gatherProgress;

    public long lastSeenMillis;

    Player(String id) {
        this.id = id;
        this.hp = MAX_HP;
    }

    public int level(double xp) {
        return (int) (xp / 100.0) + 1;
    }

    public int level() {
        return Math.max(miningLevel(), woodcuttingLevel());
    }

    public int miningLevel() {
        return level(miningXp);
    }

    public int woodcuttingLevel() {
        return level(woodcuttingXp);
    }

    public long inventoryQty(String item) {
        return inventory.getOrDefault(item, 0L);
    }

    public long bankQty(String item) {
        return bank.getOrDefault(item, 0L);
    }

    public void giveItem(String item, long qty) {
        inventory.put(item, inventoryQty(item) + qty);
    }

    public Map<String, Object> skillsJson() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("mining", miningXp);
        m.put("woodcutting", woodcuttingXp);
        return m;
    }
}