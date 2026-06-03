from abc import ABC, abstractmethod
from typing import AsyncIterator, Union

from app.models.market import UnifiedOrderBook, UnifiedTrade


MarketMessage = Union[UnifiedOrderBook, UnifiedTrade]


class BaseExchangeClient(ABC):
    def __init__(self, name: str):
        self.name = name
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect_and_stream(self) -> AsyncIterator[MarketMessage]:
        yield  # type: ignore

    @abstractmethod
    def parse_depth(self, raw: dict) -> UnifiedOrderBook:
        ...

    @abstractmethod
    def parse_trade(self, raw: dict) -> UnifiedTrade:
        ...
