import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "instagram_data.db"

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
_PLATFORM = "instagram"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id          TEXT UNIQUE,
            author_username  TEXT,
            author_name      TEXT,
            caption          TEXT,
            timestamp        TEXT,
            likes            INTEGER DEFAULT 0,
            comments_count   INTEGER DEFAULT 0,
            views            INTEGER DEFAULT 0,
            post_url         TEXT,
            media_type       TEXT,
            hashtags         TEXT,
            source           TEXT,
            scraped_at       TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id       TEXT UNIQUE,
            post_id          TEXT,
            author_username  TEXT,
            text             TEXT,
            likes            INTEGER DEFAULT 0,
            timestamp        TEXT,
            is_reply         INTEGER DEFAULT 0,
            parent_id        TEXT,
            scraped_at       TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(post_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def save_post(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO posts (
                post_id, author_username, author_name, caption, timestamp,
                likes, comments_count, views, post_url, media_type,
                hashtags, source, scraped_at
            ) VALUES (
                :post_id, :author_username, :author_name, :caption, :timestamp,
                :likes, :comments_count, :views, :post_url, :media_type,
                :hashtags, :source, :scraped_at
            )
            ON CONFLICT(post_id) DO UPDATE SET
                likes          = MAX(excluded.likes, likes),
                comments_count = MAX(excluded.comments_count, comments_count),
                views          = MAX(excluded.views, views),
                author_username = CASE WHEN excluded.author_username != '' THEN excluded.author_username ELSE author_username END,
                author_name    = CASE WHEN excluded.author_name != ''    THEN excluded.author_name    ELSE author_name    END,
                caption        = CASE WHEN excluded.caption != ''        THEN excluded.caption        ELSE caption        END,
                timestamp      = CASE WHEN excluded.timestamp != ''      THEN excluded.timestamp      ELSE timestamp      END,
                media_type     = CASE WHEN excluded.media_type != ''     THEN excluded.media_type     ELSE media_type     END,
                hashtags       = CASE WHEN excluded.hashtags != ''       THEN excluded.hashtags       ELSE hashtags       END,
                scraped_at     = excluded.scraped_at
        """, {
            "post_id":         data.get("post_id", ""),
            "author_username": data.get("author_username", ""),
            "author_name":     data.get("author_name", ""),
            "caption":         data.get("caption", ""),
            "timestamp":       data.get("timestamp", ""),
            "likes":           data.get("likes", 0),
            "comments_count":  data.get("comments_count", 0),
            "views":           data.get("views", 0),
            "post_url":        data.get("post_url", ""),
            "media_type":      data.get("media_type", ""),
            "hashtags":        data.get("hashtags", ""),
            "source":          data.get("source", ""),
            "scraped_at":      now,
        })
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_post(_PLATFORM, data, _BRAND)


def save_comment(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO comments (
                comment_id, post_id, author_username, text, likes,
                timestamp, is_reply, parent_id, scraped_at
            ) VALUES (
                :comment_id, :post_id, :author_username, :text, :likes,
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


def delete_post(post_id: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        conn.commit()
    finally:
        conn.close()


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {
        "total_posts":    c.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "total_comments": c.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "total_likes":    c.execute("SELECT SUM(likes) FROM posts").fetchone()[0] or 0,
        "total_views":    c.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
    }
    conn.close()
    return stats
