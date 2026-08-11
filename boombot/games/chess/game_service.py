"""Business logic for community games against Stockfish."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import chess

from boombot.games.chess.database import ChessDatabase
from boombot.games.chess.engine import StockfishEngine

logger = logging.getLogger(__name__)


class GameService:
    def __init__(self, database: ChessDatabase, engine: StockfishEngine):
        self.database = database
        self.engine = engine
        self._lock = asyncio.Lock()

    async def create_game(
        self,
        chat_id: int,
        starter_user_id: int,
        starter_username: str | None,
        difficulty: int = 20,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            self._ensure_user(starter_user_id, starter_username, first_name)
            if self.database.find_active_game(chat_id):
                raise ValueError("A game is already active in this chat!")

            clamped = max(0, min(20, int(difficulty)))
            community_is_white = random.random() < 0.5
            board = chess.Board()
            game = self.database.create_game(chat_id, board.fen(), clamped)
            initial_cpu_move = ""

            if not community_is_white:
                best_move = await asyncio.to_thread(
                    self.engine.get_best_move, board.fen(), 10, clamped
                )
                move = board.parse_uci(best_move)
                san = board.san(move)
                board.push(move)
                self.database.create_move(
                    game_id=game["id"],
                    user_id=None,
                    username=None,
                    move_san=san,
                    fen_after=board.fen(),
                    move_number=board.fullmove_number,
                )
                self.database.update_game(game["id"], fen=board.fen())
                game["fen"] = board.fen()
                initial_cpu_move = san

            game["communityColor"] = "w" if community_is_white else "b"
            game["initialCpuMove"] = initial_cpu_move
            return game

    async def make_move(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        move_san: str,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            game = self.database.find_active_game(chat_id)
            if not game:
                return {
                    "success": False,
                    "message": "No active game in this chat. /newgame to start.",
                }

            user = self._ensure_user(user_id, username, first_name)
            current_fen = game["fen"]
            board = chess.Board(current_fen)

            try:
                move = board.parse_san(move_san.strip())
                user_move_from = chess.square_name(move.from_square)
                user_move_to = chess.square_name(move.to_square)

                eval_before = await asyncio.to_thread(
                    self.engine.get_evaluation,
                    current_fen,
                    10,
                    game["difficulty"],
                )
                san = board.san(move)
                board.push(move)
                fen_after_user = board.fen()
                eval_after = await asyncio.to_thread(
                    self.engine.get_evaluation,
                    fen_after_user,
                    10,
                    game["difficulty"],
                )

                score_before = int(eval_before["score"])
                score_after = -int(eval_after["score"])
                score_delta = score_after - score_before
                self.database.add_score(user["id"], score_delta)

                self.database.create_move(
                    game_id=game["id"],
                    user_id=user["id"],
                    username=user.get("username") or "Unknown",
                    move_san=san,
                    fen_after=fen_after_user,
                    move_number=board.fullmove_number,
                )

                if board.is_game_over():
                    winner = self._winner(board)
                    self.database.update_game(
                        game["id"], fen=fen_after_user, status="completed", winner=winner
                    )
                    return {
                        "success": True,
                        "message": f"Game Over! {'Draw' if winner == 'draw' else winner + ' wins!'}",
                        "fen": fen_after_user,
                        "game": {**game, "fen": fen_after_user},
                        "userMoveFrom": user_move_from,
                        "userMoveTo": user_move_to,
                        "scoreDelta": score_delta,
                        "evalScore": score_after,
                    }

                best_move = await asyncio.to_thread(
                    self.engine.get_best_move,
                    fen_after_user,
                    15,
                    game["difficulty"],
                )
                cpu_move = board.parse_uci(best_move)
                cpu_from = chess.square_name(cpu_move.from_square)
                cpu_to = chess.square_name(cpu_move.to_square)
                cpu_san = board.san(cpu_move)
                board.push(cpu_move)
                fen_after_cpu = board.fen()

                self.database.create_move(
                    game_id=game["id"],
                    user_id=None,
                    username=None,
                    move_san=cpu_san,
                    fen_after=fen_after_cpu,
                    move_number=board.fullmove_number,
                )

                status = "active"
                winner = None
                if board.is_game_over():
                    status = "completed"
                    winner = self._winner(board)
                self.database.update_game(
                    game["id"],
                    fen=fen_after_cpu,
                    status=status,
                    winner=winner,
                )

                moves = self.database.find_moves(game["id"])
                first_move = moves[0] if moves else None
                community_is_black = bool(first_move and first_move["user_id"] is None)
                return {
                    "success": True,
                    "message": f"You played {san}. I played {cpu_san}.",
                    "fen": fen_after_cpu,
                    "cpuMove": cpu_san,
                    "isCommunityBlack": community_is_black,
                    "game": {**game, "fen": fen_after_cpu, "status": status},
                    "moveNumber": board.fullmove_number,
                    "scoreDelta": score_delta,
                    "evalScore": score_after,
                    "userMoveFrom": user_move_from,
                    "userMoveTo": user_move_to,
                    "cpuMoveFrom": cpu_from,
                    "cpuMoveTo": cpu_to,
                }
            except (chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError) as exc:
                logger.info("Invalid chess move %r: %s", move_san, exc)
                return {"success": False, "message": f"Invalid move or error: {move_san}"}
            except Exception:
                logger.exception("Error making chess move")
                return {"success": False, "message": f"Invalid move or error: {move_san}"}

    async def resign_game(self, chat_id: int) -> dict[str, Any]:
        async with self._lock:
            game = self.database.find_active_game(chat_id)
            if not game:
                return {"success": False, "message": "No active game to resign."}
            board = chess.Board(game["fen"])
            winner = "black" if board.turn == chess.WHITE else "white"
            self.database.update_game(game["id"], status="completed", winner=winner)
            return {
                "success": True,
                "message": f"Game resigned. {winner.capitalize()} wins!",
            }

    async def draw_game(self, chat_id: int) -> dict[str, Any]:
        async with self._lock:
            game = self.database.find_active_game(chat_id)
            if not game:
                return {"success": False, "message": "No active game to draw."}
            self.database.update_game(game["id"], status="completed", winner="draw")
            return {"success": True, "message": "Game ended in a draw by agreement."}

    def _ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> dict[str, Any]:
        user = self.database.find_user_by_telegram_id(telegram_id)
        if user:
            if not user.get("username"):
                final_username = username or self._generated_username(telegram_id)
                self.database.update_user_username(user["id"], final_username)
                user["username"] = final_username
            return user

        return self.database.create_user(
            telegram_id,
            username or self._generated_username(telegram_id),
            first_name,
        )

    @staticmethod
    def _generated_username(telegram_id: int) -> str:
        adjectives = [
            "Bold", "Lazy", "Happy", "Brave", "Calm", "Eager", "Fair", "Gentle",
            "Jolly", "Kind", "Lively", "Nice", "Proud", "Quiet", "Silly", "Witty",
        ]
        nouns = [
            "Pawn", "Knight", "Bishop", "Rook", "Queen", "King", "Board", "Check",
            "Mate", "Gambit", "Castle", "Rank", "File",
        ]
        return f"{random.choice(adjectives)}{random.choice(nouns)}{str(telegram_id)[-4:]}"

    @staticmethod
    def _winner(board: chess.Board) -> str:
        if board.is_checkmate():
            return "black" if board.turn == chess.WHITE else "white"
        return "draw"
