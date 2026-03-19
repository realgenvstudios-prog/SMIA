import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "facebook_data.db"

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
_PLATFORM = "facebook"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id         TEXT UNIQUE,
            page_name       TEXT,
            text            TEXT,
            timestamp       TEXT,
            likes           INTEGER DEFAULT 0,
            comments_count  INTEGER DEFAULT 0,
            shares          INTEGER DEFAULT 0,
            views           INTEGER DEFAULT 0,
            reactions_like  INTEGER DEFAULT 0,
            reactions_love  INTEGER DEFAULT 0,
            reactions_haha  INTEGER DEFAULT 0,
            reactions_wow   INTEGER DEFAULT 0,
            reactions_sad   INTEGER DEFAULT 0,
            reactions_angry INTEGER DEFAULT 0,
            post_url        TEXT,
            media_type      TEXT,
            scraped_at      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id  TEXT UNIQUE,
            post_id     TEXT,
            author_name TEXT,
            text        TEXT,
            likes       INTEGER DEFAULT 0,
            timestamp   TEXT,
            is_reply    INTEGER DEFAULT 0,
            parent_id   TEXT,
            scraped_at  TEXT,
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
                post_id, page_name, text, timestamp, likes, comments_count,
                shares, views, reactions_like, reactions_love, reactions_haha,
                reactions_wow, reactions_sad, reactions_angry, post_url,
                media_type, scraped_at
            ) VALUES (
                :post_id, :page_name, :text, :timestamp, :likes, :comments_count,
                :shares, :views, :reactions_like, :reactions_love, :reactions_haha,
                :reactions_wow, :reactions_sad, :reactions_angry, :post_url,
                :media_type, :scraped_at
            )
            ON CONFLICT(post_id) DO UPDATE SET
                likes           = excluded.likes,
                comments_count  = excluded.comments_count,
                shares          = excluded.shares,
                views           = excluded.views,
                reactions_like  = excluded.reactions_like,
                reactions_love  = excluded.reactions_love,
                reactions_haha  = excluded.reactions_haha,
                reactions_wow   = excluded.reactions_wow,
                reactions_sad   = excluded.reactions_sad,
                reactions_angry = excluded.reactions_angry,
                scraped_at      = excluded.scraped_at
        """, {**data, "scraped_at": now})
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
                comment_id, post_id, author_name, text, likes,
                timestamp, is_reply, parent_id, scraped_at
            ) VALUES (
                :comment_id, :post_id, :author_name, :text, :likes,
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
        "total_posts":    c.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "total_comments": c.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "total_likes":    c.execute("SELECT SUM(likes) FROM posts").fetchone()[0] or 0,
        "total_shares":   c.execute("SELECT SUM(shares) FROM posts").fetchone()[0] or 0,
    }
    conn.close()
    return stats
