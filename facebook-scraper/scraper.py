"""
Facebook Intelligence Scraper — Eddy's Pizza Ghana
Collects ALL content related to a subject across Facebook:
  1. Their official page (posts, reactions, comments)
  2. Facebook Search — posts by anyone mentioning them
  3. Their page Reviews section
  4. Tagged posts / check-ins
"""

import asyncio
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from patchright.async_api import async_playwright, Page, BrowserContext

from db import init_db, save_post, save_comment, get_stats

# ── Config ────────────────────────────────────────────────────────────────────

SEARCH_QUERY   = "KonnectedMinds"
TARGET_PAGE    = "https://www.facebook.com/KonnectedMinds"
PAGE_NAME      = "KonnectedMinds"
COOKIES_FILE   = Path(__file__).parent / "fb_session.json"
SCROLL_ROUNDS  = 15       # scrolls per section
SCROLL_PAUSE   = 2000     # ms between scrolls
COMMENT_LIMIT  = 10       # top N comments per post (FB sorts by top by default)

# ── Date range filter ─────────────────────────────────────────────────────────
# Set DATE_FROM / DATE_TO to restrict which posts are kept.
# Use None to disable the limit on either end.
_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
DATE_FROM = _today if os.getenv("CI", "").lower() == "true" else datetime(2026, 1, 1)
DATE_TO   = None

# Search URLs — all tabs
SEARCH_URLS = {
    "top":    f"https://www.facebook.com/search/top/?q={SEARCH_QUERY.replace(' ', '+')}",
    "posts":  f"https://www.facebook.com/search/posts/?q={SEARCH_QUERY.replace(' ', '+')}",
    "videos": f"https://www.facebook.com/search/videos/?q={SEARCH_QUERY.replace(' ', '+')}",
}

