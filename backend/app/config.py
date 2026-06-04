from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ARB_")

    database_url: str = "sqlite+aiosqlite:///./arbitrage.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    okx_ws_url: str = "wss://ws.okx.com:8443/ws/v5/public"
    huobi_ws_url: str = "wss://api.huobi.pro/ws"

    symbols: list[str] = ["BTC/USDT"]
    depth_levels: int = 20

    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    reconnect_factor: float = 2.0

    dedup_ttl_seconds: float = 5.0
    dedup_max_size: int = 10000

    stale_threshold_ms: float = 5000.0
    clock_alpha: float = 0.1
    spread_broadcast_interval_ms: float = 500.0
    spread_alert_threshold_pct: float = 0.1
    spread_alert_cooldown_seconds: float = 30.0

    use_mock: bool = False


settings = Settings()
