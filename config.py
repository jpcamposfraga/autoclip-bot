import os
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
DOWNLOADS_DIR = MEDIA_DIR / "downloads"
CLIPS_DIR = MEDIA_DIR / "clips"
CONFIG_FILE = BASE_DIR / "config.json"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CAPTION_TEMPLATE = "{title}\n\n{caption}\n\n🎬 What would you do in this situation? Let us know in the comments! 👇\n\n#movies #cinema #viral #fyp #shorts"

def get_ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    winget_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
    for candidate in winget_path.glob("**/ffmpeg.exe"):
        return str(candidate)
    return "ffmpeg"

FFMPEG_BIN = get_ffmpeg_path()
if FFMPEG_BIN and FFMPEG_BIN != "ffmpeg":
    ffmpeg_dir = str(Path(FFMPEG_BIN).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

def _load_config_data() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_config_data(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_gemini_key() -> str:
    keys = load_gemini_keys_pool()
    return keys[0] if keys else (os.getenv("GEMINI_API_KEY", "").strip())

def load_gemini_keys_pool() -> list[str]:
    data = _load_config_data()
    raw = data.get("gemini_keys_pool", [])
    if isinstance(raw, list):
        keys = [k.strip() for k in raw if k.strip()]
    elif isinstance(raw, str):
        keys = [k.strip() for k in raw.split(",") if k.strip()]
    else:
        keys = []
    single_key = data.get("gemini_api_key", "").strip()
    if single_key and single_key not in keys:
        keys.insert(0, single_key)
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key and env_key not in keys:
        keys.append(env_key)
    return keys

def save_gemini_key(key: str):
    save_gemini_keys_pool([key])

def save_gemini_keys_pool(keys: list[str]):
    data = _load_config_data()
    cleaned = [k.strip() for k in keys if k.strip()]
    data["gemini_keys_pool"] = cleaned
    data["gemini_api_key"] = cleaned[0] if cleaned else ""
    _save_config_data(data)

def load_duration_mode() -> str:
    data = _load_config_data()
    return data.get("duration_mode", "hybrid") # "monetization", "traction", "hybrid"

def save_duration_mode(mode: str):
    data = _load_config_data()
    data["duration_mode"] = mode
    _save_config_data(data)

def load_spike_sensitivity() -> str:
    data = _load_config_data()
    return data.get("spike_sensitivity", "high") # "high", "normal", "conservative"

def save_spike_sensitivity(sensitivity: str):
    data = _load_config_data()
    data["spike_sensitivity"] = sensitivity
    _save_config_data(data)

def load_caption_template() -> str:
    data = _load_config_data()
    return data.get("caption_template", DEFAULT_CAPTION_TEMPLATE)

def save_caption_template(template: str):
    data = _load_config_data()
    data["caption_template"] = template.strip()
    _save_config_data(data)

def load_schedule_config() -> dict:
    data = _load_config_data()
    return {
        "posts_per_day": int(data.get("posts_per_day", 3)),
        "interval_hours": float(data.get("interval_hours", 3.0))
    }

def save_schedule_config(posts_per_day: int, interval_hours: float):
    data = _load_config_data()
    data["posts_per_day"] = int(posts_per_day)
    data["interval_hours"] = float(interval_hours)
    _save_config_data(data)

def format_caption(title: str, ai_caption: str) -> str:
    template = load_caption_template()
    try:
        return template.format(title=title, caption=ai_caption)
    except KeyError:
        return f"{title}\n\n{ai_caption}\n\n{template}"

def load_telegram_config() -> dict:
    data = _load_config_data()
    return {
        "bot_token": data.get("telegram_bot_token", "").strip(),
        "chat_id": data.get("telegram_chat_id", "").strip()
    }

def save_telegram_config(bot_token: str, chat_id: str):
    data = _load_config_data()
    data["telegram_bot_token"] = bot_token.strip()
    data["telegram_chat_id"] = chat_id.strip()
    _save_config_data(data)

def load_peak_hours() -> list[str]:
    data = _load_config_data()
    return data.get("peak_hours", ["12:00", "18:00", "21:00"])

def save_peak_hours(hours: list[str]):
    data = _load_config_data()
    data["peak_hours"] = hours
    _save_config_data(data)

def load_monitored_channels() -> list[str]:
    data = _load_config_data()
    from scanner import DEFAULT_CHANNELS
    return data.get("monitored_channels", DEFAULT_CHANNELS)

def save_monitored_channels(channels: list[str]):
    data = _load_config_data()
    data["monitored_channels"] = [c.strip() for c in channels if c.strip()]
    _save_config_data(data)

def load_email_config() -> dict:
    data = _load_config_data()
    return {
        "sender_email": data.get("sender_email", "").strip(),
        "sender_password": data.get("sender_password", "").strip(),
        "recipient_email": data.get("recipient_email", "").strip(),
        "smtp_server": data.get("smtp_server", "smtp.gmail.com").strip(),
        "smtp_port": int(data.get("smtp_port", 587))
    }

def save_email_config(sender_email: str, sender_password: str, recipient_email: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
    data = _load_config_data()
    data["sender_email"] = sender_email.strip()
    data["sender_password"] = sender_password.strip()
    data["recipient_email"] = recipient_email.strip()
    data["smtp_server"] = smtp_server.strip()
    data["smtp_port"] = int(smtp_port)
    _save_config_data(data)

def load_delivery_channel() -> str:
    data = _load_config_data()
    return data.get("delivery_channel", "both") # "email", "telegram", "both"

def save_delivery_channel(channel: str):
    data = _load_config_data()
    data["delivery_channel"] = channel
    _save_config_data(data)

GEMINI_API_KEY = load_gemini_key()
