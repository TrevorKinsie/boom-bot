# Boom Bot

A Telegram bot that provides boom counts and plays Craps.

## Features

*   `/boom`: Sends a random number (1-5) of 💥 emojis.
*   `/boom <number>`: Sends the specified number (1-5) of 💥 emojis.
*   `/boom <number > 5>`: Sends a sassy reply.
*   `/boom <number < 1>`: Sends a different sassy reply.
*   `/boom <non-number>`: Sends a sassy reply about needing a number.
*   `/howmanybooms <question>`: Asks the bot how many booms something deserves (e.g., `/howmanybooms does my cat deserve`). The bot remembers questions and provides consistent (randomly assigned) answers using NLTK for fuzzy matching.
*   Sending a photo with `/howmanybooms <question>` in the caption: Same as the text command, but triggered by a photo caption.
*   `/whowouldwin <contenders>`: Asks an LLM to call a hypothetical fight (e.g. `/whowouldwin lions vs tigers`, `/whowouldwin between 100 men and one gorilla`). Requires `LLM_API_KEY` (see below).
*   **Craps Game (Multi-Channel & Multi-Player):**
    *   `/roll`: Rolls the dice for the current channel's Craps game. Resolves bets for all players in the channel.
    *   `/bet <type> <amount>`: Places a bet for the user in the current channel. Valid types include `pass_line`, `dont_pass`, `field`, `place_4`, `place_5`, `place_6`, `place_8`, `place_9`, `place_10`. (e.g., `/bet pass_line 10`, `/bet place 6 12`).
    *   `/showgame`: Displays the current channel's game state (Point, Phase) and the user's current balance and active bets.
    *   `/resetmygame`: Resets the user's balance to the starting amount ($100) and clears their bets within the current channel.
    *   `/crapshelp`: Shows detailed rules and commands for the Craps game.

## Running the Bot

1.  **Clone the repository (or download the files):**
    ```bash
    git clone <repository_url> # Or download ZIP
    cd boom-bot
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: This will also download necessary NLTK data on first run if not present.)*

4.  **Get a Telegram Bot Token:**
    *   Talk to [@BotFather](https://t.me/BotFather) on Telegram.
    *   Create a new bot using `/newbot`.
    *   Copy the token BotFather gives you.

5.  **Create a `.env` file:**
    *   Create a file named `.env` in the `boom-bot` directory.
    *   Add the following line, replacing `YOUR_TOKEN_HERE` with the token you got from BotFather:
      ```
      TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
      ```

6.  **Run the bot:**
    ```bash
    python bot.py
    ```

## LLM Configuration (`/whowouldwin`)

`/whowouldwin` calls [OpenRouter](https://openrouter.ai). Set these in `.env`:

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
tried in order until one answers, and when they all fail the reason is logged at
`WARNING` with the HTTP status and OpenRouter's error message. Two 404s are
worth recognising in those logs:

- `This model is unavailable for free ... use this slug instead: <slug>` — the
  model moved to paid. Set `LLM_FOLLOW_MODEL_HINTS=true` to have the bot retry
  the named slug automatically; it is off by default because that slug bills
  your credits. Either way the suggestion is logged.
- `No endpoints found for <model>` — the slug exists but no provider will serve
  it for your account. Usually credits or the data policy at
  <https://openrouter.ai/settings/privacy>, not something a config change fixes.

The bot should now be running and connected to Telegram.