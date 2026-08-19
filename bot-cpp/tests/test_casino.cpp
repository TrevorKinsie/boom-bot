/*
 * test_casino.cpp - casino port tests: event store, wallet, zeus, service,
 * leaderboard, facade.
 */
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "bb_casino.h"
#include "bb_casino_facade.h"
#include "bb_event_store.h"
#include "bb_json.h"
#include "bb_leaderboard.h"
#include "bb_money.h"
#include "bb_wallet.h"
#include "bb_zeus.h"
#include "tests.h"

using namespace bb;

namespace {

struct TestEnv {
    std::string dir;
    JsonEventStore store;

    explicit TestEnv(const std::string& name)
        : dir("/tmp/opencode/bb-test-" + name), store(dir + "/events.jsonl",
                                                       dir + "/events.jsonl.snapshots") {
        std::filesystem::remove_all(dir);
        std::filesystem::create_directories(dir + "/events.jsonl.snapshots");
    }
    ~TestEnv() { std::filesystem::remove_all(dir); }
};

Money m(const char* s) { return Money(std::string(s)); }

const char* kZeusEmoji = "\xF0\x9F\xA7\x94\xE2\x80\x8D\xE2\x99\x82\xEF\xB8\x8F";

} // namespace

// --- Event store -----------------------------------------------------------

TEST_CASE(casino_event_wire_format) {
    Json payload = Json::object();
    payload.set("starting_balance", "100.00");
    WalletEvent event = WalletEvent::create("WalletCreatedEvent", "user-1", 1, payload);

    CHECK(event.event_type == "WalletCreatedEvent");
    CHECK(event.aggregate_id == "user-1");
    // uuid4 format: 8-4-4-4-12 with version nibble '4'.
    CHECK(event.event_id.size() == 36);
    CHECK(event.event_id[14] == '4');
    CHECK(event.event_id[19] == '8' || event.event_id[19] == '9' || event.event_id[19] == 'a' ||
          event.event_id[19] == 'b');
    // YYYY-MM-DDTHH:MM:SS.ffffff+00:00
    CHECK(event.occurred_on.size() == 32);
    CHECK(event.occurred_on.compare(10, 1, "T") == 0);
    CHECK(event.occurred_on.compare(26, 6, "+00:00") == 0);

    Json record = event.to_record();
    CHECK(record.get_string("event_id") == event.event_id);
    CHECK(record.get_string("event_type") == "WalletCreatedEvent");
    CHECK(record.get_int("version") == 1);

    WalletEvent parsed = WalletEvent::from_record(record);
    CHECK(parsed.event_type == event.event_type);
    CHECK(parsed.aggregate_id == "user-1");
    CHECK(parsed.version == 1);
    CHECK(parsed.starting_balance() == "100.00");
    CHECK(parsed.starting_balance_cents() == 10000);

    // Typed accessors for the other payloads.
    Json p = Json::object();
    p.set("amount", "12.34");
    p.set("reason", "roulette");
    WalletEvent debited = WalletEvent::create("FundsDebitedEvent", "user-1", 2, p);
    CHECK(debited.amount() == "12.34");
    CHECK_INT_EQ(debited.amount_cents(), 1234);
    CHECK(debited.reason() == "roulette");

    Json w = Json::object();
    w.set("wager", "5.00");
    w.set("win", "35.00");
    w.set("game", "roulette");
    WalletEvent wagered = WalletEvent::create("WageredRecordedEvent", "user-1", 3, w);
    CHECK_INT_EQ(wagered.wager_cents(), 500);
    CHECK_INT_EQ(wagered.win_cents(), 3500);
    CHECK(wagered.game() == "roulette");
}

TEST_CASE(casino_event_store_append_load) {
    TestEnv env("append-load");
    Json p1 = Json::object();
    p1.set("starting_balance", "100.00");
    Json p2 = Json::object();
    p2.set("amount", "10.00");
    p2.set("reason", "roulette");
    const WalletEvent created = WalletEvent::create("WalletCreatedEvent", "alice", 1, p1);
    const WalletEvent debited = WalletEvent::create("FundsDebitedEvent", "alice", 2, p2);

    env.store.append("alice", {created, debited});

    // Log is JSONL, one event per line, UTF-8 raw (ensure_ascii=False).
    std::ifstream log(env.store.log_path());
    std::string line1, line2;
    std::getline(log, line1);
    std::getline(log, line2);
    CHECK(line1.find("\"event_type\": \"WalletCreatedEvent\"") != std::string::npos);
    CHECK(line2.find("\"reason\": \"roulette\"") != std::string::npos);
    CHECK(line2.find("\\u") == std::string::npos);

    std::vector<WalletEvent> loaded = env.store.load("alice");
    CHECK_INT_EQ(loaded.size(), 2);
    CHECK(loaded[0].event_type == "WalletCreatedEvent");
    CHECK(loaded[1].event_type == "FundsDebitedEvent");
    CHECK(loaded[1].reason() == "roulette");
    CHECK(env.store.load("bob").empty());

    // Round trip through the wire format.
    CHECK(WalletEvent::from_record(loaded[1].to_record()).to_record() ==
          loaded[1].to_record());
}

TEST_CASE(casino_event_store_snapshots) {
    TestEnv env("snapshots");
    Json state = Json::object();
    state.set("balance", "95.00");
    state.set("free_spins", 2);
    env.store.save_snapshot("alice", 7, state);

    std::string file = env.store.snapshot_dir() + "/alice.json";
    std::ifstream in(file);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    CHECK(text.find("\"version\": 7") != std::string::npos);
    CHECK(text.find("\"state\": {") != std::string::npos);

    auto snapshot = env.store.load_snapshot("alice");
    CHECK(snapshot.has_value());
    CHECK_INT_EQ(snapshot->first, 7);
    CHECK(snapshot->second.get_string("balance") == "95.00");
    CHECK_INT_EQ(snapshot->second.get_int("free_spins"), 2);
    CHECK(!env.store.load_snapshot("nobody").has_value());
}

