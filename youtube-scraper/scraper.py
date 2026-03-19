"""
YouTube scraper — no API key required.
Uses Patchright browser automation + YouTube's internal ytInitialData JSON
and XHR interception of /youtubei/v1/next for comments.
"""

import json
import re
import asyncio
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from patchright.async_api import async_playwright, Page, BrowserContext

# YouTube's embedded public API key (built into their web app, not a personal key)
YT_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
YT_NEXT_URL = "https://www.youtube.com/youtubei/v1/next"
YT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-YouTube-Client-Name": "1",
    "X-YouTube-Client-Version": "2.20240101.00.00",
    "Origin": "https://www.youtube.com",
    "Referer": "https://www.youtube.com/",
}
YT_CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": "2.20240101.00.00",
        "hl": "en",
        "gl": "US",
    }
}

# ── Configuration ─────────────────────────────────────────────────────────────

_today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
DATE_FROM = _today_utc if os.getenv("CI", "").lower() == "true" else datetime(2024, 1, 1, tzinfo=timezone.utc)
DATE_TO   = datetime.now(timezone.utc)

# Specific video URLs or IDs to scrape
TARGET_VIDEOS: list = [
    # "https://www.youtube.com/watch?v=VIDEO_ID",
]

# Channel handles/URLs — scrapes all their videos
TARGET_CHANNELS: list = [
    "@KonnectedMinds",
]

MAX_COMMENTS_PER_VIDEO = 500    # 0 = unlimited
INCLUDE_REPLIES        = True
CHANNEL_SCROLL_ROUNDS  = 15     # how many times to scroll channel page to find videos
CHANNEL_VIDEO_LIMIT    = 50     # max videos to scrape per channel (0 = all)
COMMENT_SCROLL_ROUNDS  = 30     # how many times to scroll video page to load comments
HEADLESS               = os.getenv("CI", "").lower() == "true"


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_video_id(url_or_id: str) -> str:
    patterns = [r"(?:v=|youtu\.be/|/embed/|/v/|/shorts/)([A-Za-z0-9_-]{11})"]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    clean = url_or_id.strip().split("?")[0]
    if re.match(r"^[A-Za-z0-9_-]{11}$", clean):
        return clean
    return url_or_id.strip()


def parse_count(text) -> int:
    """Parse '1.2K', '3.4M', '1,234' → int"""
    if not text:
        return 0
    text = str(text).strip()
    if not text:
        return 0
    text = text.replace(",", "")
    m = re.search(r"([\d.]+)\s*([KkMmBb]?)", text)
    if not m:
        return 0
    try:
        num  = float(m.group(1))
        mult = m.group(2).upper()
        if   mult == "K": num *= 1_000
        elif mult == "M": num *= 1_000_000
        elif mult == "B": num *= 1_000_000_000
        return int(num)
    except Exception:
        return 0


def parse_relative_time(rel: str) -> str:
    """Convert 'X units ago' → approximate ISO timestamp string."""
    if not rel:
        return ""
    rel = rel.lower().strip()
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)", rel)
    if not m:
        return now.isoformat()
    n, unit = int(m.group(1)), m.group(2)
    if   unit == "second": delta = timedelta(seconds=n)
    elif unit == "minute": delta = timedelta(minutes=n)
    elif unit == "hour":   delta = timedelta(hours=n)
    elif unit == "day":    delta = timedelta(days=n)
    elif unit == "week":   delta = timedelta(weeks=n)
    elif unit == "month":  delta = timedelta(days=n * 30)
    else:                  delta = timedelta(days=n * 365)
    return (now - delta).isoformat()


def in_date_range(ts: str) -> bool:
    if not ts:
        return True
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return DATE_FROM <= dt <= DATE_TO
    except Exception:
        return True


def safe_get(obj: dict, *keys):
    """Safely navigate nested dicts."""
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, {})
        elif isinstance(obj, list) and isinstance(k, int):
            obj = obj[k] if k < len(obj) else {}
        else:
            return None
    return obj or None


# ── Page script extraction ────────────────────────────────────────────────────

