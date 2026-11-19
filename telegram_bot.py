from pathlib import Path
import re
import requests
import config

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"

def parse_chat_ids(raw_chat_ids: str | list | None) -> list[str]:
    """Extrai lista limpa de Chat IDs a partir de string separada por vírgula, espaço ou lista."""
    if not raw_chat_ids:
        return []
    if isinstance(raw_chat_ids, list):
        return [str(c).strip() for c in raw_chat_ids if str(c).strip()]
    tokens = re.split(r"[,;\s\n]+", str(raw_chat_ids).strip())
    return [t.strip() for t in tokens if t.strip()]

def test_telegram_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Token ou Chat ID vazios."

    chat_ids = parse_chat_ids(chat_id)
    if not chat_ids:
        return False, "Nenhum Chat ID válido informado."

    success_count = 0
    errors = []

    for cid in chat_ids:
        try:
            url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": (
                    "🎬 *AutoClip Factory*: Conexão com Telegram configurada com sucesso!\n\n"
                    "Você receberá os vídeos prontos para postar aqui em tempo real assim que forem gerados pela IA."
                ),
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("ok"):
                success_count += 1
            else:
                desc = data.get("description", "Erro desconhecido")
                errors.append(f"ID {cid} ({desc})")
        except Exception as e:
            errors.append(f"ID {cid} ({e})")

    if success_count == len(chat_ids):
        return True, f"Mensagem de teste enviada com sucesso para todos os {success_count} destinatário(s)!"
    elif success_count > 0:
        return True, f"Enviado para {success_count}/{len(chat_ids)} destinatários. Falhas: {'; '.join(errors)}"
    else:
        err_msg = "; ".join(errors)
        if "chat not found" in err_msg.lower() or "blocked" in err_msg.lower():
            err_msg += " -> Dica: Essa pessoa precisa abrir o seu bot no Telegram e clicar em /start primeiro!"
        return False, f"Falha no envio: {err_msg}"

def send_clip_to_telegram(video_path: str, caption: str, bot_token: str = None, chat_id: str = None) -> bool:
    if not bot_token or not chat_id:
        cfg = config.load_telegram_config()
        bot_token = bot_token or cfg.get("bot_token")
        chat_id = chat_id or cfg.get("chat_id")

    if not bot_token or not chat_id:
        print("[Telegram] Bot Token ou Chat ID não configurados.")
        return False

    chat_ids = parse_chat_ids(chat_id)
    if not chat_ids:
        print("[Telegram] Nenhum Chat ID válido encontrado.")
        return False

    v_file = Path(video_path)
    if not v_file.exists():
        print(f"[Telegram] Arquivo de vídeo não encontrado: {video_path}")
        return False

    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/sendVideo"
    safe_caption = caption[:1020]

    try:
        with open(v_file, "rb") as f:
            video_bytes = f.read()

        sent_any = False
        for cid in chat_ids:
            try:
                files = {"video": (v_file.name, video_bytes, "video/mp4")}
                data = {
                    "chat_id": cid,
                    "caption": safe_caption,
                    "supports_streaming": True
                }
                resp = requests.post(url, data=data, files=files, timeout=90)
                result = resp.json()
                if result.get("ok"):
                    print(f"[Telegram] Vídeo {v_file.name} enviado com sucesso para {cid}!")
                    sent_any = True
                else:
                    print(f"[Telegram] Falha ao enviar para {cid}: {result.get('description')}")
            except Exception as e:
                print(f"[Telegram] Exceção ao enviar para {cid}: {e}")

        return sent_any
    except Exception as e:
        print(f"[Telegram] Erro geral ao ler vídeo: {e}")
        return False