// --- Wallet aggregate -----------------------------------------------------------

TEST_CASE(casino_wallet_aggregate) {
    Wallet wallet("u1");
    wallet.provision(m("100.00"));
    wallet.debit(m("10.00"), "roulette");
    wallet.debit(m("5.50"), "craps");
    wallet.credit(m("35.00"), "roulette");
    wallet.record_wager(m("10.00"), m("35.00"), "roulette");
    wallet.award_free_spins(3);
    wallet.redeem_free_spin();

    CHECK(m("119.50") == wallet.balance());
    CHECK(m("10.00") == wallet.total_wagered()); // debits are not wagers
    CHECK(m("35.00") == wallet.total_won());
    CHECK(m("35.00") == wallet.biggest_win());
    CHECK_INT_EQ(wallet.free_spins(), 2);
    CHECK_INT_EQ(wallet.games_played(), 1);
    CHECK_INT_EQ(wallet.uncommitted_events().size(), 7);

    // Zero-amount operations are no-ops.
    wallet.debit(Money::zero(), "roulette");
    wallet.credit(Money::zero(), "roulette");
    wallet.award_free_spins(0);
    CHECK_INT_EQ(wallet.uncommitted_events().size(), 7);

    // Overdraw raises WalletError with the Python message.
    CHECK_THROWS(wallet.debit(m("9999.00"), "zeus"), WalletError);

    // Redeeming with no free spins raises.
    Wallet empty("u2");
    CHECK_THROWS(empty.redeem_free_spin(), WalletError);

    // Snapshot state round trip.
    Json snapshot_state = wallet.to_snapshot_state();
    CHECK_INT_EQ(snapshot_state.get_int("version"), 7);
    Wallet restored = Wallet::from_snapshot_state("u1", snapshot_state);
    CHECK(restored.balance() == wallet.balance());
    CHECK(restored.total_won() == wallet.total_won());
    CHECK_INT_EQ(restored.games_played(), 1);
    CHECK_INT_EQ(restored.version().number(), 7);
}

TEST_CASE(casino_wallet_reset) {
    Wallet wallet("u1");
    wallet.provision(m("100.00"));
    wallet.debit(m("40.00"), "roulette");
    CHECK(m("60.00") == wallet.balance());
    wallet.reset(m("100.00"));
    CHECK(m("100.00") == wallet.balance());
    CHECK(wallet.uncommitted_events().back().event_type == "WalletResetEvent");
    CHECK(wallet.uncommitted_events().back().reset_balance() == "100.00");
}

// --- Repository ------------------------------------------------------------------

TEST_CASE(casino_repository_provision_and_replay) {
    TestEnv env("repo");
    SnapshotPolicy policy(50);
    WalletRepository repo(env.store, policy, m("100.00"));

    CHECK(repo.find("alice") == nullptr);

    auto wallet = repo.load_or_provision("alice");
    CHECK(wallet->has_uncommitted_events());
    CHECK(m("100.00") == wallet->balance());
    repo.save(*wallet);
    CHECK(!wallet->has_uncommitted_events());

    auto reloaded = repo.find("alice");
    CHECK(reloaded != nullptr);
    CHECK(m("100.00") == reloaded->balance());
    CHECK_INT_EQ(reloaded->version().number(), 1);
    CHECK(!reloaded->has_uncommitted_events());

    reloaded->debit(m("12.50"), "roulette");
    repo.save(*reloaded);
    auto again = repo.find("alice");
    CHECK(m("87.50") == again->balance());
    CHECK_INT_EQ(again->version().number(), 2);

    // Starting balance config controls provision.
    WalletRepository rich(env.store, policy, m("500.00"));
    auto bob = rich.load_or_provision("bob");
    CHECK(m("500.00") == bob->balance());
}

TEST_CASE(casino_repository_snapshot_threshold) {
    TestEnv env("repo-snap");
    SnapshotPolicy policy(3);
    WalletRepository repo(env.store, policy, m("100.00"));

    auto wallet = repo.load_or_provision("alice");
    repo.save(*wallet);
    CHECK(!env.store.load_snapshot("alice").has_value()); // committed=1

    wallet->award_free_spins(4);
    repo.save(*wallet);
    CHECK(!env.store.load_snapshot("alice").has_value()); // committed=2

    wallet->debit(m("5.00"), "roulette");
    repo.save(*wallet);
    auto snapshot = env.store.load_snapshot("alice"); // committed=3 -> snapshot
    CHECK(snapshot.has_value());
    CHECK_INT_EQ(snapshot->first, 3);
    CHECK(snapshot->second.get_string("balance") == "95.00");
    CHECK_INT_EQ(snapshot->second.get_int("free_spins"), 4);

    auto reloaded = repo.find("alice");
    CHECK(m("95.00") == reloaded->balance());
    CHECK_INT_EQ(reloaded->free_spins(), 4);
    CHECK_INT_EQ(reloaded->version().number(), 3);
}

TEST_CASE(casino_repository_batch_save) {
    TestEnv env("repo-version");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));

    auto wallet = repo.load_or_provision("alice");
    wallet->debit(m("5.00"), "roulette");
    wallet->debit(m("5.00"), "roulette");
    repo.save(*wallet);
    CHECK_INT_EQ(wallet->version().number(), 3);

    repo.save(*wallet); // nothing staged: no-op
    CHECK(!wallet->has_uncommitted_events());

    auto reloaded = repo.find("alice");
    CHECK(m("90.00") == reloaded->balance());
    CHECK_INT_EQ(reloaded->version().number(), 3);
}

