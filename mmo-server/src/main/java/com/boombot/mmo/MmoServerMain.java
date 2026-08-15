package com.boombot.mmo;

/**
 * Entry point for the boom-bot MMO game service.
 *
 * Wires the SQLite game store and the shared wallet store into a {@link World},
 * starts a tick thread (motion, gathering, respawn, periodic persistence), and
 * serves the browser client + REST API over HTTP.
 */
public final class MmoServerMain {

    public static void main(String[] args) throws Exception {
        int port = intEnv("MMO_PORT", 8080);
        String bind = env("MMO_BIND", "127.0.0.1");
        String gameDbPath = env("MMO_GAME_DB", null);
        String walletDbPath = env("MMO_WALLET_DB", null);

        GameDb gameDb = new GameDb(gameDbPath);
        WalletDb walletDb = new WalletDb(walletDbPath);
        World world = new World(gameDb, walletDb);
        // Persist the initial (possibly freshly seeded) world immediately.
        world.flushNow();

        Thread ticker = new Thread(() -> runTicker(world, gameDb), "mmo-ticker");
        ticker.setDaemon(true);
        ticker.start();

        HttpApi api = new HttpApi(bind, port, world);
        api.start();

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                world.flushNow();
            } catch (Throwable t) {
                System.err.println("Failed to flush world on shutdown: " + t);
            }
            try {
                gameDb.close();
            } catch (Throwable ignored) {
            }
            try {
                walletDb.close();
            } catch (Throwable ignored) {
            }
        }));

        System.out.println("┌────────────────────────────────────────────┐");
        System.out.println("  boom-bot MMO game service");
        System.out.println("  listen : http://" + bind + ":" + port);
        System.out.println("  gameDb : " + gameDbPath);
        System.out.println("  wallet : " + walletDbPath + " (shared casino_events store)");
        System.out.println("└────────────────────────────────────────────┘");
    }

    private static void runTicker(World world, GameDb gameDb) {
        long last = System.nanoTime();
        long lastFlush = System.currentTimeMillis();
        while (!Thread.currentThread().isInterrupted()) {
            long now = System.nanoTime();
            double dt = Math.max(0.0, (now - last) / 1e9);
            last = now;
            try {
                world.tick(Math.min(dt, 0.25));
            } catch (Throwable t) {
                System.err.println("Tick error: " + t);
                t.printStackTrace();
            }
            long nowMs = System.currentTimeMillis();
            if (nowMs - lastFlush >= 4000) {
                try {
                    world.flush();
                } catch (Throwable t) {
                    System.err.println("Flush error: " + t);
                }
                lastFlush = nowMs;
            }
            try {
                Thread.sleep(40);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    private static int intEnv(String key, int def) {
        String v = System.getenv(key);
        if (v == null || v.isBlank()) {
            return def;
        }
        return Integer.parseInt(v.trim());
    }

    private static String env(String key, String def) {
        String v = System.getenv(key);
        return (v == null || v.isBlank()) ? def : v;
    }
}