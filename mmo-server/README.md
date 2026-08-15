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
  depositing gold appends wallet **domain events** to the *same*
  `casino_events` SQLite table the shared casino microkernel owns
  (`data/casino.sqlite3`), keyed by aggregate `mmo:<player>`, using the exact
  Python event-sourced schema (`WalletCreatedEvent`, `FundsCreditedEvent`). The
  MMO is another writer to the one append-only wallet store.

## What's here

* `build.sh` — offline `javac` build; vendors `sqlite-jdbc` and bundles it (plus
  the browser client) into `build/mmo-server.jar`.
* `run-mmo-server.sh` — starts the service and serves the browser client.
* `pom.xml` — equivalent Maven build for teams that prefer it.
* `src/main/java/com/boombot/mmo/` — game service sources.
* `src/main/resources/static/` — Three.js low-poly browser client.
* `../../tests/test_mmo_server.py` — cross-language integration tests
  (build+run the jar, exercise the API, assert persistence and wallet events).

## Build & run

```bash
cd mmo-server
./build.sh
./run-mmo-server.sh          # then open http://127.0.0.1:8080
```

Configuration (env): `MMO_PORT`, `MMO_BIND`, `MMO_GAME_DB`, `MMO_WALLET_DB`.

## Gameplay (v1)

Click to move (point & click). Click a tree to chop logs, or a rock to mine ore.
Open the inventory to sell items (coins are credited to your shared wallet) or
bank them. Deposit gold into your wallet — the balance is read back through the
same event-sourced wallet as the casino. Everything persists.