// --- Zeus ----------------------------------------------------------------------

TEST_CASE(casino_zeus_line_evaluation) {
    LineEvaluationStrategy strategy;
    int symbol, count;
    bool jackpot;

    strategy.evaluate({8, 8, 8, 8, 8}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, -1);
    CHECK_INT_EQ(count, 5);
    CHECK(jackpot);

    strategy.evaluate({3, 3, 3, 4, 5}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, 3);
    CHECK_INT_EQ(count, 3);
    CHECK(!jackpot);

    // Four of a kind with one wild: match count = 4 + 1 = 5.
    strategy.evaluate({3, 3, 3, 8, 3}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, 3);
    CHECK_INT_EQ(count, 5);
    CHECK(!jackpot);

    strategy.evaluate({1, 1, 2, 3, 4}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, -1);
    CHECK_INT_EQ(count, 0);

    // Two wilds plus two of a kind: loss (zeus count > 1).
    strategy.evaluate({1, 1, 8, 8, 4}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, -1);
    CHECK_INT_EQ(count, 0);

    strategy.evaluate({2, 2, 2, 2, 2}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(symbol, 2);
    CHECK_INT_EQ(count, 5);

    strategy.evaluate({0, 1, 2, 3, 4}, &symbol, &count, &jackpot);
    CHECK_INT_EQ(count, 0);
}

TEST_CASE(casino_zeus_line_iteration) {
    std::vector<int> data = {1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 6, 7,
                             8, 1, 2, 3, 4, 5, 6, 7, 8, 1};
    ReelGrid grid(5, 5, data);
    std::vector<GridLine> lines = grid.iterate_lines();
    CHECK_INT_EQ(lines.size(), 12);
    CHECK_INT_EQ(lines[0].symbols.size(), 5);
    CHECK(lines[0].line_type == LineType::Row);
    CHECK(lines[5].line_type == LineType::Column);
    CHECK_INT_EQ(lines[5].symbols[0], 1);
    CHECK(lines[10].line_type == LineType::DiagonalPrimary);
    CHECK_INT_EQ(lines[10].symbols[1], 7);
    CHECK(lines[11].line_type == LineType::DiagonalSecondary);
    CHECK_INT_EQ(lines[11].symbols[1], 1); // row 1, col 3

    bool threw = false;
    try {
        ReelGrid bad(5, 5, {1, 2, 3});
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    CHECK(threw);
    threw = false;
    try {
        ReelGrid bad2(0, 0, {});
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    CHECK(threw);
}

TEST_CASE(casino_zeus_payouts) {
    PayoutTable table;
    int64_t coins;
    int spins;
    table.payouts_for(5, true, &coins, &spins);
    CHECK_INT_EQ(coins, 5000);
    CHECK_INT_EQ(spins, 0);
    table.payouts_for(6, false, &coins, &spins);
    CHECK_INT_EQ(coins, 200);
    CHECK_INT_EQ(spins, 2);
    table.payouts_for(4, false, &coins, &spins);
    CHECK_INT_EQ(coins, 50);
    CHECK_INT_EQ(spins, 1);
    table.payouts_for(3, false, &coins, &spins);
    CHECK_INT_EQ(coins, 10);
    CHECK_INT_EQ(spins, 0);
    table.payouts_for(2, false, &coins, &spins);
    CHECK_INT_EQ(coins, 0);
    CHECK_INT_EQ(spins, 0);

    // Calculator: jackpot awarded exactly once per grid.
    PayoutCalculator calculator(table);
    WinningLine j1{LineType::Row, 0, -1, 5, true};
    WinningLine j2{LineType::Column, 0, -1, 5, true};
    WinningLine fk{LineType::Row, 1, 1, 5, false};
    calculator.calculate({j1, j2, fk}, &coins, &spins);
    CHECK_INT_EQ(coins, 5200);
    CHECK_INT_EQ(spins, 2);

    calculator.calculate({fk, WinningLine{LineType::Row, 2, 2, 5, false},
                          WinningLine{LineType::Row, 3, 3, 4, false}},
                         &coins, &spins);
    CHECK_INT_EQ(coins, 450);
    CHECK_INT_EQ(spins, 5);
}

TEST_CASE(casino_zeus_grid_evaluation) {
    LineEvaluationStrategy strategy;
    // Row 0 jackpot, row 2 a 3-of-a-kind of symbol 3, others losses.
    std::vector<int> data = {8, 8, 8, 8, 8, 1, 2, 4, 5, 6, 3, 3, 3, 2, 1,
                             4, 5, 6, 7, 1, 2, 3, 4, 5, 6};
    ReelGrid grid(5, 5, data);
    GridWinEvaluator evaluator(grid, strategy);
    std::vector<WinningLine> wins = evaluator.evaluate();
    CHECK_INT_EQ(wins.size(), 2);
    CHECK(wins[0].is_jackpot);
    CHECK_INT_EQ(wins[0].line_index, 0);
    CHECK_INT_EQ(wins[1].match_count, 3);
}

// --- Money: fractional multipliers (craps) --------------------------------------

TEST_CASE(casino_money_fraction_multiply) {
    CHECK_INT_EQ(m("0.05").multiply_fraction(9, 5).cents(), 9);   // 0.09
    CHECK_INT_EQ(m("0.01").multiply_fraction(7, 6).cents(), 1);   // 0.0117 -> 0.01
    CHECK_INT_EQ(m("0.03").multiply_fraction(7, 5).cents(), 4);   // 0.042 -> 0.04
    CHECK_INT_EQ(m("10.00").multiply_fraction(7, 6).cents(), 1167); // 11.67
    CHECK_INT_EQ(m("100.00").multiply_fraction(9, 5).cents(), 18000); // 180.00
    CHECK_INT_EQ(m("5.00").multiply_fraction(7, 1).cents(), 3500); // 35.00
}

// --- Craps rules ----------------------------------------------------------------

TEST_CASE(casino_craps_resolution) {
    auto resolve = [](const char* type, int sum, std::optional<int> point, int d1, int d2) {
        return resolve_craps_bet(type, m("10.00"), sum, point, d1, d2);
    };

    CHECK(resolve("pass_line", 7, std::nullopt, 3, 4).kind == CrapsResolution::Kind::Win);
    CHECK(resolve("pass_line", 11, std::nullopt, 5, 6).kind == CrapsResolution::Kind::Win);
    CHECK(resolve("pass_line", 2, std::nullopt, 1, 1).kind == CrapsResolution::Kind::Loss);
    CHECK(resolve("pass_line", 12, std::nullopt, 6, 6).kind == CrapsResolution::Kind::Loss);
    CHECK(resolve("pass_line", 5, std::optional<int>(5), 2, 3).kind ==
          CrapsResolution::Kind::Win);
    CHECK(resolve("pass_line", 7, std::optional<int>(5), 3, 4).kind ==
          CrapsResolution::Kind::Loss);
    CHECK(resolve("pass_line", 6, std::optional<int>(5), 2, 4).kind ==
          CrapsResolution::Kind::Loss);

    CHECK(resolve("dont_pass", 3, std::nullopt, 1, 2).kind == CrapsResolution::Kind::Win);
    CHECK(resolve("dont_pass", 12, std::nullopt, 6, 6).kind == CrapsResolution::Kind::Push);
    CHECK(resolve("dont_pass", 7, std::nullopt, 3, 4).kind == CrapsResolution::Kind::Loss);
    auto push = resolve("dont_pass", 12, std::nullopt, 6, 6);
    CHECK(push.winnings.is_zero());
    CHECK(resolve("dont_pass", 7, std::optional<int>(5), 3, 4).kind ==
          CrapsResolution::Kind::Win);

    CHECK(resolve("field", 2, std::nullopt, 1, 1).winnings.cents() == 2000);
    CHECK(resolve("field", 12, std::nullopt, 6, 6).winnings.cents() == 3000);
    CHECK(resolve("field", 9, std::nullopt, 4, 5).winnings.cents() == 1000);
    CHECK(resolve("field", 5, std::nullopt, 2, 3).kind == CrapsResolution::Kind::Loss);

    CHECK(resolve("place_4", 4, std::optional<int>(4), 2, 2).winnings.cents() == 1800);
    CHECK(resolve("place_4", 4, std::nullopt, 2, 2).kind == CrapsResolution::Kind::Loss);
    CHECK(resolve("place_10", 10, std::optional<int>(10), 5, 5).winnings.cents() == 1800);
    CHECK(resolve("place_6", 6, std::optional<int>(6), 3, 3).winnings.cents() == 1167);
    CHECK(resolve("place_5", 5, std::optional<int>(5), 1, 4).winnings.cents() == 1400);

    CHECK(resolve("hard_4", 4, std::nullopt, 2, 2).winnings.cents() == 7000);
    CHECK(resolve("hard_4", 4, std::nullopt, 1, 3).kind == CrapsResolution::Kind::Loss);
    CHECK(resolve("hard_6", 6, std::nullopt, 3, 3).winnings.cents() == 9000);

    CHECK(resolve("any_craps", 2, std::nullopt, 1, 1).winnings.cents() == 7000);
    CHECK(resolve("any_craps", 7, std::nullopt, 3, 4).kind == CrapsResolution::Kind::Loss);
    CHECK(resolve("any_seven", 7, std::nullopt, 3, 4).winnings.cents() == 4000);
    CHECK(resolve("two", 2, std::nullopt, 1, 1).winnings.cents() == 30000);
    CHECK(resolve("three", 3, std::nullopt, 1, 2).winnings.cents() == 15000);
    CHECK(resolve("eleven", 11, std::nullopt, 5, 6).winnings.cents() == 15000);
    CHECK(resolve("twelve", 12, std::nullopt, 6, 6).winnings.cents() == 30000);
    CHECK(resolve("horn", 3, std::nullopt, 1, 2).winnings.cents() == 30000);
    CHECK(resolve("horn", 11, std::nullopt, 5, 6).winnings.cents() == 30000);
    CHECK(resolve("horn", 7, std::nullopt, 3, 4).kind == CrapsResolution::Kind::Loss);

    int state = 1;
    std::optional<int> point;
    WageringService::advance_craps_phase(4, std::nullopt, &state, &point);
    CHECK_INT_EQ(state, 2);
    CHECK_INT_EQ(*point, 4);
    // A non-deciding roll (neither point nor seven) keeps the point phase.
    WageringService::advance_craps_phase(9, point, &state, &point);
    CHECK_INT_EQ(state, 2);
    CHECK_INT_EQ(*point, 4);
    // Rolling the point returns to the come-out phase.
    WageringService::advance_craps_phase(4, point, &state, &point);
    CHECK_INT_EQ(state, 1);
    CHECK(!point.has_value());
    // A come-out seven ends the point phase too.
    WageringService::advance_craps_phase(5, std::nullopt, &state, &point);
    CHECK_INT_EQ(state, 2);
    CHECK_INT_EQ(*point, 5);
    WageringService::advance_craps_phase(7, point, &state, &point);
    CHECK_INT_EQ(state, 1);
    CHECK(!point.has_value());
}

// --- Service: roulette ----------------------------------------------------------------

TEST_CASE(casino_service_roulette_flow) {
    TestEnv env("service-roulette");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    CHECK_STR_EQ(service.get_balance_text("alice"),
                 "Wallet\nBalance: 100.00\nFree spins: 0\nTotal won: 0.00\nTotal wagered: 0.00");
    CHECK(service.get_balance("alice") == m("100.00"));
    CHECK_INT_EQ(env.store.load("alice").size(), 1); // provision persisted

    CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", "red", "", "10.00"),
                 "Placed 10.00 on red.");
    CHECK(service.get_balance("alice") == m("90.00"));
    CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", "straight", "7", "5.00"),
                 "Placed 5.00 on straight__7.");
    CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", "red", "", "5.00"),
                 "Placed 5.00 on red.");
    CHECK(service.get_balance("alice") == m("80.00"));

    CHECK_THROWS(service.place_roulette_bet("alice", "chat-1", "split", "", "5.00"),
                 CasinoError);
    CHECK_THROWS(service.place_roulette_bet("alice", "chat-1", "straight", "", "5.00"),
                 CasinoError);
    CHECK_THROWS(service.place_roulette_bet("alice", "chat-1", "red", "", "abc"),
                 CasinoError);
    CHECK_THROWS(service.place_roulette_bet("alice", "chat-1", "red", "", "0"),
                 CasinoError);
    CHECK_THROWS(service.place_roulette_bet("alice", "chat-1", "red", "", "1000.00"),
                 CasinoError);

    // Scripted pocket 3: red (15.00) wins 15.00; straight 7 loses.
    service.roulette_pocket = []() { return 3; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 3.\n"
                 "Player alice wins 15.00.");
    // 80.00 + 15.00 win = 95.00.
    CHECK(service.get_balance("alice") == m("95.00"));

    CHECK_STR_EQ(service.spin_roulette("chat-2"), "No bets placed for this roulette spin.");
    service.roulette_pocket = []() { return 7; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"), "No bets placed for this roulette spin.");
    CHECK(service.get_balance("alice") == m("95.00"));
}

TEST_CASE(casino_service_roulette_straight_win) {
    TestEnv env("service-roulette-straight");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", "straight", "7", "5.00"),
                 "Placed 5.00 on straight__7.");
    service.roulette_pocket = []() { return 7; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 7.\nPlayer alice wins 175.00.");
    CHECK(service.get_balance("alice") == m("270.00")); // 100 - 5 + 175
}

TEST_CASE(casino_service_roulette_double_zero) {
    TestEnv env("service-roulette-dz");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    CHECK_STR_EQ(service.place_roulette_bet("bob", "chat-1", "straight", "00", "5.00"),
                 "Placed 5.00 on straight__00.");
    service.roulette_pocket = []() { return 37; }; // "00"
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 00.\nPlayer bob wins 175.00.");
    CHECK(service.get_balance("bob") == m("270.00"));

    // Red loses on 00.
    CHECK_STR_EQ(service.place_roulette_bet("bob", "chat-1", "red", "", "10.00"),
                 "Placed 10.00 on red.");
    service.roulette_pocket = []() { return 37; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 00.");
    CHECK(service.get_balance("bob") == m("260.00"));
}

TEST_CASE(casino_service_roulette_even_money) {
    TestEnv env("service-roulette-even");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    for (const char* type : {"red", "black", "even", "odd", "low", "high",
                             "first_dozen", "second_dozen", "third_dozen"}) {
        CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", type, "", "1.00"),
                     std::string("Placed 1.00 on ") + type + ".");
    }
    CHECK(service.get_balance("alice") == m("91.00"));

    // Pocket 1: red, odd, low win 1.00 each; first dozen pays 2x.
    service.roulette_pocket = []() { return 1; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 1.\n"
                 "Player alice wins 2.00.\n"
                 "Player alice wins 1.00.\n"
                 "Player alice wins 1.00.\n"
                 "Player alice wins 1.00.");
    CHECK(service.get_balance("alice") == m("96.00")); // 91 + 5

    // Pocket 2: black, even (3rd dozen, high lose on 2).
    CHECK_STR_EQ(service.place_roulette_bet("alice", "chat-1", "black", "", "2.00"),
                 "Placed 2.00 on black.");
    service.roulette_pocket = []() { return 2; };
    CHECK_STR_EQ(service.spin_roulette("chat-1"),
                 "The wheel landed on pocket 2.\nPlayer alice wins 2.00.");
    CHECK(service.get_balance("alice") == m("96.00")); // 91 - 2 + 2 - 0 + 5
}

// --- Service: craps ------------------------------------------------------------------

TEST_CASE(casino_service_craps_flow) {
    TestEnv env("service-craps");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    CHECK_STR_EQ(service.place_craps_bet("alice", "chat-1", "pass_line", "10.00"),
                 "Placed 10.00 on pass_line.");
    CHECK(service.get_balance("alice") == m("90.00"));
    CHECK_THROWS(service.place_craps_bet("alice", "chat-1", "bogus", "5.00"), CasinoError);
    CHECK_THROWS(service.place_craps_bet("alice", "chat-1", "pass_line", "0"), CasinoError);

    // Come-out 11: pass line wins 10.00; phase stays come-out (11 is no point).
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 5;
        *d2 = 6;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 5 + 6 = 11.\nPlayer alice wins 10.00 on pass_line.");
    CHECK(service.get_balance("alice") == m("100.00"));

    // First roll of the next come-out: 4 establishes the point, and the
    // standing pass_line loses (4 is not 7/11 on a come-out).
    CHECK_STR_EQ(service.place_craps_bet("alice", "chat-1", "pass_line", "10.00"),
                 "Placed 10.00 on pass_line.");
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 1;
        *d2 = 3;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 1 + 3 = 4.\nPlayer alice loses pass_line.");
    CHECK(service.get_balance("alice") == m("90.00"));

    // Point phase: pass_line blocked; place bets and one-roll bets allowed.
    CHECK_STR_EQ(service.place_craps_bet("alice", "chat-1", "place_4", "5.00"),
                 "Placed 5.00 on place_4.");
    CHECK_THROWS(service.place_craps_bet("alice", "chat-1", "pass_line", "5.00"),
                 CasinoError);
    CHECK_STR_EQ(service.place_craps_bet("alice", "chat-1", "field", "3.00"),
                 "Placed 3.00 on field.");
    CHECK_THROWS(service.place_craps_bet("alice", "chat-1", "dont_pass", "5.00"),
                 CasinoError);

    // Rolling the point: place_4 wins 9.00 (5.00 * 9/5); field (4) wins 3.00;
    // the table returns to come-out.
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 2;
        *d2 = 2;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 2 + 2 = 4.\n"
                 "Player alice wins 3.00 on field.\n"
                 "Player alice wins 9.00 on place_4.");
    CHECK(service.get_balance("alice") == m("94.00")); // 90 - 5 - 3 + 9 + 3

    CHECK_STR_EQ(service.roll_craps("chat-1"), "No bets placed for this craps roll.");

    // Don't pass push on come-out 12.
    CHECK_STR_EQ(service.place_craps_bet("alice", "chat-1", "dont_pass", "10.00"),
                 "Placed 10.00 on dont_pass.");
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 6;
        *d2 = 6;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 6 + 6 = 12.\nPlayer alice pushes on dont_pass.");
    CHECK(service.get_balance("alice") == m("94.00")); // 94 - 10 + 10
}

