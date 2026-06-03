import pytest
from app.dedup.deduplicator import MessageDeduplicator, SequenceWindow


class TestSequenceWindow:
    def test_first_message_not_duplicate(self):
        w = SequenceWindow(window_size=100)
        assert w.is_duplicate(1) is False

    def test_same_sequence_is_duplicate(self):
        w = SequenceWindow(window_size=100)
        w.is_duplicate(1)
        assert w.is_duplicate(1) is True

    def test_increasing_sequences_not_duplicate(self):
        w = SequenceWindow(window_size=100)
        for i in range(1, 50):
            assert w.is_duplicate(i) is False

    def test_out_of_order_within_window_detected(self):
        w = SequenceWindow(window_size=100)
        w.is_duplicate(10)
        w.is_duplicate(12)
        w.is_duplicate(11)
        assert w.is_duplicate(11) is True
        assert w.is_duplicate(12) is True

    def test_sequence_beyond_window_not_tracked(self):
        w = SequenceWindow(window_size=5)
        for i in range(1, 20):
            w.is_duplicate(i)
        # sequence 1 is well beyond the window (max=19, window=5)
        # so it's considered "too old" and not a duplicate
        assert w.is_duplicate(1) is False

    def test_eviction_keeps_window_bounded(self):
        w = SequenceWindow(window_size=10)
        for i in range(1, 100):
            w.is_duplicate(i)
        assert w.size <= 20  # at most 2x window_size

    def test_max_seq_tracks_highest(self):
        w = SequenceWindow(window_size=100)
        w.is_duplicate(5)
        w.is_duplicate(3)
        w.is_duplicate(10)
        assert w.max_seq == 10


class TestMessageDeduplicator:
    def test_first_message_not_duplicate(self):
        dedup = MessageDeduplicator(window_size=100)
        assert dedup.is_duplicate("binance:BTC/USDT:depth:100") is False

    def test_same_message_is_duplicate(self):
        dedup = MessageDeduplicator(window_size=100)
        dedup.is_duplicate("binance:BTC/USDT:depth:100")
        assert dedup.is_duplicate("binance:BTC/USDT:depth:100") is True

    def test_different_sequence_not_duplicate(self):
        dedup = MessageDeduplicator(window_size=100)
        assert dedup.is_duplicate("binance:BTC/USDT:depth:100") is False
        assert dedup.is_duplicate("binance:BTC/USDT:depth:101") is False

    def test_different_streams_independent(self):
        dedup = MessageDeduplicator(window_size=100)
        assert dedup.is_duplicate("binance:BTC/USDT:depth:100") is False
        assert dedup.is_duplicate("okx:BTC/USDT:depth:100") is False
        # Same sequence on different streams - NOT a duplicate
        assert dedup.is_duplicate("binance:BTC/USDT:trade:100") is False

    def test_same_symbol_same_channel_same_seq_is_duplicate(self):
        dedup = MessageDeduplicator(window_size=100)
        dedup.is_duplicate("binance:BTC/USDT:depth:500")
        assert dedup.is_duplicate("binance:BTC/USDT:depth:500") is True

    def test_reconnect_replay_detected(self):
        """After reconnect, exchange may replay recent sequences."""
        dedup = MessageDeduplicator(window_size=50)
        # Normal flow
        for i in range(100, 120):
            assert dedup.is_duplicate(f"binance:BTC/USDT:depth:{i}") is False
        # Reconnect replays sequences 115-125
        assert dedup.is_duplicate("binance:BTC/USDT:depth:115") is True
        assert dedup.is_duplicate("binance:BTC/USDT:depth:119") is True
        # New sequences pass through
        assert dedup.is_duplicate("binance:BTC/USDT:depth:120") is False
        assert dedup.is_duplicate("binance:BTC/USDT:depth:121") is False

    def test_clear(self):
        dedup = MessageDeduplicator(window_size=100)
        dedup.is_duplicate("binance:BTC/USDT:depth:1")
        dedup.clear()
        assert dedup.size == 0
        assert dedup.is_duplicate("binance:BTC/USDT:depth:1") is False

    def test_stream_count(self):
        dedup = MessageDeduplicator(window_size=100)
        dedup.is_duplicate("binance:BTC/USDT:depth:1")
        dedup.is_duplicate("binance:BTC/USDT:trade:1")
        dedup.is_duplicate("okx:BTC/USDT:depth:1")
        assert dedup.stream_count == 3

    def test_invalid_msg_id_not_duplicate(self):
        dedup = MessageDeduplicator(window_size=100)
        assert dedup.is_duplicate("malformed") is False
        assert dedup.is_duplicate("no:sequence:here:abc") is False
