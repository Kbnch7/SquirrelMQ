import grpc
import asyncio
from src.interfaces.grpc import broker_pb2, broker_pb2_grpc

class SquirrelClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.aio.insecure_channel(f'{host}:{port}')
        self.stub = broker_pb2_grpc.MessageBrokerStub(self.channel)

    async def declare_exchange(self, name: str, ex_type: int):
        req = broker_pb2.ExchangeRequest(name=name, type=ex_type)
        return await self.stub.DeclareExchange(req)

    async def declare_queue(self, name: str):
        req = broker_pb2.QueueRequest(name=name)
        return await self.stub.DeclareQueue(req)

    async def bind_queue(self, queue: str, exchange: str, routing_key: str):
        req = broker_pb2.BindRequest(queue_name=queue, exchange_name=exchange, binding_key=routing_key)
        return await self.stub.BindQueue(req)

    async def publish(self, exchange: str, routing_key: str, payload: str):
        req = broker_pb2.PublishRequest(exchange_name=exchange, routing_key=routing_key, payload=payload)
        return await self.stub.Publish(req)

    async def consume(self, queue_name: str, callback):
        req = broker_pb2.ConsumeRequest(queue_name=queue_name)
        async for message in self.stub.Consume(req):
            await callback(message)
            ack_req = broker_pb2.AckRequest(message_id=message.id, queue_name=queue_name)
            await self.stub.AckMessage(ack_req)

    async def close(self):
        await self.channel.close()