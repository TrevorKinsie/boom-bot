"""
Wagering Application Service.

The application service is the transactional use-case orchestrator of the
wagering context. It coordinates the wallet repository, the game session
store, and the event bus to execute gambling use cases: placing wagers,
spinning/rolling, settling, resetting, and reading wallet state.

The service is the single entry point for the wagering domain; command
handlers delegate to it. All monetary mutations flow through the wallet
aggregate and are persisted as events atomically with publication to the
event bus.
"""

from __future__ import annotations

import random
from typing import Any

from boombot.casino.application.event.event_bus import IEventBus
from boombot.casino.shared.exceptions import (
    BetExceedsBalanceException,
    InvalidBetException,
    NegativeBetAmountException,
)
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.domain.model.wallet import Wallet
from boombot.casino.wagering.infrastructure.persistence.game_session_store import (
    IGameSessionStore,
)
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)

# Domain specifications produced by the specification sub-system.
from boombot.casino.wagering.domain.specification.craps_specifications import (
    CrapsBetValidationStrategy,
    CrapsPayoutStrategy,
    CrapsPushStrategy,
    CrapsRollContext,
)
from boombot.casino.wagering.domain.specification.payout_strategy import (
    BetOutcomeKind,
    CrapsBetResolutionStrategy,
)
from boombot.casino.wagering.domain.specification.roulette_specifications import (
    RoulettePayoutStrategy,
    RouletteResult,
)
from boombot.casino.zeus.domain.reel import (
    GridWinEvaluator,
    LineEvaluationStrategy,
    PayoutCalculator,
    PayoutTable,
    RandomGridFactory,
)

COME_OUT_PHASE = 1
POINT_PHASE = 2

# Bet types supported by the unified wagering application service.
SUPPORTED_ROULETTE_BET_TYPES = frozenset(
    {
        "straight",
        "red",
        "black",
        "even",
        "odd",
        "low",
        "high",
        "first_dozen",
        "second_dozen",
        "third_dozen",
    }
)
_DOZEN_COVERED_NUMBERS = {
    "first_dozen": list(range(1, 13)),
    "second_dozen": list(range(13, 25)),
    "third_dozen": list(range(25, 37)),
}


class WageringApplicationService:
    """Transactional orchestrator for casino wagering use cases."""

    def __init__(
        self,
        wallet_repository: WalletRepository,
        event_bus: IEventBus,
        session_store: IGameSessionStore,
        starting_balance: Money | None = None,
        zeus_spin_cost: Money | None = None,
    ) -> None:
        self._wallet_repository = wallet_repository
        self._event_bus = event_bus
        self._session_store = session_store
        self._starting_balance = starting_balance or Money("100.00")
        self._zeus_spin_cost = zeus_spin_cost or Money("10.00")
        self._craps_validation_strategy = CrapsBetValidationStrategy()
        self._roulette_payout_strategy = RoulettePayoutStrategy()
        self._grid_factory = RandomGridFactory()
        self._line_evaluation_strategy = LineEvaluationStrategy()
        self._payout_calculator = PayoutCalculator(PayoutTable())

    # --- Wallet access ---
    def get_wallet(self, user_id: str) -> Wallet:
        wallet = self._wallet_repository.find(user_id)
        if wallet is None:
            wallet = self._wallet_repository.load_or_provision(user_id)
            self._flush(wallet)
        return wallet

    def get_balance(self, user_id: str) -> Money:
        return self.get_wallet(user_id).get_balance()

    def get_stats(self, user_id: str) -> dict[str, Any]:
        wallet = self.get_wallet(user_id)
        return {
            "balance": wallet.get_balance(),
            "total_wagered": wallet.get_total_wagered(),
            "total_won": wallet.get_total_won(),
            "biggest_win": wallet.get_biggest_win(),
            "free_spins": wallet.get_free_spins(),
            "games_played": wallet.get_games_played(),
        }

    def _flush(self, wallet: Wallet) -> None:
        staged = wallet.get_uncommitted_events()
        self._wallet_repository.save(wallet)
        for event in staged:
            self._event_bus.publish(event)

    def _parse_amount(self, amount_str: str) -> Money:
        try:
            amount = Money(amount_str)
        except Exception as exc:
            raise InvalidBetException(f"Invalid bet amount: {amount_str}") from exc
        if amount.is_zero():
            raise NegativeBetAmountException("Bet amount must be positive.")
        return amount

    def _require_balance(self, wallet: Wallet, amount: Money) -> None:
        if amount.is_greater_than(wallet.get_balance()):
            raise BetExceedsBalanceException(
                f"Insufficient balance {wallet.get_balance().formatted()} "
                f"for wager {amount.formatted()}."
            )
