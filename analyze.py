"""
analyze.py — SMIP AI Analysis Engine
Reads recent posts from Supabase, calls Claude API, saves structured insights.

Usage:
  python3 analyze.py                        # analyse all brands, last 7 days
  python3 analyze.py --brand konnected-minds
  python3 analyze.py --days 14
  python3 analyze.py --brand konnected-minds --days 3

Requirements:
  pip3 install anthropic supabase python-dotenv
"""

import os
import json
import argparse
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import anthropic
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("analyze")

# ── Config ────────────────────────────────────────────────────────────────────

CLAUDE_MODEL   = "claude-sonnet-4-6"
DEFAULT_DAYS   = 7
MAX_POSTS      = 100    # max posts to send to Claude per analysis
MAX_COMMENTS   = 50     # max comments to include

# ── Clients ───────────────────────────────────────────────────────────────────

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set in .env")
    return create_client(url, key)


def get_claude():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
    return anthropic.Anthropic(api_key=api_key)


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_brand(sb, brand_slug: str) -> dict:
    res = sb.table("brands").select("*").eq("slug", brand_slug).single().execute()
    return res.data


def fetch_posts(sb, brand_id: str, since: datetime, until: datetime) -> list:
    res = (
        sb.table("posts")
        .select("platform, platform_post_id, author_handle, content, post_url, "
                "media_type, published_at, likes, comments_count, shares, views, extra_data")
        .eq("brand_id", brand_id)
        .gte("scraped_at", since.isoformat())
        .lte("scraped_at", until.isoformat())
        .order("likes", desc=True)
        .limit(MAX_POSTS)
        .execute()
    )
    return res.data or []


def fetch_comments(sb, brand_id: str, platform_post_ids: list, since: datetime) -> list:
    if not platform_post_ids:
        return []
    res = (
        sb.table("comments")
        .select("platform, platform_post_id, author_name, text, likes, published_at")
        .in_("platform_post_id", platform_post_ids[:20])  # cap to top 20 posts
        .gte("scraped_at", since.isoformat())
        .order("likes", desc=True)
        .limit(MAX_COMMENTS)
        .execute()
    )
    return res.data or []


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(brand: dict, posts: list, comments: list,
                 since: datetime, until: datetime) -> str:

    # Platform breakdown
    platform_counts: dict = {}
    for p in posts:
        plat = p.get("platform", "unknown")
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    total_likes   = sum(p.get("likes", 0) or 0 for p in posts)
    total_views   = sum(p.get("views", 0) or 0 for p in posts)
    total_shares  = sum(p.get("shares", 0) or 0 for p in posts)
    total_comments_count = sum(p.get("comments_count", 0) or 0 for p in posts)

    # Format posts for prompt
    posts_text = ""
    for i, p in enumerate(posts[:50], 1):  # cap at 50 for prompt length
        posts_text += (
            f"\n[Post {i}] Platform: {p.get('platform')} | "
            f"Likes: {p.get('likes',0)} | Views: {p.get('views',0)} | "
            f"Shares: {p.get('shares',0)}\n"
            f"Content: {str(p.get('content',''))[:300]}\n"
        )

    # Format comments
    comments_text = ""
    for c in comments[:30]:
        comments_text += f"- [{c.get('platform')}] {str(c.get('text',''))[:200]}\n"

    prompt = f"""You are a senior social media intelligence analyst. Analyse the following data for the brand "{brand['name']}" and return a structured JSON report.

ANALYSIS PERIOD: {since.strftime('%Y-%m-%d')} to {until.strftime('%Y-%m-%d')}

SUMMARY STATS:
- Total posts scraped: {len(posts)}
- Platforms: {json.dumps(platform_counts)}
- Total likes: {total_likes:,}
- Total views: {total_views:,}
- Total shares: {total_shares:,}
- Total comments: {total_comments_count:,}

TOP POSTS (by likes):
{posts_text if posts_text else "No posts found in this period."}

AUDIENCE COMMENTS/REPLIES (sample):
{comments_text if comments_text else "No comments found in this period."}

Return ONLY a valid JSON object with exactly this structure (no markdown, no explanation):
{{
  "sentiment_score": <float from -1.0 to 1.0>,
  "sentiment_label": "<positive|neutral|negative>",
  "top_topics": [
    {{"topic": "<topic name>", "count": <int>, "sentiment": "<positive|neutral|negative>"}}
  ],
  "crisis_flag": <true|false>,
  "crisis_reason": "<brief reason if crisis_flag is true, else null>",
  "recommended_actions": [
    "<action 1>",
    "<action 2>",
    "<action 3>"
  ],
  "summary": "<2-3 sentence executive summary of the brand's social media performance this period>",
  "platform_breakdown": {{
    "<platform>": {{
      "posts": <int>,
      "total_likes": <int>,
      "total_views": <int>,
      "sentiment": "<positive|neutral|negative>"
    }}
  }},
  "top_posts": [
    {{
      "platform": "<platform>",
      "content_preview": "<first 100 chars of content>",
      "likes": <int>,
      "views": <int>
    }}
  ]
}}

Guidelines:
- sentiment_score: -1.0 = very negative, 0 = neutral, 1.0 = very positive
- top_topics: list up to 8 most discussed themes (e.g. "customer service", "new menu item", "delivery speed")
- crisis_flag: true only if there is a clear PR issue, viral complaint, or reputational threat
- recommended_actions: 3-5 specific, actionable steps for the brand's social media team
- top_posts: include up to 5 highest-engagement posts
- If there is little or no data, still return the JSON with best-effort estimates and note the data gap in summary
"""
    return prompt


