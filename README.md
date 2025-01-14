Here's a **README.md** file for your RabbitMQ Autoscaler project:

---

# **RabbitMQ Autoscaler**

A custom Kubernetes controller written in Python that dynamically scales a Kubernetes Deployment based on the queue length of a RabbitMQ queue. The autoscaler periodically polls the RabbitMQ Management API to monitor the queue and adjusts the number of replicas for the target Deployment.

---

## **Features**
- Monitors RabbitMQ queues in real-time using the Management API.
- Scales Kubernetes Deployments dynamically based on queue length.
- Configurable thresholds for scaling up and scaling down.
- Logs actions and metrics for observability.

---

## **Architecture**

### Workflow
1. Fetch the RabbitMQ queue length periodically.
2. Compare the current queue length against predefined thresholds:
   - Scale up if the queue length exceeds the `MAX_MESSAGES` threshold.
   - Scale down if the queue length falls below the threshold.
3. Adjust the number of replicas in the target Kubernetes Deployment.

### Components
- **RabbitMQ Management API**: Provides queue metrics.
- **Kubernetes Deployment**: Target Deployment to be scaled.
- **RabbitMQ Autoscaler**: A Python-based controller running as a Kubernetes Pod.

---

## **Prerequisites**
1. **RabbitMQ Setup**:
   - Ensure RabbitMQ is running in the Kubernetes cluster.
   - Enable the Management API (default at `http://<rabbitmq-host>:15672`).

2. **Kubernetes Cluster**:
   - A running Kubernetes cluster with a Deployment to be scaled.
   - Access to `kubectl`.

3. **Python Environment**:
   - Python 3.9+ installed (for local testing and development).

4. **Dependencies**:
   - `kubernetes` Python client.
   - `requests` library.

---

## **Installation**

### 1. Clone the Repository
```bash
git clone https://github.com/SahilGupta2810/rabbitmq-controller.git
cd rabbitmq-controller
```

### 2. Build the Docker Image
```bash
docker build -t sahil2898/rabbitmq-autoscaler:latest .
```

### 3. Push the Docker Image
```bash
docker push your-docker-repo/rabbitmq-autoscaler:latest
```

### 4. Deploy to Kubernetes
Apply the deployment YAML file:
```bash
kubectl apply -f rabbitmq-autoscaler.yaml
```

---

## **Configuration**

### Environment Variables
The RabbitMQ Autoscaler is configurable via environment variables:

| Variable          | Description                                           | Default Value               |
|--------------------|-------------------------------------------------------|-----------------------------|
| `RABBITMQ_HOST`    | RabbitMQ Management API URL                           | `http://rabbitmq-service:15672` |
| `RABBITMQ_USER`    | RabbitMQ username                                     | `guest`                     |
| `RABBITMQ_PASS`    | RabbitMQ password                                     | `guest`                     |
| `QUEUE_NAME`       | RabbitMQ queue to monitor                             | `my-queue`                  |
| `TARGET_DEPLOYMENT`| Name of the Kubernetes Deployment to scale            | `my-app`                    |
| `NAMESPACE`        | Kubernetes namespace of the target Deployment         | `default`                   |
| `MAX_MESSAGES`     | Threshold for scaling up                              | `100`                       |
| `MIN_REPLICAS`     | Minimum number of replicas                            | `1`                         |
| `MAX_REPLICAS`     | Maximum number of replicas                            | `5`                         |
| `SLEEP_INTERVAL`   | Time interval (seconds) between queue checks          | `30`                        |

---

## **Usage**

### Monitor Logs
View logs for the RabbitMQ Autoscaler:
```bash
kubectl logs deployment/rabbitmq-autoscaler
```

### Verify Scaling
1. Simulate load by adding messages to the RabbitMQ queue.
2. Check the replicas of the target Deployment:
   ```bash
   kubectl get deployment my-app
   ```

---

## **Development**

### Local Testing
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the script locally:
   ```bash
   python rabbitmq_autoscaler.py
   ```

### Linting and Formatting
Ensure your code follows Python standards:
```bash
pip install flake8 black
flake8 rabbitmq_autoscaler.py
black rabbitmq_autoscaler.py
```

---

## **Customizing the Autoscaler**

### Add More Metrics
Modify the `get_queue_length()` function to include additional RabbitMQ metrics, such as `state` or `consumers`.

### Advanced Scaling Logic
Enhance the `scale_deployment()` function to implement proportional scaling based on the queue length.

---

## **Contact**
For questions or feedback, contact **[Sahil Gupta](mailto:contactsahil2810@gmail.com)**. 

---
