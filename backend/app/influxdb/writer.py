import asyncio
import logging
import time
from collections import deque

from influxdb_client import Point
from influxdb_client.client.write_api import ASYNCHRONOUS

from app.config import settings
from app.influxdb.client import get_influx_client

logger = logging.getLogger(__name__)


class InfluxDBWriter:
    BATCH_SIZE = 100
    FLUSH_INTERVAL = 10.0

    def __init__(self):
        self._buffer: deque[Point] = deque(maxlen=10000)
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if not settings.influxdb_enabled:
            logger.info("InfluxDB disabled, writer not started")
            return
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("InfluxDB writer started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush()
        logger.info("InfluxDB writer stopped")

    def record_orderbook(
        self,
        exchange: str,
        symbol: str,
        best_bid: float,
        best_ask: float,
        bid_depth: list[tuple[float, float]],
        ask_depth: list[tuple[float, float]],
        timestamp_ms: int | None = None,
    ):
        ts = timestamp_ms or int(time.time() * 1000)
        point = (
            Point("orderbook_snapshot")
            .tag("exchange", exchange)
            .tag("symbol", symbol)
            .field("best_bid", best_bid)
            .field("best_ask", best_ask)
            .field("mid_price", (best_bid + best_ask) / 2)
            .time(ts * 1_000_000)  # nanoseconds
        )
        for i, (price, qty) in enumerate(bid_depth[:5]):
            point = point.field(f"bid_{i}_price", price).field(f"bid_{i}_qty", qty)
        for i, (price, qty) in enumerate(ask_depth[:5]):
            point = point.field(f"ask_{i}_price", price).field(f"ask_{i}_qty", qty)

        self._buffer.append(point)

    def record_spread(
        self,
        symbol: str,
        exchange_a: str,
        exchange_b: str,
        spread_pct: float,
        best_spread: float,
        mid_price: float,
        direction: str,
        timestamp_ms: int | None = None,
    ):
        ts = timestamp_ms or int(time.time() * 1000)
        point = (
            Point("spread_snapshot")
            .tag("symbol", symbol)
            .tag("exchange_a", exchange_a)
            .tag("exchange_b", exchange_b)
            .tag("direction", direction)
            .field("spread_pct", spread_pct)
            .field("best_spread", best_spread)
            .field("mid_price", mid_price)
            .time(ts * 1_000_000)
        )
        self._buffer.append(point)

    async def _flush_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.FLUSH_INTERVAL)
                await self._flush()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"InfluxDB flush error: {e}")

    async def _flush(self):
        if not self._buffer:
            return
        client = await get_influx_client()
        if not client:
            self._buffer.clear()
            return

        points = []
        while self._buffer and len(points) < self.BATCH_SIZE * 10:
            points.append(self._buffer.popleft())

        try:
            write_api = client.write_api()
            await write_api.write(
                bucket=settings.influxdb_bucket,
                org=settings.influxdb_org,
                record=points,
            )
            logger.debug(f"Flushed {len(points)} points to InfluxDB")
        except Exception as e:
            logger.error(f"InfluxDB write failed: {e}")


influx_writer = InfluxDBWriter()
