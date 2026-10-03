# wagering-service

A dependency-free C port of the Kasino wagering domain, spoken over
JSON-lines on stdin/stdout just like the JVM decision engine. It can:

- manage event-sourced wallets (provision, credit, debit, reset, wager
  records, free spins),
- accept sponsorships, recorded with sponsor, purpose and reference for
  auditability,
- keep every wallet's event log and snapshots encrypted **at rest** with the
  service's own cipher.

## Why a roll-your-own cipher?

The service builds with a bare `gcc` and pulls in zero external libraries, so
the encryption is implemented in-tree (`src/bb_cipher.c`): a small 27-round
ARX block cipher ("BB64", 64-bit blocks, 128-bit keys, splitmix64 key
schedule) used in CTR mode with a CBC-MAC authenticating tag
(encrypt-then-MAC, two derived 128-bit keys). It ships with known-answer
self-test vectors and refuses to serve if they fail.

**This is honest, not certified.** BB64 is a hand-rolled design with no
published cryptanalysis and is far outside what you should trust for real
value. It fits this codebase's offline-build constraint and protects against
*accidental* exposure (a copied backup, a mis-set 0644, a stray share), but
production money should move to a cryptographically reviewed primitive
(libgcrypt, OpenSSL, or a hardware module) behind the same store interface.

## Layout

```
src/bb_util.[ch]   splitmix64, hex, growable buffers
src/bb_json.[ch]   minimal JSON DOM (no external lib)
src/bb_money.[ch]  fixed-point cents (2dp, overflow-checked, non-negative)
src/bb_cipher.[ch] BB64 block cipher, CTR, CBC-MAC, self-test
src/bb_wallet.[ch] event-sourced wallet aggregate + sponsorship records
src/bb_store.[ch]  per-wallet encrypted event log + snapshots
src/main.c         JSON-lines protocol loop (main)
src/bb_main.h      {}bb_handle_line: one request line -> one response line
tests/test_main.c  self-tests (cipher KAT, money, wallet, store, protocol)
build.sh           offline build (gcc only)
test.sh            build + run the self-tests
```

## Build & test

```sh
./build.sh        # -> build/wagering-service, build/wagering-service-tests
./test.sh         # builds and runs the whole battery
```

The self-tests also run under AddressSanitizer/UBSan in CI-less local runs;
an 3000-request soak with malformed input produces no sanitizer reports.

## Running

```sh
WAGERING_SERVICE_KEY=<64 hex chars> \
WAGERING_SERVICE_DATA_DIR=data \
./build/wagering-service
```

- `WAGERING_SERVICE_KEY` — 32 bytes of hex. The first 16 bytes encrypt
  (CTR), the last 16 authenticate (CBC-MAC). Unset/invalid falls back to the
  built-in development key with a loud warning; never use that key outside a
  dev sandbox.
- `WAGERING_SERVICE_DATA_DIR` — defaults to `./data`. The directory is
  created if missing, and store files are written `0600`.
- `WAGERING_SERVICE_FSYNC=0` — skip fsync after appends/snapshots (older
  systems or lower durability).

The process reads one JSON object per line from stdin and writes exactly one
response line per request. `crypto_selfcheck` answers a known-answer
self-test at server start too; a failure exits non-zero before serving.

## Protocol

Request: `{"id":"...","op":"...","user":"...", ...args}`

Success: `{"id":"...","ok":true,"data":{...wallet or {}...}}`
Failure: `{"id":"...","ok":false,"error":{"code":"...","message":"..."}}`

| op | args | wallets to reach | notes |
| --- | --- | --- | --- |
| `crypto_selfcheck` | — | none | `kat:"ok"` |
| `wallet_provision` | `starting_balance` | creates | `wallet_exists` on repeat |
| `wallet_get` | — | existing | full wallet state (incl. sponsorships) |
| `wallet_credit` | `amount`,`reason` | existing | |
| `wallet_debit` | `amount`,`reason` | existing | `insufficient_funds` on overdraw |
| `wallet_reset` | `reset_balance` | existing | |
| `free_spins_award` | `count` | existing | |
| `free_spins_redeem` | — | existing | `no_free_spins` when exhausted |
| `wager_record` | `wager`,`win`,`game` | existing | updates stats (biggest_win, games_played) |
| `sponsor_start` | `sponsor`,`amount`,`purpose`,`ref` | existing | credits the wallet, records sponsorship |
| `sponsorships_list` | — | existing | `data.sponsorships` array |

Wallet state in `data`:

```json
{"exists":true,"balance":"125.50","total_wagered":"5.00","total_won":"35.00",
 "biggest_win":"35.00","free_spins":0,"games_played":1,"seq":4,
 "sponsorships":[{"ref":"G-42","sponsor":"Globex","purpose":"welcome_bonus",
                  "amount":"25.50","ts":1787018280}]}
```

Money is passed and returned as decimal strings, quantised to cents (2dp),
matching the bot's `CASINO_CURRENCY_QUANTIZATION` of `0.01` (the env var is
kept by the C++20 port's `bb_config`).

## Durability & tamper handling

Every wallet is an append-only encrypted event log (`u<16-hex>.wlog`) plus an
optional snapshot (`u<16-hex>.snap`, magic `BBSN`). Each record is
`nonce(8) || CTR-encrypted JSON || CBC-MAC(8)`, and the tag covers the nonce
**and** the ciphertext, so any modification, truncation, or replay of a
record other than whole-file removal fails authentication and the wallet
refuses to load (the service replies `store_corrupt`). Whole-file removal
leniently falls back to a fresh wallet — true deletion is out of scope.

The `user` id hashes (splitmix64) to the filename, so the id never appears
on disk in cleartext; the JSON payloads themselves are sealed.

## Roadmap (not yet wired in)

- Adoption by the Telegram bot: a spawn/recovery gateway in the C++20 bot
  mirroring the former `JvmDecisionEngineGateway` pattern, placed behind the
  wallet-service seam instead of the in-process `WageringService`.
- Snapshot compaction hook (the store already supports it; nothing calls
  it yet), and a `reset`-style administrative RPC for operators.
