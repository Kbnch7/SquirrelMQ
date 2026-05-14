import asyncio

from typing import Dict, List, Optional
from src.domain.interfaces import IStorage
from src.domain.models import Exchange, Message, Binding, ExchangeType

class MemoryStorage(IStorage):
    def __init__(self):
        self._exchanges: Dict[str, Exchange] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._queued_ids: Dict[str, set[str]] = {}
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

    def upsert_exchange(self, name: str, etype: ExchangeType) -> None:
        bindings = self._exchanges[name].bindings if name in self._exchanges else []
        self._exchanges[name] = Exchange(name=name, type=etype, bindings=bindings)

    def create_queue(self, name: str) -> bool:
        if name in self._queues:
            return False
        self._queues[name] = asyncio.Queue()
        self._queued_ids[name] = set()
        return True

    def upsert_queue(self, name: str) -> None:
        if name not in self._queues:
            self._queues[name] = asyncio.Queue()
            self._queued_ids[name] = set()

    def add_binding(self, exchange_name: str, queue_name: str, binding_key: str) -> bool:
        exchange = self.get_exchange(exchange_name)
        if not exchange or queue_name not in self._queues:
            return False

        for binding in exchange.bindings:
            if binding.queue_name == queue_name and binding.binding_key == binding_key:
                return True
        
        binding = Binding(queue_name=queue_name, binding_key=binding_key)
        exchange.bindings.append(binding)
        return True

    async def enqueue_id(self, queue_name: str, message_id: str) -> bool:
        if queue_name not in self._queues:
            return False
        if message_id in self._queued_ids[queue_name]:
            return False

        self._queued_ids[queue_name].add(message_id)
        await self._queues[queue_name].put(message_id)
        return True

    def mark_dequeued(self, queue_name: str, message_id: str) -> None:
        self._queued_ids.get(queue_name, set()).discard(message_id)

    def has_queued_id(self, queue_name: str, message_id: str) -> bool:
        return message_id in self._queued_ids.get(queue_name, set())

    def queue_names(self) -> list[str]:
        return list(self._queues.keys())
    
    def get_queues_by_exchange(self, exchange_name):
        return super().get_queues_by_exchange(exchange_name)

storage = MemoryStorage()