async def extract_page_data(page: Page) -> dict:
    """
    Read ytInitialData + ytInitialPlayerResponse from the page's script tags.
    Returns a normalized video details dict.
    """
    # Wait until YouTube's JS globals are populated
    try:
        await page.wait_for_function(
            "() => !!(window.ytInitialPlayerResponse?.videoDetails?.videoId)",
            timeout=12000,
        )
    except Exception:
        pass

    try:
        result = await page.evaluate("""() => {
            // Try window globals first; fall back to parsing script tag text
            let pr = window.ytInitialPlayerResponse || null;
            let id = window.ytInitialData || null;

            if (!pr || !pr.videoDetails) {
                for (const s of document.querySelectorAll('script:not([src])')) {
                    const t = s.textContent;
                    if (!pr && t.includes('ytInitialPlayerResponse')) {
                        try {
                            const m = t.match(/ytInitialPlayerResponse\s*=\s*(\{.+\})\s*;/s);
                            if (m) pr = JSON.parse(m[1]);
                        } catch(e) {}
                    }
                    if (!id && t.includes('ytInitialData')) {
                        try {
                            const m = t.match(/ytInitialData\s*=\s*(\{.+\})\s*;/s);
                            if (m) id = JSON.parse(m[1]);
                        } catch(e) {}
                    }
                    if (pr && id) break;
                }
            }

            pr = pr || {};
            id = id || {};

            const vd = pr.videoDetails || {};

            // View count from player response
            let viewCount = parseInt(vd.viewCount || '0') || 0;

            // Like count — try every pattern YouTube has used
            let likeCount = 0;
            try {
                const str = JSON.stringify(id);
                const parseK = raw => {
                    raw = raw.replace(/,/g,'').trim();
                    const last = raw.slice(-1).toUpperCase();
                    const num  = parseFloat(raw);
                    if (last==='K') return Math.round(num*1000);
                    if (last==='M') return Math.round(num*1000000);
                    if (last==='B') return Math.round(num*1000000000);
                    return parseInt(raw) || 0;
                };
                // Pattern 1: accessibilityText with " likes" anywhere (handles "83K likes. Like")
                let m = str.match(/"accessibilityText":"([\d,\.]+[KkMmBb]?) likes/);
                if (m) { likeCount = parseK(m[1]); }
                // Pattern 2: label with " likes"
                if (!likeCount) {
                    m = str.match(/"label":"([\d,\.]+[KkMmBb]?) likes/);
                    if (m) likeCount = parseK(m[1]);
                }
                // Pattern 3: title field on the like button (e.g. "83K")
                if (!likeCount) {
                    m = str.match(/"likeButtonViewModel"[^}]{0,400}"title":"([\d,\.]+[KkMmBb]?)"/);
                    if (m) likeCount = parseK(m[1]);
                }
                // Pattern 4: direct likeCount field (older microformat)
                if (!likeCount) {
                    m = str.match(/"likeCount":"(\d+)"/);
                    if (m) likeCount = parseInt(m[1]) || 0;
                }
            } catch(e) {}

            // Published date
            let publishedAt = '';
            try {
                const micro = pr.microformat?.playerMicroformatRenderer || {};
                publishedAt = micro.publishDate || micro.uploadDate || '';
            } catch(e) {}

            // Description
            const desc = vd.shortDescription || '';

            // Tags
            let tags = [];
            try {
                tags = pr.microformat?.playerMicroformatRenderer?.keywords || [];
            } catch(e) {}

            // Channel
            const channelId   = vd.channelId || '';
            const channelName = vd.author    || '';

            // Thumbnail
            let thumbnail = '';
            try {
                const thumbs = vd.thumbnail?.thumbnails || [];
                thumbnail = thumbs[thumbs.length-1]?.url || '';
            } catch(e) {}

            // Comment count — read from engagementPanels header (same place YouTube shows it)
            let commentCount = 0;
            try {
                const panels = id.engagementPanels || [];
                for (const panel of panels) {
                    const r = panel.engagementPanelSectionListRenderer || {};
                    const isComments = r.panelIdentifier === 'comment-item-section' ||
                        (r.header?.engagementPanelTitleHeaderRenderer?.title?.runs || [])
                            .some(x => x.text === 'Comments');
                    if (!isComments) continue;
                    // contextualInfo holds the count e.g. "1,234"
                    const runs = r.header?.engagementPanelTitleHeaderRenderer
                                          ?.contextualInfo?.runs || [];
                    const countText = runs.map(x => x.text || '').join('').replace(/,/g,'').trim();
                    if (countText) {
                        const last = countText.slice(-1).toUpperCase();
                        const num  = parseFloat(countText);
                        if      (last === 'K') commentCount = Math.round(num * 1000);
                        else if (last === 'M') commentCount = Math.round(num * 1000000);
                        else                   commentCount = parseInt(countText) || 0;
                    }
                    break;
                }
            } catch(e) {}

            // Duration
            const duration = vd.lengthSeconds ? parseInt(vd.lengthSeconds) : 0;

            // Comment continuation token — walk engagementPanels properly
            let commentToken = '';
            try {
                const panels = id.engagementPanels || [];
                for (const panel of panels) {
                    const r = panel.engagementPanelSectionListRenderer || {};
                    const isComments = r.panelIdentifier === 'comment-item-section' ||
                        (r.header?.engagementPanelTitleHeaderRenderer?.title?.runs || [])
                            .some(x => x.text === 'Comments');
                    if (!isComments) continue;
                    const contents = r.content?.sectionListRenderer?.contents || [];
                    for (const sec of contents) {
                        for (const item of sec.itemSectionRenderer?.contents || []) {
                            const t = item.continuationItemRenderer
                                         ?.continuationEndpoint
                                         ?.continuationCommand?.token;
                            if (t) { commentToken = t; break; }
                        }
                        if (commentToken) break;
                    }
                    if (commentToken) break;
                }
            } catch(e) {}

            // Real API key from ytcfg (more reliable than hardcoded key)
            let innertubeKey = '';
            try { innertubeKey = window.ytcfg?.data_?.INNERTUBE_API_KEY || ''; } catch(e) {}

            // Visitor data for auth context
            let visitorData = '';
            try { visitorData = window.ytcfg?.data_?.VISITOR_DATA || ''; } catch(e) {}

            // Client version
            let clientVersion = '';
            try { clientVersion = window.ytcfg?.data_?.INNERTUBE_CLIENT_VERSION || '2.20240101.00.00'; } catch(e) {}

            return {
                video_id:        vd.videoId  || '',
                title:           vd.title    || '',
                description:     desc.slice(0, 3000),
                channel_id:      channelId,
                channel_name:    channelName,
                published_at:    publishedAt,
                duration:        duration,
                view_count:      viewCount,
                like_count:      likeCount,
                comment_count:   commentCount,
                tags:            tags.join(','),
                thumbnail_url:   thumbnail,
                comment_token:   commentToken,
                innertube_key:   innertubeKey,
                visitor_data:    visitorData,
                client_version:  clientVersion,
            };
        }""")
        return result or {}
    except Exception as e:
        print(f"  [PageData] Error: {e}")
        return {}


