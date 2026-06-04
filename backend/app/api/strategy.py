import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.models.strategy import Strategy, StrategyLog
from app.auth.dependencies import get_current_user, require_admin

router = APIRouter()


class ConditionRule(BaseModel):
    field: str  # "spread_pct", "volume", "best_spread"
    operator: str  # ">", "<", ">=", "<=", "=="
    value: float


class StrategyCreate(BaseModel):
    name: str
    conditions: list[ConditionRule]
    simulated_balance: float = 10000.0


class StrategyUpdate(BaseModel):
    name: str | None = None
    conditions: list[ConditionRule] | None = None
    active: bool | None = None


class StrategyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    conditions: list[ConditionRule]
    active: bool
    simulated_balance: float
    initial_balance: float
    pnl: float
    created_at: str | None

    class Config:
        from_attributes = True


class StrategyLogResponse(BaseModel):
    id: int
    strategy_id: int
    triggered_at: str | None
    symbol: str
    exchange_a: str
    exchange_b: str
    direction: str
    spread_pct: float
    simulated_quantity: float
    simulated_pnl: float
    balance_after: float
    condition_snapshot: str


def _strategy_to_response(s: Strategy) -> StrategyResponse:
    conditions = json.loads(s.conditions) if isinstance(s.conditions, str) else s.conditions
    return StrategyResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        conditions=[ConditionRule(**c) for c in conditions],
        active=s.active,
        simulated_balance=s.simulated_balance,
        initial_balance=s.initial_balance,
        pnl=s.simulated_balance - s.initial_balance,
        created_at=str(s.created_at) if s.created_at else None,
    )


@router.get("/", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == current_user.id).order_by(Strategy.id.desc())
    )
    return [_strategy_to_response(s) for s in result.scalars().all()]


@router.get("/all", response_model=list[StrategyResponse])
async def list_all_strategies(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).order_by(Strategy.id.desc()))
    return [_strategy_to_response(s) for s in result.scalars().all()]


@router.post("/", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_conditions(body.conditions)
    strategy = Strategy(
        user_id=current_user.id,
        name=body.name,
        conditions=json.dumps([c.model_dump() for c in body.conditions]),
        simulated_balance=body.simulated_balance,
        initial_balance=body.simulated_balance,
        active=True,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)

    from app.strategy.engine import strategy_engine
    await strategy_engine.reload_strategies()

    return _strategy_to_response(strategy)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    body: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    if body.name is not None:
        strategy.name = body.name
    if body.conditions is not None:
        _validate_conditions(body.conditions)
        strategy.conditions = json.dumps([c.model_dump() for c in body.conditions])
    if body.active is not None:
        strategy.active = body.active

    await db.commit()
    await db.refresh(strategy)

    from app.strategy.engine import strategy_engine
    await strategy_engine.reload_strategies()

    return _strategy_to_response(strategy)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(strategy)
    await db.commit()

    from app.strategy.engine import strategy_engine
    await strategy_engine.reload_strategies()


@router.get("/logs", response_model=list[StrategyLogResponse])
async def list_logs(
    strategy_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(StrategyLog).where(StrategyLog.user_id == current_user.id)
    if strategy_id:
        query = query.where(StrategyLog.strategy_id == strategy_id)
    query = query.order_by(StrategyLog.id.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        StrategyLogResponse(
            id=log.id,
            strategy_id=log.strategy_id,
            triggered_at=str(log.triggered_at) if log.triggered_at else None,
            symbol=log.symbol,
            exchange_a=log.exchange_a,
            exchange_b=log.exchange_b,
            direction=log.direction,
            spread_pct=log.spread_pct,
            simulated_quantity=log.simulated_quantity,
            simulated_pnl=log.simulated_pnl,
            balance_after=log.balance_after,
            condition_snapshot=log.condition_snapshot,
        )
        for log in logs
    ]


@router.get("/logs/all", response_model=list[StrategyLogResponse])
async def list_all_logs(
    limit: int = Query(50, le=200),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(StrategyLog).order_by(StrategyLog.id.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        StrategyLogResponse(
            id=log.id,
            strategy_id=log.strategy_id,
            triggered_at=str(log.triggered_at) if log.triggered_at else None,
            symbol=log.symbol,
            exchange_a=log.exchange_a,
            exchange_b=log.exchange_b,
            direction=log.direction,
            spread_pct=log.spread_pct,
            simulated_quantity=log.simulated_quantity,
            simulated_pnl=log.simulated_pnl,
            balance_after=log.balance_after,
            condition_snapshot=log.condition_snapshot,
        )
        for log in logs
    ]


ALLOWED_FIELDS = {"spread_pct", "best_spread", "volume"}
ALLOWED_OPERATORS = {">", "<", ">=", "<=", "=="}


def _validate_conditions(conditions: list[ConditionRule]):
    if not conditions:
        raise HTTPException(status_code=400, detail="At least one condition is required")
    for c in conditions:
        if c.field not in ALLOWED_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid field: {c.field}. Allowed: {ALLOWED_FIELDS}")
        if c.operator not in ALLOWED_OPERATORS:
            raise HTTPException(status_code=400, detail=f"Invalid operator: {c.operator}. Allowed: {ALLOWED_OPERATORS}")
