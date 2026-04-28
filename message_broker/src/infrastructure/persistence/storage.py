import asyncpg
import asyncio
from src.domain.models import Message
from src.config import DATABASE_URL

class PostgresStorage:
    def __init__(self):
        self.pool = None
        self.dsn = DATABASE_URL

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    routing_key TEXT,
                    payload TEXT,
                    timestamp FLOAT
                );
                CREATE TABLE IF NOT EXISTS queue_messages (
                    queue_name TEXT,
                    message_id TEXT REFERENCES messages(id),
                    status TEXT DEFAULT 'pending',
                    PRIMARY KEY (queue_name, message_id)
                );
            """)
            print("PostgreSQL подключен, таблицы проверены.")

    async def save_message(self, message: Message) -> None:
        if not self.pool: return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (id, routing_key, payload, timestamp) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                message.id, message.routing_key, message.payload, message.timestamp
            )

    async def enqueue_message(self, queue_name: str, message_id: str):
        if not self.pool: return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO queue_messages (queue_name, message_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                queue_name, message_id
            )

    async def ack_message(self, queue_name: str, message_id: str):
        if not self.pool: return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE queue_messages SET status = 'delivered' WHERE queue_name = $1 AND message_id = $2",
                queue_name, message_id
            )

    async def get_pending_messages(self, queue_name: str):
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT m.id, m.routing_key, m.payload, m.timestamp
                FROM messages m
                JOIN queue_messages qm ON m.id = qm.message_id
                WHERE qm.queue_name = $1 AND qm.status = 'pending'
            """, queue_name)
            
            from src.domain.models import Message
            return [
                Message(id=rec['id'], routing_key=rec['routing_key'], 
                        payload=rec['payload'], timestamp=rec['timestamp'])
                for rec in records
            ]

pg_storage = PostgresStorage()
