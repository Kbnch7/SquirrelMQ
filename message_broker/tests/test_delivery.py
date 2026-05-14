import unittest

import src.application.services as services
from src.application.services import BrokerService
from src.domain.models import ExchangeType, Message
from src.infrastructure.memory.storage import MemoryStorage


class FakePostgresStorage:
    def __init__(self):
        self.messages = {}
        self.queue_messages = {}
        self.exchanges = {}
        self.queues = set()
        self.bindings = set()

    async def load_topology(self):
        return {"exchanges": [], "queues": [], "bindings": []}

    async def save_exchange(self, name, exchange_type):
        self.exchanges[name] = exchange_type

    async def save_queue(self, name):
        self.queues.add(name)

    async def save_binding(self, exchange_name, queue_name, binding_key):
        self.bindings.add((exchange_name, queue_name, binding_key))

    async def save_message(self, message: Message):
        self.messages[message.id] = message

    async def enqueue_message(self, queue_name, message_id):
        self.queue_messages[(queue_name, message_id)] = "pending"

    async def get_available_message_ids(self, queue_name, limit=100):
        return [
            message_id
            for (stored_queue, message_id), status in self.queue_messages.items()
            if stored_queue == queue_name and status == "pending"
        ]

    async def claim_message(self, queue_name, message_id):
        key = (queue_name, message_id)
        if self.queue_messages.get(key) != "pending":
            return None
        self.queue_messages[key] = "in_flight"
        return self.messages[message_id]

    async def ack_message(self, queue_name, message_id):
        key = (queue_name, message_id)
        if key not in self.queue_messages:
            return False
        self.queue_messages[key] = "delivered"
        return True

    async def get_delivery_state(self, queue_name, message_id):
        key = (queue_name, message_id)
        status = self.queue_messages.get(key)
        return {"status": status, "locked_until": None} if status else None

    async def nack_message(self, queue_name, message_id, error=""):
        key = (queue_name, message_id)
        if self.queue_messages.get(key) != "in_flight":
            return False
        self.queue_messages[key] = "pending"
        return True


class DeliveryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_pg = services.pg_storage
        self.fake_pg = FakePostgresStorage()
        services.pg_storage = self.fake_pg
        self.service = BrokerService()
        self.service.storage = MemoryStorage()

        await self.service.declare_exchange("events", ExchangeType.FANOUT)
        await self.service.declare_queue("audit")
        await self.service.bind_queue("events", "audit", "")

    async def asyncTearDown(self):
        services.pg_storage = self.original_pg

    async def test_acknowledged_message_is_not_delivered_again(self):
        stored, message_id = await self.service.publish_message("events", "user.created", "payload")
        self.assertTrue(stored)

        stream = self.service.consume_queue("audit")
        first_message = await stream.__anext__()
        self.assertEqual(first_message.id, message_id)

        await self.service.ack_message("audit", message_id)
        await self.service._replenish_queue("audit")

        self.assertTrue(self.service.storage.get_queue("audit").empty())
        self.assertEqual(self.fake_pg.queue_messages[("audit", message_id)], "delivered")

    async def test_nack_makes_message_available_again(self):
        stored, message_id = await self.service.publish_message("events", "user.created", "payload")
        self.assertTrue(stored)

        stream = self.service.consume_queue("audit")
        first_message = await stream.__anext__()
        self.assertEqual(first_message.id, message_id)

        await self.service.nack_message("audit", message_id, "handler failed")
        second_message = await stream.__anext__()

        self.assertEqual(second_message.id, message_id)


if __name__ == "__main__":
    unittest.main()
