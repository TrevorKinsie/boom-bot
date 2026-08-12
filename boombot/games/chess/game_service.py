"""Business logic for community games against Stockfish."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import chess

from boombot.games.chess.database import ChessDatabase
from boombot.games.chess.engine import StockfishEngine
from boombot.core.config import STOCKFISH_GAME_DEPTH

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
        logger.info(
            "Chess game creation requested chat_id=%s starter_user_id=%s "
            "difficulty=%s username_present=%s first_name_present=%s",
            chat_id,
            starter_user_id,
            difficulty,
            bool(starter_username),
            bool(first_name),
        )
        try:
            async with self._lock:
                logger.debug("Chess game creation lock acquired chat_id=%s", chat_id)
                self._ensure_user(starter_user_id, starter_username, first_name)
                if self.database.find_active_game(chat_id):
                    logger.warning("Chess game creation rejected: active game exists chat_id=%s", chat_id)
                    raise ValueError("A game is already active in this chat!")

                clamped = max(0, min(20, int(difficulty)))
                community_is_white = random.random() < 0.5
                board = chess.Board()
                logger.debug(
                    "Creating chess game record chat_id=%s difficulty=%s community_color=%s "
                    "initial_fen=%r",
                    chat_id,
                    clamped,
                    "w" if community_is_white else "b",
                    board.fen(),
                )
                game = self.database.create_game(chat_id, board.fen(), clamped)
                initial_cpu_move = ""

                if not community_is_white:
                    logger.info(
                        "Requesting initial Stockfish move game_id=%s chat_id=%s "
                        "depth=%s skill_level=%s",
                        game["id"],
                        chat_id,
                        STOCKFISH_GAME_DEPTH,
                        clamped,
                    )
                    best_move = await asyncio.to_thread(
                        self.engine.get_best_move, board.fen(), STOCKFISH_GAME_DEPTH, clamped
                    )
                    logger.debug(
                        "Initial Stockfish move returned game_id=%s best_move_uci=%r",
                        game["id"],
                        best_move,
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
                    logger.info(
                        "Initial Stockfish move persisted game_id=%s san=%s fen=%r",
                        game["id"],
                        san,
                        board.fen(),
                    )

                game["communityColor"] = "w" if community_is_white else "b"
                game["initialCpuMove"] = initial_cpu_move
                logger.info(
                    "Chess game created game_id=%s chat_id=%s community_color=%s "
                    "initial_cpu_move=%r",
                    game["id"],
                    chat_id,
                    game["communityColor"],
                    initial_cpu_move,
                )
                return game
        except ValueError:
            # Duplicate-game and input validation failures are expected user
            # outcomes, but still belong in the request's complete log.
            logger.warning(
                "Chess game creation rejected by validation chat_id=%s starter_user_id=%s",
                chat_id,
                starter_user_id,
                exc_info=True,
            )
            raise
        except Exception:
            logger.exception(
                "Chess game creation failed chat_id=%s starter_user_id=%s "
                "difficulty=%s",
                chat_id,
                starter_user_id,
                difficulty,
            )
            raise

    async def make_move(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        move_san: str,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "Chess move requested chat_id=%s user_id=%s move=%r "
            "username_present=%s first_name_present=%s",
            chat_id,
            user_id,
            move_san,
            bool(username),
            bool(first_name),
        )
        game_id: str | None = None
        current_fen: str | None = None
        try:
            async with self._lock:
                logger.debug("Chess move lock acquired chat_id=%s user_id=%s", chat_id, user_id)
                game = self.database.find_active_game(chat_id)
                if not game:
                    logger.warning(
                        "Chess move rejected because no active game exists chat_id=%s "
                        "user_id=%s move=%r",
                        chat_id,
                        user_id,
                        move_san,
                    )
                    return {
                        "success": False,
                        "failureCode": "no_active_game",
                        "message": "No active game in this chat. /newgame to start.",
                    }

                game_id = game["id"]
                user = self._ensure_user(user_id, username, first_name)
                current_fen = game["fen"]
                logger.debug(
                    "Loaded active chess game game_id=%s chat_id=%s difficulty=%s "
                    "current_fen=%r",
                    game_id,
                    chat_id,
                    game["difficulty"],
                    current_fen,
                )
                board = chess.Board(current_fen)

                move = board.parse_san(move_san.strip())
                user_move_from = chess.square_name(move.from_square)
                user_move_to = chess.square_name(move.to_square)
                logger.info(
                    "User chess move parsed game_id=%s move_san=%s from=%s to=%s",
                    game_id,
                    move_san.strip(),
                    user_move_from,
                    user_move_to,
                )

                logger.debug(
                    "Requesting pre-move Stockfish evaluation game_id=%s depth=%s "
                    "skill_level=%s fen=%r",
                    game_id,
                    STOCKFISH_GAME_DEPTH,
                    game["difficulty"],
                    current_fen,
                )
                eval_before = await asyncio.to_thread(
                    self.engine.get_evaluation,
                    current_fen,
                    STOCKFISH_GAME_DEPTH,
                    game["difficulty"],
                )
                san = board.san(move)
                board.push(move)
                fen_after_user = board.fen()
                logger.debug(
                    "User chess move applied game_id=%s san=%s fen_after_user=%r",
                    game_id,
                    san,
                    fen_after_user,
                )
                eval_after = await asyncio.to_thread(
                    self.engine.get_evaluation,
                    fen_after_user,
                    STOCKFISH_GAME_DEPTH,
                    game["difficulty"],
                )

                score_before = int(eval_before["score"])
                score_after = -int(eval_after["score"])
                score_delta = score_after - score_before
                logger.info(
                    "Chess move evaluations complete game_id=%s score_before=%s "
                    "score_after=%s score_delta=%s",
                    game_id,
                    score_before,
                    score_after,
                    score_delta,
                )
                self.database.add_score(user["id"], score_delta)

                self.database.create_move(
                    game_id=game_id,
                    user_id=user["id"],
                    username=user.get("username") or "Unknown",
                    move_san=san,
                    fen_after=fen_after_user,
                    move_number=board.fullmove_number,
                )
                logger.debug("Persisted user chess move game_id=%s san=%s", game_id, san)

                if board.is_game_over():
                    winner = self._winner(board)
                    self.database.update_game(
                        game_id, fen=fen_after_user, status="completed", winner=winner
                    )
                    logger.info(
                        "Chess game ended after user move game_id=%s winner=%s fen=%r",
                        game_id,
                        winner,
                        fen_after_user,
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

                logger.debug(
                    "Requesting post-user Stockfish move game_id=%s depth=%s "
                    "skill_level=%s fen=%r",
                    game_id,
                    STOCKFISH_GAME_DEPTH,
                    game["difficulty"],
                    fen_after_user,
                )
                best_move = await asyncio.to_thread(
                    self.engine.get_best_move,
                    fen_after_user,
                    STOCKFISH_GAME_DEPTH,
                    game["difficulty"],
                )
                logger.debug(
                    "Post-user Stockfish move returned game_id=%s best_move_uci=%r",
                    game_id,
                    best_move,
                )
                cpu_move = board.parse_uci(best_move)
                cpu_from = chess.square_name(cpu_move.from_square)
                cpu_to = chess.square_name(cpu_move.to_square)
                cpu_san = board.san(cpu_move)
                board.push(cpu_move)
                fen_after_cpu = board.fen()

                self.database.create_move(
                    game_id=game_id,
                    user_id=None,
                    username=None,
                    move_san=cpu_san,
                    fen_after=fen_after_cpu,
                    move_number=board.fullmove_number,
                )
                logger.info(
                    "Stockfish chess move persisted game_id=%s san=%s from=%s to=%s "
                    "fen_after_cpu=%r",
                    game_id,
                    cpu_san,
                    cpu_from,
                    cpu_to,
                    fen_after_cpu,
                )

                status = "active"
                winner = None
                if board.is_game_over():
                    status = "completed"
                    winner = self._winner(board)
                self.database.update_game(
                    game_id,
                    fen=fen_after_cpu,
                    status=status,
                    winner=winner,
                )

                moves = self.database.find_moves(game_id)
                first_move = moves[0] if moves else None
                community_is_black = bool(first_move and first_move["user_id"] is None)
                logger.info(
                    "Chess move transaction completed game_id=%s status=%s winner=%s "
                    "community_is_black=%s",
                    game_id,
                    status,
                    winner,
                    community_is_black,
                )
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
            logger.info(
                "Invalid chess move game_id=%s chat_id=%s user_id=%s move=%r "
                "current_fen=%r reason=%s",
                game_id,
                chat_id,
                user_id,
                move_san,
                current_fen,
                exc,
                exc_info=True,
            )
            return {
                "success": False,
                "failureCode": "invalid_move",
                "message": f"Invalid move or error: {move_san}",
            }
        except Exception as exc:
            logger.exception(
                "Chess move failed game_id=%s chat_id=%s user_id=%s move=%r "
                "current_fen=%r error_type=%s",
                game_id,
                chat_id,
                user_id,
                move_san,
                current_fen,
                type(exc).__name__,
            )
            return {
                "success": False,
                "failureCode": "internal_error",
                "message": "Unable to process the chess move. Please try again.",
            }

    async def resign_game(self, chat_id: int) -> dict[str, Any]:
        logger.info("Chess resign requested chat_id=%s", chat_id)
        try:
            async with self._lock:
                game = self.database.find_active_game(chat_id)
                if not game:
                    logger.warning("Chess resign rejected because no active game chat_id=%s", chat_id)
                    return {
                        "success": False,
                        "failureCode": "no_active_game",
                        "message": "No active game to resign.",
                    }
                board = chess.Board(game["fen"])
                winner = "black" if board.turn == chess.WHITE else "white"
                self.database.update_game(game["id"], status="completed", winner=winner)
                logger.info(
                    "Chess game resigned game_id=%s chat_id=%s winner=%s",
                    game["id"],
                    chat_id,
                    winner,
                )
                return {
                    "success": True,
                    "message": f"Game resigned. {winner.capitalize()} wins!",
                }
        except Exception:
            logger.exception("Chess resign failed chat_id=%s", chat_id)
            return {
                "success": False,
                "failureCode": "internal_error",
                "message": "Unable to resign the chess game.",
            }

    async def draw_game(self, chat_id: int) -> dict[str, Any]:
        logger.info("Chess draw requested chat_id=%s", chat_id)
        try:
            async with self._lock:
                game = self.database.find_active_game(chat_id)
                if not game:
                    logger.warning("Chess draw rejected because no active game chat_id=%s", chat_id)
                    return {
                        "success": False,
                        "failureCode": "no_active_game",
                        "message": "No active game to draw.",
                    }
                self.database.update_game(game["id"], status="completed", winner="draw")
                logger.info(
                    "Chess game ended by draw agreement game_id=%s chat_id=%s",
                    game["id"],
                    chat_id,
                )
                return {"success": True, "message": "Game ended in a draw by agreement."}
        except Exception:
            logger.exception("Chess draw failed chat_id=%s", chat_id)
            return {
                "success": False,
                "failureCode": "internal_error",
                "message": "Unable to end the chess game.",
            }

    def _ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> dict[str, Any]:
        logger.debug(
            "Ensuring chess user exists telegram_id=%s username_present=%s "
            "first_name_present=%s",
            telegram_id,
            bool(username),
            bool(first_name),
        )
        user = self.database.find_user_by_telegram_id(telegram_id)
        if user:
            if not user.get("username"):
                final_username = username or self._generated_username(telegram_id)
                self.database.update_user_username(user["id"], final_username)
                user["username"] = final_username
                logger.info("Filled missing chess username user_id=%s", user["id"])
            return user

        created = self.database.create_user(
            telegram_id,
            username or self._generated_username(telegram_id),
            first_name,
        )
        logger.info(
            "Created chess user user_id=%s telegram_id=%s",
            created["id"],
            telegram_id,
        )
        return created

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
