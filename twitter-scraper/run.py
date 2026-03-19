"""
Entry point — run this to start scraping X/Twitter.

Usage:
  python3 run.py                   # scrape tweets + replies
  python3 run.py --replies-only    # skip reply scraping (faster)
  python3 run.py --schedule        # run every 12 hours automatically
  python3 run.py --stats           # show DB stats only
  python3 run.py --export          # export data to CSV/JSON
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

    tweets_file = out_dir / f"tweets_{timestamp}.csv"
    tweets = conn.execute("SELECT * FROM tweets ORDER BY timestamp DESC").fetchall()
    if tweets:
        with open(tweets_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=tweets[0].keys())
            writer.writeheader()
            writer.writerows([dict(t) for t in tweets])
        print(f"[Export] Tweets → {tweets_file}")

    replies_file = out_dir / f"replies_{timestamp}.csv"
    replies = conn.execute("SELECT * FROM replies ORDER BY timestamp DESC").fetchall()
    if replies:
        with open(replies_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=replies[0].keys())
            writer.writeheader()
            writer.writerows([dict(r) for r in replies])
        print(f"[Export] Replies → {replies_file}")

    json_file = out_dir / f"full_data_{timestamp}.json"
    data = {
        "exported_at": datetime.now().isoformat(),
        "tweets":      [dict(t) for t in tweets],
        "replies":     [dict(r) for r in replies],
    }
    json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[Export] Full JSON → {json_file}")
    conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────

def schedule_run(interval_hours: int = 12, scrape_replies: bool = True):
    print(f"[Scheduler] Running every {interval_hours} hours. Press Ctrl+C to stop.")
    while True:
        print(f"\n[Scheduler] Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        asyncio.run(run(scrape_replies_flag=scrape_replies))
        export_data()
        print(f"[Scheduler] Next run in {interval_hours} hours...")
        time.sleep(interval_hours * 3600)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Twitter/X Scraper — Eddy's Pizza Ghana")
    parser.add_argument("--replies-only", action="store_true", help="Skip reply scraping")
    parser.add_argument("--schedule",     action="store_true", help="Run on a schedule (every 12h)")
    parser.add_argument("--interval",     type=int, default=12, help="Schedule interval in hours")
    parser.add_argument("--stats",        action="store_true", help="Show DB stats and exit")
    parser.add_argument("--export",       action="store_true", help="Export data to CSV/JSON and exit")
    args = parser.parse_args()

    init_db()

    if args.stats:
        stats = get_stats()
        print("\n── Twitter/X Database Stats ─────────────")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    if args.export:
        export_data()
        return

    scrape_replies = not args.replies_only

    if args.schedule:
        schedule_run(interval_hours=args.interval, scrape_replies=scrape_replies)
    else:
        asyncio.run(run(scrape_replies_flag=scrape_replies))
        export_data()


if __name__ == "__main__":
    main()
