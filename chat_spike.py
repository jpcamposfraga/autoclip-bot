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

def extract_twitch_channel(url: str) -> str | None:
    m = re.search(r"twitch\.tv\/([a-zA-Z0-9_]{3,25})", url)
    if m:
        ch = m.group(1).lower()
        if ch not in ["directory", "videos", "p", "popout"]:
            return ch
    return None

def fetch_live_viewers(url: str) -> int:
    """Extrai a quantidade de espectadores simultâneos ao vivo (apenas se a transmissão estiver ativa)."""
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
            # 1. Checa se está de fato transmitindo ao vivo agora
            is_live = bool(re.search(r'"isLiveNow":\s*true', html))
            if not is_live:
                return 0

            # 2. Busca estritamente o bloco com "assistindo agora" ou "watching now"
            pattern = r'"runs":\s*\[\s*\{\s*"text":\s*"([\d.,]+)"\s*\}\s*,\s*\{\s*"text":\s*"[^"]*(?:assistindo|watching)'
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                digits = re.sub(r"\D", "", m.group(1))
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
        self._irc_sock = None
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
        """Piso mínimo dinâmico com teto de segurança contra valores absurdos."""
        if self.live_viewers > 100:
            dynamic_floor = round(self.live_viewers * 0.0025, 1)
            # Teto de segurança rígido: nunca exigir mais de 35 msg/s
            capped = min(35.0, dynamic_floor)
            return max(self.min_mps, capped)
        return self.min_mps

    @property
    def required_mps(self) -> float:
        avg = sum(self.baseline_history) / max(1, len(self.baseline_history))
        raw_target = max(self.effective_min_mps, avg * self.spike_multiplier)
        return round(min(35.0, raw_target), 1)

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

        # 2. Twitch: Conexão via IRC Nativo (Sem bloqueios, rápido e suporta lives +18)
        twitch_ch = extract_twitch_channel(self.stream_url)
        if twitch_ch:
            print(f"[ChatSpike] Conectando ao chat da Twitch via IRC nativo (#{twitch_ch})...")
            import socket
            sock = None
            try:
                sock = socket.socket()
                sock.settimeout(2.0)
                sock.connect(("irc.chat.twitch.tv", 6667))
                sock.send(b"PASS oauth:justinfan12345\r\n")
                sock.send(b"NICK justinfan12345\r\n")
                sock.send(f"JOIN #{twitch_ch}\r\n".encode("utf-8"))
                self._irc_sock = sock
                print(f"[ChatSpike] Chat da Twitch conectado com sucesso! (#{twitch_ch})")

                while not self._stop_event.is_set():
                    try:
                        data = sock.recv(2048).decode("utf-8", errors="ignore")
                        for line in data.split("\r\n"):
                            if not line:
                                continue
                            if line.startswith("PING"):
                                sock.send(b"PONG :tmi.twitch.tv\r\n")
                            elif "PRIVMSG" in line:
                                m = re.search(r":\w+!.*PRIVMSG #\w+ :(.*)", line)
                                if m:
                                    self._process_message(m.group(1), on_spike_callback)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if not self._stop_event.is_set():
                            print(f"[ChatSpike] Erro no stream do IRC Twitch: {e}")
                        break
            except Exception as e:
                self.error_message = f"Erro ao conectar ao chat da Twitch: {e}"
                print(f"[ChatSpike] {self.error_message}")
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self._irc_sock = None
                self.is_running = False
            return

        # 3. Fallback genérico para outras plataformas
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
        if self._irc_sock:
            try:
                self._irc_sock.close()
            except Exception:
                pass
            self._irc_sock = None
        self.is_running = False
