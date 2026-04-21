import redis
import time, os
from dotenv import load_dotenv

def redis_consumer():
    load_dotenv()
    r = redis.from_url(os.getenv("REDIS_URL"))
    queue_name = "tasks"
    
    print(f"[*] Redis Consumer запущен. Ожидание сообщений в '{queue_name}'...")
    
    count = 0
    start_time = time.time()

    try:
        while True:
            msg = r.brpop(queue_name, timeout=5)
            if msg:
                count += 1
                if count % 1000 == 0:
                    elapsed = time.time() - start_time
                    print("RPS", count / elapsed)
    except KeyboardInterrupt:
        print("\nОстановка...")

if __name__ == "__main__":
    redis_consumer()