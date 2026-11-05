import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import db
import config
import poster
import scanner
import clipper
import telegram_bot

_scheduler_thread = None
_stop_event = threading.Event()
_triggered_slots = set()

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

def run_autonomous_pipeline(status_callback=None) -> dict:
    if status_callback:
        status_callback("1/5 Buscando nova cena nos canais monitorados do YouTube...")

    channels = config.load_monitored_channels()
    scene = scanner.get_next_unprocessed_scene(channels=channels)
    if not scene:
        return {"success": False, "error": "Nenhuma cena nova não-processada encontrada nos canais monitorados."}

    video_id = f"clip_{int(time.time())}"

    # 1. Download
    if status_callback:
        status_callback(f"2/5 Baixando cena: {scene['title'][:40]}...")
    video_path = clipper.download_youtube(scene["url"], video_id=video_id)

    # 2. Extract Audio
    if status_callback:
        status_callback("3/5 Extraindo áudio para análise...")
    audio_path = clipper.extract_audio(video_path)

    # 3. Analyze with Gemini
    if status_callback:
        status_callback("4/5 IA identificando gancho viral e gerando legendas...")
    gemini_key = config.load_gemini_key()
    clips_data = clipper.analyze_scene_with_gemini(audio_path, gemini_key, max_clips=1)
    if not clips_data:
        return {"success": False, "error": "A IA não conseguiu identificar um segmento viral coerente."}

    # 4. Render 9:16
    if status_callback:
        status_callback("5/5 Renderizando vídeo 9:16 com legendas animadas...")
    rendered_clips = clipper.render_clips_batch(video_path, clips_data, video_id)
    if not rendered_clips:
        return {"success": False, "error": "Falha na renderização do vídeo vertical."}

    clip = rendered_clips[0]
    final_caption = config.format_caption(clip.get("title", ""), clip.get("caption", ""))

    # 5. Send to Telegram
    telegram_cfg = config.load_telegram_config()
    sent_telegram = False
    if telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
        if status_callback:
            status_callback("Enviando vídeo para o seu Telegram...")
        sent_telegram = telegram_bot.send_clip_to_telegram(
            video_path=clip["path"],
            caption=final_caption,
            bot_token=telegram_cfg["bot_token"],
            chat_id=telegram_cfg["chat_id"]
        )

    # 6. Mark scene as processed to prevent duplicates
    db.mark_source_processed(scene["id"], scene["title"], scene.get("channel", ""))

    return {
        "success": True,
        "title": clip.get("title", ""),
        "caption": final_caption,
        "path": clip["path"],
        "source_url": scene["url"],
        "telegram_sent": sent_telegram
    }

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
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today_date_str = now.strftime("%Y-%m-%d")

        # 1. Check Peak Hours for Autonomous Sourcing & Telegram Delivery
        peak_hours = config.load_peak_hours()
        for hour in peak_hours:
            slot_key = f"{today_date_str}_{hour}"
            if current_time_str == hour and slot_key not in _triggered_slots:
                _triggered_slots.add(slot_key)
                print(f"[Scheduler] Horário de pico atingido ({hour})! Iniciando pipeline autônomo...")
                try:
                    run_autonomous_pipeline()
                except Exception as e:
                    print(f"[Scheduler] Falha no pipeline de horário de pico: {e}")

        # 2. Check Queue for Emulator Posts
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