# ── Claude call ───────────────────────────────────────────────────────────────

def call_claude(client: anthropic.Anthropic, prompt: str) -> dict:
    log.info(f"Calling Claude ({CLAUDE_MODEL})...")
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    log.info("Claude responded.")

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── Save to Supabase ──────────────────────────────────────────────────────────

def save_analysis(sb, brand: dict, result: dict, posts: list,
                  since: datetime, until: datetime):
    platform_list = list({p.get("platform") for p in posts if p.get("platform")})
    total_likes   = sum(p.get("likes", 0) or 0 for p in posts)
    total_views   = sum(p.get("views", 0) or 0 for p in posts)
    total_shares  = sum(p.get("shares", 0) or 0 for p in posts)
    total_comments_count = sum(p.get("comments_count", 0) or 0 for p in posts)

    row = {
        "brand_id":           brand["id"],
        "analysis_date":      datetime.now().strftime("%Y-%m-%d"),
        "period_start":       since.isoformat(),
        "period_end":         until.isoformat(),
        "platforms":          platform_list,
        "total_posts":        len(posts),
        "total_comments":     total_comments_count,
        "total_likes":        total_likes,
        "total_views":        total_views,
        "total_shares":       total_shares,
        "sentiment_score":    result.get("sentiment_score"),
        "sentiment_label":    result.get("sentiment_label"),
        "top_topics":         result.get("top_topics", []),
        "crisis_flag":        result.get("crisis_flag", False),
        "crisis_reason":      result.get("crisis_reason"),
        "recommended_actions":result.get("recommended_actions", []),
        "summary":            result.get("summary"),
        "platform_breakdown": result.get("platform_breakdown", {}),
        "top_posts":          result.get("top_posts", []),
    }

    sb.table("analyses").upsert(row, on_conflict="brand_id,analysis_date").execute()
    log.info(f"Analysis saved to Supabase for brand '{brand['slug']}'")


# ── Print summary ─────────────────────────────────────────────────────────────

def print_summary(brand: dict, result: dict, posts: list):
    print("\n" + "="*60)
    print(f"ANALYSIS COMPLETE — {brand['name']}")
    print("="*60)
    print(f"  Posts analysed:   {len(posts)}")
    print(f"  Sentiment:        {result.get('sentiment_label','?').upper()} ({result.get('sentiment_score', 0):+.2f})")
    print(f"  Crisis flag:      {'🚨 YES — ' + result.get('crisis_reason','') if result.get('crisis_flag') else '✅ No'}")
    print(f"\n  Summary:")
    print(f"  {result.get('summary','')}")
    print(f"\n  Top topics:")
    for t in result.get("top_topics", [])[:5]:
        print(f"    • {t.get('topic')} ({t.get('sentiment')})")
    print(f"\n  Recommended actions:")
    for i, a in enumerate(result.get("recommended_actions", []), 1):
        print(f"    {i}. {a}")
    print("="*60)


# ── Main ──────────────────────────────────────────────────────────────────────

def analyse_brand(brand_slug: str, days: int):
    sb     = get_supabase()
    claude = get_claude()

    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)

    log.info(f"Fetching data for '{brand_slug}' ({since.date()} → {until.date()})...")

    brand    = fetch_brand(sb, brand_slug)
    posts    = fetch_posts(sb, brand["id"], since, until)
    post_ids = [p["platform_post_id"] for p in posts if p.get("platform_post_id")]
    comments = fetch_comments(sb, brand["id"], post_ids, since)

    log.info(f"Found {len(posts)} posts, {len(comments)} comments")

    prompt = build_prompt(brand, posts, comments, since, until)
    result = call_claude(claude, prompt)

    save_analysis(sb, brand, result, posts, since, until)
    print_summary(brand, result, posts)


def main():
    parser = argparse.ArgumentParser(description="SMIP AI Analysis Engine")
    parser.add_argument("--brand", type=str, default="konnected-minds",
                        help="Brand slug to analyse (default: konnected-minds)")
    parser.add_argument("--days",  type=int, default=DEFAULT_DAYS,
                        help="How many days back to analyse (default: 7)")
    args = parser.parse_args()

    analyse_brand(args.brand, args.days)


if __name__ == "__main__":
    main()
