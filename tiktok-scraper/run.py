"""
Entry point — run this to start scraping TikTok.

Usage:
  python3 run.py                  # scrape videos + comments
  python3 run.py --videos-only    # scrape videos only (faster)
  python3 run.py --schedule       # run every 12 hours automatically
  python3 run.py --stats          # show DB stats only
  python3 run.py --export         # export data to CSV/JSON
"""

import asyncio
import argparse
import time
import csv
import json
from pathlib import Path
from datetime import datetime

from db import init_db, get_conn, get_stats
from scraper import run


# ── Export ────────────────────────────────────────────────────────────────────

def export_data():
    conn = get_conn()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(exist_ok=True)

    videos_file = out_dir / f"videos_{timestamp}.csv"
    videos = conn.execute("SELECT * FROM videos ORDER BY timestamp DESC").fetchall()
    if videos:
        with open(videos_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=videos[0].keys())
            writer.writeheader()
            writer.writerows([dict(v) for v in videos])
        print(f"[Export] Videos → {videos_file}")

    comments_file = out_dir / f"comments_{timestamp}.csv"
    comments = conn.execute("SELECT * FROM comments ORDER BY timestamp DESC").fetchall()
    if comments:
        with open(comments_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=comments[0].keys())
            writer.writeheader()
            writer.writerows([dict(c) for c in comments])
        print(f"[Export] Comments → {comments_file}")

    json_file = out_dir / f"full_data_{timestamp}.json"
    data = {
        "exported_at": datetime.now().isoformat(),
        "videos":      [dict(v) for v in videos],
        "comments":    [dict(c) for c in comments],
    }
    json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[Export] Full JSON → {json_file}")
    conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────

def schedule_run(interval_hours: int = 12, scrape_comments: bool = True):
    print(f"[Scheduler] Running every {interval_hours} hours. Press Ctrl+C to stop.")
    while True:
        print(f"\n[Scheduler] Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        asyncio.run(run(scrape_comments_flag=scrape_comments))
        export_data()
        print(f"[Scheduler] Next run in {interval_hours} hours...")
        time.sleep(interval_hours * 3600)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TikTok Scraper — Eddy's Pizza Ghana")
    parser.add_argument("--videos-only", action="store_true", help="Skip comment scraping")
    parser.add_argument("--schedule",    action="store_true", help="Run on a schedule (every 12h)")
    parser.add_argument("--interval",    type=int, default=12, help="Schedule interval in hours")
    parser.add_argument("--stats",       action="store_true", help="Show DB stats and exit")
    parser.add_argument("--export",      action="store_true", help="Export data to CSV/JSON and exit")
    args = parser.parse_args()

    init_db()

    if args.stats:
        stats = get_stats()
        print("\n── TikTok Database Stats ───────────────")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    if args.export:
        export_data()
        return

    scrape_comments = not args.videos_only

    if args.schedule:
        schedule_run(interval_hours=args.interval, scrape_comments=scrape_comments)
    else:
        asyncio.run(run(scrape_comments_flag=scrape_comments))
        export_data()


if __name__ == "__main__":
    main()
