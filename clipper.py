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

def analyze_scene_with_gemini(audio_path: Path, api_key: str = None, max_clips: int = 3, status_callback=None, duration_mode: str = None, sequential_story: bool = True) -> list[dict]:
    import config
    keys = config.load_gemini_keys_pool()
    if api_key and api_key not in keys:
        keys.insert(0, api_key)
    if not keys:
        raise RuntimeError("Nenhuma chave do Gemini API configurada.")

    mode = duration_mode or config.load_duration_mode()
    if mode == "monetization":
        dur_instruction = "IMPORTANT: Each clip MUST BE AT LEAST 61.0 SECONDS (target duration: 61 to 75 seconds) for TikTok Creator Rewards monetization qualification. Do not make clips under 61 seconds."
    elif mode == "traction":
        dur_instruction = "Target clip duration: 30 to 45 seconds (punchy, high-retention hook)."
    else: # hybrid
        dur_instruction = "Target clip duration: 70% of clips should be >= 61.0 seconds (61 to 75s for monetization), and 30% between 30 and 45 seconds for viral traction."

    story_instruction = ""
    if max_clips > 1 and sequential_story:
        story_instruction = f"""
STORYTELLING ARC & MULTI-PART CONTINUITY:
The user wants these {max_clips} clips to form a SEQUENTIAL STORYLINE (Part 1, Part 2, ... Part {max_clips}) that hooks viewers and drives them to the creator profile to watch the other parts!
- PART 1: The Hook & Setup (presents the challenge, situation or plan; ends on rising action).
- PART 2: The Escalation & Climax (intense action, near-death, chaos, twist).
- FINAL PART: The Payoff & Cliffhanger (dramatic outcome, reaction + strong reason to follow).
Chronological ordering: Ensure start_seconds of Part 1 < Part 2 < Part 3 in natural progression.
In the captions, include viral multi-part CTAs:
- Part 1 caption MUST conclude with: "👉 Acompanhe o desfecho na PARTE 2 no perfil! #GTA6 #parte1"
- Middle parts conclude with: "🔥 Veja como terminou na PRÓXIMA PARTE no perfil! #GTA6"
- Final part concludes with: "😱 Gostou? Curta e siga para ver mais histórias de GTA 6! #GTA6"
"""

    prompt = f"""You are an expert viral video editor for TikTok, YouTube Shorts, and Instagram Reels.
Analyze this audio from a live stream / gameplay. Identify up to {max_clips} distinct, non-overlapping engaging viral segments.
{dur_instruction}
{story_instruction}
If the audio is short (under 90 seconds), return only 1 best segment.
Ensure segments do NOT overlap (keep at least 3 seconds between segments).

Return ONLY a JSON object adhering to this structure:
{{
  "clips": [
    {{
      "start_seconds": 10.0,
      "end_seconds": 72.0,
      "title": "When the mission went completely off the rails...",
      "caption": "Wait until you see how this ended! 🔥 #GTA6 #GTA #Viral #Gaming #FYP",
      "subtitles": [
        {{"start": 10.0, "end": 12.0, "text": "Are you seeing this?"}},
        {{"start": 12.5, "end": 15.0, "text": "Watch out behind you!"}}
      ]
    }}
  ]
}}
"""
    last_error = None
    for current_key in keys:
        try:
            client = genai.Client(api_key=current_key)
            audio_file = client.files.upload(file=str(audio_path))
            break
        except Exception as e:
            last_error = e
            continue
    else:
        raise RuntimeError(f"Falha ao conectar cliente Gemini com as chaves disponíveis: {last_error}")

    for model in FALLBACK_MODELS:
        for attempt in range(1, 3):
            try:
                if status_callback:
                    status_callback(f"Analisando com {model} (tentativa {attempt}/2)...")
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
                if valid_clips:
                    return valid_clips[:max_clips]
            except Exception as e:
                err_msg = str(e)
                last_error = e
                if "503" in err_msg or "429" in err_msg or "quota" in err_msg.lower() or "resource_exhausted" in err_msg.lower():
                    time.sleep(2 * attempt)
                    continue
                else:
                    break
    
    raise RuntimeError(f"Todos os modelos do Gemini falharam ou limite de cota atingido: {last_error}")

