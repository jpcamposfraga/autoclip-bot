# Multi-Clip Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable AutoClip Factory to identify, score, and render multiple non-overlapping 9:16 vertical clips (between 1 and 5) from a single YouTube video when duration permits.

**Architecture:** Update the Gemini prompt and JSON schema in `clipper.py` to return a list of clips (`clips: [...]`). Implement a batch rendering pipeline in `clipper.py` that processes each segment into its own vertical file with subtitles. Update `app.py` with a slider for max clips and a multi-card preview grid where each clip can be inspected and pushed to the emulator independently.

**Tech Stack:** Python 3.14, `google-genai` (Gemini Flash), `yt-dlp`, FFmpeg, Streamlit.

**Spec:** `C:\Users\João\.gemini\antigravity-cli\brain\393fffb4-8f12-4f68-bb31-29cd5a89663f\project_architecture_spec.md`

## Global Constraints
- Must maintain ponytail philosophy: smallest complete diff, no unnecessary boilerplate.
- Backward compatibility: if video has < 90 seconds, gracefully extract only 1 clip without error.
- All clips must be strictly non-overlapping (at least 3 seconds apart).

## Review Focus
1. **Video shorter than requested clip count:** When a 60s video is submitted with `max_clips=3`, the AI should return only 1 valid clip without error.
2. **Overlapping timestamps from AI:** If the LLM generates overlapping intervals, the code must adjust or drop the overlapping candidate.
3. **Partial render failure:** If clip 2 fails to render, clip 1 must remain intact and playable.
4. **Empty or missing subtitles:** Rendering must succeed even if subtitles are missing or empty for a segment.
5. **Session state handling in Streamlit:** Must store a list of clips (`st.session_state["last_clips"] = [...]`) without breaking existing single-clip references.

---

### Task 1: Update Gemini Prompt and Schema for Multiple Clips

**Files:**
- Modify: `clipper.py:30-80`
- Test: `test_smoke.py`

**Interfaces:**
- `analyze_scene_with_gemini(audio_path: Path, api_key: str, max_clips: int = 3, status_callback=None) -> list[dict]`
- Returns: `list[dict]` where each dict has keys: `start_seconds`, `end_seconds`, `title`, `caption`, `subtitles`.

- [ ] **Step 1: Write smoke test for multi-clip parsing & non-overlap validation**
Add test in `test_smoke.py` validating that a sample multi-clip payload passes duration and overlap checks.

- [ ] **Step 2: Run test to verify initial state**
Run: `& "C:\Users\João\AppData\Local\Python\bin\python.exe" test_smoke.py`

- [ ] **Step 3: Update `analyze_scene_with_gemini` in `clipper.py`**
Modify prompt to request up to `max_clips` non-overlapping segments (each 30-60s) and return `{"clips": [...]}`. Parse the response into a validated list of clips.

- [ ] **Step 4: Verify test passes**
Run: `& "C:\Users\João\AppData\Local\Python\bin\python.exe" test_smoke.py`

---

### Task 2: Implement Batch Rendering in `clipper.py`

**Files:**
- Modify: `clipper.py`
- Test: `test_smoke.py`

**Interfaces:**
- `render_clips_batch(video_path: Path, clips_data: list[dict], video_id: str, status_callback=None) -> list[dict]`
- Takes the video and the list of clip metadata, renders each vertical clip as `{video_id}_part{i+1}.mp4`, burns subtitles, and attaches `"path"` to each clip dict.

- [ ] **Step 1: Write test for batch filename and metadata formatting**
Add test asserting that given 2 clip items, `render_clips_batch` structures unique paths.

- [ ] **Step 2: Implement `render_clips_batch`**
Iterate through `clips_data`, call `render_vertical_clip` for each segment with progress callbacks, and return the updated list of clip dicts.

- [ ] **Step 3: Verify tests pass**
Run: `& "C:\Users\João\AppData\Local\Python\bin\python.exe" test_smoke.py`

---

### Task 3: Streamlit UI Multi-Clip Grid & Gallery Injection

**Files:**
- Modify: `app.py`

**Interfaces:**
- Streamlit input: `max_clips = st.slider("Quantidade máxima de cortes", min_value=1, max_value=5, value=3)`
- Session State: `st.session_state["last_clips"] = [...]`
- UI: Display a column/card for each generated clip with its own video player, title, caption copy box, and emulator push button.

- [ ] **Step 1: Update session state and add the `max_clips` slider in `app.py`**
- [ ] **Step 2: Update the processing trigger to call `render_clips_batch`**
- [ ] **Step 3: Replace single-clip preview with a multi-clip grid (columns or expandable cards)**
- [ ] **Step 4: Smoke test UI imports and emulator push logic**
Run: `& "C:\Users\João\AppData\Local\Python\bin\python.exe" test_smoke.py`
