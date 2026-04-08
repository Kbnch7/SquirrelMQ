from src.interfaces.grpc import broker_pb2, broker_pb2_grpc
from src.application.services import BrokerService

class MessageBrokerHandler(broker_pb2_grpc.MessageBrokerServicer):
    def __init__(self):
        self.service = BrokerService()

    async def DeclareExchange(self, request, context):
        success = self.service.declare_exchange(request.name, request.type)
        return broker_pb2.ActionResponse(
            success=success, 
            error_message="" if success else "exchange already exists"
        )

    async def DeclareQueue(self, request, context):
        success = self.service.declare_queue(request.name)
        return broker_pb2.ActionResponse(
            success=success, 
            error_message="" if success else "queue already exists"
        )

    async def BindQueue(self, request, context):
        success = self.service.bind_queue(
            request.exchange_name, 
            request.queue_name, 
            request.binding_key
        )
        return broker_pb2.ActionResponse(
            success=success, 
            error_message="" if success else "binding failed"
        )

    async def Publish(self, request, context):
        success = await self.service.publish_message(
            exchange_name=request.exchange_name,
            routing_key=request.routing_key,
            payload=request.payload
        )
        return broker_pb2.PublishResponse(stored=success, message_id="generated-id")

    async def Consume(self, request, context):
        print(f"консьюмер подключился к {request.queue_name}")
        
        try:
            async for message in self.service.consume_queue(request.queue_name):
                yield broker_pb2.Message(
                    id=message.id,
                    payload=message.payload,
                    routing_key=message.routing_key
                )
        except Exception as e:
            print(f"ошибка консьюмера: {e}")