# --- Roulette ---
    def place_roulette_bet(
        self,
        user_id: str,
        tenant_id: str,
        bet_type: str,
        bet_value: str,
        amount_str: str,
    ) -> str:
        """Place a roulette wager on behalf of a user within a tenant."""
        if bet_type not in SUPPORTED_ROULETTE_BET_TYPES:
            raise InvalidBetException(f"Invalid bet type: {bet_type}")
        if bet_type == "straight" and bet_value in ("", None):
            raise InvalidBetException("A straight bet requires a number.")
        amount = self._parse_amount(amount_str)
        wallet = self.get_wallet(user_id)
        self._require_balance(wallet, amount)
        session = self._session_store.get_channel_session(tenant_id)
        bet_key = bet_type if not bet_value else f"straight__{bet_value}"
        user_bets = session["roulette_bets"].setdefault(user_id, {})
        user_bets[bet_key] = str(
            Money(user_bets.get(bet_key, "0")).add(amount).amount()
        )
        self._session_store.save_channel_session(tenant_id, session)
        wallet.debit(amount, "roulette")
        self._flush(wallet)
        return f"Placed {amount.formatted()} on {bet_key}."

    def spin_roulette(self, tenant_id: str) -> str:
        """Spin the wheel and resolve every outstanding roulette wager."""
        session = self._session_store.get_channel_session(tenant_id)
        bets = session.get("roulette_bets", {})
        if not bets:
            return "No bets placed for this roulette spin."
        result_number = random.choice([0, "00"] + list(range(1, 37)))
        result = RouletteResult(result_number)
        summary_lines = [f"The wheel landed on pocket {result_number}."]
        for user_id, user_bets in bets.items():
            wallet = self.get_wallet(user_id)
            for bet_key, amount_str in user_bets.items():
                amount = Money(amount_str)
                bet_type, resolved_bet_value = self._parse_roulette_bet(bet_key)
                winnings = self._roulette_payout_strategy.calculate_winnings(
                    bet_type, resolved_bet_value, amount, result
                )
                if winnings.is_positive():
                    wallet.credit(winnings, "roulette")
                    wallet.record_wager(amount, winnings, "roulette")
                    summary_lines.append(
                        f"Player {user_id} wins {winnings.formatted()}."
                    )
                else:
                    wallet.record_wager(amount, Money("0"), "roulette")
            self._flush(wallet)
        session["roulette_bets"] = {}
        self._session_store.save_channel_session(tenant_id, session)
        return "\n".join(summary_lines)

    @staticmethod
    def _parse_roulette_bet(bet_key: str) -> tuple[str, object]:
        """Split a stored roulette bet key into (bet_type, resolved value)."""
        if bet_key.startswith("straight__"):
            bet_type = "straight"
            raw_value = bet_key.split("__", maxsplit=1)[1]
            resolved_value: object = raw_value if raw_value == "00" else int(raw_value)
            return bet_type, resolved_value
        if bet_key in _DOZEN_COVERED_NUMBERS:
            return bet_key, _DOZEN_COVERED_NUMBERS[bet_key]
        return bet_key, None
