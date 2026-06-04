import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.arbitrage.price_table import PriceTable, SlidingWindowClockEstimator, SymbolShard
from app.arbitrage.spread_engine import SpreadEngine


def now_ms() -> int:
    return int(time.time() * 1000)


class TestSlidingWindowClockEstimator:
    def test_first_sample_sets_offset(self):
        est = SlidingWindowClockEstimator(window_size=5)
        offset = est.update(1000.0, 900.0)
        assert offset == 100.0

    def test_median_of_multiple_samples(self):
        est = SlidingWindowClockEstimator(window_size=5)
        est.update(1000.0, 900.0)   # diff = 100
        est.update(1000.0, 880.0)   # diff = 120
        offset = est.update(1000.0, 890.0)  # diff = 110
        # median of [100, 120, 110] = 110
        assert offset == 110.0

    def test_sliding_window_drops_old_samples(self):
        est = SlidingWindowClockEstimator(window_size=3)
        est.update(1000.0, 900.0)   # 100
        est.update(1000.0, 800.0)   # 200
        est.update(1000.0, 850.0)   # 150
        # window: [100, 200, 150], median = 150
        assert est.offset_ms == 150.0
        est.update(1000.0, 890.0)   # 110
        # window: [200, 150, 110] (oldest 100 dropped), median = 150
        assert est.offset_ms == 150.0

    def test_offset_property_default(self):
        est = SlidingWindowClockEstimator()
        assert est.offset_ms == 0.0


