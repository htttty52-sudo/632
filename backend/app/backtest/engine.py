import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd
from numba import jit

from app.backtest.schemas import (
    BacktestRequest, BacktestResult, EquityPoint, TradeRecord,
)
from app.core.trading import compute_slippage_from_book
from app.influxdb.query import query_spread_data, query_orderbook_depth

logger = logging.getLogger(__name__)

_executor = ProcessPoolExecutor(max_workers=2)

FIELD_SPREAD_PCT = 0
FIELD_BEST_SPREAD = 1
FIELD_VOLUME = 2

FIELD_MAP = {
    "spread_pct": FIELD_SPREAD_PCT,
    "best_spread": FIELD_BEST_SPREAD,
    "volume": FIELD_VOLUME,
}

OP_GT = 0
OP_LT = 1
OP_GTE = 2
OP_LTE = 3
OP_EQ = 4

OP_MAP = {
    ">": OP_GT,
    "<": OP_LT,
    ">=": OP_GTE,
    "<=": OP_LTE,
    "==": OP_EQ,
}


@jit(nopython=True, cache=True)
def _run_backtest_core(
    spread_pcts: np.ndarray,
    best_spreads: np.ndarray,
    condition_fields: np.ndarray,
    condition_ops: np.ndarray,
    condition_values: np.ndarray,
    initial_balance: float,
    trade_fraction: float,
    min_trade_amount: float,
    round_trip_fee_rate: float,
    slippage_pcts: np.ndarray,
    cooldown_periods: int,
):
    """Numba-optimized backtest inner loop with per-bar slippage array."""
    n = len(spread_pcts)
    n_conds = len(condition_fields)

    balances = np.empty(n, dtype=np.float64)
    trade_mask = np.zeros(n, dtype=np.int8)
    trade_pnls = np.zeros(n, dtype=np.float64)
    trade_amounts = np.zeros(n, dtype=np.float64)
    trade_fees = np.zeros(n, dtype=np.float64)
    trade_slippages = np.zeros(n, dtype=np.float64)

    balance = initial_balance
    cooldown_remaining = 0

    for i in range(n):
        balances[i] = balance

        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        all_pass = True
        for c in range(n_conds):
            field_idx = condition_fields[c]
            op_idx = condition_ops[c]
            threshold = condition_values[c]

            if field_idx == FIELD_SPREAD_PCT:
                val = spread_pcts[i]
            elif field_idx == FIELD_BEST_SPREAD:
                val = best_spreads[i]
            else:
                val = 0.0

            if op_idx == OP_GT:
                if not (val > threshold):
                    all_pass = False
                    break
            elif op_idx == OP_LT:
                if not (val < threshold):
                    all_pass = False
                    break
            elif op_idx == OP_GTE:
                if not (val >= threshold):
                    all_pass = False
                    break
            elif op_idx == OP_LTE:
                if not (val <= threshold):
                    all_pass = False
                    break
            elif op_idx == OP_EQ:
                if not (val == threshold):
                    all_pass = False
                    break

        if not all_pass:
            continue

        amount = balance * trade_fraction
        if amount < min_trade_amount:
            continue

        fees = amount * round_trip_fee_rate
        slippage_cost = amount * slippage_pcts[i]
        gross_pnl = amount * (spread_pcts[i] / 100.0)
        net_pnl = gross_pnl - fees - slippage_cost

        balance += net_pnl
        balances[i] = balance
        trade_mask[i] = 1
        trade_pnls[i] = net_pnl
        trade_amounts[i] = amount
        trade_fees[i] = fees
        trade_slippages[i] = slippage_cost
        cooldown_remaining = cooldown_periods

    return balances, trade_mask, trade_pnls, trade_amounts, trade_fees, trade_slippages


def _compute_metrics(
    balances: np.ndarray,
    trade_mask: np.ndarray,
    trade_pnls: np.ndarray,
    initial_balance: float,
) -> tuple[float, float, float]:
    peak = initial_balance
    max_dd = 0.0
    for b in balances:
        if b > peak:
            peak = b
        dd = (peak - b) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    trade_pnls_only = trade_pnls[trade_mask == 1]
    if len(trade_pnls_only) > 0:
        wins = np.sum(trade_pnls_only > 0)
        win_rate = float(wins) / len(trade_pnls_only)
    else:
        win_rate = 0.0

    if len(trade_pnls_only) > 1:
        returns = trade_pnls_only / initial_balance
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(525600)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    return max_dd, sharpe, win_rate


def _precompute_slippage_from_depth(
    spread_df: pd.DataFrame,
    depth_df: pd.DataFrame,
    trade_fraction: float,
    initial_balance: float,
) -> np.ndarray:
    """Pre-compute per-bar slippage_pct by calling compute_slippage_from_book."""
    n = len(spread_df)
    slippage_pcts = np.zeros(n, dtype=np.float64)

    if depth_df.empty:
        return slippage_pcts

    depth_df = depth_df.sort_values("timestamp").reset_index(drop=True)
    depth_timestamps = depth_df["timestamp"].values

    estimate_amount = initial_balance * trade_fraction

    for i in range(n):
        ts = spread_df["timestamp"].iloc[i]
        idx = np.searchsorted(depth_timestamps, ts, side="right") - 1
        if idx < 0:
            idx = 0

        row = depth_df.iloc[idx]
        ask_levels: list[tuple[float, float]] = []
        for lvl in range(5):
            price_col = f"ask_{lvl}_price"
            qty_col = f"ask_{lvl}_qty"
            if price_col in row and qty_col in row:
                p = row.get(price_col)
                q = row.get(qty_col)
                if p and q and float(p) > 0 and float(q) > 0:
                    ask_levels.append((float(p), float(q)))

        if ask_levels:
            result = compute_slippage_from_book(ask_levels, estimate_amount)
            slippage_pcts[i] = result.slippage_pct / 100.0
        else:
            slippage_pcts[i] = 0.0

    return slippage_pcts


