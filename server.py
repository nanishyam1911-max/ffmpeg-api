import os
import tempfile
import subprocess
import requests
import whisper
import json
import re
from flask import Flask, request, send_file, jsonify
import logging
import sys
import signal
from contextlib import contextmanager
from datetime import timedelta

app = Flask(__name__)

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load Whisper model on startup
app.logger.info("Loading Whisper model...")
try:
    whisper_model = whisper.load_model("base")
    app.logger.info("Whisper model loaded successfully")
except Exception as e:
    app.logger.error(f"Failed to load Whisper model: {e}")
    whisper_model = None

# Timeout handler for long-running processes
@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    if hasattr(signal, 'SIGALRM'):  # Unix systems only
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        # Windows fallback - no timeout
        yield

def convert_dropbox_url(url):
    """Convert Dropbox share URL to direct download URL."""
    if 'dropbox.com' in url and '?dl=0' in url:
        return url.replace('?dl=0', '?dl=1')
    elif 'dropbox.com' in url and '?dl=1' not in url:
        return url + ('&dl=1' if '?' in url else '?dl=1')
    return url

def download_temp(url, suffix, max_size_mb=50):
    """Download a file from URL into a temporary local file with size limit."""
    app.logger.info(f"Downloading: {url}")
    try:
        download_url = convert_dropbox_url(url)
        app.logger.info(f"Using download URL: {download_url}")
        
        resp = requests.get(download_url, timeout=120, stream=True)
        resp.raise_for_status()
        
        content_length = resp.headers.get('content-length')
        if content_length and int(content_length) > max_size_mb * 1024 * 1024:
            raise ValueError(f"File too large: {int(content_length) / (1024*1024):.1f}MB > {max_size_mb}MB")
        
        fd, path = tempfile.mkstemp(suffix=suffix)
        total_size = 0
        max_size_bytes = max_size_mb * 1024 * 1024
        
        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > max_size_bytes:
                        os.remove(path)
                        raise ValueError(f"File too large during download: > {max_size_mb}MB")
                    f.write(chunk)
        
        app.logger.info(f"Downloaded {total_size / (1024*1024):.1f}MB")
        return path
    except requests.RequestException as e:
        app.logger.error(f"Failed to download {url}: {e}")
        raise

def fetch_lyrics(lyrics_input, max_size_mb=5):
    """Return lyrics text, either from raw text or by downloading from URL/file."""
    if lyrics_input.startswith("http://") or lyrics_input.startswith("https://"):
        app.logger.info(f"Fetching lyrics from URL: {lyrics_input}")
        try:
            download_url = convert_dropbox_url(lyrics_input)
            resp = requests.get(download_url, timeout=60, stream=True)
            resp.raise_for_status()
            
            content_length = resp.headers.get('content-length')
            if content_length and int(content_length) > max_size_mb * 1024 * 1024:
                raise ValueError(f"Lyrics file too large: {int(content_length) / (1024*1024):.1f}MB > {max_size_mb}MB")
            
            content = ""
            total_size = 0
            max_size_bytes = max_size_mb * 1024 * 1024
            
            for chunk in resp.iter_content(chunk_size=8192, decode_unicode=True):
                if chunk:
                    total_size += len(chunk.encode('utf-8'))
                    if total_size > max_size_bytes:
                        raise ValueError(f"Lyrics file too large during download: > {max_size_mb}MB")
                    content += chunk
            
            app.logger.info(f"Downloaded lyrics file: {total_size / 1024:.1f}KB")
            return content.strip()
            
        except requests.RequestException as e:
            app.logger.error(f"Failed to fetch lyrics from {lyrics_input}: {e}")
            raise
    else:
        app.logger.info("Using raw lyrics text")
        return lyrics_input.strip()

def get_whisper_timestamps(audio_path):
    """Extract timestamps using Whisper for better synchronization."""
    if not whisper_model:
        app.logger.warning("Whisper model not available, using fallback timing")
        return None
    
    try:
        app.logger.info("Extracting timestamps with Whisper...")
        result = whisper_model.transcribe(audio_path)
        
        segments = []
        for segment in result['segments']:
            segments.append({
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text'].strip()
            })
        
        app.logger.info(f"Extracted {len(segments)} segments with Whisper")
        return segments
    except Exception as e:
        app.logger.error(f"Whisper processing failed: {e}")
        return None

