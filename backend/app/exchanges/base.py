from abc import ABC, abstractmethod
from typing import AsyncIterator, Union

from app.models.market import UnifiedOrderBook, UnifiedTrade


MarketMessage = Union[UnifiedOrderBook, UnifiedTrade]


class BaseExchangeClient(ABC):
    def __init__(self, name: str):
        self.name = name
        self._connected = False
        self._subscriptions: list[dict] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        """Connect, subscribe, and yield unified messages."""
        yield  # type: ignore

    @abstractmethod
    async def _send_subscriptions(self, ws) -> None:
        """Send subscription commands to the exchange WS after connect/reconnect."""
        ...

    @abstractmethod
    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        ...

    @abstractmethod
    def parse_trade(self, raw: dict) -> UnifiedTrade:
        ...
