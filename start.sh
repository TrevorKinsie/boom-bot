#!/usr/bin/env bash
#
# Fly.io container entrypoint: run the Telegram bot (C++20 binary) and the MMO
# game service (HTTP website) together on one Machine. An optional grammY
# fishing bot can run alongside them with its own Telegram token.
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

/app/bot-cpp/build/boombot &
BOT_PID=$!

# Telegram only permits one long-polling process per bot token. The fishing
# feature is intentionally optional here and uses FISHING_BOT_TOKEN so the
# current C++ bot can keep its existing token without competing for updates.
PIDS=("$BOT_PID" "$MMO_PID")
if [[ -n "${FISHING_BOT_TOKEN:-}" ]]; then
  node /app/fishing-bot/dist/src/index.js &
  FISHING_PID=$!
  PIDS+=("$FISHING_PID")
fi

# Always reap siblings, including when the first process exits non-zero or the
# container receives SIGTERM. `set -e` is disabled only around wait so cleanup
# can preserve the real child exit status.
cleanup() {
  local status=$?
  trap - EXIT
  kill "${PIDS[@]}" 2>/dev/null || true
  wait "${PIDS[@]}" 2>/dev/null || true
  exit "$status"
}

trap cleanup EXIT
trap 'exit 143' INT TERM
set +e
wait -n "${PIDS[@]}"
STATUS=$?
set -e
exit "$STATUS"
