import pika
import time
import os

# RabbitMQ connection details from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')  # Default to 'localhost' if not set
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE', 'test_queue')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')  # Default to 'guest'
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')  # Default to 'guest'
MESSAGES_PER_SECOND = int(os.getenv('MESSAGES_PER_SECOND', '100'))

# Function to create a RabbitMQ connection and channel
def create_connection_and_channel():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    )
    channel = connection.channel()
    return connection, channel

# Function to declare a queue
def declare_queue(channel):
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

# Function to publish messages
def publish_messages(channel):
    message_count = 0
    while True:
        message = f"Message {message_count}"
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent messages
        )
        print(f"[x] Sent: {message}")
        message_count += 1
        time.sleep(1 / MESSAGES_PER_SECOND)  # Control message rate

# Main logic
if __name__ == "__main__":
    try:
        connection, channel = create_connection_and_channel()
        declare_queue(channel)
        print(f"Publishing messages to queue '{RABBITMQ_QUEUE}' at {MESSAGES_PER_SECOND} messages/second...")
        publish_messages(channel)
    except KeyboardInterrupt:
        print("\nGracefully stopping producer...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'connection' in locals():
            connection.close()
