#!/usr/bin/env python3
"""Dashboard server — live-updating screen time stats."""

import sqlite3
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screentime.db")
app = Flask(__name__)

CATEGORIES = {
    "LeetCode": "#FFA116",
    "LinkedIn": "#0A66C2",
    "Gmail": "#EA4335",
    "Streaming": "#E50914",
}


# Returns a SQLite connection with Row factory for dict-like access.
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Ensures the settings table exists with default values.
# Called once at startup so the dashboard can work even before tracker.py runs.
def init_settings():
    conn = sqlite3.connect(DB_PATH)
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


# ── API ──────────────────────────────────────────────────────────────────────


# Returns time summary per category for a given period (today/week/all),
# plus morning_greeting string and tracking_enabled boolean.
@app.route("/api/summary")
def api_summary():
    period = request.args.get("period", "today")
    conn = get_db()

    # Tracking enabled flag
    setting = conn.execute(
        "SELECT value FROM settings WHERE key = 'tracking_enabled'"
    ).fetchone()
    tracking_enabled = setting["value"] == "1" if setting else True

    # Summary data
    if period == "today":
        cutoff = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT category, SUM(duration_seconds) as total FROM time_log WHERE date = ? GROUP BY category",
            (cutoff,),
        ).fetchall()
    elif period == "week":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT category, SUM(duration_seconds) as total FROM time_log WHERE date >= ? GROUP BY category",
            (cutoff,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT category, SUM(duration_seconds) as total FROM time_log GROUP BY category"
        ).fetchall()

    # Morning greeting — yesterday's LeetCode time
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yrow = conn.execute(
        "SELECT SUM(duration_seconds) FROM time_log WHERE date = ? AND category = 'LeetCode'",
        (yesterday,),
    ).fetchone()
    conn.close()

    yesterday_lc = yrow[0] if yrow and yrow[0] else 0
    if yesterday_lc > 0:
        minutes = yesterday_lc // 60
        morning_greeting = f"Yesterday you spent {minutes}m on LeetCode"
    else:
        morning_greeting = None

    return jsonify(
        {
            "data": [
                {"category": r["category"], "seconds": r["total"] or 0} for r in rows
            ],
            "morning_greeting": morning_greeting,
            "tracking_enabled": tracking_enabled,
        }
    )


# Returns daily totals per category for the past N days.
@app.route("/api/daily")
def api_daily():
    days = int(request.args.get("days", 7))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_db()
    rows = conn.execute(
        "SELECT date, category, SUM(duration_seconds) as total FROM time_log WHERE date >= ? GROUP BY date, category ORDER BY date",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify(
        [
            {"date": r["date"], "category": r["category"], "seconds": r["total"]}
            for r in rows
        ]
    )


# Returns exactly 7 days of data grouped by date and category for the stacked chart.
# Always returns 7 entries with zeros filled in for missing days/categories.
@app.route("/api/weekly")
def api_weekly():
    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date, category, SUM(duration_seconds) as total FROM time_log WHERE date >= ? GROUP BY date, category",
        (cutoff,),
    ).fetchall()
    conn.close()

    # Build lookup: {date: {category: seconds}}
    lookup = {}
    for r in rows:
        lookup.setdefault(r["date"], {})[r["category"]] = r["total"]

    # Build 7-day array with zeros for missing data
    days = []
    for i in range(6, -1, -1):
        d = datetime.now() - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        label = d.strftime("%a")
        entry = lookup.get(date_str, {})
        days.append(
            {
                "date": date_str,
                "label": label,
                "LeetCode": entry.get("LeetCode", 0),
                "LinkedIn": entry.get("LinkedIn", 0),
                "Gmail": entry.get("Gmail", 0),
                "Streaming": entry.get("Streaming", 0),
            }
        )

    return jsonify({"days": days})


# Toggles the tracking_enabled setting between '1' and '0'.
# Returns the new tracking_enabled boolean.
@app.route("/api/toggle-tracking", methods=["POST"])
def api_toggle_tracking():
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'tracking_enabled'"
    ).fetchone()
    current = row["value"] if row else "1"
    new_val = "0" if current == "1" else "1"
    conn.execute(
        "UPDATE settings SET value = ? WHERE key = 'tracking_enabled'", (new_val,)
    )
    conn.commit()
    conn.close()
    return jsonify({"tracking_enabled": new_val == "1"})


