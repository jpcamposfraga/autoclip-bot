# GTA 6 Multi-Live Clipper & Monetization Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform AutoClip into a specialized, high-performance GTA 6 Multi-Live Clipper that monitors up to 3 streams simultaneously, calculates hype spikes dynamically based on live viewers, enforces TikTok monetization length (>=61s) with traction options (30s), provides a 3-layer Plan B for Gemini API quotas, guarantees instant Telegram delivery to multiple phones, and offers a streamlined auto-refreshing dashboard.

**Architecture:**
- **Capture Layer (`live_stream.py`):** Multi-session circular buffer manager supporting up to 3 isolated subdirectories (`media/live_buffer/live_{id}/`), retaining 15x 10s TS chunks (~150s rolling buffer) to cleanly extract 61-75s monetization cuts.
- **Intelligence & Trigger Layer (`chat_spike.py`):** Real-time `pytchat` / Twitch chat monitor with live viewer tracker (`originalViewCount`) adjusting the minimum MPS threshold dynamically ($\text{min\_mps} = \max(1.8, \text{viewers} \times 0.0025)$).
- **Duration & Fallback Engine (`clipper.py` & `live_orchestrator.py`):** Duration controller (Monetization >=61s, Traction 30s, or Hybrid 70/30). Gemini Multi-Key rotation with automatic failover to Plano B (offline heuristic action cutter centered on spike peak without API lockups).
- **Delivery Layer (`telegram_bot.py`):** Unconditional, multi-recipient sequential dispatching with upload timeouts and delivery logging.
- **UI Layer (`app.py`):** Clean 3-tab layout (Multi-Live Dashboard, Manual Clip, Settings) with 2-second auto-refresh and legacy features (ADB/Emulators, Queue, Social metrics) completely removed.

**Tech Stack:** Python 3.14, Streamlit, FFmpeg (Gyan full build with NVENC & libass), Streamlink, Pytchat, Chat-Downloader, Google Generative AI (Gemini 2.5 Flash), Telegram Bot API.

---

## Global Constraints
- Target video aspect ratio: 9:16 vertical (1080x1920) with blurred background padding and animated subtitles.
- Monetization duration floor: >= 61.0 seconds when in Monetization mode (TikTok Creator Rewards requirement).
- Maximum concurrent live streams: 3 (CPU/GPU safety ceiling).
- Memory / disk budget: ~120 MB per live buffer (15 chunks x 10s), automatically cycled.
- No media files or secrets tracked in git.

---

## Review Focus (Failure Modes to Prevent)
1. *Two lives running simultaneously overwriting each other's buffer files* -> Isolated per-session buffer folders (`live_1`, `live_2`, `live_3`).
2. *Clip duration under 60 seconds failing TikTok Creator Rewards* -> Force end-start >= 61.0s in both Gemini prompts and offline slicing.
3. *Gemini API 429 quota exhaustion halting live processing* -> Multi-key pool rotation + seamless fallback to Plano B offline action cut.
4. *Telegram deliver failing silently due to prior email setting* -> Telegram delivery executed unconditionally whenever bot_token and chat_ids are set.
5. *Chat detector crashing when live ends or streamer mutes chat* -> Graceful exit without killing the circular video recorder or other sessions.

---

## Task Structure

### Task 1: Circular Buffer Expansion & Duration Modes
**Files:**
- Modify: `live_stream.py`
- Modify: `clipper.py`
- Modify: `config.py`
- Test: `test_smoke.py`

- [ ] **Step 1.1:** Update `live_stream.py` to support multi-session isolated buffer directories (`media/live_buffer/live_{id}/`) and expand segment wrap from 10 to 15 chunks (150s buffer).
- [ ] **Step 1.2:** Update `extract_recent_buffer(session_id, output_path, num_chunks=8)` to extract 80s of raw footage (8x 10s chunks).
- [ ] **Step 1.3:** Add duration configuration helpers in `config.py` (`load_duration_mode()`, `save_duration_mode()`) supporting:
  - `"monetization"`: >= 61.0s (default 62s - 75s)
  - `"traction"`: 30s - 45s
  - `"hybrid"`: 70% monetization (>60s) / 30% traction (~35s)
- [ ] **Step 1.4:** Update `clipper.py` prompt to instruct Gemini on the minimum 61-second constraint for monetization mode, ensuring sentence boundaries are not truncated.
- [ ] **Step 1.5:** Run smoke tests to verify buffer math and duration constraints.

---

### Task 2: Multi-Live Session Orchestrator & Guaranteed Telegram Dispatch
**Files:**
- Modify: `live_orchestrator.py`
- Modify: `telegram_bot.py`
- Test: `test_smoke.py`

