import os
import time
from kubernetes import client, config, watch
import pika

# Load Kubernetes configuration (assumes running in-cluster)
config.load_incluster_config()

# Kubernetes API clients
apps_v1 = client.AppsV1Api()
custom_objects_api = client.CustomObjectsApi()


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
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
        )
        channel = connection.channel()
        queue = channel.queue_declare(queue=queue_name, durable=True, passive=True)
        return queue.method.message_count
    except Exception as e:
        print(f"Error retrieving queue length: {e}")
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
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Check if scaling is needed
        current_replicas = deployment.spec.replicas
        if current_replicas == desired_replicas:
            print(f"No scaling needed. Deployment '{deployment_name}' already has {current_replicas} replicas.")
            return

        # Update the replicas field
        deployment.spec.replicas = desired_replicas
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        print(f"Scaled deployment '{deployment_name}' from {current_replicas} to {desired_replicas} replicas.")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            print(f"Deployment '{deployment_name}' not found in namespace '{namespace}'.")
        else:
            print(f"Error scaling deployment '{deployment_name}': {e}")


def main():
    """
    Main controller loop to watch for RabbitMQConsumer resources and manage deployments.
    """
    crd_group = os.getenv("CRD_GROUP", "one2n.com")
    crd_version = os.getenv("CRD_VERSION", "v1")
    crd_plural = os.getenv("CRD_PLURAL", "rabbitmqconsumers")
    namespace = os.getenv("NAMESPACE", "poc")

    min_replicas = int(os.getenv("MIN_REPLICAS", 1))
    max_replicas = int(os.getenv("MAX_REPLICAS", 10))
    threshold = int(os.getenv("THRESHOLD", 150))

    w = watch.Watch()
    while True:
        try:
            for event in w.stream(custom_objects_api.list_cluster_custom_object, crd_group, crd_version, crd_plural):
                obj = event["object"]
                spec = obj.get("spec", {})
                name = obj["metadata"]["name"]

                if event["type"] in ["ADDED", "MODIFIED"]:
                    rabbitmq_host = spec.get("rabbitmqHost", os.getenv("RABBITMQ_HOST"))
                    rabbitmq_queue = spec.get("rabbitmqQueue", os.getenv("RABBITMQ_QUEUE"))
                    rabbitmq_user = spec.get("rabbitmqUser", os.getenv("RABBITMQ_USER"))
                    rabbitmq_password = spec.get("rabbitmqPassword", os.getenv("RABBITMQ_PASSWORD"))
                    deployment_name = f"rabbitmq-consumer"

                    # Get the current queue length
                    queue_length = get_queue_length(rabbitmq_host, rabbitmq_user, rabbitmq_password, rabbitmq_queue)

                    if queue_length == -1:
                        print(f"Failed to retrieve queue length for {name}. Skipping scaling.")
                        continue

                    # Determine the desired replicas based on queue length
                    if queue_length > threshold:
                        desired_replicas = min((queue_length // threshold) + 1, max_replicas)
                    else:
                        desired_replicas = min_replicas

                    print(f"Queue length: {queue_length}. Scaling deployment '{deployment_name}' to {desired_replicas} replicas.")
                    scale_deployment(namespace, deployment_name, desired_replicas)

                elif event["type"] == "DELETED":
                    print(f"Resource '{name}' deleted. No scaling action required.")

        except Exception as e:
            print(f"Error in watch stream: {e}. Retrying in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    print("Starting RabbitMQ Consumer Controller...")
    main()
