/*
 * bb_event_store.cpp - see bb_event_store.h.
 */
#include "bb_event_store.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "bb_json.h"
#include "bb_money.h"

namespace bb {

std::string utc_now_iso() {
    using namespace std::chrono;
    system_clock::time_point now = system_clock::now();
    time_t seconds = system_clock::to_time_t(now);
    auto sub = duration_cast<microseconds>(now.time_since_epoch()) % 1000000;

    std::tm tm;
#if defined(_WIN32)
    gmtime_s(&tm, &seconds);
#else
    gmtime_r(&seconds, &tm);
#endif

    char buf[64];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d.%06ld+00:00",
                  tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min,
                  tm.tm_sec, static_cast<long>(sub.count()));
    return std::string(buf);
}

std::string random_uuid() {
    static thread_local std::mt19937_64 rng(
        std::random_device{}() ^ static_cast<uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count()));
    static const char* hex = "0123456789abcdef";
    std::string out;
    out.reserve(36);
    for (int i = 0; i < 36; ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            out.push_back('-');
            continue;
        }
        unsigned int r = static_cast<unsigned int>(rng() & 0xFF);
        char c;
        if (i == 14) {
            c = '4';
        } else if (i == 19) {
            // RFC 4122 variant bits: 10xx -> nibbles 8..b.
            c = hex[0x08 | (r & 0x03)];
        } else {
            c = hex[r & 0x0F];
        }
        out.push_back(c);
    }
    return out;
}

WalletEvent WalletEvent::create(const std::string& type, const std::string& aggregate_id,
                                int64_t version, Json payload) {
    WalletEvent event;
    event.event_id = random_uuid();
    event.aggregate_id = aggregate_id;
    event.occurred_on = utc_now_iso();
    event.version = version;
    event.event_type = type;
    event.payload = std::move(payload);
    return event;
}

Json WalletEvent::to_record() const {
    Json record = Json::object();
    record.set("event_id", event_id);
    record.set("aggregate_id", aggregate_id);
    record.set("occurred_on", occurred_on);
    record.set("version", version);
    record.set("event_type", event_type);
    record.set("payload", payload);
    return record;
}

WalletEvent WalletEvent::from_record(const Json& record) {
    WalletEvent event;
    event.event_id = record.get_string("event_id");
    event.aggregate_id = record.get_string("aggregate_id");
    event.occurred_on = record.get_string("occurred_on");
    event.version = record.get_int("version", 0);
    event.event_type = record.get_string("event_type");
    const Json* payload = record.find("payload");
    event.payload = payload ? *payload : Json::object();
    return event;
}

static std::string payload_string(const Json& payload, const char* key) {
    const Json* value = payload.find(key);
    if (!value || !value->is_string())
        return "";
    return value->as_string();
}

std::string WalletEvent::amount() const { return payload_string(payload, "amount"); }
int64_t WalletEvent::amount_cents() const { return decimal_to_cents(amount()); }
std::string WalletEvent::reason() const { return payload_string(payload, "reason"); }
std::string WalletEvent::starting_balance() const { return payload_string(payload, "starting_balance"); }
int64_t WalletEvent::starting_balance_cents() const { return decimal_to_cents(starting_balance()); }
std::string WalletEvent::reset_balance() const { return payload_string(payload, "reset_balance"); }
int64_t WalletEvent::reset_balance_cents() const { return decimal_to_cents(reset_balance()); }
int64_t WalletEvent::count() const {
    const Json* value = payload.find("count");
    return value && value->is_number() ? value->as_int() : 0;
}
int64_t WalletEvent::wager_cents() const { return decimal_to_cents(payload_string(payload, "wager")); }
int64_t WalletEvent::win_cents() const { return decimal_to_cents(payload_string(payload, "win")); }
std::string WalletEvent::game() const { return payload_string(payload, "game"); }

JsonEventStore::JsonEventStore(std::string log_path, std::string snapshot_dir)
    : log_path_(std::move(log_path)), snapshot_dir_(std::move(snapshot_dir)) {}

void JsonEventStore::append(const std::string& aggregate_id,
                            const std::vector<WalletEvent>& events) {
    if (events.empty())
        return;
    std::ofstream stream(log_path_, std::ios::app);
    if (!stream)
        throw std::runtime_error("Could not append events for aggregate " + aggregate_id);
    for (const WalletEvent& event : events) {
        stream << event.to_record().dump(-1) << "\n";
    }
    stream.close();
    if (!stream)
        throw std::runtime_error("Could not append events for aggregate " + aggregate_id);
}

std::vector<WalletEvent> JsonEventStore::load(const std::string& aggregate_id) const {
    std::vector<WalletEvent> events;
    std::ifstream stream(log_path_);
    if (!stream)
        return events;
    std::string line;
    while (std::getline(stream, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
            line.pop_back();
        if (line.empty())
            continue;
        Json record = Json::parse(line);
        if (record.get_string("aggregate_id") != aggregate_id)
            continue;
        events.push_back(WalletEvent::from_record(record));
    }
    return events;
}

std::vector<WalletEvent> JsonEventStore::load_all_events() const {
    std::vector<WalletEvent> events;
    std::ifstream stream(log_path_);
    if (!stream)
        return events;
    std::string line;
    while (std::getline(stream, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
            line.pop_back();
        if (line.empty())
            continue;
        events.push_back(WalletEvent::from_record(Json::parse(line)));
    }
    return events;
}

void JsonEventStore::save_snapshot(const std::string& aggregate_id, int64_t version,
                                   const Json& state) {
    std::string file = snapshot_dir_ + "/" + aggregate_id + ".json";
    Json snapshot = Json::object();
    snapshot.set("version", version);
    snapshot.set("state", state);
    std::ofstream stream(file);
    if (!stream)
        throw std::runtime_error("Could not save snapshot for aggregate " + aggregate_id);
    stream << snapshot.dump(2) << "\n";
    stream.close();
    if (!stream)
        throw std::runtime_error("Could not save snapshot for aggregate " + aggregate_id);
}

std::optional<std::pair<int64_t, Json>> JsonEventStore::load_snapshot(
    const std::string& aggregate_id) const {
    std::string file = snapshot_dir_ + "/" + aggregate_id + ".json";
    std::ifstream stream(file);
    if (!stream)
        return std::nullopt;
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    Json snapshot = Json::parse(buffer.str());
    int64_t version = snapshot.get_int("version", 0);
    const Json* state = snapshot.find("state");
    if (!state)
        return std::nullopt;
    return std::make_pair(version, *state);
}

} // namespace bb