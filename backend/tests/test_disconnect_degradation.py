import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.arbitrage.price_table import PriceTable, SlidingWindowClockEstimator, ExchangeSymbolSlot
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
        assert est.offset_ms == 150.0
        est.update(1000.0, 890.0)   # 110 -> window [200, 150, 110], median=150
        assert est.offset_ms == 150.0

    def test_offset_property_default(self):
        est = SlidingWindowClockEstimator()
        assert est.offset_ms == 0.0

    def test_reset_clears_window(self):
        est = SlidingWindowClockEstimator(window_size=5)
        est.update(1000.0, 900.0)
        est.update(1000.0, 850.0)
        est.reset()
        assert est.offset_ms == 0.0
        offset = est.update(2000.0, 1950.0)  # fresh start: diff=50
        assert offset == 50.0

    def test_stable_burst_discards_stale_entries(self):
        """After 5 stable samples, old entries deviating >2s are discarded."""
        est = SlidingWindowClockEstimator(
            window_size=20, stable_count=5, stale_discard_ms=2000.0
        )
        # Add some very skewed old samples (offset ~5000ms)
        for _ in range(5):
            est.update(10000.0, 5000.0)  # diff = 5000

        # Now feed 5 stable samples around 100ms
        for i in range(5):
            est.update(10000.0 + i, 9900.0 + i)  # diff ~100

        # The old 5000ms entries should be discarded since they deviate >2000 from median(~100)
        # Median should now be close to 100, not pulled up by 5000
        assert est.offset_ms < 200.0


@pytest.mark.asyncio
class TestPerExchangePerSymbolLocking:
    async def test_different_exchanges_same_symbol_independent_locks(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())

        # Mark only binance stale
        await table.mark_exchange_stale("binance", "BTC/USDT")
        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" not in valid
        assert "okx" in valid

    async def test_same_exchange_different_symbols_independent(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("binance", "ETH/USDT", Decimal("3500"), Decimal("3501"), now_ms())

        await table.mark_exchange_stale("binance", "BTC/USDT")
        btc = await table.get_valid_prices("BTC/USDT")
        eth = await table.get_valid_prices("ETH/USDT")
        assert "binance" not in btc
        assert "binance" in eth

    async def test_parallel_updates_no_contention(self):
        """Different (exchange, symbol) pairs update truly in parallel."""
        table = PriceTable(stale_threshold_ms=5000)

        async def update_binance_btc():
            for _ in range(20):
                await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
                await asyncio.sleep(0.005)

        async def update_okx_eth():
            for _ in range(20):
                await table.update("okx", "ETH/USDT", Decimal("3500"), Decimal("3501"), now_ms())
                await asyncio.sleep(0.005)

        async def update_huobi_btc():
            for _ in range(20):
                await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())
                await asyncio.sleep(0.005)

        await asyncio.gather(update_binance_btc(), update_okx_eth(), update_huobi_btc())

        btc = await table.get_valid_prices("BTC/USDT")
        eth = await table.get_valid_prices("ETH/USDT")
        assert "binance" in btc
        assert "huobi" in btc
        assert "okx" in eth


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

    async def test_5s_no_data_timeout(self):
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

        await table.mark_exchange_stale("binance", "BTC/USDT")
        await table.mark_exchange_stale("okx", "BTC/USDT")

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
class TestClearStaleOnReconnect:
    async def test_clear_exchange_stale_restores_all_symbols(self):
        """Reconnect clears stale mark for all symbols of that exchange."""
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())
        await table.update("huobi", "ETH/USDT", Decimal("3490"), Decimal("3491"), now_ms())

        # Disconnect marks all stale
        await table.mark_exchange_stale("huobi")
        btc = await table.get_valid_prices("BTC/USDT")
        eth = await table.get_valid_prices("ETH/USDT")
        assert "huobi" not in btc
        assert "huobi" not in eth

        # Reconnect clears all
        await table.clear_exchange_stale("huobi")
        btc = await table.get_valid_prices("BTC/USDT")
        eth = await table.get_valid_prices("ETH/USDT")
        assert "huobi" in btc
        assert "huobi" in eth

    async def test_clear_stale_resets_clock_estimator(self):
        """After reconnect, clock estimator starts fresh."""
        table = PriceTable(stale_threshold_ms=5000, clock_window_size=5)
        # Feed skewed timestamps
        for _ in range(5):
            await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"),
                               now_ms() - 5000)

        await table.clear_exchange_stale("binance")

        # Now feed fresh timestamp - should be immediately valid
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" in valid


