import time
import threading
from collections import deque
from chat_downloader import ChatDownloader

HYPE_KEYWORDS = {
    "kkk", "kkkk", "lol", "lmao", "wtf", "omg", "clip", "clipe", "pog",
    "caralho", "mds", "surreal", "gta", "hype", "w", "crazy", "mentira"
}

class ChatSpikeDetector:
    def __init__(self, stream_url: str, spike_multiplier: float = 2.5, min_mps: float = 2.5, cooldown_seconds: int = 90):
        self.stream_url = stream_url
        self.spike_multiplier = spike_multiplier
        self.min_mps = min_mps
        self.cooldown_seconds = cooldown_seconds
        
        self.recent_msg_times = deque()
        self.baseline_history = deque(maxlen=60) # Amostras de MPS dos últimos 60s
        self.last_spike_time = 0.0
        self.current_mps = 0.0
        self.is_running = False
        self._thread = None
        self._stop_event = threading.Event()

    def _calculate_score(self, text: str) -> float:
        score = 1.0
        lower = text.lower()
        for kw in HYPE_KEYWORDS:
            if kw in lower:
                score += 1.5
                break
        return score

    def _monitor_loop(self, on_spike_callback):
        downloader = ChatDownloader()
        try:
            chat = downloader.get_chat(self.stream_url)
            for msg in chat:
                if self._stop_event.is_set():
                    break

                now = time.time()
                text = msg.get("message", "")
                weight = self._calculate_score(text)

                for _ in range(int(round(weight))):
                    self.recent_msg_times.append(now)

                # Remove mensagens com mais de 10s
                while self.recent_msg_times and now - self.recent_msg_times[0] > 10.0:
                    self.recent_msg_times.popleft()

                self.current_mps = len(self.recent_msg_times) / 10.0
                self.baseline_history.append(self.current_mps)

                # Média móvel da live
                avg_mps = sum(self.baseline_history) / max(1, len(self.baseline_history))

                # Checagem de pico
                if self.current_mps >= self.min_mps and self.current_mps >= (avg_mps * self.spike_multiplier):
                    if now - self.last_spike_time >= self.cooldown_seconds:
                        self.last_spike_time = now
                        print(f"[ChatSpike] Pico detectado! MPS atual: {self.current_mps:.1f} (Média: {avg_mps:.1f})")
                        if on_spike_callback:
                            threading.Thread(target=on_spike_callback, args=({"mps": self.current_mps, "avg": avg_mps, "time": now},), daemon=True).start()

        except Exception as e:
            print(f"[ChatSpike] Conexão com chat encerrada: {e}")
        finally:
            self.is_running = False

    def start(self, on_spike_callback):
        if not self.is_running:
            self._stop_event.clear()
            self.is_running = True
            self._thread = threading.Thread(target=self._monitor_loop, args=(on_spike_callback,), daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.is_running = False
