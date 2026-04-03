# Screen Time Tracker

A local macOS app that tracks how much time you spend on **LeetCode**, **LinkedIn**, and **Gmail** in Google Chrome, and displays it on a live-updating dashboard.

Everything runs locally on your Mac — no internet, no cloud, no accounts.

---

## Quick Start (1 command)

```bash
git clone https://github.com/ankitasethi/screen-time-tracker.git
cd screen-time-tracker
bash setup.sh
```

That's it. The setup script will:
1. Install Python dependencies (Flask)
2. Register macOS background services
3. Start tracking immediately
4. Open the dashboard in your browser

**Requirements:** macOS + Python 3 + Google Chrome

To uninstall: `bash uninstall.sh`

---

## Architecture

```
                          ┌───────────────────┐
                          │   Google Chrome    │
                          │   (your tabs)      │
                          └────────┬──────────┘
                                   │
                          AppleScript reads
                          active tab title + URL
                                   │
                                   ▼
                          ┌───────────────────┐
                          │   tracker.py       │
                          │   (polls every 5s) │
                          └────────┬──────────┘
                                   │
                              writes rows
                                   │
                                   ▼
                          ┌───────────────────┐
                          │   screentime.db   │
                          │   (SQLite file)   │
                          └────────┬──────────┘
                                   │
                              queries data
                                   │
                                   ▼
                          ┌───────────────────┐
                          │     app.py        │
                          │  (Flask :8050)    │
                          └────────┬──────────┘
                                   │
                            JSON responses
                          (auto-refresh 10s)
                                   │
                                   ▼
                          ┌───────────────────┐
                          │    Dashboard      │
                          │   (Browser UI)    │
                          └───────────────────┘
```

---

## How It Works

### 1. Tracker (`tracker.py`)
- Runs a **polling loop** every 5 seconds
- Uses **AppleScript** (`osascript`) to ask macOS System Events for the frontmost app
- If the active app is **Google Chrome**, it reads the current tab's **title** and **URL**
- Matches against keywords:
  - `leetcode` → LeetCode
  - `linkedin` → LinkedIn
  - `gmail` / `mail.google` → Gmail
- If matched, inserts a row into the **SQLite database** with timestamp, date, category, and duration (5s)
- If Chrome isn't active or the tab doesn't match, it skips — zero overhead

### 2. Dashboard (`app.py`)
- A **Flask** web server on `http://localhost:8050`
- Serves a single-page dark-themed dashboard (HTML/CSS/JS inline — no template files)
- Exposes **REST API endpoints**:
  - `GET /api/summary?period=today|week|all` — time per category
  - `GET /api/daily?days=7` — daily breakdown
- The frontend **auto-refreshes every 10 seconds** using `fetch()` + `setInterval()`
- Shows:
  - Time cards for each site
  - Horizontal bar chart breakdown
  - Last 7 days timeline
  - Toggle between Today / This Week / All Time

### 3. Auto-Start (launchd)
- Three **macOS launchd agents** registered in `~/Library/LaunchAgents/`:
  - `com.ankita.screentime-tracker` — starts `tracker.py` on login, keeps it alive
  - `com.ankita.screentime-dashboard` — starts `app.py` on login, keeps it alive
  - `com.ankita.screentime-morning-open` — opens the dashboard in your browser when Chrome launches
- Everything starts automatically when you open your laptop and stops when you shut down

---

## Tech Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Language        | Python 3                          |
| Web Framework   | Flask                             |
| Database        | SQLite (file-based, zero config)  |
| macOS Automation| AppleScript via `osascript`       |
| Frontend        | Vanilla HTML / CSS / JavaScript   |
| Scheduling      | macOS `launchd` (plist agents)    |
| Data Format     | JSON (REST API responses)         |

---

## Project Structure

```
screen-time-tracker/
├── tracker.py          # Polls Chrome, classifies tabs, logs to SQLite
├── app.py              # Flask dashboard server + inline HTML/JS frontend
├── screentime.db       # SQLite database (auto-created)
├── requirements.txt    # Python dependencies (flask)
├── tracker.log         # Tracker process logs
├── dashboard.log       # Dashboard process logs
└── README.md
```

---

## Manual Usage

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start the tracker
python3 tracker.py

# Start the dashboard (in another terminal)
python3 app.py

# Open http://localhost:8050 in your browser
```

---

## Uninstall

```bash
bash uninstall.sh
```
