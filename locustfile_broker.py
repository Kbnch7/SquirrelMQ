from locust import User, task
import pika
import time, os
from dotenv import load_dotenv
from utils import get_payload

class RabbitMQClient:
    def __init__(self, queue):
        self.connection = pika.BlockingConnection(pika.URLParameters(os.getenv("BROKER_URL")))
        self.channel = self.connection.channel()
        self.queue = queue

    def publish(self, message):
        self.channel.basic_publish(exchange='', routing_key=self.queue, body=message)

class MQUser(User):
    wait_time = lambda _: 0.1

    def on_start(self):
        load_dotenv()
        self.client = RabbitMQClient("tasks")

    @task
    def send_message(self):
        payload = get_payload(1024 * 100)
        start_time = time.time()
        
        try:
            self.client.publish(payload)
            total_time = int((time.time() - start_time) * 1000)
            
            self.environment.events.request.fire(
                request_type="MQ",
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
