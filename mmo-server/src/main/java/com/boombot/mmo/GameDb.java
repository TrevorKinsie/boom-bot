package com.boombot.mmo;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * SQLite persistence for the game/world state (players + resources), separate
 * from the shared wallet store. WAL mode + a busy timeout let the service
 * coexist with other writers on the same volume.
 *
 * <p>All mutations funnel through {@link World} (synchronized), so connection
 * use is inherently serialized and safe without extra locking.
 */
public final class GameDb {
    private final Connection conn;

    public GameDb(String path) {
        path = (path == null || path.isBlank()) ? defaultGameDbPath() : path;
        com.boombot.mmo.Util.mkdirsFor(path);
        try {
            Class.forName("org.sqlite.JDBC");
        } catch (ClassNotFoundException cnfe) {
            throw new IllegalStateException("SQLite JDBC driver not on classpath.", cnfe);
        }
        try {
            this.conn = DriverManager.getConnection("jdbc:sqlite:" + path);
            try (Statement st = conn.createStatement()) {
                st.execute("PRAGMA journal_mode=WAL");
                st.execute("PRAGMA busy_timeout=5000");
            }
            createSchema();
        } catch (SQLException e) {
            throw new IllegalStateException("Cannot open game database " + path + ": " + e.getMessage(), e);
        }
    }

    public static String defaultGameDbPath() {
        String env = System.getenv("MMO_GAME_DB");
        if (env != null && !env.isBlank()) {
            return env;
        }
        return "data/mmo.sqlite3";
    }

    private void createSchema() throws SQLException {
        try (Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE IF NOT EXISTS players ("
                    + "id TEXT PRIMARY KEY,"
                    + "name TEXT NOT NULL,"
                    + "token TEXT NOT NULL,"
                    + "x REAL NOT NULL, y REAL NOT NULL,"
                    + "tx REAL NOT NULL, ty REAL NOT NULL,"
                    + "moving INTEGER NOT NULL,"
                    + "hp REAL NOT NULL,"
                    + "gold_cents INTEGER NOT NULL,"
                    + "skills TEXT NOT NULL,"
                    + "inventory TEXT NOT NULL,"
                    + "bank TEXT NOT NULL,"
                    + "last_seen INTEGER NOT NULL)");
            st.execute("CREATE TABLE IF NOT EXISTS resources ("
                    + "id TEXT PRIMARY KEY,"
                    + "type TEXT NOT NULL,"
                    + "x REAL NOT NULL, y REAL NOT NULL,"
                    + "amount INTEGER NOT NULL,"
                    + "max_amount INTEGER NOT NULL,"
                    + "restore_at INTEGER NOT NULL)");
        }
    }

    public void loadResources(Map<String, Resource> out) {
        out.clear();
        long now = System.currentTimeMillis();
        String sql = "SELECT id,type,x,y,amount,max_amount,restore_at FROM resources";
        try (Statement st = conn.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            while (rs.next()) {
                String type = rs.getString("type");
                Resource.Type t = "tree".equals(type) ? Resource.Type.TREE : Resource.Type.ROCK;
                long max = rs.getLong("max_amount");
                Resource r = new Resource(rs.getString("id"), t,
                        rs.getDouble("x"), rs.getDouble("y"), max);
                r.amount = rs.getLong("amount");
                r.restoreAtMillis = rs.getLong("restore_at");
                if (r.restoreAtMillis > 0 && now >= r.restoreAtMillis) {
                    r.amount = max;
                    r.restoreAtMillis = 0;
                }
                out.put(r.id, r);
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to load resources: " + e.getMessage(), e);
        }
}
public void loadPlayers(Map<String, Player> out) {
        out.clear();
        String sql = "SELECT id,name,token,x,y,tx,ty,moving,hp,gold_cents,"
                + "skills,inventory,bank,last_seen FROM players";
        try (Statement st = conn.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            while (rs.next()) {
                Player p = new Player(rs.getString("id"));
                p.name = rs.getString("name");
                p.token = rs.getString("token");
                p.x = rs.getDouble("x");
                p.y = rs.getDouble("y");
                p.tx = rs.getDouble("tx");
                p.ty = rs.getDouble("ty");
                p.moving = rs.getInt("moving") != 0;
                p.hp = rs.getDouble("hp");
                p.goldCents = rs.getLong("gold_cents");
                p.lastSeenMillis = rs.getLong("last_seen");
                Map<String, Object> skills = Util.asMap(Json.parse(rs.getString("skills")));
                p.miningXp = Util.numDouble(skills.get("mining"));
                p.woodcuttingXp = Util.numDouble(skills.get("woodcutting"));
                Map<String, Object> inv = Util.asMap(Json.parse(rs.getString("inventory")));
                for (Map.Entry<String, Object> e : inv.entrySet()) {
                    p.inventory.put(e.getKey(), Util.numLong(e.getValue()));
                }
                Map<String, Object> bank = Util.asMap(Json.parse(rs.getString("bank")));
                for (Map.Entry<String, Object> e : bank.entrySet()) {
                    p.bank.put(e.getKey(), Util.numLong(e.getValue()));
                }
                out.put(p.id, p);
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to load players: " + e.getMessage(), e);
        }
    }
public void saveAll(Map<String, Player> players, Map<String, Resource> resources) {
        try {
            conn.setAutoCommit(false);
            try (PreparedStatement ps = conn.prepareStatement(
                    "INSERT OR REPLACE INTO players "
                    + "(id,name,token,x,y,tx,ty,moving,hp,gold_cents,skills,inventory,bank,last_seen) "
                    + "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")) {
                for (Player p : players.values()) {
                    ps.setString(1, p.id);
                    ps.setString(2, p.name);
                    ps.setString(3, p.token);
                    ps.setDouble(4, p.x);
                    ps.setDouble(5, p.y);
                    ps.setDouble(6, p.tx);
                    ps.setDouble(7, p.ty);
                    ps.setInt(8, p.moving ? 1 : 0);
                    ps.setDouble(9, p.hp);
                    ps.setLong(10, p.goldCents);
                    ps.setString(11, Json.write(p.skillsJson()));
                    ps.setString(12, Json.write(p.inventory));
                    ps.setString(13, Json.write(p.bank));
                    ps.setLong(14, p.lastSeenMillis);
                    ps.addBatch();
                }
                ps.executeBatch();
            }
            try (PreparedStatement ps = conn.prepareStatement(
                    "INSERT OR REPLACE INTO resources "
                    + "(id,type,x,y,amount,max_amount,restore_at) VALUES (?,?,?,?,?,?,?)")) {
                for (Resource r : resources.values()) {
                    ps.setString(1, r.id);
                    ps.setString(2, r.type.name().toLowerCase());
                    ps.setDouble(3, r.x);
                    ps.setDouble(4, r.y);
                    ps.setLong(5, r.amount);
                    ps.setLong(6, r.maxAmount);
                    ps.setLong(7, r.restoreAtMillis);
                    ps.addBatch();
                }
                ps.executeBatch();
            }
            conn.commit();
        } catch (SQLException e) {
            try {
                conn.rollback();
            } catch (SQLException ignored) {
            }
            throw new IllegalStateException("Failed to persist world state: " + e.getMessage(), e);
        } finally {
            try {
                conn.setAutoCommit(true);
            } catch (SQLException ignored) {
            }
        }
    }

    public void close() {
        try {
            conn.close();
        } catch (SQLException ignored) {
        }
    }
}
