from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base


class ExchangeConfig(Base):
    __tablename__ = "exchange_configs"

    id = Column(Integer, primary_key=True, index=True)
    exchange_name = Column(String(50), nullable=False)
    api_key = Column(String(256), nullable=False, default="")
    api_secret = Column(String(256), nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