def split_long_lines(text, max_chars=50):
    """Split long lyrics lines into smaller chunks for better display."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) <= max_chars:
            current_line = current_line + " " + word if current_line else word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def create_srt_with_whisper(lyrics_text, whisper_segments=None, audio_duration=None):
    """Create SRT subtitle file with Whisper timestamps or smart timing."""
    fd, srt_path = tempfile.mkstemp(suffix=".srt")
    
    # Clean and split lyrics
    original_lines = [line.strip() for line in lyrics_text.split("\n") if line.strip()]
    
    if not original_lines:
        raise ValueError("No lyrics content found")
    
    # Process long lines
    processed_lines = []
    for line in original_lines:
        if len(line) > 50:  # If line is too long
            split_lines = split_long_lines(line, max_chars=50)
            processed_lines.extend(split_lines)
        else:
            processed_lines.append(line)
    
    app.logger.info(f"Processed {len(original_lines)} original lines into {len(processed_lines)} display lines")
    
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if whisper_segments and len(whisper_segments) > 0:
            # Use Whisper timing
            app.logger.info("Using Whisper-based timing")
            
            # Map lyrics to whisper segments
            lyrics_index = 0
            for idx, segment in enumerate(whisper_segments):
                if lyrics_index >= len(processed_lines):
                    break
                    
                start_time = segment['start']
                end_time = segment['end']
                
                # Add small gap between segments for readability
                if idx < len(whisper_segments) - 1:
                    gap = 0.2  # 200ms gap
                    end_time = min(end_time, whisper_segments[idx + 1]['start'] - gap)
                
                start_minutes = int(start_time // 60)
                start_seconds = int(start_time % 60)
                start_milliseconds = int((start_time % 1) * 1000)
                
                end_minutes = int(end_time // 60)
                end_seconds = int(end_time % 60)
                end_milliseconds = int((end_time % 1) * 1000)
                
                f.write(f"{lyrics_index + 1}\n")
                f.write(f"{start_minutes:02d}:{start_seconds:02d}:{start_milliseconds:03d} --> ")
                f.write(f"{end_minutes:02d}:{end_seconds:02d}:{end_milliseconds:03d}\n")
                f.write(f"{processed_lines[lyrics_index]}\n\n")
                
                lyrics_index += 1
        else:
            # Fallback to duration-based timing
            app.logger.info("Using duration-based timing")
            
            if audio_duration:
                time_per_line = audio_duration / len(processed_lines)
            else:
                time_per_line = 3.0  # Default 3 seconds per line
            
            # Add small gaps between lines
            gap_time = 0.2  # 200ms gap
            effective_time = time_per_line - gap_time
            
            for idx, line in enumerate(processed_lines):
                start_time = idx * time_per_line
                end_time = start_time + effective_time
                
                start_minutes = int(start_time // 60)
                start_seconds = int(start_time % 60)
                start_milliseconds = int((start_time % 1) * 1000)
                
                end_minutes = int(end_time // 60)
                end_seconds = int(end_time % 60)
                end_milliseconds = int((end_time % 1) * 1000)
                
                f.write(f"{idx + 1}\n")
                f.write(f"{start_minutes:02d}:{start_seconds:02d}:{start_milliseconds:03d} --> ")
                f.write(f"{end_minutes:02d}:{end_seconds:02d}:{end_milliseconds:03d}\n")
                f.write(f"{line}\n\n")
    
    return srt_path

def get_audio_duration(audio_path):
    """Get audio duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        app.logger.info(f"Audio duration: {duration:.2f} seconds")
        return duration
    except (subprocess.CalledProcessError, ValueError) as e:
        app.logger.warning(f"Could not get audio duration: {e}")
        return None

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "ok": True,
        "whisper_available": whisper_model is not None,
        "ffmpeg_available": subprocess.run(["ffmpeg", "-version"], 
                                         capture_output=True).returncode == 0
    })

