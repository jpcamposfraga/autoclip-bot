import time
import threading
from pathlib import Path
from config import CLIPS_DIR, load_gemini_key, format_caption, load_delivery_channel
import live_stream
import chat_spike
import clipper
import email_sender
import telegram_bot

_current_session = {
    "active": False,
    "stream_url": "",
    "p_stream": None,
    "p_ffmpeg": None,
    "detector": None,
    "clips_count": 0,
    "last_clip_title": "",
    "on_clip_callback": None
}

def is_live_session_active() -> bool:
    return _current_session["active"]

def get_live_session_status() -> dict:
    detector = _current_session["detector"]
    mps = detector.current_mps if detector else 0.0
    return {
        "active": _current_session["active"],
        "stream_url": _current_session["stream_url"],
        "current_mps": mps,
        "clips_count": _current_session["clips_count"],
        "last_clip_title": _current_session["last_clip_title"]
    }

def _process_spike_job(event_data):
    print(f"[LiveOrchestrator] Processando pico de chat (MPS: {event_data.get('mps', 0):.1f})...")
    # Aguarda 12 segundos para a reação do streamer entrar completamente no buffer circular
    time.sleep(12)

    video_id = f"live_gta6_{int(time.time())}"
    raw_snippet = live_stream.LIVE_BUFFER_DIR / f"{video_id}_raw.mp4"

    try:
        # 1. Extrai os últimos 60 segundos do buffer
        live_stream.extract_recent_buffer(raw_snippet, num_chunks=6)

        # 2. Extrai áudio para o Gemini
        audio_path = clipper.extract_audio(raw_snippet)

        # 3. Analisa momento viral e ganchos de fala com Gemini
        gemini_key = load_gemini_key()
        clips_data = clipper.analyze_scene_with_gemini(audio_path, gemini_key, max_clips=1)
        if not clips_data:
            print("[LiveOrchestrator] IA não identificou fala clara no trecho.")
            return

        clip_info = clips_data[0]
        output_clip_path = CLIPS_DIR / f"{video_id}_vertical.mp4"

        # 4. Renderiza em 9:16 com fundo desfocado e legendas animadas
        clipper.render_vertical_clip(
            video_path=raw_snippet,
            start_s=clip_info.get("start_seconds", 0.0),
            end_s=clip_info.get("end_seconds", 55.0),
            subtitles=clip_info.get("subtitles", []),
            output_path=output_clip_path
        )

        title = clip_info.get("title", "GTA 6 Live Moment")
        formatted_caption = format_caption(title, clip_info.get("caption", "#GTA6 #GTA #Viral"))

        # 5. Entrega multi-canal (E-mail e/ou Telegram)
        delivery_mode = load_delivery_channel()

        # Envio por E-mail
        if delivery_mode in ["email", "both"]:
            ok, msg = email_sender.send_clip_by_email(str(output_clip_path), title, formatted_caption)
            print(f"[LiveOrchestrator] Envio por E-mail: {msg}")

        # Envio por Telegram
        if delivery_mode in ["telegram", "both"]:
            telegram_bot.send_clip_to_telegram(str(output_clip_path), formatted_caption)

        _current_session["clips_count"] += 1
        _current_session["last_clip_title"] = title

        if _current_session["on_clip_callback"]:
            _current_session["on_clip_callback"]({
                "title": title,
                "caption": formatted_caption,
                "path": str(output_clip_path)
            })

    except Exception as e:
        print(f"[LiveOrchestrator] Erro ao processar pico da live: {e}")
    finally:
        # Limpa o arquivo temporário bruto
        if raw_snippet.exists():
            try:
                raw_snippet.unlink()
            except Exception:
                pass

def start_live_session(stream_url: str, on_clip_callback=None) -> tuple[bool, str]:
    if _current_session["active"]:
        return False, "Já existe uma sessão de monitoramento de live em andamento."

    try:
        p_stream, p_ffmpeg = live_stream.start_circular_buffer(stream_url)
        time.sleep(2) # Aguarda inicialização do processo
        if p_stream.poll() is not None:
            return False, "Falha ao iniciar captura da live via streamlink (verifique a URL)."

        detector = chat_spike.ChatSpikeDetector(stream_url)
        detector.start(on_spike_callback=lambda evt: threading.Thread(target=_process_spike_job, args=(evt,), daemon=True).start())

        _current_session["active"] = True
        _current_session["stream_url"] = stream_url
        _current_session["p_stream"] = p_stream
        _current_session["p_ffmpeg"] = p_ffmpeg
        _current_session["detector"] = detector
        _current_session["on_clip_callback"] = on_clip_callback

        return True, "Sessão de monitoramento ao vivo iniciada com sucesso!"
    except Exception as e:
        return False, f"Erro ao iniciar sessão: {e}"

def stop_live_session():
    if not _current_session["active"]:
        return

    if _current_session["detector"]:
        _current_session["detector"].stop()

    live_stream.stop_circular_buffer(_current_session["p_stream"], _current_session["p_ffmpeg"])

    _current_session["active"] = False
    _current_session["stream_url"] = ""
    _current_session["p_stream"] = None
    _current_session["p_ffmpeg"] = None
    _current_session["detector"] = None