@pytest.mark.asyncio
class TestPriceTableSharding:
    async def test_different_symbols_use_different_shards(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("binance", "ETH/USDT", Decimal("3500"), Decimal("3501"), now_ms())

        btc_prices = await table.get_valid_prices("BTC/USDT")
        eth_prices = await table.get_valid_prices("ETH/USDT")
        assert "binance" in btc_prices
        assert "binance" in eth_prices
        assert btc_prices["binance"].best_bid == Decimal("67500")
        assert eth_prices["binance"].best_bid == Decimal("3500")

    async def test_stale_on_one_symbol_doesnt_affect_other(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("binance", "ETH/USDT", Decimal("3500"), Decimal("3501"), now_ms())

        await table.mark_exchange_stale("binance", "BTC/USDT")

        btc_valid = await table.get_valid_prices("BTC/USDT")
        eth_valid = await table.get_valid_prices("ETH/USDT")
        assert "binance" not in btc_valid
        assert "binance" in eth_valid


@pytest.mark.asyncio
class TestPriceTableStaleness:
    async def test_fresh_price_is_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" in valid

    async def test_mark_exchange_stale_excludes_from_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("huobi", "BTC/USDT")

        valid = await table.get_valid_prices("BTC/USDT")
        assert "huobi" not in valid
        assert "binance" in valid
        assert "okx" in valid

    async def test_no_data_timeout_marks_stale(self):
        """5s no new data = stale (based on local_receive_time)."""
        table = PriceTable(stale_threshold_ms=200)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await asyncio.sleep(0.25)
        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" not in valid

    async def test_reconnect_restores_validity(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())
        await table.mark_exchange_stale("huobi", "BTC/USDT")

        valid = await table.get_valid_prices("BTC/USDT")
        assert "huobi" not in valid

        await table.update("huobi", "BTC/USDT", Decimal("67492"), Decimal("67493"), now_ms())
        valid = await table.get_valid_prices("BTC/USDT")
        assert "huobi" in valid

    async def test_all_exchanges_stale_returns_empty(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("binance", "BTC/USDT")
        await table.mark_exchange_stale("okx", "BTC/USDT")
        await table.mark_exchange_stale("huobi", "BTC/USDT")

        valid = await table.get_valid_prices("BTC/USDT")
        assert len(valid) == 0

    async def test_get_stale_exchanges(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.mark_exchange_stale("okx", "BTC/USDT")

        stale = await table.get_stale_exchanges("BTC/USDT")
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
        matrix = await engine._compute_matrix("BTC/USDT")

        assert matrix is not None
        assert len(matrix.exchanges) == 3
        assert len(matrix.cells) == 3
        assert len(matrix.stale_exchanges) == 0

    async def test_spread_matrix_excludes_stale_exchange(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        await table.mark_exchange_stale("huobi", "BTC/USDT")

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix("BTC/USDT")

        assert matrix is not None
        assert "huobi" not in matrix.exchanges
        assert len(matrix.cells) == 1
        assert "huobi" in matrix.stale_exchanges

    async def test_spread_matrix_returns_empty_cells_when_one_valid(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.mark_exchange_stale("binance", "BTC/USDT")
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.mark_exchange_stale("okx", "BTC/USDT")
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix("BTC/USDT")

        assert matrix is not None
        assert len(matrix.cells) == 0
        assert len(matrix.exchanges) == 1

    async def test_spread_calculation_correctness(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67520"), Decimal("67530"), now_ms())

        engine = SpreadEngine(table)
        matrix = await engine._compute_matrix("BTC/USDT")

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
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await engine._compute_matrix("BTC/USDT")

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 1
        alert = alert_calls[0][0][0]
        assert alert.exchange_a == "binance"
        assert alert.exchange_b == "okx"

    @patch("app.arbitrage.spread_engine.connection_manager")
    async def test_alert_30min_cooldown_prevents_flooding(self, mock_cm):
        """Same pair only triggers once within 30-minute window."""
        mock_cm.broadcast = AsyncMock()
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")
        engine._cooldown_seconds = 1800.0

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await engine._compute_matrix("BTC/USDT")
            await engine._compute_matrix("BTC/USDT")

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 1


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
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 3

        # First disconnect
        await table.mark_exchange_stale("huobi", "BTC/USDT")
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 1
        assert matrix.cells[0].exchange_a == "binance"
        assert matrix.cells[0].exchange_b == "okx"

        # Second disconnect
        await table.mark_exchange_stale("okx", "BTC/USDT")
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 0

        # Reconnect one
        await table.update("okx", "BTC/USDT", Decimal("67515"), Decimal("67516"), now_ms())
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 1

        # Reconnect all
        await table.update("huobi", "BTC/USDT", Decimal("67495"), Decimal("67496"), now_ms())
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 3

    async def test_5s_no_data_timeout_shows_delayed(self):
        """When no new data arrives for >5s, exchange is marked stale."""
        table = PriceTable(stale_threshold_ms=200)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())

        # Both fresh
        valid = await table.get_valid_prices("BTC/USDT")
        assert len(valid) == 2

        # Wait for timeout
        await asyncio.sleep(0.25)

        # Now stale
        valid = await table.get_valid_prices("BTC/USDT")
        assert len(valid) == 0
        stale = await table.get_stale_exchanges("BTC/USDT")
        assert "binance" in stale
        assert "okx" in stale

    async def test_stale_detection_with_clock_skew(self):
        """Exchange with clock ahead should still be detected as fresh if recent."""
        table = PriceTable(stale_threshold_ms=5000, clock_window_size=5)
        future_ts = now_ms() + 2000
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), future_ts)

        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" in valid

    async def test_parallel_symbol_updates_independent(self):
        """Different symbols can update concurrently without blocking each other."""
        table = PriceTable(stale_threshold_ms=5000)

        async def update_btc():
            for _ in range(10):
                await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
                await asyncio.sleep(0.01)

        async def update_eth():
            for _ in range(10):
                await table.update("binance", "ETH/USDT", Decimal("3500"), Decimal("3501"), now_ms())
                await asyncio.sleep(0.01)

        await asyncio.gather(update_btc(), update_eth())

        btc = await table.get_valid_prices("BTC/USDT")
        eth = await table.get_valid_prices("ETH/USDT")
        assert "binance" in btc
        assert "binance" in eth
