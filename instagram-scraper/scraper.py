"""
Instagram Intelligence Scraper — Eddy's Pizza Ghana
Collects ALL Instagram content related to the brand:
  1. Official Instagram page posts + reels
  2. Hashtag pages (#eddyspizzaghana, #eddyspizza, etc.)
  3. Per-post enrichment for any posts missing stats
  4. Top 10 comments per post

Primary strategy: XHR interception of Instagram's own internal API calls
  - web_profile_info  → profile posts with full stats
  - api/graphql       → individual post stats + comments
  - media/comments/   → paginated comments
Fallback: DOM scraping with time[datetime] for timestamps

NOTE: Instagram does not expose share/send counts publicly.
      Only the account owner can see those via Instagram Insights.
"""

import asyncio
import getpass
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from patchright.async_api import async_playwright, Page, BrowserContext

from db import init_db, save_post, save_comment, delete_post, get_stats

# ── Config ────────────────────────────────────────────────────────────────────

TARGET_USERNAME = "KonnectedMinds"
TARGET_PAGE     = f"https://www.instagram.com/{TARGET_USERNAME}/"
COOKIES_FILE    = Path(__file__).parent / "instagram_session.json"
SCROLL_ROUNDS   = 15
SCROLL_PAUSE    = 3000    # ms between scrolls
COMMENT_LIMIT   = 10

_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
DATE_FROM = _today if os.getenv("CI", "").lower() == "true" else datetime(2026, 1, 1)
DATE_TO   = None

HASHTAG_URLS = [
    "https://www.instagram.com/explore/tags/konnectedminds/",
    "https://www.instagram.com/explore/tags/konnected/",
    "https://www.instagram.com/explore/tags/konnectedmindsgh/",
]

# Must match brand in caption/author
BRAND_RE = re.compile(r"konnected.{0,5}minds?|konnectedminds", re.I)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_id(*parts) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode()).hexdigest()


def parse_timestamp(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(int(raw)).isoformat()
        except Exception:
            return ""
    raw = str(raw).strip()
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw)).isoformat()
        except Exception:
            pass
    if re.match(r'\d{4}-\d{2}-\d{2}', raw):
        return raw[:19]
    return raw


def in_date_range(timestamp_str: str) -> bool:
    if not timestamp_str:
        return True   # unknown date — keep until enrichment confirms otherwise
    try:
        dt = datetime.fromisoformat(timestamp_str[:19])
    except Exception:
        return True
    if DATE_FROM and dt < DATE_FROM:
        return False
    if DATE_TO and dt > DATE_TO:
        return False
    return True


def parse_count(val) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    text = str(val).strip().replace(",", "").replace(" ", "")
    try:
        if re.search(r'[Kk]$', text):
            return int(float(text[:-1]) * 1_000)
        if re.search(r'[Mm]$', text):
            return int(float(text[:-1]) * 1_000_000)
        nums = re.findall(r'\d+\.?\d*', text)
        return int(float(nums[0])) if nums else 0
    except Exception:
        return 0


def is_relevant(caption: str, author: str, source: str) -> bool:
    """Keep only content genuinely about Eddy's Pizza Ghana."""
    if source == "official_page":
        return True
    if author.lower() == TARGET_USERNAME.lower():
        return True
    return bool(BRAND_RE.search(caption))


# ── Parse Instagram API response nodes ────────────────────────────────────────

