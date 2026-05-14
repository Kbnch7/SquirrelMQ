import asyncio
import time

from src.domain.models import ExchangeType, Message
from src.domain.router import Router
from src.infrastructure.memory.storage import storage
from src.infrastructure.persistence.storage import pg_storage


class BrokerService:
    def __init__(self):
        self.storage = storage
        self.router = Router()

    async def initialize(self) -> None:
        topology = await pg_storage.load_topology()

        for exchange in topology["exchanges"]:
            self.storage.upsert_exchange(
                exchange["name"],
                ExchangeType(exchange["type"]),
            )
        for queue in topology["queues"]:
            self.storage.upsert_queue(queue["name"])
        for binding in topology["bindings"]:
            self.storage.add_binding(
                binding["exchange_name"],
                binding["queue_name"],
                binding["binding_key"],
            )

        for queue_name in self.storage.queue_names():
            await self._replenish_queue(queue_name)

    async def publish_message(self, exchange_name: str, routing_key: str, payload: str) -> tuple[bool, str]:
        exchange = self.storage.get_exchange(exchange_name)
        if not exchange:
            return False, ""

        target_queue_names = self.router.get_destination_queues(
            exchange,
            Message(payload=payload, routing_key=routing_key),
        )
        if not target_queue_names:
            return False, ""

        message = Message(payload=payload, routing_key=routing_key)
        await pg_storage.save_message(message)

        for queue_name in target_queue_names:
            await pg_storage.enqueue_message(queue_name, message.id)
            await self.storage.enqueue_id(queue_name, message.id)

        return True, message.id

    async def ack_message(self, queue_name: str, message_id: str) -> bool:
        return await pg_storage.ack_message(queue_name, message_id)

    async def nack_message(self, queue_name: str, message_id: str, error: str = "") -> bool:
        success = await pg_storage.nack_message(queue_name, message_id, error)
        if success:
            await self.storage.enqueue_id(queue_name, message_id)
        return success

    async def declare_exchange(self, name: str, etype_value: int) -> bool:
        etype = etype_value if isinstance(etype_value, ExchangeType) else list(ExchangeType)[etype_value]
        created = self.storage.create_exchange(name, etype)
        if not created:
            self.storage.upsert_exchange(name, etype)
        await pg_storage.save_exchange(name, etype)
        return created

    async def declare_queue(self, name: str) -> bool:
        created = self.storage.create_queue(name)
        await pg_storage.save_queue(name)
        return created

    async def bind_queue(self, exchange_name: str, queue_name: str, binding_key: str) -> bool:
        success = self.storage.add_binding(exchange_name, queue_name, binding_key)
        if success:
            await pg_storage.save_binding(exchange_name, queue_name, binding_key)
        return success

    async def consume_queue(self, queue_name: str):
        queue = self.storage.get_queue(queue_name)
        if not queue:
            raise ValueError("queue not found")

        await self._replenish_queue(queue_name)

        while True:
            try:
                message_id = await asyncio.wait_for(queue.get(), timeout=1)
                self.storage.mark_dequeued(queue_name, message_id)
            except asyncio.TimeoutError:
                await self._replenish_queue(queue_name)
                continue

            message = await pg_storage.claim_message(queue_name, message_id)
            if not message:
                continue

            yield message
            await self._wait_for_ack_or_timeout(queue_name, message.id)

    async def _replenish_queue(self, queue_name: str) -> None:
        available_ids = await pg_storage.get_available_message_ids(queue_name)
        for message_id in available_ids:
            await self.storage.enqueue_id(queue_name, message_id)

    async def _wait_for_ack_or_timeout(self, queue_name: str, message_id: str) -> None:
        while True:
            state = await pg_storage.get_delivery_state(queue_name, message_id)
            if not state or state["status"] != "in_flight":
                return
            if state["locked_until"] and state["locked_until"] <= time.time():
                return
            await asyncio.sleep(0.1)