TEST_CASE(casino_service_craps_multiple_players_and_loss) {
    TestEnv env("service-craps-2");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    service.place_craps_bet("alice", "chat-1", "any_seven", "10.00");
    service.place_craps_bet("bob", "chat-1", "any_seven", "20.00");
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 3;
        *d2 = 3;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 3 + 3 = 6.\n"
                 "Player alice loses any_seven.\n"
                 "Player bob loses any_seven.");
    CHECK(service.get_balance("alice") == m("90.00"));
    CHECK(service.get_balance("bob") == m("80.00"));

    // Winners are listed in bet placement order... (map order by user id).
    service.place_craps_bet("carol", "chat-1", "eleven", "5.00");
    service.place_craps_bet("alice", "chat-1", "eleven", "5.00");
    service.craps_roll = [](int* d1, int* d2) {
        *d1 = 5;
        *d2 = 6;
    };
    CHECK_STR_EQ(service.roll_craps("chat-1"),
                 "Rolled 5 + 6 = 11.\n"
                 "Player alice wins 75.00 on eleven.\n"
                 "Player carol wins 75.00 on eleven.");
    CHECK(service.get_balance("alice") == m("160.00"));
    CHECK(service.get_balance("carol") == m("170.00"));
}

// --- Service: zeus -------------------------------------------------------------------

