#!/usr/bin/env python3
"""
Screen Time Tracker — polls the active Chrome tab every 5 seconds
and logs time on LeetCode, Job Search, Gmail, and Streaming to SQLite.
"""

import sqlite3
import subprocess
import time
import signal
import stat
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screentime.db")
POLL_INTERVAL = 5  # seconds

SITE_RULES = [
    {"keyword": "leetcode", "category": "LeetCode"},
    {"keyword": "linkedin", "category": "Job Search"},
    {"keyword": "workday", "category": "Job Search"},
    {"keyword": "/career", "category": "Job Search"},
    {"keyword": "/job", "category": "Job Search"},
    {"keyword": "gmail", "category": "Gmail"},
    {"keyword": "mail.google", "category": "Gmail"},
    {"keyword": "netflix.com", "category": "Streaming"},
    {"keyword": "primevideo.com", "category": "Streaming"},
    {"keyword": "github.com", "category": "GitHub"},
    {"keyword": "vscode", "category": "VS Code"},
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
    # Restrict DB file to owner-only read/write
    os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)


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


# Gets the frontmost app name using lsappinfo (no permissions required).
# Returns the display name string (e.g. "Code", "Google Chrome"), or None on error.
def get_frontmost_app():
    try:
        # Step 1: get the ASN (app serial number) of the frontmost app
        asn = subprocess.run(
            ["lsappinfo", "front"], capture_output=True, text=True, timeout=3
        ).stdout.strip()
        if not asn:
            return None
        # Step 2: get the display name for that ASN
        r = subprocess.run(
            ["lsappinfo", "info", "-only", "name", asn],
            capture_output=True, text=True, timeout=3,
        )
        # Output looks like: "LSDisplayName"="Code"
        out = r.stdout.strip()
        if '="' in out:
            return out.split('="', 1)[1].rstrip('"')
    except Exception:
        pass
    return None


# Reads the active Chrome tab's title, URL, and incognito status via AppleScript.
# Returns (title, url) or (None, None) if incognito or error.
def get_chrome_tab_info():
    script = '''
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
        if out == "INCOGNITO" or "|||" not in out:
            return None, None
        title, url = out.split("|||", 1)
        return title, url
    except Exception:
        return None, None


# Detects the active app and returns (title, url) for classification.
# Uses lsappinfo for app detection (works under launchd without permissions).
# Only calls AppleScript when Chrome is active (to read the tab).
# Returns (None, None) if no trackable app is active.
def get_active_context():
    app = get_frontmost_app()
    if app == "Code":
        return "VS Code", "vscode"
    if app == "Google Chrome":
        return get_chrome_tab_info()
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


# Fires a macOS notification using osascript via System Events.
# Uses System Events explicitly so notifications work reliably from launchd agents.
# Takes a title string and message string. Sanitizes inputs to prevent script injection.
def send_notification(title, message):
    safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
    safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
    script = (
        f'tell application "System Events" to display notification '
        f'"{safe_message}" with title "{safe_title}"'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"[ALERT FAILED] {title}: {message} — {result.stderr.strip()}")
        else:
            print(f"[ALERT SENT] {title}: {message}")
    except Exception as e:
        print(f"[ALERT ERROR] {title}: {message} — {e}")


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
    print("Tracking: LeetCode · Job Search · Gmail · Streaming · GitHub · VS Code")
    print(f"Polling every {POLL_INTERVAL}s — Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda *_: (print("\nStopped."), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    while True:
        if is_tracking_enabled():
            title, url = get_active_context()
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
