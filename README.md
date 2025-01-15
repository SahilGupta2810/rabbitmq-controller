# RabbitMQ Controller

This project implements a Kubernetes-native solution to scale RabbitMQ consumers dynamically based on queue length. It includes a custom Kubernetes controller, a producer to publish messages to a RabbitMQ queue, and a consumer to process messages from the queue.

## Repository Structure

```
.
├── rabbitmq_controller.py       # Custom RabbitMQ controller logic
├── rabbitmq_producer.py         # RabbitMQ producer script
├── rabbitmq_consumer.py         # RabbitMQ consumer script
├── cr.yaml                      # Custom Resource (CR) instance
├── crd.yaml                     # Custom Resource Definition (CRD)
├── rbac.yaml                    # RBAC for the controller
├── producer-deployment.yaml     # Deployment configuration for the producer
├── consumer-deployment.yaml     # Deployment configuration for the consumer
├── controller-deployment.yaml   # Deployment configuration for the controller
```

## Custom Resource Definition (CRD)
The CRD defines the schema for `RabbitMQConsumer` resources, allowing users to specify RabbitMQ connection details, scaling thresholds, and replica limits.

### `crd.yaml` Highlights
- **Group**: `one2n.com`
- **Kind**: `RabbitMQConsumer`
- **Properties**:
  - `rabbitmqHost`: RabbitMQ host address
  - `rabbitmqQueue`: RabbitMQ queue name
  - `rabbitmqUser`: Username for authentication
  - `rabbitmqPassword`: Password for authentication
  - `minReplicas`: Minimum number of consumer replicas
  - `maxReplicas`: Maximum number of consumer replicas
  - `threshold`: Queue length threshold to trigger scaling

CR:
```yaml
apiVersion: one2n.com/v1
kind: RabbitMQConsumer
metadata:
  name: one2n-consumer
  namespace: poc
spec:
  rabbitmqHost: "rabbitmq-service.poc.svc.cluster.local"
  rabbitmqQueue: "one2n"
  rabbitmqUser: "guest"
  rabbitmqPassword: "test@123"
  minReplicas: 1
  maxReplicas: 10
  threshold: 100
```

## Components Overview

### 1. RabbitMQ Controller
The custom controller (`rabbitmq_controller.py`) monitors the queue length and dynamically adjusts the replicas of the consumer deployment based on the CR specifications.

#### Key Features:
- Retrieves queue length using RabbitMQ's management API.
- Scales consumer deployments based on:
  - Minimum and maximum replica limits
  - Message threshold in the queue
- Periodically polls the RabbitMQ queue.

#### Environment Variables:
- `NAMESPACE`: Kubernetes namespace
- `MIN_REPLICAS`, `MAX_REPLICAS`: Scaling limits
- `THRESHOLD`: Queue length to trigger scaling
- `POLLING_INTERVAL`: Interval (in seconds) for polling queue length

#### Deployment:
Refer to `controller-deployment.yaml` for deployment configuration.

#### Function Explanations:

##### `get_queue_length`
- **Purpose**: Connects to RabbitMQ and retrieves the current number of messages in the specified queue.
- **Input**:
  - `rabbitmq_host`: RabbitMQ host address.
  - `rabbitmq_user`: Username for authentication.
  - `rabbitmq_password`: Password for authentication.
  - `queue_name`: Name of the RabbitMQ queue.
- **Output**:
  - Returns the count of messages in the queue or `-1` if an error occurs.
- **Key Operations**:
  - Establishes a connection with RabbitMQ using credentials.
  - Queries the queue to fetch the message count.
  - Logs success or error messages.

##### `scale_deployment`
- **Purpose**: Adjusts the number of replicas for a specific Kubernetes deployment based on the desired state.
- **Input**:
  - `namespace`: Kubernetes namespace where the deployment resides.
  - `deployment_name`: Name of the deployment to scale.
  - `desired_replicas`: Number of replicas desired.
- **Output**:
  - Logs the scaling action and updates the deployment replicas if necessary.
- **Key Operations**:
  - Fetches the current deployment state.
  - Compares current and desired replica counts.
  - Updates the replica count if they differ.

##### `main`
- **Purpose**: Main loop to monitor RabbitMQ queue length and scale the deployment accordingly.
- **Key Operations**:
  - Retrieves environment variables for configuration.
  - Periodically fetches the queue length using `get_queue_length`.
  - Determines the desired number of replicas based on the queue length and threshold.
  - Invokes `scale_deployment` to apply scaling.
  - Logs key actions and errors during execution.

