import chess
import pytest

from boombot.games.chess.analysis_service import AnalysisService
from boombot.games.chess.database import ChessDatabase
from boombot.games.chess.game_service import GameService
from boombot.games.chess.image_service import image_service


class FakeEngine:
    def get_best_move(self, fen, depth=None, skill_level=20):
        board = chess.Board(fen)
        return "e2e4" if board.turn == chess.WHITE else "e7e5"

    def get_evaluation(self, fen, depth=None, skill_level=20):
        return {"score": 0, "best_move": self.get_best_move(fen, depth, skill_level)}


@pytest.mark.asyncio
async def test_full_game_flow_persists_moves_and_score(tmp_path, monkeypatch):
    database = ChessDatabase(tmp_path / "chess.sqlite3")
    service = GameService(database, FakeEngine())
    monkeypatch.setattr("boombot.games.chess.game_service.random.random", lambda: 0.1)

    game = await service.create_game(123, 456, None, difficulty=10, first_name="Kevin")
    assert game["communityColor"] == "w"
    assert game["initialCpuMove"] == ""
    assert database.find_active_game(123)["difficulty"] == 10

    result = await service.make_move(123, 456, None, "e4", first_name="Kevin")
    assert result["success"] is True
    assert result["cpuMove"] == "e5"
    assert result["userMoveFrom"] == "e2"
    assert result["userMoveTo"] == "e4"
    assert result["scoreDelta"] == 0
    assert len(database.find_moves(game["id"])) == 2
    assert database.find_active_game(123)["fen"] == result["fen"]

    resign = await service.resign_game(123)
    assert resign["success"] is True
    assert database.find_active_game(123) is None

    database.close()


@pytest.mark.asyncio
async def test_black_community_gets_initial_stockfish_move(tmp_path, monkeypatch):
    database = ChessDatabase(tmp_path / "chess.sqlite3")
    service = GameService(database, FakeEngine())
    monkeypatch.setattr("boombot.games.chess.game_service.random.random", lambda: 0.9)

    game = await service.create_game(123, 456, "player", difficulty=5)
    assert game["communityColor"] == "b"
    assert game["initialCpuMove"] == "e4"
    assert len(database.find_moves(game["id"])) == 1
    assert database.find_moves(game["id"])[0]["user_id"] is None
    database.close()


@pytest.mark.asyncio
async def test_completed_game_is_analyzed_and_user_move_graded(tmp_path, monkeypatch):
    database = ChessDatabase(tmp_path / "chess.sqlite3")
    service = GameService(database, FakeEngine())
    monkeypatch.setattr("boombot.games.chess.game_service.random.random", lambda: 0.1)
    game = await service.create_game(123, 456, "player")
    await service.make_move(123, 456, "player", "e4")
    await service.resign_game(123)

    analysis = AnalysisService(database, FakeEngine())
    await analysis.process_pending_games()
    user_move = next(move for move in database.find_moves(game["id"]) if move["user_id"])
    assert user_move["best_move_suggestion"] == "e2e4"
    assert user_move["evaluation_score"] == 100

    database.close()


def test_board_renderer_produces_png_with_original_dimensions():
    png = image_service.generate_board_image(chess.Board().fen())
    assert png.startswith(b"\x89PNG")
    from PIL import Image
    from io import BytesIO

    with Image.open(BytesIO(png)) as image:
        assert image.size == (776, 776)
