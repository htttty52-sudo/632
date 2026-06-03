import time
import pytest
from app.dedup.deduplicator import MessageDeduplicator


def test_first_message_not_duplicate():
    dedup = MessageDeduplicator(ttl_seconds=5.0)
    assert dedup.is_duplicate("msg1") is False


def test_second_same_message_is_duplicate():
    dedup = MessageDeduplicator(ttl_seconds=5.0)
    dedup.is_duplicate("msg1")
    assert dedup.is_duplicate("msg1") is True


def test_different_messages_not_duplicate():
    dedup = MessageDeduplicator(ttl_seconds=5.0)
    assert dedup.is_duplicate("msg1") is False
    assert dedup.is_duplicate("msg2") is False


def test_ttl_expiry():
    dedup = MessageDeduplicator(ttl_seconds=0.1)
    assert dedup.is_duplicate("msg1") is False
    time.sleep(0.15)
    assert dedup.is_duplicate("msg1") is False


def test_max_size_eviction():
    dedup = MessageDeduplicator(ttl_seconds=60.0, max_size=5)
    for i in range(10):
        dedup.is_duplicate(f"msg{i}")
    assert dedup.size <= 5
    assert dedup.is_duplicate("msg0") is False
    assert dedup.is_duplicate("msg9") is True


def test_clear():
    dedup = MessageDeduplicator(ttl_seconds=60.0)
    dedup.is_duplicate("msg1")
    dedup.clear()
    assert dedup.size == 0
    assert dedup.is_duplicate("msg1") is False


def test_interleaved_messages():
    dedup = MessageDeduplicator(ttl_seconds=5.0)
    ids = ["binance:BTC/USDT:depth:100", "okx:BTC/USDT:depth:200", "binance:BTC/USDT:trade:5001"]
    for msg_id in ids:
        assert dedup.is_duplicate(msg_id) is False
    for msg_id in ids:
        assert dedup.is_duplicate(msg_id) is True
