# Boom Bot

A Telegram bot that provides boom counts and runs an enterprise casino.

Since the C++20 rewrite the bot is a **standalone C++20 binary** (`bot-cpp/`)
built with nothing but `g++` — JSON, money, HTTP (via a `curl` subprocess), the
Telegram client, NLTK-style fuzzy matching, and the LLM client are all
implemented in `bot-cpp/src/`. The Python implementation was retired in the
port; chess now runs against the in-house Objective-C engine
(`chess-objc/`), a UCI subprocess driven through `bot-cpp/src/bb_chess.cpp`.


## Features

*   `/boom`: Sends a random number (1-5) of 💥 emojis.
*   `/boom <number>`: Sends the specified number (1-5) of 💥 emojis.
*   `/boom <number > 5>`: Sends a sassy reply.
*   `/boom <number < 1>`: Sends a different sassy reply.
*   `/boom <non-number>`: Sends a sassy reply about needing a number.
*   `/howmanybooms <question>`: Asks the bot how many booms something deserves
    (e.g., `/howmanybooms does my cat deserve`). The bot remembers questions
    and provides consistent (randomly assigned) answers using fuzzy matching
    (NLTK logic ported to `bot-cpp/src/bb_nltk.cpp`).
*   Sending a photo with `/howmanybooms <question>` in the caption: Same as the
    text command, but triggered by a photo caption.
*   `/whowouldwin <contenders>`: Asks an LLM to call a hypothetical fight
    (e.g. `/whowouldwin lions vs tigers`, `/whowouldwin between 100 men and
    one gorilla`). Requires `LLM_API_KEY` (see below).
*   `/friggedthedeposit <name>`: Asks the LLM for a humorous story about how
    the named person frigged the deposit (e.g. `/friggedthedeposit Kevin`).
*   **Enterprise Casino (unified, event-sourced wallet):**
    *   One persistent wallet per player across all games. State is stored as
        an append-only domain-event stream (JSON Lines with per-aggregate
        snapshots).
    *   `/wallet`: Show your unified balance, free spins, and cumulative stats.
    *   `/leaderboard`: Show the top players ranked by balance.
    *   `/resetwallet`: Restore your balance to the starting amount.
    *   `/roulette <type> [number] <amount>`: Place a roulette wager, e.g.
        `/roulette red 10`, `/roulette straight 7 10`.
    *   `/roulettespin`: Spin the wheel and settle this chat's roulette wagers.
    *   `/craps <type> <amount>`: Place a craps wager, e.g.
        `/craps pass_line 10`, `/craps any_seven 5`.
    *   `/crapsroll`: Roll the dice and settle this chat's craps wagers.
    *   `/zeus`: Spin the persistent Zeus reel family (four/five-of-a-kind
        earn free spins, jackpots pay 5,000 coins; replies use MarkdownV2).
