"""
AI Analysis Pipeline for SMIP.

Pulls recent posts + comments from Supabase, calls Claude API for each platform,
and stores the resulting weekly analysis in the `analyses` table.

Usage:
    python3 analyze.py                         # last 7 days, all platforms
    python3 analyze.py --days 14               # last 14 days
    python3 analyze.py --platform tiktok       # single platform
    python3 analyze.py --brand konnectedminds  # explicit brand slug

Prerequisites:
    - Run infra/analyses_table.sql in Supabase SQL editor first (once)
    - SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY in /Users/Ted/ghana-intel/.env
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL         = "claude-sonnet-4-6"
BRAND_SLUG    = "konnected-minds"

PLATFORMS = ["youtube", "instagram", "tiktok", "facebook", "twitter"]


# ── Supabase helpers ──────────────────────────────────────────────────────────

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] SUPABASE_URL / SUPABASE_KEY not set in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_brand_id(sb, slug: str) -> str:
    r = sb.table("brands").select("id").eq("slug", slug).single().execute()
    if not r.data:
        print(f"[ERROR] Brand '{slug}' not found in Supabase.")
        sys.exit(1)
    return r.data["id"]


def fetch_posts(sb, brand_id: str, platform: str, since: date, until: date) -> list[dict]:
    q = (
        sb.table("posts")
        .select("platform_post_id,platform,content,author_name,likes,views,shares,comments_count,published_at,post_url")
        .eq("brand_id", brand_id)
        .gte("published_at", since.isoformat())
        .lte("published_at", (until + timedelta(days=1)).isoformat())
        .order("likes", desc=True)
    )
    if platform != "all":
        q = q.eq("platform", platform)
    return q.execute().data or []


def fetch_comments(sb, brand_id: str, platform: str, since: date, until: date, limit: int = 150) -> list[dict]:
    q = (
        sb.table("comments")
        .select("platform,platform_post_id,text,author_name,likes,published_at,sentiment_label")
        .eq("brand_id", brand_id)
        .gte("published_at", since.isoformat())
        .lte("published_at", (until + timedelta(days=1)).isoformat())
        .order("likes", desc=True)
        .limit(limit)
    )
    if platform != "all":
        q = q.eq("platform", platform)
    return q.execute().data or []


def upsert_analysis(sb, brand_id: str, platform: str, analysis_type: str,
                    period_start: date, period_end: date,
                    title: str, content: str, data: dict, model: str):
    record = {
        "brand_id":     brand_id,
        "platform":     platform,
        "analysis_type": analysis_type,
        "period_start": period_start.isoformat(),
        "period_end":   period_end.isoformat(),
        "title":        title,
        "content":      content,
        "data":         data,
        "model":        model,
    }
    try:
        sb.table("analyses").upsert(
            record,
            on_conflict="brand_id,platform,analysis_type,period_start"
        ).execute()
        print(f"  [Supabase] Saved: {title}")
    except Exception as e:
        print(f"  [Supabase] WARNING: could not save analysis — {e}")


# ── Stats + prompt ────────────────────────────────────────────────────────────

def compute_stats(posts: list[dict]) -> dict:
    if not posts:
        return {"post_count": 0}
    total_likes    = sum(p.get("likes") or 0 for p in posts)
    total_views    = sum(p.get("views") or 0 for p in posts)
    total_shares   = sum(p.get("shares") or 0 for p in posts)
    total_comments = sum(p.get("comments_count") or 0 for p in posts)
    top = max(posts, key=lambda p: (p.get("likes") or 0) + (p.get("views") or 0))
    return {
        "post_count":     len(posts),
        "total_likes":    total_likes,
        "total_views":    total_views,
        "total_shares":   total_shares,
        "total_comments": total_comments,
        "avg_likes":      round(total_likes / len(posts), 1),
        "avg_views":      round(total_views / len(posts), 1),
        "top_post": {
            "id":      top.get("platform_post_id"),
            "content": (top.get("content") or "")[:250],
            "likes":   top.get("likes"),
            "views":   top.get("views"),
            "url":     top.get("post_url"),
        },
    }


def build_prompt(platform: str, period_start: date, period_end: date,
                 posts: list[dict], comments: list[dict], stats: dict) -> str:
    label = platform.capitalize() if platform != "all" else "All Platforms"

    top_posts_text = ""
    for i, p in enumerate(posts[:5], 1):
        text = (p.get("content") or "—")[:300].replace("\n", " ")
        top_posts_text += (
            f"\n{i}. [{p.get('likes', '?')} likes | {p.get('views', '?')} views | "
            f"{p.get('comments_count', '?')} comments]\n   {text}\n"
        )

    comments_text = ""
    for c in comments[:30]:
        line = (c.get("text") or "").replace("\n", " ")[:150]
        sentiment = c.get("sentiment_label") or ""
        comments_text += f"- {line}  [{sentiment}]\n"

    return f"""You are a social media analyst for KonnectedMinds, a podcast brand based in Ghana.

