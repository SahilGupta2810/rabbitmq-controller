# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the Python script
COPY rabbitmq_producer.py .

# Install pika library
RUN pip install pika

# Command to run the consumer app
CMD ["python", "rabbitmq_consumer.py"]