@pytest.mark.asyncio
class TestSpreadEngineAlertWindowing:
    @patch("app.arbitrage.spread_engine.connection_manager")
    async def test_alert_allows_max_3_within_5min(self, mock_cm):
        """Same pair+direction: max 3 alerts within the cooldown window."""
        mock_cm.broadcast = AsyncMock()
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")
        engine._cooldown_seconds = 300.0
        engine._max_per_window = 3

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            # Fire 5 times, only first 3 should emit alerts
            for _ in range(5):
                await engine._compute_matrix("BTC/USDT")

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 3

    @patch("app.arbitrage.spread_engine.connection_manager")
    async def test_different_directions_have_separate_quotas(self, mock_cm):
        """a_to_b and b_to_a are tracked separately."""
        mock_cm.broadcast = AsyncMock()
        table = PriceTable(stale_threshold_ms=5000)

        engine = SpreadEngine(table)
        engine._threshold_pct = Decimal("0.01")
        engine._cooldown_seconds = 300.0
        engine._max_per_window = 1

        with patch("app.arbitrage.spread_engine.async_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            # First: spread favors a_to_b
            await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
            await table.update("okx", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())
            await engine._compute_matrix("BTC/USDT")

            # Flip: spread favors b_to_a
            await table.update("binance", "BTC/USDT", Decimal("67600"), Decimal("67610"), now_ms())
            await table.update("okx", "BTC/USDT", Decimal("67500"), Decimal("67510"), now_ms())
            await engine._compute_matrix("BTC/USDT")

        alert_calls = [
            c for c in mock_cm.broadcast.call_args_list
            if hasattr(c[0][0], 'direction')
        ]
        assert len(alert_calls) == 2
        directions = {c[0][0].direction for c in alert_calls}
        assert "a_to_b" in directions
        assert "b_to_a" in directions


@pytest.mark.asyncio
class TestConsecutiveDisconnectDegradation:
    async def test_sequential_disconnects_degrade_gracefully(self):
        table = PriceTable(stale_threshold_ms=5000)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())
        await table.update("huobi", "BTC/USDT", Decimal("67490"), Decimal("67491"), now_ms())

        engine = SpreadEngine(table)

        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 3

        await table.mark_exchange_stale("huobi", "BTC/USDT")
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 1

        await table.mark_exchange_stale("okx", "BTC/USDT")
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 0

        # Reconnect: clear + fresh data
        await table.clear_exchange_stale("okx")
        await table.update("okx", "BTC/USDT", Decimal("67515"), Decimal("67516"), now_ms())
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 1

        await table.clear_exchange_stale("huobi")
        await table.update("huobi", "BTC/USDT", Decimal("67495"), Decimal("67496"), now_ms())
        matrix = await engine._compute_matrix("BTC/USDT")
        assert len(matrix.cells) == 3

    async def test_5s_timeout_marks_delayed(self):
        table = PriceTable(stale_threshold_ms=200)
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), now_ms())
        await table.update("okx", "BTC/USDT", Decimal("67510"), Decimal("67511"), now_ms())

        await asyncio.sleep(0.25)
        stale = await table.get_stale_exchanges("BTC/USDT")
        assert "binance" in stale
        assert "okx" in stale

    async def test_clock_skew_handled_correctly(self):
        table = PriceTable(stale_threshold_ms=5000, clock_window_size=5)
        future_ts = now_ms() + 2000
        await table.update("binance", "BTC/USDT", Decimal("67500"), Decimal("67501"), future_ts)
        valid = await table.get_valid_prices("BTC/USDT")
        assert "binance" in valid
