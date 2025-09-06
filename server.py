from flask import Flask, request, send_file, jsonify
import os
import uuid
import requests
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip
import srt

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def download_file(url, filename):
    if not url or not isinstance(url, str):
        raise ValueError("Invalid URL provided")

    # Convert Dropbox link to direct download
    if "dropbox.com" in url and "?dl=0" in url:
        url = url.replace("?dl=0", "?dl=1")

    response = requests.get(url, stream=True, timeout=60)
    if response.status_code != 200:
        raise ValueError(f"Failed to download file from {url}, status {response.status_code}")

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)
    return filepath

def split_text(text, max_len=40):
    """Split long text into two lines if too long"""
    if len(text) <= max_len:
        return text
    mid = len(text) // 2
    left = text.rfind(" ", 0, mid)
    right = text.find(" ", mid)
    split_index = left if left != -1 else right
    if split_index == -1:
        split_index = mid
    return text[:split_index] + "\n" + text[split_index:].strip()

def get_font_name():
    """Detect available RushFlow font"""
    for name in ["RushFlow", "RushFlow-Regular"]:
        try:
            TextClip("test", fontsize=10, font=name, color="white")
            return name
        except Exception:
            continue
    return "Arial"  # fallback font

@app.route("/create_video", methods=["POST"])
def create_video():
    try:
        data = request.get_json(force=True)

        # Validate input
        if not all(k in data for k in ["image_url", "audio_url", "lyrics_url"]):
            return jsonify({"error": "Missing required fields: image_url, audio_url, lyrics_url"}), 400

        # Download input files
        image_path = download_file(data["image_url"], f"{uuid.uuid4()}.jpg")
        audio_path = download_file(data["audio_url"], f"{uuid.uuid4()}.mp3")
        lyrics_path = download_file(data["lyrics_url"], f"{uuid.uuid4()}.srt")

        # Load audio & background
        audio_clip = AudioFileClip(audio_path)
        image_clip = ImageClip(image_path).set_duration(audio_clip.duration)

        # Load lyrics
        with open(lyrics_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        subtitles = list(srt.parse(srt_content))

        font_name = get_font_name()

        # Build text clips
        text_clips = []
        for sub in subtitles:
            split_content = split_text(sub.content)
            txt_clip = (
                TextClip(split_content, fontsize=50, color="white", font=font_name, align="center")
                .set_start(sub.start.total_seconds())
                .set_end(sub.end.total_seconds())
                .set_position(("center", "bottom"))
            )
            text_clips.append(txt_clip)

        # Combine video
        video = CompositeVideoClip([image_clip, *text_clips])
        video = video.set_audio(audio_clip)

        # Save output
        output_file = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.mp4")
        video.write_videofile(output_file, fps=30, codec="libx264", audio_codec="aac", verbose=False, logger=None)

        return send_file(output_file, mimetype="video/mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 400  # Always return 400 for predictable handling

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