# ── Direct comment API (no browser scrolling needed) ─────────────────────────

def fetch_comments_api(continuation_token: str, video_id: str,
                       max_count: int = 0,
                       api_key: str = "", visitor_data: str = "",
                       client_version: str = "") -> list:
    """
    Fetch comments by POSTing directly to YouTube's internal /next API.
    Uses the continuation token extracted from the page's ytInitialData.
    Much more reliable than XHR interception.
    """
    comments  = []
    token     = continuation_token
    page_num  = 0

    while token:
        page_num += 1
        try:
            key = api_key or YT_API_KEY
            ctx = {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": client_version or "2.20240101.00.00",
                    "hl": "en", "gl": "US",
                    **({"visitorData": visitor_data} if visitor_data else {}),
                }
            }
            resp = requests.post(
                YT_NEXT_URL,
                params={"key": key},
                headers=YT_HEADERS,
                json={"context": ctx, "continuation": token},
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [API] Comment fetch error (page {page_num}): {e}")
            break

        new = extract_comments_from_continuation(data, video_id)
        comments.extend(new)
        print(f"  [API] Page {page_num}: +{len(new)} comments (total {len(comments)})")

        if max_count and len(comments) >= max_count:
            comments = comments[:max_count]
            break

        # Find next page token
        token = _find_next_token(data)

    return comments


def _find_next_token(data: dict) -> str:
    """Extract the next continuation token from a /next response."""
    # Walk onResponseReceivedEndpoints continuation items
    for endpoint in data.get("onResponseReceivedEndpoints", []):
        for key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
            items = (endpoint.get(key) or {}).get("continuationItems", [])
            for item in items:
                token = (safe_get(item, "continuationItemRenderer",
                                  "continuationEndpoint", "continuationCommand", "token") or
                         safe_get(item, "continuationItemRenderer",
                                  "button", "buttonRenderer", "command",
                                  "continuationCommand", "token"))
                if token:
                    return token
    return ""


# ── Comment XHR interception (fallback) ──────────────────────────────────────

def parse_comment_renderer(item: dict, video_id: str,
                            is_reply: bool = False, parent_id: str = "") -> dict | None:
    """Extract a single comment from a commentRenderer dict."""
    cr = item.get("commentRenderer", {})
    if not cr:
        return None

    comment_id = cr.get("commentId", "")
    if not comment_id:
        return None

    # Text
    text_runs = safe_get(cr, "contentText", "runs") or []
    text = "".join(r.get("text", "") for r in text_runs if isinstance(r, dict))

    # Author
    author_runs = safe_get(cr, "authorText", "runs") or []
    author = "".join(r.get("text", "") for r in author_runs if isinstance(r, dict))

    author_ch_id = safe_get(cr, "authorEndpoint", "browseEndpoint", "browseId") or ""

    # Likes (try multiple paths YouTube has used over time)
    like_text = (safe_get(cr, "voteCount", "simpleText") or
                 safe_get(cr, "voteCount", "accessibility", "accessibilityData", "label") or
                 safe_get(cr, "likeCount") or
                 safe_get(cr, "actionButtons", "commentActionButtonsRenderer",
                          "likeButton", "toggleButtonRenderer",
                          "defaultText", "accessibility", "accessibilityData", "label") or "")
    likes = parse_count(like_text)

    # Published time (relative)
    time_runs = safe_get(cr, "publishedTimeText", "runs") or []
    rel_time  = "".join(r.get("text", "") for r in time_runs if isinstance(r, dict))
    published_at = parse_relative_time(rel_time)

    # Reply count
    reply_count = cr.get("replyCount", 0) or 0

    return {
        "comment_id":        comment_id,
        "video_id":          video_id,
        "author_name":       author,
        "author_channel_id": author_ch_id,
        "text":              text,
        "likes":             likes,
        "published_at":      published_at,
        "updated_at":        "",
        "is_reply":          is_reply,
        "parent_id":         parent_id,
        "reply_count":       reply_count,
    }


def extract_comments_from_continuation(data: dict, video_id: str) -> list:
    """
    Parse a /youtubei/v1/next response to extract comments and reply threads.
    Returns list of comment dicts.
    """
    comments = []

    # Find continuation items from various response shapes
    items = []
    for endpoint in data.get("onResponseReceivedEndpoints", []):
        for key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
            cont_items = safe_get(endpoint, key, "continuationItems")
            if cont_items and isinstance(cont_items, list):
                items.extend(cont_items)

    # Also check frameworkUpdates path (newer YouTube)
    for update in data.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []):
        payload = update.get("payload", {})
        comment = payload.get("commentEntityPayload", {})
        if comment:
            cid = comment.get("properties", {}).get("commentId", "")
            text = comment.get("properties", {}).get("content", {}).get("content", "")
            author = comment.get("author", {}).get("displayName", "")
            toolbar = comment.get("toolbar", {})
            likes_raw = toolbar.get("likeCountNotliked") or toolbar.get("likeCountLiked") or 0
            ts = comment.get("properties", {}).get("publishedTime", "")
            if cid:
                comments.append({
                    "comment_id":        cid,
                    "video_id":          video_id,
                    "author_name":       author,
                    "author_channel_id": "",
                    "text":              text,
                    "likes":             parse_count(str(likes_raw)),
                    "published_at":      parse_relative_time(ts),
                    "updated_at":        "",
                    "is_reply":          False,
                    "parent_id":         "",
                    "reply_count":       0,
                })

    for item in items:
        if not isinstance(item, dict):
            continue

        # Top-level comment thread
        if "commentThreadRenderer" in item:
            thread = item["commentThreadRenderer"]
            top = thread.get("comment", {})
            c = parse_comment_renderer(top, video_id)
            if c:
                c["reply_count"] = c.get("reply_count", 0)
                comments.append(c)

            # Inline replies
            if INCLUDE_REPLIES:
                replies_cont = safe_get(thread, "replies", "commentRepliesRenderer", "contents")
                if replies_cont:
                    for ri in replies_cont:
                        if "commentRenderer" in ri:
                            r = parse_comment_renderer({"commentRenderer": ri["commentRenderer"]},
                                                       video_id, is_reply=True, parent_id=c["comment_id"])
                            if r:
                                comments.append(r)

    return comments


