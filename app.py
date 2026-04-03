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
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/summary")
def api_summary():
    period = request.args.get("period", "today")
    conn = get_db()
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
    conn.close()
    return jsonify([{"category": r["category"], "seconds": r["total"] or 0} for r in rows])


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
    return jsonify([{"date": r["date"], "category": r["category"], "seconds": r["total"]} for r in rows])


# ── Dashboard (single-page, no template files needed) ───────────────────────

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
  :root { --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a; --text: #e1e4ed; --muted: #8b8fa3; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height:100vh; }
  .container { max-width:900px; margin:0 auto; padding:24px 16px; }
  h1 { font-size:1.6rem; margin-bottom:4px; }
  .subtitle { color:var(--muted); font-size:0.85rem; margin-bottom:24px; }
  .live-dot { display:inline-block; width:8px; height:8px; background:#22c55e; border-radius:50%;
              margin-right:6px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  /* Period toggle */
  .toggle { display:flex; gap:4px; margin-bottom:20px; }
  .toggle button { background:var(--card); border:1px solid var(--border); color:var(--muted);
                   padding:6px 16px; border-radius:8px; cursor:pointer; font-size:.85rem; }
  .toggle button.active { background:#5b5ef4; color:#fff; border-color:#5b5ef4; }

  /* Cards */
  .cards { display:grid; grid-template-columns: repeat(3, 1fr); gap:14px; margin-bottom:28px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }
  .card .label { font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .card .value { font-size:1.8rem; font-weight:700; margin-top:4px; }
  .card .sub { font-size:.8rem; color:var(--muted); margin-top:2px; }

  /* Bar chart */
  .chart-section { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:28px; }
  .chart-title { font-size:.95rem; font-weight:600; margin-bottom:16px; }
  .bar-row { display:flex; align-items:center; margin-bottom:12px; }
  .bar-label { width:80px; font-size:.85rem; flex-shrink:0; }
  .bar-track { flex:1; background:var(--bg); border-radius:6px; height:28px; overflow:hidden; position:relative; }
  .bar-fill { height:100%; border-radius:6px; transition: width .6s ease; display:flex; align-items:center;
              padding-left:10px; font-size:.75rem; font-weight:600; min-width:fit-content; }

  /* Timeline */
  .timeline { display:grid; grid-template-columns: repeat(7,1fr); gap:8px; }
  .day-col { text-align:center; }
  .day-col .day-label { font-size:.7rem; color:var(--muted); margin-bottom:6px; }
  .day-col .day-bars { display:flex; flex-direction:column; gap:3px; }
  .day-bar { border-radius:4px; height:22px; font-size:.65rem; display:flex; align-items:center;
             justify-content:center; color:#fff; font-weight:600; }
  .empty { color:var(--muted); font-size:.75rem; text-align:center; padding:40px 0; }
</style>
</head>
<body>
<div class="container">
  <h1><span class="live-dot"></span>Screen Time Tracker</h1>
  <p class="subtitle">Tracking LeetCode · LinkedIn · Gmail on Chrome</p>

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
    <div class="timeline" id="timeline"></div>
  </div>
</div>

<script>
const COLORS = { LeetCode:"#FFA116", LinkedIn:"#0A66C2", Gmail:"#EA4335" };
let period = "today";

function fmt(sec) {
  if (!sec || sec < 1) return "0m";
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60);
  return h > 0 ? h + "h " + m + "m" : m + "m";
}

async function load() {
  const res = await fetch("/api/summary?period=" + period);
  const data = await res.json();
  const total = data.reduce((s,d) => s + d.seconds, 0);
  const max = Math.max(...data.map(d => d.seconds), 1);

  // Cards
  const cats = ["LeetCode","LinkedIn","Gmail"];
  document.getElementById("cards").innerHTML = cats.map(c => {
    const s = (data.find(d => d.category === c) || {}).seconds || 0;
    const pct = total > 0 ? Math.round(s/total*100) : 0;
    return '<div class="card"><div class="label" style="color:'+COLORS[c]+'">'+c+'</div>'
      + '<div class="value">'+fmt(s)+'</div>'
      + '<div class="sub">'+pct+'% of tracked</div></div>';
  }).join("");

  // Bars
  if (data.length === 0) {
    document.getElementById("bars").innerHTML = '<div class="empty">No data yet — open LeetCode, LinkedIn, or Gmail in Chrome</div>';
  } else {
    document.getElementById("bars").innerHTML = data.sort((a,b)=>b.seconds-a.seconds).map(d => {
      const pct = Math.max(d.seconds/max*100, 2);
      return '<div class="bar-row"><div class="bar-label">'+d.category+'</div>'
        + '<div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:'+COLORS[d.category]+'">'
        + fmt(d.seconds)+'</div></div></div>';
    }).join("");
  }

  // Timeline
  const tres = await fetch("/api/daily?days=7");
  const tdata = await tres.json();
  const days = {};
  for (let i = 6; i >= 0; i--) {
    const d = new Date(); d.setDate(d.getDate()-i);
    const key = d.toISOString().slice(0,10);
    days[key] = { label: d.toLocaleDateString("en-US",{weekday:"short"}), cats:{} };
  }
  tdata.forEach(r => { if (days[r.date]) days[r.date].cats[r.category] = r.seconds; });

  document.getElementById("timeline").innerHTML = Object.entries(days).map(([k,v]) => {
    const bars = Object.entries(v.cats).map(([c,s]) =>
      '<div class="day-bar" style="background:'+COLORS[c]+'">'+fmt(s)+'</div>'
    ).join("") || '<div style="color:var(--muted);font-size:.7rem;padding:8px 0">—</div>';
    return '<div class="day-col"><div class="day-label">'+v.label+'</div><div class="day-bars">'+bars+'</div></div>';
  }).join("");
}

// Toggle buttons
document.querySelector(".toggle").addEventListener("click", e => {
  if (!e.target.dataset.period) return;
  period = e.target.dataset.period;
  document.querySelectorAll(".toggle button").forEach(b => b.classList.remove("active"));
  e.target.classList.add("active");
  load();
});

// Auto-refresh every 10s
load();
setInterval(load, 10000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        # Create the DB so the dashboard can start even before the tracker runs
        import tracker
        tracker.init_db()
    print("Dashboard → http://localhost:8050")
    app.run(host="127.0.0.1", port=8050, debug=True)
