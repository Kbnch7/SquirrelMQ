import time
from typing import Any

import asyncpg

from src.config import DATABASE_URL, MAX_DELIVERY_ATTEMPTS, VISIBILITY_TIMEOUT_SECONDS
from src.domain.models import ExchangeType, Message


class PostgresStorage:
    def __init__(self):
        self.pool = None
        self.dsn = DATABASE_URL

    async def connect(self):
        if not self.dsn:
            raise RuntimeError("DATABASE_URL is not configured")

        self.pool = await asyncpg.create_pool(self.dsn)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exchanges (
                    name TEXT PRIMARY KEY,
                    type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS queues (
                    name TEXT PRIMARY KEY,
                    created_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())
                );

                CREATE TABLE IF NOT EXISTS bindings (
                    exchange_name TEXT NOT NULL REFERENCES exchanges(name) ON DELETE CASCADE,
                    queue_name TEXT NOT NULL REFERENCES queues(name) ON DELETE CASCADE,
                    binding_key TEXT NOT NULL,
                    PRIMARY KEY (exchange_name, queue_name, binding_key)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    routing_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL
                );

                CREATE TABLE IF NOT EXISTS queue_messages (
                    queue_name TEXT NOT NULL REFERENCES queues(name) ON DELETE CASCADE,
                    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until DOUBLE PRECISION,
                    created_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),
                    delivered_at DOUBLE PRECISION,
                    last_error TEXT,
                    PRIMARY KEY (queue_name, message_id)
                );
                """
            )
            await self._migrate_legacy_schema(conn)
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_messages_delivery
                    ON queue_messages (queue_name, status, created_at);
                """
            )
            print("PostgreSQL подключен, таблицы проверены.")

    async def _migrate_legacy_schema(self, conn: asyncpg.Connection) -> None:
        columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'queue_messages'
            """
        )
        names = {row["column_name"] for row in columns}
        migrations = {
            "attempts": "ALTER TABLE queue_messages ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0",
            "locked_until": "ALTER TABLE queue_messages ADD COLUMN locked_until DOUBLE PRECISION",
            "created_at": "ALTER TABLE queue_messages ADD COLUMN created_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())",
            "delivered_at": "ALTER TABLE queue_messages ADD COLUMN delivered_at DOUBLE PRECISION",
            "last_error": "ALTER TABLE queue_messages ADD COLUMN last_error TEXT",
        }
        for column, sql in migrations.items():
            if column not in names:
                await conn.execute(sql)

    async def save_exchange(self, name: str, exchange_type: ExchangeType) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO exchanges (name, type)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type
                """,
                name,
                exchange_type.value,
            )

    async def save_queue(self, name: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO queues (name) VALUES ($1) ON CONFLICT DO NOTHING",
                name,
            )

    async def save_binding(self, exchange_name: str, queue_name: str, binding_key: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bindings (exchange_name, queue_name, binding_key)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                exchange_name,
                queue_name,
                binding_key,
            )

    async def load_topology(self) -> dict[str, list[dict[str, Any]]]:
        async with self.pool.acquire() as conn:
            exchanges = await conn.fetch("SELECT name, type FROM exchanges ORDER BY name")
            queues = await conn.fetch("SELECT name FROM queues ORDER BY name")
            bindings = await conn.fetch(
                """
                SELECT exchange_name, queue_name, binding_key
                FROM bindings
                ORDER BY exchange_name, queue_name, binding_key
                """
            )
            return {
                "exchanges": [dict(row) for row in exchanges],
                "queues": [dict(row) for row in queues],
                "bindings": [dict(row) for row in bindings],
            }

    async def save_message(self, message: Message) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (id, routing_key, payload, timestamp)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
                """,
                message.id,
                message.routing_key,
                message.payload,
                message.timestamp,
            )

    async def enqueue_message(self, queue_name: str, message_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO queue_messages (queue_name, message_id, status, created_at)
                VALUES ($1, $2, 'pending', $3)
                ON CONFLICT DO NOTHING
                """,
                queue_name,
                message_id,
                time.time(),
            )

    async def get_available_message_ids(self, queue_name: str, limit: int = 100) -> list[str]:
        await self.move_expired_to_dead_letter(queue_name)
        now = time.time()
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT message_id
                FROM queue_messages
                WHERE queue_name = $1
                  AND status IN ('pending', 'in_flight')
                  AND attempts < $2
                  AND (status = 'pending' OR locked_until <= $3)
                ORDER BY created_at ASC
                LIMIT $4
                """,
                queue_name,
                MAX_DELIVERY_ATTEMPTS,
                now,
                limit,
            )
            return [record["message_id"] for record in records]

    async def claim_message(self, queue_name: str, message_id: str) -> Message | None:
        now = time.time()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                record = await conn.fetchrow(
                    """
                    SELECT m.id, m.routing_key, m.payload, m.timestamp,
                           qm.status, qm.attempts, qm.locked_until
                    FROM queue_messages qm
                    JOIN messages m ON m.id = qm.message_id
                    WHERE qm.queue_name = $1 AND qm.message_id = $2
                    FOR UPDATE OF qm
                    """,
                    queue_name,
                    message_id,
                )
                if not record:
                    return None
                if record["status"] in {"delivered", "dead_letter"}:
                    return None
                if record["status"] == "in_flight" and record["locked_until"] and record["locked_until"] > now:
                    return None

                attempts = record["attempts"] + 1
                if attempts > MAX_DELIVERY_ATTEMPTS:
                    await conn.execute(
                        """
                        UPDATE queue_messages
                        SET status = 'dead_letter', last_error = $3
                        WHERE queue_name = $1 AND message_id = $2
                        """,
                        queue_name,
                        message_id,
                        "max delivery attempts exceeded",
                    )
                    return None

                await conn.execute(
                    """
                    UPDATE queue_messages
                    SET status = 'in_flight',
                        attempts = $3,
                        locked_until = $4
                    WHERE queue_name = $1 AND message_id = $2
                    """,
                    queue_name,
                    message_id,
                    attempts,
                    now + VISIBILITY_TIMEOUT_SECONDS,
                )

                return Message(
                    id=record["id"],
                    routing_key=record["routing_key"],
                    payload=record["payload"],
                    timestamp=record["timestamp"],
                )

    async def ack_message(self, queue_name: str, message_id: str) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE queue_messages
                SET status = 'delivered',
                    delivered_at = $3,
                    locked_until = NULL
                WHERE queue_name = $1
                  AND message_id = $2
                  AND status != 'dead_letter'
                """,
                queue_name,
                message_id,
                time.time(),
            )
            return result.endswith("1")

    async def get_delivery_state(self, queue_name: str, message_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT status, locked_until
                FROM queue_messages
                WHERE queue_name = $1 AND message_id = $2
                """,
                queue_name,
                message_id,
            )
            return dict(record) if record else None

    async def nack_message(self, queue_name: str, message_id: str, error: str = "") -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE queue_messages
                SET status = 'pending',
                    locked_until = NULL,
                    last_error = NULLIF($3, '')
                WHERE queue_name = $1
                  AND message_id = $2
                  AND status = 'in_flight'
                """,
                queue_name,
                message_id,
                error,
            )
            return result.endswith("1")

    async def move_expired_to_dead_letter(self, queue_name: str | None = None) -> int:
        now = time.time()
        query = """
            UPDATE queue_messages
            SET status = 'dead_letter',
                last_error = 'max delivery attempts exceeded'
            WHERE status = 'in_flight'
              AND attempts >= $1
              AND locked_until <= $2
        """
        params: list[Any] = [MAX_DELIVERY_ATTEMPTS, now]
        if queue_name:
            query += " AND queue_name = $3"
            params.append(queue_name)

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *params)
            return int(result.split()[-1])

    async def get_metrics(self) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT status, COUNT(*) AS count
                FROM queue_messages
                GROUP BY status
                """
            )
            metrics = {row["status"]: row["count"] for row in rows}
            metrics["messages_total"] = await conn.fetchval("SELECT COUNT(*) FROM messages")
            metrics["queues_total"] = await conn.fetchval("SELECT COUNT(*) FROM queues")
            metrics["exchanges_total"] = await conn.fetchval("SELECT COUNT(*) FROM exchanges")
            return metrics


pg_storage = PostgresStorage()
