package com.boombot.mmo;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.UUID;

/**
 * The persistent MMO world: a tile map, resource nodes, and players.
 *
 * The whole mutable state of the world lives here and is guarded by the monitor
 * on {@code this}. The server tick thread advances motion/gathering/respawn and
 * {@link GameDb} writes it all out to SQLite (write-through on actions,
 * periodic flush from the tick thread) so the world survives restarts.
 *
 * <p>Economy calls are routed to {@link WalletDb} so coins are held in the same
 * event-sourced wallet the rest of the platform shares (aggregate {@code mmo:<id>}).
 */
public final class World {
    public static final int WIDTH = 72;
    public static final int HEIGHT = 72;

    // Tile type codes (kept as bytes in the payload to keep it small).
    public static final int T_GRASS = 0;
    public static final int T_WATER = 1;
    public static final int T_PATH = 2;
    public static final int T_ROCK = 3;
    public static final int T_BANK = 4;

    // Economic constants.
    public static final int LOG_PRICE_CENTS = 200;
    public static final int ORE_PRICE_CENTS = 500;
    public static final double XP_PER_GATHER = 15.0;
    public static final double GATHER_INTERVAL_SECONDS = 1.2;
    public static final double GATHER_RANGE = 3.0;
    public static final double MOVE_SPEED = 7.0;
    public static final long RESPAWN_MS = 20_000L;

    public static final double SPAWN_X = 3.0;
    public static final double SPAWN_Y = 3.0;
    public static final double BANK_X = 10.0;
    public static final double BANK_Y = 10.0;

    private final int[] tiles = new int[WIDTH * HEIGHT];
    private final Map<String, Player> players = new HashMap<>();
    private final Map<String, Resource> resources = new LinkedHashMap<>();

    private final GameDb gameDb;
    private final WalletDb walletDb;

    private long dirtySinceFlush = 0;