@app.route("/generate", methods=["POST"])
def generate_video():
    """Generate video with synchronized lyrics using Dropbox URLs."""
    audio_path = img_path = srt_path = out_path = None
    try:
        with timeout(600):  # 10 minute timeout for complex processing
            data = request.get_json(force=True)
            app.logger.info(f"Received request with keys: {list(data.keys())}")
            
            audio_url = data.get("audio")
            image_url = data.get("image")
            lyrics_input = data.get("lyrics")
            use_whisper = data.get("use_whisper", True)  # Default to using Whisper
            
            if not all([audio_url, image_url, lyrics_input]):
                app.logger.error("Missing required parameters")
                return jsonify({
                    "error": "Missing required parameters",
                    "required": ["audio", "image", "lyrics"],
                    "received": list(data.keys())
                }), 400
            
            # Validate URLs
            for url_name, url in [("audio", audio_url), ("image", image_url)]:
                if not (url.startswith("http://") or url.startswith("https://")):
                    return jsonify({"error": f"Invalid {url_name} URL: {url}"}), 400
            
            app.logger.info("Starting downloads...")
            
            # Download files with Dropbox support
            audio_path = download_temp(audio_url, ".mp3", max_size_mb=50)
            img_path = download_temp(image_url, ".png", max_size_mb=15)
            
            app.logger.info("Processing lyrics...")
            lyrics_text = fetch_lyrics(lyrics_input, max_size_mb=5)
            
            if not lyrics_text.strip():
                return jsonify({"error": "Empty lyrics content"}), 400
            
            # Get audio duration
            audio_duration = get_audio_duration(audio_path)
            
            # Extract Whisper timestamps if requested and available
            whisper_segments = None
            if use_whisper and whisper_model:
                whisper_segments = get_whisper_timestamps(audio_path)
            
            # Create SRT file with advanced timing
            srt_path = create_srt_with_whisper(lyrics_text, whisper_segments, audio_duration)
            app.logger.info("SRT file created with advanced timing")
            
            # Output video file
            fd, out_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            
            # Check for RushFlow font (use .otf now)
            font_path = os.path.join(os.getcwd(), "fonts", "RushFlow.otf")
            if os.path.exists(font_path):
                font_style = f"FontName=RushFlow,FontFile={font_path}"
                app.logger.info("Using RushFlow font")
            else:
                font_style = "FontName=Arial"
                app.logger.warning("RushFlow.otf not found, using Arial")
 
            # Advanced subtitle styling for better readability
            subtitle_style = (
                f"force_style='{font_style},"
                "FontSize=32,"
                "PrimaryColour=&HFFFFFF&,"  # White text
                "OutlineColour=&H000000&,"  # Black outline
                "BackColour=&H80000000&,"   # Semi-transparent background
                "Outline=3,"                # Thick outline
                "Shadow=2,"                 # Shadow for depth
                "Alignment=2,"              # Bottom center alignment
                "MarginV=50'"               # Bottom margin
            )
            
            # Advanced FFmpeg command for high-quality output
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-i", audio_path,
                "-vf", f"subtitles={srt_path}:{subtitle_style}",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-preset", "medium",        # Good quality/speed balance
                "-crf", "20",               # High quality
                "-maxrate", "4M",           # Max bitrate
                "-bufsize", "8M",           # Buffer size
                "-movflags", "+faststart",  # Web optimization
                out_path
            ]
            
            app.logger.info("Starting video generation...")
            
            try:
                result = subprocess.run(
                    cmd, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    timeout=480  # 8 minute timeout for ffmpeg
                )
                app.logger.info("Video generation completed successfully")
            except subprocess.TimeoutExpired:
                app.logger.error("FFmpeg process timed out")
                return jsonify({"error": "Video generation timed out"}), 500
            except subprocess.CalledProcessError as e:
                app.logger.error(f"FFmpeg failed: {e.stderr}")
                return jsonify({
                    "error": "Video generation failed", 
                    "details": e.stderr[-1000:]  # Last 1000 chars of error
                }), 500
            
            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                app.logger.error("Output video is empty or missing")
                return jsonify({"error": "Video generation failed - empty output"}), 500
            
            file_size = os.path.getsize(out_path) / (1024 * 1024)
            app.logger.info(f"Video generated successfully: {file_size:.1f}MB")
            
            return send_file(
                out_path, 
                mimetype="video/mp4", 
                as_attachment=True, 
                download_name="lyrics_video.mp4"
            )
    
    except TimeoutError as e:
        app.logger.error(f"Request timed out: {e}")
        return jsonify({"error": "Request timed out", "details": str(e)}), 408
    except ValueError as e:
        app.logger.error(f"Invalid input: {e}")
        return jsonify({"error": "Invalid input", "details": str(e)}), 400
    except requests.RequestException as e:
        app.logger.error(f"Network error: {e}")
        return jsonify({"error": "Network error", "details": str(e)}), 502
    except Exception as e:
        app.logger.exception("Unexpected error")
        return jsonify({
            "error": "Unexpected server error", 
            "details": str(e),
            "type": type(e).__name__
        }), 500
    finally:
        # Cleanup temporary files
        for path in [audio_path, img_path, srt_path, out_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    app.logger.debug(f"Cleaned up: {os.path.basename(path)}")
                except Exception as cleanup_error:
                    app.logger.warning(f"Cleanup failed for {path}: {cleanup_error}")

if __name__ == "__main__":
    # Production settings for Render deployment
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
