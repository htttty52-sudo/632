from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
import app.models  # noqa: F401 - ensure all models are registered with Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.exchanges.manager import exchange_manager
    from app.arbitrage.spread_engine import SpreadEngine
    from app.strategy.engine import StrategyEngine, strategy_engine as _se_placeholder
    from app.influxdb.writer import influx_writer
    from app.influxdb.client import close_influx_client
    import app.strategy.engine as strategy_module

    spread_engine = SpreadEngine(exchange_manager.price_table)
    _strategy_engine = StrategyEngine(exchange_manager.price_table)
    strategy_module.strategy_engine = _strategy_engine

    await influx_writer.start()
    await exchange_manager.start()
    await spread_engine.start()
    await _strategy_engine.start()
    yield
    await _strategy_engine.stop()
    await spread_engine.stop()
    await exchange_manager.stop()
    await influx_writer.stop()
    await close_influx_client()


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
from app.api.strategy import router as strategy_router
from app.api.backtest import router as backtest_router
from app.ws.router import router as ws_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(config_router, prefix="/api/exchange-configs", tags=["config"])
app.include_router(strategy_router, prefix="/api/strategies", tags=["strategies"])
app.include_router(backtest_router, prefix="/api/backtest", tags=["backtest"])
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    from app.ws.broadcast import connection_manager
    return {"status": "ok", "ws_connections": connection_manager.client_count}

