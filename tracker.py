#!/usr/bin/env python3
"""
Screen Time Tracker — polls the active Chrome tab every 5 seconds
and logs time on LeetCode, LinkedIn, Gmail, and Streaming to SQLite.
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
    {"keyword": "leetcode", "category": "LeetCode"},
    {"keyword": "linkedin", "category": "LinkedIn"},
    {"keyword": "gmail", "category": "Gmail"},
    {"keyword": "mail.google", "category": "Gmail"},
    {"keyword": "netflix.com", "category": "Streaming"},
    {"keyword": "primevideo.com", "category": "Streaming"},
]

# In-memory tracking for streaming alerts (reset daily)
_alerts_fired = set()
_alerts_date = None


# Creates the time_log and settings tables if they don't exist.
# Inserts default settings rows on first run.
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("INSERT OR IGNORE INTO settings VALUES ('tracking_enabled', '1')")
    conn.execute("INSERT OR IGNORE INTO settings VALUES ('dashboard_opened_today', '')")
    conn.commit()
    conn.close()


# Reads the tracking_enabled flag from the settings table.
# Returns True if tracking is on, False if paused.
def is_tracking_enabled():
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'tracking_enabled'"
        ).fetchone()
        conn.close()
        return row is not None and row[0] == "1"
    except Exception:
        return True


# Uses AppleScript to get the active Chrome tab's title and URL.
# Returns (None, None) if Chrome is not frontmost, window is incognito, or error.
def get_chrome_tab():
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell
    if frontApp is not "Google Chrome" then return "NOT_CHROME"
    tell application "Google Chrome"
        set w to front window
        set m to mode of w
        if m is "incognito" then return "INCOGNITO"
        set t to title of active tab of w
        set u to URL of active tab of w
    end tell
    return t & "|||" & u
    '''
    try:
        r = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
        out = r.stdout.strip()
        if out in ("NOT_CHROME", "INCOGNITO") or "|||" not in out:
            return None, None
        title, url = out.split("|||", 1)
        return title, url
    except Exception:
        return None, None


# Matches tab title+URL against SITE_RULES keywords.
# Takes title and url strings, returns category name or None.
def classify(title, url):
    combined = (title + " " + url).lower()
    for rule in SITE_RULES:
        if rule["keyword"] in combined:
            return rule["category"]
    return None


# Inserts a time_log row for the current moment.
# Takes a category string and tab_title string.
def log_entry(category, tab_title):
    now = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO time_log (timestamp, date, category, tab_title, duration_seconds) VALUES (?,?,?,?,?)",
        (now.isoformat(), now.strftime("%Y-%m-%d"), category, tab_title, POLL_INTERVAL),
    )
    conn.commit()
    conn.close()


# Fires a macOS notification using osascript.
# Takes a title string and message string.
def send_notification(title, message):
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


# Checks today's streaming total and fires alerts at 30min and 45min.
# Each alert fires only once per calendar day using an in-memory set.
def check_streaming_alerts():
    global _alerts_fired, _alerts_date

    today = datetime.now().strftime("%Y-%m-%d")

    # Reset alerts on new calendar day
    if _alerts_date != today:
        _alerts_fired = set()
        _alerts_date = today

    # Both alerts already sent today — skip the DB query
    if len(_alerts_fired) >= 2:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT SUM(duration_seconds) FROM time_log WHERE date = ? AND category = 'Streaming'",
            (today,),
        ).fetchone()
        conn.close()
        total = row[0] or 0
    except Exception:
        return

    # Check 45min first so both can fire on the same poll if needed
    if total >= 2700 and "45min" not in _alerts_fired:
        send_notification(
            "Screen Time Alert",
            "45 minutes of streaming today. Seriously — close the tab.",
        )
        _alerts_fired.add("45min")
        # Also mark 30min as fired so it doesn't fire after 45min
        _alerts_fired.add("30min")
    elif total >= 1800 and "30min" not in _alerts_fired:
        send_notification(
            "Screen Time Alert",
            "You've been streaming for 30 minutes. Maybe switch to LeetCode?",
        )
        _alerts_fired.add("30min")


# Main loop: initializes DB, polls Chrome every 5s, classifies and logs matching tabs.
# Respects the tracking_enabled pause flag and skips incognito windows.
def run():
    init_db()
    print(f"Screen Time Tracker started (PID {os.getpid()})")
    print(f"Logging to {DB_PATH}")
    print("Tracking: LeetCode · LinkedIn · Gmail · Streaming  (Chrome only)")
    print(f"Polling every {POLL_INTERVAL}s — Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda *_: (print("\nStopped."), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    while True:
        if is_tracking_enabled():
            title, url = get_chrome_tab()
            if title:
                cat = classify(title, url)
                if cat:
                    log_entry(cat, title)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {cat}")
                    if cat == "Streaming":
                        check_streaming_alerts()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
