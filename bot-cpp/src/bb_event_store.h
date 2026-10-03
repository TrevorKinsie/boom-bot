/*
 * bb_event_store.h - append-only JSON Lines domain event store.
 *
 * Mirrors boombot/casino/infrastructure/eventsourcing/json_event_store.py and
 * the wallet event wire format from application/event/domain_event.py:
 * each log line is
 *   {"event_id","aggregate_id","occurred_on","version","event_type","payload"}
 * with ensure_ascii=False (raw UTF-8); snapshots live in
 * <logfile>.snapshots/<aggregate_id>.json as {"version": N, "state": {...}}
 * with indent=2.
 */
#ifndef BB_EVENT_STORE_H
#define BB_EVENT_STORE_H

#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "bb_json.h"

namespace bb {

// Current UTC time in Python isoformat() style:
// "2026-08-18T13:20:07.123456+00:00" (microseconds, +00:00 offset).
std::string utc_now_iso();

// uuid4-style random identifier: "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".
std::string random_uuid();

// A single wallet domain event after deserialization.
struct WalletEvent {
    std::string event_id;
    std::string aggregate_id;
    std::string occurred_on;
    int64_t version = 0;
    std::string event_type;
    Json payload;

    static WalletEvent create(const std::string& type, const std::string& aggregate_id,
                              int64_t version, Json payload);

    // Event envelope; payload remains a separate key, matching Python.
    Json to_record() const;

    static WalletEvent from_record(const Json& record);

    // Typed payload accessors (amounts are decimal strings).
    std::string amount() const;
    int64_t amount_cents() const;
    std::string reason() const;
    std::string starting_balance() const;
    int64_t starting_balance_cents() const;
    std::string reset_balance() const;
    int64_t reset_balance_cents() const;
    int64_t count() const;
    int64_t wager_cents() const;
    int64_t win_cents() const;
    std::string game() const;
};

// Snapshot policy: take a snapshot when committed + staged reaches threshold.
class SnapshotPolicy {
public:
    explicit SnapshotPolicy(int64_t threshold = 50) : threshold_(threshold) {}
    bool should_take_snapshot(int64_t uncommitted_count, int64_t committed_version) const {
        return committed_version + uncommitted_count >= threshold_;
    }
    int64_t threshold() const { return threshold_; }

private:
    int64_t threshold_;
};

// Append-only JSONL event store with per-aggregate snapshot files.
class JsonEventStore {
public:
    JsonEventStore(std::string log_path, std::string snapshot_dir);

    const std::string& log_path() const { return log_path_; }
    const std::string& snapshot_dir() const { return snapshot_dir_; }

    void append(const std::string& aggregate_id, const std::vector<WalletEvent>& events);
    // Events for one aggregate, in log order. Replay sorts by version.
    std::vector<WalletEvent> load(const std::string& aggregate_id) const;
    // Every event in the log, in log order (leaderboard replay).
    std::vector<WalletEvent> load_all_events() const;

    void save_snapshot(const std::string& aggregate_id, int64_t version, const Json& state);
    std::optional<std::pair<int64_t, Json>> load_snapshot(const std::string& aggregate_id) const;

private:
    std::string log_path_;
    std::string snapshot_dir_;
};

} // namespace bb

#endif // BB_EVENT_STORE_H