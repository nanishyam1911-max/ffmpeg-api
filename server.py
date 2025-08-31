import os
import tempfile
import subprocess
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def download_to_temp(url, suffix):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)
    return path

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=False)
    image_url = data.get("image")
    audio_url = data.get("audio")
    lyrics = data.get("lyrics")
    if not image_url or not audio_url or not lyrics:
        return jsonify({"error": "Fields 'image', 'audio', and 'lyrics' are required"}), 400

    img_path = aud_path = srt_path = out_path = None
    try:
        img_path = download_to_temp(image_url, ".jpg")
        aud_path = download_to_temp(audio_url, ".mp3")

        fd, srt_path = tempfile.mkstemp(suffix=".srt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(lyrics)

        fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-i", aud_path,
            "-vf", f"subtitles='{srt_path}':force_style='FontName=Rush Flow,FontSize=36,PrimaryColour=&HFFFFFF&'",
            "-tune", "stillimage",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path,
        ]
        subprocess.run(cmd, check=True)
        return send_file(out_path, mimetype="video/mp4", as_attachment=True, download_name="video.mp4")
    except requests.RequestException as e:
        return jsonify({"error": f"Download failed: {str(e)}"}), 400
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"ffmpeg failed: {str(e)}"}), 500
    finally:
        for p in [img_path, aud_path, srt_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

