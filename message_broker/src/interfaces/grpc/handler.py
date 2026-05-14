from google.protobuf.timestamp_pb2 import Timestamp

from src.application.services import BrokerService
from src.interfaces.grpc import broker_pb2, broker_pb2_grpc


class MessageBrokerHandler(broker_pb2_grpc.MessageBrokerServicer):
    def __init__(self):
        self.service = BrokerService()

    async def initialize(self) -> None:
        await self.service.initialize()

    async def DeclareExchange(self, request, context):
        try:
            created = await self.service.declare_exchange(request.name, request.type)
            return broker_pb2.ActionResponse(
                success=True,
                error_message="" if created else "exchange already existed; configuration was updated",
            )
        except Exception as exc:
            return broker_pb2.ActionResponse(success=False, error_message=str(exc))

    async def DeclareQueue(self, request, context):
        try:
            created = await self.service.declare_queue(request.name)
            return broker_pb2.ActionResponse(
                success=True,
                error_message="" if created else "queue already existed",
            )
        except Exception as exc:
            return broker_pb2.ActionResponse(success=False, error_message=str(exc))

    async def BindQueue(self, request, context):
        try:
            success = await self.service.bind_queue(
                request.exchange_name,
                request.queue_name,
                request.binding_key,
            )
            return broker_pb2.ActionResponse(
                success=success,
                error_message="" if success else "exchange or queue does not exist",
            )
        except Exception as exc:
            return broker_pb2.ActionResponse(success=False, error_message=str(exc))

    async def Publish(self, request, context):
        try:
            success, message_id = await self.service.publish_message(
                exchange_name=request.exchange_name,
                routing_key=request.routing_key,
                payload=request.payload,
            )
            return broker_pb2.PublishResponse(stored=success, message_id=message_id)
        except Exception:
            return broker_pb2.PublishResponse(stored=False, message_id="")

    async def Consume(self, request, context):
        print(f"consumer connected to {request.queue_name}")

        try:
            async for message in self.service.consume_queue(request.queue_name):
                timestamp = Timestamp()
                seconds = int(message.timestamp)
                timestamp.seconds = seconds
                timestamp.nanos = int((message.timestamp - seconds) * 1_000_000_000)

                yield broker_pb2.Message(
                    id=message.id,
                    payload=message.payload,
                    routing_key=message.routing_key,
                    timestamp=timestamp,
                )
        except Exception as exc:
            print(f"consumer error: {exc}")

    async def AckMessage(self, request, context):
        try:
            success = await self.service.ack_message(
                queue_name=request.queue_name,
                message_id=request.message_id,
            )
            return broker_pb2.ActionResponse(
                success=success,
                error_message="" if success else "message not found or already dead-lettered",
            )
        except Exception as exc:
            return broker_pb2.ActionResponse(success=False, error_message=str(exc))
