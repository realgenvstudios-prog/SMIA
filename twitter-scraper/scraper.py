"""
Twitter/X Intelligence Scraper — Eddy's Pizza Ghana
Collects all X/Twitter content related to the brand:
  1. Their official X profile tweets
  2. X Search — tweets by anyone mentioning them
  3. Hashtag pages (#eddyspizzaghana, #eddyspizza)
  4. Top replies on each tweet
"""

import asyncio
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from patchright.async_api import async_playwright, Page, BrowserContext

from db import init_db, save_tweet, save_reply, delete_tweet, get_stats

# ── Config ────────────────────────────────────────────────────────────────────

SEARCH_QUERY  = "KonnectedMinds"
TARGET_HANDLE = "KonnectedMinds"
TARGET_PAGE   = f"https://x.com/{TARGET_HANDLE}"
BRAND_NAME    = "konnectedminds"
COOKIES_FILE  = Path(__file__).parent / "x_session.json"
SCROLL_ROUNDS = 12
SCROLL_PAUSE  = 2500   # ms — X loads more slowly than TikTok
REPLY_LIMIT   = 10     # top N replies per tweet

# ── Date range filter ─────────────────────────────────────────────────────────

_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
DATE_FROM = _today if os.getenv("CI", "").lower() == "true" else datetime(2026, 1, 1)
DATE_TO   = None

