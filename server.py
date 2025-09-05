import os
import tempfile
import subprocess
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def download_temp(url, suffix):
    """Download a file from URL into a temporary local file."""
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
def generate_video():
    audio_path = img_path = srt_path = out_path = None
    try:
        data = request.get_json(force=True)
        audio_url = data.get("audio")
        image_url = data.get("image")
        lyrics_text = data.get("lyrics")

        if not all([audio_url, image_url, lyrics_text]):
            return jsonify({"error": "audio, image, and lyrics are required"}), 400

        # Download audio and image
        audio_path = download_temp(audio_url, ".mp3")
        img_path = download_temp(image_url, ".png")

        # Prepare temporary SRT for FFmpeg
        fd, srt_path = tempfile.mkstemp(suffix=".srt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lyrics_text.split("\n"):
                line = line.strip()
                # Gentle split for long lines
                if len(line) > 40:
                    mid = len(line) // 2
                    f.write(line[:mid] + "\n" + line[mid:] + "\n\n")  # small gap
                else:
                    f.write(line + "\n\n")  # small gap for short lines

        # Output temporary video
        fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        # Use absolute path for font
        font_path = os.path.join(os.getcwd(), "RushFlow.ttf")

        # FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-i", audio_path,
            "-vf", f"subtitles={srt_path}:force_style='FontName=RushFlow,FontSize=36,PrimaryColour=&HFFFFFF&,FontFile={font_path}'",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path
        ]
        subprocess.run(cmd, check=True)

        # Send video file
        return send_file(out_path, mimetype="video/mp4", as_attachment=True, download_name="final_video.mp4")

    except requests.RequestException as e:
        return jsonify({"error": f"Download failed: {str(e)}"}), 400
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"FFmpeg failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup temporary files AFTER sending
        for p in [audio_path, img_path, srt_path, out_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
