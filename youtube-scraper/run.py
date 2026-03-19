import argparse
import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path

EXPORTS_DIR = Path(__file__).parent / "exports"
DATA_DIR    = Path(__file__).parent / "data"


# ── Flat CSV/JSON export (existing behaviour, kept as-is) ────────────────────

def export_data():
    from db import get_all_videos, get_all_comments
    EXPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    videos   = get_all_videos()
    comments = get_all_comments()

    if videos:
        vp = EXPORTS_DIR / f"videos_{ts}.csv"
        with open(vp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=videos[0].keys())
            w.writeheader()
            w.writerows(videos)
        print(f"[Export] Videos CSV   → {vp}")

    if comments:
        cp = EXPORTS_DIR / f"comments_{ts}.csv"
        with open(cp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=comments[0].keys())
            w.writeheader()
            w.writerows(comments)
        print(f"[Export] Comments CSV → {cp}")

    jp = EXPORTS_DIR / f"full_data_{ts}.json"
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"videos": videos, "comments": comments},
                  f, indent=2, ensure_ascii=False)
    print(f"[Export] Full JSON    → {jp}")


# ── Per-channel structured JSON output ───────────────────────────────────────

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_channel_data(result: dict):
    """
    Save per-channel folder structure:
      data/{channel_id}/channel.json
      data/{channel_id}/videos.json
      data/{channel_id}/comments.json
      data/{channel_id}/analysis.json
    """
    from analysis import normalize_video, normalize_comment, normalize_channel, compute_analysis

    channel_map      = result.get("channel_map", {})
    scraped_videos   = result.get("scraped_videos", [])
    scraped_comments = result.get("scraped_comments", [])

    if not channel_map and not scraped_videos:
        return

    # Group videos and comments by channel_id
    # If scraping specific videos (no channel), group under their channel_id
    videos_by_channel:   dict = {}
    comments_by_channel: dict = {}

    for v in scraped_videos:
        cid = v.get("channel_id") or "unknown"
        videos_by_channel.setdefault(cid, []).append(v)

    for c in scraped_comments:
        vid = c.get("video_id", "")
        # Find which channel this video belongs to
        cid = next(
            (v.get("channel_id", "unknown") for v in scraped_videos
             if v.get("video_id") == vid),
            "unknown"
        )
        comments_by_channel.setdefault(cid, []).append(c)

    # Merge channel_map with any channels inferred from videos
    all_channel_ids = set(list(channel_map.keys()) + list(videos_by_channel.keys()))

    for cid in all_channel_ids:
        ch_entry  = channel_map.get(cid, {})
        ch_info   = ch_entry.get("info", {"channel_id": cid, "channel_name": cid})
        ch_videos = videos_by_channel.get(cid, [])
        ch_comments = comments_by_channel.get(cid, [])

        if not ch_videos:
            continue

        folder = DATA_DIR / (cid or "unknown")

        # Normalize
        norm_channel  = normalize_channel(ch_info)
        norm_videos   = [normalize_video(v)   for v in ch_videos]
        norm_comments = [normalize_comment(c) for c in ch_comments]

        # Analysis
        analysis = compute_analysis(norm_channel, norm_videos, norm_comments)

        # Write files
        _write_json(folder / "channel.json",  norm_channel)
        _write_json(folder / "videos.json",   norm_videos)
        _write_json(folder / "comments.json", norm_comments)
        _write_json(folder / "analysis.json", analysis)

        print(f"\n[Data] Channel folder → {folder}/")
        print(f"       channel.json   — {norm_channel['channel_name']}")
        print(f"       videos.json    — {len(norm_videos)} videos")
        print(f"       comments.json  — {len(norm_comments)} comments")
        print(f"       analysis.json  — avg engagement "
              f"{analysis['summary']['avg_engagement_rate']}%")


# ── Stats display ─────────────────────────────────────────────────────────────

def show_stats():
    from db import init_db, get_stats
    init_db()
    s = get_stats()
    print(f"\nYouTube Scraper — Database Stats")
    print(f"{'─'*35}")
    print(f"  Videos:      {s['videos']:>8,}")
    print(f"  Comments:    {s['comments']:>8,}")
    print(f"  Total views: {s['views']:>8,}")
    print(f"  Total likes: {s['likes']:>8,}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YouTube scraper — no API key needed",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python3 run.py --video https://youtube.com/watch?v=abc123
  python3 run.py --channel @eddyspizzaghana
  python3 run.py --channel @channelhandle --no-comments
  python3 run.py --stats
  python3 run.py --export
        """,
    )
    parser.add_argument("--video",       nargs="+", metavar="URL_OR_ID",
                        help="Scrape specific video(s) by URL or video ID")
    parser.add_argument("--channel",     nargs="+", metavar="HANDLE",
                        help="Scrape all videos from channel(s), e.g. @channelname")
    parser.add_argument("--stats",       action="store_true",
                        help="Show database stats and exit")
    parser.add_argument("--export",      action="store_true",
                        help="Export DB to CSV + JSON files in exports/")
    parser.add_argument("--no-comments", action="store_true",
                        help="Skip comment scraping (faster, videos only)")
    parser.add_argument("--schedule",    type=int, metavar="HOURS",
                        help="Run repeatedly every N hours")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.export and not args.video and not args.channel:
        from db import init_db
        init_db()
        export_data()
        return

    from db import init_db
    from scraper import run
    init_db()

    def do_run():
        result = asyncio.run(run(
            target_videos=args.video    or [],
            target_channels=args.channel or [],
            skip_comments=args.no_comments,
        ))
        # Always export flat CSV + JSON (existing behaviour)
        export_data()
        # Save per-channel structured JSON + analysis
        if result:
            save_channel_data(result)

    if args.schedule:
        interval = args.schedule * 3600
        print(f"[Schedule] Running every {args.schedule} hour(s). Ctrl+C to stop.")
        while True:
            do_run()
            next_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[Schedule] Done. Next run in {args.schedule}h (at {next_run})")
            time.sleep(interval)
    else:
        do_run()


if __name__ == "__main__":
    main()
