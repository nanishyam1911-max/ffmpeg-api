from flask import Flask, request, jsonify
import subprocess
import os
import uuid

app = Flask(__name__)

# Route to generate video with ffmpeg
@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.json
    image = data.get("image")
    audio = data.get("audio")
    lyrics = data.get("lyrics", "Sample lyrics")  # for now just simple overlay text

    if not image or not audio:
        return jsonify({"error": "image and audio are required"}), 400

    output_file = f"output_{uuid.uuid4().hex}.mp4"

    # ffmpeg comma