TEST_CASE(casino_service_zeus_flow) {
    TestEnv env("service-zeus");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    // Scripted grid: row 0 all wilds (jackpot), row 2 a 3-of-a-kind of 3.
    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        return std::vector<int>{8, 8, 8, 8, 8, 1, 2, 4, 5, 6, 3, 3, 3, 2, 1,
                                4, 5, 6, 7, 1, 2, 3, 4, 5, 6};
    };
    std::string reply = service.spin_zeus("alice");
    // Fence + grid row 0 (all Zeus emoji).
    CHECK(reply.find("```\n") == 0);
    std::string row0 = std::string(kZeusEmoji) + " | " + kZeusEmoji + " | " +
                       kZeusEmoji + " | " + kZeusEmoji + " | " + kZeusEmoji;
    CHECK(reply.find(row0) != std::string::npos);
    // Jackpot (5000) + the row-2 3-of-a-kind (10) both pay out.
    CHECK(reply.find("Won 5010.00 coins and 0 free spins.") != std::string::npos);
    CHECK(reply.find("Balance: 5100.00 | Free spins: 0") != std::string::npos);
    CHECK(service.get_balance("alice") == m("5100.00")); // 100 - 10 + 5010
}

TEST_CASE(casino_service_zeus_free_spins) {
    TestEnv env("service-zeus-spins");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    // A 4-of-a-kind grid: 50.00 + 1 free spin.
    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        return std::vector<int>{2, 2, 2, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6,
                                7, 8, 1, 2, 3, 4, 5, 6, 7, 8};
    };
    std::string reply = service.spin_zeus("alice");
    CHECK(reply.find("Won 50.00 coins and 1 free spins.") != std::string::npos);
    CHECK(reply.find("Balance: 140.00 | Free spins: 1") != std::string::npos);
    CHECK(service.get_balance("alice") == m("140.00"));

    // The next spin is free (free_spins redeemed, no 10.00 debit), jackpot!
    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        return std::vector<int>(25, 8);
    };
    reply = service.spin_zeus("alice");
    CHECK(reply.find("Won 5000.00 coins and 0 free spins.") != std::string::npos);
    CHECK(reply.find("Balance: 5140.00 | Free spins: 0") != std::string::npos);
    CHECK(service.get_balance("alice") == m("5140.00"));

    // A 5-of-a-kind grid: 200.00 + 2 free spins.
    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        return std::vector<int>{4, 4, 4, 4, 4, 1, 2, 3, 5, 6, 7, 8, 1, 2, 3,
                                4, 5, 6, 7, 1, 2, 3, 4, 5, 6};
    };
    reply = service.spin_zeus("alice");
    CHECK(reply.find("Won 200.00 coins and 2 free spins.") != std::string::npos);
    CHECK(reply.find("Balance: 5330.00 | Free spins: 2") != std::string::npos);
}

