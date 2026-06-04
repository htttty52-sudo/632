import asyncio
import json
import time
import logging
from dataclasses import dataclass, field

from app.config import settings
from app.arbitrage.price_table import PriceTable
from app.db.database import async_session
from app.models.strategy import Strategy, StrategyLog
from app.ws.broadcast import connection_manager

from sqlalchemy import select, update

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}


@dataclass
class StrategyState:
    id: int
    user_id: int
    name: str
    conditions: list[dict]
    simulated_balance: float
    initial_balance: float
    active: bool
    cooldown_until: float = 0.0


@dataclass
class TradeSignal:
    strategy_id: int
    user_id: int
    strategy_name: str
    symbol: str
    exchange_a: str
    exchange_b: str
    direction: str
    spread_pct: float
    best_spread: float
    snapshot: dict


class UserFundLock:
    """Per-user atomic fund lock. Ensures only one trade settles per user at a time."""

    def __init__(self):
        self._locks: dict[int, asyncio.Lock] = {}

    def get(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]


class StrategyEngine:
    """
    Decoupled scanner + worker architecture.

    Scanner: 1s loop, evaluates conditions, puts TradeSignal into queue. Never does I/O.
    Worker: consumes queue, acquires per-user fund lock, checks balance sufficiency,
            deducts atomically or rejects, persists log.
    """

    SCAN_INTERVAL = 1.0
    TRADE_COOLDOWN = 5.0
    SIMULATED_TRADE_FRACTION = 0.1
    MIN_TRADE_AMOUNT = 1.0  # reject if available balance < this

    def __init__(self, price_table: PriceTable):
        self._price_table = price_table
        self._strategies: dict[int, StrategyState] = {}
        self._user_funds = UserFundLock()
        self._signal_queue: asyncio.Queue[TradeSignal] = asyncio.Queue(maxsize=2000)
        self._scanner_task: asyncio.Task | None = None
        self._worker_tasks: list[asyncio.Task] = []
        self._running = False
        self._num_workers = 3

    async def start(self):
        self._running = True
        await self.reload_strategies()
        self._scanner_task = asyncio.create_task(self._scan_loop())
        self._worker_tasks = [
            asyncio.create_task(self._worker_loop(i)) for i in range(self._num_workers)
        ]
        logger.info(f"StrategyEngine started (1 scanner + {self._num_workers} workers)")

    async def stop(self):
        self._running = False
        tasks = [t for t in [self._scanner_task] + self._worker_tasks if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("StrategyEngine stopped")

    async def reload_strategies(self):
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Strategy).where(Strategy.active == True)
                )
                strategies = result.scalars().all()
                new_states: dict[int, StrategyState] = {}
                for s in strategies:
                    existing = self._strategies.get(s.id)
                    conditions = json.loads(s.conditions) if isinstance(s.conditions, str) else s.conditions
                    new_states[s.id] = StrategyState(
                        id=s.id,
                        user_id=s.user_id,
                        name=s.name,
                        conditions=conditions,
                        simulated_balance=s.simulated_balance,
                        initial_balance=s.initial_balance,
                        active=s.active,
                        cooldown_until=existing.cooldown_until if existing else 0.0,
                    )
                self._strategies = new_states
                logger.info(f"Loaded {len(new_states)} active strategies")
        except Exception as e:
            logger.error(f"Failed to reload strategies: {e}")

    # ─── Scanner: only evaluates and enqueues ───────────────────────────────

    async def _scan_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.SCAN_INTERVAL)
                now = time.time()

                for symbol in settings.symbols:
                    valid_prices = await self._price_table.get_valid_prices(symbol)
                    if len(valid_prices) < 2:
                        continue

                    exchanges = sorted(valid_prices.keys())
                    for i, ex_a in enumerate(exchanges):
                        for j, ex_b in enumerate(exchanges):
                            if i >= j:
                                continue
                            pa, pb = valid_prices[ex_a], valid_prices[ex_b]
                            spread_ab = float(pb.best_bid - pa.best_ask)
                            spread_ba = float(pa.best_bid - pb.best_ask)
                            best_spread = max(spread_ab, spread_ba)
                            mid_price = float((pa.best_ask + pb.best_ask) / 2)
                            spread_pct = (best_spread / mid_price) * 100 if mid_price else 0.0
                            direction = "a_to_b" if spread_ab >= spread_ba else "b_to_a"

                            market_ctx = {
                                "spread_pct": spread_pct,
                                "best_spread": best_spread,
                                "volume": 0.0,
                            }

                            for strat in self._strategies.values():
                                if not strat.active:
                                    continue
                                if now < strat.cooldown_until:
                                    continue
                                if self._evaluate_conditions(strat.conditions, market_ctx):
                                    strat.cooldown_until = now + self.TRADE_COOLDOWN
                                    signal = TradeSignal(
                                        strategy_id=strat.id,
                                        user_id=strat.user_id,
                                        strategy_name=strat.name,
                                        symbol=symbol,
                                        exchange_a=ex_a,
                                        exchange_b=ex_b,
                                        direction=direction,
                                        spread_pct=spread_pct,
                                        best_spread=best_spread,
                                        snapshot=market_ctx.copy(),
                                    )
                                    try:
                                        self._signal_queue.put_nowait(signal)
                                    except asyncio.QueueFull:
                                        logger.warning("Signal queue full, dropping signal")

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Strategy scan error: {e}")

    def _evaluate_conditions(self, conditions: list[dict], ctx: dict) -> bool:
        for cond in conditions:
            field = cond.get("field", "")
            operator = cond.get("operator", "")
            threshold = cond.get("value", 0)
            if field not in ctx:
                return False
            op_fn = OPERATOR_MAP.get(operator)
            if not op_fn:
                return False
            if not op_fn(ctx[field], threshold):
                return False
        return True

    # ─── Worker: lock → check → deduct-or-reject → persist ─────────────────

    async def _worker_loop(self, worker_id: int):
        while self._running:
            try:
                signal = await asyncio.wait_for(self._signal_queue.get(), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not self._running:
                    return
                continue

            try:
                await self._execute_trade(signal)
            except Exception as e:
                logger.error(f"Worker-{worker_id} execution error: {e}")

    async def _execute_trade(self, signal: TradeSignal):
        user_lock = self._user_funds.get(signal.user_id)

        async with user_lock:
            strat = self._strategies.get(signal.strategy_id)
            if not strat:
                return

            trade_amount = strat.simulated_balance * self.SIMULATED_TRADE_FRACTION

            if trade_amount < self.MIN_TRADE_AMOUNT:
                logger.info(
                    f"Strategy '{signal.strategy_name}' rejected: "
                    f"insufficient balance ({strat.simulated_balance:.2f})"
                )
                return

            # Atomic deduct: lock held, compute pnl, update balance
            simulated_pnl = trade_amount * (signal.spread_pct / 100.0)
            new_balance = strat.simulated_balance - trade_amount + trade_amount + simulated_pnl
            strat.simulated_balance = new_balance
            balance_after = new_balance

        # Persist outside the lock to minimize hold time, but use DB-level atomic update
        try:
            async with async_session() as session:
                await session.execute(
                    update(Strategy)
                    .where(Strategy.id == signal.strategy_id)
                    .values(simulated_balance=balance_after)
                )
                log_entry = StrategyLog(
                    strategy_id=signal.strategy_id,
                    user_id=signal.user_id,
                    symbol=signal.symbol,
                    exchange_a=signal.exchange_a,
                    exchange_b=signal.exchange_b,
                    direction=signal.direction,
                    spread_pct=signal.spread_pct,
                    simulated_quantity=trade_amount,
                    simulated_pnl=simulated_pnl,
                    balance_after=balance_after,
                    condition_snapshot=json.dumps(signal.snapshot),
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist strategy trade: {e}")

        event = {
            "type": "strategy_trigger",
            "data": {
                "strategy_id": signal.strategy_id,
                "strategy_name": signal.strategy_name,
                "user_id": signal.user_id,
                "symbol": signal.symbol,
                "exchange_a": signal.exchange_a,
                "exchange_b": signal.exchange_b,
                "direction": signal.direction,
                "spread_pct": round(signal.spread_pct, 4),
                "simulated_pnl": round(simulated_pnl, 4),
                "balance_after": round(balance_after, 2),
            },
        }
        await connection_manager.broadcast_raw(event)
        logger.info(
            f"Strategy '{signal.strategy_name}' triggered: {signal.symbol} "
            f"{signal.exchange_a}->{signal.exchange_b} pnl={simulated_pnl:.4f}"
        )


strategy_engine = StrategyEngine.__new__(StrategyEngine)
