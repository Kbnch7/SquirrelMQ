import json
import os
import random
import time

import psycopg2
import redis


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "15432"))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "16379"))

DB_NAME = "cache_demo"
DB_USER = "cache_user"
DB_PASSWORD = "cache_password"

ITEMS = int(os.getenv("ITEMS", "100"))
REQUESTS = int(os.getenv("REQUESTS", "1000"))
FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "500"))

CASES = [
    ("lazy", "read-heavy", 0.8),
    ("lazy", "balanced", 0.5),
    ("lazy", "write-heavy", 0.2),
    ("write-through", "read-heavy", 0.8),
    ("write-through", "balanced", 0.5),
    ("write-through", "write-heavy", 0.2),
    ("write-back", "read-heavy", 0.8),
    ("write-back", "balanced", 0.5),
    ("write-back", "write-heavy", 0.2),
]


metrics = {}
dirty = {}


def connect_db():
    for _ in range(30):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError:
            time.sleep(1)
    raise RuntimeError("Postgres is not ready")


def connect_cache():
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    for _ in range(30):
        try:
            client.ping()
            return client
        except redis.exceptions.RedisError:
            time.sleep(1)
    raise RuntimeError("Redis is not ready")


def reset_metrics():
    global metrics, dirty
    metrics = {"hits": 0, "misses": 0, "db_reads": 0, "db_writes": 0, "flushes": 0}
    dirty = {}


def prepare_db(conn, cache):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute("TRUNCATE TABLE items")
        for item_id in range(1, ITEMS + 1):
            cur.execute("INSERT INTO items VALUES (%s, %s)", (item_id, f"value-{item_id}"))
    cache.flushdb()
    reset_metrics()


def cache_key(item_id):
    return f"item:{item_id}"


def db_read(conn, item_id):
    metrics["db_reads"] += 1
    with conn.cursor() as cur:
        cur.execute("SELECT id, value FROM items WHERE id = %s", (item_id,))
        row = cur.fetchone()
    return {"id": row[0], "value": row[1]}


def db_write(conn, item_id, value):
    metrics["db_writes"] += 1
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO items VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value
            """,
            (item_id, value),
        )


def read_item(conn, cache, item_id):
    cached = cache.get(cache_key(item_id))
    if cached:
        metrics["hits"] += 1
        return json.loads(cached)

    metrics["misses"] += 1
    item = db_read(conn, item_id)
    cache.set(cache_key(item_id), json.dumps(item))
    return item


def write_item(conn, cache, strategy, item_id, value):
    item = {"id": item_id, "value": value}

    if strategy == "lazy":
        db_write(conn, item_id, value)
        cache.delete(cache_key(item_id))
    elif strategy == "write-through":
        db_write(conn, item_id, value)
        cache.set(cache_key(item_id), json.dumps(item))
    elif strategy == "write-back":
        cache.set(cache_key(item_id), json.dumps(item))
        dirty[item_id] = value


def flush_write_back(conn):
    if not dirty:
        return 0
    count = len(dirty)
    for item_id, value in list(dirty.items()):
        db_write(conn, item_id, value)
    dirty.clear()
    metrics["flushes"] += 1
    return count


def make_actions(read_ratio):
    reads = int(REQUESTS * read_ratio)
    actions = ["read"] * reads + ["write"] * (REQUESTS - reads)
    random.shuffle(actions)
    return actions


def run_case(conn, cache, strategy, profile, read_ratio):
    prepare_db(conn, cache)
    actions = make_actions(read_ratio)
    times = []
    started = time.time()

    for i, action in enumerate(actions, start=1):
        item_id = random.randint(1, ITEMS)
        before = time.time()

        if action == "read":
            read_item(conn, cache, item_id)
        else:
            write_item(conn, cache, strategy, item_id, f"value-{i}")

        if strategy == "write-back" and i % FLUSH_EVERY == 0:
            flush_write_back(conn)

        times.append((time.time() - before) * 1000)

    buffer_before_flush = len(dirty)
    flush_write_back(conn)
    total_time = time.time() - started
    cache_reads = metrics["hits"] + metrics["misses"]
    hit_rate = metrics["hits"] / cache_reads if cache_reads else 0

    return {
        "strategy": strategy,
        "profile": profile,
        "rps": REQUESTS / total_time,
        "avg_ms": sum(times) / len(times),
        "db_reads": metrics["db_reads"],
        "db_writes": metrics["db_writes"],
        "hit_rate": hit_rate,
        "buffer": buffer_before_flush,
    }


def print_table(rows):
    print("\nRESULTS")
    print("-" * 107)
    print(
        f"{'strategy':<14} {'profile':<12} {'req/sec':>8} {'avg ms':>8} "
        f"{'db reads':>9} {'db writes':>10} {'hit rate':>9} {'wb buffer':>10}"
    )
    print("-" * 107)
    for row in rows:
        print(
            f"{row['strategy']:<14} {row['profile']:<12} "
            f"{row['rps']:>8.2f} {row['avg_ms']:>8.2f} "
            f"{row['db_reads']:>9} {row['db_writes']:>10} "
            f"{row['hit_rate']:>9.2%} {row['buffer']:>10}"
        )
    print("-" * 107)


def main():
    random.seed(1)
    conn = connect_db()
    cache = connect_cache()

    rows = []
    for case in CASES:
        print(f"running: {case[0]} / {case[1]}")
        rows.append(run_case(conn, cache, *case))

    print_table(rows)


if __name__ == "__main__":
    main()
