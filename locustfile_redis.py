from locust import User, task
import time, os
from dotenv import load_dotenv
import redis
from utils import get_payload

class RedisClient:
    def __init__(self, queue_name):
        self.client = redis.from_url(os.getenv("REDIS_URL"))
        self.queue_name = queue_name

    def publish(self, message):
        return self.client.lpush(self.queue_name, message)

    def close(self):
        self.client.close()


class RedisUser(User):
    wait_time = lambda _: 0.5

    def on_start(self):
        load_dotenv()
        self.client = RedisClient("tasks")

    @task
    def send_message(self):
        payload = get_payload(1024 * 100)
        start_time = time.time()
        
        try:
            self.client.publish(payload)
            total_time = int((time.time() - start_time) * 1000)
            
            self.environment.events.request.fire(
                request_type="Redis",
                name="Publish",
                response_time=total_time,
                response_length=len(payload),
                exception=None
            )
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            
            self.environment.events.request.fire(
                request_type="MQ",
                name="Publish",
                response_time=total_time,
                response_length=0,
                exception=e 
            )

    def on_stop(self):
        self.client.connection.close()
