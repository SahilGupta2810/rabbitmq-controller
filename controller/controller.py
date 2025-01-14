import os
import time
import requests
from kubernetes import client, config

# Load Kubernetes configuration (in-cluster or kubeconfig)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    config.load_incluster_config()  # For in-cluster execution (e.g., when running in a Kubernetes pod)
else:
    config.load_kube_config()  # For local development (requires kubeconfig)

# Kubernetes API client
apps_v1 = client.AppsV1Api()

# RabbitMQ configuration (passed as environment variables or hardcoded)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "http://rabbitmq-service:15672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
QUEUE_NAME = os.getenv("QUEUE_NAME", "my-queue")

# Scaling configuration
NAMESPACE = os.getenv("NAMESPACE", "default")
TARGET_DEPLOYMENT = os.getenv("TARGET_DEPLOYMENT", "consumer-deployment")
MAX_QUEUE_MESSAGES = int(os.getenv("MAX_QUEUE_MESSAGES", 100))  # Scale up if > 100 messages
MIN_REPLICAS = int(os.getenv("MIN_REPLICAS", 1))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", 10))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))  # Interval (seconds) to check queue depth


def get_queue_depth():
    """
    Fetch the current message count of the RabbitMQ queue using the Management API.

    Returns:
        int: The number of messages in the specified RabbitMQ queue.
    """
    try:
        url = f"{RABBITMQ_HOST}/api/queues/%2f/{QUEUE_NAME}"  # RabbitMQ API endpoint
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        queue_data = response.json()
        return queue_data.get("messages", 0)  # Return message count
    except requests.RequestException as e:
        print(f"Error fetching queue depth: {e}")
        return 0  # Default to 0 on error


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
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        return deployment.spec.replicas
    except client.exceptions.ApiException as e:
        print(f"Error fetching deployment '{deployment_name}': {e}")
        return None


def scale_deployment(deployment_name, namespace, replicas):
    """
    Scale a Kubernetes Deployment to the specified number of replicas.

    Args:
        deployment_name (str): The name of the Deployment to scale.
        namespace (str): The namespace of the Deployment.
        replicas (int): The desired number of replicas.

    Returns:
        None
    """
    try:
        # Get the current Deployment object
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        # Update the replicas field
        deployment.spec.replicas = replicas
        # Apply the changes
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        print(f"Scaled deployment '{deployment_name}' to {replicas} replicas.")
    except client.exceptions.ApiException as e:
        print(f"Error scaling deployment '{deployment_name}': {e}")


def reconcile():
    """
    Main reconciliation loop to monitor the RabbitMQ queue depth and scale the Deployment accordingly.
    """
    while True:
        # Get the current queue depth
        queue_depth = get_queue_depth()
        print(f"Queue '{QUEUE_NAME}' depth: {queue_depth} messages.")

        # Fetch the current number of replicas in the Deployment
        current_replicas = get_current_replicas(TARGET_DEPLOYMENT, NAMESPACE)
        if current_replicas is None:
            time.sleep(CHECK_INTERVAL)
            continue

        # Determine the desired number of replicas based on queue depth
        if queue_depth > MAX_QUEUE_MESSAGES:
            desired_replicas = min(MAX_REPLICAS, current_replicas + 1)  # Scale up by 1, capped at MAX_REPLICAS
        elif queue_depth == 0:
            desired_replicas = MIN_REPLICAS  # Scale down to minimum
        else:
            desired_replicas = current_replicas  # No scaling needed

        # Scale the Deployment if needed
        if desired_replicas != current_replicas:
            print(f"Scaling '{TARGET_DEPLOYMENT}' from {current_replicas} to {desired_replicas} replicas.")
            scale_deployment(TARGET_DEPLOYMENT, NAMESPACE, desired_replicas)
        else:
            print(f"No scaling needed for '{TARGET_DEPLOYMENT}'.")

        # Sleep before the next reconciliation loop
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    print("Starting RabbitMQ autoscaler...")
    reconcile()
