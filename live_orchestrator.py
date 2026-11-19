import time
import threading
from pathlib import Path
from config import CLIPS_DIR, format_caption, load_delivery_channel
import config
import live_stream
import chat_spike
import clipper
import email_sender
import telegram_bot

MAX_SESSIONS = 3

_sessions = {
    1: {"active": False, "stream_url": "", "p_stream": None, "p_ffmpeg": None, "detector": None, "clips_count": 0, "last_clip_title": "", "on_clip_callback": None, "started_at": 0},
    2: {"active": False, "stream_url": "", "p_stream": None, "p_ffmpeg": None, "detector": None, "clips_count": 0, "last_clip_title": "", "on_clip_callback": None, "started_at": 0},
    3: {"active": False, "stream_url": "", "p_stream": None, "p_ffmpeg": None, "detector": None, "clips_count": 0, "last_clip_title": "", "on_clip_callback": None, "started_at": 0},
}

_watchdog_thread = None
_watchdog_lock = threading.Lock()

def _ensure_watchdog_started():
    global _watchdog_thread
    with _watchdog_lock:
        if _watchdog_thread is None or not _watchdog_thread.is_alive():
            _watchdog_thread = threading.Thread(target=_live_watchdog_loop, daemon=True)
            _watchdog_thread.start()

def _live_watchdog_loop():
    while True:
        time.sleep(4)
        for sid, s in list(_sessions.items()):
            if not s["active"]:
                continue
            if time.time() - s.get("started_at", 0) < 10:
                continue

            p_stream = s.get("p_stream")
            if p_stream and p_stream.poll() is not None:
                stream_url = s.get("stream_url", "")
                print(f"[LiveOrchestrator] [Live #{sid}] Transmissão encerrada pelo streamer (código {p_stream.returncode}).")
                stop_live_session(sid, manual=False)

                notif_msg = (
                    f"🔴 *[AutoClip] Live Encerrada!*\n\n"
                    f"A transmissão no *Slot #{sid}* ({stream_url}) foi finalizada pelo streamer.\n\n"
                    f"👉 O *Slot #{sid}* já está liberado no dashboard para você adicionar outra live:\n"
                    f"http://localhost:8501"
                )
                try:
                    telegram_bot.send_telegram_notification(notif_msg)
                except Exception as e:
                    print(f"[LiveOrchestrator] Falha ao notificar encerramento no Telegram: {e}")

def is_live_session_active(session_id: int = 1) -> bool:
    return _sessions.get(session_id, {}).get("active", False)

def get_live_session_status(session_id: int = 1) -> dict:
    s = _sessions.get(session_id, {})
    detector = s.get("detector")
    mps = detector.current_mps if detector else 0.0
    req_mps = detector.required_mps if detector else 0.0
    viewers = detector.live_viewers if detector else 0
    err = detector.error_message if detector else ""
    return {
        "session_id": session_id,
        "active": s.get("active", False),
        "stream_url": s.get("stream_url", ""),
        "current_mps": mps,
        "required_mps": req_mps,
        "viewers": viewers,
        "clips_count": s.get("clips_count", 0),
        "last_clip_title": s.get("last_clip_title", ""),
        "error_message": err
    }

def get_all_sessions_status() -> list[dict]:
    return [get_live_session_status(sid) for sid in sorted(_sessions.keys())]

def update_all_detectors_sensitivity(sensitivity: str):
    for sid, s in _sessions.items():
        detector = s.get("detector")
        if detector and hasattr(detector, "set_sensitivity"):
            detector.set_sensitivity(sensitivity)

def trigger_manual_live_clip(session_id: int = 1) -> tuple[bool, str]:
    """Permite clipar manualmente os últimos 60-70 segundos do buffer sem depender do chat."""
    s = _sessions.get(session_id)
    if not s or not s["active"]:
        return False, f"Nenhuma live ativa no Slot #{session_id}."
    threading.Thread(
        target=_process_spike_job,
        args=(session_id, {"mps": 99.9, "manual": True}),
        daemon=True
    ).start()
    return True, f"Corte manual solicitado para Live #{session_id}! Processando buffer..."

