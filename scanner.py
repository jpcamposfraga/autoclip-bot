import yt_dlp
import db

DEFAULT_CHANNELS = [
    "https://www.youtube.com/@Movieclips/videos",
    "https://www.youtube.com/@BingeSociety/videos",
    "https://www.youtube.com/@scenecity7000/videos"
]

def get_next_unprocessed_scene(channels: list[str] = None, min_duration: int = 90, max_duration: int = 480) -> dict | None:
    if not channels:
        channels = DEFAULT_CHANNELS

    ydl_opts = {
        "extract_flat": True,
        "playlistend": 15,
        "quiet": True,
        "no_warnings": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for channel in channels:
            try:
                info = ydl.extract_info(channel, download=False)
                entries = info.get("entries") or []
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get("id")
                    if not video_id:
                        continue

                    # Check if already processed
                    if db.is_source_processed(video_id):
                        continue

                    duration = entry.get("duration")
                    # If duration is available, filter 1.5min to 8min
                    if duration and (duration < min_duration or duration > max_duration):
                        continue

                    title = entry.get("title", "Movie Scene")
                    return {
                        "id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": title,
                        "duration": duration,
                        "channel": channel
                    }
            except Exception as e:
                print(f"[Scanner] Erro ao varrer canal {channel}: {e}")
                continue

    return None
