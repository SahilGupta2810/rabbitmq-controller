# Use a lightweight Python base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the controller script into the container
COPY rabbitmq_controller.py .

# Install required Python libraries
RUN pip install kubernetes pika

# Set the command to run the controller
CMD ["python", "rabbitmq_controller.py"]
