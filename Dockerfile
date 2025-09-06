FROM python:3.12-slim

# Install FFmpeg and fonts
RUN apt-get update && \
    apt-get install -y ffmpeg fontconfig && \
    rm -rf /var/lib/apt/lists/*

# Copy RushFlow font (OTF) into system fonts
COPY fonts/RushFlow.otf /usr/share/fonts/opentype/rushflow/RushFlow.otf
RUN fc-cache -fv

# Work directory
WORKDIR /app

# Copy app
COPY server.py .
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask port
EXPOSE 5000

# Start server
CMD ["python", "server.py"]
