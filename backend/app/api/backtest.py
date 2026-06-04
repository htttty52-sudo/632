from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.backtest.schemas import BacktestRequest, BacktestResult
from app.backtest.engine import run_backtest
from app.influxdb.query import query_available_ranges
from app.config import settings, reload_settings

router = APIRouter()

MAX_BACKTEST_RANGE_DAYS = 90


@router.post("/run", response_model=BacktestResult)
async def run_backtest_endpoint(
    body: BacktestRequest,
    current_user=Depends(get_current_user),
):
    live_settings = reload_settings()

    if not live_settings.influxdb_enabled:
        raise HTTPException(status_code=503, detail="Historical data service not available")

    duration = body.end_time - body.start_time
    if duration > timedelta(days=MAX_BACKTEST_RANGE_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"Time range cannot exceed {MAX_BACKTEST_RANGE_DAYS} days",
        )
    if duration.total_seconds() <= 0:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    if not body.conditions:
        raise HTTPException(status_code=400, detail="At least one condition is required")

    if "maker_fee_rate" not in body.model_fields_set:
        body.maker_fee_rate = live_settings.maker_fee_rate
    if "taker_fee_rate" not in body.model_fields_set:
        body.taker_fee_rate = live_settings.taker_fee_rate
    if "trade_fraction" not in body.model_fields_set:
        body.trade_fraction = live_settings.trade_fraction
    if "min_trade_amount" not in body.model_fields_set:
        body.min_trade_amount = live_settings.min_trade_amount
    if "slippage_multiplier" not in body.model_fields_set:
        body.slippage_multiplier = live_settings.slippage_spread_multiplier

    allowed_fields = {"spread_pct", "best_spread", "volume"}
    allowed_ops = {">", "<", ">=", "<=", "=="}
    for cond in body.conditions:
        if cond.get("field") not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Invalid condition field: {cond.get('field')}")
        if cond.get("operator") not in allowed_ops:
            raise HTTPException(status_code=400, detail=f"Invalid operator: {cond.get('operator')}")

    result = await run_backtest(body)
    return result


@router.get("/available-ranges")
async def get_available_ranges(current_user=Depends(get_current_user)):
    if not settings.influxdb_enabled:
        return {"ranges": [], "message": "Historical data service not available"}
    ranges = await query_available_ranges()
    return {"ranges": ranges}
