from pydantic import BaseModel
from datetime import datetime


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    exchange_a: str
    exchange_b: str
    start_time: datetime
    end_time: datetime
    conditions: list[dict]
    initial_balance: float = 10000.0
    trade_fraction: float = 0.10
    maker_fee_rate: float = 0.001
    taker_fee_rate: float = 0.001
    cooldown_seconds: float = 5.0
    min_trade_amount: float = 1.0
    slippage_model: str = "simple"
    slippage_multiplier: float = 0.0005


class TradeRecord(BaseModel):
    timestamp: str
    spread_pct: float
    trade_amount: float
    slippage_pct: float
    fees: float
    pnl: float
    balance_after: float
    direction: str


class EquityPoint(BaseModel):
    timestamp: str
    balance: float
    pnl: float


class BacktestResult(BaseModel):
    equity_curve: list[EquityPoint]
    trades: list[TradeRecord]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    final_balance: float
    execution_time_ms: float
