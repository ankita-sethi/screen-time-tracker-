# Screen Time Tracker

A local macOS app that tracks how much time you spend on LeetCode, LinkedIn, Gmail, GitHub, and streaming sites (Netflix, Prime Video) in Google Chrome — plus VS Code as a native app — and displays it on a live-updating dashboard. Built for personal productivity — everything runs on your Mac, nothing leaves your machine.

---

## What We Built

A lightweight screen time tracker that monitors your Google Chrome tabs and VS Code usage, logging time spent on LeetCode (job prep), LinkedIn (networking), Gmail (email), GitHub (code), streaming (Netflix, Prime Video), and VS Code (editor). It runs silently in the background, auto-starts when you log in, and shows your stats on a clean dark-themed dashboard at `http://localhost:8050`. You get daily, weekly, and all-time breakdowns with bar charts, a stacked 7-day chart, streaming alerts, a pause/resume toggle, and data management tools. Cards are adaptive — only categories with tracked time appear.

---

## How It Works

1. When your Mac is on, the tracker polls the active app every 5 seconds.
2. If Chrome is in front, it reads the tab's title and URL using macOS AppleScript. Incognito windows are automatically skipped. If VS Code is in front, it detects the app by name.
3. If the tab matches LeetCode, LinkedIn, Gmail, GitHub, Netflix, or Prime Video — or VS Code is active — it logs a 5-second entry to a local SQLite database.
4. The Flask dashboard queries the database and serves a single-page UI with time cards, bar charts, a stacked 7-day chart, and a morning greeting.
5. The dashboard auto-refreshes every 10 seconds — no manual reload needed.
6. Three macOS launchd agents handle auto-start: one for the tracker, one for the dashboard, and one that opens the dashboard in your browser once per day when Chrome launches.
7. Streaming alerts fire as macOS notifications at 30 and 45 minutes per day. Tracking can be paused/resumed from the dashboard.

---

## Tech Stack

| Tool / Technology | What It Is | Why We Use It Here |
|---|---|---|
| Python 3 | Programming language | Main language for the tracker and dashboard server |
| Flask 3.1 | Web framework | Serves the dashboard and REST API endpoints |
| SQLite | File-based database | Stores all time entries locally, zero config needed |
| AppleScript (osascript) | macOS automation | Reads the active Chrome tab title and URL |
| Vanilla HTML / CSS / JS | Frontend | Builds the dashboard UI — no framework dependencies |
| macOS launchd | Service manager | Auto-starts tracker and dashboard on login |

---

## Architecture

```
  +-------------------+       +-------------------+
  |   Google Chrome   |       |     VS Code       |
  |   (your tabs)     |       |  (native app)     |
  +---------+---------+       +---------+---------+
            |                           |
   AppleScript reads             Detected by app
   active tab title + URL        name ("Code")
            |                           |
            +-------------+-------------+
                          |
                          v
                +-------------------+
                |   tracker.py      |
                |   (polls every 5s)|
                +---------+---------+
                                |
                           writes rows
                                |
                                v
                      +-------------------+
                      |  screentime.db    |
                      |  (SQLite file)    |
                      +---------+---------+
                                |
                           queries data
                                |
                                v
                      +-------------------+
                      |    app.py         |
                      |  (Flask :8050)    |
                      +---------+---------+
                                |
                          JSON responses
                        (auto-refresh 10s)
                                |
                                v
                      +-------------------+
                      |   Dashboard       |
                      |  (Browser UI)     |
                      +-------------------+
```

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
├── .gitignore          # Keeps database, logs, and local files out of git
└── README.md           # This file
```

---

## Jargon Glossary

| Term | Plain English Meaning |
|---|---|
| API | A way for two pieces of software to talk to each other |
| Endpoint | A specific URL that the app responds to (e.g. `/api/summary`) |
| SQLite | A database stored as a single file — no server needed |
| launchd | macOS built-in system for starting programs automatically on login |
| AppleScript | A macOS scripting language that can talk to apps like Chrome |
| Polling | Checking for something repeatedly at a fixed interval (every 5 seconds here) |
| plist | A macOS config file that tells launchd what to run and when |

---

## How to Run This Locally

### Prerequisites

- macOS (required — uses AppleScript and launchd)
- Python 3 installed
- Google Chrome installed

### Quick Start (1 command)

```bash
git clone https://github.com/ankitasethi/screen-time-tracker.git
cd screen-time-tracker
bash setup.sh
```

The setup script will:
1. Install Python dependencies (Flask)
2. Register 3 macOS background services
3. Start tracking immediately
4. Open the dashboard in your browser

### Manual Usage

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start the tracker (in one terminal)
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

This stops all services and removes the launchd agents. Your data (`screentime.db`) stays in the folder if you want it.

---

## Current Status

| Area | Status |
|---|---|
| Chrome tab tracking (LeetCode, LinkedIn, Gmail, GitHub, Streaming) | Done |
| VS Code tracking (native app detection) | Done |
| Adaptive cards (hide categories with 0 time) | Done |
| SQLite logging | Done |
| Flask dashboard with live refresh | Done |
| Auto-start via launchd | Done |
| Auto-open dashboard once per day on Chrome launch | Done |
| One-command setup and uninstall | Done |
| Streaming alerts (30min, 45min macOS notifications) | Done |
| Incognito mode exclusion | Done |
| Pause/resume tracking toggle | Done |
| Morning greeting with yesterday's LeetCode stats | Done |
| Stacked 7-day bar chart | Done |
| Data management (delete by month) | Done |

---

## Known Issues

- Chrome tracking only covers Chrome (not Safari, Firefox, or Arc). VS Code is tracked as a native app.
- AppleScript requires accessibility permissions — macOS may prompt you on first run.
- The dashboard uses inline HTML/CSS/JS in `app.py`, so UI changes require editing Python.
- YouTube is intentionally excluded from streaming tracking.
