"""
TikTok Intelligence Scraper — Eddy's Pizza Ghana
Collects ALL TikTok content related to the brand:
  1. Their official TikTok page videos
  2. TikTok Search — videos by anyone mentioning them
  3. Hashtag pages (#eddyspizzaghana, #eddyspizza)
  4. Top comments on each video
"""

import asyncio
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from patchright.async_api import async_playwright, Page, BrowserContext

from db import init_db, save_video, save_comment, delete_video, get_stats

# ── Config ────────────────────────────────────────────────────────────────────

SEARCH_QUERY    = "KonnectedMinds"
TARGET_PAGE     = "https://www.tiktok.com/@KonnectedMinds"
BRAND_NAME      = "konnectedminds"
COOKIES_FILE    = Path(__file__).parent / "tiktok_session.json"
SCROLL_ROUNDS   = 12      # scrolls per section
SCROLL_PAUSE    = 2500    # ms between scrolls (TikTok is slower to load)
COMMENT_LIMIT   = 10      # top N comments per video

# ── Date range filter ─────────────────────────────────────────────────────────
# When running in GitHub Actions (CI=true), only scrape today's posts
_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
DATE_FROM = _today if os.getenv("CI", "").lower() == "true" else datetime(2026, 1, 1)
DATE_TO   = None

