#!/usr/bin/env python3
"""
Opens the dashboard in the browser once per calendar day when Chrome is detected.
Called by launchd (com.screentime.morning-open).
"""

import sqlite3
import subprocess
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screentime.db")


# Checks if Google Chrome is currently running via pgrep.
# Returns True if running, False otherwise.
def is_chrome_running():
    try:
        r = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


# Reads the dashboard_opened_today value from the settings table.
# Returns a date string (e.g. "2026-04-03") or empty string.
def get_last_opened_date():
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'dashboard_opened_today'"
        ).fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


# Writes today's date to the dashboard_opened_today setting.
# Takes a date string like "2026-04-03".
def set_opened_today(date_str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'dashboard_opened_today'",
            (date_str,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# Main loop: checks every 30s if Chrome is running and the dashboard
# hasn't been opened yet today. Opens it once per calendar day.
def run():
    while True:
        today = datetime.now().strftime("%Y-%m-%d")
        if is_chrome_running() and get_last_opened_date() != today:
            subprocess.run(["open", "http://localhost:8050"], capture_output=True)
            set_opened_today(today)
        time.sleep(30)


if __name__ == "__main__":
    run()