def generate_offline_action_clip(video_path: Path, output_path: Path, title: str = None, duration_seconds: float = 65.0, part_label: str = None) -> dict:
    """Plano B: Gera corte vertical 9:16 de ação centralizado sem depender de IA caso a cota do Gemini acabe."""
    import config
    # Determina duração com base no modo
    mode = config.load_duration_mode()
    dur = 35.0 if mode == "traction" else max(61.5, float(duration_seconds))
    
    # Renderiza vídeo 9:16 com blur usando FFmpeg diretamente
    render_vertical_clip(
        video_path=video_path,
        start_s=5.0,
        end_s=5.0 + dur,
        subtitles=[],
        output_path=output_path,
        part_label=part_label
    )
    
    clip_title = title or "GTA 6 MOMENTO INSANO 🔥"
    clip_caption = config.format_caption(clip_title, "O chat ao vivo foi à loucura com essa cena! #GTA6 #GTA #Viral #Gaming")
    return {
        "start_seconds": 5.0,
        "end_seconds": 5.0 + dur,
        "title": clip_title,
        "caption": clip_caption,
        "path": str(output_path),
        "part_label": part_label,
        "is_fallback": True
    }

def render_clips_batch(video_path: Path, clips_data: list[dict], video_id: str, status_callback=None, on_clip_rendered_callback=None, sequential_story: bool = True) -> list[dict]:
    rendered = []
    total = len(clips_data)
    for idx, clip in enumerate(clips_data):
        part_num = idx + 1
        if status_callback:
            status_callback(f"Renderizando clipe {part_num}/{total}...")
        
        part_label = f"PARTE {part_num} DE {total}" if (total > 1 and sequential_story) else clip.get("part_label")
        output_clip_path = CLIPS_DIR / f"{video_id}_part{part_num}.mp4"
        render_vertical_clip(
            video_path=video_path,
            start_s=clip["start_seconds"],
            end_s=clip["end_seconds"],
            subtitles=clip.get("subtitles", []),
            output_path=output_clip_path,
            part_label=part_label
        )
        clip_item = dict(clip)
        clip_item["path"] = str(output_clip_path)
        clip_item["part"] = part_num
        clip_item["part_label"] = part_label
        rendered.append(clip_item)

        if on_clip_rendered_callback:
            try:
                on_clip_rendered_callback(clip_item)
            except Exception as e:
                print(f"[Clipper] Erro no callback de pós-renderização: {e}")

    return rendered

def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def create_ass_subtitles(subtitles: list, offset_seconds: float, output_path: Path, part_label: str = None) -> Path:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,42,&H0000FFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,0,2,50,50,210,1
Style: PartBadge,Arial,32,&H0000FFFF,&H00000000,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,1,3.0,1,8,40,40,95,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    if part_label:
        events.append(f"Dialogue: 1,0:00:00.00,2:00:00.00,PartBadge,,0,0,0,,📌 {part_label}")

    for item in subtitles:
        # Normalize time relative to clip start
        start = max(0.0, item["start"] - offset_seconds)
        end = max(start + 0.5, item["end"] - offset_seconds)
        text = item["text"].replace("\n", " ").strip()
        events.append(f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{text}")

    output_path.write_text(header + "\n".join(events), encoding="utf-8")
    return output_path

def render_vertical_clip(video_path: Path, start_s: float, end_s: float, subtitles: list, output_path: Path, part_label: str = None) -> Path:
    duration = end_s - start_s
    ass_path = output_path.with_suffix(".ass")
    create_ass_subtitles(subtitles, start_s, ass_path, part_label=part_label)
    duration = end_s - start_s
    ass_path = output_path.with_suffix(".ass")
    create_ass_subtitles(subtitles, start_s, ass_path)

    # Escape path for FFmpeg subtitles filter on Windows
    escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")

    # Filter: blurred background 720x1280 + centered cinema aspect ratio + ASS subtitles + anti-copyright 1.03x
    vf = (
        f"[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:4[bg];"
        f"[0:v]scale=720:-1[fg];"
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
        "-preset", "faster",
        "-crf", "24",
        "-maxrate", "2200k",
        "-bufsize", "4400k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    subprocess.run(cmd, check=True)
    return output_path
