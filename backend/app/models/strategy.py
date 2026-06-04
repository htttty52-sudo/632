from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func

from app.db.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    conditions = Column(Text, nullable=False)  # JSON DSL
    active = Column(Boolean, default=True, nullable=False)
    simulated_balance = Column(Float, default=10000.0, nullable=False)
    initial_balance = Column(Float, default=10000.0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StrategyLog(Base):
    __tablename__ = "strategy_logs"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    triggered_at = Column(DateTime, server_default=func.now())
    symbol = Column(String(20), nullable=False)
    exchange_a = Column(String(20), nullable=False)
    exchange_b = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    spread_pct = Column(Float, nullable=False)
    simulated_quantity = Column(Float, nullable=False)
    simulated_pnl = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    condition_snapshot = Column(Text, nullable=False)  # JSON of evaluated values
