import asyncio

import grpc

from src.config import METRICS_HOST, METRICS_PORT
from src.infrastructure.persistence.storage import pg_storage
from src.interfaces.grpc import broker_pb2_grpc
from src.interfaces.grpc.handler import MessageBrokerHandler


async def handle_metrics(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        await reader.read(4096)
        metrics = await pg_storage.get_metrics()
        body = "\n".join(
            f"squirrelmq_{name} {value}"
            for name, value in sorted(metrics.items())
        ) + "\n"
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain; version=0.0.4\r\n"
            f"Content-Length: {len(body.encode())}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{body}"
        )
        writer.write(response.encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def serve():
    await pg_storage.connect()

    handler = MessageBrokerHandler()
    await handler.initialize()

    server = grpc.aio.server()
    broker_pb2_grpc.add_MessageBrokerServicer_to_server(handler, server)

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)

    metrics_server = await asyncio.start_server(
        handle_metrics,
        METRICS_HOST,
        METRICS_PORT,
    )

    print(f"SquirrelMQ gRPC started on {listen_addr}")
    print(f"SquirrelMQ metrics started on {METRICS_HOST}:{METRICS_PORT}")

    await server.start()
    async with metrics_server:
        await server.wait_for_termination()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nbroker stopped")
