import asyncio
import grpc
from src.interfaces.grpc import broker_pb2_grpc
from src.interfaces.grpc.handler import MessageBrokerHandler
from src.infrastructure.persistence.storage import pg_storage

async def serve():
    server = grpc.aio.server()
    
    broker_pb2_grpc.add_MessageBrokerServicer_to_server(
        MessageBrokerHandler(), server
    )
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    print(f"SquirrelMQ запущен на {listen_addr}")

    await pg_storage.connect()
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nброкер остановлен")