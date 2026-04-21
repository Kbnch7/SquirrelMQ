import pika
import time, os
from dotenv import load_dotenv

def rabbit_callback(ch, method, properties, body):
    global count, start_time
    count += 1
    if count % 1000 == 0:
        elapsed = time.time() - start_time
        print(f"Processed {count} messages... (~{int(count/elapsed)} msg/s)")

def rabbit_consumer():
    global count, start_time
    count = 0
    start_time = time.time()
    load_dotenv()
    connection = pika.BlockingConnection(pika.URLParameters(os.getenv("BROKER_URL")))
    channel = connection.channel()

    queue_name = 'tasks'
    channel.queue_declare(queue=queue_name)

    print(f"[*] RabbitMQ Consumer запущен. Ожидание сообщений в '{queue_name}'...")

    channel.basic_consume(queue=queue_name, on_message_callback=rabbit_callback, auto_ack=True)
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    rabbit_consumer()