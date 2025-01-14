import pika
import os

# RabbitMQ connection details from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')  # Default to 'localhost'
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE', 'one2n')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')  # Default to 'guest'
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'test@123')  # Default to 'guest'

# Callback function to process messages
def callback(ch, method, properties, body):
    print(f"[x] Received: {body.decode('utf-8')}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    try:
        # Establish connection
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        )
        channel = connection.channel()

        # Declare queue
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

        # Start consuming messages
        print(f"Waiting for messages from queue '{RABBITMQ_QUEUE}'. To exit, press CTRL+C")
        channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

        channel.start_consuming()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    main()