REVIEWS_URL = f"{TARGET_PAGE}/reviews"

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_id(*parts) -> str:
    raw = "_".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def parse_timestamp(raw: str) -> str:
    """
    Convert Facebook's various timestamp formats to ISO datetime string.
    Examples handled:
      - Unix epoch from data-utime: "1741823400"
      - Absolute: "March 10, 2026 at 3:45 PM", "Friday, March 10 at 3:45 PM"
      - Relative: "2 hours ago", "3 days ago", "Just now", "Yesterday at 2pm"
      - Short: "2h", "3d", "5w", "March 10"
    """
    if not raw:
        return ""
    raw = raw.strip()
    now = datetime.now()

    # Unix timestamp (from data-utime attribute)
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw)).isoformat()
        except Exception:
            pass

    # Already looks like ISO format
    if re.match(r'\d{4}-\d{2}-\d{2}', raw):
        return raw

    # Full date with time: "March 10, 2026 at 3:45 PM"
    for fmt in [
        "%B %d, %Y at %I:%M %p",
        "%B %d, %Y",
        "%A, %B %d, %Y at %I:%M %p",
        "%A, %B %d at %I:%M %p",
        "%b %d, %Y at %I:%M %p",
        "%b %d, %Y",
    ]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.isoformat()
        except Exception:
            pass

    # Relative: "2 hours ago", "3 days ago", "5 minutes ago"
    m = re.search(r'(\d+)\s*(second|minute|hour|day|week|month|year)', raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta_map = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour":   timedelta(hours=n),
            "day":    timedelta(days=n),
            "week":   timedelta(weeks=n),
            "month":  timedelta(days=n * 30),
            "year":   timedelta(days=n * 365),
        }
        return (now - delta_map[unit]).isoformat()

    # Short relative: "2h", "3d", "5w", "1y"
    m = re.match(r'^(\d+)(h|d|w|m|y)$', raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta_map = {"h": timedelta(hours=n), "d": timedelta(days=n),
                     "w": timedelta(weeks=n), "m": timedelta(days=n*30),
                     "y": timedelta(days=n*365)}
        return (now - delta_map[unit]).isoformat()

    # "Just now" / "Now"
    if re.match(r'^(just now|now)$', raw, re.I):
        return now.isoformat()

    # "Yesterday at 2:30 PM"
    if re.match(r'^yesterday', raw, re.I):
        time_m = re.search(r'(\d+:\d+\s*[AP]M)', raw, re.I)
        base = now - timedelta(days=1)
        if time_m:
            try:
                t = datetime.strptime(time_m.group(1).strip().upper(), "%I:%M %p")
                return base.replace(hour=t.hour, minute=t.minute).isoformat()
            except Exception:
                pass
        return base.date().isoformat()

    # Return raw string if we can't parse it — better than nothing
    return raw


# ── Relevance filter ──────────────────────────────────────────────────────────

# Phrases that indicate "Eddy's Pizza" is only being used as a location landmark
_LOCATION_ONLY_PHRASES = [
    r"opposite eddy",
    r"opp\.?\s*eddy",
    r"near eddy.{0,10}pizza",
    r"next to eddy",
    r"beside eddy",
    r"behind eddy",
    r"close to eddy",
    r"in front of eddy",
    r"around eddy",
    r"after eddy.{0,10}pizza",
    r"before eddy.{0,10}pizza",
    r"landmark.{0,30}eddy",
    r"eddy.{0,10}pizza.{0,30}direction",
]

def is_relevant(text: str, author: str, source: str) -> bool:
    """
    Return True if this post is genuinely about Eddy's Pizza Ghana.
    Filters out posts that only mention Eddy's Pizza as a location reference
    (e.g. "our showroom is opposite Eddy's Pizza").
    Official page and review posts are always kept.
    """
    if source in ("official_page", "reviews"):
        return True

    text_l  = text.lower()
    author_l = author.lower()

    # If the author IS Eddy's Pizza — always keep
    if "eddy" in author_l and "pizza" in author_l:
        return True

    # For search results: the post text must actually mention "eddy" or "pizza"
    # If neither word appears in the text, it only showed up due to location metadata — drop it
    if not re.search(r"eddy|pizza", text_l):
        return False

    # Reject if it's a pure location-landmark mention
    for pattern in _LOCATION_ONLY_PHRASES:
        if re.search(pattern, text_l):
            # Keep only if the post also has food/experience signals AND multiple Eddy mentions
            food_signals = re.findall(
                r"\b(food|pizza|meal|order|delivery|taste|service|customer|menu|branch|restaurant|dine|eat|delicious|yummy|price)\b",
                text_l
            )
            eddy_count = len(re.findall(r"eddy.{0,5}pizza", text_l))
            if not (len(food_signals) >= 2 and eddy_count >= 2):
                return False

    return True


def in_date_range(timestamp_str: str) -> bool:
    """Return True if timestamp falls within DATE_FROM–DATE_TO window."""
    if not timestamp_str:
        return True  # no timestamp = can't filter, keep it
    try:
        # Handle both full ISO and date-only strings
        dt = datetime.fromisoformat(timestamp_str[:19])
    except Exception:
        return True  # unparseable = keep

    if DATE_FROM and dt < DATE_FROM:
        return False
    if DATE_TO and dt > DATE_TO:
        return False
    return True


def parse_count(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(",", "")
    try:
        if "K" in text.upper():
            return int(float(text.upper().replace("K", "")) * 1_000)
        if "M" in text.upper():
            return int(float(text.upper().replace("M", "")) * 1_000_000)
        nums = re.findall(r"\d+", text)
        return int(nums[0]) if nums else 0
    except Exception:
        return 0


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(page: Page, email: str, password: str):
    print("[Login] Navigating to Facebook...")
    await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    email_selectors = [
        '#email', 'input[name="email"]', 'input[type="email"]',
        'input[placeholder*="email" i]', 'input[placeholder*="phone" i]',
    ]
    email_field = None
    for sel in email_selectors:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            email_field = sel
            break
        except Exception:
            continue

    if not email_field:
        try:
            await page.screenshot(path=str(Path(__file__).parent / "login_debug.png"), timeout=5000)
        except Exception:
            pass
        print("[Login] Could not find email field — saved login_debug.png")
        return False

    print(f"[Login] Found email field: {email_field}")
    await page.click(email_field)
    await page.wait_for_timeout(500)
    await page.type(email_field, email, delay=80)
    await page.wait_for_timeout(1000)

    pass_selectors = ['#pass', 'input[name="pass"]', 'input[type="password"]']
    pass_field = None
    for sel in pass_selectors:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            pass_field = sel
            break
        except Exception:
            continue

    if not pass_field:
        print("[Login] Could not find password field.")
        return False

    await page.click(pass_field)
    await page.wait_for_timeout(500)
    await page.type(pass_field, password, delay=80)
    await page.wait_for_timeout(1200)

    clicked = False
    for sel in ['[name="login"]', 'button[type="submit"]', 'button:has-text("Log in")', 'button:has-text("Log In")']:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                clicked = True
                print(f"[Login] Clicked via: {sel}")
                break
        except Exception:
            continue

    if not clicked:
        print("[Login] Pressing Enter to submit...")
        await page.press(pass_field, "Enter")

    print("[Login] Waiting for redirect...")
    await page.wait_for_timeout(8000)

    if "login" in page.url:
        print("[Login] Waiting up to 60s for you to complete any verification...")
        try:
            await page.wait_for_function(
                "() => !window.location.href.includes('/login')", timeout=60000
            )
        except Exception:
            pass

    if "checkpoint" in page.url or "two_step" in page.url:
        print("[Login] 2FA detected — complete it in the browser (90s)...")
        try:
            await page.wait_for_function(
                "() => !window.location.href.includes('checkpoint') && !window.location.href.includes('login')",
                timeout=90000
            )
        except Exception:
            pass

    if "facebook.com" in page.url and "login" not in page.url and "checkpoint" not in page.url:
        print("[Login] Login successful!")
        return True
    else:
        print(f"[Login] Login failed. URL: {page.url}")
        try:
            await page.screenshot(path=str(Path(__file__).parent / "login_debug.png"), timeout=5000)
        except Exception:
            pass
        return False


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
        await page.goto(url, wait_until="commit", timeout=60000)
    await page.wait_for_timeout(4000)
    await dismiss_dialogs(page)


async def dismiss_dialogs(page: Page):
    for label in ['Allow all cookies', 'Accept all', 'Accept All', 'Decline optional cookies',
                  'Close', 'Not now', 'No thanks', 'Only allow essential cookies']:
        try:
            btn = await page.query_selector(f'button:has-text("{label}"), [aria-label="{label}"]')
            if btn:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            continue
    # Close login pop-up overlay if visible
    for sel in ['[aria-label="Close"]', '[data-testid="close-button"]']:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            continue


async def scroll_and_collect(page: Page, rounds: int = SCROLL_ROUNDS, source: str = "") -> list[dict]:
    """Scroll down to load content, then extract all posts found."""
    await page.wait_for_timeout(2000)

    # Save screenshot before scrolling (best effort)
    try:
        await page.screenshot(path=str(Path(__file__).parent / f"debug_{source or 'page'}.png"), timeout=5000)
    except Exception:
        pass

    posts = []
    seen_ids = set()
    too_old_streak = 0  # consecutive scrolls where all new posts are before DATE_FROM

    for i in range(rounds):
        batch = await extract_all_posts(page, source=source)
        new_this_scroll = 0
        old_this_scroll = 0
        for p in batch:
            if p["post_id"] not in seen_ids:
                seen_ids.add(p["post_id"])
                posts.append(p)
                ts = p.get("timestamp", "")
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

        # If this scroll added only out-of-range posts, increment streak
        if DATE_FROM and old_this_scroll > 0 and new_this_scroll == 0:
            too_old_streak += 1
        else:
            too_old_streak = 0

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2.5)")
        await page.wait_for_timeout(SCROLL_PAUSE)
        print(f"  scroll {i+1}/{rounds} — {len(posts)} posts so far")

        # Stop early if we've seen 3 consecutive scrolls of only old content
        if too_old_streak >= 3:
            print(f"  [DateFilter] Feed is older than {DATE_FROM.date()} — stopping early")
            break

    print(f"[Collect] Total from {source}: {len(posts)} posts")
    return posts


# ── Post extraction ───────────────────────────────────────────────────────────

async def extract_all_posts(page: Page, source: str = "") -> list[dict]:
    posts = []

    # Try to find feed container first
    feed = await page.query_selector('[role="feed"]')
    if feed:
        articles = await feed.query_selector_all('[role="article"]')
    else:
        articles = await page.query_selector_all('[role="article"]')

    for i, article in enumerate(articles):
        try:
            post = await extract_post(article, source=source)
            if post:
                posts.append(post)
        except Exception:
            continue

    return posts


async def extract_post(article, source: str = "") -> dict | None:
    # --- Text ---
    text = ""
    for sel in ['[data-ad-preview="message"]', '[dir="auto"]', 'span[lang]', 'p']:
        try:
            els = await article.query_selector_all(sel)
            for el in els:
                t = (await el.inner_text()).strip()
                if len(t) > 15:
                    text = t
                    break
            if text:
                break
        except Exception:
            continue

    # --- Post URL & timestamp ---
    post_url = ""
    raw_timestamp = ""

    for frag in ['/posts/', '/videos/', 'story_fbid', '/reel/', '/photo/', '/permalink/']:
        try:
            el = await article.query_selector(f'a[href*="{frag}"]')
            if el:
                href = await el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://www.facebook.com" + href
                post_url = href
                # Also try to grab timestamp from this same link element
                if not raw_timestamp:
                    raw_timestamp = await el.get_attribute("aria-label") or ""
                break
        except Exception:
            continue

    # Timestamp — try multiple methods in order of reliability
    # Method 1: data-utime (Unix timestamp — most accurate)
    if not raw_timestamp:
        try:
            el = await article.query_selector('[data-utime]')
            if el:
                raw_timestamp = await el.get_attribute("data-utime") or ""
        except Exception:
            pass

    # Method 2: abbr element
    if not raw_timestamp:
        try:
            abbr = await article.query_selector('abbr[data-utime], abbr[title]')
            if abbr:
                raw_timestamp = (await abbr.get_attribute("data-utime") or
                                 await abbr.get_attribute("title") or
                                 await abbr.inner_text())
        except Exception:
            pass

    # Method 3: <time> HTML element (modern Facebook)
    if not raw_timestamp:
        try:
            time_el = await article.query_selector('time[datetime]')
            if time_el:
                raw_timestamp = await time_el.get_attribute("datetime") or await time_el.inner_text()
        except Exception:
            pass

    # Method 4: aria-label on time/span/a elements
    if not raw_timestamp:
        try:
            for sel in [
                'a[aria-label*="at "]', 'span[aria-label*="at "]',
                'a[aria-label*="ago"]',  'span[aria-label*="ago"]',
                'a[aria-label*="hour"]', 'a[aria-label*="day"]',
                'a[aria-label*="week"]', 'a[aria-label*="minute"]',
                'a[aria-label*="March"]','a[aria-label*="February"]',
                'a[aria-label*="January"]','a[aria-label*="April"]',
            ]:
                el = await article.query_selector(sel)
                if el:
                    raw_timestamp = await el.get_attribute("aria-label") or ""
                    if raw_timestamp:
                        break
        except Exception:
            pass

    # Method 5: visible relative time text ("2h", "3d", "March 10")
    if not raw_timestamp:
        try:
            time_els = await article.query_selector_all('a span, span[id], a[role="link"] span')
            for el in time_els:
                t = (await el.inner_text()).strip()
                if (re.match(r'^\d+[hHdDwWmMyY]$', t) or
                        re.match(r'^\d+ (hour|day|week|minute|month|year)', t, re.I) or
                        re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* \d+', t)):
                    raw_timestamp = t
                    break
        except Exception:
            pass

    timestamp = parse_timestamp(raw_timestamp)

    # --- Author (useful for search results from other people) ---
    author = ""
    try:
        for sel in [
            'h2 a[role="link"]', 'h3 a[role="link"]',
            'h2 a', 'h3 a', 'h4 a',
            '[data-testid="post_author"] a',
            'strong a', 'a[aria-label][role="link"]',
        ]:
            author_el = await article.query_selector(sel)
            if author_el:
                candidate = (await author_el.inner_text()).strip()
                # Skip generic labels like "See more", "Photo", etc.
                if candidate and len(candidate) > 1 and len(candidate) < 80:
                    author = candidate
                    break
    except Exception:
        pass

    # Skip truly empty
    if not text and not post_url:
        return None

    post_id = make_id(source or PAGE_NAME, post_url or text[:50], timestamp)

    # --- Reactions & counts (text-based parsing — resilient to HTML changes) ---
    reactions = await extract_reactions(article)
    counts    = await extract_counts_from_text(article)

    comments_count = counts["comments"] or await get_count(article, ["comment", "comments"])
    shares         = counts["shares"]   or await get_count(article, ["share", "shares"])
    views          = counts["views"]    or await get_count(article, ["view", "views"])
    if reactions["total"] == 0:
        reactions["total"] = counts["reactions"]

    # --- Media type ---
    media_type = "text"
    try:
        if await article.query_selector("video"):
            media_type = "video"
        elif await article.query_selector('img[src*="scontent"]'):
            media_type = "image"
    except Exception:
        pass

    return {
        "post_id":         post_id,
        "page_name":       author or source or PAGE_NAME,
        "text":            text,
        "timestamp":       timestamp,
        "likes":           reactions.get("total", 0),
        "comments_count":  comments_count,
        "shares":          shares,
        "views":           views,
        "reactions_like":  reactions.get("like", 0),
        "reactions_love":  reactions.get("love", 0),
        "reactions_haha":  reactions.get("haha", 0),
        "reactions_wow":   reactions.get("wow", 0),
        "reactions_sad":   reactions.get("sad", 0),
        "reactions_angry": reactions.get("angry", 0),
        "post_url":        post_url,
        "media_type":      media_type,
    }


_debug_printed = False  # reset each run — prints first article raw text for diagnosis

async def extract_counts_from_text(article) -> dict:
    """
    Parse the post's raw text for reaction/comment/share/view counts.
    Resilient to Facebook HTML changes because it uses text patterns.
    """
    global _debug_printed
    counts = {"reactions": 0, "comments": 0, "shares": 0, "views": 0}
    try:
        text = await article.inner_text()

        # Debug: print the raw text of the first article once so we can see the format
        if not _debug_printed:
            _debug_printed = True
            print("\n[DEBUG] First article raw text (first 1200 chars):")
            print(repr(text[:1200]))
            print("[DEBUG] ---\n")

        # Reactions — multiple patterns Facebook uses
        for pattern in [
            r'([\d,.]+[KkMm]?)\s*(?:people\s+)?reaction',        # "143 reactions"
            r'You(?:,\s*\w+)? and ([\d,.]+[KkMm]?) others',      # "You and 142 others"
            r'([\d,.]+[KkMm]?)\s*others?\s+reacted',              # "143 others reacted"
            r'^([\d,.]+[KkMm]?)\s*$',                             # bare number on its own line
        ]:
            m = re.search(pattern, text, re.I | re.M)
            if m:
                counts["reactions"] = parse_count(m.group(1))
                break

        # If still 0, look for a standalone number just before the action bar
        if counts["reactions"] == 0:
            # The action bar contains "Like · Comment · Share" — find numbers just above it
            action_m = re.search(
                r'([\d,.]+[KkMm]?)\s*\n+\s*(?:Like|Comment|Share)',
                text, re.I
            )
            if action_m:
                counts["reactions"] = parse_count(action_m.group(1))

        # Comments — "45 Comments" or "1 Comment"
        m = re.search(r'([\d,.]+[KkMm]?)\s*[Cc]omments?(?:\s|$)', text)
        if m:
            counts["comments"] = parse_count(m.group(1))

        # Shares — "12 Shares" or "12 shares"
        m = re.search(r'([\d,.]+[KkMm]?)\s*[Ss]hares?(?:\s|$)', text)
        if m:
            counts["shares"] = parse_count(m.group(1))

        # Views — "5K Views" or "5K views"
        m = re.search(r'([\d,.]+[KkMm]?)\s*[Vv]iews?(?:\s|$)', text)
        if m:
            counts["views"] = parse_count(m.group(1))

    except Exception:
        pass
    return counts


async def get_count(article, labels: list) -> int:
    # Kept for backwards compat — use extract_counts_from_text instead
    for label in labels:
        try:
            el = await article.query_selector(f'[aria-label*="{label}"]')
            if el:
                return parse_count(await el.inner_text())
        except Exception:
            continue
    return 0


async def extract_reactions(article) -> dict:
    r = {"total": 0, "like": 0, "love": 0, "haha": 0, "wow": 0, "sad": 0, "angry": 0}
    try:
        # Method 1: aria-label selectors
        for sel in ['[aria-label*="reaction"]', '[aria-label*=" reacted"]', '[aria-label*="people reacted"]']:
            el = await article.query_selector(sel)
            if el:
                r["total"] = parse_count(await el.inner_text())
                if r["total"]:
                    break

        # Method 2: fall back to text parsing if aria-label gave nothing
        if r["total"] == 0:
            counts = await extract_counts_from_text(article)
            r["total"] = counts["reactions"]

        # Individual reaction types
        for key, aria in {
            "like": "Like", "love": "Love", "haha": "Haha",
            "wow": "Wow", "sad": "Sad", "angry": "Angry"
        }.items():
            for sel in [f'[aria-label="{aria}"]', f'[aria-label*="{aria} reaction"]']:
                el = await article.query_selector(sel)
                if el:
                    val = parse_count(await el.inner_text())
                    if val:
                        r[key] = val
                        break
    except Exception:
        pass
    return r


# ── Per-post metrics enrichment ───────────────────────────────────────────────

async def enrich_metrics(page: Page, post_url: str) -> dict:
    """
    Visit a post's own page and extract engagement metrics.
    Much more reliable than feed-view extraction because the numbers
    are rendered prominently on the post page itself.
    Returns dict with keys: likes, comments_count, shares, views,
    reactions_like, reactions_love, reactions_haha, reactions_wow,
    reactions_sad, reactions_angry.
    """
    metrics = {
        "likes": 0, "comments_count": 0, "shares": 0, "views": 0,
        "reactions_like": 0, "reactions_love": 0, "reactions_haha": 0,
        "reactions_wow": 0, "reactions_sad": 0, "reactions_angry": 0,
    }
    try:
        await goto(page, post_url, label="enrich metrics")
        await page.wait_for_timeout(2000)

        # Get the main content text — much cleaner than the feed
        main_text = ""
        try:
            main_el = await page.query_selector('[role="main"]')
            if main_el:
                main_text = await main_el.inner_text()
        except Exception:
            pass

        if not main_text:
            main_text = await page.inner_text("body")

        # ── Reaction count ──────────────────────────────────────────────
        # Try DOM elements first
        for sel in [
            '[aria-label*="people reacted"]',
            '[data-testid="UFI2ReactionsCount/root"] span',
            'span[aria-label*="reaction"]',
            'a[aria-label*="people reacted"]',
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    val = parse_count(await el.inner_text() or await el.get_attribute("aria-label") or "")
                    if val:
                        metrics["likes"] = val
                        break
            except Exception:
                continue

        # Text-based fallback on the page text
        if metrics["likes"] == 0:
            for pattern in [
                r'([\d,.]+[KkMm]?)\s*(?:people\s+)?reaction',
                r'You(?:,\s*\w+)? and ([\d,.]+[KkMm]?) others',
                r'([\d,.]+[KkMm]?)\s*others?\s+reacted',
            ]:
                m = re.search(pattern, main_text, re.I)
                if m:
                    metrics["likes"] = parse_count(m.group(1))
                    break

        # Look for standalone number just before the Like/Comment/Share bar
        if metrics["likes"] == 0:
            m = re.search(r'([\d,.]+[KkMm]?)\s*\n+\s*(?:Like|Comment|Share)', main_text, re.I)
            if m:
                metrics["likes"] = parse_count(m.group(1))

        # ── Comment count ───────────────────────────────────────────────
        for sel in [
            '[data-testid="UFI2CommentsCount/root"]',
            'a[href*="comment"]',
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    val = parse_count(await el.inner_text())
                    if val:
                        metrics["comments_count"] = val
                        break
            except Exception:
                continue

        if metrics["comments_count"] == 0:
            m = re.search(r'([\d,.]+[KkMm]?)\s*[Cc]omments?', main_text)
            if m:
                metrics["comments_count"] = parse_count(m.group(1))

        # ── Share count ─────────────────────────────────────────────────
        for sel in [
            '[data-testid="UFI2SharesCount/root"]',
            'a[aria-label*="share"]',
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    val = parse_count(await el.inner_text())
                    if val:
                        metrics["shares"] = val
                        break
            except Exception:
                continue

        if metrics["shares"] == 0:
            m = re.search(r'([\d,.]+[KkMm]?)\s*[Ss]hares?', main_text)
            if m:
                metrics["shares"] = parse_count(m.group(1))

        # ── View count (videos) ─────────────────────────────────────────
        m = re.search(r'([\d,.]+[KkMm]?)\s*[Vv]iews?', main_text)
        if m:
            metrics["views"] = parse_count(m.group(1))

        # ── Individual reaction types ───────────────────────────────────
        for key, label in {
            "reactions_like": "Like", "reactions_love": "Love",
            "reactions_haha": "Haha", "reactions_wow": "Wow",
            "reactions_sad":  "Sad",  "reactions_angry": "Angry",
        }.items():
            try:
                el = await page.query_selector(
                    f'[aria-label="{label}"], [aria-label*="{label} reaction"]'
                )
                if el:
                    val = parse_count(await el.inner_text())
                    if val:
                        metrics[key] = val
            except Exception:
                continue

    except Exception as e:
        print(f"  [Enrich] Error for {post_url[:60]}: {e}")

    return metrics


# ── Comment scraping ──────────────────────────────────────────────────────────

async def scrape_comments(page: Page, post: dict) -> list[dict]:
    if not post.get("post_url"):
        return []

    comments = []
    try:
        await goto(page, post["post_url"], label="post for comments")
        await page.wait_for_timeout(2000)

        # Click "Most relevant" dropdown → switch to "All comments" to get more
        try:
            sort_btn = await page.query_selector(
                'div[aria-label*="Comment"] span:has-text("Most relevant"), '
                'span:has-text("Most relevant"), [role="button"]:has-text("Most relevant")'
            )
            if sort_btn:
                await sort_btn.click()
                await page.wait_for_timeout(1500)
                top_opt = await page.query_selector('div[role="menuitem"]:has-text("Top comments")')
                if top_opt:
                    await top_opt.click()
                    await page.wait_for_timeout(1500)
        except Exception:
            pass

        # Try selectors for comment containers (modern Facebook uses nested [role="article"])
        comment_els = []

        for sel in [
            '[aria-label^="Comment by"]',
            '[role="article"][tabindex="-1"]',
            'ul[aria-label*="omment"] > li',
            'div[data-testid="UFI2CommentsList/root_depth_0"] > div',
        ]:
            els = await page.query_selector_all(sel)
            if els:
                comment_els = els
                break

        # Fallback: find the comment section by looking for nested articles
        if not comment_els:
            feed = await page.query_selector('[role="main"]')
            if feed:
                comment_els = await feed.query_selector_all('[role="article"]')
                # Skip the first one — it's the post itself
                comment_els = comment_els[1:]

        # Limit to top COMMENT_LIMIT (Facebook sorts top comments by default)
        comment_els = comment_els[:COMMENT_LIMIT]

        for el in comment_els:
            try:
                c = await extract_comment(el, post["post_id"])
                if c:
                    comments.append(c)
            except Exception:
                continue

        print(f"  [Comments] {len(comments)} extracted from {post.get('text','')[:40]!r}")
    except Exception as e:
        print(f"  [Comments] Error: {e}")

    return comments


async def extract_comment(el, post_id: str) -> dict | None:
    try:
        full_text = (await el.inner_text()).strip()
        if not full_text or len(full_text) < 2:
            return None

        # Author — first linked name in the comment
        author = ""
        for sel in ['a[role="link"] span', 'a span', 'h3 a', 'h4 a']:
            author_el = await el.query_selector(sel)
            if author_el:
                candidate = (await author_el.inner_text()).strip()
                if candidate and len(candidate) > 1:
                    author = candidate
                    break

        # Comment text — prefer [dir="auto"] blocks, skip author name
        text = ""
        for sel in ['[dir="auto"]', 'span[lang]', 'p']:
            text_els = await el.query_selector_all(sel)
            for te in text_els:
                t = (await te.inner_text()).strip()
                # Skip very short bits and bits that are just the author name
                if len(t) > 2 and t != author:
                    text = t
                    break
            if text:
                break

        # Fall back to full text minus author prefix if needed
        if not text:
            text = full_text
        if not text or len(text) < 2:
            return None

        # Timestamp
        raw_ts = ""
        for sel in ['abbr[data-utime]', 'abbr[title]', 'time[datetime]',
                    'a[aria-label*="ago"]', 'a[aria-label*="at "]', 'abbr']:
            ts_el = await el.query_selector(sel)
            if ts_el:
                raw_ts = (await ts_el.get_attribute("data-utime") or
                          await ts_el.get_attribute("datetime") or
                          await ts_el.get_attribute("title") or
                          await ts_el.get_attribute("aria-label") or
                          await ts_el.inner_text())
                if raw_ts:
                    break
        timestamp = parse_timestamp(raw_ts)

        # Likes on the comment
        likes = 0
        for sel in ['[aria-label*="reaction"]', '[aria-label*="Like"]']:
            like_el = await el.query_selector(sel)
            if like_el:
                likes = parse_count(await like_el.inner_text())
                if likes:
                    break

        return {
            "comment_id":  make_id(post_id, author, text[:40]),
            "post_id":     post_id,
            "author_name": author,
            "text":        text,
            "likes":       likes,
            "timestamp":   timestamp,
            "is_reply":    0,
            "parent_id":   None,
        }
    except Exception:
        return None


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run(email: str, password: str, scrape_comments_flag: bool = True):
    global _debug_printed
    _debug_printed = False  # reset so we always see debug output on a fresh run
    init_db()
    all_posts = []

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

        # Session / login
        session_loaded = await load_session(context)
        if session_loaded:
            await goto(page, "https://www.facebook.com", "home check")
            if "login" in page.url:
                print("[Session] Expired — logging in fresh...")
                session_loaded = False

        if not session_loaded:
            ok = await login(page, email, password)
            if not ok:
                print("[!] Login failed. Exiting.")
                await browser.close()
                return
            await save_session(context)

        def collect_and_save(posts: list, source: str):
            """Apply relevance + date filters then save."""
            kept = dropped = out_of_range = 0
            for post in posts:
                if not in_date_range(post.get("timestamp", "")):
                    out_of_range += 1
                    continue
                if is_relevant(post.get("text", ""), post.get("page_name", ""), source):
                    save_post(post)
                    all_posts.append(post)
                    kept += 1
                else:
                    dropped += 1
            if out_of_range:
                print(f"  [DateFilter] Dropped {out_of_range} posts outside date range")
            if dropped:
                print(f"  [Filter] Kept {kept}, dropped {dropped} location-only mentions")

        # ── 1. Official page posts ─────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 1: Official page posts")
        print("="*55)
        await goto(page, TARGET_PAGE, "official page")
        # Wait for at least one article to appear before scrolling
        try:
            await page.wait_for_selector('[role="article"]', timeout=15000)
        except Exception:
            print("  [!] No articles found on official page — FB may require login or the page is slow")
        posts = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="official_page")
        collect_and_save(posts, "official_page")

        # ── 2. Facebook Search — Posts tab ────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 2: Facebook Search — all posts mentioning the brand")
        print("="*55)
        await goto(page, SEARCH_URLS["posts"], "search:posts")
        try:
            await page.wait_for_selector('[role="article"]', timeout=10000)
        except Exception:
            pass
        posts = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="search_posts")
        collect_and_save(posts, "search_posts")

        # ── 3. Facebook Search — Top results ──────────────────────────────
        print("\n" + "="*55)
        print("SECTION 3: Facebook Search — Top results")
        print("="*55)
        await goto(page, SEARCH_URLS["top"], "search:top")
        try:
            await page.wait_for_selector('[role="article"]', timeout=10000)
        except Exception:
            pass
        posts = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="search_top")
        collect_and_save(posts, "search_top")

        # ── 4. Facebook Search — Videos ───────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 4: Facebook Search — Videos")
        print("="*55)
        await goto(page, SEARCH_URLS["videos"], "search:videos")
        try:
            await page.wait_for_selector('[role="article"]', timeout=10000)
        except Exception:
            pass
        posts = await scroll_and_collect(page, rounds=8, source="search_videos")
        collect_and_save(posts, "search_videos")

        # ── 5. Reviews ────────────────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 5: Page reviews")
        print("="*55)
        await goto(page, REVIEWS_URL, "reviews")
        try:
            await page.wait_for_selector('[role="article"]', timeout=10000)
        except Exception:
            pass
        posts = await scroll_and_collect(page, rounds=5, source="reviews")
        collect_and_save(posts, "reviews")

        # ── 6. Enrich metrics for posts that came back empty ──────────────
        zero_engagement = [
            p for p in all_posts
            if p.get("post_url") and p.get("likes", 0) == 0 and p.get("comments_count", 0) == 0
        ]
        if zero_engagement:
            print("\n" + "="*55)
            print(f"SECTION 6: Enriching metrics for {len(zero_engagement)} posts with zero engagement")
            print("="*55)
            for i, post in enumerate(zero_engagement):
                print(f"  [{i+1}/{len(zero_engagement)}] {post.get('text','')[:50]}...")
                metrics = await enrich_metrics(page, post["post_url"])
                # Update in-memory post and DB if we found anything
                if any(v > 0 for v in metrics.values()):
                    post.update(metrics)
                    save_post(post)
                    print(f"    → likes={metrics['likes']} comments={metrics['comments_count']} shares={metrics['shares']}")
                await page.wait_for_timeout(800)

        # ── 7. Comments on all posts ──────────────────────────────────────
        if scrape_comments_flag:
            # Only scrape comments for posts that have a URL
            posts_with_url = [p for p in all_posts if p.get("post_url")]
            print("\n" + "="*55)
            print(f"SECTION 7: Scraping top {COMMENT_LIMIT} comments for {len(posts_with_url)} posts")
            print("="*55)
            for i, post in enumerate(posts_with_url):
                print(f"[{i+1}/{len(posts_with_url)}] {post.get('text', '')[:50]}...")
                comments = await scrape_comments(page, post)
                for c in comments:
                    save_comment(c)
                await page.wait_for_timeout(1000)

        await browser.close()

    stats = get_stats()
    print("\n" + "="*55)
    print("SCRAPE COMPLETE")
    print(f"  Posts collected:    {stats['total_posts']}")
    print(f"  Comments collected: {stats['total_comments']}")
    print(f"  Total likes:        {stats['total_likes']}")
    print(f"  Total shares:       {stats['total_shares']}")
    print("="*55)
