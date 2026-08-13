"""Background post-game analysis and move grading."""

from __future__ import annotations

import asyncio
import logging

import chess

from boombot.core.config import STOCKFISH_ANALYSIS_DEPTH
from boombot.games.chess.database import ChessDatabase
from boombot.games.chess.engine import StockfishEngine

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, database: ChessDatabase, engine: StockfishEngine):
        self.database = database
        self.engine = engine

    async def process_pending_games(self) -> None:
        logger.debug("Chess analysis queue tick started")
        try:
            games = self.database.find_pending_analysis(1)
            if games:
                logger.info(
                    "Chess analysis queue selected game game_id=%s pending_count=%s",
                    games[0]["id"],
                    len(games),
                )
                await self.analyze_game(games[0]["id"])
            else:
                logger.debug("Chess analysis queue found no pending games")
        except Exception:
            logger.exception("Chess analysis processing error while polling pending games")

    async def analyze_game(self, game_id: str) -> None:
        logger.info("Chess game analysis started game_id=%s", game_id)
        self.database.update_game(game_id, analysis_status="processing")
        try:
            moves = self.database.find_moves(game_id)
            if not moves:
                logger.error("Chess game analysis found no moves game_id=%s", game_id)
                raise ValueError("No moves found")

            board = chess.Board()
            logger.info(
                "Chess game analysis replay started game_id=%s move_count=%s",
                game_id,
                len(moves),
            )
            for index, record in enumerate(moves, start=1):
                logger.debug(
                    "Replaying chess analysis move game_id=%s index=%s move_id=%s "
                    "sequence=%s user_id=%s move_san=%r fen_after=%r",
                    game_id,
                    index,
                    record.get("id"),
                    record.get("sequence"),
                    record.get("user_id"),
                    record.get("move_san"),
                    record.get("fen_after"),
                )
                if record["user_id"]:
                    current_fen = board.fen()
                    logger.debug(
                        "Requesting analysis best move game_id=%s move_id=%s fen=%r "
                        "depth=%s",
                        game_id,
                        record["id"],
                        current_fen,
                        STOCKFISH_ANALYSIS_DEPTH,
                    )
                    best_move_uci = await asyncio.to_thread(
                        self.engine.get_best_move,
                        current_fen,
                        STOCKFISH_ANALYSIS_DEPTH,
                        20,
                    )
                    user_move = board.parse_san(record["move_san"])
                    best_move = board.parse_uci(best_move_uci)
                    score = 100 if user_move == best_move else 50
                    logger.info(
                        "Chess move analysis scored game_id=%s move_id=%s user_move=%s "
                        "best_move=%s score=%s",
                        game_id,
                        record["id"],
                        record["move_san"],
                        best_move_uci,
                        score,
                    )
                    self.database.update_move_analysis(
                        record["id"],
                        best_move_suggestion=best_move_uci,
                        evaluation_score=score,
                    )
                try:
                    board.push_san(record["move_san"])
                except (chess.IllegalMoveError, chess.InvalidMoveError) as exc:
                    logger.warning(
                        "Invalid move in chess replay game_id=%s move_id=%s "
                        "move_san=%r reason=%s",
                        game_id,
                        record.get("id"),
                        record["move_san"],
                        exc,
                        exc_info=True,
                    )

            self.database.update_game(game_id, analysis_status="completed")
            logger.info(
                "Chess game analysis completed game_id=%s move_count=%s",
                game_id,
                len(moves),
            )
        except Exception as exc:
            logger.exception(
                "Chess game analysis failed game_id=%s error_type=%s",
                game_id,
                type(exc).__name__,
            )
            try:
                self.database.update_game(game_id, analysis_status="failed")
                logger.info("Chess game analysis marked failed game_id=%s", game_id)
            except Exception:
                logger.exception(
                    "Could not mark failed chess analysis game game_id=%s",
                    game_id,
                )