# Deletes all time_log rows with dates before the first day of the current month.
# Returns the count of deleted rows.
@app.route("/api/data/before-this-month", methods=["DELETE"])
def api_delete_before_month():
    first_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.execute("DELETE FROM time_log WHERE date < ?", (first_of_month,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"deleted": deleted})


# Deletes all time_log rows within the current calendar month.
# Returns the count of deleted rows.
@app.route("/api/data/this-month", methods=["DELETE"])
def api_delete_this_month():
    first_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.execute("DELETE FROM time_log WHERE date >= ?", (first_of_month,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"deleted": deleted})


# ── Dashboard (single-page, no template files needed) ───────────────────────


# Serves the dashboard HTML page.
@app.route("/")
def dashboard():
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Screen Time Tracker</title>
<style>
  :root { --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a; --text: #e1e4ed; --muted: #8b8fa3;
          --danger: #ef4444; --danger-hover: #dc2626; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height:100vh; }
  .container { max-width:900px; margin:0 auto; padding:24px 16px; }

  /* Header */
  .header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:20px; }
  .header-center { text-align:center; flex:1; }
  h1 { font-size:1.6rem; margin-bottom:4px; }
  .subtitle { color:var(--muted); font-size:0.85rem; }
  .live-dot { display:inline-block; width:8px; height:8px; background:#22c55e; border-radius:50%;
              margin-right:6px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  .manage-btn { background:var(--card); border:1px solid var(--border); color:var(--muted);
                padding:6px 14px; border-radius:8px; cursor:pointer; font-size:.8rem;
                white-space:nowrap; margin-top:4px; }
  .manage-btn:hover { border-color:var(--muted); color:var(--text); }

  .pause-btn { background:#22c55e22; border:1px solid #22c55e44; color:#22c55e;
               padding:6px 14px; border-radius:8px; cursor:pointer; font-size:.8rem;
               white-space:nowrap; margin-top:4px; transition: all .2s; }
  .pause-btn:hover { background:#22c55e33; }
  .pause-btn.paused { background:#ef444422; border-color:#ef444444; color:var(--danger); }
  .pause-btn.paused:hover { background:#ef444433; }

  /* Greeting banner */
  .greeting { background:var(--card); border:1px solid var(--border); border-radius:10px;
              padding:12px 18px; margin-bottom:18px; font-size:.9rem; color:var(--muted); }

  /* Paused badge */
  .paused-badge { display:inline-block; background:#ef444422; color:var(--danger); font-size:.75rem;
                  padding:2px 10px; border-radius:6px; margin-left:10px; vertical-align:middle; }

  /* Period toggle */
  .toggle { display:flex; gap:4px; margin-bottom:20px; }
  .toggle button { background:var(--card); border:1px solid var(--border); color:var(--muted);
                   padding:6px 16px; border-radius:8px; cursor:pointer; font-size:.85rem; }
  .toggle button.active { background:#5b5ef4; color:#fff; border-color:#5b5ef4; }

  /* Cards */
  .cards { display:grid; grid-template-columns: repeat(4, 1fr); gap:14px; margin-bottom:28px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }
  .card .label { font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .card .value { font-size:1.8rem; font-weight:700; margin-top:4px; }
  .card .sub { font-size:.8rem; color:var(--muted); margin-top:2px; }
  .card.warning { border-color: var(--danger); }
  .card.warning .label { color: var(--danger) !important; }
  .card.warning .value { color: var(--danger); }

  /* Bar chart */
  .chart-section { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:28px; }
  .chart-title { font-size:.95rem; font-weight:600; margin-bottom:16px; }
  .bar-row { display:flex; align-items:center; margin-bottom:12px; }
  .bar-label { width:80px; font-size:.85rem; flex-shrink:0; }
  .bar-track { flex:1; background:var(--bg); border-radius:6px; height:28px; overflow:hidden; position:relative; }
  .bar-fill { height:100%; border-radius:6px; transition: width .6s ease; display:flex; align-items:center;
              padding-left:10px; font-size:.75rem; font-weight:600; min-width:fit-content; }

  /* Chart legend */
  .chart-legend { display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap; }
  .chart-legend span { font-size:.78rem; color:var(--muted); display:flex; align-items:center; gap:5px; }
  .legend-dot { width:10px; height:10px; border-radius:2px; display:inline-block; }

  /* Weekly canvas */
  #weeklyChart { display:block; width:100%; }

  .empty { color:var(--muted); font-size:.75rem; text-align:center; padding:40px 0; }

  /* Modal */
  .modal-overlay { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,.6);
                   display:flex; align-items:center; justify-content:center; z-index:1000;
                   animation: fadeIn .15s ease; }
  @keyframes fadeIn { from{opacity:0} to{opacity:1} }
  .modal-card { background:var(--card); border:1px solid var(--border); border-radius:14px;
                padding:28px; width:380px; max-width:90vw; }
  .modal-title { font-size:1.1rem; font-weight:600; margin-bottom:18px; }
  .modal-text { color:var(--muted); font-size:.9rem; margin-bottom:18px; }
  .modal-btn { display:block; width:100%; padding:10px; border-radius:8px; border:none;
               font-size:.88rem; cursor:pointer; margin-bottom:10px; font-weight:500; }
  .modal-btn.danger { background:var(--danger); color:#fff; }
  .modal-btn.danger:hover { background:var(--danger-hover); }
  .modal-btn.cancel { background:var(--bg); color:var(--muted); border:1px solid var(--border); }
  .modal-btn.cancel:hover { color:var(--text); border-color:var(--muted); }
  .modal-btn:last-child { margin-bottom:0; }

  @media (max-width: 700px) {
    .cards { grid-template-columns: repeat(2, 1fr); }
    .header { flex-wrap:wrap; gap:8px; }
  }
</style>
</head>
<body>
<div class="container">
  <!-- Header -->
  <div class="header">
    <button class="manage-btn" onclick="openModal()">Manage Data</button>
    <div class="header-center">
      <h1><span class="live-dot"></span>Screen Time Tracker<span id="pausedBadge" class="paused-badge" style="display:none">Paused</span></h1>
      <p class="subtitle">Tracking LeetCode · LinkedIn · Gmail · Streaming on Chrome</p>
    </div>
    <button class="pause-btn" id="pauseBtn" onclick="togglePause()">Tracking Active</button>
  </div>

  <!-- Morning greeting -->
  <div id="greeting" class="greeting" style="display:none"></div>

  <!-- Period toggle -->
  <div class="toggle">
    <button class="active" data-period="today">Today</button>
    <button data-period="week">This Week</button>
    <button data-period="all">All Time</button>
  </div>

  <div class="cards" id="cards"></div>

  <div class="chart-section">
    <div class="chart-title">Time Breakdown</div>
    <div id="bars"></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Last 7 Days</div>
    <div class="chart-legend" id="legend">
      <span><span class="legend-dot" style="background:#FFA116"></span>LeetCode</span>
      <span><span class="legend-dot" style="background:#0A66C2"></span>LinkedIn</span>
      <span><span class="legend-dot" style="background:#EA4335"></span>Gmail</span>
      <span><span class="legend-dot" style="background:#E50914"></span>Streaming</span>
    </div>
    <canvas id="weeklyChart" height="260"></canvas>
  </div>
</div>

<!-- Modal overlay -->
<div id="modal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeModal()">
  <div class="modal-card">
    <div id="modalContent"></div>
  </div>
</div>

<script>
const COLORS = { LeetCode:"#FFA116", LinkedIn:"#0A66C2", Gmail:"#EA4335", Streaming:"#E50914" };
const CATS = ["LeetCode","LinkedIn","Gmail","Streaming"];
let period = "today";

/* ── Helpers ─────────────────────────────────────────── */

// Formats seconds into a human-readable string like "1h 23m".
function fmt(sec) {
  if (!sec || sec < 1) return "0m";
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60);
  return h > 0 ? h + "h " + m + "m" : m + "m";
}

/* ── Morning greeting ────────────────────────────────── */

// Shows or hides the greeting banner based on time of day and yesterday's data.
function updateGreeting(morningGreeting) {
  const el = document.getElementById("greeting");
  const hour = new Date().getHours();
  if (hour >= 12) { el.style.display = "none"; return; }
  if (morningGreeting) {
    el.textContent = "Good morning! " + morningGreeting;
  } else {
    el.innerHTML = "Good morning! No LeetCode yesterday \\u2014 let\\u2019s fix that today \\uD83D\\uDCAA";
  }
  el.style.display = "block";
}

/* ── Pause toggle ────────────────────────────────────── */

// Sends POST to toggle tracking and updates button state.
async function togglePause() {
  const res = await fetch("/api/toggle-tracking", { method: "POST" });
  const json = await res.json();
  updatePauseUI(json.tracking_enabled);
}

// Updates the pause button and badge to reflect enabled/disabled state.
function updatePauseUI(enabled) {
  const btn = document.getElementById("pauseBtn");
  const badge = document.getElementById("pausedBadge");
  if (enabled) {
    btn.textContent = "Tracking Active";
    btn.classList.remove("paused");
    badge.style.display = "none";
  } else {
    btn.textContent = "Tracking Paused";
    btn.classList.add("paused");
    badge.style.display = "inline-block";
  }
}

/* ── Data management modal ───────────────────────────── */

let _confirmTarget = null;

// Opens the modal with the two delete options.
function openModal() {
  _confirmTarget = null;
  renderModalOptions();
  document.getElementById("modal").style.display = "flex";
}

// Closes the modal.
function closeModal() {
  document.getElementById("modal").style.display = "none";
}

// Renders the two-option view inside the modal.
function renderModalOptions() {
  document.getElementById("modalContent").innerHTML =
    '<div class="modal-title">Delete Data</div>' +
    '<button class="modal-btn danger" onclick="confirmDelete(\'before-this-month\')">Delete data before this month</button>' +
    '<button class="modal-btn danger" onclick="confirmDelete(\'this-month\')">Delete this month\\u2019s data</button>' +
    '<button class="modal-btn cancel" onclick="closeModal()">Cancel</button>';
}

// Switches the modal to the confirmation view for a given delete target.
function confirmDelete(target) {
  _confirmTarget = target;
  document.getElementById("modalContent").innerHTML =
    '<div class="modal-title">Are you sure?</div>' +
    '<p class="modal-text">This cannot be undone.</p>' +
    '<button class="modal-btn danger" onclick="executeDelete()">Yes, delete</button>' +
    '<button class="modal-btn cancel" onclick="renderModalOptions()">Cancel</button>';
}

// Calls the delete API and refreshes the dashboard on success.
async function executeDelete() {
  if (!_confirmTarget) return;
  await fetch("/api/data/" + _confirmTarget, { method: "DELETE" });
  closeModal();
  load();
}

// Close modal on Escape key
document.addEventListener("keydown", function(e) { if (e.key === "Escape") closeModal(); });

/* ── Stacked bar chart (Canvas) ──────────────────────── */

// Draws a stacked bar chart on the weeklyChart canvas.
// Takes the /api/weekly response object with a .days array.
function drawWeeklyChart(weeklyData) {
  var canvas = document.getElementById("weeklyChart");
  if (!canvas) return;

  // Size canvas to container
  var cWidth = canvas.parentElement.clientWidth - 40;
  if (cWidth < 200) cWidth = 200;
  var cHeight = 260;
  var dpr = window.devicePixelRatio || 1;
  canvas.width = cWidth * dpr;
  canvas.height = cHeight * dpr;
  canvas.style.width = cWidth + "px";
  canvas.style.height = cHeight + "px";
  var ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  var W = cWidth, H = cHeight;
  var pad = { top: 15, bottom: 32, left: 42, right: 10 };
  var chartW = W - pad.left - pad.right;
  var chartH = H - pad.top - pad.bottom;

  // Find max total seconds across days for Y-axis scaling
  var maxSec = 0;
  weeklyData.days.forEach(function(d) {
    var total = CATS.reduce(function(s, c) { return s + (d[c] || 0); }, 0);
    if (total > maxSec) maxSec = total;
  });
  if (maxSec === 0) maxSec = 3600;

  // Round max up to a nice number in minutes
  var maxMin = Math.ceil(maxSec / 60 / 10) * 10;
  if (maxMin === 0) maxMin = 10;

  // Y-axis grid lines and labels
  var yTicks = 4;
  ctx.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
  for (var i = 0; i <= yTicks; i++) {
    var val = maxMin / yTicks * i;
    var y = pad.top + chartH - (chartH * val / maxMin);
    ctx.strokeStyle = "#2a2d3a";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = "#8b8fa3";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(Math.round(val) + "m", pad.left - 6, y);
  }

  // Draw stacked bars
  var barGap = chartW / 7;
  var barW = barGap * 0.5;

  weeklyData.days.forEach(function(d, idx) {
    var x = pad.left + idx * barGap + (barGap - barW) / 2;
    var yOffset = 0;

    CATS.forEach(function(c) {
      var sec = d[c] || 0;
      var h = (sec / 60) / maxMin * chartH;
      if (h > 0.5) {
        ctx.fillStyle = COLORS[c];
        ctx.fillRect(x, pad.top + chartH - yOffset - h, barW, h);
        yOffset += h;
      }
    });

    // X-axis day label
    ctx.fillStyle = "#8b8fa3";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillText(d.label, pad.left + idx * barGap + barGap / 2, pad.top + chartH + 8);
  });
}

/* ── Main data loader ────────────────────────────────── */

// Fetches summary, daily, and weekly data, then re-renders the entire dashboard.
async function load() {
  // Fetch summary and weekly in parallel
  var [summaryRes, weeklyRes] = await Promise.all([
    fetch("/api/summary?period=" + period),
    fetch("/api/weekly")
  ]);
  var summary = await summaryRes.json();
  var weekly = await weeklyRes.json();
  var data = summary.data;
  var total = data.reduce(function(s,d) { return s + d.seconds; }, 0);
  var max = Math.max.apply(null, data.map(function(d) { return d.seconds; }).concat([1]));

  // Update greeting, pause state
  updateGreeting(summary.morning_greeting);
  updatePauseUI(summary.tracking_enabled);

  // Cards — always show all 4 categories
  document.getElementById("cards").innerHTML = CATS.map(function(c) {
    var s = 0;
    data.forEach(function(d) { if (d.category === c) s = d.seconds; });
    var pct = total > 0 ? Math.round(s / total * 100) : 0;
    var warn = (c === "Streaming" && s >= 1800) ? " warning" : "";
    return '<div class="card' + warn + '"><div class="label" style="color:' + COLORS[c] + '">' + c + '</div>'
      + '<div class="value">' + fmt(s) + '</div>'
      + '<div class="sub">' + pct + '% of tracked</div></div>';
  }).join("");

  // Bars
  if (data.length === 0) {
    document.getElementById("bars").innerHTML = '<div class="empty">No data yet — open a tracked site in Chrome</div>';
  } else {
    var sorted = data.slice().sort(function(a,b) { return b.seconds - a.seconds; });
    document.getElementById("bars").innerHTML = sorted.map(function(d) {
      var pct = Math.max(d.seconds / max * 100, 2);
      return '<div class="bar-row"><div class="bar-label">' + d.category + '</div>'
        + '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + COLORS[d.category] + '">'
        + fmt(d.seconds) + '</div></div></div>';
    }).join("");
  }

  // Weekly stacked chart
  drawWeeklyChart(weekly);
}

/* ── Event listeners ─────────────────────────────────── */

// Period toggle buttons
document.querySelector(".toggle").addEventListener("click", function(e) {
  if (!e.target.dataset.period) return;
  period = e.target.dataset.period;
  document.querySelectorAll(".toggle button").forEach(function(b) { b.classList.remove("active"); });
  e.target.classList.add("active");
  load();
});

// Initial load + auto-refresh every 10s
load();
setInterval(load, 10000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        import tracker

        tracker.init_db()
    else:
        init_settings()
    print("Dashboard → http://localhost:8050")
    app.run(host="127.0.0.1", port=8050, debug=True)
