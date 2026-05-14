import asyncio
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sdk import ExchangeType, SquirrelClient
from message_broker.src.interfaces.grpc import broker_pb2


async def main():
    suffix = uuid.uuid4().hex[:8]
    exchange = f"demo_redelivery_{suffix}"
    queue = f"demo_redelivery_queue_{suffix}"

    client = SquirrelClient()
    await client.connect()

    await client.declare_exchange(exchange, ExchangeType.DIRECT)
    await client.declare_queue(queue)
    await client.bind_queue(queue, exchange, "demo.redelivery")

    message_id = await client.publish(exchange, "demo.redelivery", "сообщение-без-ack")
    print(f"Опубликовал сообщение: {message_id}")

    first_stream = client.stub.Consume(broker_pb2.ConsumeRequest(queue_name=queue))
    first_message = await asyncio.wait_for(first_stream.read(), timeout=5)
    print(f"Получил без ACK: {first_message.id} {first_message.payload}")
    first_stream.cancel()

    print("Жду visibility timeout. После него broker должен вернуть сообщение в доставку...")
    await asyncio.sleep(11)

    second_stream = client.stub.Consume(broker_pb2.ConsumeRequest(queue_name=queue))
    second_message = await asyncio.wait_for(second_stream.read(), timeout=5)
    print(f"Получил повторно после timeout: {second_message.id} {second_message.payload}")

    if second_message.id != first_message.id:
        raise RuntimeError("Ошибка: ожидалось повторное получение того же самого сообщения.")

    await client.ack(queue, second_message.id)
    print("OK: неподтверждённое сообщение вернулось в очередь, после этого я отправил ACK.")

    second_stream.cancel()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