TEST_CASE(casino_service_zeus_loss_and_insufficient) {
    TestEnv env("service-zeus-loss");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        // No line has 3+ of a kind and no wilds: (2r+c)%8 with 5x5 rows.
        return std::vector<int>{0, 1, 2, 3, 4, 2, 3, 4, 5, 6, 4, 5, 6, 7, 0,
                                6, 7, 0, 1, 2, 0, 1, 2, 3, 4};
    };
    std::string reply = service.spin_zeus("alice");
    CHECK(reply.find("No winning lines this spin.") != std::string::npos);
    CHECK(reply.find("Balance: 90.00 | Free spins: 0") != std::string::npos);
    CHECK(service.get_balance("alice") == m("90.00"));

    // Exhaust the balance; the next zeus spin is rejected.
    service.place_roulette_bet("alice", "chat-1", "red", "", "90.00");
    CHECK(service.get_balance("alice") == m("0.00"));
    bool threw = false;
    try {
        service.spin_zeus("alice");
    } catch (const CasinoError& e) {
        threw = true;
        CHECK_STR_EQ(std::string(e.what()),
                     "Insufficient balance 0.00 for wager 10.00.");
    }
    CHECK(threw);
    CHECK(service.get_balance("alice") == m("0.00"));
}

// --- Service: reset -----------------------------------------------------------------