def parse_post_node(node: dict, source: str = "") -> dict:
    """
    Normalise a post node from any Instagram API response into our flat dict.
    Handles both profile-grid nodes and GraphQL post-detail nodes.
    """
    shortcode = node.get("shortcode", "")

    # Media type
    typename = node.get("__typename", "")
    if "Video" in typename or node.get("is_video"):
        media_type = "reel" if node.get("product_type") == "clips" else "video"
    elif "Sidecar" in typename or node.get("media_type") == 8:
        media_type = "carousel"
    else:
        media_type = "image"

    # Caption — two locations depending on API version
    caption = ""
    cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
    if cap_edges:
        caption = cap_edges[0].get("node", {}).get("text", "")
    if not caption:
        cap_edges2 = node.get("caption", {})
        if isinstance(cap_edges2, dict):
            caption = cap_edges2.get("text", "")
        elif isinstance(cap_edges2, str):
            caption = cap_edges2

    # Likes — multiple field names across API versions
    likes = parse_count(
        node.get("edge_liked_by", {}).get("count") or
        node.get("edge_media_preview_like", {}).get("count") or
        node.get("like_count") or
        node.get("likes", {}).get("count") or 0
    )

    # Comments count
    comments_count = parse_count(
        node.get("edge_media_to_comment", {}).get("count") or
        node.get("edge_media_to_parent_comment", {}).get("count") or
        node.get("comment_count") or
        node.get("comments", {}).get("count") or 0
    )

    # Views (videos/reels only)
    views = parse_count(
        node.get("video_view_count") or
        node.get("video_play_count") or
        node.get("play_count") or
        node.get("view_count") or 0
    )

    # Timestamp (Unix epoch → ISO)
    ts_raw = (node.get("taken_at_timestamp") or
              node.get("taken_at") or
              node.get("timestamp") or "")
    timestamp = parse_timestamp(ts_raw)

    # Author
    owner = node.get("owner", {}) or node.get("user", {})
    author_username = owner.get("username", "")
    author_name     = owner.get("full_name", "")

    # Post URL  — support both /p/ and /reel/
    if shortcode:
        post_url = f"https://www.instagram.com/p/{shortcode}/"
    else:
        post_url = node.get("permalink", "")

    hashtags = " ".join(re.findall(r'#\w+', caption))

    return {
        "post_id":         shortcode or make_id(post_url or caption[:40]),
        "author_username": author_username,
        "author_name":     author_name,
        "caption":         caption,
        "timestamp":       timestamp,
        "likes":           likes,
        "comments_count":  comments_count,
        "views":           views,
        "post_url":        post_url,
        "media_type":      media_type,
        "hashtags":        hashtags,
        "source":          source,
    }


def parse_comment_node(node: dict, post_id: str) -> dict:
    author = node.get("owner", {}).get("username", "") or node.get("user", {}).get("username", "")
    text   = node.get("text", "")
    return {
        "comment_id":      make_id(post_id, node.get("id", ""), text[:30]),
        "post_id":         post_id,
        "author_username": author,
        "text":            text,
        "likes":           parse_count(node.get("edge_liked_by", {}).get("count") or
                                       node.get("like_count") or 0),
        "timestamp":       parse_timestamp(node.get("created_at") or
                                           node.get("timestamp") or ""),
        "is_reply":        0,
        "parent_id":       None,
    }


# ── XHR response handler factory ─────────────────────────────────────────────

