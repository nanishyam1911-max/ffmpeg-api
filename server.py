import os
import tempfile
import subprocess
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def download_temp(url, suffix):
    """Download a file from URL into a temporary local file."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)
    return path

def fetch_lyrics(lyrics_input):
    """Return lyrics text, either from raw text or by downloading from URL."""
    if lyrics_input.startswith("http://") or lyrics_input.startswith("https://"):
        resp = requests.get(lyrics_input, timeout=60)
        resp.raise_for_status()
        return resp.text
    return lyrics_input

def make_srt(lyrics_text, out_path):
    """Write lyrics into valid .srt file with dummy timings."""
    lines = [l.strip() for l in lyrics_text.split("\n") if l.strip()]
    with open(out_path, "w", encoding="utf-8") as f:
        start_time = 0
        index = 1
        for line in lines:
            # split long lines into 2 halves
            if len(line) > 40:
                line1 = line[:len(line)//2].strip()
                line2 = line[len(line)//2:].strip()
                text = line1 + "\n" + line2
            else:
                text = line

            end_time = start_time + 3  # 3s per line (dummy timing)
            f.write(f"{index}\n")
            f.write(f"00:00:{start_time:02d},000 --> 00:00:{end_time:02d},000\n")
            f.write(text + "\n\n")
            start_time = end_time
            index += 1

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
        lyrics_input = data.get("lyrics")

        if not all([audio_url, image_url, lyrics_input]):
            return jsonify({"error": "audio, image, and lyrics are required"}), 400

        # Download audio and image
        audio_path = download_temp(audio_url, ".mp3")
        img_path = download_temp(image_url, ".png")

        # Fetch lyrics
        lyrics_text = fetch_lyrics(lyrics_input)

        # Make SRT file
        fd, srt_path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        make_srt(lyrics_text, srt_path)

        # Output temp video
        fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        # FFmpeg subtitles with RushFlow font
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-i", audio_path,
            "-vf", f"subtitles={srt_path}:force_style='FontName=Rush Flow,FontSize=36,PrimaryColour=&HFFFFFF&'",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path
        ]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        return send_file(out_path, mimetype="video/mp4", as_attachment=True, download_name="final_video.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for p in [audio_path, img_path, srt_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

