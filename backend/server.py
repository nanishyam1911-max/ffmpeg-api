from flask import Flask, request, send_file, jsonify
# Split long lines into 2 lines
def split_text(text, max_len=40):
if len(text) <= max_len:
return text
mid = len(text) // 2
left = text.rfind(" ", 0, mid)
right = text.find(" ", mid)
idx = left if left != -1 else right
if idx == -1:
idx = mid
return text[:idx] + "\n" + text[idx:].strip()


# Find usable RushFlow font name or fallback
def detect_font():
for name in ["RushFlow", "RushFlow-Regular"]:
try:
TextClip("test", fontsize=10, font=name, color="white")
return name
except Exception:
continue
return "Arial"


@app.route("/create_video", methods=["POST"])
def create_video():
try:
data = request.get_json(force=True)
# Accept url fields or 'upload' boolean to handle multipart (not implemented here)
if not data:
return jsonify({"error": "Empty request body"}), 400
required = ["image_url", "audio_url", "lyrics_url"]
if not all(k in data for k in required):
return jsonify({"error": "Missing fields. Provide image_url, audio_url, lyrics_url."}), 400


image_url = data["image_url"]
audio_url = data["audio_url"]
lyrics_url = data["lyrics_url"]


image_path = download_file(image_url, f"{uuid.uuid4()}.img")
audio_path = download_file(audio_url, f"{uuid.uuid4()}.mp3")
lyrics_path = download_file(lyrics_url, f"{uuid.uuid4()}.srt")


# Load audio and set image duration
audio_clip = AudioFileClip(audio_path)
image_clip = ImageClip(image_path).set_duration(audio_clip.duration)


# Read and parse SRT
with open(lyrics_path, "r", encoding="utf-8") as f:
srt_content = f.read()
subs = list(srt.parse(srt_content))


font_name = detect_font()


text_clips = []
for s in subs:
txt = split_text(s.content)
tc = (TextClip(txt, fontsize=50, font=font_name, color="white", align="center")
.set_start(s.start.total_seconds())
.set_end(s.end.total_seconds())
.set_position(("center", "bottom")))
text_clips.append(tc)


video = CompositeVideoClip([image_clip, *text_clips]).set_audio(audio_clip)


out_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")
# suppress verbose logging from moviepy
video.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", verbose=False, logger=None)


return send_file(out_path, mimetype="video/mp4")


except Exception as e:
return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
# Not used in production; production run uses gunicorn
app.run(host="0.0.0.0", port=5000)
