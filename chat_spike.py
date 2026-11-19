import time
import re
import threading
from collections import deque

HYPE_KEYWORDS = {
    "kkk", "kkkk", "lol", "lmao", "wtf", "omg", "clip", "clipe", "pog",
    "caralho", "mds", "surreal", "gta", "hype", "w", "crazy", "mentira",
    "krai", "eita", "nossa", "morreu", "bizarro", "gg", "slk"
}

def extract_youtube_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|\/live\/|youtu\.be\/|\/v\/|\/embed\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$"
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None

class ChatSpikeDetector:
    def __init__(self, stream_url: str, spike_multiplier: float = 2.0, min_mps: float = 1.0, cooldown_seconds: int = 60):
        self.stream_url = stream_url
        self.spike_multiplier = spike_multiplier
        self.min_mps = min_mps
        self.cooldown_seconds = cooldown_seconds
        
        self.recent_msg_times = deque()
        self.baseline_history = deque(maxlen=60)
        self.last_spike_time = 0.0
        self.is_running = False
        self.error_message = ""
        self._thread = None
        self._stop_event = threading.Event()

    @property
    def current_mps(self) -> float:
        now = time.time()
        while self.recent_msg_times and now - self.recent_msg_times[0] > 10.0:
            self.recent_msg_times.popleft()
        return round(len(self.recent_msg_times) / 10.0, 1)

    def _calculate_score(self, text: str) -> float:
        score = 1.0
        lower = text.lower()
        for kw in HYPE_KEYWORDS:
            if kw in lower:
                score += 1.5
                break
        return score

    def _process_message(self, text: str, on_spike_callback):
        now = time.time()
        weight = self._calculate_score(text)
        for _ in range(int(round(weight))):
            self.recent_msg_times.append(now)

        while self.recent_msg_times and now - self.recent_msg_times[0] > 10.0:
            self.recent_msg_times.popleft()

        mps = len(self.recent_msg_times) / 10.0
        self.baseline_history.append(mps)
        avg_mps = sum(self.baseline_history) / max(1, len(self.baseline_history))

        if mps >= self.min_mps and mps >= (avg_mps * self.spike_multiplier):
            if now - self.last_spike_time >= self.cooldown_seconds:
                self.last_spike_time = now
                print(f"[ChatSpike] 🔥 Pico de chat detectado! MPS: {mps:.1f} (Média: {avg_mps:.1f})")
                if on_spike_callback:
                    threading.Thread(
                        target=on_spike_callback,
                        args=({"mps": mps, "avg": avg_mps, "time": now},),
                        daemon=True
                    ).start()

    def _monitor_loop(self, on_spike_callback):
        # 1. Verifica se a URL é do YouTube
        yt_id = extract_youtube_id(self.stream_url)
        if not yt_id and ("youtube.com" in self.stream_url or "youtu.be" in self.stream_url):
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                    info = ydl.extract_info(self.stream_url, download=False)
                    yt_id = info.get("id")
            except Exception as e:
                print(f"[ChatSpike] Falha ao extrair ID com yt-dlp: {e}")

        if yt_id:
            print(f"[ChatSpike] Conectando via pytchat ao YouTube (ID: {yt_id})...")
            try:
                import pytchat
                chat = pytchat.create(video_id=yt_id)
                if not chat.is_alive():
                    self.error_message = "Chat do YouTube indisponível ou live offline."
                    print(f"[ChatSpike] {self.error_message}")
                    return

                print(f"[ChatSpike] Chat do YouTube conectado com sucesso! Monitorando mensagens...")
                while chat.is_alive() and not self._stop_event.is_set():
                    data = chat.get()
                    for item in data.sync_items():
                        self._process_message(item.message, on_spike_callback)
                    time.sleep(0.5)

                if not chat.is_alive():
                    print("[ChatSpike] Conexão com o chat do YouTube finalizada.")
            except Exception as e:
                self.error_message = f"Erro no chat do YouTube: {e}"
                print(f"[ChatSpike] {self.error_message}")
            finally:
                self.is_running = False
            return

        # 2. Twitch ou outros: fallback para chat-downloader
        print(f"[ChatSpike] Conectando via chat-downloader ({self.stream_url})...")
        try:
            from chat_downloader import ChatDownloader
            downloader = ChatDownloader()
            chat = downloader.get_chat(self.stream_url)
            for msg in chat:
                if self._stop_event.is_set():
                    break
                text = msg.get("message", "")
                self._process_message(text, on_spike_callback)
        except Exception as e:
            self.error_message = f"Erro no chat: {e}"
            print(f"[ChatSpike] {self.error_message}")
        finally:
            self.is_running = False

    def start(self, on_spike_callback):
        if not self.is_running:
            self._stop_event.clear()
            self.is_running = True
            self.error_message = ""
            self._thread = threading.Thread(target=self._monitor_loop, args=(on_spike_callback,), daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.is_running = False
