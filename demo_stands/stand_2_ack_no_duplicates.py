import asyncio
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sdk import ExchangeType, SquirrelClient
from message_broker.src.interfaces.grpc import broker_pb2


async def main():
    suffix = uuid.uuid4().hex[:8]
    exchange = f"demo_ack_{suffix}"
    queue = f"demo_ack_queue_{suffix}"

    client = SquirrelClient()
    await client.connect()

    await client.declare_exchange(exchange, ExchangeType.DIRECT)
    await client.declare_queue(queue)
    await client.bind_queue(queue, exchange, "demo.ack")

    message_id = await client.publish(exchange, "demo.ack", "сообщение-которое-не-должно-повториться")
    print(f"Опубликовал сообщение: {message_id}")

    first_stream = client.stub.Consume(broker_pb2.ConsumeRequest(queue_name=queue))
    first_message = await asyncio.wait_for(first_stream.read(), timeout=5)
    print(f"Получил первый раз: {first_message.id} {first_message.payload}")
    await client.ack(queue, first_message.id)
    print("Отправил ACK. Теперь broker должен считать сообщение прочитанным.")
    first_stream.cancel()

    second_stream = client.stub.Consume(broker_pb2.ConsumeRequest(queue_name=queue))
    try:
        repeated_message = await asyncio.wait_for(second_stream.read(), timeout=3)
    except asyncio.TimeoutError:
        print("OK: после ACK сообщение повторно не выдалось.")
    else:
        raise RuntimeError(f"Ошибка: сообщение повторилось после ACK: {repeated_message.id}")
    finally:
        second_stream.cancel()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
