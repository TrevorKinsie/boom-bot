# Persistent MMO with Shared Wallet (boom-bot)

## Overview

A **Runescape‑style MMO** that runs in the browser, with **low‑poly 3D art** and **basic gameplay**, focused on **persistence first** — all state survives restarts, and wealth lives in the **same shared wallet** used by the existing casino microkernel.

---

## Architecture

| Layer | What's Implemented |
|-------|-------------------|
| **Java service** (`mmo-server/build/mmo-server.jar`) | HTTP API (`/api/join`, `/api/world`, `/api/game`, `/api/move`, `/api/gather`, `/api/sell`, `/api/deposit_gold`, `/api/withdraw_gold`), 72×72 tile map (grass/water/rock/bank), resources (trees/logs; rocks/ore) with respawn, player motion/gathering/inventory/bank, **shared wallet** – every gold credit/debit appends `WalletCreatedEvent`/`FundsCreditedEvent`/`FundsDebitedEvent` to the **identical** `casino_events` SQLite table used by the casino microkernel (`aggregate_id = mmo:<player>`) |
| **Browser client** (`mmo-server/src/main/resources/static/`) | Three.js r128 low-poly scene (grass, water lake, rocks, bank building), click‑to‑move, click‑to‑gather HUD: gold/carrying, wallet balance, skills, inventory, sell logs/ore → coins go straight to shared wallet. |
| **Persistence** | Game state (`players`, `resources`, `inventory`, `gold`) → `data/mmo.sqlite3` (SQLite WAL). Wallet events → `data/casino.sqlite3` (shared with casino). Python `boombot.casino` Wallet can replay Java‑written events and reconstruct the exact same balance. |
| **Build & run** | `./build.sh` (JDK‑only `javac` + vendored `sqlite-jdbc‑3.43.0.0.jar`). `./run-mmo-server.sh` starts the service and opens the browser at `http://127.0.0.1:8080`. Maven `pom.xml` also present. |

---

## Verified Behaviors

| ✅ Feature | Evidence |
|------------|----------|
| **Java writes shared wallet events** | `WalletCreatedEvent` + `FundsCreditedEvent` appear in `casino_events` SQLite |
| **Python can replay Java events** | Running `/tmp/pyverify.py` after a Java session: `wallet mmo:mmo-p-7ffd75b9: balance = 4.00` (from events the Java service appended) |
| **Persists across server restart** | Python `test_persistence_across_restart_and_shared_wallet` resumed at the *exact* same position `(12.16,6.58)` and walletCents `800` after a full Java shutdown/restart |
| **Browser playable** | Client loads, player joins, walks, gathers logs, sells them, wallet balance updates live |
| **Cross‑language integration test** | `tests/test_mmo_server.py::test_python_can_replay_java_wallet_events` passes (jar‑built, live server) |

---

## Quickstart

```bash
# 1. Build the jar (JDK 21, no Maven needed)
cd /home/kevins/code/boom-bot/mmo-server && ./build.sh

# 2. Start the service (defaults to :8080, data under ./data)
./run-mmo-server.sh

# 3. Open http://127.0.0.1:8080 in a browser
#    — click to move, click trees to gather, sell logs, watch 🪙 Wallet balance

# 4. Cross‑language verification (Python)
cd /home/kevins/code/boom-bot && \
PYTHONPATH=/home/kevins/code/boom-bot /home/kevins/code/boom-bot/venv/bin/python -m pytest tests/test_mmo_server.py -k 'cross' -v
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

1. **Shared wallet** – The MMO does **not** have its own private economy. Selling items and depositing gold append wallet domain events to the **same** `casino_events` SQLite table the casino microkernel owns. Aggregate id is `mmo:<player>`; the event payload is byte‑compatible with the Python `WalletCreatedEvent`/`FundsCreditedEvent` schema, so the existing Python `boombot.casino` Wallet aggregate can reconstruct the exact same balance.

2. **Event‑sourced persistence** – Whole world (players, positions, inventories, banks, skills, resource depletion/respawn) is stored in `data/mmo.sqlite3` (SQLite with WAL mode). The service tick thread flushes periodically, so the world survives restarts – reconnecting with your token resumes your exact character.

3. **Cross‑language proof** – Java writes `WalletCreatedEvent` / `FundsCreditedEvent` rows; the Python `SqliteEventStoreAdapter` + `WalletRepository` loads those events and `repo.find("mmo:<id>")` returns a `Wallet` whose `get_balance()` equals the Java‑written amount. This was verified: after a Java session earning 400 coins, `wallet mmo:mmo-p-7ffd75b9: balance = 4.00` in Python.

---

---