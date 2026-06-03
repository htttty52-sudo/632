from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ARB_")

    database_url: str = "sqlite+aiosqlite:///./arbitrage.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    okx_ws_url: str = "wss://ws.okx.com:8443/ws/v5/public"

    symbols: list[str] = ["BTC/USDT"]
    depth_levels: int = 20

    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    reconnect_factor: float = 2.0

    dedup_ttl_seconds: float = 5.0
    dedup_max_size: int = 10000

    use_mock: bool = False


settings = Settings()
