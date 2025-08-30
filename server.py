from flask import Flask, request, send_file, jsonify
import subprocess, os, tempfile, uuid

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.get_json()
    image_url = data.get("image")
    audio_url = data.get("audio")
    lyrics = data.get("lyrics")

    if not image_url or not audio_url or not lyrics:
        return jsonify({"error": "image, audio, and lyrics are required"}), 400

    tmpdir = tempfile.mkdtemp()
    image = os.path.join(tmpdir, "bg.jpg")
    audio = os.path.join(tmpdir, "audio.mp3")
    srt = os.path.join(tmpdir, "subtitles.srt")
    out = os.path.join(tmpdir, f"out_{uuid.uuid4().hex}.mp4")

    # Download inputs
    os.system(f"curl -s '{image_url}' -o {image}")
    os.system(f"curl -s '{audio_url}' -o {audio}")

    # Save subtitles
    with open(srt, "w", encoding="utf-8") as f:
        f.write(lyrics)

    # Run ffmpeg
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image, "-i", audio,
        "-vf", f"scale=1280:-2,subtitles={srt}:force_style='FontName=Rush Flow,Fontsize=48,PrimaryColour=&H00FFFFFF,Outline=2,Shadow=1,Alignment=2,MarginV=40'",
        "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage", "-crf", "18",
        "-c:a", "aac", "-shortest", out
    ]
    subprocess.run(cmd, check=True)

    return send_file(out, as_attachment=True, download_name="video.mp4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

