# boom-bot MMO Game Service

A persistent, Runescape-style MMO playable in the browser (low-poly 3D), as a
Java service that persists through the same shared wallet the casino microkernel
uses.

## Persistence-first design

* **Game persistence** — the whole world (players, positions, inventories,
  banks, skills, resource depletion/respawn) is stored in `data/mmo.sqlite3`
  (WAL). Every action writes through; the server tick flushes continuously. The
  world survives restarts — reconnect with your token to resume your character.
* **Shared wallet** — wealth is not a private MMO ledger. Selling items and
  depositing gold appends wallet **domain events** to the `casino_events` table
  of the casino's SQLite event store (`data/casino.sqlite3`), keyed by
  aggregate `mmo:<player>`, using the Python-era event-sourced schema
  (`WalletCreatedEvent`, `FundsCreditedEvent`). The MMO is another writer to
  the one append-only wallet store.

  **Note (post C++20 rewrite):** the Telegram casino was ported to C++20
  (`bot-cpp/`) and persists wallets to its own JSON Lines log
  (`casino_events.json`); it does not read this SQLite store, and the Python
  wallet that consumed it was deleted. The MMO's wallet events keep the common
  schema so a future SQLite adapter on the C++20 side (or replay of the JSONL
  log in the MMO) reunifies them.

## What's here

* `build.sh` — offline `javac` build; vendors `sqlite-jdbc` and bundles it (plus
  the browser client) into `build/mmo-server.jar`.
* `run-mmo-server.sh` — starts the service and serves the browser client.
* `pom.xml` — equivalent Maven build for teams that prefer it.
* `src/main/java/com/boombot/mmo/` — game service sources.
* `src/main/resources/static/` — Three.js low-poly browser client.
* `../../tests/test_mmo_server.py` — integration tests (build+run the jar,
  exercise the API, assert persistence and wallet events). The cross-language
  wallet case verifies the written `casino_events` schema and credit balance
  with the stdlib `sqlite3` driver (the Python casino wallet it used to replay
  with was retired in the C++20 rewrite).

## Build & run

```bash
cd mmo-server
./build.sh
./run-mmo-server.sh          # then open http://127.0.0.1:8080
```

Configuration (env): `MMO_PORT`, `MMO_BIND`, `MMO_GAME_DB`, `MMO_WALLET_DB`.

## Gameplay (v1)

Click to move (point & click). Click a tree to chop logs, or a rock to mine ore.
Open the inventory to sell items (coins are credited to your wallet store) or
bank them. Deposit gold into your wallet — on the pre-rewrite stack the balance
was read back through the same event-sourced wallet as the casino; today the
wallet events land in `casino.sqlite3` (see the note above). Everything
persists.
