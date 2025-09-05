FROM python:3.11-slim

# Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg build-essential fonts-dejavu && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code and RushFlow font
COPY server.py .
COPY RushFlow.ttf .

# Expose port
EXPOSE 8080

# Command to run the server
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8080"]