SEARCH_URL   = f"https://x.com/search?q={SEARCH_QUERY.replace(' ', '%20')}&f=live"
HASHTAG_URLS = [
    "https://x.com/hashtag/konnectedminds",
    "https://x.com/hashtag/konnected",
    "https://x.com/hashtag/konnectedmindsgh",
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

    # X embeds ISO timestamps in time[datetime] attributes — prefer these
    # e.g. "2026-03-10T14:23:00.000Z"
    m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', raw)
    if m:
        return m.group(1)

    # Already YYYY-MM-DD
    if re.match(r'\d{4}-\d{2}-\d{2}', raw):
        return raw

    # "Mar 10" / "March 10, 2026"
    for fmt in ["%b %d, %Y", "%B %d, %Y", "%b %d", "%B %d"]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.isoformat()
        except Exception:
            pass

    # Relative: "2h", "3d", "5m"
    m = re.match(r'^(\d+)(s|m|h|d|w)$', raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta_map = {
            "s": timedelta(seconds=n), "m": timedelta(minutes=n),
            "h": timedelta(hours=n),   "d": timedelta(days=n),
            "w": timedelta(weeks=n),
        }
        return (now - delta_map[unit]).isoformat()

    # Long-form relative: "2 hours ago"
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

    if re.match(r'^(just now|now)$', raw, re.I):
        return now.isoformat()

    return raw


def in_date_range(timestamp_str: str) -> bool:
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
        nums = re.findall(r'\d+\.?\d*', text)
        return int(float(nums[0])) if nums else 0
    except Exception:
        return 0


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
        'button:has-text("Accept all cookies")',
        'button:has-text("Refuse non-essential cookies")',
        'button:has-text("Close")',
        '[data-testid="xMigrationBottomBar"] button',
        'div[role="dialog"] button:has-text("Not now")',
        'div[role="dialog"] button:has-text("Skip for now")',
        'a[role="button"]:has-text("Not now")',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            continue


# ── Tweet extraction ──────────────────────────────────────────────────────────

_debug_printed = False


async def scroll_and_collect(page: Page, rounds: int = SCROLL_ROUNDS, source: str = "") -> list[dict]:
    await page.wait_for_timeout(2000)
    tweets = []
    seen_ids = set()
    too_old_streak = 0

    for i in range(rounds):
        batch = await extract_all_tweets(page, source=source)
        new_this_scroll = old_this_scroll = 0
        for t in batch:
            if t["tweet_id"] not in seen_ids:
                seen_ids.add(t["tweet_id"])
                tweets.append(t)
                ts = t.get("timestamp", "")
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
        print(f"  scroll {i+1}/{rounds} — {len(tweets)} tweets so far")

        if too_old_streak >= 3:
            print(f"  [DateFilter] Feed is older than {DATE_FROM.date()} — stopping early")
            break

    print(f"[Collect] Total from {source}: {len(tweets)} tweets")
    return tweets


async def extract_all_tweets(page: Page, source: str = "") -> list[dict]:
    tweets = []
    items = await page.query_selector_all('article[data-testid="tweet"]')
    for item in items:
        try:
            t = await extract_tweet(item, source=source)
            if t:
                tweets.append(t)
        except Exception:
            continue
    return tweets


async def extract_tweet(item, source: str = "") -> dict | None:
    global _debug_printed

    # ── Tweet URL & ID ────────────────────────────────────────────────────────
    tweet_url = ""
    tweet_id  = ""
    try:
        # X tweet links are in the time element's parent anchor
        link_el = await item.query_selector('a[href*="/status/"]')
        if link_el:
            href = await link_el.get_attribute("href") or ""
            tweet_url = href if href.startswith("http") else "https://x.com" + href
    except Exception:
        pass

    m = re.search(r'/status/(\d+)', tweet_url)
    if m:
        tweet_id = m.group(1)

    # ── Author ────────────────────────────────────────────────────────────────
    author_username = ""
    author_name     = ""
    try:
        # Display name: first span in the User-Name block
        name_el = await item.query_selector('[data-testid="User-Name"] span span')
        if name_el:
            author_name = (await name_el.inner_text()).strip()

        # Username: the @handle link
        handle_el = await item.query_selector('[data-testid="User-Name"] a[href^="/"]')
        if handle_el:
            href = await handle_el.get_attribute("href") or ""
            author_username = href.lstrip("/").split("/")[0]
    except Exception:
        pass

    if not author_name:
        author_name = author_username

    # ── Tweet text ────────────────────────────────────────────────────────────
    text = ""
    try:
        text_el = await item.query_selector('[data-testid="tweetText"]')
        if text_el:
            text = (await text_el.inner_text()).strip()
    except Exception:
        pass

    # Debug print first card
    if not _debug_printed and source and text:
        _debug_printed = True
        try:
            raw = (await item.inner_text()).strip()
            print(f"\n[DEBUG] First tweet card raw text ({source}):")
            print(repr(raw[:600]))
            print("[DEBUG] ---\n")
        except Exception:
            pass

    # ── Timestamp ─────────────────────────────────────────────────────────────
    raw_ts = ""
    try:
        time_el = await item.query_selector("time")
        if time_el:
            raw_ts = await time_el.get_attribute("datetime") or ""
    except Exception:
        pass
    timestamp = parse_timestamp(raw_ts)

    # ── Engagement counts ─────────────────────────────────────────────────────
    replies_count = await _get_action_count(item, "reply")
    retweets      = await _get_action_count(item, "retweet")
    likes         = await _get_action_count(item, "like")
    views         = await _get_view_count(item)

    # ── Hashtags ──────────────────────────────────────────────────────────────
    hashtags = " ".join(re.findall(r'#\w+', text))

    # Skip truly empty
    if not tweet_url and not text:
        return None

    if not tweet_id:
        tweet_id = make_id(source, tweet_url or text[:60])

    return {
        "tweet_id":       tweet_id,
        "author_username": author_username,
        "author_name":    author_name,
        "text":           text,
        "timestamp":      timestamp,
        "likes":          likes,
        "replies_count":  replies_count,
        "retweets":       retweets,
        "views":          views,
        "post_url":       tweet_url,
        "hashtags":       hashtags,
        "source":         source,
    }


async def _get_action_count(item, action: str) -> int:
    """Read count from X's action button aria-label (most reliable)."""
    # X renders counts in the aria-label of the action group button
    # e.g. aria-label="123 Likes. Like."  or just aria-label="Like"
    try:
        btn = await item.query_selector(f'button[data-testid="{action}"]')
        if btn:
            label = await btn.get_attribute("aria-label") or ""
            m = re.search(r'([\d,.]+[KkMmBb]?)\s+', label)
            if m:
                return parse_count(m.group(1))
            # Also try the inner span count
            count_el = await btn.query_selector('span[data-testid="app-text-transition-container"] span')
            if count_el:
                val = parse_count(await count_el.inner_text())
                if val:
                    return val
    except Exception:
        pass
    return 0


async def _get_view_count(item) -> int:
    """X shows views as a separate analytics link."""
    try:
        # aria-label on the analytics link: "1234 views"
        analytics_el = await item.query_selector('a[href*="/analytics"]')
        if analytics_el:
            label = await analytics_el.get_attribute("aria-label") or ""
            m = re.search(r'([\d,.]+[KkMmBb]?)\s+views?', label, re.I)
            if m:
                return parse_count(m.group(1))
            # fallback: inner text
            count_el = await analytics_el.query_selector('span')
            if count_el:
                val = parse_count(await count_el.inner_text())
                if val:
                    return val
        # Newer X layout: data-testid="views"
        views_el = await item.query_selector('[data-testid="views"]')
        if views_el:
            label = await views_el.get_attribute("aria-label") or ""
            m = re.search(r'([\d,.]+[KkMmBb]?)', label)
            if m:
                return parse_count(m.group(1))
            return parse_count(await views_el.inner_text())
    except Exception:
        pass
    return 0


# ── Reply scraping ────────────────────────────────────────────────────────────

async def scrape_replies(page: Page, tweet: dict) -> list[dict]:
    if not tweet.get("post_url"):
        return []

    replies = []
    try:
        await goto(page, tweet["post_url"], label="tweet page")
        await page.wait_for_timeout(2000)

        # Scroll to load replies
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
            await page.wait_for_timeout(1200)

        # All tweet articles on a tweet detail page — first is the original, rest are replies
        articles = await page.query_selector_all('article[data-testid="tweet"]')
        reply_articles = articles[1:REPLY_LIMIT + 1]  # skip the original tweet

        for el in reply_articles:
            try:
                r = await extract_reply(el, tweet["tweet_id"])
                if r:
                    replies.append(r)
            except Exception:
                continue

        print(f"  [Replies] {len(replies)} extracted from tweet {tweet['tweet_id']}")
    except Exception as e:
        print(f"  [Replies] Error: {e}")

    return replies


async def extract_reply(el, parent_tweet_id: str) -> dict | None:
    try:
        text_el = await el.query_selector('[data-testid="tweetText"]')
        if not text_el:
            return None
        text = (await text_el.inner_text()).strip()
        if not text or len(text) < 2:
            return None

        # Author
        author_username = ""
        author_name     = ""
        name_el = await el.query_selector('[data-testid="User-Name"] span span')
        if name_el:
            author_name = (await name_el.inner_text()).strip()
        handle_el = await el.query_selector('[data-testid="User-Name"] a[href^="/"]')
        if handle_el:
            href = await handle_el.get_attribute("href") or ""
            author_username = href.lstrip("/").split("/")[0]
        if not author_name:
            author_name = author_username

        # Timestamp
        raw_ts = ""
        time_el = await el.query_selector("time")
        if time_el:
            raw_ts = await time_el.get_attribute("datetime") or ""
        timestamp = parse_timestamp(raw_ts)

        # Likes
        likes = await _get_action_count(el, "like")

        # Reply URL for ID
        reply_url = ""
        link_el = await el.query_selector('a[href*="/status/"]')
        if link_el:
            href = await link_el.get_attribute("href") or ""
            reply_url = href if href.startswith("http") else "https://x.com" + href

        m = re.search(r'/status/(\d+)', reply_url)
        reply_id = m.group(1) if m else make_id(parent_tweet_id, author_username, text[:40])

        return {
            "reply_id":       reply_id,
            "tweet_id":       parent_tweet_id,
            "author_username": author_username,
            "author_name":    author_name,
            "text":           text,
            "likes":          likes,
            "timestamp":      timestamp,
            "is_reply":       1,
            "parent_id":      parent_tweet_id,
        }
    except Exception:
        return None


# ── Relevance filter ──────────────────────────────────────────────────────────

def is_relevant(text: str, author_username: str, source: str) -> bool:
    """Keep only content genuinely about Eddy's Pizza Ghana."""
    if source in ("profile", "hashtag_konnectedminds"):
        return True

    text_l   = text.lower()
    author_l = author_username.lower()

    # Official account's own tweets
    if "konnected" in author_l:
        return True

    # Must mention "konnected" specifically
    if not re.search(r"konnected", text_l):
        return False

    return True


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run(scrape_replies_flag: bool = True):
    global _debug_printed
    _debug_printed = False
    init_db()
    all_tweets = []

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

        await load_session(context)

        def collect_and_save(tweets: list, source: str):
            kept = dropped = out_of_range = 0
            for t in tweets:
                if not in_date_range(t.get("timestamp", "")):
                    out_of_range += 1
                    continue
                if is_relevant(t.get("text", ""), t.get("author_username", ""), source):
                    save_tweet(t)
                    all_tweets.append(t)
                    kept += 1
                else:
                    dropped += 1
            if out_of_range:
                print(f"  [DateFilter] Dropped {out_of_range} tweets outside date range")
            if dropped:
                print(f"  [Filter] Kept {kept}, dropped {dropped} off-topic tweets")

        # ── 1. Official X profile ──────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 1: Official X profile")
        print("="*55)
        await goto(page, TARGET_PAGE, "official profile")
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
        except Exception:
            print("  [!] No tweets found on official profile — may require login")
        tweets = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="profile")
        collect_and_save(tweets, "profile")

        # ── 2. X Search ───────────────────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 2: X Search")
        print("="*55)
        await goto(page, SEARCH_URL, "search")
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
        except Exception:
            pass
        tweets = await scroll_and_collect(page, rounds=SCROLL_ROUNDS, source="search")
        collect_and_save(tweets, "search")

        # ── 3. Hashtag pages ──────────────────────────────────────────────
        for tag_url in HASHTAG_URLS:
            tag = tag_url.split("/hashtag/")[-1]
            print("\n" + "="*55)
            print(f"SECTION 3: Hashtag #{tag}")
            print("="*55)
            await goto(page, tag_url, f"#{tag}")
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            except Exception:
                pass
            source = f"hashtag_{tag}"
            tweets = await scroll_and_collect(page, rounds=8, source=source)
            collect_and_save(tweets, source)

        # ── 4. Save session ───────────────────────────────────────────────
        await save_session(context)

        # ── 5. Replies ────────────────────────────────────────────────────
        if scrape_replies_flag:
            tweets_with_url = [t for t in all_tweets if t.get("post_url")]
            print("\n" + "="*55)
            print(f"SECTION 4: Scraping top {REPLY_LIMIT} replies for {len(tweets_with_url)} tweets")
            print("="*55)
            for i, tweet in enumerate(tweets_with_url):
                print(f"[{i+1}/{len(tweets_with_url)}] {tweet.get('text', '')[:50]}...")
                replies = await scrape_replies(page, tweet)
                for r in replies:
                    save_reply(r)
                await page.wait_for_timeout(1500)

        await browser.close()

    stats = get_stats()
    print("\n" + "="*55)
    print("SCRAPE COMPLETE")
    print(f"  Tweets collected:  {stats['total_tweets']}")
    print(f"  Replies collected: {stats['total_replies']}")
    print(f"  Total likes:       {stats['total_likes']}")
    print(f"  Total views:       {stats['total_views']}")
    print(f"  Total retweets:    {stats['total_retweets']}")
    print("="*55)