TEST_CASE(casino_service_reset) {
    TestEnv env("service-reset");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    service.place_roulette_bet("alice", "chat-1", "red", "", "40.00");
    CHECK(service.get_balance("alice") == m("60.00"));
    CHECK_STR_EQ(service.reset_wallet("alice"), "Balance reset to 100.00.");
    CHECK(service.get_balance("alice") == m("100.00"));

    // Persisted reset survives a fresh load.
    WalletRepository repo2(env.store, SnapshotPolicy(50), m("100.00"));
    auto wallet = repo2.load_or_provision("alice");
    CHECK(m("100.00") == wallet->balance());
}

TEST_CASE(casino_service_stats_event_fold) {
    TestEnv env("service-stats");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    WageringService service(repo, env.store, sessions, bus);

    service.place_roulette_bet("alice", "chat-1", "straight", "7", "5.00");
    service.roulette_pocket = []() { return 7; };
    service.spin_roulette("chat-1");

    // total_wagered / total_won / biggest_win / games_played fold.
    auto wallet = repo.find("alice");
    CHECK(m("5.00") == wallet->total_wagered());
    CHECK(m("175.00") == wallet->total_won());
    CHECK(m("175.00") == wallet->biggest_win());
    CHECK_INT_EQ(wallet->games_played(), 1);
}

// --- Leaderboard ---------------------------------------------------------------------

TEST_CASE(casino_leaderboard_projection) {
    TestEnv env("leaderboard");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    LeaderboardProjection projection;
    bus.subscribe_all([&projection](const WalletEvent& event) { projection.notify(event); });
    WageringService service(repo, env.store, sessions, bus);

    service.place_roulette_bet("alice", "chat-1", "red", "", "30.00"); // 70.00
    service.place_roulette_bet("bob", "chat-1", "red", "", "10.00");   // 90.00
    service.place_roulette_bet("carol", "chat-1", "red", "", "50.00"); // 50.00
    service.place_roulette_bet("dave", "chat-1", "red", "", "5.00");   // 95.00

    std::vector<PlayerStanding> ranking = projection.get_leaderboard(10);
    CHECK_INT_EQ(ranking.size(), 4);
    CHECK_STR_EQ(ranking[0].user_id, "dave");
    CHECK_STR_EQ(ranking[1].user_id, "bob");
    CHECK_STR_EQ(ranking[2].user_id, "alice");
    CHECK_STR_EQ(ranking[3].user_id, "carol");

    projection.register_name("alice", "Alice A");
    ranking = projection.get_leaderboard(10);
    CHECK_STR_EQ(ranking[2].display_name, "Alice A");
    CHECK_STR_EQ(ranking[0].display_name, "dave"); // falls back to user id

    // Wins re-rank: alice +30 -> 100.00 tops.
    service.roulette_pocket = []() { return 3; };
    service.spin_roulette("chat-1");
    ranking = projection.get_leaderboard(10);
    CHECK_STR_EQ(ranking[0].user_id, "alice");
    CHECK(ranking[0].balance == m("100.00"));

    const PlayerStanding* carol = projection.get_standing("carol");
    CHECK(carol != nullptr);
    CHECK_INT_EQ(carol->games_played, 1);
    CHECK(carol->total_wagered == m("50.00"));
    CHECK(carol->total_won == m("50.00"));

    CHECK_INT_EQ(projection.get_leaderboard(2).size(), 2);
    projection.clear();
    CHECK(projection.get_leaderboard(10).empty());
}

// --- Facade ---------------------------------------------------------------------------

