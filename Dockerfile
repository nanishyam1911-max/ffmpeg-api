# Base image with Python 3.11 slim
FROM python:3.11-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg build-essential fontconfig && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server.py and RushFlow font into container
COPY server.py .
COPY RushFlow.ttf /usr/share/fonts/truetype/RushFlow.ttf

# Rebuild font cache so FFmpeg can find RushFlow.ttf
RUN fc-cache -f -v

# Expose the port
EXPOSE 8080

# Run server with gunicorn
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8080"]
