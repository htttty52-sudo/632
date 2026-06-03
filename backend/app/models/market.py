from pydantic import BaseModel
from typing import Literal
from decimal import Decimal


class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: Decimal


class UnifiedOrderBook(BaseModel):
    msg_id: str
    exchange: str
    symbol: str
    timestamp: int
    sequence: int
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


class UnifiedTrade(BaseModel):
    msg_id: str
    exchange: str
    symbol: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    side: Literal["buy", "sell"]
    timestamp: int


class SpreadSnapshot(BaseModel):
    symbol: str
    exchange_a: str
    exchange_b: str
    a_best_bid: Decimal
    a_best_ask: Decimal
    b_best_bid: Decimal
    b_best_ask: Decimal
    spread: Decimal
    spread_pct: Decimal
    timestamp: int
