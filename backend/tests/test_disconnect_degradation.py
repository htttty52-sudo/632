import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.arbitrage.price_table import PriceTable, ClockEstimator
from app.arbitrage.spread_engine import SpreadEngine


def now_ms() -> int:
    return int(time.time() * 1000)


class TestClockEstimator:
    def test_first_sample_sets_offset(self):
        est = ClockEstimator(alpha=0.1)
        offset = est.update(1000.0, 900.0)
        assert offset == 100.0

    def test_ewma_smooths_jitter(self):
        est = ClockEstimator(alpha=0.5)
        est.update(1000.0, 900.0)  # offset = 100
        offset = est.update(1000.0, 880.0)  # sample = 120, ewma = 0.5*120 + 0.5*100 = 110
        assert offset == 110.0

    def test_offset_property_default(self):
        est = ClockEstimator()
        assert est.offset_ms == 0.0


@pytest.mark.asyncio
class TestPriceTableStaleness:
    async def test_fresh_price_is_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        valid = await table.get_valid_prices()
        assert "binance" in valid

    async def test_mark_exchange_stale_excludes_from_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("huobi")

        valid = await table.get_valid_prices()
        assert "huobi" not in valid
        assert "binance" in valid
        assert "okx" in valid

    async def test_time_based_staleness(self):
        table = PriceTable(stale_threshold_ms=100)
        old_ts = now_ms() - 500
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), old_ts)
        await asyncio.sleep(0.15)
        valid = await table.get_valid_prices()
        assert "binance" not in valid

    async def test_reconnect_restores_validity(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())
        await table.mark_exchange_stale("huobi")

        valid = await table.get_valid_prices()
        assert "huobi" not in valid

        await table.update("huobi", "BTC/USDT", Decimal("67492"), Decimal("67493"), now_ms())
        valid = await table.get_valid_prices()
        assert "huobi" in valid

    async def test_all_exchanges_stale_returns_empty(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("binance")
        await table.mark_exchange_stale("okx")
        await table.mark_exchange_stale("huobi")

        valid = await table.get_valid_prices()
        assert len(valid) == 0

    async def test_get_stale_exchanges(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.mark_exchange_stale("okx")

        stale = await table.get_stale_exchanges()
        assert "okx" in stale
        assert "binance" not in stale


@pytest.mark.asyncio
class TestSpreadEngineWithDegradation:
    async def test_spread_matrix_with_all_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix()

        assert matrix is not None
        assert len(matrix.exchanges) == 3
        assert len(matrix.cells) == 3  # C(3,2) = 3 pairs
        assert len(matrix.stale_exchanges) == 0

    async def test_spread_matrix_excludes_stale_exchange(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("huobi")

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix()

        assert matrix is not None
        assert "huobi" not in matrix.exchanges
        assert len(matrix.cells) == 1  # only binance-okx pair
        assert "huobi" in matrix.stale_exchanges

    async def test_spread_matrix_returns_empty_cells_when_one_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.mark_exchange_stale("binance")
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.mark_exchange_stale("okx")
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix()

        assert matrix is not None
        assert len(matrix.cells) == 0
        assert len(matrix.exchanges) == 1

    async def test_spread_calculation_correctness(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67520"), Decimal("67530"), now_ms())

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix()

        assert matrix is not None
        cell = matrix.cells[0]
        assert cell.exchange_a == "binance"
        assert cell.exchange_b == "okx"
        # spread_ab = okx_bid - binance_ask = 67520 - 67510 = 10
        assert cell.spread_ab == Decimal("10")
        # spread_ba = binance_bid - okx_ask = 67500 - 67530 = -30
        assert cell.spread_ba == Decimal("-30")
        assert cell.best_spread == Decimal("10")

    @patch("app.arbitrage.spread_engine.connection_manager")
    async def test_alert_triggered_on_threshold(self, mock_cm):
        mock_cm.broadcast = AsyncMock()
        table = PriceTable(stale_threshold_ms=5000)
        # Large spread: buy on binance at 67510, sell on okx at 67600
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await engine._compute_matrix()

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 1
        alert = alert_calls[0][0][0]
        assert alert.exchange_a == "binance"
        assert alert.exchange_b == "okx"

    @patch("app.arbitrage.spread_engine.connection_manager")
    async def test_alert_cooldown_prevents_flooding(self, mock_cm):
        mock_cm.broadcast = AsyncMock()
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")
        engine._cooldown_seconds = 60.0

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await engine._compute_matrix()
            await engine._compute_matrix()

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 1  # second call suppressed by cooldown


@pytest.mark.asyncio
class TestConsecutiveDisconnectDegradation:
    async def test_sequential_disconnects_degrade_gracefully(self):
        """Simulate exchanges disconnecting one by one."""
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        engine = SpreadEngine(table)

        # All valid: 3 pairs
        matrix = await engine._compute_matrix()
        assert len(matrix.cells) == 3

        # First disconnect
        await table.mark_exchange_stale("huobi")
        matrix = await engine._compute_matrix()
        assert len(matrix.cells) == 1
        assert matrix.cells[0].exchange_a == "binance"
        assert matrix.cells[0].exchange_b == "okx"

        # Second disconnect
        await table.mark_exchange_stale("okx")
        matrix = await engine._compute_matrix()
        assert len(matrix.cells) == 0

        # Reconnect one
        await table.update("okx", "BTC/USDT", Decimal("67515"), Decimal("67516"), now_ms())
        matrix = await engine._compute_matrix()
        assert len(matrix.cells) == 1

        # Reconnect all
        await table.update("huobi", "BTC/USDT", Decimal("67495"), Decimal("67496"), now_ms())
        matrix = await engine._compute_matrix()
        assert len(matrix.cells) == 3

    async def test_stale_detection_with_clock_skew(self):
        """Exchange with clock significantly ahead should still be detected as fresh."""
        table = PriceTable(stale_threshold_ms=5000, clock_alpha=1.0)
        # Exchange clock is 2 seconds ahead of local
        future_ts = now_ms() + 2000
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), future_ts)

        valid = await table.get_valid_prices()
        assert "binance" in valid
