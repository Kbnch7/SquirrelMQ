import asyncio

from typing import Dict, List, Optional
from src.domain.interfaces import IStorage
from src.domain.models import Exchange, Message, Binding, ExchangeType

class MemoryStorage(IStorage):
    def __init__(self):
        self._exchanges: Dict[str, Exchange] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._messages_log: List = []

    async def save_message(self, message: Message) -> None:
        self._messages_log.append(message)

    def get_exchange(self, name: str) -> Optional[Exchange]:
        return self._exchanges.get(name)

    def get_queue(self, name: str) -> Optional[asyncio.Queue]:
        return self._queues.get(name)

    def create_exchange(self, name: str, etype: ExchangeType) -> bool:
        if name in self._exchanges:
            return False
        self._exchanges[name] = Exchange(name=name, type=etype)
        return True

    def create_queue(self, name: str) -> bool:
        if name in self._queues:
            return False
        self._queues[name] = asyncio.Queue()
        return True

    def add_binding(self, exchange_name: str, queue_name: str, binding_key: str) -> bool:
        exchange = self.get_exchange(exchange_name)
        if not exchange or queue_name not in self._queues:
            return False
        
        binding = Binding(queue_name=queue_name, binding_key=binding_key)
        exchange.bindings.append(binding)
        return True
    
    def get_queues_by_exchange(self, exchange_name):
        return super().get_queues_by_exchange(exchange_name)

storage = MemoryStorage()
