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
        try:
            games = self.database.find_pending_analysis(1)
            if games:
                await self.analyze_game(games[0]["id"])
        except Exception:
            logger.exception("Chess analysis processing error")

    async def analyze_game(self, game_id: str) -> None:
        logger.info("Analyzing chess game %s", game_id)
        self.database.update_game(game_id, analysis_status="processing")
        try:
            moves = self.database.find_moves(game_id)
            if not moves:
                raise ValueError("No moves found")

            board = chess.Board()
            for record in moves:
                if record["user_id"]:
                    current_fen = board.fen()
                    best_move_uci = await asyncio.to_thread(
                        self.engine.get_best_move,
                        current_fen,
                        STOCKFISH_ANALYSIS_DEPTH,
                        20,
                    )
                    user_move = board.parse_san(record["move_san"])
                    best_move = board.parse_uci(best_move_uci)
                    score = 100 if user_move == best_move else 50
                    self.database.update_move_analysis(
                        record["id"],
                        best_move_suggestion=best_move_uci,
                        evaluation_score=score,
                    )
                try:
                    board.push_san(record["move_san"])
                except (chess.IllegalMoveError, chess.InvalidMoveError) as exc:
                    logger.warning("Invalid move in chess replay %s: %s", record["move_san"], exc)

            self.database.update_game(game_id, analysis_status="completed")
            logger.info("Chess analysis for %s completed", game_id)
        except Exception:
            logger.exception("Failed to analyze chess game %s", game_id)
            self.database.update_game(game_id, analysis_status="failed")
