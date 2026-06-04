import logging
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.config import settings

logger = logging.getLogger(__name__)

_client: InfluxDBClientAsync | None = None


async def get_influx_client() -> InfluxDBClientAsync | None:
    global _client
    if not settings.influxdb_enabled:
        return None
    if _client is None:
        _client = InfluxDBClientAsync(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
    return _client


async def close_influx_client():
    global _client
    if _client:
        await _client.close()
        _client = None
        logger.info("InfluxDB client closed")
