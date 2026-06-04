import logging
from datetime import datetime

import pandas as pd

from app.config import settings
from app.influxdb.client import get_influx_client

logger = logging.getLogger(__name__)


async def query_spread_data(
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    start_time: datetime,
    end_time: datetime,
) -> pd.DataFrame:
    """Query spread snapshots from InfluxDB, returns DataFrame with columns:
    timestamp, spread_pct, best_spread, mid_price, direction
    """
    client = await get_influx_client()
    if not client:
        return pd.DataFrame()

    query = f'''
    from(bucket: "{settings.influxdb_bucket}")
        |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
        |> filter(fn: (r) => r._measurement == "spread_snapshot")
        |> filter(fn: (r) => r.symbol == "{symbol}")
        |> filter(fn: (r) => r.exchange_a == "{exchange_a}" and r.exchange_b == "{exchange_b}")
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"])
    '''

    try:
        query_api = client.query_api()
        tables = await query_api.query(query, org=settings.influxdb_org)

        records = []
        for table in tables:
            for record in table.records:
                records.append({
                    "timestamp": record.get_time(),
                    "spread_pct": record.values.get("spread_pct", 0.0),
                    "best_spread": record.values.get("best_spread", 0.0),
                    "mid_price": record.values.get("mid_price", 0.0),
                    "direction": record.values.get("direction", ""),
                })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp").reset_index(drop=True)

    except Exception as e:
        logger.error(f"InfluxDB query failed: {e}")
        return pd.DataFrame()


async def query_orderbook_depth(
    symbol: str,
    exchange: str,
    start_time: datetime,
    end_time: datetime,
) -> pd.DataFrame:
    """Query orderbook depth snapshots from InfluxDB."""
    client = await get_influx_client()
    if not client:
        return pd.DataFrame()

    query = f'''
    from(bucket: "{settings.influxdb_bucket}")
        |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
        |> filter(fn: (r) => r._measurement == "orderbook_snapshot")
        |> filter(fn: (r) => r.symbol == "{symbol}" and r.exchange == "{exchange}")
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"])
    '''

    try:
        query_api = client.query_api()
        tables = await query_api.query(query, org=settings.influxdb_org)

        records = []
        for table in tables:
            for record in table.records:
                row = {"timestamp": record.get_time()}
                for key, val in record.values.items():
                    if key.startswith(("bid_", "ask_", "best_", "mid_")):
                        row[key] = val
                records.append(row)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp").reset_index(drop=True)

    except Exception as e:
        logger.error(f"InfluxDB orderbook query failed: {e}")
        return pd.DataFrame()


async def query_available_ranges() -> list[dict]:
    """Query the available time ranges of data in InfluxDB."""
    client = await get_influx_client()
    if not client:
        return []

    query = f'''
    from(bucket: "{settings.influxdb_bucket}")
        |> range(start: -90d)
        |> filter(fn: (r) => r._measurement == "spread_snapshot")
        |> group(columns: ["symbol", "exchange_a", "exchange_b"])
        |> first()
    '''

    query_last = f'''
    from(bucket: "{settings.influxdb_bucket}")
        |> range(start: -90d)
        |> filter(fn: (r) => r._measurement == "spread_snapshot")
        |> group(columns: ["symbol", "exchange_a", "exchange_b"])
        |> last()
    '''

    try:
        query_api = client.query_api()
        first_tables = await query_api.query(query, org=settings.influxdb_org)
        last_tables = await query_api.query(query_last, org=settings.influxdb_org)

        ranges = {}
        for table in first_tables:
            for record in table.records:
                key = f"{record.values.get('symbol')}:{record.values.get('exchange_a')}:{record.values.get('exchange_b')}"
                ranges[key] = {
                    "symbol": record.values.get("symbol"),
                    "exchange_a": record.values.get("exchange_a"),
                    "exchange_b": record.values.get("exchange_b"),
                    "start_time": record.get_time().isoformat(),
                }

        for table in last_tables:
            for record in table.records:
                key = f"{record.values.get('symbol')}:{record.values.get('exchange_a')}:{record.values.get('exchange_b')}"
                if key in ranges:
                    ranges[key]["end_time"] = record.get_time().isoformat()

        return list(ranges.values())

    except Exception as e:
        logger.error(f"InfluxDB range query failed: {e}")
        return []
