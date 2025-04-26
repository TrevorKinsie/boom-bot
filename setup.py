from setuptools import setup, find_packages

setup(
    name="boombot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot>=20.0",
        "python-dotenv",
        "nltk",
        "inflect",
    ],
    entry_points={
        "console_scripts": [
            "boombot=boombot.core.bot:main",
        ],
    },
    author="Kevin Stewart",
    description="A Telegram bot with various games and features",
    keywords="telegram, bot, games, craps, roulette",
    python_requires=">=3.10",
)