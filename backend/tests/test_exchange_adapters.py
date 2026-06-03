import pytest
from decimal import Decimal
from app.exchanges.binance import BinanceClient
from app.exchanges.okx import OKXClient
from app.models.market import UnifiedOrderBook, UnifiedTrade


def test_binance_parse_depth():
    client = BinanceClient()
    raw = {
        "lastUpdateId": 123456,
        "bids": [["67500.00", "1.5"], ["67499.50", "2.0"]],
        "asks": [["67501.00", "0.8"], ["67501.50", "1.2"]],
    }
    result = client.parse_depth(raw)
    assert isinstance(result, UnifiedOrderBook)
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT"
    assert result.sequence == 123456
    assert len(result.bids) == 2
    assert result.bids[0].price == Decimal("67500.00")
    assert result.asks[0].price == Decimal("67501.00")
    assert result.msg_id == "binance:BTC/USDT:depth:123456"


def test_binance_parse_trade():
    client = BinanceClient()
    raw = {
        "e": "trade",
        "t": 9876543,
        "p": "67500.50",
        "q": "0.123",
        "T": 1700000000000,
        "m": True,
    }
    result = client.parse_trade(raw)
    assert isinstance(result, UnifiedTrade)
    assert result.exchange == "binance"
    assert result.trade_id == "9876543"
    assert result.price == Decimal("67500.50")
    assert result.quantity == Decimal("0.123")
    assert result.side == "sell"
    assert result.msg_id == "binance:BTC/USDT:trade:9876543"


def test_okx_parse_depth():
    client = OKXClient()
    raw = {
        "arg": {"channel": "books5", "instId": "BTC-USDT"},
        "data": [{
            "bids": [["67500.0", "1.5", "0", "3"], ["67499.5", "2.0", "0", "5"]],
            "asks": [["67501.0", "0.8", "0", "2"], ["67501.5", "1.2", "0", "4"]],
            "ts": "1700000000123",
            "seqId": 99999,
        }]
    }
    result = client.parse_depth(raw)
    assert isinstance(result, UnifiedOrderBook)
    assert result.exchange == "okx"
    assert result.symbol == "BTC/USDT"
    assert result.sequence == 99999
    assert result.bids[0].price == Decimal("67500.0")
    assert result.msg_id == "okx:BTC/USDT:depth:99999"


def test_okx_parse_trade():
    client = OKXClient()
    raw = {
        "tradeId": "555111",
        "px": "67505.5",
        "sz": "0.05",
        "side": "buy",
        "ts": "1700000000500",
    }
    result = client.parse_trade(raw)
    assert isinstance(result, UnifiedTrade)
    assert result.exchange == "okx"
    assert result.trade_id == "555111"
    assert result.price == Decimal("67505.5")
    assert result.side == "buy"