# --- Craps ---
    def place_craps_bet(
        self, user_id: str, tenant_id: str, bet_type: str, amount_str: str
    ) -> str:
        """Place a craps wager on behalf of a user within a tenant."""
        self._craps_validation_strategy.validate(bet_type)
        amount = self._parse_amount(amount_str)
        wallet = self.get_wallet(user_id)
        self._require_balance(wallet, amount)
        session = self._session_store.get_channel_session(tenant_id)
        if session["craps_state"] == POINT_PHASE and bet_type in (
            "pass_line",
            "dont_pass",
        ):
            raise InvalidBetException(
                f"Cannot place {bet_type.replace('_', ' ')} when a point is established."
            )
        user_bets = session["craps_bets"].setdefault(user_id, {})
        user_bets[bet_type] = str(
            Money(user_bets.get(bet_type, "0")).add(amount).amount()
        )
        self._session_store.save_channel_session(tenant_id, session)
        wallet.debit(amount, "craps")
        self._flush(wallet)
        return f"Placed {amount.formatted()} on {bet_type}."

    def roll_craps(self, tenant_id: str) -> str:
        """Roll the dice and resolve every outstanding craps wager."""
        session = self._session_store.get_channel_session(tenant_id)
        bets = session.get("craps_bets", {})
        if not bets:
            return "No bets placed for this craps roll."
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        roll_sum = die1 + die2
        point = session.get("craps_point")
        context = CrapsRollContext(die1, die2, point)
        summary_lines = [f"Rolled {die1} + {die2} = {roll_sum}."]
        for user_id, user_bets in bets.items():
            wallet = self.get_wallet(user_id)
            for bet_type, amount_str in user_bets.items():
                amount = Money(amount_str)
                resolution = CrapsBetResolutionStrategy(bet_type, amount).resolve(context)
                kind = resolution.get_kind()
                if kind == BetOutcomeKind.WIN:
                    winnings = resolution.get_winnings()
                    wallet.credit(winnings, "craps")
                    wallet.record_wager(amount, winnings, "craps")
                    summary_lines.append(
                        f"Player {user_id} wins {winnings.formatted()} on {bet_type}."
                    )
                elif kind == BetOutcomeKind.PUSH:
                    wallet.credit(amount, "craps")
                    wallet.record_wager(amount, Money("0"), "craps")
                    summary_lines.append(f"Player {user_id} pushes on {bet_type}.")
                else:
                    wallet.record_wager(amount, Money("0"), "craps")
                    summary_lines.append(f"Player {user_id} loses {bet_type}.")
            self._flush(wallet)
        session["craps_bets"] = {}
        session["craps_state"], session["craps_point"] = self._advance_craps_phase(
            roll_sum, point
        )
        self._session_store.save_channel_session(tenant_id, session)
        return "\n".join(summary_lines)

    @staticmethod
    def _advance_craps_phase(roll_sum: int, point: object) -> tuple[int, object]:
        """Return the next (phase, point) for the craps table."""
        if point is None:
            if roll_sum in (4, 5, 6, 8, 9, 10):
                return POINT_PHASE, roll_sum
            return COME_OUT_PHASE, None
        if roll_sum in (point, 7):
            return COME_OUT_PHASE, None
# --- Zeus ---
    def spin_zeus(self, user_id: str) -> str:
        """Charge the user and spin the Zeus reel family."""
        wallet = self.get_wallet(user_id)
        wager = Money("0")
        if wallet.get_free_spins() > 0:
            wallet.redeem_free_spin()
        else:
            self._require_balance(wallet, self._zeus_spin_cost)
            wallet.debit(self._zeus_spin_cost, "zeus")
            wager = self._zeus_spin_cost
        grid = self._grid_factory.generate(5, 5)
        winnings = GridWinEvaluator(
            grid, self._line_evaluation_strategy
        ).evaluate()
        coins, free_spins = self._payout_calculator.calculate(winnings)
        wallet.record_wager(wager, coins, "zeus")
        if coins.is_positive():
            wallet.credit(coins, "zeus")
        if free_spins > 0:
            wallet.award_free_spins(free_spins)
        self._flush(wallet)
        return self._format_zeus_result(grid, winnings, coins, free_spins, wallet)

    @staticmethod
    def _format_zeus_result(
        grid: object, winnings: list, coins: Money, free_spins: int, wallet: Wallet
    ) -> str:
        """Format the zeus spin result for presentation."""
        rows = "\n".join(
            " | ".join(grid.get_all_rows()[i]) for i in range(grid.get_rows())
        )
        lines = [f"```\n{rows}\n```"]
        if coins.is_positive():
            lines.append(f"Won {coins.formatted()} coins and {free_spins} free spins.")
        else:
            lines.append("No winning lines this spin.")
        lines.append(
            f"Balance: {wallet.get_balance().formatted()} | "
            f"Free spins: {wallet.get_free_spins()}"
        )
        return "\n".join(lines)

    # --- Reset ---
    def reset_wallet(self, user_id: str) -> str:
        """Restore the wallet balance to the starting amount."""
        wallet = self.get_wallet(user_id)
        wallet.reset(self._starting_balance)
        self._flush(wallet)
        return f"Balance reset to {self._starting_balance.formatted()}."
        return POINT_PHASE, point