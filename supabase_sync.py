"""
supabase_sync.py — Shared Supabase sync module for all SMIP scrapers.

Place at: /Users/Ted/supabase_sync.py  (one level above each scraper directory)

Each scraper's db.py imports it with:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from supabase_sync import upsert_post as _upsert_post, upsert_comment as _upsert_comment

Required env vars (in /Users/Ted/.env or any scraper's own .env):
    SUPABASE_URL=https://your-project.supabase.co
    SUPABASE_KEY=your-service-role-key

Failure policy: every public function catches all exceptions, logs a warning,
and returns False/0 — the scraper is never interrupted by sync failures.
"""

import os
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("supabase_sync")

_client = None
_brands_cache: dict = {}   # slug -> brand_id UUID string


# ── Client initialisation ─────────────────────────────────────────────────────

def _get_client():
    """Lazy-init Supabase client. Returns None if env vars are missing."""
    global _client
    if _client is not None:
        return _client
    try:
        from dotenv import load_dotenv
        # Load root .env (override=False so scraper-level .env takes precedence if loaded first)
        root_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(dotenv_path=root_env, override=False)

        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            log.warning("[Supabase] SUPABASE_URL / SUPABASE_KEY not set — sync disabled.")
            return None
        _client = create_client(url, key)
        log.info("[Supabase] Client initialised.")
    except Exception as e:
        log.error(f"[Supabase] Failed to initialise client: {e}")
    return _client


def _resolve_brand_id(brand_slug: str) -> Optional[str]:
    """Resolve brand slug to UUID, caching the result."""
    if not brand_slug:
        return None
    if brand_slug in _brands_cache:
        return _brands_cache[brand_slug]
    client = _get_client()
    if not client:
        return None
    try:
        res = client.table("brands").select("id").eq("slug", brand_slug).single().execute()
        brand_id = res.data["id"]
        _brands_cache[brand_slug] = brand_id
        return brand_id
    except Exception as e:
        log.error(f"[Supabase] Could not resolve brand '{brand_slug}': {e}")
        return None


# ── Field mappers (platform dict → unified post row) ─────────────────────────

def _map_youtube(data: dict) -> tuple[dict, dict]:
    unified = {
        "platform_post_id": data.get("video_id"),
        "author_name":      data.get("channel_name"),
        "author_handle":    data.get("channel_id"),
        "content":          data.get("description"),
        "post_url":         data.get("post_url"),
        "media_type":       "video",
        "published_at":     data.get("published_at") or None,
        "likes":            data.get("like_count", 0),
        "comments_count":   data.get("comment_count", 0),
        "shares":           0,
        "views":            data.get("view_count", 0),
    }
    extra = {
        "title":         data.get("title"),
        "duration":      data.get("duration"),
        "tags":          data.get("tags"),
        "thumbnail_url": data.get("thumbnail_url"),
        "channel_id":    data.get("channel_id"),
    }
    return unified, extra


def _map_tiktok(data: dict) -> tuple[dict, dict]:
    unified = {
        "platform_post_id": data.get("video_id"),
        "author_name":      data.get("author_name"),
        "author_handle":    data.get("author_username"),
        "content":          data.get("description"),
        "post_url":         data.get("video_url"),
        "media_type":       "video",
        "published_at":     data.get("timestamp") or None,
        "likes":            data.get("likes", 0),
        "comments_count":   data.get("comments_count", 0),
        "shares":           data.get("shares", 0),
        "views":            data.get("views", 0),
    }
    extra = {
        "bookmarks":   data.get("bookmarks", 0),
        "music_title": data.get("music_title"),
        "hashtags":    data.get("hashtags"),
        "source":      data.get("source"),
    }
    return unified, extra


def _map_instagram(data: dict) -> tuple[dict, dict]:
    unified = {
        "platform_post_id": data.get("post_id"),
        "author_name":      data.get("author_name"),
        "author_handle":    data.get("author_username"),
        "content":          data.get("caption"),
        "post_url":         data.get("post_url"),
        "media_type":       data.get("media_type"),
        "published_at":     data.get("timestamp") or None,
        "likes":            data.get("likes", 0),
        "comments_count":   data.get("comments_count", 0),
        "shares":           0,
        "views":            data.get("views", 0),
    }
    extra = {
        "hashtags": data.get("hashtags"),
        "source":   data.get("source"),
    }
    return unified, extra


def _map_facebook(data: dict) -> tuple[dict, dict]:
    unified = {
        "platform_post_id": data.get("post_id"),
        "author_name":      data.get("page_name"),
        "author_handle":    data.get("page_name"),
        "content":          data.get("text"),
        "post_url":         data.get("post_url"),
        "media_type":       data.get("media_type"),
        "published_at":     data.get("timestamp") or None,
        "likes":            data.get("likes", 0),
        "comments_count":   data.get("comments_count", 0),
        "shares":           data.get("shares", 0),
        "views":            data.get("views", 0),
    }
    extra = {
        "reactions_like":  data.get("reactions_like", 0),
        "reactions_love":  data.get("reactions_love", 0),
        "reactions_haha":  data.get("reactions_haha", 0),
        "reactions_wow":   data.get("reactions_wow", 0),
        "reactions_sad":   data.get("reactions_sad", 0),
        "reactions_angry": data.get("reactions_angry", 0),
    }
    return unified, extra


