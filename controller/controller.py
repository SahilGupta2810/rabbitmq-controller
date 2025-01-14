import os
import time
import requests
import logging
from kubernetes import client, config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Load Kubernetes configuration (in-cluster or kubeconfig)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    logging.info("Loading in-cluster Kubernetes configuration.")
    config.load_incluster_config()  # For in-cluster execution
else:
    logging.info("Loading kubeconfig for local development.")
    config.load_kube_config()  # For local development

# Kubernetes API client
apps_v1 = client.AppsV1Api()

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "http://rabbitmq-service:15672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "test@123")
QUEUE_NAME = os.getenv("QUEUE_NAME", "one2n")

# Scaling configuration
NAMESPACE = os.getenv("NAMESPACE", "default")
TARGET_DEPLOYMENT = os.getenv("TARGET_DEPLOYMENT", "consumer-deployment")
MAX_QUEUE_MESSAGES = int(os.getenv("MAX_QUEUE_MESSAGES", 15))
MIN_REPLICAS = int(os.getenv("MIN_REPLICAS", 1))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", 6))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))


def get_queue_depth():
    """
    Fetch the current message count of the RabbitMQ queue using the Management API.

    Returns:
        int: The number of messages in the specified RabbitMQ queue.
    """
    try:
        url = f"{RABBITMQ_HOST}/api/queues/%2f/{QUEUE_NAME}"  # RabbitMQ API endpoint
        logging.debug(f"Fetching queue depth from {url}")
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS), timeout=5)
        response.raise_for_status()
        queue_data = response.json()
        queue_depth = queue_data.get("messages", 0)
        logging.info(f"Queue '{QUEUE_NAME}' depth: {queue_depth} messages.")
        return queue_depth
    except requests.RequestException as e:
        logging.error(f"Error fetching queue depth: {e}")
        return 0


def get_current_replicas(deployment_name, namespace):
    """
    Get the current number of replicas for a Kubernetes Deployment.

    Args:
        deployment_name (str): The name of the Deployment.
        namespace (str): The namespace where the Deployment resides.

    Returns:
        int: The number of replicas in the Deployment or None if an error occurs.
    """
    try:
        logging.debug(f"Fetching current replicas for deployment '{deployment_name}' in namespace '{namespace}'.")
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        current_replicas = deployment.spec.replicas
        logging.info(f"Current replicas for '{deployment_name}': {current_replicas}")
        return current_replicas
    except client.exceptions.ApiException as e:
        logging.error(f"Error fetching deployment '{deployment_name}': {e}")
        return None


def scale_deployment(deployment_name, namespace, replicas):
    """
    Scale a Kubernetes Deployment to the specified number of replicas.

    Args:
        deployment_name (str): The name of the Deployment to scale.
        namespace (str): The namespace of the Deployment.
        replicas (int): The desired number of replicas.
    """
    try:
        logging.debug(f"Scaling deployment '{deployment_name}' to {replicas} replicas in namespace '{namespace}'.")
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        deployment.spec.replicas = replicas
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        logging.info(f"Scaled deployment '{deployment_name}' to {replicas} replicas.")
    except client.exceptions.ApiException as e:
        logging.error(f"Error scaling deployment '{deployment_name}': {e}")


def reconcile():
    """
    Main reconciliation loop to monitor the RabbitMQ queue depth and scale the Deployment accordingly.
    """
    while True:
        logging.debug("Starting reconciliation loop.")
        queue_depth = get_queue_depth()
        current_replicas = get_current_replicas(TARGET_DEPLOYMENT, NAMESPACE)

        if current_replicas is None:
            logging.warning("Current replicas could not be fetched. Skipping this cycle.")
            time.sleep(CHECK_INTERVAL)
            continue

        # Determine the desired number of replicas
        if queue_depth > MAX_QUEUE_MESSAGES:
            desired_replicas = min(MAX_REPLICAS, current_replicas + 1)
        elif queue_depth == 0:
            desired_replicas = MIN_REPLICAS
        else:
            desired_replicas = current_replicas

        # Scale if needed
        if desired_replicas != current_replicas:
            logging.info(f"Scaling '{TARGET_DEPLOYMENT}' from {current_replicas} to {desired_replicas} replicas.")
            scale_deployment(TARGET_DEPLOYMENT, NAMESPACE, desired_replicas)
        else:
            logging.info(f"No scaling required for '{TARGET_DEPLOYMENT}'.")

        logging.debug(f"Sleeping for {CHECK_INTERVAL} seconds before next loop.")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    logging.info("Starting RabbitMQ autoscaler...")
    reconcile()
