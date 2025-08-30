FROM jrottenberg/ffmpeg:4.4-ubuntu
RUN apt-get update && apt-get install -y python3 python3-pip curl

# Install Rush Flow font
COPY RushFlow.ttf /usr/share/fonts/
RUN fc-cache -f -v

WORKDIR /app
COPY server.py .
RUN pip3 install flask
CMD ["python3", "server.py"]