TEST_CASE(casino_facade_wallet_leaderboard_reset) {
    TestEnv env("facade");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    LeaderboardProjection projection;
    bus.subscribe_all([&projection](const WalletEvent& event) { projection.notify(event); });
    WageringService service(repo, env.store, sessions, bus);
    CasinoFacade facade(service, projection, bus);

    facade.register_identity("alice", "Alice A");
    CHECK_STR_EQ(facade.wallet_command("alice"),
                 "Wallet\nBalance: 100.00\nFree spins: 0\nTotal won: 0.00\nTotal wagered: 0.00");
    // wallet_command above provisions Alice, so the leaderboard lists her.
    CHECK_STR_EQ(facade.leaderboard_command(), "Leaderboard\n1. Alice A - 100.00");

    facade.roulette_command("alice", "chat-1", {"red", "30"});
    facade.roulette_command("bob", "chat-1", {"red", "10"});
    // Bob is unknown: display name falls back to user id.
    CHECK_STR_EQ(facade.leaderboard_command(),
                 "Leaderboard\n1. bob - 90.00\n2. Alice A - 70.00");

    CHECK_STR_EQ(facade.reset_wallet_command("alice"), "Balance reset to 100.00.");
    CHECK_STR_EQ(facade.wallet_command("alice"),
                 "Wallet\nBalance: 100.00\nFree spins: 0\nTotal won: 0.00\nTotal wagered: 0.00");
}

TEST_CASE(casino_facade_command_usage) {
    TestEnv env("facade-usage");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    LeaderboardProjection projection;
    bus.subscribe_all([&projection](const WalletEvent& event) { projection.notify(event); });
    WageringService service(repo, env.store, sessions, bus);
    CasinoFacade facade(service, projection, bus);

    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {}),
                 "Usage: /roulette <type> [number] <amount>\n"
                 "e.g. /roulette red 10, /roulette straight 7 10");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"red"}),
                 "Usage: /roulette <type> [number] <amount>\n"
                 "e.g. /roulette red 10, /roulette straight 7 10");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"straight", "7"}),
                 "Usage: /roulette straight <number> <amount>");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"straight", "7", "10"}),
                 "Placed 10.00 on straight__7.");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"split", "10"}),
                 "Invalid bet type: split");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"RED", "10"}),
                 "Placed 10.00 on red.");
    CHECK_STR_EQ(facade.roulette_command("alice", "chat-1", {"red", "abc"}),
                 "Invalid bet amount: abc");

    CHECK_STR_EQ(facade.craps_command("alice", "chat-1", {}),
                 "Usage: /craps <type> <amount>\n"
                 "e.g. /craps pass_line 10, /craps any_seven 5");
    CHECK_STR_EQ(facade.craps_command("alice", "chat-1", {"pass_line", "10"}),
                 "Placed 10.00 on pass_line.");
    CHECK_STR_EQ(facade.craps_command("alice", "chat-1", {"Pass_Line", "10"}),
                 "Placed 10.00 on pass_line.");
    CHECK_STR_EQ(facade.craps_command("alice", "chat-1", {"bogus", "10"}),
                 "Invalid bet type: bogus");
}

TEST_CASE(casino_facade_roulette_spin_commands) {
    TestEnv env("facade-spin");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    LeaderboardProjection projection;
    bus.subscribe_all([&projection](const WalletEvent& event) { projection.notify(event); });
    WageringService service(repo, env.store, sessions, bus);
    CasinoFacade facade(service, projection, bus);

    CHECK_STR_EQ(facade.roulette_spin_command("chat-1"),
                 "No bets placed for this roulette spin.");
    CHECK_STR_EQ(facade.craps_roll_command("chat-1"), "No bets placed for this craps roll.");

    facade.roulette_command("alice", "chat-1", {"red", "10"});
    service.roulette_pocket = []() { return 3; };
    CHECK_STR_EQ(facade.roulette_spin_command("chat-1"),
                 "The wheel landed on pocket 3.\nPlayer alice wins 10.00.");
}

TEST_CASE(casino_facade_zeus_markdown) {
    TestEnv env("facade-zeus");
    WalletRepository repo(env.store, SnapshotPolicy(50), m("100.00"));
    InMemoryGameSessionStore sessions;
    InProcessEventBus bus;
    LeaderboardProjection projection;
    bus.subscribe_all([&projection](const WalletEvent& event) { projection.notify(event); });
    WageringService service(repo, env.store, sessions, bus);
    CasinoFacade facade(service, projection, bus);

    service.zeus_grid = [](int rows, int cols) {
        (void)rows;
        (void)cols;
        return std::vector<int>(25, 4);
    };
    auto [reply, markdown] = facade.zeus_command("alice");
    CHECK(markdown);
    CHECK(reply.find("```\n") == 0);
    CHECK(reply.find("\n```\n") != std::string::npos);
    // All-👑: 12 winning lines x 200.00 = 2400.00 (+2 free spins each).
    CHECK(reply.find("Won 2400\\.00 coins and 24 free spins\\.") != std::string::npos);
    // Trailing line escaped for MarkdownV2 ('.' and '|').
    CHECK(reply.find("Balance: 2490\\.00 \\| Free spins: 24") != std::string::npos);

    // Error replies are plain text (no parsing): force bob broke first.
    CHECK_STR_EQ(facade.roulette_command("bob", "chat-2", {"red", "100"}),
                 "Placed 100.00 on red.");
    auto [err, markdown_err] = facade.zeus_command("bob");
    CHECK(!markdown_err);
    CHECK(err.find("Insufficient balance 100\\.00") == std::string::npos);
    CHECK_STR_EQ(err, "Insufficient balance 0.00 for wager 10.00.");
}

TEST_CASE(casino_zeus_markdown_escape) {
    CHECK_STR_EQ(zeus_markdown_v2("```\ngrid\n```\nWon 1.00 coins and 0 free spins."),
                 "```\ngrid\n```\nWon 1\\.00 coins and 0 free spins\\.");
    CHECK_STR_EQ(zeus_markdown_v2("plain text"), "plain text");
}