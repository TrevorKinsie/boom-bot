# Boom Bot

A simple Telegram bot that reacts with 💥 or sends explosion emojis.

## Features

*   `/boom`: Sends a random number (1-5) of 💥 emojis.
*   `/boom <number>`: Sends the specified number (1-5) of 💥 emojis.
*   `/boom <number > 5>`: Sends a sassy reply.
*   `/boom <number < 1>`: Sends a different sassy reply.
*   `/boom <non-number>`: Sends a sassy reply about needing a number.
*   Replying to a message with `/boom`: Adds a 💥 reaction to the replied message.

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

The bot should now be running and connected to Telegram.