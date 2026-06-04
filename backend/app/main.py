from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.exchanges.manager import exchange_manager
    from app.arbitrage.spread_engine import SpreadEngine
    spread_engine = SpreadEngine(exchange_manager.price_table)
    await exchange_manager.start()
    await spread_engine.start()
    yield
    await spread_engine.stop()
    await exchange_manager.stop()


app = FastAPI(title="Crypto Arbitrage Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.auth.router import router as auth_router
from app.api.exchange_config import router as config_router
from app.ws.router import router as ws_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(config_router, prefix="/api/exchange-configs", tags=["config"])
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
