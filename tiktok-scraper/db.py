import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "tiktok_data.db"

# ── Supabase sync (optional — fails gracefully if not configured) ─────────────
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv as _ld
    _ld(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), ".env"), override=False)
    from supabase_sync import upsert_post as _upsert_post, upsert_comment as _upsert_comment
    _SUPABASE = True
except ImportError:
    _SUPABASE = False

_BRAND    = "konnected-minds"
_PLATFORM = "tiktok"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id        TEXT UNIQUE,
            author_name     TEXT,
            author_username TEXT,
            description     TEXT,
            timestamp       TEXT,
            likes           INTEGER DEFAULT 0,
            comments_count  INTEGER DEFAULT 0,
            shares          INTEGER DEFAULT 0,
            views           INTEGER DEFAULT 0,
            bookmarks       INTEGER DEFAULT 0,
            video_url       TEXT,
            music_title     TEXT,
            hashtags        TEXT,
            source          TEXT,
            scraped_at      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id  TEXT UNIQUE,
            video_id    TEXT,
            author_name TEXT,
            text        TEXT,
            likes       INTEGER DEFAULT 0,
            timestamp   TEXT,
            is_reply    INTEGER DEFAULT 0,
            parent_id   TEXT,
            scraped_at  TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def save_video(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO videos (
                video_id, author_name, author_username, description, timestamp,
                likes, comments_count, shares, views, bookmarks,
                video_url, music_title, hashtags, source, scraped_at
            ) VALUES (
                :video_id, :author_name, :author_username, :description, :timestamp,
                :likes, :comments_count, :shares, :views, :bookmarks,
                :video_url, :music_title, :hashtags, :source, :scraped_at
            )
            ON CONFLICT(video_id) DO UPDATE SET
                likes          = excluded.likes,
                comments_count = excluded.comments_count,
                shares         = excluded.shares,
                views          = excluded.views,
                bookmarks      = excluded.bookmarks,
                music_title    = CASE WHEN excluded.music_title != '' THEN excluded.music_title ELSE music_title END,
                scraped_at     = excluded.scraped_at
        """, {**data, "scraped_at": now})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_post(_PLATFORM, data, _BRAND)


def delete_video(video_id: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM comments WHERE video_id = ?", (video_id,))
        conn.commit()
    finally:
        conn.close()


def save_comment(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO comments (
                comment_id, video_id, author_name, text, likes,
                timestamp, is_reply, parent_id, scraped_at
            ) VALUES (
                :comment_id, :video_id, :author_name, :text, :likes,
                :timestamp, :is_reply, :parent_id, :scraped_at
            )
            ON CONFLICT(comment_id) DO UPDATE SET
                likes      = excluded.likes,
                scraped_at = excluded.scraped_at
        """, {**data, "scraped_at": now})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_comment(_PLATFORM, data)


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {
        "total_videos":   c.execute("SELECT COUNT(*) FROM videos").fetchone()[0],
        "total_comments": c.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "total_likes":    c.execute("SELECT SUM(likes) FROM videos").fetchone()[0] or 0,
        "total_views":    c.execute("SELECT SUM(views) FROM videos").fetchone()[0] or 0,
        "total_shares":   c.execute("SELECT SUM(shares) FROM videos").fetchone()[0] or 0,
    }
    conn.close()
    return stats
