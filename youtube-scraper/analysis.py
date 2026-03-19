"""
Analysis layer — computes engagement metrics, top keywords,
posting frequency, and sentiment from scraped YouTube data.
"""

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# Common English stop words to filter out of keyword analysis
STOP_WORDS = {
    "this", "that", "with", "have", "from", "they", "what", "when", "your",
    "will", "been", "were", "their", "there", "about", "would", "could",
    "should", "very", "just", "more", "also", "some", "than", "then",
    "into", "over", "such", "even", "most", "much", "like", "make",
    "know", "need", "want", "good", "great", "really", "thank", "thanks",
    "please", "video", "watch", "channel", "subscribe", "comment", "like",
    "share", "click", "link", "check", "youtube", "amazing", "love",
    "time", "people", "thing", "things", "because", "actually",
}


def normalize_video(v: dict) -> dict:
    """Map raw scraped video dict → clean standard format."""
    tags_raw = v.get("tags", "")
    if isinstance(tags_raw, list):
        tags = [t for t in tags_raw if t]
    elif isinstance(tags_raw, str) and tags_raw:
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    else:
        tags = []

    duration_raw = v.get("duration", 0)
    if isinstance(duration_raw, int):
        duration_seconds = duration_raw
    else:
        duration_seconds = _parse_iso_duration(str(duration_raw))

    return {
        "video_id":        v.get("video_id", ""),
        "channel_id":      v.get("channel_id", ""),
        "title":           v.get("title", ""),
        "published_at":    v.get("published_at", ""),
        "views":           int(v.get("view_count", 0) or 0),
        "likes":           int(v.get("like_count", 0) or 0),
        "comment_count":   int(v.get("comment_count", 0) or 0),
        "duration_seconds": duration_seconds,
        "tags":            tags,
        "description":     v.get("description", ""),
        "thumbnail_url":   v.get("thumbnail_url", ""),
        "post_url":        v.get("post_url", ""),
        "scraped_at":      v.get("scraped_at", datetime.now().isoformat()),
    }


def normalize_comment(c: dict) -> dict:
    """Map raw scraped comment dict → clean standard format."""
    return {
        "comment_id":  c.get("comment_id", ""),
        "video_id":    c.get("video_id", ""),
        "author":      c.get("author_name", c.get("author", "")),
        "text":        c.get("text", ""),
        "likes":       int(c.get("likes", 0) or 0),
        "published_at": c.get("published_at", ""),
        "is_reply":    bool(c.get("is_reply", False)),
        "parent_id":   c.get("parent_id", ""),
        "reply_count": int(c.get("reply_count", 0) or 0),
    }


def normalize_channel(info: dict) -> dict:
    """Map channel info → clean standard format."""
    return {
        "channel_id":        info.get("channel_id", ""),
        "channel_name":      info.get("channel_name", ""),
        "subscriber_count":  int(info.get("subscriber_count", 0) or 0),
        "total_videos":      int(info.get("total_videos_on_channel", 0) or 0),
        "scraped_at":        datetime.now().isoformat(),
    }


def _parse_iso_duration(d: str) -> int:
    """Convert PT5M30S or raw int string → seconds."""
    if not d:
        return 0
    if d.isdigit():
        return int(d)
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m:
        return 0
    h   = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    s   = int(m.group(3) or 0)
    return h * 3600 + mins * 60 + s


def _engagement_rate(views: int, likes: int, comments: int) -> float:
    if not views:
        return 0.0
    return round((likes + comments) / views * 100, 4)


def _posting_frequency(videos: list) -> dict:
    dates = []
    for v in videos:
        ts = v.get("published_at", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dates.append(dt)
            except Exception:
                pass

    if len(dates) < 2:
        return {"avg_days_between_posts": None, "posts_analyzed": len(dates)}

    dates.sort()
    gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
    avg_gap = round(sum(gaps) / len(gaps), 1)

    now = datetime.now(timezone.utc)
    posts_last_30 = sum(1 for d in dates if (now - d).days <= 30)
    posts_last_90 = sum(1 for d in dates if (now - d).days <= 90)

    return {
        "avg_days_between_posts": avg_gap,
        "posts_analyzed":         len(dates),
        "posts_last_30_days":     posts_last_30,
        "posts_last_90_days":     posts_last_90,
        "first_post":             dates[0].isoformat(),
        "latest_post":            dates[-1].isoformat(),
    }


def _top_keywords(comments: list, top_n: int = 25) -> list:
    words = []
    for c in comments:
        text = c.get("text", "") or ""
        tokens = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        words.extend(t for t in tokens if t not in STOP_WORDS)
    counts = Counter(words).most_common(top_n)
    return [{"word": w, "count": n} for w, n in counts]


def compute_analysis(channel_info: dict, videos: list, comments: list) -> dict:
    """
    Run the full analysis layer on normalized videos + comments.
    Returns analysis.json content.
    """
    total_views    = sum(v.get("views", 0) for v in videos)
    total_likes    = sum(v.get("likes", 0) for v in videos)
    total_comments = sum(v.get("comment_count", 0) for v in videos)
    avg_views      = round(total_views / len(videos)) if videos else 0

    video_stats = []
    for v in videos:
        er = _engagement_rate(v.get("views", 0), v.get("likes", 0), v.get("comment_count", 0))
        video_stats.append({
            "video_id":       v["video_id"],
            "title":          v["title"],
            "published_at":   v.get("published_at", ""),
            "views":          v.get("views", 0),
            "likes":          v.get("likes", 0),
            "comment_count":  v.get("comment_count", 0),
            "duration_seconds": v.get("duration_seconds", 0),
            "engagement_rate": er,
        })

    by_engagement = sorted(video_stats, key=lambda x: x["engagement_rate"], reverse=True)
    avg_engagement = round(
        sum(v["engagement_rate"] for v in video_stats) / len(video_stats), 4
    ) if video_stats else 0

    return {
        "channel_id":   channel_info.get("channel_id", ""),
        "channel_name": channel_info.get("channel_name", ""),
        "analyzed_at":  datetime.now().isoformat(),
        "videos_analyzed": len(videos),
        "comments_analyzed": len(comments),

        "summary": {
            "total_views":          total_views,
            "total_likes":          total_likes,
            "total_comments_count": total_comments,
            "avg_views_per_video":  avg_views,
            "avg_engagement_rate":  avg_engagement,
        },

        "videos_by_engagement": by_engagement,
        "best_performing":  by_engagement[:3] if by_engagement else [],
        "worst_performing": by_engagement[-3:][::-1] if len(by_engagement) >= 3 else [],

        "posting_frequency": _posting_frequency(videos),

        "top_comment_keywords": _top_keywords(comments),

        # Sentiment: set to null — requires Claude API key
        # To enable, run: python3 sentiment.py --channel CHANNEL_ID
        "sentiment": None,
    }
