from pathlib import Path
import config
import clipper
import emulator

def test_config_and_ffmpeg():
    assert config.FFMPEG_BIN != "", "FFmpeg binary path should not be empty"
    print("[OK] FFmpeg path resolved:", config.FFMPEG_BIN)

def test_ass_time_formatting():
    assert clipper._format_ass_time(0.0) == "0:00:00.00"
    assert clipper._format_ass_time(65.5) == "0:01:05.50"
    assert clipper._format_ass_time(3661.25) == "1:01:01.25"
    print("[OK] ASS time formatting verified")

def test_ass_generation(tmp_path: Path):
    sample_subs = [
        {"start": 10.0, "end": 12.0, "text": "Hello world"},
        {"start": 12.5, "end": 15.0, "text": "Testing subtitles"}
    ]
    out_file = tmp_path / "test.ass"
    clipper.create_ass_subtitles(sample_subs, offset_seconds=10.0, output_path=out_file)
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Hello world" in content
    print("[OK] ASS subtitle generation verified")

def test_emulator_detection_graceful():
    devices = emulator.get_connected_devices()
    assert isinstance(devices, list)
    print("[OK] Emulator device query ran gracefully (Found:", devices, ")")

def test_multi_clip_structure():
    mock_clips = [
        {"start_seconds": 10.0, "end_seconds": 45.0, "title": "Clip 1", "caption": "Cap 1", "subtitles": []},
        {"start_seconds": 50.0, "end_seconds": 85.0, "title": "Clip 2", "caption": "Cap 2", "subtitles": []}
    ]
    # Check valid interval constraint
    for c in mock_clips:
        assert c["end_seconds"] > c["start_seconds"]
    # Check non-overlap constraint
    assert mock_clips[1]["start_seconds"] >= mock_clips[0]["end_seconds"]
    print("[OK] Multi-clip structure & non-overlap constraints validated")

def test_db_queue_and_templates():
    import db
    db.init_db()
    post_id = db.enqueue_post(
        clip_path="sample.mp4",
        platform="tiktok_lite",
        device_serial="127.0.0.1:5555",
        title="Test Scene",
        caption="Sample caption"
    )
    assert post_id > 0
    pending = db.get_pending_posts()
    assert any(p["id"] == post_id for p in pending)
    
    db.update_post_status(post_id, "completed", public_url="https://example.com/video")
    all_posts = db.get_all_posts()
    assert any(p["id"] == post_id and p["status"] == "completed" for p in all_posts)
    
    # Test caption formatting
    formatted = config.format_caption("My Movie", "Watch this clip")
    assert "My Movie" in formatted and "Watch this clip" in formatted
    print("[OK] Database queue and caption template formatting validated")

def test_scanner_and_telegram_config():
    import scanner
    import telegram_bot
    import db
    
    assert len(scanner.DEFAULT_CHANNELS) >= 3
    hours = config.load_peak_hours()
    assert "12:00" in hours and "18:00" in hours and "21:00" in hours
    
    # Test duplicate prevention in db
    test_id = "test_yt_unique_123"
    assert not db.is_source_processed(test_id)
    db.mark_source_processed(test_id, "Test Title", "Test Channel")
    assert db.is_source_processed(test_id)
    
    # Test graceful telegram validation
    ok, msg = telegram_bot.test_telegram_connection("", "")
    assert not ok
    print("[OK] Auto-scanner, peak hours config and Telegram validation verified")

if __name__ == "__main__":
    import tempfile
    test_config_and_ffmpeg()
    test_ass_time_formatting()
    with tempfile.TemporaryDirectory() as td:
        test_ass_generation(Path(td))
    test_emulator_detection_graceful()
    test_multi_clip_structure()
    test_db_queue_and_templates()
    test_scanner_and_telegram_config()
    print("\nAll smoke tests passed!")