def make_comment_handler(all_comments: list, video_id: str):
    """Returns an async XHR handler that captures YouTube comment responses."""
    async def handle(response):
        url = response.url
        # Log all youtubei API calls so we can see what's happening
        if "youtubei" in url:
            print(f"  [XHR] {url.split('?')[0]}")
        if "/youtubei/v1/next" not in url:
            return
        if response.status != 200:
            return
        try:
            data = await response.json()
            new_comments = extract_comments_from_continuation(data, video_id)
            if new_comments:
                all_comments.extend(new_comments)
                print(f"  [XHR] +{len(new_comments)} comments (total {len(all_comments)})")
        except Exception as e:
            print(f"  [XHR] Parse error: {e}")
    return handle


# ── Video page scraper ────────────────────────────────────────────────────────

async def scrape_video(page: Page, url_or_id: str) -> tuple:
    """
    Scrape a single video. Returns (video_details_dict, comments_list).
    Strategy:
      1. Load page, read ytInitialData/ytInitialPlayerResponse for stats
      2. Extract comment continuation token from page data
      3. POST directly to YouTube's internal API to fetch comments (reliable)
      4. Fall back to XHR interception if token extraction fails
    """
    vid = extract_video_id(url_or_id)
    url = f"https://www.youtube.com/watch?v={vid}"

    # XHR fallback handler (used if direct API fails)
    xhr_comments: list = []
    handler = make_comment_handler(xhr_comments, vid)
    page.on("response", handler)

    print(f"  [Nav] {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    # Get video metadata + comment continuation token from page
    details = await extract_page_data(page)
    details["video_id"] = vid
    details["post_url"] = url

    # ── Comments via direct API (primary method) ──────────────────────────
    all_comments = []
    comment_token  = details.pop("comment_token",  "")
    innertube_key  = details.pop("innertube_key",  "")
    visitor_data   = details.pop("visitor_data",   "")
    client_version = details.pop("client_version", "")

    print(f"  [Token] {'Found ✓' if comment_token else 'Not found — will use XHR scroll'}")
    if innertube_key:
        print(f"  [Key]   Using page key: {innertube_key[:20]}...")

    if comment_token:
        print(f"  [API] Fetching comments...")
        all_comments = fetch_comments_api(
            comment_token, vid,
            max_count=MAX_COMMENTS_PER_VIDEO,
            api_key=innertube_key,
            visitor_data=visitor_data,
            client_version=client_version,
        )
    else:
        # Token not found — scroll to trigger XHR, collect all pages
        print(f"  [XHR] No token found, scrolling to trigger comment load...")
        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        await page.wait_for_timeout(2500)
        prev_count = 0
        for i in range(COMMENT_SCROLL_ROUNDS):
            await page.evaluate("window.scrollBy(0, 1200)")
            await page.wait_for_timeout(1500)
            if MAX_COMMENTS_PER_VIDEO and len(xhr_comments) >= MAX_COMMENTS_PER_VIDEO:
                break
            # If XHR gave us new comments, try to get next page token and fetch via API
            if len(xhr_comments) > prev_count:
                print(f"  scroll {i+1} — {len(xhr_comments)} comments so far")
                prev_count = len(xhr_comments)
        all_comments = xhr_comments[:MAX_COMMENTS_PER_VIDEO] if MAX_COMMENTS_PER_VIDEO else xhr_comments

        # If we got any XHR comments, try to continue pagination via direct API
        if all_comments:
            print(f"  [XHR] Got {len(all_comments)} via scroll — trying API pagination...")
            fresh_data   = await extract_page_data(page)
            fresh_token  = fresh_data.pop("comment_token",  "")
            fresh_key    = fresh_data.pop("innertube_key",  "") or innertube_key
            fresh_vis    = fresh_data.pop("visitor_data",   "") or visitor_data
            fresh_cv     = fresh_data.pop("client_version", "") or client_version
            if fresh_token:
                extra = fetch_comments_api(
                    fresh_token, vid,
                    max_count=MAX_COMMENTS_PER_VIDEO - len(all_comments) if MAX_COMMENTS_PER_VIDEO else 0,
                    api_key=fresh_key, visitor_data=fresh_vis, client_version=fresh_cv,
                )
                all_comments.extend(extra)

    page.remove_listener("response", handler)

    # Deduplicate
    seen = set()
    unique = []
    for c in all_comments:
        if c["comment_id"] not in seen:
            seen.add(c["comment_id"])
            unique.append(c)

    return details, unique


# ── Channel info ──────────────────────────────────────────────────────────────

async def extract_channel_info(page: Page, channel_ref: str) -> dict:
    """Extract channel_id, name, subscriber_count, total_videos from channel page."""
    try:
        result = await page.evaluate("""() => {
            const id = window.ytInitialData || {};
            const header = id.header?.c4TabbedHeaderRenderer ||
                           id.header?.pageHeaderRenderer?.content?.pageHeaderViewModel || {};
            const meta   = id.metadata?.channelMetadataRenderer || {};

            // Channel ID
            const channelId = meta.externalId ||
                              id.header?.c4TabbedHeaderRenderer?.channelId || '';

            // Channel name
            const name = meta.title ||
                         id.header?.c4TabbedHeaderRenderer?.title || '';

            // Subscriber count text e.g. "12.3K subscribers"
            const subText = (id.header?.c4TabbedHeaderRenderer?.subscriberCountText?.simpleText ||
                             id.header?.c4TabbedHeaderRenderer?.subscriberCountText?.runs?.[0]?.text || '');
            let subs = 0;
            if (subText) {
                const m = subText.match(/([\d,\.]+)\s*([KkMmBb]?)/);
                if (m) {
                    const num  = parseFloat(m[1].replace(/,/g,''));
                    const last = m[2].toUpperCase();
                    if      (last==='K') subs = Math.round(num*1000);
                    else if (last==='M') subs = Math.round(num*1000000);
                    else if (last==='B') subs = Math.round(num*1000000000);
                    else                 subs = parseInt(num) || 0;
                }
            }

            // Total video count
            let totalVideos = 0;
            const tabs = id.contents?.twoColumnBrowseResultsRenderer?.tabs || [];
            for (const tab of tabs) {
                const runs = tab.tabRenderer?.content?.richGridRenderer
                               ?.header?.feedFilterChipBarRenderer
                               ?.contents?.[0]?.chipCloudChipRenderer
                               ?.text?.runs || [];
                // fallback: look for "X videos" in page text
            }

            return { channel_id: channelId, channel_name: name, subscriber_count: subs,
                     total_videos: totalVideos };
        }""")
        return result or {}
    except Exception:
        return {}


# ── Channel scraper ───────────────────────────────────────────────────────────

async def scrape_channel_video_urls(page: Page, channel_ref: str) -> list:
    """Navigate to a channel's videos tab and collect video URLs."""
    # Normalise URL
    if channel_ref.startswith("http"):
        base = channel_ref.rstrip("/")
        if not base.endswith("/videos"):
            base += "/videos"
        url = base
    elif channel_ref.startswith("@"):
        url = f"https://www.youtube.com/{channel_ref}/videos"
    else:
        url = f"https://www.youtube.com/@{channel_ref}/videos"

    print(f"  [Nav] {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    # Try to get channel name
    try:
        channel_name = await page.title()
    except Exception:
        channel_name = channel_ref

    # Use dict to preserve insertion order (YouTube shows newest first)
    video_urls: dict = {}
    print(f"  Scrolling to collect video links ({CHANNEL_SCROLL_ROUNDS} rounds)...")

    for i in range(CHANNEL_SCROLL_ROUNDS):
        # Collect all video links in DOM order (top = newest)
        links = await page.eval_on_selector_all(
            'a[href*="/watch?v="]',
            'els => els.map(e => e.href)'
        )
        for link in links:
            m = re.search(r"v=([A-Za-z0-9_-]{11})", link)
            if m:
                vid = m.group(1)
                if vid not in video_urls:
                    video_urls[vid] = True  # preserve first-seen order = newest first

        await page.evaluate("window.scrollBy(0, 1500)")
        await page.wait_for_timeout(1200)

        if (i + 1) % 5 == 0:
            print(f"  scroll {i+1}/{CHANNEL_SCROLL_ROUNDS} — {len(video_urls)} videos found")

    ordered = list(video_urls.keys())  # newest first
    print(f"  Found {len(ordered)} unique videos on {channel_name} (newest first)")
    return ordered


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run(target_videos: list = None, target_channels: list = None,
              skip_comments: bool = False):
    from db import init_db, save_video, save_comment, get_stats

    init_db()

    video_ids = list(target_videos or TARGET_VIDEOS)
    channels  = list(target_channels or TARGET_CHANNELS)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()

        # Dismiss cookie consent if it appears
        await page.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)
        for sel in ['button[aria-label*="Accept"]', 'button:has-text("Accept all")',
                    'button:has-text("Reject all")', 'tp-yt-paper-button:has-text("AGREE")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # channel_id → {info dict, video_ids list}
        channel_map: dict = {}

        # Collect video IDs from channels
        for ch in channels:
            print(f"\n[Channel] {ch}")
            ch_vids = await scrape_channel_video_urls(page, ch)
            ch_info = await extract_channel_info(page, ch)
            ch_info["total_videos_on_channel"] = len(ch_vids)

            if CHANNEL_VIDEO_LIMIT:
                ch_vids = ch_vids[:CHANNEL_VIDEO_LIMIT]
                print(f"  [Limit] Taking first {CHANNEL_VIDEO_LIMIT} videos for testing")

            ch_id = ch_info.get("channel_id") or ch
            ch_info.setdefault("channel_name", ch)
            channel_map[ch_id] = {"info": ch_info, "video_ids": ch_vids}
            video_ids.extend(ch_vids)

        # Deduplicate
        video_ids = list(dict.fromkeys(
            extract_video_id(v) for v in video_ids
        ))

        if not video_ids:
            print("\n[!] No videos to scrape.")
            print("    Pass --video URL or --channel @handle, "
                  "or add to TARGET_VIDEOS/TARGET_CHANNELS in scraper.py")
            await browser.close()
            return

        print(f"\n[Scraper] Processing {len(video_ids)} video(s)...")

        saved_videos   = 0
        saved_comments = 0
        skipped        = 0
        # For JSON export: track scraped data per channel_id
        scraped_videos:   list = []
        scraped_comments: list = []

        for i, vid in enumerate(video_ids):
            print(f"\n{'='*55}")
            print(f"[{i+1}/{len(video_ids)}] {vid}")

            try:
                details, comments = await scrape_video(page, vid)
            except Exception as e:
                print(f"  [!] Skipping {vid} — error: {e}")
                skipped += 1
                continue

            # If we got nothing at all (no title, no views, no channel), skip
            if not details.get("title") and not details.get("channel_name") and details.get("view_count", 0) == 0:
                # Try DOM fallback for title
                try:
                    title_el = await page.query_selector("h1.ytd-watch-metadata, h1[class*='title']")
                    if title_el:
                        details["title"] = (await title_el.inner_text()).strip()
                except Exception:
                    pass
                if not details.get("title"):
                    print("  [!] Could not load video (private, deleted, or geo-blocked)")
                    skipped += 1
                    continue

            ts = details.get("published_at", "")

            # Always print what we found
            print(f"  Title:    {details.get('title','')[:65]}")
            print(f"  Channel:  {details.get('channel_name','')}")
            print(f"  Date:     {str(ts)[:10]}")
            print(f"  Views:    {details.get('view_count',0):,}")
            print(f"  Likes:    {details.get('like_count',0):,}")
            print(f"  Comments: {details.get('comment_count',0):,}")

            if ts and not in_date_range(ts):
                print(f"  [DateFilter] Skipping — published {ts[:10]}")
                skipped += 1
                continue

            save_video(details)
            saved_videos += 1
            scraped_videos.append(details)

            if not skip_comments:
                for c in comments:
                    save_comment(c)
                saved_comments += len(comments)
                scraped_comments.extend(comments)
                print(f"  Saved {len(comments)} comments")

        await browser.close()

    stats = get_stats()
    print(f"\n{'='*55}")
    print("SCRAPE COMPLETE")
    print(f"{'='*55}")
    print(f"  ── This run ──────────────────")
    print(f"  Videos scraped:  {saved_videos}")
    print(f"  Comments scraped:{saved_comments}")
    print(f"  Skipped:         {skipped}")
    print(f"  ── All time (DB) ─────────────")
    print(f"  Total videos:    {stats['videos']}")
    print(f"  Total comments:  {stats['comments']}")
    print(f"  Total views:     {stats['views']:,}")
    print(f"  Total likes:     {stats['likes']:,}")

    return {
        "channel_map":      channel_map,
        "scraped_videos":   scraped_videos,
        "scraped_comments": scraped_comments,
        "saved_videos":     saved_videos,
        "saved_comments":   saved_comments,
        "skipped":          skipped,
    }
