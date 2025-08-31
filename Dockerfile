FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fontconfig curl ca-certificates python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Font: make sure file exists at repo root and name matches exactly
COPY RushFlow.ttf /usr/share/fonts/truetype/RushFlow.ttf
RUN fc-cache -f -v

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
COPY server.py /app/server.py

EXPOSE 8080
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "server:app"]