def _map_twitter(data: dict) -> tuple[dict, dict]:
    unified = {
        "platform_post_id": data.get("tweet_id"),
        "author_name":      data.get("author_name"),
        "author_handle":    data.get("author_username"),
        "content":          data.get("text"),
        "post_url":         data.get("post_url"),
        "media_type":       "tweet",
        "published_at":     data.get("timestamp") or None,
        "likes":            data.get("likes", 0),
        "comments_count":   data.get("replies_count", 0),
        "shares":           data.get("retweets", 0),
        "views":            data.get("views", 0),
    }
    extra = {
        "retweets": data.get("retweets", 0),
        "hashtags": data.get("hashtags"),
        "source":   data.get("source"),
    }
    return unified, extra


_MAPPERS = {
    "youtube":   _map_youtube,
    "tiktok":    _map_tiktok,
    "instagram": _map_instagram,
    "facebook":  _map_facebook,
    "twitter":   _map_twitter,
}


# ── Comment mapper ────────────────────────────────────────────────────────────

def _map_comment(platform: str, data: dict) -> tuple[dict, dict]:
    """Normalise a platform comment/reply dict into a unified comments row."""
    if platform == "youtube":
        cid    = data.get("comment_id")
        pid    = data.get("video_id")
        handle = data.get("author_channel_id")
        name   = data.get("author_name")
        ts     = data.get("published_at")
        extra  = {"reply_count": data.get("reply_count", 0), "updated_at": data.get("updated_at")}
    elif platform == "tiktok":
        cid    = data.get("comment_id")
        pid    = data.get("video_id")
        handle = None
        name   = data.get("author_name")
        ts     = data.get("timestamp")
        extra  = {}
    elif platform == "instagram":
        cid    = data.get("comment_id")
        pid    = data.get("post_id")
        handle = data.get("author_username")
        name   = data.get("author_name") or handle
        ts     = data.get("timestamp")
        extra  = {}
    elif platform == "facebook":
        cid    = data.get("comment_id")
        pid    = data.get("post_id")
        handle = None
        name   = data.get("author_name")
        ts     = data.get("timestamp")
        extra  = {}
    elif platform == "twitter":
        cid    = data.get("reply_id")
        pid    = data.get("tweet_id")
        handle = data.get("author_username")
        name   = data.get("author_name") or handle
        ts     = data.get("timestamp")
        extra  = {}
    else:
        return {}, {}

    unified = {
        "platform_comment_id": cid,
        "platform_post_id":    pid,
        "author_name":         name,
        "author_handle":       handle,
        "text":                data.get("text"),
        "likes":               data.get("likes", 0),
        "published_at":        ts or None,
        "is_reply":            bool(data.get("is_reply", False)),
        "parent_id":           data.get("parent_id"),
    }
    return unified, extra


# ── Public API ────────────────────────────────────────────────────────────────

def upsert_post(platform: str, data: dict, brand_slug: str = "") -> bool:
    """
    Upsert one post to Supabase. Returns True on success, False on any failure.
    Safe to call from within async scraper code — runs synchronously.
    """
    client = _get_client()
    if not client:
        return False
    try:
        mapper = _MAPPERS.get(platform)
        if not mapper:
            log.warning(f"[Supabase] Unknown platform '{platform}'")
            return False

        unified, extra = mapper(data)
        if not unified.get("platform_post_id"):
            return False  # nothing to upsert

        brand_id = _resolve_brand_id(brand_slug) if brand_slug else None

        row = {
            "platform":   platform,
            "brand_id":   brand_id,
            "extra_data": extra,
            "scraped_at": datetime.now().isoformat(),
            **unified,
        }

        client.table("posts").upsert(row, on_conflict="platform,platform_post_id").execute()
        return True
    except Exception as e:
        log.error(f"[Supabase] upsert_post failed ({platform}): {e}")
        return False


def upsert_comment(platform: str, data: dict) -> bool:
    """Upsert one comment/reply to Supabase. Returns True on success."""
    client = _get_client()
    if not client:
        return False
    try:
        unified, extra = _map_comment(platform, data)
        if not unified.get("platform_comment_id"):
            return False

        row = {
            "platform":   platform,
            "extra_data": extra,
            "scraped_at": datetime.now().isoformat(),
            **unified,
        }
        client.table("comments").upsert(row, on_conflict="platform,platform_comment_id").execute()
        return True
    except Exception as e:
        log.error(f"[Supabase] upsert_comment failed ({platform}): {e}")
        return False


def upsert_comments(platform: str, comments: list) -> int:
    """Batch upsert a list of comments. Returns count of rows submitted."""
    client = _get_client()
    if not client or not comments:
        return 0
    try:
        rows = []
        for data in comments:
            unified, extra = _map_comment(platform, data)
            if not unified.get("platform_comment_id"):
                continue
            rows.append({
                "platform":   platform,
                "extra_data": extra,
                "scraped_at": datetime.now().isoformat(),
                **unified,
            })
        if rows:
            client.table("comments").upsert(rows, on_conflict="platform,platform_comment_id").execute()
        return len(rows)
    except Exception as e:
        log.error(f"[Supabase] upsert_comments batch failed ({platform}): {e}")
        return 0
