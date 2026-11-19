import re
import urllib.request
from typing import List, Dict
import yt_dlp
import chat_spike

TOP_CREATOR_CHANNELS = [
    # YouTube Creator Channels
    {"name": "LOUD Coringa (YT)", "url": "https://www.youtube.com/@LOUDCORINGA/live", "platform": "youtube"},
    {"name": "Davy Jones (Gameplayrj)", "url": "https://www.youtube.com/@Gameplayrj/live", "platform": "youtube"},
    {"name": "LipãoGamer", "url": "https://www.youtube.com/@lipaogamer/live", "platform": "youtube"},
    {"name": "Paulinho o Loko (YT)", "url": "https://www.youtube.com/@Paulinholokooficial/live", "platform": "youtube"},
    {"name": "Nobru", "url": "https://www.youtube.com/@Nobru/live", "platform": "youtube"},
    {"name": "Piuzinho", "url": "https://www.youtube.com/@Piuzinho/live", "platform": "youtube"},
    {"name": "Luqueta", "url": "https://www.youtube.com/@luqueta/live", "platform": "youtube"},

    # Twitch Top Channels
    {"name": "loud_coringa (Twitch)", "url": "https://www.twitch.tv/loud_coringa", "platform": "twitch"},
    {"name": "alanzoka (Twitch)", "url": "https://www.twitch.tv/alanzoka", "platform": "twitch"},
    {"name": "gaules (Twitch)", "url": "https://www.twitch.tv/gaules", "platform": "twitch"},
    {"name": "paulinholokobr (Twitch)", "url": "https://www.twitch.tv/paulinholokobr", "platform": "twitch"},
    {"name": "luquet4 (Twitch)", "url": "https://www.twitch.tv/luquet4", "platform": "twitch"}
]

def check_youtube_channel_live(channel_live_url: str) -> dict | None:
    """Verifica se a URL /live de um canal do YouTube está transmitindo agora."""
    try:
        req = urllib.request.Request(
            channel_live_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if '"isLiveNow":true' not in html and '"isLive":true' not in html:
                return None

            # Extrai videoId
            m_id = re.search(r'"videoId":\s*"([a-zA-Z0-9_-]{11})"', html)
            vid = m_id.group(1) if m_id else None
            if not vid:
                return None

            # Extrai título
            m_title = re.search(r'<title>(.*?)<\/title>', html)
            title = m_title.group(1).replace("- YouTube", "").strip() if m_title else "GTA 6 Ao Vivo"

            # Espectadores
            viewers = chat_spike.fetch_live_viewers(f"https://www.youtube.com/watch?v={vid}")

            return {
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": title,
                "viewers": viewers,
                "platform": "youtube"
            }
    except Exception:
        return None

def search_youtube_gta6_lives(max_results: int = 6) -> List[Dict]:
    """Busca transmissões ao vivo de GTA 6 em tempo real no YouTube."""
    results = []
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True
    }
    queries = ["ytsearch4:live gta 6", "ytsearch4:gta vi ao vivo"]
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for q in queries:
                info = ydl.extract_info(q, download=False)
                for entry in info.get("entries", []):
                    if entry and entry.get("live_status") == "is_live":
                        v_id = entry.get("id")
                        v_url = f"https://www.youtube.com/watch?v={v_id}"
                        # Evita duplicados
                        if any(r["url"] == v_url for r in results):
                            continue
                        viewers = chat_spike.fetch_live_viewers(v_url)
                        results.append({
                            "url": v_url,
                            "title": entry.get("title", "Live GTA 6"),
                            "channel": entry.get("channel", entry.get("uploader", "Streamer")),
                            "viewers": viewers,
                            "platform": "youtube"
                        })
    except Exception as e:
        print(f"[StreamScanner] Erro na busca de lives: {e}")

    return results

def discover_top_gta6_lives(limit: int = 5) -> List[Dict]:
    """
    Retorna as maiores lives ativas de GTA 6 no momento,
    combinando a checagem dos top streamers e busca dinâmica.
    Ordenadas por audiência decrescente.
    """
    found = []

    # 1. Verifica os top streamers pré-definidos
    for c in TOP_CREATOR_CHANNELS:
        if c["platform"] == "youtube":
            live_data = check_youtube_channel_live(c["url"])
            if live_data:
                live_data["channel"] = c["name"]
                found.append(live_data)
        elif c["platform"] == "twitch":
            # Para Twitch, verifica via IRC se o canal está ativo com mensagens
            # (ou inclui como opção de monitoramento se configurado)
            pass

    # 2. Busca dinâmica por novas lives de GTA 6
    dynamic_lives = search_youtube_gta6_lives(max_results=6)
    for dl in dynamic_lives:
        if not any(f["url"] == dl["url"] for f in found):
            found.append(dl)

    # Ordena pelos canais com maior número de espectadores
    found.sort(key=lambda x: x.get("viewers", 0), reverse=True)
    return found[:limit]
