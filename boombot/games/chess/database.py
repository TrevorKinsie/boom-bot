"""Durable SQLite storage for the Chess Challenge feature.

The original chess bot used a small repository layer over PostgreSQL.  This
module keeps those boundaries and fields while using SQLite, which matches
boom-bot's single-process deployment and existing mounted `/data` volume.
"""

from __future__ import annotations

from functools import wraps
import logging
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from boombot.core.config import CHESS_DATABASE_FILE


logger = logging.getLogger(__name__)


def _logged_database_operation(operation: str):
    """Log every repository boundary without exposing SQL parameters."""

    def decorator(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            logger.debug("Chess database operation started operation=%s", operation)
            try:
                result = method(self, *args, **kwargs)
            except Exception:
                logger.exception(
                    "Chess database operation failed operation=%s",
                    operation,
                )
                raise
            logger.debug("Chess database operation completed operation=%s", operation)
            return result

        return wrapped

    return decorator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    score INTEGER NOT NULL DEFAULT 1200,
    matches_played INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    fen TEXT NOT NULL,
    pgn TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    chat_id INTEGER NOT NULL,
    white_player_id TEXT REFERENCES users(id),
    black_player_id TEXT REFERENCES users(id),
    winner TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    difficulty INTEGER NOT NULL DEFAULT 20,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_games_active_chat
    ON games(chat_id, status);
CREATE INDEX IF NOT EXISTS idx_games_analysis
    ON games(status, analysis_status);

CREATE TABLE IF NOT EXISTS moves (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    game_id TEXT NOT NULL REFERENCES games(id),
    user_id TEXT REFERENCES users(id),
    username TEXT,
    move_san TEXT NOT NULL,
    fen_after TEXT NOT NULL,
    move_number INTEGER NOT NULL,
    evaluation_score INTEGER,
    best_move_suggestion TEXT,
    is_blunder INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moves_game
    ON moves(game_id, sequence);
"""


class ChessDatabase:
    """Thread-safe repository facade used by the game and analysis services."""

    def __init__(self, path: Path | str = CHESS_DATABASE_FILE):
        self.path = Path(path)
        logger.info("Opening chess database path=%s", self.path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._lock = threading.RLock()
            self._connection = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=30,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript(SCHEMA)
            self._connection.commit()
            logger.info("Chess database ready path=%s", self.path)
        except Exception:
            logger.exception("Chess database initialization failed path=%s", self.path)
            raise

    @_logged_database_operation("close")
    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _row(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        try:
            with self._lock:
                row = self._connection.execute(query, params).fetchone()
                return dict(row) if row else None
        except Exception:
            logger.exception(
                "Chess database single-row query failed query=%s",
                " ".join(query.split())[:240],
            )
            raise

    def _rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            with self._lock:
                return [
                    dict(row)
                    for row in self._connection.execute(query, params).fetchall()
                ]
        except Exception:
            logger.exception(
                "Chess database multi-row query failed query=%s",
                " ".join(query.split())[:240],
            )
            raise

    @_logged_database_operation("find_user_by_telegram_id")
    def find_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        return self._row("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

    @_logged_database_operation("create_user")
    def create_user(
        self,
        telegram_id: int,
        username: str,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO users (id, telegram_id, username, first_name)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, telegram_id, username, first_name),
            )
            self._connection.commit()
        return self._row("SELECT * FROM users WHERE id = ?", (user_id,))  # type: ignore[return-value]

    @_logged_database_operation("update_user_username")
    def update_user_username(self, user_id: str, username: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (username, user_id),
            )
            self._connection.commit()

    @_logged_database_operation("add_score")
    def add_score(self, user_id: str, delta: int) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE users SET score = score + ? WHERE id = ?",
                (delta, user_id),
            )
            self._connection.commit()

    @_logged_database_operation("find_active_game")
    def find_active_game(self, chat_id: int) -> dict[str, Any] | None:
        return self._row(
            """
            SELECT * FROM games
            WHERE chat_id = ? AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (chat_id,),
        )

    @_logged_database_operation("create_game")
    def create_game(self, chat_id: int, fen: str, difficulty: int) -> dict[str, Any]:
        game_id = str(uuid.uuid4())
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO games (id, fen, status, chat_id, difficulty)
                VALUES (?, ?, 'active', ?, ?)
                """,
                (game_id, fen, chat_id, difficulty),
            )
            self._connection.commit()
        return self._row("SELECT * FROM games WHERE id = ?", (game_id,))  # type: ignore[return-value]

    @_logged_database_operation("update_game")
    def update_game(
        self,
        game_id: str,
        *,
        fen: str | None = None,
        status: str | None = None,
        winner: str | None = None,
        analysis_status: str | None = None,
    ) -> None:
        changes: dict[str, Any] = {}
        if fen is not None:
            changes["fen"] = fen
        if status is not None:
            changes["status"] = status
        if winner is not None:
            changes["winner"] = winner
        if analysis_status is not None:
            changes["analysis_status"] = analysis_status
        if not changes:
            return

        assignments = ", ".join(f"{key} = ?" for key in changes)
        values = tuple(changes.values()) + (game_id,)
        with self._lock:
            self._connection.execute(
                f"UPDATE games SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
            self._connection.commit()

    @_logged_database_operation("find_pending_analysis")
    def find_pending_analysis(self, limit: int = 1) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT * FROM games
            WHERE status = 'completed' AND analysis_status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )

    @_logged_database_operation("create_move")
    def create_move(
        self,
        *,
        game_id: str,
        user_id: str | None,
        username: str | None,
        move_san: str,
        fen_after: str,
        move_number: int,
    ) -> dict[str, Any]:
        move_id = str(uuid.uuid4())
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO moves
                    (id, game_id, user_id, username, move_san, fen_after, move_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (move_id, game_id, user_id, username, move_san, fen_after, move_number),
            )
            self._connection.commit()
        return self._row("SELECT * FROM moves WHERE id = ?", (move_id,))  # type: ignore[return-value]

    @_logged_database_operation("find_moves")
    def find_moves(self, game_id: str) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY sequence ASC",
            (game_id,),
        )

    @_logged_database_operation("update_move_analysis")
    def update_move_analysis(
        self,
        move_id: str,
        *,
        best_move_suggestion: str,
        evaluation_score: int,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE moves
                SET best_move_suggestion = ?, evaluation_score = ?
                WHERE id = ?
                """,
                (best_move_suggestion, evaluation_score, move_id),
            )
            self._connection.commit()
