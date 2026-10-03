package com.boombot.mmo;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * {@code WalletDb} is the Java writer for the <b>shared wallet</b>.
 *
 * It appends wallet <i>domain events</i> to the exact same {@code casino_events}
 * SQLite table the boom-bot casino microkernel uses as its append-only event
 * store (aggregate id {@code mmo:<player>}), using the same JSON schema the
 * {@code boombot.casino} Python side deserializes. Banked coins / item-sale
 * proceeds therefore live in the one shared wallet ledger rather than a private
 * MMO economy — a Python reader can replay the exact same events.
 *
 * <p>Schema compatibility matters: rows use columns
 * {@code (event_id, aggregate_id, occurred_on, version, event_type, payload_json)}
 * where {@code payload_json} is the full {@code event.to_dictionary()} including
 * {@code event_type} and {@code payload}. Version numbers are per-aggregate
 * optimistically-locked (table has {@code UNIQUE(aggregate_id, version)}),
 * matching the Python adapter's concurrent-write guard.
 */
public final class WalletDb {
    private static final DateTimeFormatter OCCURRED =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSSSSxxx");

    private final Connection conn;

    public WalletDb(String path) {
        path = (path == null || path.isBlank()) ? defaultWalletDbPath() : path;
        Util.mkdirsFor(path);
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
            throw new IllegalStateException("Cannot open shared wallet store " + path + ": " + e.getMessage(), e);
        }
    }

    public static String defaultWalletDbPath() {
        String env = System.getenv("MMO_WALLET_DB");
        if (env != null && !env.isBlank()) {
            return env;
        }
        return "data/casino.sqlite3";
    }

    /** Idempotently mirrors the Python event store schema. */
    private void createSchema() throws SQLException {
        try (Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE IF NOT EXISTS casino_events ("
                    + "event_id TEXT PRIMARY KEY,"
                    + "aggregate_id TEXT NOT NULL,"
                    + "occurred_on TEXT NOT NULL,"
                    + "version INTEGER NOT NULL,"
                    + "event_type TEXT NOT NULL,"
                    + "payload_json TEXT NOT NULL,"
                    + "UNIQUE(aggregate_id, version))");
            st.execute("CREATE INDEX IF NOT EXISTS idx_casino_events_aggregate "
                    + "ON casino_events (aggregate_id, version)");
            st.execute("CREATE TABLE IF NOT EXISTS casino_snapshots ("
                    + "aggregate_id TEXT PRIMARY KEY,"
                    + "version INTEGER NOT NULL,"
                    + "state_json TEXT NOT NULL)");
        }
    }

    // ------------------------------------------------------------------
    // Public wallet operations
    // ------------------------------------------------------------------

    public synchronized void ensureWallet(String aggregateId) {
        if (!hasEvents(aggregateId)) {
            appendEvent(aggregateId, "WalletCreatedEvent",
                    Map.of("starting_balance", "0.00"));
        }
}
public synchronized void credit(String aggregateId, long cents, String reason) {
        if (cents <= 0) {
            throw new ApiException(400, "Amount must be positive.");
        }
        ensureWallet(aggregateId);
        appendEvent(aggregateId, "FundsCreditedEvent",
                Map.of("amount", formatCents(cents), "reason", reason));
    }

    public synchronized void debit(String aggregateId, long cents, String reason) {
        if (cents <= 0) {
            throw new ApiException(400, "Amount must be positive.");
        }
        ensureWallet(aggregateId);
        if (balanceCentsUnchecked(aggregateId) < cents) {
            throw new ApiException(400, "Insufficient wallet funds.");
        }
        appendEvent(aggregateId, "FundsDebitedEvent",
                Map.of("amount", formatCents(cents), "reason", reason));
    }

    public synchronized long balanceCents(String aggregateId) {
        return balanceCentsUnchecked(aggregateId);
    }

    // ------------------------------------------------------------------
    // Internals
    // ------------------------------------------------------------------

    private boolean hasEvents(String aggregateId) {
        String sql = "SELECT 1 FROM casino_events WHERE aggregate_id = ? LIMIT 1";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, aggregateId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to inspect wallet: " + e.getMessage(), e);
        }
    }

    private long balanceCentsUnchecked(String aggregateId) {
        long balance = 0;
        String sql = "SELECT event_type, payload_json FROM casino_events "
                + "WHERE aggregate_id = ? ORDER BY version ASC";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, aggregateId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    String type = rs.getString("event_type");
                    Map<String, Object> payload = readPayload(rs.getString("payload_json"));
                    if ("WalletCreatedEvent".equals(type)
                            || "FundsCreditedEvent".equals(type)) {
                        String field = "WalletCreatedEvent".equals(type)
                                ? "starting_balance" : "amount";
                        balance += centsFromAmount(str(payload.get(field)));
                    } else if ("FundsDebitedEvent".equals(type)) {
                        balance -= centsFromAmount(str(payload.get("amount")));
                    }
                }
            }
            return balance;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to read wallet balance: " + e.getMessage(), e);
        }
    }

    private static String str(Object o) {
        return o == null ? "0" : o.toString();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> readPayload(String payloadJson) {
        Map<String, Object> event = (Map<String, Object>) Json.parse(payloadJson);
        Object p = event.get("payload");
        return p instanceof Map ? (Map<String, Object>) p : new LinkedHashMap<>();
    }
/**
     * Append a single wallet event to the shared store with a Python-compatible
     * record, using an immediate transaction + the uniqueness constraint to
     * detect concurrent writes. Retries up to twice on a busy/conflict write.
     */
    private void appendEvent(String aggregateId, String eventType, Map<String, Object> payload) {
        for (int attempt = 0; attempt < 3; attempt++) {
            try {
                conn.setAutoCommit(false);
                int version = maxVersion(aggregateId) + 1;

                Map<String, Object> record = new LinkedHashMap<>();
                record.put("event_id", UUID.randomUUID().toString());
                record.put("aggregate_id", aggregateId);
                record.put("occurred_on", OCCURRED.format(OffsetDateTime.now(ZoneOffset.UTC)));
                record.put("version", version);
                record.put("event_type", eventType);
                record.put("payload", payload);

                try (PreparedStatement ps = conn.prepareStatement(
                        "INSERT INTO casino_events "
                        + "(event_id, aggregate_id, occurred_on, version, event_type, payload_json) "
                        + "VALUES (?, ?, ?, ?, ?, ?)")) {
                    ps.setString(1, str(record.get("event_id")));
                    ps.setString(2, aggregateId);
                    ps.setString(3, str(record.get("occurred_on")));
                    ps.setInt(4, version);
                    ps.setString(5, eventType);
                    ps.setString(6, Json.write(record));
                    ps.executeUpdate();
                }
                conn.commit();
                return;
            } catch (SQLException e) {
                try {
                    conn.rollback();
                } catch (SQLException ignored) {
                }
                if (e.getMessage() != null && e.getMessage().contains("UNIQUE")
                        && attempt < 2) {
                    continue; // concurrent write landed first; recompute version
                }
                throw new IllegalStateException(
                        "Failed to append wallet event " + eventType + ": " + e.getMessage(), e);
            } finally {
                try {
                    conn.setAutoCommit(true);
                } catch (SQLException ignored) {
                }
            }
        }
    }

    private int maxVersion(String aggregateId) {
        String sql = "SELECT MAX(version) AS m FROM casino_events WHERE aggregate_id = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, aggregateId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? rs.getInt("m") : 0;
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to read wallet version: " + e.getMessage(), e);
        }
    }

    public static String formatCents(long cents) {
        long whole = cents / 100;
        long frac = Math.abs(cents % 100);
        return whole + "." + (frac < 10 ? "0" : "") + frac;
    }

    static long centsFromAmount(String s) {
        if (s == null || s.isEmpty()) {
            return 0;
        }
        int dot = s.indexOf('.');
        String whole = dot < 0 ? s : s.substring(0, dot);
        String frac = dot < 0 ? "00" : s.substring(dot + 1);
        while (frac.length() < 2) {
            frac += "0";
        }
        if (frac.length() > 2) {
            frac = frac.substring(0, 2);
        }
        long sign = whole.startsWith("-") ? -1 : 1;
        String w = whole.startsWith("-") ? whole.substring(1) : whole;
        return sign * (Long.parseLong(w) * 100 + Long.parseLong(frac));
    }

    public void close() {
        try {
            conn.close();
        } catch (SQLException ignored) {
        }
    }
}
