from setuptools import setup, find_packages

setup(
    name="boombot",
    version="0.1.0",
    # Only the Chess Challenge reference remains Python-side; the Telegram bot
    # and casino run as the C++20 binary in bot-cpp/. There is no Python bot
    # entry point anymore.
    packages=find_packages(),
    package_data={
        "boombot.games.chess": ["assets/merida/*.png", "assets/fonts/*.ttf"],
    },
    author="Kevin Stewart",
    description="A Telegram bot with various games and features",
    keywords="telegram, bot, games, chess, casino",
    python_requires=">=3.10",
)