def _run_backtest_sync(params: dict) -> dict:
    start_t = time.perf_counter()

    spread_pcts = np.array(params["spread_pcts"], dtype=np.float64)
    best_spreads = np.array(params["best_spreads"], dtype=np.float64)
    slippage_pcts = np.array(params["slippage_pcts"], dtype=np.float64)
    timestamps = params["timestamps"]
    directions = params["directions"]

    conditions = params["conditions"]
    condition_fields = np.array(
        [FIELD_MAP.get(c.get("field", ""), 0) for c in conditions], dtype=np.int64
    )
    condition_ops = np.array(
        [OP_MAP.get(c.get("operator", ""), 0) for c in conditions], dtype=np.int64
    )
    condition_values = np.array(
        [float(c.get("value", 0)) for c in conditions], dtype=np.float64
    )

    initial_balance = params["initial_balance"]
    trade_fraction = params["trade_fraction"]
    min_trade_amount = params["min_trade_amount"]
    round_trip_fee_rate = params["maker_fee_rate"] + params["taker_fee_rate"]
    cooldown_seconds = params["cooldown_seconds"]

    if len(timestamps) > 1:
        intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(min(10, len(timestamps)-1))]
        avg_interval = max(sum(intervals) / len(intervals), 1.0)
    else:
        avg_interval = 60.0
    cooldown_periods = max(1, int(cooldown_seconds / avg_interval))

    balances, trade_mask, trade_pnls, trade_amounts, trade_fees, trade_slippages = _run_backtest_core(
        spread_pcts=spread_pcts,
        best_spreads=best_spreads,
        condition_fields=condition_fields,
        condition_ops=condition_ops,
        condition_values=condition_values,
        initial_balance=initial_balance,
        trade_fraction=trade_fraction,
        min_trade_amount=min_trade_amount,
        round_trip_fee_rate=round_trip_fee_rate,
        slippage_pcts=slippage_pcts,
        cooldown_periods=cooldown_periods,
    )

    max_dd, sharpe, win_rate = _compute_metrics(
        balances, trade_mask, trade_pnls, initial_balance
    )

    n = len(balances)
    step = max(1, n // 1000)
    equity_curve = []
    for i in range(0, n, step):
        equity_curve.append({
            "timestamp": timestamps[i].isoformat() if hasattr(timestamps[i], 'isoformat') else str(timestamps[i]),
            "balance": float(balances[i]),
            "pnl": float(balances[i] - initial_balance),
        })

    trades = []
    trade_indices = np.where(trade_mask == 1)[0]
    for idx in trade_indices:
        trades.append({
            "timestamp": timestamps[idx].isoformat() if hasattr(timestamps[idx], 'isoformat') else str(timestamps[idx]),
            "spread_pct": float(spread_pcts[idx]),
            "trade_amount": float(trade_amounts[idx]),
            "slippage_pct": float(slippage_pcts[idx] * 100),
            "fees": float(trade_fees[idx]),
            "pnl": float(trade_pnls[idx]),
            "balance_after": float(balances[idx]),
            "direction": directions[idx] if idx < len(directions) else "",
        })

    total_trades = len(trades)
    winning_trades = int(np.sum(trade_pnls[trade_mask == 1] > 0)) if total_trades > 0 else 0
    losing_trades = total_trades - winning_trades

    elapsed_ms = (time.perf_counter() - start_t) * 1000

    return {
        "equity_curve": equity_curve,
        "trades": trades,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "total_pnl": float(balances[-1] - initial_balance) if n > 0 else 0.0,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "final_balance": float(balances[-1]) if n > 0 else initial_balance,
        "execution_time_ms": elapsed_ms,
    }


async def run_backtest(request: BacktestRequest) -> BacktestResult:
    """Load data from InfluxDB and run backtest in process pool."""
    df = await query_spread_data(
        symbol=request.symbol,
        exchange_a=request.exchange_a,
        exchange_b=request.exchange_b,
        start_time=request.start_time,
        end_time=request.end_time,
    )

    if df.empty:
        return BacktestResult(
            equity_curve=[],
            trades=[],
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            final_balance=request.initial_balance,
            execution_time_ms=0.0,
        )

    # Pre-compute slippage array
    if request.slippage_model == "orderbook":
        sell_exchange = request.exchange_b
        depth_df = await query_orderbook_depth(
            symbol=request.symbol,
            exchange=sell_exchange,
            start_time=request.start_time,
            end_time=request.end_time,
        )
        slippage_pcts = _precompute_slippage_from_depth(
            df, depth_df, request.trade_fraction, request.initial_balance
        )
    else:
        slippage_pcts = np.full(len(df), request.slippage_multiplier, dtype=np.float64)

    params = {
        "spread_pcts": df["spread_pct"].tolist(),
        "best_spreads": df["best_spread"].tolist(),
        "slippage_pcts": slippage_pcts.tolist(),
        "timestamps": df["timestamp"].tolist(),
        "directions": df["direction"].tolist() if "direction" in df.columns else [""] * len(df),
        "conditions": request.conditions,
        "initial_balance": request.initial_balance,
        "trade_fraction": request.trade_fraction,
        "min_trade_amount": request.min_trade_amount,
        "maker_fee_rate": request.maker_fee_rate,
        "taker_fee_rate": request.taker_fee_rate,
        "cooldown_seconds": request.cooldown_seconds,
    }

    loop = asyncio.get_event_loop()
    result_dict = await loop.run_in_executor(_executor, _run_backtest_sync, params)
    return BacktestResult(**result_dict)