#### Code Snippet:
```python
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
        return -1
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

def scale_deployment(namespace, deployment_name, desired_replicas):
    try:
        logging.info(f"Fetching deployment '{deployment_name}' in namespace '{namespace}'.")
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        current_replicas = deployment.spec.replicas
        logging.info(f"Current replicas for '{deployment_name}': {current_replicas}")
        logging.info(f"Desired replicas for '{deployment_name}': {desired_replicas}")

        if current_replicas == desired_replicas:
            logging.info(f"No scaling needed for '{deployment_name}'.")
            return

        deployment.spec.replicas = desired_replicas
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        logging.info(f"Scaled deployment '{deployment_name}' from {current_replicas} to {desired_replicas} replicas.")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logging.error(f"Deployment '{deployment_name}' not found in namespace '{namespace}'.")
        else:
            logging.error(f"Error scaling deployment '{deployment_name}': {e}")

def main():
    namespace = os.getenv("NAMESPACE", "default")
    min_replicas = int(os.getenv("MIN_REPLICAS", 1))
    max_replicas = int(os.getenv("MAX_REPLICAS", 10))
    threshold = int(os.getenv("THRESHOLD", 100))
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq.default.svc.cluster.local")
    rabbitmq_queue = os.getenv("RABBITMQ_QUEUE", "my-queue")
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
    deployment_name = f"rabbitmq-consumer"

    polling_interval = int(os.getenv("POLLING_INTERVAL", 10))

    logging.info("Starting RabbitMQ Consumer Controller with periodic queue monitoring...")

    while True:
        try:
            queue_length = get_queue_length(rabbitmq_host, rabbitmq_user, rabbitmq_password, rabbitmq_queue)

            if queue_length == -1:
                logging.warning("Failed to retrieve queue length. Skipping scaling.")
                time.sleep(polling_interval)
                continue

            if queue_length > threshold:
                desired_replicas = min((queue_length // threshold) + 1, max_replicas)
            else:
                desired_replicas = min_replicas

            logging.info(f"Queue length: {queue_length}. Desired replicas: {desired_replicas}.")
            scale_deployment(namespace, deployment_name, desired_replicas)

        except Exception as e:
            logging.error(f"Error during queue monitoring: {e}")

        time.sleep(polling_interval)

if __name__ == "__main__":
    main()
```

---

### Issues

1. **Deployment Scaling Logic**
   - **Issue**: The controller created a deployment instead of scaling an existing one.
   - **Resolution**: Updated the logic to fetch and scale an existing Kubernetes deployment based on the RabbitMQ queue length.

2. **Polling Interval for Queue Monitoring**
   - **Issue**: Clarified whether the controller continuously fetches the queue length or relies on events.
   - **Resolution**: Modified the code to periodically fetch queue length based on the `POLLING_INTERVAL` environment variable.

3. **RBAC Permissions**
   - **Issue**: The service account lacked sufficient permissions to scale deployments or interact with custom resources.
   - **Resolution**: Updated `rbac.yaml` to include necessary permissions for watching, listing, and modifying deployments.

5. **Scaling Accuracy**
   - **Issue**: Incorrect calculation of desired replicas during scaling.
   - **Resolution**: Adjusted scaling logic to calculate replicas based on the queue length and `threshold` configuration.

---

### Log Highlights

Below are key log entries demonstrating the successful operation of the RabbitMQ Controller:

```
2025-01-15T03:19:42.136+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,136 [INFO] Created channel=1
2025-01-15T03:19:42.140+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,139 [INFO] Queue 'one2n' has 8564 messages.
2025-01-15T03:19:42.144+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,144 [INFO] Queue length: 8564. Desired replicas: 10.
2025-01-15T03:19:42.144+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,144 [INFO] Fetching deployment 'rabbitmq-consumer' in namespace 'poc'.
2025-01-15T03:19:42.175+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,174 [INFO] Current replicas for 'rabbitmq-consumer': 0
2025-01-15T03:19:42.175+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,175 [INFO] Desired replicas for 'rabbitmq-consumer': 10
2025-01-15T03:19:42.190+05:30 [rabbitmq-controller] 2025-01-14 21:49:42,189 [INFO] Scaled deployment 'rabbitmq-consumer' from 0 to 10 replicas.
2025-01-15T03:19:52.275+05:30 [rabbitmq-controller] 2025-01-14 21:49:52,275 [INFO] Queue 'one2n' has 0 messages.
2025-01-15T03:19:52.290+05:30 [rabbitmq-controller] 2025-01-14 21:49:52,290 [INFO] Current replicas for 'rabbitmq-consumer': 10
2025-01-15T03:19:52.290+05:30 [rabbitmq-controller] 2025-01-14 21:49:52,290 [INFO] Desired replicas for 'rabbitmq-consumer': 0
2025-01-15T03:19:52.243+05:30 [rabbitmq-controller] 2025-01-14 21:49:52,243 [INFO] Scaled deployment 'rabbitmq-consumer' from 10 to 0 replicas.
```

These logs demonstrate:
- Successful connection to RabbitMQ and fetching of queue metrics.
- Determination of desired replica count based on the queue length.
- Accurate scaling of the deployment to match the desired state.

