FROM python:3.12-slim


# Install FFmpeg and fontconfig
RUN apt-get update && \
apt-get install -y ffmpeg fontconfig && \
rm -rf /var/lib/apt/lists/*


# Copy RushFlow font from repo into container
COPY ../fonts/RushFlow.otf /usr/share/fonts/opentype/rushflow/RushFlow.otf
RUN fc-cache -fv


WORKDIR /app
COPY server.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "server:app"]
