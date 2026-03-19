"""
Entry point — run this to start scraping.

Usage:
  python3 run.py                  # scrape posts + comments
  python3 run.py --posts-only     # scrape posts only (faster)
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
from getpass import getpass

from db import init_db, get_conn, get_stats
from scraper import run

# ── Credentials ───────────────────────────────────────────────────────────────
# Option 1: hardcode here (not recommended for shared machines)
# Option 2: use environment variables (recommended)
# Option 3: enter at runtime (default below)

import os
FB_EMAIL    = os.getenv("FB_EMAIL", "")
FB_PASSWORD = os.getenv("FB_PASSWORD", "")


# ── Export ────────────────────────────────────────────────────────────────────

def export_data():
    conn = get_conn()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(exist_ok=True)

    # Export posts to CSV
    posts_file = out_dir / f"posts_{timestamp}.csv"
    posts = conn.execute("SELECT * FROM posts ORDER BY timestamp DESC").fetchall()
    if posts:
        with open(posts_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=posts[0].keys())
            writer.writeheader()
            writer.writerows([dict(p) for p in posts])
        print(f"[Export] Posts → {posts_file}")

    # Export comments to CSV
    comments_file = out_dir / f"comments_{timestamp}.csv"
    comments = conn.execute("SELECT * FROM comments ORDER BY timestamp DESC").fetchall()
    if comments:
        with open(comments_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=comments[0].keys())
            writer.writeheader()
            writer.writerows([dict(c) for c in comments])
        print(f"[Export] Comments → {comments_file}")

    # Export combined JSON
    json_file = out_dir / f"full_data_{timestamp}.json"
    data = {
        "exported_at": datetime.now().isoformat(),
        "posts":       [dict(p) for p in posts],
        "comments":    [dict(c) for c in comments],
    }
    json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[Export] Full JSON → {json_file}")

    conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────

def schedule_run(email: str, password: str, interval_hours: int = 12):
    print(f"[Scheduler] Running every {interval_hours} hours. Press Ctrl+C to stop.")
    while True:
        print(f"\n[Scheduler] Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        asyncio.run(run(email, password, scrape_comments_flag=True))
        export_data()
        next_run = interval_hours * 3600
        print(f"[Scheduler] Next run in {interval_hours} hours...")
        time.sleep(next_run)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Facebook Page Scraper")
    parser.add_argument("--posts-only", action="store_true",  help="Skip comment scraping")
    parser.add_argument("--schedule",   action="store_true",  help="Run on a schedule (every 12h)")
    parser.add_argument("--interval",   type=int, default=12, help="Schedule interval in hours")
    parser.add_argument("--stats",      action="store_true",  help="Show DB stats and exit")
    parser.add_argument("--export",     action="store_true",  help="Export data to CSV/JSON and exit")
    args = parser.parse_args()

    init_db()

    if args.stats:
        stats = get_stats()
        print("\n── Database Stats ──────────────────")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    if args.export:
        export_data()
        return

    # Get credentials
    email    = FB_EMAIL    or input("Facebook email: ").strip()
    password = FB_PASSWORD or getpass("Facebook password: ")

    if args.schedule:
        schedule_run(email, password, interval_hours=args.interval)
    else:
        scrape_comments = not args.posts_only
        asyncio.run(run(email, password, scrape_comments_flag=scrape_comments))
        export_data()


if __name__ == "__main__":
    main()
