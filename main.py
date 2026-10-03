#!/usr/bin/env python
"""
Boom Bot - A Telegram bot with various games and interactions.
This is the main entry point for the application.
"""

import logging
from boombot.core.bot import main

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    main()