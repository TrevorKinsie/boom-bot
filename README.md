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
| `LLM_MODELS` | no | `deepseek/deepseek-chat-v3-0324:free,meta-llama/llama-3.3-70b-instruct:free,deepseek/deepseek-chat-v3-0324,meta-llama/llama-3.3-70b-instruct,openai/gpt-4o-mini` | Comma separated model chain, tried in order until one answers. |
| `LLM_MODEL` | no | – | Shorthand for pinning a single model (ignored if `LLM_MODELS` is set). |
| `LLM_FOLLOW_MODEL_HINTS` | no | `true` | Retry with the replacement slug when OpenRouter's 404 names one. Set to `false` to stay on the configured chain. |
| `LLM_TIMEOUT` | no | `30` | Per-request timeout in seconds. |
| `LLM_REFERER` / `LLM_APP_NAME` | no | – / `boom-bot` | Optional OpenRouter attribution headers. |

Free-tier models are rate limited and get retired without notice, which is why
the default is a chain rather than a single model — if the first one 404s or
429s the bot moves to the next. When every model fails, the reason is logged at
`WARNING` with the HTTP status and OpenRouter's error message.

OpenRouter has also been moving models off the free tier, answering the `:free`
slug with `This model is unavailable for free ... use this slug instead: <slug>`.
With `LLM_FOLLOW_MODEL_HINTS` on, the bot immediately retries the suggested slug
before continuing down the chain, so a retirement doesn't break `/whowouldwin`
until the config is edited. The suggested slug is normally the **paid** version
of the model, so those retries bill your OpenRouter credits — set
`LLM_FOLLOW_MODEL_HINTS=false` if you only ever want free models. The default
chain lists the paid twins explicitly for the same reason; drop them from
`LLM_MODELS` to keep the bot free-tier only.

A `No endpoints found for <model>` 404 is different: the slug exists but no
provider will serve it for your account. That is usually credits or the data
policy at <https://openrouter.ai/settings/privacy>, not something a config
change here fixes.

The bot should now be running and connected to Telegram.