def _process_spike_job(session_id: int, event_data: dict):
    is_manual = event_data.get("manual", False)
    mps_val = event_data.get("mps", 0.0)
    viewers = event_data.get("viewers", 0)
    print(f"[LiveOrchestrator] [Live #{session_id}] Processando clipe (Manual: {is_manual}, MPS: {mps_val:.1f}, Espectadores: {viewers})...")
    
    # Se foi disparado por pico de chat, aguarda 12 segundos para a reação do streamer entrar completamente no buffer
    if not is_manual:
        time.sleep(12)

    video_id = f"live_gta6_s{session_id}_{int(time.time())}"
    s_dir = live_stream.get_session_buffer_dir(session_id)
    raw_snippet = s_dir / f"{video_id}_raw.mp4"
    output_clip_path = CLIPS_DIR / f"{video_id}_vertical.mp4"

    try:
        # 1. Extrai 8 chunks (80 segundos) do buffer circular isolado da sessão
        live_stream.extract_recent_buffer(raw_snippet, session_id=session_id, num_chunks=8)

        # 2. Extrai áudio para o Gemini
        audio_path = clipper.extract_audio(raw_snippet)

        # 3. Analisa momento viral e ganchos com Gemini (com fallback para Plano B)
        clips_data = None
        try:
            clips_data = clipper.analyze_scene_with_gemini(audio_path, max_clips=1)
        except Exception as e:
            print(f"[LiveOrchestrator] [Live #{session_id}] Gemini indisponível ou cota esgotada ({e}). Ativando Plano B...")

        if not clips_data:
            # PLANO B: Corte Heurístico de Ação (100% Offline / Sem dependência de IA)
            print(f"[LiveOrchestrator] [Live #{session_id}] Executando Plano B: Corte de ação sem IA...")
            clip_info = clipper.generate_offline_action_clip(
                video_path=raw_snippet,
                output_path=output_clip_path,
                title=f"GTA 6 Momento Insano (Live #{session_id})",
                duration_seconds=65.0
            )
            title = clip_info["title"]
            formatted_caption = clip_info["caption"]
        else:
            clip_info = clips_data[0]
            start_s = float(clip_info.get("start_seconds", 5.0))
            end_s = float(clip_info.get("end_seconds", 70.0))
            
            # Garante que no modo monetização tenha pelo menos 61.0 segundos
            mode = config.load_duration_mode()
            if mode == "monetization" and (end_s - start_s) < 61.0:
                end_s = min(78.0, start_s + 63.0)

            clipper.render_vertical_clip(
                video_path=raw_snippet,
                start_s=start_s,
                end_s=end_s,
                subtitles=clip_info.get("subtitles", []),
                output_path=output_clip_path
            )
            title = clip_info.get("title", f"GTA 6 Live #{session_id} Moment")
            formatted_caption = format_caption(title, clip_info.get("caption", "#GTA6 #GTA #Viral"))

        # 4. DISPARO GARANTIDO TELEGRAM (Canal Primário Obrigatório)
        tg_cfg = config.load_telegram_config()
        if tg_cfg.get("bot_token") and tg_cfg.get("chat_id"):
            print(f"[LiveOrchestrator] [Live #{session_id}] Enviando vídeo para os destinatários do Telegram...")
            sent_tg = telegram_bot.send_clip_to_telegram(str(output_clip_path), formatted_caption)
            if sent_tg:
                print(f"[LiveOrchestrator] [Live #{session_id}] ✅ Vídeo entregue no Telegram com sucesso!")
            else:
                print(f"[LiveOrchestrator] [Live #{session_id}] ⚠️ Falha ao entregar no Telegram.")

        # 5. Entrega secundária por E-mail (se configurado)
        delivery_mode = load_delivery_channel()
        if delivery_mode in ["email", "both"]:
            email_sender.send_clip_by_email(str(output_clip_path), title, formatted_caption)

        s = _sessions[session_id]
        s["clips_count"] += 1
        s["last_clip_title"] = title

        if s["on_clip_callback"]:
            s["on_clip_callback"]({
                "session_id": session_id,
                "title": title,
                "caption": formatted_caption,
                "path": str(output_clip_path)
            })

    except Exception as e:
        print(f"[LiveOrchestrator] [Live #{session_id}] Erro ao processar clipe: {e}")
    finally:
        if raw_snippet.exists():
            try:
                raw_snippet.unlink()
            except Exception:
                pass

def start_live_session(stream_url: str, session_id: int = 1, on_clip_callback=None) -> tuple[bool, str]:
    if session_id not in _sessions:
        return False, "ID de sessão inválido (use 1, 2 ou 3)."

    s = _sessions[session_id]
    if s["active"]:
        return False, f"A Live #{session_id} já está em andamento."

    try:
        p_stream, p_ffmpeg = live_stream.start_circular_buffer(stream_url, session_id=session_id)
        time.sleep(2)
        if p_stream.poll() is not None:
            return False, f"Falha ao iniciar captura da Live #{session_id} via streamlink (verifique a URL)."

        detector = chat_spike.ChatSpikeDetector(stream_url)
        detector.start(on_spike_callback=lambda evt: threading.Thread(
            target=_process_spike_job,
            args=(session_id, evt),
            daemon=True
        ).start())

        s["active"] = True
        s["stream_url"] = stream_url
        s["p_stream"] = p_stream
        s["p_ffmpeg"] = p_ffmpeg
        s["detector"] = detector
        s["on_clip_callback"] = on_clip_callback
        s["started_at"] = time.time()
        _ensure_watchdog_started()

        return True, f"Monitoramento da Live #{session_id} iniciado com sucesso!"
    except Exception as e:
        return False, f"Erro ao iniciar Live #{session_id}: {e}"

def stop_live_session(session_id: int = 1, manual: bool = True):
    s = _sessions.get(session_id)
    if not s or not s["active"]:
        return

    if s["detector"]:
        s["detector"].stop()

    live_stream.stop_circular_buffer(s["p_stream"], s["p_ffmpeg"])

    s["active"] = False
    s["stream_url"] = ""
    s["p_stream"] = None
    s["p_ffmpeg"] = None
    s["detector"] = None
    s["started_at"] = 0

def stop_all_sessions():
    for sid in _sessions:
        stop_live_session(sid)
