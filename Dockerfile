# Base image with Python 3.11 slim
FROM python:3.11-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg build-essential fonts-dejavu && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server.py and RushFlow font into container
COPY server.py .
COPY RushFlow.ttf .

# Expose the port
EXPOSE 8080

# Run server with gunicorn
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8080"]
