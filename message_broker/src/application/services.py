from src.infrastructure.memory.storage import storage
from src.domain.router import Router
from src.domain.models import Message, ExchangeType

class BrokerService:
    def __init__(self):
        self.storage = storage
        self.router = Router()

    async def publish_message(self, exchange_name: str, routing_key: str, payload: bytes):
        message = Message(payload=payload, routing_key=routing_key)
        await self.storage.save_message(message)

        exchange = self.storage.get_exchange(exchange_name)
        if not exchange:
            print(f"exchange {exchange_name} не найден")
            return False

        target_queue_names = self.router.get_destination_queues(exchange, message)
        for q_name in target_queue_names:
            queue = self.storage.get_queue(q_name)
            if queue:
                await queue.put(message)
                print(f"сообщение доставлено в очередь: {q_name}")
        
        return True

    def declare_exchange(self, name: str, etype_value: int):
        etype = list(ExchangeType)[etype_value]
        return self.storage.create_exchange(name, etype)

    def declare_queue(self, name: str):
        return self.storage.create_queue(name)

    def bind_queue(self, ex_name: str, q_name: str, key: str):
        return self.storage.add_binding(ex_name, q_name, key)

    async def consume_queue(self, queue_name: str):
        queue = self.storage.get_queue(queue_name)
        if not queue:
            raise ValueError("queue not found")

        while True:
            message = await queue.get()
            yield message
