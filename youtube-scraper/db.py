import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "youtube_data.db"

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
_PLATFORM = "youtube"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id      TEXT PRIMARY KEY,
            title         TEXT,
            description   TEXT,
            channel_id    TEXT,
            channel_name  TEXT,
            published_at  TEXT,
            duration      TEXT,
            view_count    INTEGER DEFAULT 0,
            like_count    INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            tags          TEXT,
            thumbnail_url TEXT,
            post_url      TEXT,
            scraped_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS comments (
            comment_id        TEXT PRIMARY KEY,
            video_id          TEXT,
            author_name       TEXT,
            author_channel_id TEXT,
            text              TEXT,
            likes             INTEGER DEFAULT 0,
            published_at      TEXT,
            updated_at        TEXT,
            is_reply          INTEGER DEFAULT 0,
            parent_id         TEXT,
            reply_count       INTEGER DEFAULT 0,
            scraped_at        TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );

        CREATE INDEX IF NOT EXISTS idx_comments_video      ON comments(video_id);
        CREATE INDEX IF NOT EXISTS idx_comments_published  ON comments(published_at);
        CREATE INDEX IF NOT EXISTS idx_videos_channel      ON videos(channel_id);
        CREATE INDEX IF NOT EXISTS idx_videos_published    ON videos(published_at);
        """)
        conn.commit()
        print(f"[DB] Initialized at {DB_PATH}")
    finally:
        conn.close()


def save_video(v: dict):
    conn = get_conn()
    try:
        conn.execute("""
        INSERT INTO videos
            (video_id, title, description, channel_id, channel_name, published_at,
             duration, view_count, like_count, comment_count, tags, thumbnail_url,
             post_url, scraped_at)
        VALUES
            (:video_id, :title, :description, :channel_id, :channel_name, :published_at,
             :duration, :view_count, :like_count, :comment_count, :tags, :thumbnail_url,
             :post_url, :scraped_at)
        ON CONFLICT(video_id) DO UPDATE SET
            title         = excluded.title,
            description   = excluded.description,
            view_count    = MAX(view_count,    excluded.view_count),
            like_count    = MAX(like_count,    excluded.like_count),
            comment_count = MAX(comment_count, excluded.comment_count),
            tags          = excluded.tags,
            scraped_at    = excluded.scraped_at
        """, {**v, "scraped_at": datetime.now().isoformat()})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_post(_PLATFORM, v, _BRAND)


def save_comment(c: dict):
    conn = get_conn()
    try:
        conn.execute("""
        INSERT INTO comments
            (comment_id, video_id, author_name, author_channel_id, text, likes,
             published_at, updated_at, is_reply, parent_id, reply_count, scraped_at)
        VALUES
            (:comment_id, :video_id, :author_name, :author_channel_id, :text, :likes,
             :published_at, :updated_at, :is_reply, :parent_id, :reply_count, :scraped_at)
        ON CONFLICT(comment_id) DO UPDATE SET
            likes       = MAX(likes, excluded.likes),
            reply_count = MAX(reply_count, excluded.reply_count),
            scraped_at  = excluded.scraped_at
        """, {**c, "is_reply": int(c.get("is_reply", False)),
              "scraped_at": datetime.now().isoformat()})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_comment(_PLATFORM, c)


def delete_video(video_id: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM comments WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM videos   WHERE video_id = ?", (video_id,))
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict:
    conn = get_conn()
    try:
        videos   = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        likes    = conn.execute("SELECT COALESCE(SUM(like_count),0)  FROM videos").fetchone()[0]
        views    = conn.execute("SELECT COALESCE(SUM(view_count),0)  FROM videos").fetchone()[0]
        return {"videos": videos, "comments": comments, "likes": likes, "views": views}
    finally:
        conn.close()


def get_all_videos() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY published_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_comments() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM comments ORDER BY published_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
