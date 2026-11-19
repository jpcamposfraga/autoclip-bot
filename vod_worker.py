import time
import threading
from pathlib import Path
import config
from config import CLIPS_DIR
import clipper
import telegram_bot

_current_job = {
    "running": False,
    "url": "",
    "max_clips": 2,
    "step_label": "",
    "clips": [],
    "error": None,
    "done": False,
    "completed_at": None
}

def is_vod_job_running() -> bool:
    return _current_job["running"]

def get_vod_job_status() -> dict:
    return dict(_current_job)

def clear_vod_job():
    _current_job["running"] = False
    _current_job["url"] = ""
    _current_job["step_label"] = ""
    _current_job["clips"] = []
    _current_job["error"] = None
    _current_job["done"] = False
    _current_job["completed_at"] = None

def _set_step(label: str):
    _current_job["step_label"] = label

def _run_vod_pipeline(url: str, max_clips: int, auto_send_telegram: bool, sequential_story: bool = True):
    try:
        _current_job["running"] = True
        _current_job["done"] = False
        _current_job["error"] = None
        _current_job["clips"] = []
        _current_job["url"] = url
        _current_job["step_label"] = "1/4 Baixando vídeo em alta definição..."

        video_id = f"vod_{int(time.time())}"
        video_path = clipper.download_youtube(url, video_id=video_id)

        _current_job["step_label"] = "2/4 Extraindo áudio para análise..."
        audio_path = clipper.extract_audio(video_path)

        _current_job["step_label"] = "3/4 IA identificando ganchos virais e sequência narrativa..."
        clips_data = None
        try:
            clips_data = clipper.analyze_scene_with_gemini(
                audio_path,
                max_clips=max_clips,
                status_callback=lambda msg: _set_step(f"3/4 {msg}"),
                sequential_story=sequential_story
            )
        except Exception as e:
            print(f"[VODWorker] Aviso na análise IA ({e}). Usando Plano B...")

        if not clips_data:
            # Plano B: corte heurístico
            out_clip = CLIPS_DIR / f"{video_id}_part1.mp4"
            part_label = "PARTE 1 DE 1" if sequential_story else None
            clip_info = clipper.generate_offline_action_clip(video_path, out_clip, part_label=part_label)
            clip_info["path"] = str(out_clip)
            clip_info["part"] = 1
            if auto_send_telegram:
                tg_ok = telegram_bot.send_clip_to_telegram(str(out_clip), clip_info["caption"])
                clip_info["telegram_sent"] = tg_ok
            clips_data = [clip_info]
            rendered_clips = [clip_info]
        else:
            def _on_clip_done(clip_item):
                if auto_send_telegram:
                    caption = config.format_caption(clip_item.get("title", ""), clip_item.get("caption", ""))
                    tg_ok = telegram_bot.send_clip_to_telegram(clip_item["path"], caption)
                    clip_item["telegram_sent"] = tg_ok

            _current_job["step_label"] = f"4/4 Renderizando {len(clips_data)} corte(s) em 9:16 com badges e legendas..."
            rendered_clips = clipper.render_clips_batch(
                video_path=video_path,
                clips_data=clips_data,
                video_id=video_id,
                status_callback=lambda msg: _set_step(f"4/4 {msg}"),
                on_clip_rendered_callback=_on_clip_done,
                sequential_story=sequential_story
            )

        _current_job["clips"] = rendered_clips
        tg_count = sum(1 for c in rendered_clips if c.get("telegram_sent"))
        if auto_send_telegram:
            if tg_count == len(rendered_clips):
                _current_job["step_label"] = f"✅ {len(rendered_clips)} corte(s) concluído(s) e entregues no Telegram!"
            else:
                _current_job["step_label"] = f"✅ {len(rendered_clips)} corte(s) concluído(s)! ({tg_count}/{len(rendered_clips)} entregues no Telegram)"
        else:
            _current_job["step_label"] = f"✅ {len(rendered_clips)} corte(s) concluído(s) com sucesso!"
        _current_job["done"] = True
        _current_job["completed_at"] = time.strftime("%H:%M:%S")

    except Exception as e:
        _current_job["error"] = str(e)
        _current_job["step_label"] = f"❌ Erro: {e}"
    finally:
        _current_job["running"] = False

def start_vod_job(url: str, max_clips: int = 2, auto_send_telegram: bool = True, sequential_story: bool = True) -> tuple[bool, str]:
    if _current_job["running"]:
        return False, "Já existe um processamento de VOD em andamento em segundo plano."

    t = threading.Thread(
        target=_run_vod_pipeline,
        args=(url, max_clips, auto_send_telegram, sequential_story),
        daemon=True
    )
    t.start()
    return True, "Processamento de VOD iniciado em segundo plano! Você pode navegar entre as abas livremente."
