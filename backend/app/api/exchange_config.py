from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.exchange_config import ExchangeConfig
from app.auth.dependencies import require_admin

router = APIRouter()


class ExchangeConfigCreate(BaseModel):
    exchange_name: str
    api_key: str = ""
    api_secret: str = ""
    is_active: bool = True


class ExchangeConfigOut(BaseModel):
    id: int
    exchange_name: str
    api_key: str
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ExchangeConfigOut])
async def list_configs(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExchangeConfig))
    return result.scalars().all()


@router.post("/", response_model=ExchangeConfigOut, status_code=status.HTTP_201_CREATED)
async def create_config(
    req: ExchangeConfigCreate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    config = ExchangeConfig(**req.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/{config_id}", response_model=ExchangeConfigOut)
async def update_config(
    config_id: int,
    req: ExchangeConfigCreate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExchangeConfig).where(ExchangeConfig.id == config_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    for key, value in req.model_dump().items():
        setattr(config, key, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExchangeConfig).where(ExchangeConfig.id == config_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    await db.delete(config)
    await db.commit()
