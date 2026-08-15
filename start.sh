#!/usr/bin/env bash
#
# Fly.io container entrypoint: run the Telegram bot and the MMO game service
# (HTTP website) together on one Machine.
#
set -euo pipefail

export MMO_BIND="${MMO_BIND:-0.0.0.0}"
export MMO_PORT="${MMO_PORT:-8080}"
export MMO_GAME_DB="${MMO_GAME_DB:-/data/mmo.sqlite3}"
export MMO_WALLET_DB="${MMO_WALLET_DB:-/data/casino.sqlite3}"

mkdir -p "$(dirname "$MMO_GAME_DB")" "$(dirname "$MMO_WALLET_DB")"

SQLITE_JAR="$(ls /app/mmo-server/build/sqlite-jdbc-*.jar 2>/dev/null | head -1 || true)"

java -cp "/app/mmo-server/build/mmo-server.jar${SQLITE_JAR:+:$SQLITE_JAR}" com.boombot.mmo.MmoServerMain &
MMO_PID=$!

python main.py &
BOT_PID=$!

# If either process exits, tear down the container so Fly restarts it cleanly.
wait -n "$BOT_PID" "$MMO_PID"
STATUS=$?
kill "$BOT_PID" "$MMO_PID" 2>/dev/null || true
wait "$BOT_PID" "$MMO_PID" 2>/dev/null || true
exit "$STATUS"
