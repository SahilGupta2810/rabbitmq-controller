FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the Python script
COPY controller.py .

# Command to run the controller
CMD ["python", "controller.py"]
