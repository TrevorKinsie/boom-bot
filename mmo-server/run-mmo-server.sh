#!/usr/bin/env bash
#
# Run the boom-bot MMO game service.
#
#   MMO_PORT        - HTTP port (default 8080)
#   MMO_GAME_DB     - game/world SQLite path  (default <repo>/data/mmo.sqlite3)
#   MMO_WALLET_DB   - shared wallet SQLite path (default <repo>/data/casino.sqlite3)
#   MMO_BIND        - bind address (default 127.0.0.1)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR="$ROOT/build/mmo-server.jar"

if [ ! -f "$JAR" ]; then
    echo "game service not built; run ./build.sh first" >&2
    exit 1
fi

REPO_ROOT="$(cd "$ROOT/.." && pwd)"
export MMO_PORT="${MMO_PORT:-8080}"
export MMO_BIND="${MMO_BIND:-127.0.0.1}"
export MMO_GAME_DB="${MMO_GAME_DB:-$REPO_ROOT/data/mmo.sqlite3}"
export MMO_WALLET_DB="${MMO_WALLET_DB:-$REPO_ROOT/data/casino.sqlite3}"

mkdir -p "$(dirname "$MMO_GAME_DB")" "$(dirname "$MMO_WALLET_DB")"

SQLITE_JAR="$(ls "$ROOT"/build/sqlite-jdbc-*.jar 2>/dev/null | head -1 || true)"

echo "MMO server: http://${MMO_BIND}:${MMO_PORT}"
echo "  game db  : $MMO_GAME_DB"
echo "  wallet db: $MMO_WALLET_DB"

exec java -cp "$JAR${SQLITE_JAR:+:$SQLITE_JAR}" com.boombot.mmo.MmoServerMain