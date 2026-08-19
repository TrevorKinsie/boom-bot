#!/bin/sh
# Build the boom-bot C++ port and its self-tests with a bare g++ toolchain.
# Offline: no external libraries - JSON, money, HTTP (via curl subprocess)
# and the Telegram client are all implemented in src/.
set -eu

cd "$(dirname "$0")"

CXX=${CXX:-g++}
CXXFLAGS=${CXXFLAGS:--O2 -std=c++20 -Wall -Wextra -pedantic -D_POSIX_C_SOURCE=200809L}

mkdir -p build

SRC="src/bb_json.cpp src/bb_money.cpp src/bb_util.cpp src/bb_log.cpp \
     src/bb_config.cpp src/bb_http.cpp src/bb_data.cpp src/bb_regex.cpp \
     src/bb_nltk.cpp src/bb_llm.cpp src/bb_telegram.cpp src/bb_handlers.cpp \
     src/bb_event_store.cpp src/bb_wallet.cpp src/bb_zeus.cpp \
     src/bb_casino.cpp src/bb_leaderboard.cpp src/bb_casino_facade.cpp"

$CXX $CXXFLAGS -Isrc -o build/boombot-tests tests/test_main.cpp \
    tests/test_foundation.cpp tests/test_util.cpp tests/test_data.cpp \
    tests/test_regex.cpp tests/test_replies.cpp tests/test_nltk.cpp \
    tests/test_llm.cpp tests/test_telegram.cpp tests/test_handlers.cpp \
    tests/test_casino.cpp \
    $SRC

$CXX $CXXFLAGS -Isrc -o build/boombot src/bb_bot.cpp $SRC

echo "built: build/boombot-tests build/boombot"