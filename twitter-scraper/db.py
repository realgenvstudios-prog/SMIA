import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "twitter_data.db"

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
_PLATFORM = "twitter"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id        TEXT UNIQUE,
            author_username TEXT,
            author_name     TEXT,
            text            TEXT,
            timestamp       TEXT,
            likes           INTEGER DEFAULT 0,
            replies_count   INTEGER DEFAULT 0,
            retweets        INTEGER DEFAULT 0,
            views           INTEGER DEFAULT 0,
            post_url        TEXT,
            hashtags        TEXT,
            source          TEXT,
            scraped_at      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            reply_id        TEXT UNIQUE,
            tweet_id        TEXT,
            author_username TEXT,
            author_name     TEXT,
            text            TEXT,
            likes           INTEGER DEFAULT 0,
            timestamp       TEXT,
            is_reply        INTEGER DEFAULT 1,
            parent_id       TEXT,
            scraped_at      TEXT,
            FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def save_tweet(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO tweets (
                tweet_id, author_username, author_name, text, timestamp,
                likes, replies_count, retweets, views,
                post_url, hashtags, source, scraped_at
            ) VALUES (
                :tweet_id, :author_username, :author_name, :text, :timestamp,
                :likes, :replies_count, :retweets, :views,
                :post_url, :hashtags, :source, :scraped_at
            )
            ON CONFLICT(tweet_id) DO UPDATE SET
                likes         = MAX(excluded.likes, likes),
                replies_count = MAX(excluded.replies_count, replies_count),
                retweets      = MAX(excluded.retweets, retweets),
                views         = MAX(excluded.views, views),
                text          = CASE WHEN excluded.text != '' THEN excluded.text ELSE text END,
                scraped_at    = excluded.scraped_at
        """, {**data, "scraped_at": now})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_post(_PLATFORM, data, _BRAND)


def save_reply(data: dict):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("""
            INSERT INTO replies (
                reply_id, tweet_id, author_username, author_name, text,
                likes, timestamp, is_reply, parent_id, scraped_at
            ) VALUES (
                :reply_id, :tweet_id, :author_username, :author_name, :text,
                :likes, :timestamp, :is_reply, :parent_id, :scraped_at
            )
            ON CONFLICT(reply_id) DO UPDATE SET
                likes      = MAX(excluded.likes, likes),
                scraped_at = excluded.scraped_at
        """, {**data, "scraped_at": now})
        conn.commit()
    finally:
        conn.close()
    if _SUPABASE:
        _upsert_comment(_PLATFORM, data)


def delete_tweet(tweet_id: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM tweets  WHERE tweet_id = ?", (tweet_id,))
        conn.execute("DELETE FROM replies WHERE tweet_id = ?", (tweet_id,))
        conn.commit()
    finally:
        conn.close()


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {
        "total_tweets":  c.execute("SELECT COUNT(*) FROM tweets").fetchone()[0],
        "total_replies": c.execute("SELECT COUNT(*) FROM replies").fetchone()[0],
        "total_likes":   c.execute("SELECT SUM(likes) FROM tweets").fetchone()[0] or 0,
        "total_views":   c.execute("SELECT SUM(views) FROM tweets").fetchone()[0] or 0,
        "total_retweets":c.execute("SELECT SUM(retweets) FROM tweets").fetchone()[0] or 0,
    }
    conn.close()
    return stats
