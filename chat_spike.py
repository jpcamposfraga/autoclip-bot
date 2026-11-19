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

def fetch_live_viewers(url: str) -> int:
    """Extrai a quantidade de espectadores ao vivo da live."""
    import urllib.request
    try:
        yt_id = extract_youtube_id(url)
        target_url = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else url
        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # 1. Tenta originalViewCount
            orig = re.search(r'"originalViewCount":\s*"(\d+)"', html)
            if orig:
                return int(orig.group(1))
            # 2. Tenta videoViewCountRenderer
            view_m = re.search(r'"videoViewCountRenderer":\s*\{\s*"viewCount":\s*\{\s*"runs":\s*\[\s*\{\s*"text":\s*"([^"]+)"', html)
            if view_m:
                digits = re.sub(r"\D", "", view_m.group(1))
                if digits:
                    return int(digits)
    except Exception:
        pass
    return 0

class ChatSpikeDetector:
    def __init__(self, stream_url: str, spike_multiplier: float = 2.2, min_mps: float = 1.8, cooldown_seconds: int = 60):
        self.stream_url = stream_url
        self.spike_multiplier = spike_multiplier
        self.min_mps = min_mps
        self.cooldown_seconds = cooldown_seconds
        
        self.live_viewers = 0
        self.recent_msg_times = deque()
        self.baseline_history = deque(maxlen=60)
        self.last_spike_time = 0.0
        self.is_running = False
        self.error_message = ""
        self._chat_instance = None
        self._thread = None
        self._viewers_thread = None
        self._stop_event = threading.Event()

    @property
    def current_mps(self) -> float:
        now = time.time()
        while self.recent_msg_times and now - self.recent_msg_times[0] > 10.0:
            self.recent_msg_times.popleft()
        return round(len(self.recent_msg_times) / 10.0, 1)

    @property
    def effective_min_mps(self) -> float:
        """Piso mínimo dinâmico baseado no tamanho da audiência."""
        if self.live_viewers > 100:
            # ex: 1000 viewers -> max(1.8, 2.5) = 2.5; 10.000 viewers -> 25.0
            dynamic_floor = round(self.live_viewers * 0.0025, 1)
            return max(self.min_mps, dynamic_floor)
        return self.min_mps

    @property
    def required_mps(self) -> float:
        avg = sum(self.baseline_history) / max(1, len(self.baseline_history))
        return round(max(self.effective_min_mps, avg * self.spike_multiplier), 1)

    def _calculate_score(self, text: str) -> float:
        score = 1.0
        lower = text.lower()
        for kw in HYPE_KEYWORDS:
            if kw in lower:
                score += 1.5
                break
        return score

    def _track_viewers_loop(self):
        while not self._stop_event.is_set():
            v = fetch_live_viewers(self.stream_url)
            if v > 0:
                self.live_viewers = v
            # Atualiza espectadores a cada 60s
            for _ in range(60):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

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

        threshold = max(self.effective_min_mps, avg_mps * self.spike_multiplier)
        if mps >= threshold:
            if now - self.last_spike_time >= self.cooldown_seconds:
                self.last_spike_time = now
                print(f"[ChatSpike] 🔥 Pico de chat detectado! MPS: {mps:.1f} (Gatilho exigido: {threshold:.1f}, Espectadores: {self.live_viewers})")
                if on_spike_callback:
                    threading.Thread(
                        target=on_spike_callback,
                        args=({"mps": mps, "avg": avg_mps, "viewers": self.live_viewers, "time": now},),
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
                # interruptable=False é essencial para rodar em thread de background sem erro de signal
                chat = pytchat.create(video_id=yt_id, interruptable=False)
                self._chat_instance = chat
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
                self._chat_instance = None
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
            self._viewers_thread = threading.Thread(target=self._track_viewers_loop, daemon=True)
            self._viewers_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._chat_instance:
            try:
                self._chat_instance.terminate()
            except Exception:
                pass
            self._chat_instance = None
        self.is_running = False
