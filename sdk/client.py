import inspect
import asyncio
from enum import IntEnum

import grpc

from message_broker.src.interfaces.grpc import broker_pb2, broker_pb2_grpc


class ExchangeType(IntEnum):
    DIRECT = broker_pb2.DIRECT
    FANOUT = broker_pb2.FANOUT
    TOPIC = broker_pb2.TOPIC


class SquirrelMQError(RuntimeError):
    pass


class SquirrelClient:
    def __init__(self, host: str = "localhost", port: int = 50051):
        self.channel = grpc.aio.insecure_channel(f"{host}:{port}")
        self.stub = broker_pb2_grpc.MessageBrokerStub(self.channel)

    async def connect(self, timeout: float = 5) -> None:
        try:
            await asyncio.wait_for(self.channel.channel_ready(), timeout=timeout)
        except grpc.RpcError as exc:
            raise SquirrelMQError(f"failed to connect to broker: {exc}") from exc

    async def declare_exchange(self, name: str, ex_type: int | ExchangeType):
        req = broker_pb2.ExchangeRequest(name=name, type=int(ex_type))
        return await self._checked(self.stub.DeclareExchange(req))

    async def declare_queue(self, name: str):
        req = broker_pb2.QueueRequest(name=name)
        return await self._checked(self.stub.DeclareQueue(req))

    async def bind_queue(self, queue: str, exchange: str, routing_key: str):
        req = broker_pb2.BindRequest(
            queue_name=queue,
            exchange_name=exchange,
            binding_key=routing_key,
        )
        return await self._checked(self.stub.BindQueue(req))

    async def publish(self, exchange: str, routing_key: str, payload: str) -> str:
        req = broker_pb2.PublishRequest(
            exchange_name=exchange,
            routing_key=routing_key,
            payload=payload,
        )
        response = await self.stub.Publish(req)
        if not response.stored:
            raise SquirrelMQError("message was not routed to any queue")
        return response.message_id

    async def ack(self, queue_name: str, message_id: str):
        req = broker_pb2.AckRequest(message_id=message_id, queue_name=queue_name)
        return await self._checked(self.stub.AckMessage(req))

    async def consume(self, queue_name: str, callback, auto_ack: bool = True):
        req = broker_pb2.ConsumeRequest(queue_name=queue_name)
        async for message in self.stub.Consume(req):
            result = callback(message)
            if inspect.isawaitable(result):
                await result
            if auto_ack:
                await self.ack(queue_name, message.id)

    async def close(self):
        await self.channel.close()

    async def _checked(self, awaitable):
        response = await awaitable
        if not response.success:
            raise SquirrelMQError(response.error_message)
        return response
