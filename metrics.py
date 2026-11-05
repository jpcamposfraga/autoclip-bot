import yt_dlp
import db

def fetch_public_video_metrics(url: str) -> dict:
    if not url:
        return {"views": 0, "likes": 0, "comments": 0}
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": False
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "views": int(info.get("view_count") or 0),
                "likes": int(info.get("like_count") or 0),
                "comments": int(info.get("comment_count") or 0)
            }
    except Exception as e:
        print(f"Erro ao extrair métricas públicas de {url}: {e}")
        return {"views": 0, "likes": 0, "comments": 0}

def refresh_metrics_for_post(post_id: int, public_url: str):
    if not public_url:
        return
    metrics = fetch_public_video_metrics(public_url)
    db.record_metric(
        post_id=post_id,
        views=metrics["views"],
        likes=metrics["likes"],
        comments=metrics["comments"]
    )
