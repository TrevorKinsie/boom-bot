import logging
import os
import asyncio
from dotenv import load_dotenv
# Add CallbackQueryHandler, MessageHandler, and filters imports
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import logging.handlers # Import handlers

# Import setup functions and handlers
from boombot.utils.nltk_utils import setup_nltk
from boombot.core.data_manager import load_answers
from boombot.handlers.base_handlers import (
    boom_command,
    booms_command,
    handle_photo_caption,
)
# Import beast handlers
from boombot.handlers.beast_handlers import whowouldwin_command
# Import deposit handlers
from boombot.handlers.deposit_handlers import frigged_deposit_command
from boombot.core.config import TELEGRAM_TOKEN # Corrected import name
from boombot.casino.di.casino_application_context import build_casino_container
from boombot.casino.infrastructure.telegram.casino_telegram_facade import (
    CasinoTelegramFacade,
)
from boombot.games.chess.analysis_service import AnalysisService
from boombot.games.chess.database import ChessDatabase
from boombot.games.chess.engine import StockfishEngine
from boombot.games.chess.game_service import GameService
from boombot.handlers.chess_handlers import (
    callback_query_handler as chess_callback_query_handler,
    help_command as chess_help_command,
    move_command as chess_move_command,
    new_game_command as chess_new_game_command,
    reply_move_handler as chess_reply_move_handler,
    start_command as chess_start_command,
)
from boombot.core.config import CHESS_ANALYSIS_INTERVAL

load_dotenv()  # Load environment variables from .env file

# --- Logging Setup ---
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger() # Get root logger
logger.setLevel(logging.INFO) # Set root logger level

# Remove existing handlers from the root logger to prevent duplicates
if logger.hasHandlers():
    logger.handlers.clear()

# Console Handler (INFO level)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler("logs/error.log")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.ERROR)
logger.addHandler(file_handler)

# --- Application Setup ---
def create_application(token: str) -> Application:
    """Builds and configures the Telegram bot application."""
    # Perform setup when creating the application
    setup_nltk()
    load_answers()

    chess_database = ChessDatabase()
    chess_engine = StockfishEngine()
    chess_game_service = GameService(chess_database, chess_engine)
    chess_analysis_service = AnalysisService(chess_database, chess_engine)

    application = (
        Application.builder()
        .token(token)
        .post_init(_start_chess_analysis)
        .post_shutdown(_stop_chess_analysis)
        .build()
    )
    application.bot_data["chess_database"] = chess_database
    application.bot_data["chess_engine"] = chess_engine
    application.bot_data["chess_game_service"] = chess_game_service
    application.bot_data["chess_analysis_service"] = chess_analysis_service

    # --- Enterprise Casino Microkernel wiring ---
    casino_container = build_casino_container()
    casino_facade = CasinoTelegramFacade(casino_container)
    application.bot_data["casino_container"] = casino_container

    # Register handlers from the handlers module
    application.add_handler(CommandHandler("boom", boom_command))
    application.add_handler(CommandHandler("howmanybooms", booms_command))
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_caption))


    # --- Beast Wars Handlers ---
    application.add_handler(CommandHandler("whowouldwin", whowouldwin_command))

    # --- Deposit Handlers ---
    application.add_handler(CommandHandler("friggedthedeposit", frigged_deposit_command))

    # --- Enterprise Casino Command Handlers ---
    application.add_handler(CommandHandler("wallet", casino_facade.wallet_command))
    application.add_handler(CommandHandler("leaderboard", casino_facade.leaderboard_command))
    application.add_handler(CommandHandler("resetwallet", casino_facade.reset_wallet_command))
    application.add_handler(CommandHandler("roulette", casino_facade.roulette_command))
    application.add_handler(CommandHandler("roulettespin", casino_facade.roulette_spin_command))
    application.add_handler(CommandHandler("craps", casino_facade.craps_command))
    application.add_handler(CommandHandler("crapsroll", casino_facade.craps_roll_command))
    application.add_handler(CommandHandler("zeus", casino_facade.zeus_command))

    # --- Chess Challenge Handlers ---
    application.add_handler(CommandHandler("start", chess_start_command))
    application.add_handler(CommandHandler("help", chess_help_command))
    application.add_handler(CommandHandler("newgame", chess_new_game_command))
    application.add_handler(CommandHandler("move", chess_move_command))
    application.add_handler(
        CallbackQueryHandler(
            chess_callback_query_handler,
            pattern=r"^(difficulty_|newgame_menu$|help$|game_options$|back_to_game$|back_to_options$|resign_check$|resign_confirm$|draw_check$|draw_confirm$)",
        )
    )
    application.add_handler(
        MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, chess_reply_move_handler)
    )

    return application


async def _chess_analysis_loop(application: Application) -> None:
    """Run the original five-second pending-game analysis queue."""
    service = application.bot_data["chess_analysis_service"]
    while True:
        await service.process_pending_games()
        await asyncio.sleep(CHESS_ANALYSIS_INTERVAL)


async def _start_chess_analysis(application: Application) -> None:
    application.bot_data["chess_analysis_task"] = application.create_task(
        _chess_analysis_loop(application),
        name="chess-analysis-queue",
    )


async def _stop_chess_analysis(application: Application) -> None:
    task = application.bot_data.get("chess_analysis_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    application.bot_data["chess_engine"].quit()
    application.bot_data["chess_database"].close()
    casino_container = application.bot_data.get("casino_container")
    if casino_container is not None:
        casino_container.shutdown()

# --- Main Bot Function ---
def main() -> None:
    """Start the bot."""
    if not TELEGRAM_TOKEN: 
        logger.error("TELEGRAM_TOKEN not set in config.py or environment.")
        return

    application = create_application(TELEGRAM_TOKEN)

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
