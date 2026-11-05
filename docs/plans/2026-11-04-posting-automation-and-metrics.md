# Automated Posting, Scheduling & Metrics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement autonomous scheduled posting to TikTok Lite, Instagram Lite, and YouTube Shorts via LDPlayer 9, customizable caption templates, and a metrics tracking dashboard in Streamlit.

**Architecture:** A lightweight SQLite database (`autoclip.db`) manages the queue of scheduled posts, target platforms, and metric snapshots. A background scheduler enforces daily post limits and hour intervals. Dedicated UI automation scripts in `uiautomator2` handle upload flows specifically for Lite apps and YouTube Shorts. A public metrics collector queries post performance for the Streamlit analytics view.

**Tech Stack:** Python 3.14, SQLite3, `uiautomator2`, `adbutils`, Streamlit, `yt-dlp`.

**Spec:** `C:\Users\João\.gemini\antigravity-cli\brain\393fffb4-8f12-4f68-bb31-29cd5a89663f\project_architecture_spec.md`

## Global Constraints
- **Ponytail standard:** Minimum viable code, no heavy ORM; use Python's built-in `sqlite3`.
- **Lite App Compatibility:** Target package IDs:
  - TikTok Lite: `com.zhiliaoapp.musically.go`
  - Instagram Lite: `com.instagram.lite`
  - YouTube (Shorts): `com.google.android.youtube`
- **Anti-ban & Humanized input:** Random coordinate jitter (+/- 5px) and random pauses (1.5s - 3.5s) on every UI click.
- **Fail-safe:** If an upload step fails, the queue marks the item as `failed` with an error log rather than hanging the application.

## Review Focus
1. **Network or Dialog Popups on App Launch:** Lite apps often display "Allow storage" or "Update app" prompts; the UI automation must dismiss common dialogs or continue gracefully.
2. **Post Rate Limiter:** Ensure the scheduler never exceeds the configured `posts_per_day` limit per account.
3. **Template Variable Resolution:** Missing variables like `{movie}` or `{caption}` must fall back to default text rather than raising a `KeyError`.
4. **App Not Installed:** If a selected platform app is missing on the emulator, raise a clear error before attempting automation.
5. **Database Concurrency:** Streamlit and background scheduler thread must safely access SQLite without lock errors (use `check_same_thread=False` and short transactions).

---

### Task 1: SQLite Storage & Template Configuration (`db.py` & `config.py`)

**Files:**
- Create: `db.py`
- Modify: `config.py`
- Test: `test_smoke.py`

**Interfaces:**
- `db.init_db()`: Initializes tables `posts_queue` and `metrics`.
- `db.enqueue_post(clip_path: str, platform: str, device_serial: str, title: str, caption: str, scheduled_at: str) -> int`
- `db.get_pending_posts() -> list[dict]`
- `db.update_post_status(post_id: int, status: str, error_msg: str = "")`
- `config.get_caption_template() -> str` / `config.save_caption_template(template: str)`
- `config.get_posting_schedule_settings() -> dict` (posts_per_day, interval_hours)

- [ ] **Step 1: Write smoke tests for queue insertion, template formatting, and database queries**
- [ ] **Step 2: Implement SQLite tables and queue operations in `db.py`**
- [ ] **Step 3: Add template configuration and scheduling settings in `config.py`**
- [ ] **Step 4: Run smoke tests to verify database operations pass**

---

### Task 2: UI Automation Flows for TikTok Lite, Instagram Lite & YouTube Shorts (`poster.py`)

**Files:**
- Create: `poster.py`
- Test: `test_smoke.py`

**Interfaces:**
- `poster.post_clip(device_serial: str, platform: str, video_path: str, caption: str) -> bool`
- Supports `platform in ["tiktok_lite", "instagram_lite", "youtube_shorts"]`.
- Pushes video to `/sdcard/DCIM/Camera/`, launches target app, navigates creation UI, sets caption, taps Publish, and confirms upload.

- [ ] **Step 1: Implement humanized click & type helpers (random jitter + randomized delays)**
- [ ] **Step 2: Implement `post_tiktok_lite(d, video_name, caption)`**
- [ ] **Step 3: Implement `post_instagram_lite(d, video_name, caption)`**
- [ ] **Step 4: Implement `post_youtube_shorts(d, video_name, title, caption)`**
- [ ] **Step 5: Write unit tests verifying dispatch logic and error handling**

---

### Task 3: Background Scheduler Worker (`scheduler.py`)

**Files:**
- Create: `scheduler.py`
- Test: `test_smoke.py`

**Interfaces:**
- `scheduler.start_scheduler_loop()`: Spawns a daemon thread checking pending posts in `db.py`.
- Enforces `posts_per_day` limit and `interval_hours` delay between consecutive uploads.
- Invokes `poster.post_clip()` when scheduled time arrives and marks post status.

- [ ] **Step 1: Write unit test validating interval calculation and daily post count limiter**
- [ ] **Step 2: Implement `scheduler.py` worker thread**
- [ ] **Step 3: Verify worker loop runs safely and respects intervals**

---

### Task 4: Public Metrics Collector (`metrics.py`)

**Files:**
- Create: `metrics.py`
- Test: `test_smoke.py`

**Interfaces:**
- `metrics.fetch_youtube_shorts_metrics(video_url: str) -> dict`: Extracts views, likes, comments using `yt-dlp` metadata dump (zero emulator cost).
- `metrics.record_metrics_snapshot(post_id: int, views: int, likes: int, comments: int)`
- `metrics.get_account_analytics() -> dict`: Aggregates total views and growth trends for the dashboard.

- [ ] **Step 1: Implement `fetch_youtube_shorts_metrics` using `yt-dlp` dump json**
- [ ] **Step 2: Store metric snapshots into `metrics` table**
- [ ] **Step 3: Smoke test metric retrieval and snapshot storage**

---

### Task 5: Dashboard Tabs: Fila de Postagem, Métricas & Configuração de Templates (`app.py`)

**Files:**
- Modify: `app.py`

**Interfaces:**
- **Aba Configurações:** Edit caption template (`{title}`, `{hook}`, `{hashtags}`), set `Posts por Dia` (1-5), set `Intervalo entre Posts (horas)`.
- **Aba Fila & Agendamento:** View pending/completed posts, schedule a generated clip to TikTok Lite / Instagram Lite / YouTube Shorts with 1-click.
- **Aba Métricas:** Display performance charts (views per post, total impressions, success rate).

- [ ] **Step 1: Add Template & Scheduler settings section to Settings tab**
- [ ] **Step 2: Add "Agendar Postagem" action under each generated clip in Tab 1**
- [ ] **Step 3: Create dedicated "📅 Fila de Postagem" tab with manual "Postar Agora" trigger**
- [ ] **Step 4: Create dedicated "📊 Dashboard de Métricas" tab with metrics overview**
- [ ] **Step 5: Run full integration smoke test and launch app**
