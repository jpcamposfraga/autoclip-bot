from pathlib import Path
import requests
import config

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"

def test_telegram_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Token ou Chat ID vazios."
    try:
        url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "🎬 *AutoClip Factory*: Conexão com Telegram configurada com sucesso!\n\nVocê receberá os vídeos prontos para postar aqui nos horários programados (12h, 18h e 21h).",
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return True, "Mensagem de teste enviada com sucesso!"
        return False, f"Erro Telegram: {data.get('description')}"
    except Exception as e:
        return False, f"Falha de rede: {e}"

def send_clip_to_telegram(video_path: str, caption: str, bot_token: str = None, chat_id: str = None) -> bool:
    if not bot_token or not chat_id:
        cfg = config.load_telegram_config()
        bot_token = bot_token or cfg.get("bot_token")
        chat_id = chat_id or cfg.get("chat_id")

    if not bot_token or not chat_id:
        print("[Telegram] Bot Token ou Chat ID não configurados.")
        return False

    v_file = Path(video_path)
    if not v_file.exists():
        print(f"[Telegram] Arquivo de vídeo não encontrado: {video_path}")
        return False

    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/sendVideo"
    
    # Telegram captions have a limit of 1024 characters
    safe_caption = caption[:1020]

    try:
        with open(v_file, "rb") as f:
            files = {"video": (v_file.name, f, "video/mp4")}
            data = {
                "chat_id": chat_id,
                "caption": safe_caption,
                "supports_streaming": True
            }
            resp = requests.post(url, data=data, files=files, timeout=60)
            result = resp.json()
            if result.get("ok"):
                print(f"[Telegram] Vídeo {v_file.name} enviado com sucesso!")
                return True
            else:
                print(f"[Telegram] Erro no envio: {result.get('description')}")
                return False
    except Exception as e:
        print(f"[Telegram] Exceção ao enviar vídeo: {e}")
        return False