def make_response_handler(posts_store: dict, comments_store: dict, source: str):
    """
    Returns an async response handler that intercepts Instagram's internal API calls:
      - web_profile_info  → profile post grid (likes, views, timestamps, captions)
      - api/graphql       → individual post detail + comments
      - media/comments/   → paginated comments list
    """
    async def handle(response):
        url = response.url
        if response.status != 200:
            return
        ct = response.headers.get("content-type", "")
        # Be permissive — Instagram sometimes uses text/javascript or no content-type
        if ct and "html" in ct and "json" not in ct:
            return

        # Debug: log any Instagram API responses we see
        if any(k in url for k in ("web_profile_info", "graphql", "/api/v1/", "/media/")):
            print(f"  [XHR] {url[:120]}")

        try:
            # ── Profile API: web_profile_info ──────────────────────────────
            if "web_profile_info" in url:
                data = await response.json()
                user = (data.get("data", {}).get("user") or
                        data.get("graphql", {}).get("user") or {})

                # Posts grid
                for edge in user.get("edge_owner_to_timeline_media", {}).get("edges", []):
                    node = edge.get("node", {})
                    sc = node.get("shortcode", "")
                    if sc:
                        posts_store[sc] = parse_post_node(node, source)

                # Reels tab
                for edge in user.get("edge_felix_video_timeline", {}).get("edges", []):
                    node = edge.get("node", {})
                    sc = node.get("shortcode", "")
                    if sc:
                        p = parse_post_node(node, source)
                        p["media_type"] = "reel"
                        if sc not in posts_store or posts_store[sc].get("likes", 0) == 0:
                            posts_store[sc] = p
                return

            # ── Instagram v1 API: user feed ────────────────────────────────
            if "/api/v1/feed/user/" in url or "/api/v1/users/" in url:
                try:
                    data = await response.json()
                    items = data.get("items", [])
                    for item in items:
                        sc = item.get("code") or item.get("shortcode", "")
                        if sc:
                            posts_store[sc] = parse_post_node(item, source)
                except Exception as e:
                    print(f"  [XHR] v1 parse error: {e}")
                return

            # ── GraphQL: post detail + comments ───────────────────────────
            if "graphql" in url or "api/graphql" in url:
                data = await response.json()
                d = data.get("data", {})

                # Individual post detail
                media = (d.get("xdt_shortcode_media") or
                         d.get("shortcode_media") or
                         d.get("media"))
                if media and isinstance(media, dict):
                    sc = media.get("shortcode", "")
                    if sc:
                        parsed = parse_post_node(media, source or posts_store.get(sc, {}).get("source", ""))
                        # Merge: prefer higher counts
                        existing = posts_store.get(sc, {})
                        parsed["likes"]          = max(parsed["likes"],          existing.get("likes", 0))
                        parsed["comments_count"] = max(parsed["comments_count"], existing.get("comments_count", 0))
                        parsed["views"]          = max(parsed["views"],          existing.get("views", 0))
                        if not parsed["caption"] and existing.get("caption"):
                            parsed["caption"] = existing["caption"]
                        posts_store[sc] = parsed

                        # Comments from this response
                        for cmt_key in ("edge_media_to_parent_comment", "edge_media_to_comment"):
                            cmt_edges = media.get(cmt_key, {}).get("edges", [])
                            if cmt_edges:
                                comments_store[sc] = [
                                    parse_comment_node(e["node"], sc)
                                    for e in cmt_edges[:COMMENT_LIMIT]
                                ]
                                break
                    return

                # Hashtag feed
                hashtag = d.get("hashtag", {})
                if hashtag:
                    for feed_key in ("edge_hashtag_to_media", "edge_hashtag_to_top_posts",
                                     "edge_hashtag_to_content_advisory"):
                        for edge in hashtag.get(feed_key, {}).get("edges", []):
                            node = edge.get("node", {})
                            sc = node.get("shortcode", "")
                            if sc and sc not in posts_store:
                                posts_store[sc] = parse_post_node(node, source)
                    return

                # Paginated timeline (scroll events)
                for feed_key in ("edge_owner_to_timeline_media", "edge_web_feed_timeline",
                                 "edge_saved_media"):
                    edges = d.get(feed_key, {}).get("edges", [])
                    for edge in edges:
                        node = edge.get("node", {})
                        sc = node.get("shortcode", "")
                        if sc and sc not in posts_store:
                            posts_store[sc] = parse_post_node(node, source)

            # ── Media comments API ─────────────────────────────────────────
            if "/media/" in url and "/comments/" in url:
                data = await response.json()
                comments_list = data.get("comments", [])
                # Find matching post — extract media ID from URL
                m = re.search(r'/media/(\d+)/comments/', url)
                if m:
                    media_id = m.group(1)
                    # We store by media_id temporarily; resolved to shortcode later
                    key = f"mediaid_{media_id}"
                    comments_store[key] = [
                        parse_comment_node(c, key) for c in comments_list[:COMMENT_LIMIT]
                    ]

        except Exception as e:
            if any(k in url for k in ("web_profile_info", "graphql", "/api/v1/")):
                print(f"  [XHR] Parse error on {url[:80]}: {e}")

    return handle


# ── Session & login ───────────────────────────────────────────────────────────

async def save_session(context: BrowserContext):
    cookies = await context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    print(f"[Session] Saved → {COOKIES_FILE}")


async def load_session(context: BrowserContext) -> bool:
    if COOKIES_FILE.exists():
        try:
            cookies = json.loads(COOKIES_FILE.read_text())
            await context.add_cookies(cookies)
            print("[Session] Loaded saved session.")
            return True
        except Exception:
            pass
    return False


