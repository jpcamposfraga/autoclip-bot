# Live Stream Real-Time Clipper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a real-time live stream clipping engine in AutoClip Factory that connects to active livestreams (Twitch / YouTube), detects chat velocity spikes (excitement / humor), automatically extracts the preceding 60-second video buffer, transcribes and generates 9:16 vertical clips with subtitles, and delivers them via Telegram / E-mail.

**Architecture:** A lightweight stream listener (`live_stream.py`) captures a circular rolling buffer of the last 90 seconds in 10-second TS segments using `streamlink` and `ffmpeg` without re-encoding (~80MB fixed disk footprint). A parallel chat monitor (`chat_spike.py`) tracks messages per second (MPS) over a moving average window. When a spike is detected, the preceding 60 seconds are concatenated, sent to Gemini Flash for speech boundary alignment, rendered to 9:16 with animated subtitles, and delivered to the user.

**Tech Stack:** Python 3.14, `streamlink`, `chat-downloader`, FFmpeg, Google Gemini Flash API, SQLite3, Streamlit.

**Spec:** `C:\Users\João\.gemini\antigravity-cli\brain\393fffb4-8f12-4f68-bb31-29cd5a89663f\project_architecture_spec.md`

## Global Constraints
- **Circular buffer isolation:** Buffer TS chunks must never accumulate indefinitely; max 9 chunks of 10s (~90s total), overwriting old segments.
- **Low CPU footprint:** Video ingestion uses `-c copy` (zero re-encoding during stream capture).
- **Spike debounce:** After triggering a clip, a 90-second cooldown is enforced to prevent duplicate clips of the same ongoing event.
- **Fail-safe fallback:** If chat stream disconnects or stream drops, auto-reconnect without crashing the UI.

## Review Focus
1. **Host CPU Throttling on 1 vCPU:** On low-tier VPS environments without GPU, heavy software encoding blocks the stream capture thread; pipeline must offload transcription to Gemini Flash cloud API and use `-preset ultrafast` for FFmpeg.
2. **Chat Stream Delay vs Video Buffer:** Chat reactions lag behind video by 3–8 seconds; the clip slice must include 45s before the spike and 15s after.
3. **Empty Chat / Small Streamer:** If a stream has low baseline chat velocity (< 0.2 msgs/sec), relative percentage spikes might trigger false positives; minimum absolute threshold (e.g. at least 6 msgs/sec) is required.
4. **Buffer Concurrency:** Stitching segments into MP4 must read from completed TS chunks, avoiding the actively written segment.
5. **Memory and Temp Disk Cleanup:** Sliced temporary TS segments must be purged immediately after final MP4 delivery.

---

### Task 1: Circular Stream Buffer Engine (`live_stream.py`)

**Files:**
- Create: `live_stream.py`
- Test: `test_smoke.py`

**Interfaces:**
- `live_stream.start_circular_buffer(stream_url: str, buffer_dir: Path) -> subprocess.Popen`: Uses `streamlink` piped to `ffmpeg` with `-f segment -segment_time 10 -segment_wrap 9` to maintain 90s in rolling chunks.
- `live_stream.extract_recent_buffer(buffer_dir: Path, duration_seconds: int = 60, output_mp4: Path) -> Path`: Concatenates the last completed TS segments without re-encoding into a single MP4.
- `live_stream.stop_buffer(process)`: Cleanly terminates background capture.

- [ ] **Step 1: Write smoke test for buffer segment concatenation logic**
- [ ] **Step 2: Implement `live_stream.py` with circular HLS segmentation**
- [ ] **Step 3: Verify segment extraction creates a valid playable MP4**

---

### Task 2: Real-Time Chat Velocity & Spike Detector (`chat_spike.py`)

**Files:**
- Create: `chat_spike.py`
- Test: `test_smoke.py`

**Interfaces:**
- `chat_spike.ChatSpikeDetector(stream_url: str, spike_multiplier: float = 3.0, min_mps: float = 5.0, cooldown_seconds: int = 90)`
- `detector.start(on_spike_callback)`: Runs a background thread polling chat messages via `chat-downloader` or Twitch IRC, maintaining a 10s sliding window of message counts and keyword scores (e.g., "KKK", "WTF", "POG", "LMAO").
- `detector.stop()`: Closes connection.

- [ ] **Step 1: Write unit test validating moving average and spike detection trigger**
- [ ] **Step 2: Implement `chat_spike.py` with keyword weighting and sliding window**
- [ ] **Step 3: Verify spike callback fires on synthetic message bursts**

---

### Task 3: Live Clip Orchestrator & Fast Pipeline (`live_orchestrator.py`)

**Files:**
- Create: `live_orchestrator.py`
- Modify: `config.py`
- Test: `test_smoke.py`

**Interfaces:**
- `live_orchestrator.start_live_session(stream_url: str, delivery_channel: str = "all")`: Spawns buffer capture and chat listener.
- `live_orchestrator.on_spike_triggered(timestamp)`:
  1. Calls `live_stream.extract_recent_buffer()` to get the raw 60s snippet.
  2. Extracts audio and sends to Gemini Flash for hook boundary refinement (returns clean start/end offsets and subtitles).
  3. Renders 9:16 vertical video with blurred background and ASS captions.
  4. Dispatches via `telegram_bot.py` and/or `email_sender.py`.
- `live_orchestrator.stop_live_session()`: Tears down processes cleanly.

- [ ] **Step 1: Implement `on_spike_triggered` worker function**
- [ ] **Step 2: Implement start/stop session management**
- [ ] **Step 3: Write end-to-end smoke test validating pipeline chaining**

---

### Task 4: Streamlit UI Live Clipper Tab (`app.py`)

**Files:**
- Modify: `app.py`

**Interfaces:**
- Nova aba: **"🔴 Live Clipper ao Vivo"**:
  - Campo para URL da live (Twitch ou YouTube).
  - Botão "▶️ Iniciar Monitoramento da Live" / "⏹️ Parar".
  - Gráfico em tempo real de Velocidade do Chat (Mensagens por Segundo).
  - Feed dos clipes capturados ao vivo com player de vídeo e status de entrega.

- [ ] **Step 1: Add "🔴 Live Clipper" tab in `app.py`**
- [ ] **Step 2: Add live session status indicators and start/stop controls**
- [ ] **Step 3: Test UI live controls with mock/real stream**
