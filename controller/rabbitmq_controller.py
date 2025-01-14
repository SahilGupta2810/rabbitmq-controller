import os
import time
import logging
from kubernetes import client, config
import pika

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

# Load Kubernetes configuration (assumes running in-cluster)
config.load_incluster_config()

# Kubernetes API clients
apps_v1 = client.AppsV1Api()


def get_queue_length(rabbitmq_host, rabbitmq_user, rabbitmq_password, queue_name):
    """
    Connect to RabbitMQ and retrieve the queue length.

    Args:
        rabbitmq_host (str): RabbitMQ host address.
        rabbitmq_user (str): RabbitMQ username.
        rabbitmq_password (str): RabbitMQ password.
        queue_name (str): Name of the RabbitMQ queue.

    Returns:
        int: The number of messages in the queue. Returns -1 if an error occurs.
    """
    try:
        logging.info(f"Connecting to RabbitMQ at {rabbitmq_host} to check queue '{queue_name}'.")
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
        )
        channel = connection.channel()
        queue = channel.queue_declare(queue=queue_name, durable=True, passive=True)
        message_count = queue.method.message_count
        logging.info(f"Queue '{queue_name}' has {message_count} messages.")
        return message_count
    except Exception as e:
        logging.error(f"Error retrieving queue length: {e}")
        return -1  # Return -1 to indicate an error
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()


def scale_deployment(namespace, deployment_name, desired_replicas):
    """
    Scale the existing RabbitMQ consumer deployment.

    Args:
        namespace (str): Kubernetes namespace for the deployment.
        deployment_name (str): Name of the deployment to scale.
        desired_replicas (int): Desired number of replicas.
    """
    try:
        # Fetch the existing deployment
        logging.info(f"Fetching deployment '{deployment_name}' in namespace '{namespace}'.")
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Current replicas
        current_replicas = deployment.spec.replicas
        logging.info(f"Current replicas for '{deployment_name}': {current_replicas}")
        logging.info(f"Desired replicas for '{deployment_name}': {desired_replicas}")

        # Check if scaling is needed
        if current_replicas == desired_replicas:
            logging.info(f"No scaling needed for '{deployment_name}'. Replicas are already at {current_replicas}.")
            return

        # Update the replicas field
        deployment.spec.replicas = desired_replicas
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        logging.info(f"Scaled deployment '{deployment_name}' from {current_replicas} to {desired_replicas} replicas.")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logging.error(f"Deployment '{deployment_name}' not found in namespace '{namespace}'.")
        else:
            logging.error(f"Error scaling deployment '{deployment_name}': {e}")


def main():
    """
    Main controller loop to periodically fetch RabbitMQ queue length and manage deployments.
    """
    namespace = os.getenv("NAMESPACE", "default")
    min_replicas = int(os.getenv("MIN_REPLICAS", 1))
    max_replicas = int(os.getenv("MAX_REPLICAS", 10))
    threshold = int(os.getenv("THRESHOLD", 100))
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq.default.svc.cluster.local")
    rabbitmq_queue = os.getenv("RABBITMQ_QUEUE", "my-queue")
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
    deployment_name = f"rabbitmq-consumer"

    polling_interval = int(os.getenv("POLLING_INTERVAL", 10))  # Polling interval in seconds

    logging.info("Starting RabbitMQ Consumer Controller with periodic queue monitoring...")

    while True:
        try:
            # Fetch the current queue length
            queue_length = get_queue_length(rabbitmq_host, rabbitmq_user, rabbitmq_password, rabbitmq_queue)

            if queue_length == -1:
                logging.warning("Failed to retrieve queue length. Skipping scaling.")
                time.sleep(polling_interval)
                continue

            # Determine desired replicas
            if queue_length > threshold:
                desired_replicas = min((queue_length // threshold) + 1, max_replicas)
            else:
                desired_replicas = min_replicas

            logging.info(f"Queue length: {queue_length}. Desired replicas: {desired_replicas}.")
            scale_deployment(namespace, deployment_name, desired_replicas)

        except Exception as e:
            logging.error(f"Error during queue monitoring: {e}")

        # Wait for the next polling cycle
        time.sleep(polling_interval)


if __name__ == "__main__":
    main()
