"""Pillow board renderer matching the original Chess Challenge image UX."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import logging
from pathlib import Path

import chess
from PIL import Image, ImageDraw, ImageFont


ASSET_DIR = Path(__file__).resolve().parent / "assets"
logger = logging.getLogger(__name__)


class ImageService:
    board_size = 720
    square_size = 90
    margin = 28
    total_size = board_size + margin * 2
    light_color = "#f0d9b5"
    dark_color = "#b58863"
    highlight_color = (155, 199, 0, 105)
    cpu_highlight_color = (20, 85, 30, 128)
    margin_color = "#2c2c2c"
    label_color = "#e0e0e0"

    @property
    @lru_cache(maxsize=1)
    def font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = ASSET_DIR / "fonts" / "Roboto-Bold.ttf"
        if font_path.exists():
            return ImageFont.truetype(str(font_path), 18)
        logger.error("Chess board font asset is missing path=%s; using Pillow default", font_path)
        return ImageFont.load_default()

    @staticmethod
    @lru_cache(maxsize=12)
    def _piece_image(color: str, piece_type: str) -> Image.Image | None:
        names = {"p": "Pawn", "n": "Knight", "b": "Bishop", "r": "Rook", "q": "Queen", "k": "King"}
        colors = {"w": "White", "b": "Black"}
        path = ASSET_DIR / "merida" / f"{colors[color]}{names[piece_type]}.png"
        if not path.exists():
            logger.error(
                "Chess piece asset is missing path=%s color=%s piece_type=%s",
                path,
                color,
                piece_type,
            )
            return None
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            logger.exception(
                "Chess piece asset could not be loaded path=%s color=%s piece_type=%s",
                path,
                color,
                piece_type,
            )
            raise

    def generate_board_image(
        self,
        fen: str,
        flipped: bool = False,
        last_move: tuple[str, str] | None = None,
        cpu_destination: str | None = None,
    ) -> bytes:
        logger.debug(
            "Chess board image rendering started fen=%r flipped=%s last_move=%r "
            "cpu_destination=%r",
            fen,
            flipped,
            last_move,
            cpu_destination,
        )
        board = chess.Board(fen)
        image = Image.new("RGBA", (self.total_size, self.total_size), self.margin_color)
        draw = ImageDraw.Draw(image)

        for row in range(8):
            for col in range(8):
                x = self.margin + col * self.square_size
                y = self.margin + row * self.square_size
                draw.rectangle(
                    (x, y, x + self.square_size, y + self.square_size),
                    fill=self.light_color if (row + col) % 2 == 0 else self.dark_color,
                )
                square = self._square_name(row, col, flipped)
                if last_move and square in last_move:
                    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
                    ImageDraw.Draw(overlay).rectangle(
                        (x, y, x + self.square_size, y + self.square_size),
                        fill=self.highlight_color,
                    )
                    image = Image.alpha_composite(image, overlay)
                    draw = ImageDraw.Draw(image)
                if cpu_destination == square:
                    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
                    ImageDraw.Draw(overlay).rectangle(
                        (x, y, x + self.square_size, y + self.square_size),
                        fill=self.cpu_highlight_color,
                    )
                    image = Image.alpha_composite(image, overlay)
                    draw = ImageDraw.Draw(image)

        files = list("hgfedcba") if flipped else list("abcdefgh")
        ranks = list("12345678") if flipped else list("87654321")
        for col, label in enumerate(files):
            x = self.margin + col * self.square_size + self.square_size // 2
            draw.text((x, self.total_size - self.margin // 2), label, fill=self.label_color, font=self.font, anchor="mm")
        for row, label in enumerate(ranks):
            y = self.margin + row * self.square_size + self.square_size // 2
            draw.text((self.margin // 2, y), label, fill=self.label_color, font=self.font, anchor="mm")

        for row in range(8):
            for col in range(8):
                file_index = 7 - col if flipped else col
                rank_index = row if flipped else 7 - row
                piece = board.piece_at(chess.square(file_index, rank_index))
                if not piece:
                    continue
                piece_image = self._piece_image(
                    "w" if piece.color == chess.WHITE else "b",
                    chess.piece_symbol(piece.piece_type),
                )
                if piece_image is None:
                    continue
                x = self.margin + col * self.square_size
                y = self.margin + row * self.square_size
                image.alpha_composite(piece_image.resize((self.square_size, self.square_size)), (x, y))

        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        rendered = output.getvalue()
        logger.info(
            "Chess board image rendering completed bytes=%s flipped=%s",
            len(rendered),
            flipped,
        )
        return rendered

    @staticmethod
    def _square_name(row: int, col: int, flipped: bool) -> str:
        file_index = 7 - col if flipped else col
        rank_index = row if flipped else 7 - row
        return chess.square_name(chess.square(file_index, rank_index))


image_service = ImageService()
