import asyncio
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sdk import ExchangeType, SquirrelClient
from message_broker.src.interfaces.grpc import broker_pb2


async def read_and_ack(client: SquirrelClient, queue_name: str, count: int) -> list[str]:
    stream = client.stub.Consume(broker_pb2.ConsumeRequest(queue_name=queue_name))
    messages = []

    try:
        for _ in range(count):
            message = await asyncio.wait_for(stream.read(), timeout=5)
            messages.append(message.payload)
            await client.ack(queue_name, message.id)
    finally:
        stream.cancel()

    return messages


async def main():
    suffix = uuid.uuid4().hex[:8]
    exchange = f"demo_pubsub_{suffix}"
    audit_queue = f"demo_audit_{suffix}"
    notifications_queue = f"demo_notifications_{suffix}"

    client = SquirrelClient()
    await client.connect()

    await client.declare_exchange(exchange, ExchangeType.FANOUT)
    await client.declare_queue(audit_queue)
    await client.declare_queue(notifications_queue)
    await client.bind_queue(audit_queue, exchange, "")
    await client.bind_queue(notifications_queue, exchange, "")

    for index in range(1, 4):
        message_id = await client.publish(exchange, "demo.event", f"событие-{index}")
        print(f"Опубликовал сообщение: {message_id}")

    audit_messages = await read_and_ack(client, audit_queue, 3)
    notification_messages = await read_and_ack(client, notifications_queue, 3)

    print(f"Очередь аудита получила: {audit_messages}")
    print(f"Очередь уведомлений получила: {notification_messages}")
    print("Вывод: FANOUT exchange разослал каждое сообщение в обе очереди.")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
