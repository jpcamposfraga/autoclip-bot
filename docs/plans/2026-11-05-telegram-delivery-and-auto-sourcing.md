# Auto-Sourcing, Daily Peak Hours Scheduler & Telegram Delivery Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform AutoClip Factory into a 100% autonomous content pipeline that automatically discovers high-retention movie scenes from YouTube, renders viral 9:16 vertical clips with subtitles, and delivers them directly to the creator's phone via Telegram at peak algorithm hours (12:00, 18:00, and 21:00).

**Architecture:** A channel scanner queries target YouTube channels via `yt-dlp` to discover fresh 2–7 minute scene clips without duplicates. A dedicated Telegram Bot service sends the rendered video and formatted caption to the user's chat. An upgraded cron-style scheduler triggers the pipeline at 12:00, 18:00, and 21:00 local time, with manual one-click testing in Streamlit.

**Tech Stack:** Python 3.14, `yt-dlp`, Telegram Bot API (`requests`), SQLite3, FFmpeg, Streamlit.

**Spec:** `C:\Users\João\.gemini\antigravity-cli\brain\393fffb4-8f12-4f68-bb31-29cd5a89663f\project_architecture_spec.md`

## Global Constraints
- **Ponytail standard:** Minimum viable code, no heavy bot frameworks; use standard `requests` for the Telegram Bot API.
- **Zero duplicates:** Every processed YouTube video ID is logged in `autoclip.db` so the system never clips the same video twice.
- **Delivery payload:** Telegram caption must contain the viral hook, movie context, call to action, and algorithm-optimized hashtags, ready to copy in 1 tap on mobile.
- **Peak hour precision:** Target execution times: `12:00`, `18:00`, `21:00` local time (-03:00).

## Review Focus
1. **Telegram API 50MB Limit:** Video clips of 30–60s rendered in 1080x1920 CRF 21 are typically 10–25MB; ensure file sizes stay well below Telegram's 50MB bot upload limit.
2. **Channel Scraping Throttling:** Querying channel video lists must use flat playlist extraction to avoid IP rate-limiting from YouTube.
3. **Double Trigger Prevention:** The scheduler must mark an hour slot as completed so it does not trigger multiple times within the same hour window.
4. **Invalid Telegram Credentials:** Provide clear user feedback in the UI if the token or chat ID is invalid, rather than crashing silently.
5. **Channel Exhaustion Fallback:** If the primary channel has no new unseen videos matching duration filters, cycle automatically to secondary channels.

---

### Task 1: YouTube Channel Auto-Scanner (`scanner.py` & `db.py`)

**Files:**
- Create: `scanner.py`
- Modify: `db.py`
- Test: `test_smoke.py`

**Interfaces:**
- `db.is_source_processed(youtube_id: str) -> bool`
- `db.mark_source_processed(youtube_id: str, title: str, channel: str)`
- `scanner.get_next_unprocessed_scene(channel_urls: list[str]) -> dict`: Scans channels using `yt_dlp` flat extraction, filters by duration (120s to 420s), checks against `db`, and returns the first unseen candidate `{id, url, title, duration}`.

- [ ] **Step 1: Write smoke test for source tracking and duplicate prevention in `db.py`**
- [ ] **Step 2: Add `processed_sources` table and helpers in `db.py`**
- [ ] **Step 3: Implement `scanner.py` with flat playlist extraction and duration filtering**
- [ ] **Step 4: Verify scanner and db tests pass**

---

### Task 2: Telegram Delivery Service (`telegram_bot.py`)

**Files:**
- Create: `telegram_bot.py`
- Modify: `config.py`
- Test: `test_smoke.py`

**Interfaces:**
- `config.load_telegram_config() -> dict`: Returns `{"bot_token": str, "chat_id": str}`
- `config.save_telegram_config(bot_token: str, chat_id: str)`
- `telegram_bot.test_connection(bot_token: str, chat_id: str) -> bool`: Sends a text ping.
- `telegram_bot.send_clip_to_telegram(video_path: str, caption: str) -> bool`: Sends video MP4 with caption via `https://api.telegram.org/bot<TOKEN>/sendVideo`.

- [ ] **Step 1: Add Telegram token and chat_id configuration in `config.py`**
- [ ] **Step 2: Implement `telegram_bot.py` with video upload and caption payload**
- [ ] **Step 3: Write smoke test verifying payload generation and error handling**

---

### Task 3: Peak Hours Scheduler Trigger (`scheduler.py`)

**Files:**
- Modify: `scheduler.py`
- Test: `test_smoke.py`

**Interfaces:**
- `scheduler.get_scheduled_peak_hours() -> list[str]`: Defaults to `["12:00", "18:00", "21:00"]`.
- `scheduler.run_autonomous_pipeline() -> dict`:
  1. Finds next scene via `scanner.py`.
  2. Downloads & extracts audio via `clipper.py`.
  3. Identifies viral hook & generates formatted caption via Gemini Flash.
  4. Renders vertical 9:16 clip with blurred background & ASS subtitles.
  5. Dispatches video and caption to Telegram via `telegram_bot.py`.
  6. Marks video as processed in `db.py`.
- Scheduler background loop checks current time and fires when matching an hour slot.

- [ ] **Step 1: Implement `run_autonomous_pipeline` chaining scan -> clip -> render -> telegram**
- [ ] **Step 2: Upgrade `_worker_loop` to trigger at configured peak hours with duplicate-run guards**
- [ ] **Step 3: Write test verifying peak-hour matching logic**

---

### Task 4: Streamlit UI Integration (`app.py`)

**Files:**
- Modify: `app.py`

**Interfaces:**
- **Aba Configurações:** Telegram Bot Token, Chat ID, botão "🔔 Testar Conexão com Telegram", lista de canais monitorados e seletor de horários de pico.
- **Aba Criador de Cortes:** Adicionar botão de ação rápida "⚡ Buscar e Enviar Próximo Vídeo para o Telegram Agora".
- **Histórico/Log:** Exibir os vídeos enviados recentemente para o Telegram.

- [ ] **Step 1: Add Telegram configuration fields & test ping button in `app.py`**
- [ ] **Step 2: Add instant "Buscar e Enviar para o Telegram Agora" trigger in Tab 1**
- [ ] **Step 3: Run smoke tests and verify application integrity**