*   **Chess Challenge (community vs the in-house engine):** `/chess
    [difficulty 0-20]` or `/newgame` starts a game against the Objective-C
    engine; `/move <SAN>` (e.g. `/move Nf3`) or a bare message (e.g. `e4`)
    plays; `/resign`, `/draw`, `/board` manage the game. Board and
    end-of-game detection come from the engine itself (no Stockfish). See
    [Chess Challenge configuration](#chess-challenge-configuration).
*   **Lake Ontario Fishing (native grammY bot):** `/fish` opens a stateful
    inline-keyboard fishing camp; players collect rods, reusable lures, bait,
    and fish, then sell catches for gold. Larger species need better bait and
    can miss or break an equipped rod. Catches are shown with a Wikipedia image
    resolved for that species.

The legacy multi-channel Python games (`/roll`, `/bet`, `/showgame`,
`/resetmygame`, `/crapshelp` and the standalone roulette/Zeus handlers) were
removed with the Python retirement; the casino wagering commands above are
their unified replacement.

## Repository layout

| Path | What it is |
| --- | --- |
| `bot-cpp/` | The Telegram bot: C++20 sources, headers, self-tests, `build.sh` |
| `fishing-bot/` | Native grammY Lake Ontario fishing bot, assets, domain tests |
| `chess-objc/` | The in-house Objective-C chess engine (UCI) the bot plays against |
| `decision-engine/` | JVM Decision Engine (Java middleware + Rust atomic logic) |
| `wagering-service/` | Standalone C wallet service (encrypted event logs, sponsorship) |
| `mmo-server/` | Persistent browser MMO (Java service + Three.js client) |
| `tests/` | Python integration tests for the C wagering service and the MMO (the C++20 bot's own suite lives in `bot-cpp/tests`) |
| `data/` | Runtime state: casino event log, chess games file, MMO world DB |

## Building

The bot builds with a bare `g++` toolchain — no external libraries. You need a
C++20-capable compiler (g++ 12 or newer) and `curl` at runtime. There is no
`make`; `build.sh` invokes the compiler directly:

```bash
cd bot-cpp
./build.sh            # produces build/boombot and build/boombot-tests
./build/boombot-tests # self-tests: 0 failures
```

Chess needs the engine binary; build it once (a C compiler with Objective-C
support and `libobjc`):

```bash
cd chess-objc
make clean && make all   # produces build/chess-objc
```

JSON (dom/existential), money (fixed-point cents), regex, NLTK-style fuzzy
matching, the OpenRouter client, the Telegram long-polling client, the
event-sourced wallet store, and the casino application service are all
implemented in `bot-cpp/src/` (`bb_*.cpp`).

## Running the Bot

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd boom-bot
    ```

2.  **Get a Telegram Bot Token:**
    *   Talk to [@BotFather](https://t.me/BotFather) on Telegram.
    *   Create a new bot using `/newbot`.
    *   Copy the token BotFather gives you.

3.  **Set the token** (the bot reads the environment directly, or a `.env`
    via your shell):
    ```bash
    export TELEGRAM_TOKEN=YOUR_TOKEN_HERE
    ```

4.  **Build and run the bot:**
    ```bash
    ./bot-cpp/build.sh
    ./bot-cpp/build/boombot
    ```

    Optional: on Windows the token is read from `TELEGRAM_TOKEN_DEV` instead
    (matching the previous Python behaviour).

## Native Telegram Fishing bot (grammY)

The fishing game lives in `fishing-bot/` and uses grammY with a durable JSON
store. It provides `/fish`, `/gear`, and `/collection`, with all equipment
selection, purchases, casting, repairs, and sales handled by inline buttons.
The first biome is Lake Ontario; the fish catalog stores realistic species,
weight ranges, tiers, odds, and Wikipedia page names so caught fish can be
rendered from their encyclopedia image.

The existing production bot in this checkout is a C++ long-poller. Telegram
does not allow two polling processes to share one token, so the optional
fishing process uses a separate `FISHING_BOT_TOKEN` (create a second bot with
BotFather) while preserving the existing bot token:

```bash
cd fishing-bot
npm ci
FISHING_BOT_TOKEN=YOUR_FISHING_TOKEN npm start
```

In the Docker/Fly image, setting `FISHING_BOT_TOKEN` starts it alongside the
existing bot and persists angler state in `${BOT_DATA_DIR}/fishing.json`.
Fishing gold is currently its own game economy, separate from the C++ casino
wallet.
Do not point both long-pollers at the same Telegram token.

## LLM Configuration (`/whowouldwin`, `/friggedthedeposit`)

Both commands call [OpenRouter](https://openrouter.ai) through the ported
`bb_llm.cpp` client. Set these in the environment:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LLM_API_KEY` | yes | – | OpenRouter API key. Without it the command replies that it isn't configured. |
| `LLM_MODELS` | no | `openrouter/free` | Comma separated model chain, tried in order until one answers. |
| `LLM_MODEL` | no | – | Shorthand for pinning a single model (ignored if `LLM_MODELS` is set). |
| `LLM_FOLLOW_MODEL_HINTS` | no | `false` | When a 404 names a replacement slug, retry it. Off by default — the replacement is normally the paid model. |
| `LLM_TIMEOUT` | no | `30` | Per-request timeout in seconds. |
| `LLM_REFERER` / `LLM_APP_NAME` | no | – / `boom-bot` | Optional OpenRouter attribution headers. |

The default is [`openrouter/free`](https://openrouter.ai/openrouter/free),
OpenRouter's free-models router: it picks a currently available free model that
can serve the request. Pinning individual `:free` slugs is what used to break
this command — they get rate limited and retired without notice, and OpenRouter
has been moving them to paid — so let the router absorb that churn instead.
Free usage is capped at 20 requests/minute and 1,000/day (50/day until you have
ever added $10 in credits).

`LLM_MODELS` still takes a chain if you want to pin specific models: they are
tried in order until one answers, and when they all fail the reason is logged
with the HTTP status and OpenRouter's error message. Two 404s are worth
recognising in those logs:

- `This model is unavailable for free ... use this slug instead: <slug>` — the
  model moved to paid. Set `LLM_FOLLOW_MODEL_HINTS=true` to have the bot retry
  the named slug automatically; it is off by default because that slug bills
  your credits. Either way the suggestion is logged.
- `No endpoints found for <model>` — the slug exists but no provider will serve
  it for your account. Usually credits or the data policy at
  <https://openrouter.ai/settings/privacy>, not something a config change fixes.

The bot should now be running and connected to Telegram.
