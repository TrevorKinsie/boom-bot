# Persistent MMO with Shared Wallet (boom-bot)

## Overview

A **Runescape‑style MMO** that runs in the browser, with **low‑poly 3D art** and **basic gameplay**, focused on **persistence first** — all state survives restarts, and wealth lives in a **shared wallet event store** that was purpose‑built for the boom-bot casino.

---

## Architecture

| Layer | What's Implemented |
|-------|-------------------|
| **Java service** (`mmo-server/build/mmo-server.jar`) | HTTP API (`/api/join`, `/api/world`, `/api/game`, `/api/move`, `/api/gather`, `/api/sell`, `/api/deposit_gold`, `/api/withdraw_gold`), 72×72 tile map (grass/water/rock/bank), resources (trees/logs; rocks/ore) with respawn, player motion/gathering/inventory/bank, **shared wallet** – every gold credit/debit appends `WalletCreatedEvent`/`FundsCreditedEvent`/`FundsDebitedEvent` to the `casino_events` table in `casino.sqlite3` (`aggregate_id = mmo:<player>`) |
| **Browser client** (`mmo-server/src/main/resources/static/`) | Three.js r128 low-poly scene (grass, water lake, rocks, bank building), click‑to‑move, click‑to‑gather HUD: gold/carrying, wallet balance, skills, inventory, sell logs/ore → coins go straight to the wallet store. |
| **Persistence** | Game state (`players`, `resources`, `inventory`, `gold`) → `data/mmo.sqlite3` (SQLite WAL). Wallet events → `data/casino.sqlite3` (the casino's SQLite event store). |
| **Build & run** | `./build.sh` (JDK‑only `javac` + vendored `sqlite-jdbc‑3.43.0.0.jar`). `./run-mmo-server.sh` starts the service and opens the browser at `http://127.0.0.1:8080`. Maven `pom.xml` also present. |

---

## The wallet story after the C++20 rewrite

The Telegram bot was ported to a standalone **C++20 binary** (`bot-cpp/`),
and the Python casino (`boombot.casino`) was retired. Consequences for the
shared wallet:

* The **C++20 casino wallet** persists to its own **JSON Lines log**
  (`data/casino_events.json` + `.snapshots/`), handled by `JsonEventStore` in
  `bot-cpp/src/bb_event_store.cpp`. It does **not** read the SQLite store.
* The **MMO still writes** Python-format wallet events to the `casino_events`
  table of `casino.sqlite3` (the event schema of the retired Python casino:
  `WalletCreatedEvent`, `FundsCreditedEvent`, `FundsDebitedEvent`, …
  keyed `mmo:<player>`).
* On this branch those two stores are **separate**: the MMO's SQLite wealth has
  no live reader. Reunification means giving the C++ wallet a SQLite adapter
  (or replaying the JSONL log in the MMO) — the events in both stores share the
  same schema, so the change is mechanical.

---

## Verified Behaviors

| ✅ Feature | Evidence |
|------------|----------|
| **Java writes wallet events** | `WalletCreatedEvent` + `FundsCreditedEvent` appear in the `casino_events` table of `casino.sqlite3` |
| **Python can replay Java events** *(historical)* | Until the rewrite, `repo.find("mmo:<id>")` on the Python `boombot.casino` wallet replayed Java-written rows to an identical balance (e.g. `wallet mmo:mmo-p-7ffd75b9: balance = 4.00`); the Python casino has since been deleted |
| **Persists across server restart** | Python `test_persistence_across_restart_and_shared_wallet` resumed at the *exact* same position `(12.16,6.58)` and walletCents `800` after a full Java shutdown/restart |
| **Browser playable** | Client loads, player joins, walks, gathers logs, sells them, wallet balance updates live |
| **Cross‑language integration test** | `tests/test_mmo_server.py::test_python_can_replay_java_wallet_events` builds the jar, drives a real play session, and asserts the `casino_events` table holds `WalletCreatedEvent` + `FundsCreditedEvent` rows whose credit sum equals the Java‑reported balance (checked with the stdlib `sqlite3` driver) |

---

## Quickstart

```bash
# 1. Build the jar (JDK 21, no Maven needed)
cd /home/kevins/code/boom-bot/mmo-server && ./build.sh

# 2. Start the service (defaults to :8080, data under ./data)
./run-mmo-server.sh

# 3. Open http://127.0.0.1:8080 in a browser
#    — click to move, click trees to gather, sell logs, watch 🪙 Wallet balance
```

---

## Files Touched / Created

| Path | Description |
|------|-------------|
| `mmo-server/build.sh` | Offline `javac` build, vendored sqlite‑jdbc, static assets bundling |
| `mmo-server/run-mmo-server.sh` | Launcher with driver‑class warming (`Class.forName("org.sqlite.JDBC")`) |
| `mmo-server/pom.xml` | Maven‑equivalent for teams that prefer it |
| `mmo-server/src/main/java/com/boombot/mmo/` | `MmoServerMain`, `HttpApi`, `World`, `GameDb`, `WalletDb`, `Player`, `Resource`, `Util`, `ApiException` |
| `mmo-server/src/main/resources/static/` | `index.html`, `styles.css`, `app.js` (Three.js client) |
| `.gitignore` | Added `mmo-server/build/` and `mmo-server/*.log` |
| `tests/test_mmo_server.py` | Integration tests – cross‑language wallet replay + persistence |

---

## How It Works (Persistence‑First)

1. **Shared wallet** – The MMO does **not** have its own private economy.
   Selling items and depositing gold append wallet domain events to the
   `casino_events` table of `casino.sqlite3`. Aggregate id is `mmo:<player>`;
   the event payload is the Python-era schema
   (`WalletCreatedEvent`/`FundsCreditedEvent`/`FundsDebitedEvent`), so any
   consumer that speaks that schema — the retired Python wallet, a future C++20
   SQLite adapter — reconstructs the exact same balance.

2. **Event‑sourced persistence** – Whole world (players, positions,
   inventories, banks, skills, resource depletion/respawn) is stored in
   `data/mmo.sqlite3` (SQLite with WAL mode). The service tick thread flushes
   periodically, so the world survives restarts – reconnecting with your token
   resumes your exact character.

3. **Cross‑language proof (historical)** – Java wrote
   `WalletCreatedEvent` / `FundsCreditedEvent` rows; the Python
   `SqliteEventStoreAdapter` + `WalletRepository` loaded those events and
   `repo.find("mmo:<id>")` returned a `Wallet` whose `get_balance()` equaled
   the Java‑written amount. This was verified: after a Java session earning 400
   coins, `wallet mmo:mmo-p-7ffd75b9: balance = 4.00` in Python.
