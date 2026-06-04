import asyncio
import time
import logging
from collections import deque
from decimal import Decimal

from app.config import settings
from app.arbitrage.price_table import PriceTable
from app.models.market import SpreadCell, SpreadMatrix, SpreadAlertEvent
from app.ws.broadcast import connection_manager
from app.db.database import async_session
from app.models.alert import SpreadAlert

logger = logging.getLogger(__name__)


class SpreadEngine:
    """Computes pairwise spread matrix. Alerts: max N per 5-min window per pair type."""

    def __init__(self, price_table: PriceTable):
        self._price_table = price_table
        self._interval = settings.spread_broadcast_interval_ms / 1000.0
        self._threshold_pct = Decimal(str(settings.spread_alert_threshold_pct))
        self._cooldown_seconds = settings.spread_alert_cooldown_seconds
        self._max_per_window = settings.spread_alert_max_per_window
        self._task: asyncio.Task | None = None
        self._running = False
        # key -> deque of timestamps within the cooldown window
        self._alert_timestamps: dict[str, deque[float]] = {}

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SpreadEngine started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SpreadEngine stopped")

    async def _loop(self):
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                for symbol in settings.symbols:
                    matrix = await self._compute_matrix(symbol)
                    if matrix:
                        await connection_manager.broadcast(matrix)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"SpreadEngine error: {e}")

    async def _compute_matrix(self, symbol: str = "BTC/USDT") -> SpreadMatrix | None:
        valid = await self._price_table.get_valid_prices(symbol)
        stale = await self._price_table.get_stale_exchanges(symbol)
        if len(valid) < 2:
            return SpreadMatrix(
                symbol=symbol,
                exchanges=sorted(valid.keys()),
                cells=[],
                stale_exchanges=stale,
                timestamp=int(time.time() * 1000),
            )

        exchanges = sorted(valid.keys())
        cells: list[SpreadCell] = []

        for i, ex_a in enumerate(exchanges):
            for j, ex_b in enumerate(exchanges):
                if i >= j:
                    continue
                pa, pb = valid[ex_a], valid[ex_b]
                spread_ab = pb.best_bid - pa.best_ask
                spread_ba = pa.best_bid - pb.best_ask
                best_spread = max(spread_ab, spread_ba)
                mid_price = (pa.best_ask + pb.best_ask) / 2
                spread_pct = (best_spread / mid_price) * 100 if mid_price else Decimal(0)

                cells.append(SpreadCell(
                    exchange_a=ex_a,
                    exchange_b=ex_b,
                    spread_ab=spread_ab,
                    spread_ba=spread_ba,
                    best_spread=best_spread,
                    spread_pct=spread_pct,
                ))

                if spread_pct > self._threshold_pct:
                    direction = "a_to_b" if spread_ab > spread_ba else "b_to_a"
                    await self._trigger_alert(symbol, ex_a, ex_b, spread_pct, direction)

        return SpreadMatrix(
            symbol=symbol,
            exchanges=exchanges,
            cells=cells,
            stale_exchanges=stale,
            timestamp=int(time.time() * 1000),
        )

    def _can_alert(self, pair_key: str) -> bool:
        """Check if we can fire another alert within the 5-min window (max N)."""
        now = time.time()
        if pair_key not in self._alert_timestamps:
            self._alert_timestamps[pair_key] = deque()
        q = self._alert_timestamps[pair_key]
        # Purge expired entries
        while q and (now - q[0]) > self._cooldown_seconds:
            q.popleft()
        return len(q) < self._max_per_window

    async def _trigger_alert(self, symbol: str, exchange_a: str, exchange_b: str,
                             spread_pct: Decimal, direction: str):
        pair_key = f"{symbol}:{exchange_a}:{exchange_b}:{direction}"
        if not self._can_alert(pair_key):
            return

        now = time.time()
        self._alert_timestamps[pair_key].append(now)
        ts = int(now * 1000)

        alert_event = SpreadAlertEvent(
            symbol=symbol,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            spread_pct=spread_pct,
            direction=direction,
            timestamp=ts,
        )
        await connection_manager.broadcast(alert_event)
        logger.warning(
            f"SPREAD ALERT: {symbol} {exchange_a}/{exchange_b} spread={spread_pct:.4f}% "
            f"direction={direction} ({len(self._alert_timestamps[pair_key])}/{self._max_per_window} in window)"
        )

        try:
            async with async_session() as session:
                record = SpreadAlert(
                    symbol=symbol,
                    exchange_a=exchange_a,
                    exchange_b=exchange_b,
                    spread_pct=float(spread_pct),
                    threshold_pct=float(self._threshold_pct),
                    direction=direction,
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist alert: {e}")