Analyse the following {label} performance data for the period {period_start} to {period_end}.

## STATS SUMMARY
{json.dumps(stats, indent=2)}

## TOP POSTS (sorted by engagement)
{top_posts_text or "No posts found."}

## SAMPLE COMMENTS (most liked, up to 30)
{comments_text or "No comments found."}

## INSTRUCTIONS
Write a structured weekly performance report with these sections:

1. **Performance Overview** — 2-3 sentences summarising the engagement numbers for the period.
2. **Top Content** — What content worked best and why (reference specific posts/numbers).
3. **Audience Sentiment** — What are people saying? Recurring themes, questions, or praise?
4. **Platform Insights** — Notable algorithm or audience behaviour this week.
5. **Recommendations** — 3 concrete, actionable suggestions for the next week.

Tone: professional but warm — this is read by the KonnectedMinds team.
Be specific with numbers. Maximum 500 words total."""


# ── Main analysis runner ──────────────────────────────────────────────────────

def run_analysis(sb, ai: anthropic.Anthropic, brand_id: str,
                 platform: str, period_start: date, period_end: date):
    print(f"\n[{platform.upper()}] {period_start} → {period_end}")

    posts    = fetch_posts(sb, brand_id, platform, period_start, period_end)
    comments = fetch_comments(sb, brand_id, platform, period_start, period_end)
    print(f"  Posts: {len(posts)}  |  Comments: {len(comments)}")

    if not posts:
        print("  No posts — skipping.")
        return

    stats  = compute_stats(posts)
    prompt = build_prompt(platform, period_start, period_end, posts, comments, stats)

    print(f"  Calling Claude ({MODEL})...")
    response = ai.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    analysis_text = next(b.text for b in response.content if b.type == "text")

    title = f"KonnectedMinds {platform.capitalize()} — {period_start} to {period_end}"
    upsert_analysis(
        sb, brand_id, platform, "weekly_summary",
        period_start, period_end,
        title, analysis_text,
        {"stats": stats, "post_count": len(posts), "comment_count": len(comments)},
        MODEL,
    )

    # Print preview
    preview = analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text
    print(f"\n{'─' * 60}")
    print(preview)
    print(f"{'─' * 60}")


def main():
    parser = argparse.ArgumentParser(description="SMIP AI Analysis Pipeline")
    parser.add_argument("--days",     type=int, default=7,
                        help="Number of days to analyse (default: 7)")
    parser.add_argument("--platform", default="all",
                        choices=["all"] + PLATFORMS,
                        help="Platform to analyse (default: all)")
    parser.add_argument("--brand",    default=BRAND_SLUG,
                        help="Brand slug (default: konnectedminds)")
    args = parser.parse_args()

    if not ANTHROPIC_KEY:
        print("[ERROR] ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    sb       = get_supabase()
    ai       = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    brand_id = get_brand_id(sb, args.brand)
    print(f"[Brand] {args.brand} → {brand_id}")

    period_end   = date.today()
    period_start = period_end - timedelta(days=args.days)

    platforms = PLATFORMS if args.platform == "all" else [args.platform]

    for plat in platforms:
        run_analysis(sb, ai, brand_id, plat, period_start, period_end)

    print("\n[DONE] All analyses complete.")


if __name__ == "__main__":
    main()
