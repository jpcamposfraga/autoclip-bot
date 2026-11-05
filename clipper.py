import json
import subprocess
import time
from pathlib import Path
from google import genai
from google.genai import types
import yt_dlp
from config import FFMPEG_BIN, DOWNLOADS_DIR, CLIPS_DIR

def download_youtube(url: str, video_id: str = None) -> Path:
    if not video_id:
        video_id = f"yt_{int(time.time())}"
    output_path = DOWNLOADS_DIR / f"{video_id}.mp4"
    
    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "overwrites": True,
        "ffmpeg_location": str(Path(FFMPEG_BIN).parent),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return output_path

def extract_audio(video_path: Path) -> Path:
    audio_path = video_path.with_suffix(".mp3")
    cmd = [
        FFMPEG_BIN, "-y", "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame", "-b:a", "64k",
        str(audio_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return audio_path

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-pro"
]

def analyze_scene_with_gemini(audio_path: Path, api_key: str, max_clips: int = 3, status_callback=None) -> list[dict]:
    client = genai.Client(api_key=api_key)
    audio_file = client.files.upload(file=str(audio_path))
    
    prompt = f"""You are an expert viral movie clip editor for TikTok, YouTube Shorts, and Instagram Reels.
Analyze this movie scene audio. Identify up to {max_clips} distinct, non-overlapping engaging viral segments (each 30 to 60 seconds long).
If the audio is short (under 90 seconds), return only 1 segment.
Ensure segments do NOT overlap (keep at least 3 seconds between segments).

Return ONLY a JSON object adhering to this structure:
{{
  "clips": [
    {{
      "start_seconds": 12.5,
      "end_seconds": 58.0,
      "title": "When he realized who was behind the door...",
      "caption": "Unbelievable scene from the movie. Wait for the end! #movies #cinema #viral #fyp",
      "subtitles": [
        {{"start": 12.5, "end": 14.0, "text": "Who is there?"}},
        {{"start": 14.1, "end": 16.2, "text": "You already know."}}
      ]
    }}
  ]
}}
"""
    last_error = None
    for model in FALLBACK_MODELS:
        for attempt in range(1, 4):
            try:
                if status_callback:
                    status_callback(f"Analisando com {model} (tentativa {attempt}/3)...")
                response = client.models.generate_content(
                    model=model,
                    contents=[audio_file, prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                data = json.loads(response.text)
                if isinstance(data, dict) and "clips" in data and isinstance(data["clips"], list):
                    clips = data["clips"]
                elif isinstance(data, list):
                    clips = data
                elif isinstance(data, dict) and "start_seconds" in data:
                    clips = [data]
                else:
                    clips = []
                
                # Filter out invalid segments
                valid_clips = [c for c in clips if c.get("end_seconds", 0) > c.get("start_seconds", 0)]
                return valid_clips[:max_clips]
            except Exception as e:
                err_msg = str(e)
                last_error = e
                if "503" in err_msg or "429" in err_msg or "high demand" in err_msg.lower():
                    time.sleep(2 * attempt)
                    continue
                else:
                    break
    
    raise RuntimeError(f"Todos os modelos do Gemini falharam ou estão indisponíveis temporariamente: {last_error}")

def render_clips_batch(video_path: Path, clips_data: list[dict], video_id: str, status_callback=None) -> list[dict]:
    rendered = []
    total = len(clips_data)
    for idx, clip in enumerate(clips_data):
        part_num = idx + 1
        if status_callback:
            status_callback(f"Renderizando clipe {part_num}/{total}...")
        
        output_clip_path = CLIPS_DIR / f"{video_id}_part{part_num}.mp4"
        render_vertical_clip(
            video_path=video_path,
            start_s=clip["start_seconds"],
            end_s=clip["end_seconds"],
            subtitles=clip.get("subtitles", []),
            output_path=output_clip_path
        )
        clip_item = dict(clip)
        clip_item["path"] = str(output_clip_path)
        clip_item["part"] = part_num
        rendered.append(clip_item)
    return rendered

def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def create_ass_subtitles(subtitles: list, offset_seconds: float, output_path: Path) -> Path:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H0000FFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,80,80,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for item in subtitles:
        # Normalize time relative to clip start
        start = max(0.0, item["start"] - offset_seconds)
        end = max(start + 0.5, item["end"] - offset_seconds)
        text = item["text"].replace("\n", " ").strip()
        events.append(f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{text}")

    output_path.write_text(header + "\n".join(events), encoding="utf-8")
    return output_path

def render_vertical_clip(video_path: Path, start_s: float, end_s: float, subtitles: list, output_path: Path) -> Path:
    duration = end_s - start_s
    ass_path = output_path.with_suffix(".ass")
    create_ass_subtitles(subtitles, start_s, ass_path)

    # Escape path for FFmpeg subtitles filter on Windows
    escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")

    # Filter: blurred background 1080x1920 + centered cinema aspect ratio + ASS subtitles + anti-copyright 1.03x
    vf = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        f"[0:v]scale=1080:-1[fg];"
        f"[bg][fg]overlay=0:(H-h)/2,"
        f"subtitles='{escaped_ass}',"
        f"setpts=PTS/1.03[v];"
        f"[0:a]atempo=1.03[a]"
    )

    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", str(start_s),
        "-t", str(duration),
        "-i", str(video_path),
        "-filter_complex", vf,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_path)
    ]
    subprocess.run(cmd, check=True)
    return output_path
