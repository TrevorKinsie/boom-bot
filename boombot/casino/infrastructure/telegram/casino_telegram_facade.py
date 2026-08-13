"""
Casino Telegram Facade.

The presentation layer of the casino platform. This facade is the thin
controller that binds Telegram commands and callbacks to the CQRS command and
query buses. It holds no business logic: it parses user input, constructs the
appropriate command or query, dispatches it, and renders the resulting text.

Exceptions raised by the domain are caught and translated into friendly
user-facing messages.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from boombot.casino.application.bus.command_bus import CommandBus
from boombot.casino.application.bus.query_bus import QueryBus
from boombot.casino.di.dependency_container import DependencyContainer
from boombot.casino.reporting.application.leaderboard_query import GetLeaderboardQuery
from boombot.casino.reporting.domain.leaderboard import LeaderboardSnapshot
from boombot.casino.reporting.infrastructure.leaderboard_projection import (
    LeaderboardProjection,
)
from boombot.casino.shared.exceptions import CasinoException
from boombot.casino.wagering.application.command.wallet_commands import (
    PlaceCrapsBetCommand,
    PlaceRouletteBetCommand,
    ResetWalletCommand,
    RollCrapsCommand,
    SpinRouletteCommand,
    SpinZeusCommand,
)
from boombot.casino.wagering.application.query.wallet_queries import (
    GetWalletBalanceQuery,
    GetWalletStatsQuery,
)


class CasinoTelegramFacade:
    """Binds Telegram interactions to the casino command and query buses."""

    def __init__(self, container: DependencyContainer) -> None:
        self._command_bus: CommandBus = container.resolve(CommandBus)
        self._query_bus: QueryBus = container.resolve(QueryBus)
        self._projection: LeaderboardProjection = container.resolve(LeaderboardProjection)

    # --- Identity helpers ---
    @staticmethod
    def _user_id(update: Update) -> str:
        return str(update.effective_user.id)

    @staticmethod
    def _tenant_id(update: Update) -> str:
        return str(update.effective_chat.id)

    def _register_identity(self, update: Update) -> None:
        self._projection.register_name(
            self._user_id(update), update.effective_user.full_name
        )

    # --- Commands ---
    async def wallet_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        result = self._query_bus.dispatch(GetWalletBalanceQuery(self._user_id(update)))
        stats = self._query_bus.dispatch(
            GetWalletStatsQuery(self._user_id(update))
        ).get_payload()
        text = (
            "Wallet\n"
            f"Balance: {result.get_balance().formatted()}\n"
            f"Free spins: {result.get_free_spins()}\n"
            f"Total won: {stats['total_won'].formatted()}\n"
            f"Total wagered: {stats['total_wagered'].formatted()}"
        )
        await update.message.reply_text(text)

    async def leaderboard_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        result = self._query_bus.dispatch(GetLeaderboardQuery(10))
        snapshot: LeaderboardSnapshot = result.get_leaderboard()
        if snapshot.get_size() == 0:
            await update.message.reply_text("No players have any coins yet.")
            return
        medals = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        lines = ["Leaderboard"]
        for index, standing in enumerate(snapshot.get_rankings(), start=1):
            medal = medals[index - 1]
            lines.append(
                f"{medal}. {standing.get_display_name()} - "
                f"{standing.get_balance().formatted()}"
            )
        await update.message.reply_text("\n".join(lines))

    async def reset_wallet_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        reply = self._dispatch(ResetWalletCommand(self._user_id(update)))
        await update.message.reply_text(reply)

    async def roulette_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /roulette <type> [number] <amount>\n"
                "e.g. /roulette red 10, /roulette straight 7 10"
            )
            return
        bet_type = args[0].lower()
        if bet_type == "straight":
            if len(args) != 3:
                await update.message.reply_text(
                    "Usage: /roulette straight <number> <amount>"
                )
                return
            bet_value, amount = args[1], args[2]
        else:
            bet_value, amount = "", args[1]
        reply = self._dispatch(
            PlaceRouletteBetCommand(
                self._user_id(update),
                self._tenant_id(update),
                bet_type,
                bet_value,
                amount,
            )
        )
        await update.message.reply_text(reply)

    async def roulette_spin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        reply = self._dispatch(
            SpinRouletteCommand(self._user_id(update), self._tenant_id(update))
        )
        await update.message.reply_text(reply)

    async def craps_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /craps <type> <amount>\n"
                "e.g. /craps pass_line 10, /craps any_seven 5"
            )
            return
        reply = self._dispatch(
            PlaceCrapsBetCommand(
                self._user_id(update),
                self._tenant_id(update),
                args[0].lower(),
                args[1],
            )
        )
        await update.message.reply_text(reply)

    async def craps_roll_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        reply = self._dispatch(
            RollCrapsCommand(self._user_id(update), self._tenant_id(update))
        )
        await update.message.reply_text(reply)

    async def zeus_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self._register_identity(update)
        reply = self._dispatch(SpinZeusCommand(self._user_id(update)))
        await update.message.reply_text(reply, parse_mode="MarkdownV2")

    # --- Dispatch helper ---
    def _dispatch(self, command: object) -> str:
        try:
            result = self._command_bus.dispatch(command)
            return result.get_text()
        except CasinoException as exc:
            return exc.get_message()