SEARCH_URL   = f"https://www.tiktok.com/search/video?q={SEARCH_QUERY.replace(' ', '%20')}"
HASHTAG_URLS = [
    "https://www.tiktok.com/tag/konnectedminds",
    "https://www.tiktok.com/tag/konnected",
    "https://www.tiktok.com/tag/konnectedmindsgh",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_id(*parts) -> str:
    raw = "_".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def parse_timestamp(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    now = datetime.now()

    # Unix timestamp
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw)).isoformat()
        except Exception:
            pass

    # Already ISO
    if re.match(r'\d{4}-\d{2}-\d{2}', raw):
        return raw

    # TikTok shows dates like "2026-3-10" or "2026-03-10"
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            pass

    # "Mar 10" or "March 10, 2026"
    for fmt in ["%b %d, %Y", "%B %d, %Y", "%b %d", "%B %d"]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.isoformat()
        except Exception:
            pass

    # Relative: "2 hours ago", "3 days ago"
    m = re.search(r'(\d+)\s*(second|minute|hour|day|week|month|year)', raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta_map = {
            "second": timedelta(seconds=n), "minute": timedelta(minutes=n),
            "hour":   timedelta(hours=n),   "day":    timedelta(days=n),
            "week":   timedelta(weeks=n),   "month":  timedelta(days=n * 30),
            "year":   timedelta(days=n * 365),
        }
        return (now - delta_map[unit]).isoformat()

    # Short: "2h", "3d"
    m = re.match(r'^(\d+)(h|d|w|m|y)$', raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta_map = {"h": timedelta(hours=n), "d": timedelta(days=n),
                     "w": timedelta(weeks=n), "m": timedelta(days=n*30),
                     "y": timedelta(days=n*365)}
        return (now - delta_map[unit]).isoformat()

    if re.match(r'^(just now|now)$', raw, re.I):
        return now.isoformat()

    return raw


def in_date_range(timestamp_str: str) -> bool:
    """Return True if timestamp falls within DATE_FROM–DATE_TO window."""
    if not timestamp_str:
        return True
    try:
        dt = datetime.fromisoformat(timestamp_str[:19])
    except Exception:
        return True
    if DATE_FROM and dt < DATE_FROM:
        return False
    if DATE_TO and dt > DATE_TO:
        return False
    return True


def parse_count(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(",", "").replace(" ", "")
    try:
        if re.search(r'[Kk]$', text):
            return int(float(text[:-1]) * 1_000)
        if re.search(r'[Mm]$', text):
            return int(float(text[:-1]) * 1_000_000)
        if re.search(r'[Bb]$', text):
            return int(float(text[:-1]) * 1_000_000_000)
        nums = re.findall(r'\d+\.?\d*', text)
        return int(float(nums[0])) if nums else 0
    except Exception:
        return 0


# ── JSON rehydration extraction (most reliable method) ────────────────────────

async def extract_from_rehydration_json(page: Page) -> dict:
    """
    TikTok embeds ALL video stats in a <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">
    tag on every video page. This is far more stable than DOM selectors.
    Returns a flat metrics dict if found, empty dict otherwise.
    """
    try:
        script_content = await page.eval_on_selector(
            'script#__UNIVERSAL_DATA_FOR_REHYDRATION__',
            'el => el.textContent'
        )
        if not script_content:
            return {}
        data = json.loads(script_content)
        scope = data.get("__DEFAULT_SCOPE__", {})

        # Video detail page
        item = (scope
                .get("webapp.video-detail", {})
                .get("itemInfo", {})
                .get("itemStruct", {}))
        if not item:
            return {}

        stats     = item.get("stats", {})
        music     = item.get("music", {})
        create_ts = item.get("createTime", 0)

        result = {
            "likes":          stats.get("diggCount", 0),
            "comments_count": stats.get("commentCount", 0),
            "shares":         stats.get("shareCount", 0),
            "bookmarks":      stats.get("collectCount", 0),
            "views":          stats.get("playCount", 0),
            "music_title":    music.get("title", ""),
        }
        if create_ts:
            result["timestamp"] = datetime.fromtimestamp(int(create_ts)).isoformat()

        print(f"    [JSON] likes={result['likes']} views={result['views']} "
              f"comments={result['comments_count']} shares={result['shares']} "
              f"bookmarks={result['bookmarks']} date={result.get('timestamp','?')[:10]} "
              f"music={result['music_title'][:30]!r}")
        return result

    except Exception as e:
        print(f"    [JSON] Extraction failed: {e}")
        return {}


# ── Session handling ──────────────────────────────────────────────────────────

async def save_session(context: BrowserContext):
    cookies = await context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    print(f"[Session] Saved to {COOKIES_FILE}")


async def load_session(context: BrowserContext) -> bool:
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        await context.add_cookies(cookies)
        print("[Session] Loaded saved session.")
        return True
    return False


# ── Page navigation helpers ───────────────────────────────────────────────────

async def goto(page: Page, url: str, label: str = ""):
    print(f"\n[Nav] Going to: {label or url[:80]}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        try:
            await page.goto(url, wait_until="commit", timeout=60000)
        except Exception:
            pass
    await page.wait_for_timeout(4000)
    await dismiss_popups(page)


async def dismiss_popups(page: Page):
    for sel in [
        'button:has-text("Allow all")',
        'button:has-text("Accept")',
        'button:has-text("Accept all")',
        '[aria-label="Close"]',
        'button:has-text("No, thanks")',
        'button:has-text("Skip")',
        '[data-e2e="modal-close-inner-button"]',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            continue


# ── Video extraction ──────────────────────────────────────────────────────────

_debug_printed = False


async def scroll_and_collect(page: Page, rounds: int = SCROLL_ROUNDS, source: str = "") -> list[dict]:
    await page.wait_for_timeout(2000)
    videos = []
    seen_ids = set()
    too_old_streak = 0

    for i in range(rounds):
        batch = await extract_all_videos(page, source=source)
        new_this_scroll = old_this_scroll = 0
        for v in batch:
            if v["video_id"] not in seen_ids:
                seen_ids.add(v["video_id"])
                videos.append(v)
                ts = v.get("timestamp", "")
                if ts and DATE_FROM:
                    try:
                        if datetime.fromisoformat(ts[:19]) < DATE_FROM:
                            old_this_scroll += 1
                        else:
                            new_this_scroll += 1
                    except Exception:
                        new_this_scroll += 1
                else:
                    new_this_scroll += 1

        if DATE_FROM and old_this_scroll > 0 and new_this_scroll == 0:
            too_old_streak += 1
        else:
            too_old_streak = 0

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2.5)")
        await page.wait_for_timeout(SCROLL_PAUSE)
        print(f"  scroll {i+1}/{rounds} — {len(videos)} videos so far")

        if too_old_streak >= 3:
            print(f"  [DateFilter] Feed is older than {DATE_FROM.date()} — stopping early")
            break

    print(f"[Collect] Total from {source}: {len(videos)} videos")
    return videos


async def extract_all_videos(page: Page, source: str = "") -> list[dict]:
    videos = []

    # TikTok video cards use different containers depending on the page type
    item_selectors = [
        '[data-e2e="search_video-item"]',         # search results (current 2025 selector)
        '[data-e2e="search_top-item"]',           # search results (older fallback)
        '[data-e2e="user-post-item"]',            # profile page
        '[data-e2e="challenge-item"]',            # hashtag page
        'div[class*="DivItemContainerV2"]',       # generic video card
        'div[class*="video-feed-item"]',
        'article',
    ]

    items = []
    for sel in item_selectors:
        items = await page.query_selector_all(sel)
        if items:
            break

    # Fallback: look for any element containing a TikTok video link
    if not items:
        items = await page.query_selector_all('a[href*="/video/"]')

    for item in items:
        try:
            v = await extract_video(item, source=source)
            if v:
                videos.append(v)
        except Exception:
            continue

    return videos


async def extract_video(item, source: str = "") -> dict | None:
    global _debug_printed

    # --- Video URL & ID ---
    video_url = ""
    video_id  = ""

    try:
        # If the item itself is a link
        href = await item.get_attribute("href") or ""
        if "/video/" in href:
            video_url = href if href.startswith("http") else "https://www.tiktok.com" + href
        else:
            # Find link inside the item
            link_el = await item.query_selector('a[href*="/video/"]')
            if link_el:
                href = await link_el.get_attribute("href") or ""
                video_url = href if href.startswith("http") else "https://www.tiktok.com" + href
    except Exception:
        pass

    # Extract video ID from URL
    m = re.search(r'/video/(\d+)', video_url)
    if m:
        video_id = m.group(1)

    # --- Author ---
    author_name     = ""
    author_username = ""
    try:
        for sel in [
            '[data-e2e="search-card-user-unique-id"]',
            '[data-e2e="video-author-uniqueid"]',
            'a[href*="/@"] span',
            'p[data-e2e*="author"]',
            'a[href*="/@"]',
        ]:
            el = await item.query_selector(sel)
            if el:
                t = (await el.inner_text()).strip()
                if t:
                    author_username = t.lstrip("@")
                    break
    except Exception:
        pass

    try:
        for sel in [
            '[data-e2e="search-card-user-nickname"]',
            '[data-e2e="video-author-avatar"] + div span',
            'p[class*="nickname"]',
        ]:
            el = await item.query_selector(sel)
            if el:
                t = (await el.inner_text()).strip()
                if t:
                    author_name = t
                    break
    except Exception:
        pass

    if not author_name:
        author_name = author_username

    # --- Description / caption ---
    description = ""
    try:
        for sel in [
            'div[data-e2e="search-card-video-caption"] span',  # search results (2025)
            '[data-e2e="search-card-desc"]',                   # search results (older)
            '[data-e2e="video-desc"]',
            'div[class*="DivContainer"] span[class*="SpanText"]',
            'span[class*="video-card-desc"]',
            'h1',
        ]:
            el = await item.query_selector(sel)
            if el:
                t = (await el.inner_text()).strip()
                if t and len(t) > 1:
                    description = t
                    break
    except Exception:
        pass

    # --- Counts ---
    full_text = ""
    try:
        full_text = await item.inner_text()
        if not _debug_printed and source:
            _debug_printed = True
            print(f"\n[DEBUG] First video card raw text ({source}):")
            print(repr(full_text[:800]))
            print("[DEBUG] ---\n")
    except Exception:
        pass

    likes          = await get_count_from_item(item, full_text, "like")
    comments_count = await get_count_from_item(item, full_text, "comment")
    shares         = await get_count_from_item(item, full_text, "share")
    views          = await get_count_from_item(item, full_text, "view")
    bookmarks      = await get_count_from_item(item, full_text, "collect")

    # --- Timestamp ---
    raw_timestamp = ""
    try:
        for sel in [
            'time',
            '[datetime]',
            'span[class*="time"]',
            'p[class*="time"]',
        ]:
            el = await item.query_selector(sel)
            if el:
                raw_timestamp = (await el.get_attribute("datetime") or
                                 await el.inner_text() or "")
                if raw_timestamp:
                    break
    except Exception:
        pass
    timestamp = parse_timestamp(raw_timestamp)

    # --- Hashtags from description ---
    hashtags = " ".join(re.findall(r'#\w+', description))

    # --- Music ---
    music_title = ""
    try:
        for sel in [
            '[data-e2e="video-music"]',
            'a[href*="/music/"]',
            'div[class*="music"] span',
        ]:
            el = await item.query_selector(sel)
            if el:
                music_title = (await el.inner_text()).strip()
                if music_title:
                    break
    except Exception:
        pass

    # Skip truly empty
    if not video_url and not description:
        return None

    if not video_id:
        video_id = make_id(source, video_url or description[:50])

    return {
        "video_id":        video_id,
        "author_name":     author_name,
        "author_username": author_username,
        "description":     description,
        "timestamp":       timestamp,
        "likes":           likes,
        "comments_count":  comments_count,
        "shares":          shares,
        "views":           views,
        "bookmarks":       bookmarks,
        "video_url":       video_url,
        "music_title":     music_title,
        "hashtags":        hashtags,
        "source":          source,
    }


async def get_count_from_item(item, full_text: str, metric: str) -> int:
    """Try aria-label / data-e2e attribute first, then fall back to text parsing."""

    # data-e2e selectors TikTok uses
    e2e_map = {
        "like":    ['[data-e2e="like-count"]',     '[data-e2e="search-card-like-count"]'],
        "comment": ['[data-e2e="comment-count"]',  '[data-e2e="search-card-comment-count"]'],
        "share":   ['[data-e2e="share-count"]'],
        "view":    ['[data-e2e="video-views"]',    'strong[data-e2e="video-views"]',
                    'div[class*="video-count"]'],
        "collect": ['[data-e2e="undefined-count"]', '[data-e2e="collect-count"]'],
    }

    for sel in e2e_map.get(metric, []):
        try:
            el = await item.query_selector(sel)
            if el:
                val = parse_count(await el.inner_text())
                if val:
                    return val
        except Exception:
            continue

    # Text-based fallback
    if full_text:
        pattern_map = {
            "like":    r'([\d,.]+[KkMmBb]?)\s*(?:Likes?|likes?)',
            "comment": r'([\d,.]+[KkMmBb]?)\s*(?:Comments?|comments?)',
            "share":   r'([\d,.]+[KkMmBb]?)\s*(?:Shares?|shares?)',
            "view":    r'([\d,.]+[KkMmBb]?)\s*(?:Views?|views?|Plays?)',
            "collect": r'([\d,.]+[KkMmBb]?)\s*(?:Saves?|saves?|Bookmarks?)',
        }
        if metric in pattern_map:
            m = re.search(pattern_map[metric], full_text, re.I)
            if m:
                return parse_count(m.group(1))

    return 0


# ── Metrics enrichment from video page ────────────────────────────────────────

async def enrich_metrics_from_page(page: Page, video_id: str) -> dict:
    """
    Read the real engagement numbers + music + date from an already-loaded video page.
    Strategy 1: Parse TikTok's embedded JSON (most reliable, covers all fields).
    Strategy 2: DOM data-e2e selectors as fallback.
    Strategy 3: Full body text regex as last resort.
    """
    # Give TikTok's React app a moment to hydrate
    await page.wait_for_timeout(2500)

    # ── Strategy 1: JSON rehydration (preferred) ──
    metrics = await extract_from_rehydration_json(page)
    if metrics and metrics.get("likes", 0) + metrics.get("views", 0) > 0:
        return metrics  # Got good data — skip DOM scraping

    # ── Strategy 2: DOM data-e2e selectors ──
    print(f"    [Metrics] JSON empty — falling back to DOM selectors")
    metrics = {"likes": 0, "comments_count": 0, "shares": 0,
               "views": 0, "bookmarks": 0, "music_title": ""}

    count_map = {
        # TikTok uses 'browse-*' when in vertical swipe mode, plain keys on direct video pages
        "likes":          ['strong[data-e2e="browse-like-count"]',    'strong[data-e2e="like-count"]',    '[data-e2e="like-count"]'],
        "comments_count": ['strong[data-e2e="browse-comment-count"]', 'strong[data-e2e="comment-count"]', '[data-e2e="comment-count"]'],
        "shares":         ['strong[data-e2e="browse-share-count"]',   'strong[data-e2e="share-count"]',   '[data-e2e="share-count"]'],
        "views":          ['strong[data-e2e="browse-video-count"]',   '[data-e2e="video-views"]',         'strong[data-e2e="video-views"]', '[data-e2e="play-count"]'],
        # Bookmark: TikTok literally uses "undefined-count" as the data-e2e value for saves
        "bookmarks":      ['strong[data-e2e="undefined-count"]',      'strong[data-e2e="browse-collect-count"]', '[data-e2e="collect-count"]'],
    }
    for field, selectors in count_map.items():
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    val = parse_count(await el.inner_text())
                    if val:
                        metrics[field] = val
                        break
            except Exception:
                continue

    # ── Strategy 3: full-body text regex ──
    page_text = ""
    try:
        page_text = await page.inner_text("body")
    except Exception:
        pass

    if page_text:
        text_patterns = {
            "likes":          r'([\d,.]+[KkMmBb]?)\s*Likes?',
            "comments_count": r'([\d,.]+[KkMmBb]?)\s*Comments?',
            "shares":         r'([\d,.]+[KkMmBb]?)\s*Shares?',
            "views":          r'([\d,.]+[KkMmBb]?)\s*(?:Views?|Plays?)',
            "bookmarks":      r'([\d,.]+[KkMmBb]?)\s*(?:Saves?|Bookmarks?)',
        }
        for field, pattern in text_patterns.items():
            if metrics[field] == 0:
                m = re.search(pattern, page_text, re.I)
                if m:
                    metrics[field] = parse_count(m.group(1))

    # Music — try DOM then page-text regex
    for sel in [
        '[data-e2e="video-music"]', '[data-e2e="browse-music"]',
        'h4[data-e2e="browse-music"]',
        'a[href*="/music/"] h4', 'a[href*="/music/"] p', 'a[href*="/music/"]',
        'div[class*="DivMusicInfo"] span', 'div[class*="music"] h4',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                t = (await el.inner_text()).strip()
                if t and t.lower() not in ("music", "sound", "original sound", ""):
                    metrics["music_title"] = t
                    break
        except Exception:
            continue
    if not metrics["music_title"] and page_text:
        m = re.search(r'original sound\s*[-–]\s*(.+?)[\n\r]', page_text, re.I)
        if m:
            metrics["music_title"] = m.group(1).strip()

    # Timestamp — try DOM then page-text date pattern
    raw_ts = ""
    for sel in ['time[datetime]', 'time',
                'span[data-e2e="browser-nickname"] span:last-child',
                'span[class*="SpanOtherInfos"] span',
                'span[class*="date"]']:
        try:
            el = await page.query_selector(sel)
            if el:
                raw_ts = (await el.get_attribute("datetime") or
                          await el.inner_text() or "").strip()
                if raw_ts and re.search(r'\d{4}', raw_ts):
                    break
        except Exception:
            continue
    if not raw_ts and page_text:
        m = re.search(r'\b(202[0-9]-\d{1,2}-\d{1,2})\b', page_text)
        if m:
            raw_ts = m.group(1)
    if raw_ts:
        metrics["timestamp"] = parse_timestamp(raw_ts)

    print(f"    [DOM] likes={metrics['likes']} views={metrics['views']} "
          f"comments={metrics['comments_count']} shares={metrics['shares']} "
          f"bookmarks={metrics['bookmarks']} date={metrics.get('timestamp','?')[:10]} "
          f"music={metrics['music_title'][:30]!r}")
    return metrics


# ── Comment scraping ──────────────────────────────────────────────────────────

async def scrape_comments(page: Page, video: dict) -> tuple[list[dict], dict]:
    """Returns (comments, enriched_metrics). Visits the video page once for both."""
    if not video.get("video_url"):
        return [], {}

    comments = []
    enriched = {}
    try:
        await goto(page, video["video_url"], label="video page")
        await page.wait_for_timeout(2000)

        # Grab real metrics while we're on the page
        enriched = await enrich_metrics_from_page(page, video["video_id"])

        # TikTok defaults to "You may like" tab — explicitly click "Comments" tab
        clicked_comments_tab = False
        for sel in [
            '[data-e2e="comment-tab"]',
            'button:has-text("Comments")',
            'span:has-text("Comments")',
            'div[role="tab"]:has-text("Comments")',
        ]:
            try:
                tab = await page.query_selector(sel)
                if tab and await tab.is_visible():
                    await tab.click()
                    await page.wait_for_timeout(1500)
                    clicked_comments_tab = True
                    print(f"    [Comments] Clicked Comments tab via: {sel}")
                    break
            except Exception:
                continue

        if not clicked_comments_tab:
            try:
                tabs = await page.query_selector_all('[role="tab"], button, div[tabindex="0"]')
                for tab in tabs:
                    t = (await tab.inner_text()).strip()
                    if t.lower() == "comments":
                        await tab.click()
                        await page.wait_for_timeout(1500)
                        break
            except Exception:
                pass

        # Wait for the comment list to appear
        try:
            await page.wait_for_selector(
                '[data-e2e="comment-list"], [data-e2e="comment-level-1"]',
                timeout=8000
            )
        except Exception:
            await page.wait_for_timeout(2000)

        # Scroll inside comment panel to load more
        for _ in range(3):
            try:
                comment_section = await page.query_selector('[data-e2e="comment-list"]')
                if comment_section:
                    await comment_section.evaluate("el => el.scrollBy(0, 600)")
                else:
                    await page.evaluate("window.scrollBy(0, 400)")
                await page.wait_for_timeout(1200)
            except Exception:
                break

        # Find comment elements
        comment_els = []
        for sel in [
            '[data-e2e="comment-level-1"]',
            '[class*="DivCommentItemWrapper"]',
            '[class*="comment-item"]',
            'div[class*="CommentItem"]',
        ]:
            els = await page.query_selector_all(sel)
            if els:
                comment_els = els[:COMMENT_LIMIT]
                break

        for el in comment_els:
            try:
                c = await extract_comment(el, video["video_id"])
                if c:
                    comments.append(c)
            except Exception:
                continue

        print(f"  [Comments] {len(comments)} extracted from {video.get('description','')[:40]!r}")
    except Exception as e:
        print(f"  [Comments] Error: {e}")

    return comments, enriched


async def extract_comment(el, video_id: str) -> dict | None:
    try:
        full_text = (await el.inner_text()).strip()
        if not full_text or len(full_text) < 2:
            return None

        # Author
        author = ""
        for sel in [
            '[data-e2e="comment-username-1"]',
            'a[href*="/@"] span',
            'span[class*="user-name"]',
            'p[class*="author"]',
        ]:
            author_el = await el.query_selector(sel)
            if author_el:
                candidate = (await author_el.inner_text()).strip().lstrip("@")
                if candidate and len(candidate) > 1:
                    author = candidate
                    break

        # Comment text
        text = ""
        for sel in [
            '[data-e2e="comment-level-1-text"]',
            'p[class*="CommentText"]',
            'span[class*="comment-text"]',
            '[dir="auto"]',
        ]:
            text_el = await el.query_selector(sel)
            if text_el:
                t = (await text_el.inner_text()).strip()
                if t and t != author and len(t) > 1:
                    text = t
                    break

        if not text:
            text = full_text
        if not text or len(text) < 2:
            return None

        # Timestamp
        raw_ts = ""
        for sel in ['time', '[datetime]', 'span[class*="time"]']:
            ts_el = await el.query_selector(sel)
            if ts_el:
                raw_ts = (await ts_el.get_attribute("datetime") or
                          await ts_el.inner_text() or "")
                if raw_ts:
                    break
        timestamp = parse_timestamp(raw_ts)

        # Likes
        likes = 0
        for sel in [
            '[data-e2e="comment-like-count"]',
            'span[class*="like-count"]',
        ]:
            like_el = await el.query_selector(sel)
            if like_el:
                likes = parse_count(await like_el.inner_text())
                if likes:
                    break

        return {
            "comment_id":  make_id(video_id, author, text[:40]),
            "video_id":    video_id,
            "author_name": author,
            "text":        text,
            "likes":       likes,
            "timestamp":   timestamp,
            "is_reply":    0,
            "parent_id":   None,
        }
    except Exception:
        return None


# ── Relevance filter ──────────────────────────────────────────────────────────

def is_relevant(description: str, author_username: str, source: str) -> bool:
    """Keep only content genuinely about Eddy's Pizza Ghana."""
    if source in ("official_page", "hashtag_konnectedminds"):
        return True

    desc_l   = description.lower()
    author_l = author_username.lower()

    # Official account's own videos
    if "konnected" in author_l:
        return True

    # Must mention "konnected" specifically
    if not re.search(r"konnected", desc_l):
        return False

    return True


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run(scrape_comments_flag: bool = True):
    global _debug_printed
    _debug_printed = False
    init_db()
    all_videos = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=os.getenv("CI", "").lower() == "true",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # Load saved session if available
        await load_session(context)

        def collect_and_save(videos: list, source: str):
            kept = dropped = out_of_range = 0
            for v in videos:
                if not in_date_range(v.get("timestamp", "")):
                    out_of_range += 1
                    continue
                if is_relevant(v.get("description", ""), v.get("author_username", ""), source):
                    save_video(v)
                    all_videos.append(v)
                    kept += 1
                else:
                    dropped += 1
            if out_of_range:
                print(f"  [DateFilter] Dropped {out_of_range} videos outside date range")
            if dropped:
                print(f"  [Filter] Kept {kept}, dropped {dropped} off-topic videos")

        # ── 1. Official TikTok page ────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 1: Official TikTok page")
        print("="*55)

        # Intercept TikTok's /api/post/item_list/ XHR — it returns per-video stats
        # without needing to visit each video page individually.
        xhr_stats: dict[str, dict] = {}  # video_id -> stats dict

        async def capture_item_list(response):
            if "/api/post/item_list/" not in response.url:
                return
            try:
                data = await response.json()
                for item in data.get("itemList", []):
                    vid = str(item.get("id", ""))
                    if not vid:
                        continue
                    stats = item.get("stats", {})
                    music = item.get("music", {})
                    ct    = item.get("createTime", 0)
                    xhr_stats[vid] = {
                        "likes":          stats.get("diggCount", 0),
                        "comments_count": stats.get("commentCount", 0),
                        "shares":         stats.get("shareCount", 0),
                        "bookmarks":      stats.get("collectCount", 0),
                        "views":          stats.get("playCount", 0),
                        "music_title":    music.get("title", ""),
                        "timestamp":      datetime.fromtimestamp(int(ct)).isoformat() if ct else "",
                    }
            except Exception:
                pass

        page.on("response", capture_item_list)

        await goto(page, TARGET_PAGE, "official page")
        try:
            await page.wait_for_selector(
                '[data-e2e="user-post-item"], article', timeout=15000
            )
        except Exception:
            print("  [!] No videos found on official page")
        videos = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="official_page")

        # Merge XHR-captured stats into the discovered videos before saving
        for v in videos:
            if v["video_id"] in xhr_stats:
                v.update(xhr_stats[v["video_id"]])

        page.remove_listener("response", capture_item_list)
        if xhr_stats:
            print(f"  [XHR] Captured stats for {len(xhr_stats)} videos from API")

        collect_and_save(videos, "official_page")

        # ── 2. TikTok Search ──────────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 2: TikTok Search")
        print("="*55)
        await goto(page, SEARCH_URL, "search")
        try:
            await page.wait_for_selector(
                '[data-e2e="search_video-item"], [data-e2e="search_top-item"], article',
                timeout=10000
            )
        except Exception:
            pass
        videos = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="search")
        collect_and_save(videos, "search")

        # ── 3. Hashtag pages ──────────────────────────────────────────────
        for tag_url in HASHTAG_URLS:
            tag = tag_url.split("/tag/")[-1]
            print("\n" + "="*55)
            print(f"SECTION 3: Hashtag #{tag}")
            print("="*55)
            await goto(page, tag_url, f"#{tag}")
            try:
                await page.wait_for_selector(
                    '[data-e2e="challenge-item"], article', timeout=10000
                )
            except Exception:
                pass
            source = f"hashtag_{tag}"
            videos = await scroll_and_collect(page, rounds=8, source=source)
            collect_and_save(videos, source)

        # ── 4. Save session for future runs ───────────────────────────────
        await save_session(context)

        # ── 5. Enrich metrics + Comments ──────────────────────────────────
        posts_with_url = [v for v in all_videos if v.get("video_url")]
        print("\n" + "="*55)
        if scrape_comments_flag:
            print(f"SECTION 4: Enriching metrics + scraping top {COMMENT_LIMIT} comments for {len(posts_with_url)} videos")
        else:
            print(f"SECTION 4: Enriching metrics for {len(posts_with_url)} videos")
        print("="*55)
        for i, video in enumerate(posts_with_url):
            print(f"[{i+1}/{len(posts_with_url)}] {video.get('description', '')[:50]}...")
            if scrape_comments_flag:
                comments, enriched = await scrape_comments(page, video)
            else:
                await goto(page, video["video_url"], label="video page")
                await page.wait_for_timeout(2000)
                enriched = await enrich_metrics_from_page(page, video["video_id"])
                comments = []

            # Update the video record with real metrics + real timestamp from the page
            if enriched:
                updated = {**video, **enriched}
                real_ts = enriched.get("timestamp") or video.get("timestamp", "")
                if real_ts and not in_date_range(real_ts):
                    # Now that we know the real date, remove it if it's out of range
                    delete_video(video["video_id"])
                    print(f"    [DateFilter] Removed — real date {real_ts[:10]} is outside range")
                    continue
                save_video(updated)

            for c in comments:
                save_comment(c)
            await page.wait_for_timeout(1500)

        await browser.close()

    stats = get_stats()
    print("\n" + "="*55)
    print("SCRAPE COMPLETE")
    print(f"  Videos collected:   {stats['total_videos']}")
    print(f"  Comments collected: {stats['total_comments']}")
    print(f"  Total likes:        {stats['total_likes']}")
    print(f"  Total views:        {stats['total_views']}")
    print(f"  Total shares:       {stats['total_shares']}")
    print("="*55)
