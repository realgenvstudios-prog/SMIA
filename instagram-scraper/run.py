"""
Entry point — run this to start scraping Instagram.

Usage:
  python3 run.py                  # scrape posts + comments
  python3 run.py --posts-only     # scrape posts only (faster)
  python3 run.py --schedule       # run every 12 hours automatically
  python3 run.py --stats          # show DB stats only
  python3 run.py --export         # export data to CSV/JSON and exit
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


def export_data():
    conn = get_conn()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(exist_ok=True)

    posts = conn.execute("SELECT * FROM posts ORDER BY timestamp DESC").fetchall()
    if posts:
        posts_file = out_dir / f"posts_{timestamp}.csv"
        with open(posts_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=posts[0].keys())
            writer.writeheader()
            writer.writerows([dict(p) for p in posts])
        print(f"[Export] Posts → {posts_file}")

    comments = conn.execute("SELECT * FROM comments ORDER BY timestamp DESC").fetchall()
    if comments:
        comments_file = out_dir / f"comments_{timestamp}.csv"
        with open(comments_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=comments[0].keys())
            writer.writeheader()
            writer.writerows([dict(c) for c in comments])
        print(f"[Export] Comments → {comments_file}")

    json_file = out_dir / f"full_data_{timestamp}.json"
    json_file.write_text(json.dumps({
        "exported_at": datetime.now().isoformat(),
        "posts":       [dict(p) for p in posts],
        "comments":    [dict(c) for c in comments],
    }, indent=2, ensure_ascii=False))
    print(f"[Export] Full JSON → {json_file}")
    conn.close()


def schedule_run(interval_hours: int = 12, scrape_comments: bool = True):
    print(f"[Scheduler] Running every {interval_hours} hours. Press Ctrl+C to stop.")
    while True:
        print(f"\n[Scheduler] Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        asyncio.run(run(scrape_comments_flag=scrape_comments))
        export_data()
        print(f"[Scheduler] Next run in {interval_hours} hours...")
        time.sleep(interval_hours * 3600)


def main():
    parser = argparse.ArgumentParser(description="Instagram Scraper — Eddy's Pizza Ghana")
    parser.add_argument("--posts-only", action="store_true", help="Skip comment scraping")
    parser.add_argument("--schedule",   action="store_true", help="Run on a schedule (every 12h)")
    parser.add_argument("--interval",   type=int, default=12, help="Schedule interval in hours")
    parser.add_argument("--stats",      action="store_true", help="Show DB stats and exit")
    parser.add_argument("--export",     action="store_true", help="Export data to CSV/JSON and exit")
    args = parser.parse_args()

    init_db()

    if args.stats:
        stats = get_stats()
        print("\n── Instagram Database Stats ───────────────")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    if args.export:
        export_data()
        return

    scrape_comments = not args.posts_only

    if args.schedule:
        schedule_run(interval_hours=args.interval, scrape_comments=scrape_comments)
    else:
        asyncio.run(run(scrape_comments_flag=scrape_comments))
        export_data()


if __name__ == "__main__":
    main()