    public World(GameDb gameDb, WalletDb walletDb) {
        this.gameDb = gameDb;
        this.walletDb = walletDb;
        generate();
        loadPersisted();
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    public static int tileIndex(double x, double y) {
        int cx = clamp((int) Math.floor(x), 0, WIDTH - 1);
        int cy = clamp((int) Math.floor(y), 0, HEIGHT - 1);
        return cy * WIDTH + cx;
    }

    private static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    public int tileAt(double x, double y) {
        return tiles[tileIndex(x, y)];
    }

    private boolean walkable(double x, double y) {
        int t = tileAt(x, y);
        return t != T_WATER && t != T_ROCK;
    }

    private static double dist(double ax, double ay, double bx, double by) {
        double dx = ax - bx;
        double dy = ay - by;
        return Math.sqrt(dx * dx + dy * dy);
    }

    // ------------------------------------------------------------------
    // Deterministic world generation
    // ------------------------------------------------------------------

    private void generate() {
        // Flat grass everywhere.
        for (int i = 0; i < tiles.length; i++) {
            tiles[i] = T_GRASS;
        }
        Random rng = new Random(20260815L);

        // Central lake (un-walkable water).
        for (int y = 26; y <= 46; y++) {
            for (int x = 26; x <= 46; x++) {
                tiles[y * WIDTH + x] = T_WATER;
            }
        }

        // Spawn plaza + bank cleared as path tiles.
        tileArea(1, 1, 5, 5, T_PATH);
        tileArea(8, 8, 12, 12, T_PATH);
        // Path corridor linking spawn to the bank.
        for (int x = 2; x <= 12; x++) {
            tiles[9 * WIDTH + x] = T_PATH;
        }
        for (int y = 2; y <= 9; y++) {
            tiles[y * WIDTH + 12] = T_PATH;
        }
        // Bank building sits on T_PATH -> mark its footprint T_BANK.
        tileArea(9, 9, 11, 11, T_BANK);

        // Scatter decorative obstacle rocks on grass (un-walkable), away from
        // the spawn/bank plazas.
        int rocks = 0;
        while (rocks < 60) {
            int x = rng.nextInt(WIDTH);
            int y = rng.nextInt(HEIGHT);
            if (tiles[y * WIDTH + x] != T_GRASS) {
                continue;
            }
            tiles[y * WIDTH + x] = T_ROCK;
            rocks++;
        }
    }

    private void tileArea(int x0, int y0, int x1, int y1, int type) {
        for (int y = y0; y <= y1; y++) {
            for (int x = x0; x <= x1; x++) {
                if (x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT) {
                    tiles[y * WIDTH + x] = type;
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Persistence hooks
    // ------------------------------------------------------------------

    private void loadPersisted() {
        gameDb.loadResources(resources);
        gameDb.loadPlayers(players);
        spawnInitialResourcesIfNeeded();
        // Any player who was mid-move when the service stopped resumes motion.
        for (Player p : players.values()) {
            p.lastSeenMillis = System.currentTimeMillis();
        }
    }
// ------------------------------------------------------------------
    // Players
    // ------------------------------------------------------------------

    public synchronized Player findPlayerByToken(String token) {
        if (token == null) {
            return null;
        }
        for (Player p : players.values()) {
            if (token.equals(p.token)) {
                return p;
            }
        }
        return null;
    }

    public synchronized Player joinOrResume(String name, String token) {
        if (token != null) {
            Player existing = findPlayerByToken(token);
            if (existing != null) {
                existing.lastSeenMillis = System.currentTimeMillis();
                ensureWallet(existing);
                return existing;
            }
        }
        Player p = new Player("mmo-p-" + UUID.randomUUID().toString().substring(0, 8));
        p.name = (name == null || name.isBlank()) ? "Adventurer" : name.trim();
        p.token = UUID.randomUUID().toString();
        p.x = SPAWN_X;
        p.y = SPAWN_Y;
        p.moving = false;
        p.lastSeenMillis = System.currentTimeMillis();
        players.put(p.id, p);
        ensureWallet(p);
        markDirty();
        return p;
    }

    private void ensureWallet(Player p) {
        walletDb.ensureWallet("mmo:" + p.id);
    }

    public Map<String, Player> players() {
        return players;
    }

    public Map<String, Resource> resources() {
        return resources;
    }

    // ------------------------------------------------------------------
    // Resource seeding (fresh world only)
    // ------------------------------------------------------------------

    private synchronized void spawnInitialResourcesIfNeeded() {
        if (!resources.isEmpty()) {
            return;
        }
        Random rng = new Random(898989L);
        int treeCount = 0;
        int rockCount = 0;
        int guard = 0;
        while ((treeCount < 45 || rockCount < 28) && guard++ < 20000) {
            int x = rng.nextInt(WIDTH);
            int y = rng.nextInt(HEIGHT);
            if (tiles[y * WIDTH + x] != T_GRASS) {
                continue;
            }
            if (dist(x + 0.5, y + 0.5, SPAWN_X, SPAWN_Y) < 4) {
                continue;
            }
            if (dist(x + 0.5, y + 0.5, BANK_X, BANK_Y) < 4) {
                continue;
            }
            boolean tree = treeCount < 45;
            String type = tree ? "tree" : "rock";
            String id = "r-" + type + "-" + (tree ? treeCount : rockCount);
            double cx = x + 0.5;
            double cy = y + 0.5;
            long maxAmount = tree ? 8 : 5;
            Resource r = new Resource(id, tree ? Resource.Type.TREE : Resource.Type.ROCK,
                    cx, cy, maxAmount);
            resources.put(id, r);
            if (tree) {
                treeCount++;
            } else {
                rockCount++;
            }
        }
        markDirty();
    }
// ------------------------------------------------------------------
    // Simulation tick (called from the server thread at ~20 Hz)
    // ------------------------------------------------------------------

    public synchronized void tick(double dt) {
        long nowMs = System.currentTimeMillis();

        // Respawn depleted resources.
        boolean anyRespawn = false;
        for (Resource r : resources.values()) {
            if (r.restoreAtMillis > 0 && nowMs >= r.restoreAtMillis) {
                r.amount = r.maxAmount;
                r.restoreAtMillis = 0;
                anyRespawn = true;
            }
        }
        if (anyRespawn) {
            markDirty();
        }

        for (Player p : players.values()) {
            p.lastSeenMillis = nowMs;

            if (p.moving) {
                advanceMotion(p, dt);
            }
            if (p.gatheringResourceId != null) {
                advanceGathering(p, dt);
            }
        }
    }

    private void advanceMotion(Player p, double dt) {
        double dx = p.tx - p.x;
        double dy = p.ty - p.y;
        double d = Math.sqrt(dx * dx + dy * dy);
        if (d < 0.05) {
            p.moving = false;
            markDirty();
            return;
        }
        double dirX = dx / d;
        double dirY = dy / d;
        double remaining = MOVE_SPEED * dt;
        while (remaining > 1e-6) {
            double step = Math.min(0.25, remaining);
            double nx = p.x + dirX * step;
            double ny = p.y + dirY * step;
            if (!walkable(nx, ny) || nx < 0 || ny < 0 || nx >= WIDTH || ny >= HEIGHT) {
                p.moving = false;
                markDirty();
                return;
            }
            p.x = nx;
            p.y = ny;
            remaining -= step;
            if (dist(p.x, p.y, p.tx, p.ty) < 0.05) {
                p.tx = p.x;
                p.ty = p.y;
                p.moving = false;
                break;
            }
        }
        markDirty();
    }

    private void advanceGathering(Player p, double dt) {
        Resource r = resources.get(p.gatheringResourceId);
        if (r == null || !r.alive() || dist(p.x, p.y, r.x, r.y) > GATHER_RANGE) {
            p.gatheringResourceId = null;
            p.gatherProgress = 0;
            return;
        }
        p.gatherProgress += dt;
        if (p.gatherProgress < GATHER_INTERVAL_SECONDS) {
            return;
        }
        p.gatherProgress -= GATHER_INTERVAL_SECONDS;
        r.amount -= 1;
        String item = r.type == Resource.Type.TREE ? "logs" : "ore";
        if (r.type == Resource.Type.TREE) {
            p.woodcuttingXp += XP_PER_GATHER;
        } else {
            p.miningXp += XP_PER_GATHER;
        }
        p.giveItem(item, 1);
        if (r.amount <= 0) {
            r.amount = 0;
            r.restoreAtMillis = System.currentTimeMillis() + RESPAWN_MS;
            p.gatheringResourceId = null;
            p.gatherProgress = 0;
        }
        markDirty();
    }
// ------------------------------------------------------------------
    // Player actions (invoked from the HTTP API layer)
    // ------------------------------------------------------------------

    public synchronized void move(Player p, double tx, double ty) {
        tx = Math.max(0.5, Math.min(WIDTH - 0.5, tx));
        ty = Math.max(0.5, Math.min(HEIGHT - 0.5, ty));
        p.tx = tx;
        p.ty = ty;
        p.moving = true;
        p.gatheringResourceId = null;
        p.gatherProgress = 0;
        markDirty();
    }

    public synchronized void stop(Player p) {
        p.moving = false;
        p.gatheringResourceId = null;
        p.gatherProgress = 0;
        markDirty();
    }

    public synchronized void gather(Player p, String resourceId) {
        Resource r = resources.get(resourceId);
        if (r == null) {
            throw new ApiException(404, "Resource not found.");
        }
        if (!r.alive()) {
            throw new ApiException(409, "That resource is depleted; it will regrow soon.");
        }
        // You must be within reach to start gathering.
        if (dist(p.x, p.y, r.x, r.y) > GATHER_RANGE) {
            move(p, r.x, r.y);
            throw new ApiException(202, "Moving toward the resource; get closer to gather.");
        }
        p.moving = false;
        p.gatheringResourceId = r.id;
        p.gatherProgress = 0;
        markDirty();
    }

    public synchronized int bankItem(Player p, String item, long qty) {
        long have = p.inventoryQty(item);
        qty = Math.max(0, qty);
        if (qty <= 0) {
            throw new ApiException(400, "Quantity must be positive.");
        }
        if (have < qty) {
            throw new ApiException(400, "You only carry " + have + " " + item + ".");
        }
        p.inventory.put(item, have - qty);
        p.bank.put(item, p.bankQty(item) + qty);
        markDirty();
        return (int) qty;
    }

    public synchronized int withdrawItem(Player p, String item, long qty) {
        long have = p.bankQty(item);
        qty = Math.max(0, qty);
        if (qty <= 0) {
            throw new ApiException(400, "Quantity must be positive.");
        }
        if (have < qty) {
            throw new ApiException(400, "Bank holds only " + have + " " + item + ".");
        }
        p.bank.put(item, have - qty);
        p.giveItem(item, qty);
        markDirty();
        return (int) qty;
    }

    /** Sell items; the proceeds are credited straight to the shared wallet. */
    public synchronized long sell(Player p, String item, long qty) {
        long have = p.inventoryQty(item);
        qty = Math.max(0, qty);
        if (qty <= 0) {
            throw new ApiException(400, "Quantity must be positive.");
        }
        if (have < qty) {
            throw new ApiException(400, "You only carry " + have + " " + item + ".");
        }
        int unitPrice;
        switch (item) {
            case "logs": unitPrice = LOG_PRICE_CENTS; break;
            case "ore": unitPrice = ORE_PRICE_CENTS; break;
            default: throw new ApiException(400, "You cannot sell " + item + ".");
        }
        p.inventory.put(item, have - qty);
        long cents = unitPrice * qty;
        walletDb.credit("mmo:" + p.id, cents, "sell:" + qty + "x" + item);
        markDirty();
        return cents;
    }

    /** Deposit loose carrying coins into the shared wallet. */
    public synchronized long depositGold(Player p, long cents) {
        if (cents <= 0) {
            throw new ApiException(400, "Amount must be positive.");
        }
        if (p.goldCents < cents) {
            throw new ApiException(400, "You only carry " + p.goldCents + " coins.");
        }
        p.goldCents -= cents;
        walletDb.credit("mmo:" + p.id, cents, "deposit:gold");
        markDirty();
        return cents;
    }

    /** Withdraw coins from the shared wallet back into the hand. */
    public synchronized long withdrawGold(Player p, long cents) {
        if (cents <= 0) {
            throw new ApiException(400, "Amount must be positive.");
        }
        long balance = walletDb.balanceCents("mmo:" + p.id);
        if (balance < cents) {
            throw new ApiException(400, "Wallet has only " + balance + " coins.");
        }
        walletDb.debit("mmo:" + p.id, cents, "withdraw:gold");
        p.goldCents += cents;
        markDirty();
        return cents;
    }

    public long walletBalanceCents(Player p) {
        return walletDb.balanceCents("mmo:" + p.id);
    }
// ------------------------------------------------------------------
    // Snapshots for the client
    // ------------------------------------------------------------------

    public synchronized Map<String, Object> worldSnapshot() {
        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("w", WIDTH);
        snap.put("h", HEIGHT);
        snap.put("spawn", Map.of("x", SPAWN_X, "y", SPAWN_Y));
        snap.put("bank", Map.of("x", BANK_X, "y", BANK_Y));
        List<Integer> tileList = new ArrayList<>(tiles.length);
        for (int t : tiles) {
            tileList.add(t);
        }
        snap.put("tiles", tileList);
        return snap;
    }

    public synchronized Map<String, Object> gameSnapshot(String token) {
        Player self = findPlayerByToken(token);
        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("you", self == null ? null : playerView(self, true));
        snap.put("t", System.currentTimeMillis());

        List<Object> playersView = new ArrayList<>();
        for (Player p : players.values()) {
            playersView.add(playerView(p, p == self));
        }
        snap.put("players", playersView);

        List<Object> resourcesView = new ArrayList<>();
        for (Resource r : resources.values()) {
            Map<String, Object> rv = new LinkedHashMap<>();
            rv.put("id", r.id);
            rv.put("type", r.type.name().toLowerCase());
            rv.put("x", r.x);
            rv.put("y", r.y);
            rv.put("amount", r.amount);
            rv.put("maxAmount", r.maxAmount);
            rv.put("alive", r.alive());
            resourcesView.add(rv);
        }
        snap.put("resources", resourcesView);
        return snap;
    }

    private Map<String, Object> playerView(Player p, boolean includePrivate) {
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("id", p.id);
        v.put("name", p.name);
        v.put("x", round2(p.x));
        v.put("y", round2(p.y));
        v.put("moving", p.moving);
        v.put("miningLevel", p.miningLevel());
        v.put("woodcuttingLevel", p.woodcuttingLevel());
        if (includePrivate) {
            v.put("hp", round2(p.hp));
            v.put("maxHp", Player.MAX_HP);
            v.put("goldCents", p.goldCents);
            v.put("walletCents", walletBalanceCents(p));
            v.put("inventory", p.inventory);
            v.put("bank", p.bank);
            v.put("miningXp", round2(p.miningXp));
            v.put("woodcuttingXp", round2(p.woodcuttingXp));
            v.put("gathering", p.gatheringResourceId);
        }
        return v;
    }

    private static double round2(double v) {
        return Math.round(v * 100.0) / 100.0;
    }

    // ------------------------------------------------------------------
    // Persistence flush
    // ------------------------------------------------------------------

    private void markDirty() {
        dirtySinceFlush = System.currentTimeMillis();
    }

    public synchronized boolean wasDirty() {
        return dirtySinceFlush != 0;
    }

    public synchronized void flush() {
        if (dirtySinceFlush != 0) {
            gameDb.saveAll(players, resources);
            dirtySinceFlush = 0;
        }
    }

    public synchronized void flushNow() {
        gameDb.saveAll(players, resources);
        dirtySinceFlush = 0;
    }

    public void close() {
        flushNow();
    }
}