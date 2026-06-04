from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime

from app.db.database import Base


class SpreadAlert(Base):
    __tablename__ = "spread_alerts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)
    exchange_a = Column(String(50), nullable=False)
    exchange_b = Column(String(50), nullable=False)
    spread_pct = Column(Float, nullable=False)
    threshold_pct = Column(Float, nullable=False)
    direction = Column(String(10), nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
