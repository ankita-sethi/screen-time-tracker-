#!/usr/bin/env python3
"""
Screen Time Tracker — polls the active Chrome tab every 5 seconds
and logs time on LeetCode, LinkedIn, and Gmail to SQLite.
"""

import sqlite3
import subprocess
import time
import signal
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screentime.db")
POLL_INTERVAL = 5  # seconds

SITE_RULES = [
    {"keyword": "leetcode", "category": "LeetCode", "color": "#FFA116"},
    {"keyword": "linkedin", "category": "LinkedIn", "color": "#0A66C2"},
    {"keyword": "gmail", "category": "Gmail", "color": "#EA4335"},
    {"keyword": "mail.google", "category": "Gmail", "color": "#EA4335"},
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            tab_title TEXT,
            duration_seconds INTEGER NOT NULL DEFAULT 5
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date_cat ON time_log(date, category)")
    conn.commit()
    conn.close()


def get_chrome_tab():
    """Return (title, url) of the active Chrome tab, or (None, None)."""
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell
    if frontApp is not "Google Chrome" then return "NOT_CHROME"
    tell application "Google Chrome"
        set t to title of active tab of front window
        set u to URL of active tab of front window
    end tell
    return t & "|||" & u
    '''
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=5)
        out = r.stdout.strip()
        if out == "NOT_CHROME" or "|||" not in out:
            return None, None
        title, url = out.split("|||", 1)
        return title, url
    except Exception:
        return None, None


def classify(title, url):
    """Return category name if the tab matches a tracked site, else None."""
    combined = (title + " " + url).lower()
    for rule in SITE_RULES:
        if rule["keyword"] in combined:
            return rule["category"]
    return None


def log_entry(category, tab_title):
    now = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO time_log (timestamp, date, category, tab_title, duration_seconds) VALUES (?,?,?,?,?)",
        (now.isoformat(), now.strftime("%Y-%m-%d"), category, tab_title, POLL_INTERVAL),
    )
    conn.commit()
    conn.close()


def run():
    init_db()
    print(f"Screen Time Tracker started (PID {os.getpid()})")
    print(f"Logging to {DB_PATH}")
    print("Tracking: LeetCode · LinkedIn · Gmail  (Chrome only)")
    print(f"Polling every {POLL_INTERVAL}s — Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda *_: (print("\nStopped."), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    while True:
        title, url = get_chrome_tab()
        if title:
            cat = classify(title, url)
            if cat:
                log_entry(cat, title)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {cat}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