- [ ] **Step 2.1:** Refactor `live_orchestrator.py` from single `_current_session` to `_sessions = {}` mapping `session_id` (1, 2, 3) to session state.
- [ ] **Step 2.2:** Add multi-live methods:
  - `start_session(session_id, stream_url)`
  - `stop_session(session_id)`
  - `stop_all_sessions()`
  - `get_all_sessions_status()`
  - `trigger_manual_clip(session_id)`
- [ ] **Step 2.3:** In `_process_spike_job(session_id, event_data)`:
  - Extract buffer from `live_{session_id}` folder.
  - Apply duration mode logic (61s vs 35s).
  - Unconditionally send to Telegram if Bot Token and Chat IDs exist, logging recipient count.
  - Fall back to secondary channels (e.g. Email) if configured.
- [ ] **Step 2.4:** Run smoke tests for multi-session status dictionary and isolated buffers.

---

### Task 3: Viewer-Based Dynamic Spike Formula & YouTube Viewers Tracker
**Files:**
- Modify: `chat_spike.py`
- Test: `test_smoke.py`

- [ ] **Step 3.1:** Add `fetch_live_viewers(stream_url)` in `chat_spike.py` pulling `originalViewCount` / `videoViewCountRenderer` via regex from live page.
- [ ] **Step 3.2:** In `ChatSpikeDetector`, add background viewer tracking thread updating `self.live_viewers` every 60 seconds.
- [ ] **Step 3.3:** Implement dynamic threshold formula:
  $$\text{effective\_min\_mps} = \max(1.8, \;\; \text{viewers} \times 0.0025)$$
- [ ] **Step 3.4:** Add sensitivity scale factor (`sensitivity`: `0.8` relaxed, `1.0` normal, `1.4` epic moments only).
- [ ] **Step 3.5:** Test viewer extraction and dynamic calculation in `test_smoke.py`.

---

### Task 4: Gemini Quota Plan B (Multi-Key Pool + Offline Heuristic Action Cut)
**Files:**
- Modify: `config.py`
- Modify: `clipper.py`
- Modify: `live_orchestrator.py`
- Test: `test_smoke.py`

- [ ] **Step 4.1:** In `config.py`, add `load_gemini_keys_pool()` and `save_gemini_keys_pool()` supporting multiple API keys (e.g., Key 1, Key 2, Key 3).
- [ ] **Step 4.2:** In `clipper.py`, wrap Gemini calls with round-robin key rotation on `429: RESOURCE_EXHAUSTED` or quota errors.
- [ ] **Step 4.3:** Implement Plano B in `clipper.py` / `live_orchestrator.py`:
  - If all keys fail or no key is provided, automatically trigger `generate_offline_action_clip()`.
  - Cuts 65s (monetization) around the hype peak.
  - Applies 9:16 vertical crop with boxblur.
  - Generates hype GTA 6 title and caption (`"🔥 GTA 6 MOMENTO INSANO | O chat foi à loucura! #GTA6 #GTA #Viral"`).
  - Dispatches immediately to Telegram with tag `[Plano B: Corte de Ação]`.
- [ ] **Step 4.4:** Test key rotation and Plano B offline cut in `test_smoke.py`.

---

### Task 5: Dashboard Radical Clean-Up & Real-Time Auto-Refresh
**Files:**
- Modify: `app.py`
- Test: Streamlit browser validation

- [ ] **Step 5.1:** Strip out legacy emulator ADB components, legacy posting queues (`posts_queue`), and legacy social metrics from `app.py`.
- [ ] **Step 5.2:** Restructure `app.py` into exactly 3 focused tabs:
  - **Tab 1: 🔴 GTA 6 Multi-Live Clipper:**
    - Live Sessions Grid (3 columns or 3 cards for Live 1, Live 2, Live 3).
    - Each card displays: Stream URL input, Start/Stop buttons, Status badge, Live Viewers count (👥), Current MPS vs Required Spike MPS, and "⚡ Clipar Últimos 65s (Manual)".
    - Real-time auto-refresh toggle: `st.toggle("🔄 Atualização da tela em tempo real (a cada 2s)", value=True)`.
    - Live Clips Gallery with Telegram delivery status badges.
  - **Tab 2: 🎬 Gerador Manual / VOD:** Link input for fast multi-clip generation from YouTube links with instant Telegram delivery.
  - **Tab 3: ⚙️ Configurações & Telegram:**
    - Telegram Bot Token & Multi Chat IDs (Você + Amigo).
    - Gemini API Keys Pool (Chave Principal + Chaves de Backup do Plano B).
    - Seletor de Duração dos Cortes: `[ Monetização (>=61s) | Tração Rápida (30s) | Híbrido Inteligente (70% >60s / 30% 30s) ]`.
    - Sensibilidade do Hype: `[ Normal | Apenas Momentos Épicos | Sensível ]`.
    - Botão "Testar Telegram para Todos".
- [ ] **Step 5.3:** Validate Streamlit UI rendering and auto-refresh loop.
- [ ] **Step 5.4:** Commit and push all changes to GitHub.