async def do_login(page: Page, context: BrowserContext, username: str, password: str):
    """Fill the login form with pre-collected credentials and save session."""
    await page.goto("https://www.instagram.com/accounts/login/",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    # Dismiss cookie / consent banners — try several variants
    for sel in [
        'button:has-text("Allow all cookies")',
        'button:has-text("Accept All")',
        'button:has-text("Allow essential and optional cookies")',
        'button:has-text("Only allow essential cookies")',
        '[data-testid="cookie-policy-manage-dialog-accept-button"]',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Find the username input — try several selectors
    user_input = None
    for sel in [
        'input[name="username"]',
        'input[aria-label*="username" i]',
        'input[aria-label*="Phone number, username" i]',
        '#loginForm input[type="text"]',
        'form input[type="text"]',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                user_input = sel
                print(f"  [Login] Found username field via: {sel}")
                break
        except Exception:
            continue

    if not user_input:
        # Last resort: wait up to 15s for any visible text input
        print("  [Login] Waiting for login form to appear...")
        try:
            await page.wait_for_selector('input[type="text"], input[type="email"]',
                                         state="visible", timeout=15000)
            user_input = 'input[type="text"]'
        except Exception:
            # Nothing found — let user handle it manually
            print("[Login] Could not find login form automatically.")
            input("[Login] Please log in manually in the browser, then press Enter > ")
            await page.wait_for_timeout(2000)
            await save_session(context)
            print("[Login] Session saved.")
            return

    await page.fill(user_input, username)
    await page.wait_for_timeout(600)

    # Password field
    pwd_input = None
    for sel in ['input[name="password"]', 'input[type="password"]']:
        try:
            el = await page.query_selector(sel)
            if el:
                pwd_input = sel
                break
        except Exception:
            continue
    if not pwd_input:
        pwd_input = 'input[type="password"]'

    await page.fill(pwd_input, password)
    await page.wait_for_timeout(600)

    # Submit — press Enter on the password field (most reliable)
    # Fall back to clicking various button selectors if Enter doesn't trigger navigation
    await page.press(pwd_input, "Enter")
    await page.wait_for_timeout(1500)

    # If still on login page, try clicking the button
    if "login" in page.url:
        for btn_sel in [
            'button[type="submit"]',
            'button:has-text("Log in")',
            'div[role="button"]:has-text("Log in")',
            '[type="submit"]',
        ]:
            try:
                el = await page.query_selector(btn_sel)
                if el and await el.is_visible():
                    await el.click()
                    break
            except Exception:
                continue

    print("[Login] Credentials submitted — waiting for Instagram to respond...")

    # Wait up to 20 seconds for redirect away from the login page
    try:
        await page.wait_for_function(
            "() => !window.location.href.includes('/accounts/login')",
            timeout=20000
        )
        await page.wait_for_timeout(2000)
    except Exception:
        # If 2FA or a challenge appears, let the user handle it manually
        print("[Login] Verification required (2FA or challenge) — complete it in the browser.")
        input("[Login] Press Enter once the home feed is visible > ")
        await page.wait_for_timeout(2000)

    print("[Login] Logged in successfully.")
    await save_session(context)


def prompt_credentials() -> tuple[str, str]:
    """Ask for Instagram credentials in the terminal. Call this BEFORE opening a browser."""
    print("\n" + "="*55)
    print("INSTAGRAM LOGIN")
    print("="*55)
    username = input("Instagram username: ").strip()
    password = getpass.getpass("Instagram password: ").strip()
    return username, password


async def ensure_logged_in(page: Page, context: BrowserContext,
                            username: str = "", password: str = ""):
    """
    Check login status:
      - No session file → use pre-collected credentials to log in
      - Session file exists but expired → use pre-collected credentials to log in again
      - Session valid → continue
    """
    if not COOKIES_FILE.exists():
        # First run — no saved session at all
        await do_login(page, context, username, password)
        return

    # Session file exists — verify it's still valid
    await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    if "accounts/login" in page.url or "challenge" in page.url:
        print("[Session] Saved session has expired. Logging in again...")
        await do_login(page, context, username, password)
    else:
        print("[Session] Session is valid — already logged in.")


# ── Navigation helpers ────────────────────────────────────────────────────────

async def goto(page: Page, url: str, label: str = ""):
    print(f"\n[Nav] {label or url[:80]}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        try:
            await page.goto(url, wait_until="commit", timeout=60000)
        except Exception:
            pass
    await page.wait_for_timeout(3000)
    await dismiss_dialogs(page)


async def dismiss_dialogs(page: Page):
    for sel in [
        'button:has-text("Not Now")',
        'button:has-text("Not now")',
        'button:has-text("Dismiss")',
        'button:has-text("Cancel")',
        '[aria-label="Close"]',
        'button:has-text("Allow all cookies")',
        'button:has-text("Accept All")',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            continue


# ── Post URL discovery via DOM ────────────────────────────────────────────────

async def collect_shortcodes_from_dom(page: Page) -> set:
    shortcodes = set()
    try:
        links = await page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
        for link in links:
            href = await link.get_attribute("href") or ""
            m = re.search(r'/(p|reel)/([A-Za-z0-9_-]+)/', href)
            if m:
                shortcodes.add(m.group(2))
    except Exception:
        pass
    return shortcodes


async def scroll_and_discover(page: Page, rounds: int, posts_store: dict) -> set:
    """Scroll the page to trigger lazy loading. Returns all discovered shortcodes."""
    all_codes: set = set()
    too_old_streak = 0

    for i in range(rounds):
        codes = await collect_shortcodes_from_dom(page)
        new_old = 0
        all_codes.update(codes)

        # Count how many newly discovered posts are too old
        for sc in codes:
            ts = posts_store.get(sc, {}).get("timestamp", "")
            if ts:
                try:
                    if DATE_FROM and datetime.fromisoformat(ts[:19]) < DATE_FROM:
                        new_old += 1
                except Exception:
                    pass

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2.5)")
        await page.wait_for_timeout(SCROLL_PAUSE)
        print(f"  scroll {i+1}/{rounds} — {len(all_codes)} posts found "
              f"({len(posts_store)} with stats)")

        if DATE_FROM and new_old > 3:
            too_old_streak += 1
        else:
            too_old_streak = 0
        if too_old_streak >= 2:
            print(f"  [DateFilter] Content older than {DATE_FROM.date()} — stopping early")
            break

    return all_codes


# ── Per-post enrichment ───────────────────────────────────────────────────────

async def extract_stats_from_page_json(page: Page) -> dict:
    """
    Extract post stats from Instagram's embedded JSON (script tags / window globals).
    Instagram embeds stats in multiple places — we scan them all.
    """
    try:
        result = await page.evaluate("""() => {
            // Try window.__additionalData (older Instagram)
            if (window.__additionalData) {
                for (const key of Object.keys(window.__additionalData)) {
                    const d = window.__additionalData[key];
                    const media = (d && d.data && d.data.shortcode_media) ||
                                  (d && d.graphql && d.graphql.shortcode_media);
                    if (media) return {
                        likes:          media.edge_liked_by?.count || media.like_count || 0,
                        comments_count: media.edge_media_to_parent_comment?.count ||
                                        media.edge_media_to_comment?.count ||
                                        media.comment_count || 0,
                        views:          media.video_view_count || media.video_play_count || 0,
                        timestamp:      media.taken_at_timestamp || '',
                        caption:        media.edge_media_to_caption?.edges?.[0]?.node?.text || '',
                        shortcode:      media.shortcode || '',
                    };
                }
            }
            // Scan <script type="application/json"> tags for embedded relay/GraphQL data
            for (const s of document.querySelectorAll('script[type="application/json"]')) {
                try {
                    const str = s.textContent;
                    if (!str || str.length < 100) continue;
                    const likeMatch  = str.match(/"edge_liked_by":\{"count":(\d+)\}/);
                    const tsMatch    = str.match(/"taken_at_timestamp":(\d+)/);
                    if (likeMatch || tsMatch) {
                        const viewMatch = str.match(/"video_view_count":(\d+)/);
                        const cmtMatch  = str.match(/"edge_media_to_parent_comment":\{"count":(\d+)\}/) ||
                                          str.match(/"edge_media_to_comment":\{"count":(\d+)\}/);
                        const scMatch   = str.match(/"shortcode":"([A-Za-z0-9_-]+)"/);
                        const capMatch  = str.match(/"text":"((?:[^"\\]|\\.)*)"/);
                        return {
                            likes:          likeMatch  ? parseInt(likeMatch[1])  : 0,
                            comments_count: cmtMatch   ? parseInt(cmtMatch[1])   : 0,
                            views:          viewMatch  ? parseInt(viewMatch[1])  : 0,
                            timestamp:      tsMatch    ? parseInt(tsMatch[1])    : '',
                            shortcode:      scMatch    ? scMatch[1]              : '',
                            caption:        capMatch   ? capMatch[1]             : '',
                        };
                    }
                } catch(e) {}
            }
            return null;
        }""")
        if not result:
            return {}
        # Convert Unix timestamp to ISO
        ts_val = result.get("timestamp", "")
        if ts_val and str(ts_val).isdigit():
            result["timestamp"] = datetime.fromtimestamp(int(ts_val)).isoformat()
        return result
    except Exception as e:
        print(f"    [PageJSON] Error: {e}")
        return {}


async def enrich_post_page(page: Page, shortcode: str,
                            posts_store: dict, comments_store: dict):
    """
    Visit the post page. The XHR handler will fire and capture stats automatically.
    If XHR misses, fall back to DOM timestamp.
    """
    url = f"https://www.instagram.com/p/{shortcode}/"
    await goto(page, url, f"post /{shortcode}/")
    await page.wait_for_timeout(2500)

    # Strategy 1: page JSON extraction (most reliable)
    page_stats = await extract_stats_from_page_json(page)
    if page_stats and (page_stats.get("likes", 0) > 0 or page_stats.get("timestamp")):
        existing = posts_store.get(shortcode, {"post_id": shortcode, "post_url": url,
                                               "source": ""})
        for k, v in page_stats.items():
            if v:
                existing[k] = v
        posts_store[shortcode] = existing
        print(f"    [PageJSON] likes={page_stats.get('likes',0)} "
              f"views={page_stats.get('views',0)} ts={page_stats.get('timestamp','')[:10]}")

    # DOM fallback if still no stats
    if shortcode not in posts_store or posts_store[shortcode].get("likes", 0) == 0:
        partial = posts_store.get(shortcode, {
            "post_id": shortcode, "post_url": url,
            "likes": 0, "comments_count": 0, "views": 0,
        })
        # Timestamp
        try:
            time_el = await page.query_selector("time[datetime]")
            if time_el:
                partial["timestamp"] = parse_timestamp(
                    await time_el.get_attribute("datetime") or "")
        except Exception:
            pass
        # Caption
        if not partial.get("caption"):
            try:
                for sel in ['h1', 'div[data-testid="post-comment-root"] span',
                            'article span[dir="auto"]']:
                    el = await page.query_selector(sel)
                    if el:
                        t = (await el.inner_text()).strip()
                        if t and len(t) > 5:
                            partial["caption"] = t
                            break
            except Exception:
                pass
        # Like count from DOM aria-label
        if partial.get("likes", 0) == 0:
            try:
                like_section = await page.query_selector(
                    'section[class*="like"], button[aria-label*="like"], '
                    'span[aria-label*="like"], div[aria-label*="like"]'
                )
                if like_section:
                    text = await like_section.inner_text()
                    m = re.search(r'([\d,]+)', text)
                    if m:
                        partial["likes"] = parse_count(m.group(1))
            except Exception:
                pass
        posts_store[shortcode] = partial


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run(scrape_comments_flag: bool = True):
    init_db()
    all_posts: dict    = {}   # shortcode → post dict
    all_comments: dict = {}   # shortcode → list of comment dicts

    # Collect credentials BEFORE opening the browser so the user is prompted in
    # the terminal first (and password is hidden). Skip if session already saved.
    username = password = ""
    if not COOKIES_FILE.exists():
        username, password = prompt_credentials()

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
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()

        # Session + login
        await load_session(context)
        await ensure_logged_in(page, context, username, password)

        # ── Helper: filter & save posts to DB ─────────────────────────────
        def commit_posts(posts_dict: dict, source: str):
            saved = dropped = out_of_range = 0
            for sc, post in posts_dict.items():
                ts = post.get("timestamp", "")
                if ts and not in_date_range(ts):
                    out_of_range += 1
                    continue
                caption  = post.get("caption", "")
                author   = post.get("author_username", "")
                is_stub  = not caption and not ts  # stub: no real data yet
                # Keep stubs (will be validated after enrichment fills real data)
                # Keep official page posts always
                # Drop hashtag posts only when we have real caption/author and they don't match
                if not is_stub and not is_relevant(caption, author, source):
                    dropped += 1
                    continue
                effective_source = post.get("source") or source
                post["source"] = effective_source
                save_post(post)
                all_posts[sc] = post
                saved += 1
            if out_of_range:
                print(f"  [DateFilter] Dropped {out_of_range} outside date range")
            if dropped:
                print(f"  [Filter] Kept {saved}, dropped {dropped} off-topic")
            else:
                print(f"  [Saved] {saved} posts")

        # ── SECTION 1: Official profile ────────────────────────────────────
        print("\n" + "="*55)
        print("SECTION 1: Official Instagram page")
        print("="*55)

        profile_posts: dict    = {}
        profile_comments: dict = {}
        handler = make_response_handler(profile_posts, profile_comments, "official_page")
        page.on("response", handler)

        await goto(page, TARGET_PAGE, f"@{TARGET_USERNAME}")
        try:
            await page.wait_for_selector('article, main', timeout=15000)
        except Exception:
            print("  [!] Profile page took long to load")

        dom_codes = await scroll_and_discover(page, rounds=SCROLL_ROUNDS, posts_store=profile_posts)

        # Add stub entries for any DOM-discovered posts not captured via XHR
        # so the enrichment section will visit each and fill in the stats
        for sc in dom_codes:
            if sc not in profile_posts:
                profile_posts[sc] = {
                    "post_id":         sc,
                    "post_url":        f"https://www.instagram.com/p/{sc}/",
                    "author_username": TARGET_USERNAME,
                    "author_name":     "",
                    "caption":         "",
                    "timestamp":       "",
                    "likes":           0,
                    "comments_count":  0,
                    "views":           0,
                    "media_type":      "image",
                    "hashtags":        "",
                    "source":          "official_page",
                }

        page.remove_listener("response", handler)
        print(f"  [XHR] Captured {len(profile_posts)} posts (XHR + DOM stubs)")
        commit_posts(profile_posts, "official_page")
        all_comments.update(profile_comments)

        # ── SECTION 2: Hashtag pages ───────────────────────────────────────
        for tag_url in HASHTAG_URLS:
            tag = tag_url.rstrip("/").split("/")[-1]
            print("\n" + "="*55)
            print(f"SECTION 2: Hashtag #{tag}")
            print("="*55)

            tag_posts: dict    = {}
            tag_comments: dict = {}
            handler = make_response_handler(tag_posts, tag_comments, f"hashtag_{tag}")
            page.on("response", handler)

            await goto(page, tag_url, f"#{tag}")
            try:
                await page.wait_for_selector('article, main', timeout=10000)
            except Exception:
                pass

            tag_codes = await scroll_and_discover(page, rounds=8, posts_store=tag_posts)

            # Add stubs for DOM-discovered hashtag posts not captured via XHR
            for sc in tag_codes:
                if sc not in tag_posts:
                    tag_posts[sc] = {
                        "post_id":         sc,
                        "post_url":        f"https://www.instagram.com/p/{sc}/",
                        "author_username": "",
                        "author_name":     "",
                        "caption":         "",
                        "timestamp":       "",
                        "likes":           0,
                        "comments_count":  0,
                        "views":           0,
                        "media_type":      "image",
                        "hashtags":        "",
                        "source":          f"hashtag_{tag}",
                    }

            page.remove_listener("response", handler)
            print(f"  [XHR] Captured {len(tag_posts)} posts from #{tag} (XHR + DOM stubs)")
            # For hashtag stubs (empty caption/author), defer relevance check to enrichment
            commit_posts(tag_posts, f"hashtag_{tag}")
            all_comments.update(tag_comments)

        # ── Save session ───────────────────────────────────────────────────
        await save_session(context)

        # ── SECTION 3: Enrich posts missing stats ─────────────────────────
        needs_enrich = [
            sc for sc, p in all_posts.items()
            if p.get("likes", 0) + p.get("views", 0) == 0 and p.get("post_url")
        ]
        if needs_enrich:
            print("\n" + "="*55)
            print(f"SECTION 3: Enriching {len(needs_enrich)} posts missing stats")
            print("="*55)

            enrich_posts: dict    = {}
            enrich_comments: dict = {}
            handler = make_response_handler(enrich_posts, enrich_comments, "")
            page.on("response", handler)

            for i, sc in enumerate(needs_enrich):
                print(f"[{i+1}/{len(needs_enrich)}] {sc}")
                await enrich_post_page(page, sc, enrich_posts, enrich_comments)

                if sc in enrich_posts:
                    merged = {**all_posts[sc], **{
                        k: v for k, v in enrich_posts[sc].items()
                        if v or v == 0
                    }}
                    # Preserve original source
                    src = all_posts[sc].get("source") or merged.get("source", "")
                    merged["source"] = src
                    ts = merged.get("timestamp", "")
                    if ts and not in_date_range(ts):
                        delete_post(sc)
                        del all_posts[sc]
                        print(f"    [DateFilter] Removed {sc} — real date outside range")
                    elif src.startswith("hashtag_") and not is_relevant(
                            merged.get("caption", ""), merged.get("author_username", ""), src):
                        # Hashtag stub turned out irrelevant after enrichment
                        delete_post(sc)
                        if sc in all_posts:
                            del all_posts[sc]
                        print(f"    [Filter] Removed {sc} — irrelevant after enrichment")
                    else:
                        save_post(merged)
                        all_posts[sc] = merged

                if sc in enrich_comments and sc not in all_comments:
                    all_comments[sc] = enrich_comments[sc]
                await page.wait_for_timeout(2000)

            page.remove_listener("response", handler)

        # ── SECTION 4: Comments ────────────────────────────────────────────
        if scrape_comments_flag:
            print("\n" + "="*55)
            print("SECTION 4: Saving comments")
            print("="*55)

            # Save comments already captured via XHR
            saved_c = 0
            for sc, comments in all_comments.items():
                if sc in all_posts:
                    for c in comments[:COMMENT_LIMIT]:
                        save_comment(c)
                        saved_c += 1
            print(f"  Saved {saved_c} XHR-captured comments for {len(all_comments)} posts")

            # For posts with comments but none captured yet, visit the post page
            posts_need_comments = [
                sc for sc in all_posts
                if sc not in all_comments
                and all_posts[sc].get("comments_count", 0) > 0
            ][:50]  # cap at 50 to keep runtime reasonable

            if posts_need_comments:
                print(f"  Fetching comments for {len(posts_need_comments)} posts...")
                cmt_store: dict = {}
                handler = make_response_handler({}, cmt_store, "")
                page.on("response", handler)

                for i, sc in enumerate(posts_need_comments):
                    print(f"  [{i+1}/{len(posts_need_comments)}] {sc}")
                    await goto(page, f"https://www.instagram.com/p/{sc}/", f"comments {sc}")
                    await page.wait_for_timeout(2500)
                    if sc in cmt_store:
                        for c in cmt_store[sc][:COMMENT_LIMIT]:
                            save_comment(c)
                    await page.wait_for_timeout(1500)

                page.remove_listener("response", handler)

        await browser.close()

    stats = get_stats()
    print("\n" + "="*55)
    print("SCRAPE COMPLETE")
    print(f"  Posts collected:    {stats['total_posts']}")
    print(f"  Comments collected: {stats['total_comments']}")
    print(f"  Total likes:        {stats['total_likes']}")
    print(f"  Total views:        {stats['total_views']}")
    print("="*55)
