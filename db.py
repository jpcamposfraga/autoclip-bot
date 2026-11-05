import sqlite3
from pathlib import Path
from datetime import datetime
from config import BASE_DIR

DB_PATH = BASE_DIR / "autoclip.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS posts_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_path TEXT NOT NULL,
            platform TEXT NOT NULL,
            device_serial TEXT NOT NULL,
            title TEXT,
            caption TEXT,
            scheduled_at TIMESTAMP,
            posted_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            error_msg TEXT,
            public_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts_queue(id)
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            youtube_id TEXT UNIQUE NOT NULL,
            title TEXT,
            channel_url TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

def enqueue_post(clip_path: str, platform: str, device_serial: str, title: str, caption: str, scheduled_at: str = None) -> int:
    if not scheduled_at:
        scheduled_at = datetime.now().isoformat()
    with get_connection() as conn:
        cur = conn.execute("""
        INSERT INTO posts_queue (clip_path, platform, device_serial, title, caption, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (clip_path, platform, device_serial, title, caption, scheduled_at))
        conn.commit()
        return cur.lastrowid

def get_pending_posts() -> list[dict]:
    with get_connection() as conn:
        cur = conn.execute("""
        SELECT * FROM posts_queue
        WHERE status = 'pending' AND datetime(scheduled_at) <= datetime('now')
        ORDER BY scheduled_at ASC
        """)
        return [dict(row) for row in cur.fetchall()]

def get_all_posts(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM posts_queue ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]

def update_post_status(post_id: int, status: str, error_msg: str = "", public_url: str = ""):
    with get_connection() as conn:
        posted_at = datetime.now().isoformat() if status == "completed" else None
        conn.execute("""
        UPDATE posts_queue
        SET status = ?, error_msg = ?, public_url = COALESCE(NULLIF(?, ''), public_url),
            posted_at = COALESCE(?, posted_at)
        WHERE id = ?
        """, (status, error_msg, public_url, posted_at, post_id))
        conn.commit()

def record_metric(post_id: int, views: int, likes: int, comments: int):
    with get_connection() as conn:
        conn.execute("""
        INSERT INTO metrics (post_id, views, likes, comments)
        VALUES (?, ?, ?, ?)
        """, (post_id, views, likes, comments))
        conn.commit()

def get_metrics_summary() -> dict:
    with get_connection() as conn:
        cur = conn.execute("""
        SELECT 
            COUNT(DISTINCT p.id) as total_posts,
            COALESCE(SUM(m.views), 0) as total_views,
            COALESCE(SUM(m.likes), 0) as total_likes,
            COALESCE(SUM(m.comments), 0) as total_comments
        FROM posts_queue p
        LEFT JOIN (
            SELECT post_id, views, likes, comments
            FROM metrics
            WHERE id IN (SELECT MAX(id) FROM metrics GROUP BY post_id)
        ) m ON p.id = m.post_id
        WHERE p.status = 'completed'
        """)
        row = cur.fetchone()
        return dict(row) if row else {"total_posts": 0, "total_views": 0, "total_likes": 0, "total_comments": 0}

def is_source_processed(youtube_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("SELECT 1 FROM processed_sources WHERE youtube_id = ?", (youtube_id,))
        return cur.fetchone() is not None

def mark_source_processed(youtube_id: str, title: str = "", channel_url: str = ""):
    with get_connection() as conn:
        conn.execute("""
        INSERT OR IGNORE INTO processed_sources (youtube_id, title, channel_url)
        VALUES (?, ?, ?)
        """, (youtube_id, title, channel_url))
        conn.commit()

def get_processed_sources_count() -> int:
    with get_connection() as conn:
        cur = conn.execute("SELECT COUNT(*) as cnt FROM processed_sources")
        row = cur.fetchone()
        return row["cnt"] if row else 0

init_db()
