# Screen Time Tracker

A local macOS app that tracks how much time you spend on LeetCode, job search sites (LinkedIn, Workday, career/job pages), Gmail, GitHub, and streaming sites (Netflix, Prime Video) in Google Chrome, plus VS Code as a native app and displays it on a live-updating dashboard. Built for personal productivity everything runs on your Mac, nothing leaves your machine.

---

## Features

- Tracks 6 categories: LeetCode, Job Search, Gmail, Streaming, GitHub, VS Code
- Job Search covers LinkedIn, Workday, and any URL with `/career` or `/job`
- Dark-themed dashboard at `http://localhost:8050` with auto-refresh every 10s
- Adaptive cards: only categories with tracked time appear
- Stacked 7-day bar chart and time breakdown bars
- Streaming alerts at 30min and 45min (macOS notifications)
- Pause/resume tracking from the dashboard
- Morning greeting with yesterday's LeetCode stats
- Incognito windows automatically skipped
- Data management: delete by month from the dashboard
- Auto-starts on login via macOS launchd
- Security: per-session API token on destructive endpoints, owner-only DB file permissions, debug mode disabled, notification input sanitization

---

## How It Works

1. The tracker polls the active app every 5 seconds.
2. If Chrome is in front, it reads the tab's title and URL via AppleScript. If VS Code is in front, it detects the app by name. Incognito windows are skipped.
3. If the tab matches a tracked site, it logs a 5-second entry to a local SQLite database.
4. The Flask dashboard queries the database and serves a single-page UI with time cards, bar charts, and a stacked 7-day chart.
5. Three macOS launchd agents handle auto-start: one for the tracker, one for the dashboard, and one that opens the dashboard once per day when Chrome launches.

---

## Tech Stack

| Technology          | Why                                     |
| ------------------- | --------------------------------------- |
| Python 3            | Tracker and dashboard server            |
| Flask               | REST API and dashboard serving          |
| SQLite              | Local file-based storage, zero config   |
| AppleScript         | Reads the active Chrome tab             |
| Vanilla HTML/CSS/JS | Dashboard UI, no framework dependencies |
| macOS launchd       | Auto-starts services on login           |

---

## Folder Structure

```
screen-time-tracker/
├── tracker.py          # Polls Chrome + VS Code, classifies activity, logs to SQLite
├── app.py              # Flask dashboard server + inline HTML/JS frontend
├── open_dashboard.py   # Auto-opens dashboard once per day when Chrome launches
├── setup.sh            # One-command installer (registers launchd agents)
├── uninstall.sh        # One-command remover (stops and removes agents)
├── requirements.txt    # Python dependencies (flask)
├── screentime.db       # SQLite database (auto-created, gitignored)
└── README.md           # This file
```

---

## How to Run

### Prerequisites

- macOS (required — uses AppleScript and launchd)
- Python 3 installed
- Google Chrome installed

### Quick Start

```bash
git clone https://github.com/ankitasethi/screen-time-tracker.git
cd screen-time-tracker
bash setup.sh
```

### Manual Usage

```bash
pip3 install -r requirements.txt
python3 tracker.py        # in one terminal
python3 app.py            # in another terminal
# Open http://localhost:8050
```

### Uninstall

```bash
bash uninstall.sh
```

Your data (`screentime.db`) stays in the folder if you want it.

---

## Known Issues

- Only tracks Chrome (not Safari, Firefox, or Arc). VS Code is tracked as a native app.
- AppleScript requires accessibility permissions — macOS may prompt you on first run.
- The dashboard UI is inline in `app.py`, so UI changes require editing Python.
- YouTube is intentionally excluded from streaming tracking.
