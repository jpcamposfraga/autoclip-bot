import time
import threading
from datetime import datetime, timedelta
import db
import config
import poster

_scheduler_thread = None
_stop_event = threading.Event()

def get_today_post_count() -> int:
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    with db.get_connection() as conn:
        cur = conn.execute("""
        SELECT COUNT(*) as cnt FROM posts_queue 
        WHERE status = 'completed' AND date(posted_at) = date('now')
        """)
        row = cur.fetchone()
        return row["cnt"] if row else 0

def get_last_posted_time() -> datetime | None:
    with db.get_connection() as conn:
        cur = conn.execute("""
        SELECT posted_at FROM posts_queue 
        WHERE status = 'completed' AND posted_at IS NOT NULL
        ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row and row["posted_at"]:
            try:
                return datetime.fromisoformat(row["posted_at"])
            except Exception:
                pass
    return None

def process_due_posts_once(force: bool = False) -> str:
    cfg = config.load_schedule_config()
    max_per_day = cfg.get("posts_per_day", 3)
    interval_hours = cfg.get("interval_hours", 3.0)

    # Check daily quota (skip if force=True)
    today_posts = get_today_post_count()
    if not force and today_posts >= max_per_day:
        return f"Limite diário atingido ({today_posts}/{max_per_day} posts)."

    # Check interval (skip if force=True)
    last_post = get_last_posted_time()
    if not force and last_post:
        elapsed = datetime.now() - last_post
        if elapsed < timedelta(hours=interval_hours):
            remaining = timedelta(hours=interval_hours) - elapsed
            rem_minutes = int(remaining.total_seconds() // 60)
            return f"Aguardando intervalo mínimo ({rem_minutes} minutos restantes)."

    pending = db.get_pending_posts()
    if not pending:
        return "Nenhuma postagem pendente no momento."

    post = pending[0]
    post_id = post["id"]
    db.update_post_status(post_id, "processing")

    try:
        formatted_caption = config.format_caption(post["title"], post["caption"])
        success = poster.post_clip(
            device_serial=post["device_serial"],
            platform=post["platform"],
            video_path=post["clip_path"],
            title=post["title"],
            caption=formatted_caption
        )
        if success:
            db.update_post_status(post_id, "completed")
            return f"Post #{post_id} publicado com sucesso em {post['platform']}!"
        else:
            db.update_post_status(post_id, "failed", error_msg="Robô não conseguiu confirmar publicação na tela.")
            return f"Post #{post_id} falhou ao tentar interagir com a tela do app."
    except Exception as e:
        err = str(e)
        db.update_post_status(post_id, "failed", error_msg=err)
        return f"Erro ao processar post #{post_id}: {err}"

def _worker_loop():
    while not _stop_event.is_set():
        try:
            process_due_posts_once()
        except Exception as e:
            print(f"[Scheduler Error]: {e}")
        time.sleep(30)

def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _stop_event.clear()
        _scheduler_thread = threading.Thread(target=_worker_loop, daemon=True)
        _scheduler_thread.start()
