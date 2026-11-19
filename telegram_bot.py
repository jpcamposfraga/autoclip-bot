import json
import re
import shutil
import subprocess
from pathlib import Path
import config

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"

def _get_curl_bin() -> str:
    path = shutil.which("curl.exe") or shutil.which("curl")
    if path:
        return path
    system_curl = Path(r"C:\Windows\System32\curl.exe")
    if system_curl.exists():
        return str(system_curl)
    return "curl"

CURL_BIN = _get_curl_bin()

def parse_chat_ids(raw_chat_ids: str | list | None) -> list[str]:
    """Extrai lista limpa de Chat IDs a partir de string separada por vírgula, espaço ou lista."""
    if not raw_chat_ids:
        return []
    if isinstance(raw_chat_ids, list):
        return [str(c).strip() for c in raw_chat_ids if str(c).strip()]
    tokens = re.split(r"[,;\s\n]+", str(raw_chat_ids).strip())
    return [t.strip() for t in tokens if t.strip()]

def _curl_request(endpoint: str, bot_token: str, form_fields: dict = None, files: dict = None, timeout: int = 180) -> tuple[bool, dict]:
    """Executa requisição à Telegram Bot API via curl.exe (imune a stalls de TLS no Windows)."""
    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/{endpoint}"
    cmd = [CURL_BIN, "-s", "--max-time", str(timeout), url]

    if files:
        for field_name, file_path in files.items():
            cmd.extend(["-F", f"{field_name}=@{Path(file_path).resolve()}"])

    if form_fields:
        for k, v in form_fields.items():
            cmd.extend(["-F", f"{k}={v}"])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if not res.stdout:
            err_desc = res.stderr.strip() or "Nenhuma resposta de curl.exe"
            return False, {"ok": False, "description": err_desc}
        try:
            data = json.loads(res.stdout)
            return data.get("ok", False), data
        except json.JSONDecodeError:
            return False, {"ok": False, "description": res.stdout[:200]}
    except Exception as e:
        return False, {"ok": False, "description": str(e)}

def test_telegram_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Token ou Chat ID vazios."

    chat_ids = parse_chat_ids(chat_id)
    if not chat_ids:
        return False, "Nenhum Chat ID válido informado."

    success_count = 0
    errors = []

    text_msg = (
        "🎬 *AutoClip Factory*: Conexão com Telegram configurada com sucesso!\n\n"
        "Você receberá os vídeos prontos para postar aqui em tempo real assim que forem gerados pela IA."
    )

    for cid in chat_ids:
        fields = {
            "chat_id": cid,
            "text": text_msg,
            "parse_mode": "Markdown"
        }
        ok, data = _curl_request("sendMessage", bot_token, form_fields=fields, timeout=15)
        if ok:
            success_count += 1
        else:
            desc = data.get("description", "Erro desconhecido")
            errors.append(f"ID {cid} ({desc})")

    if success_count == len(chat_ids):
        return True, f"Mensagem de teste enviada com sucesso para todos os {success_count} destinatário(s)!"
    elif success_count > 0:
        return True, f"Enviado para {success_count}/{len(chat_ids)} destinatários. Falhas: {'; '.join(errors)}"
    else:
        err_msg = "; ".join(errors)
        if "chat not found" in err_msg.lower() or "blocked" in err_msg.lower():
            err_msg += " -> Dica: Essa pessoa precisa abrir o seu bot no Telegram e clicar em /start primeiro!"
        return False, f"Falha no envio: {err_msg}"

def send_telegram_notification(text: str, bot_token: str = None, chat_id: str = None) -> bool:
    """Envia uma notificação de texto (ex: aviso de live encerrada) para todos os Chat IDs configurados."""
    if not bot_token or not chat_id:
        cfg = config.load_telegram_config()
        bot_token = bot_token or cfg.get("bot_token")
        chat_id = chat_id or cfg.get("chat_id")

    if not bot_token or not chat_id:
        return False

    chat_ids = parse_chat_ids(chat_id)
    if not chat_ids:
        return False

    sent_any = False
    for cid in chat_ids:
        fields = {
            "chat_id": cid,
            "text": text,
            "parse_mode": "Markdown"
        }
        ok, _ = _curl_request("sendMessage", bot_token, form_fields=fields, timeout=15)
        if ok:
            sent_any = True

    return sent_any

def send_clip_to_telegram(video_path: str, caption: str, bot_token: str = None, chat_id: str = None) -> bool:
    """
    Envia o vídeo para os destinatários via curl.exe.
    Para múltiplos destinatários, faz o upload físico uma única vez e reutiliza o file_id 
    da nuvem do Telegram para entregar aos demais em fração de segundo.
    """
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

    safe_caption = caption[:1020]
    sent_any = False
    file_id = None

    for cid in chat_ids:
        if file_id:
            # Entrega instantânea na nuvem do Telegram sem re-upload
            fields = {
                "chat_id": cid,
                "video": file_id,
                "caption": safe_caption,
                "supports_streaming": "true"
            }
            ok, data = _curl_request("sendVideo", bot_token, form_fields=fields, timeout=25)
            if ok:
                print(f"[Telegram] Vídeo {v_file.name} entregue via nuvem para {cid} com sucesso!")
                sent_any = True
            else:
                print(f"[Telegram] Falha ao enviar via nuvem para {cid}: {data.get('description')}")
        else:
            # Upload físico do arquivo via curl.exe
            fields = {
                "chat_id": cid,
                "caption": safe_caption,
                "supports_streaming": "true"
            }
            files = {"video": str(v_file)}
            ok, data = _curl_request("sendVideo", bot_token, form_fields=fields, files=files, timeout=240)
            if ok:
                print(f"[Telegram] Vídeo {v_file.name} enviado com sucesso para {cid}!")
                sent_any = True
                file_id = data.get("result", {}).get("video", {}).get("file_id")
            else:
                print(f"[Telegram] Falha no upload para {cid}: {data.get('description')}")

    return sent_any
