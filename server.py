import os
import tempfile
import subprocess
import requests
import whisper
import json
from flask import Flask, request, send_file, jsonify
import logging
import sys
import signal
from contextlib import contextmanager

app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load Whisper
app.logger.info("Loading Whisper model...")
try:
    whisper_model = whisper.load_model("base")
    app.logger.info("Whisper model loaded successfully")
except Exception as e:
    app.logger.error(f"Failed to load Whisper model: {e}")
    whisper_model = None

# Timeout helper
@contextmanager
def timeout(seconds):
    def handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds}s")
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        yield

# Convert Dropbox links
def convert_dropbox_url(url):
    if "dropbox.com" in url and "?dl=0" in url:
        return url.replace("?dl=0", "?dl=1")
    elif "dropbox.com" in url and "?dl=1" not in url:
        return url + ("&dl=1" if "?" in url else "?dl=1")
    return url

# Download helper
def download_temp(url, suffix, max_size_mb=50):
    url = convert_dropbox_url(url)
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=suffix)
    total = 0
    limit = max_size_mb * 1024 * 1024
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > limit:
                os.remove(path)
                raise ValueError("File too large")
            f.write(chunk)
    return path

# Get audio duration
def get_audio_duration(audio_path):
    try:
        cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
               "-of", "csv=p=0", audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None

# Health check
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

# Generate video
@app.route("/generate", methods=["POST"])
def generate_video():
    audio_path = img_path = srt_path = out_path = None
    try:
        data = request.get_json(force=True)
        audio_url = data.get("audio")
        image_url = data.get("image")
        lyrics = data.get("lyrics")

        if not all([audio_url, image_url, lyrics]):
            return jsonify({"error": "Missing parameters"}), 400

        audio_path = download_temp(audio_url, ".mp3")
        img_path = download_temp(image_url, ".png")

        # Create temp lyrics file
        fd, srt_path = tempfile.mkstemp(suffix=".srt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:05,000\n")
            f.write(lyrics.strip() + "\n")

        fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        # Font
        font_path = os.path.join(os.getcwd(), "fonts", "RushFlow.ttf")
        if os.path.exists(font_path):
            font_style = f"FontName=RushFlow,FontFile={font_path}"
        else:
            font_style = "FontName=Arial"

        subtitle_style = (
            f"force_style='{font_style},FontSize=32,"
            "PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Shadow=1'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-i", audio_path,
            "-vf", f"subtitles={srt_path}:{subtitle_style}",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            out_path
        ]
        subprocess.run(cmd, check=True)

        return send_file(out_path, mimetype="video/mp4",
                         as_attachment=True, download_name="lyrics_video.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for p in [audio_path, img_path, srt_path, out_path]:
            if p and os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
