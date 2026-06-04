import asyncio
import json
import time
import logging
from dataclasses import dataclass
from decimal import Decimal

from app.config import settings
from app.arbitrage.price_table import PriceTable
from app.db.database import async_session
from app.models.strategy import Strategy, StrategyLog
from app.ws.broadcast import connection_manager

from sqlalchemy import select

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
    cooldown_until: float = 0.0  # prevent rapid re-triggers


@dataclass
class TradeSignal:
    strategy: StrategyState
    symbol: str
    exchange_a: str
    exchange_b: str
    direction: str
    spread_pct: float
    best_spread: float
    snapshot: dict


class StrategyEngine:
    """
    Async non-blocking strategy engine.

    Design:
    - Scanner loop runs every 1s, reads spread data from PriceTable (same as SpreadEngine).
    - Evaluation is decoupled via asyncio.Queue so it never blocks market data ingestion.
    - Simulated fund locking uses an asyncio.Lock to serialize fund allocation
      when multiple strategies trigger simultaneously on the same tick.
    """

    SCAN_INTERVAL = 1.0
    TRADE_COOLDOWN = 5.0  # seconds between trades for same strategy
    SIMULATED_TRADE_FRACTION = 0.1  # use 10% of balance per trade

    def __init__(self, price_table: PriceTable):
        self._price_table = price_table
        self._strategies: dict[int, StrategyState] = {}
        self._fund_lock = asyncio.Lock()  # global fund allocation lock
        self._signal_queue: asyncio.Queue[TradeSignal] = asyncio.Queue(maxsize=1000)
        self._scanner_task: asyncio.Task | None = None
        self._executor_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        self._running = True
        await self.reload_strategies()
        self._scanner_task = asyncio.create_task(self._scan_loop())
        self._executor_task = asyncio.create_task(self._execute_loop())
        logger.info("StrategyEngine started (scanner + executor)")

    async def stop(self):
        self._running = False
        for task in (self._scanner_task, self._executor_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("StrategyEngine stopped")

    async def reload_strategies(self):
        """Reload active strategies from DB into memory."""
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

    async def _scan_loop(self):
        """Every 1s, evaluate all strategies against current spreads. Non-blocking."""
        while self._running:
            try:
                await asyncio.sleep(self.SCAN_INTERVAL)
                scan_start = time.monotonic()

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
                                "volume": 0.0,  # placeholder for volume data
                            }

                            now = time.time()
                            for strat in self._strategies.values():
                                if not strat.active:
                                    continue
                                if now < strat.cooldown_until:
                                    continue
                                if self._evaluate_conditions(strat.conditions, market_ctx):
                                    signal = TradeSignal(
                                        strategy=strat,
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

                elapsed = time.monotonic() - scan_start
                if elapsed > 0.5:
                    logger.warning(f"Strategy scan took {elapsed:.3f}s (> 500ms)")

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Strategy scan error: {e}")

    def _evaluate_conditions(self, conditions: list[dict], ctx: dict) -> bool:
        """Safe DSL evaluator - no exec/eval. All conditions must be true (AND logic)."""
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

    async def _execute_loop(self):
        """Consume signals from the queue and execute simulated trades with fund locking."""
        while self._running:
            try:
                signal = await asyncio.wait_for(
                    self._signal_queue.get(), timeout=2.0
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not self._running:
                    return
                continue

            try:
                await self._execute_trade(signal)
            except Exception as e:
                logger.error(f"Strategy execution error: {e}")

    async def _execute_trade(self, signal: TradeSignal):
        """Simulate a trade with fund locking to prevent multi-strategy over-allocation."""
        strat = signal.strategy

        async with self._fund_lock:
            if strat.simulated_balance <= 0:
                return

            trade_amount = strat.simulated_balance * self.SIMULATED_TRADE_FRACTION
            simulated_pnl = trade_amount * (signal.spread_pct / 100.0)
            strat.simulated_balance += simulated_pnl
            strat.cooldown_until = time.time() + self.TRADE_COOLDOWN
            balance_after = strat.simulated_balance

        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Strategy).where(Strategy.id == strat.id)
                )
                db_strategy = result.scalar_one_or_none()
                if db_strategy:
                    db_strategy.simulated_balance = balance_after

                log_entry = StrategyLog(
                    strategy_id=strat.id,
                    user_id=strat.user_id,
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
                "strategy_id": strat.id,
                "strategy_name": strat.name,
                "user_id": strat.user_id,
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
            f"Strategy '{strat.name}' triggered: {signal.symbol} "
            f"{signal.exchange_a}->{signal.exchange_b} pnl={simulated_pnl:.4f}"
        )


strategy_engine = StrategyEngine.__new__(StrategyEngine)
