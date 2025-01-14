import os
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


def create_or_update_deployment(namespace, spec, desired_replicas):
    """
    Create or update the RabbitMQ consumer deployment based on the desired number of replicas.

    Args:
        namespace (str): Kubernetes namespace for the deployment.
        spec (dict): Spec of the RabbitMQConsumer resource.
        desired_replicas (int): Desired number of replicas.
    """
    deployment_name = f"rabbitmq-consumer"

    # Prepare environment variables for the container
    container_env = [
        client.V1EnvVar(name="RABBITMQ_HOST", value=spec['rabbitmqHost']),
        client.V1EnvVar(name="RABBITMQ_QUEUE", value=spec['rabbitmqQueue']),
        client.V1EnvVar(name="RABBITMQ_USER", value=spec['rabbitmqUser']),
        client.V1EnvVar(name="RABBITMQ_PASSWORD", value=spec['rabbitmqPassword']),
    ]

    # Define the deployment
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=deployment_name, namespace=namespace),
        spec=client.V1DeploymentSpec(
            replicas=desired_replicas,
            selector=client.V1LabelSelector(match_labels={"app": deployment_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": deployment_name}),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="rabbitmq-consumer",
                            image="sahil2898/one2n-controller:v1.1",
                            env=container_env,
                            resources=client.V1ResourceRequirements(
                                limits={"memory": "128Mi", "cpu": "500m"},
                                requests={"memory": "64Mi", "cpu": "250m"},
                            ),
                        )
                    ]
                ),
            ),
        ),
    )

    try:
        # Attempt to create the deployment
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
        print(f"Created deployment: {deployment_name}")
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Deployment already exists, patch it
            existing_deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
            if existing_deployment.spec.replicas != desired_replicas:
                apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
                print(f"Updated deployment: {deployment_name} to {desired_replicas} replicas.")
        else:
            print(f"Error creating or updating deployment: {e}")


def delete_deployment(namespace, deployment_name):
    """
    Delete the RabbitMQ consumer deployment.

    Args:
        namespace (str): Kubernetes namespace for the deployment.
        deployment_name (str): Name of the deployment to delete.
    """
    try:
        apps_v1.delete_namespaced_deployment(name=deployment_name, namespace=namespace)
        print(f"Deleted deployment: {deployment_name}")
    except client.exceptions.ApiException as e:
        if e.status != 404:  # Ignore 404 (not found) errors
            print(f"Error deleting deployment '{deployment_name}': {e}")


def main():
    """
    Main controller loop to watch for RabbitMQConsumer resources and manage deployments.
    """
    crd_group = os.getenv("CRD_GROUP", "one2n.com")
    crd_version = os.getenv("CRD_VERSION", "v1")
    crd_plural = os.getenv("CRD_PLURAL", "rabbitmqconsumers")
    namespace = os.getenv("NAMESPACE", "default")

    min_replicas = int(os.getenv("MIN_REPLICAS", 1))
    max_replicas = int(os.getenv("MAX_REPLICAS", 10))
    threshold = int(os.getenv("THRESHOLD", 100))

    w = watch.Watch()
    for event in w.stream(custom_objects_api.list_cluster_custom_object, crd_group, crd_version, crd_plural):
        obj = event["object"]
        spec = obj.get("spec", {})
        name = obj["metadata"]["name"]

        if event["type"] in ["ADDED", "MODIFIED"]:
            rabbitmq_host = spec.get("rabbitmqHost", os.getenv("RABBITMQ_HOST"))
            rabbitmq_queue = spec.get("rabbitmqQueue", os.getenv("RABBITMQ_QUEUE"))
            rabbitmq_user = spec.get("rabbitmqUser", os.getenv("RABBITMQ_USER"))
            rabbitmq_password = spec.get("rabbitmqPassword", os.getenv("RABBITMQ_PASSWORD"))

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

            print(f"Queue length: {queue_length}. Setting replicas to {desired_replicas}.")
            create_or_update_deployment(namespace, spec, desired_replicas)

        elif event["type"] == "DELETED":
            deployment_name = f"rabbitmq-consumer-{spec.get('rabbitmqQueue')}"
            delete_deployment(namespace, deployment_name)


if __name__ == "__main__":
    print("Starting RabbitMQ Consumer Controller...")
    main()
