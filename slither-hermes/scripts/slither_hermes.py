#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover - import guard for first-time setup
    print(
        "Playwright is not available. Install it with:\n"
        "  python3 -m venv .venv\n"
        "  ./.venv/bin/pip install playwright\n"
        "  PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers "
        "./.venv/bin/python -m playwright install chromium\n"
        f"\nImport error: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autonomous slither.io demo runner for Hermes."
    )
    parser.add_argument("--nickname", default="hermetic")
    parser.add_argument("--url", default="http://slither.io")
    parser.add_argument("--output-dir", default="slither-run")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--clip-interval", type=float, default=None)
    parser.add_argument("--clip-duration", type=float, default=10.0)
    parser.add_argument("--frame-interval", type=float, default=0.25)
    parser.add_argument("--duration", type=float, default=21600.0)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--verbose-stdout", action="store_true")
    parser.add_argument("--join-wait-ms", type=int, default=5000)
    parser.add_argument("--tick-ms", type=int, default=80)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_peek_dashboard(run_dir: Path, asset_prefix: str = "") -> None:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Slither Hermes Peek</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: rgba(17, 24, 39, 0.82);
      --panel-strong: rgba(15, 23, 42, 0.95);
      --border: rgba(148, 163, 184, 0.16);
      --text: #e6edf3;
      --muted: #94a3b8;
      --accent: #60a5fa;
      --accent-2: #a78bfa;
      --good: #3fb950;
      --warn: #d29922;
      --bad: #f85149;
      --shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 20px;
      background:
        radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(167, 139, 250, 0.18), transparent 24%),
        linear-gradient(180deg, #0b1020 0%, #0a0f1b 100%);
      color: var(--text);
      font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1, h2, h3, h4, p { margin: 0; }
    .shell { display: grid; gap: 18px; max-width: 1560px; margin: 0 auto; }
    .hero {
      position: relative;
      overflow: hidden;
      border-radius: 22px;
      border: 1px solid rgba(148, 163, 184, 0.2);
      background:
        radial-gradient(circle at 0% 0%, rgba(96, 165, 250, 0.25), transparent 28%),
        radial-gradient(circle at 100% 0%, rgba(167, 139, 250, 0.22), transparent 26%),
        linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(17, 24, 39, 0.92));
      box-shadow: var(--shadow);
      padding: 22px;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
      pointer-events: none;
    }
    .topbar { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; position: relative; z-index: 1; }
    .hero-title { display: grid; gap: 8px; max-width: 860px; }
    .hero-title h1 { font-size: 32px; letter-spacing: -0.03em; }
    .meta { color: var(--muted); font-size: 13px; }
    .panel {
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      min-width: 0;
      box-shadow: var(--shadow);
    }
    .cards {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      position: relative;
      z-index: 1;
      margin-top: 16px;
    }
    .stat-card {
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)),
        var(--panel-strong);
    }
    .stat-card::before {
      content: "";
      position: absolute;
      inset: 0 auto auto 0;
      width: 100%;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
      opacity: 0.8;
    }
    .stat-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; }
    .stat-value { font-size: 30px; font-weight: 750; margin-top: 10px; line-height: 1; }
    .stat-hint { margin-top: 10px; }
    .layout {
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(0, 1.8fr) minmax(320px, 1fr);
      align-items: start;
    }
    .media-stack, .side-stack { display: grid; gap: 16px; min-width: 0; }
    .media-panel {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0)),
        var(--panel-strong);
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .panel-head h2 { font-size: 17px; }
    .subpill {
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.18);
      padding: 4px 10px;
      font-size: 11px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
    }
    .media-frame {
      position: relative;
      overflow: hidden;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
      border: 1px solid rgba(148, 163, 184, 0.14);
      padding: 8px;
    }
    img { width: 100%; border-radius: 10px; background: #000; display: block; }
    .tiny { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .status-box, .summary-box {
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.5;
      max-height: 30vh;
      overflow: auto;
      margin-top: 10px;
      padding-right: 4px;
    }
    .summary-box {
      font-size: 13px;
      max-height: 36vh;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--border);
      padding: 8px 6px;
      text-align: left;
    }
    th { color: var(--muted); font-weight: 600; }
    tbody tr:hover {
      background: rgba(255,255,255,0.03);
    }
    .best-row {
      background: linear-gradient(90deg, rgba(96,165,250,0.12), rgba(167,139,250,0.06));
    }
    .mode-chip {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 11px;
      border: 1px solid rgba(148,163,184,0.16);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .pill {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.18);
      font-size: 12px;
      color: #dbeafe;
      background: rgba(96,165,250,0.12);
    }
    .ok { color: var(--good); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    .links { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .empty {
      color: var(--muted);
      font-size: 13px;
      padding: 12px 0 4px;
    }
    @media (max-width: 1100px) {
      .layout { grid-template-columns: 1fr; }
      .hero-title h1 { font-size: 26px; }
    }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module">
    import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18";
    import { createRoot } from "https://esm.sh/react-dom@18/client";
    import htm from "https://esm.sh/htm@3";

    const html = htm.bind(React.createElement);
    const ASSETS = {
      live: "%LIVE_SRC%",
      gif: "%GIF_SRC%",
      summary: "%SUMMARY_SRC%",
      status: "%STATUS_SRC%",
      batchSummary: "%BATCH_SUMMARY_SRC%",
      bestGif: "%BEST_GIF_SRC%",
      bestPng: "%BEST_PNG_SRC%",
      longestGif: "%LONGEST_GIF_SRC%"
    };

    function stampNow(ts = Date.now()) {
      return new Date(ts).toLocaleTimeString();
    }

    function useTextFile(path, intervalMs) {
      const [state, setState] = useState({ text: "", error: "", updatedAt: null, status: null });

      useEffect(() => {
        let cancelled = false;
        async function load() {
          try {
            const resp = await fetch(path + "?ts=" + Date.now(), { cache: "no-store" });
            if (!resp.ok) {
              throw new Error("HTTP " + resp.status);
            }
            const text = await resp.text();
            if (!cancelled) {
              setState({ text, error: "", updatedAt: Date.now(), status: resp.status });
            }
          } catch (err) {
            if (!cancelled) {
              setState((prev) => ({ ...prev, error: String(err), updatedAt: Date.now() }));
            }
          }
        }
        load();
        const timer = setInterval(load, intervalMs);
        return () => {
          cancelled = true;
          clearInterval(timer);
        };
      }, [path, intervalMs]);

      return state;
    }

    function useBlobAsset(path, intervalMs) {
      const [state, setState] = useState({ url: path, error: "", updatedAt: null, ok: false });

      useEffect(() => {
        let cancelled = false;
        let currentUrl = null;

        async function load() {
          try {
            const resp = await fetch(path + "?ts=" + Date.now(), { cache: "no-store" });
            if (!resp.ok) {
              throw new Error("HTTP " + resp.status);
            }
            const blob = await resp.blob();
            if (!blob.size) {
              throw new Error("empty file");
            }
            const nextUrl = URL.createObjectURL(blob);
            if (cancelled) {
              URL.revokeObjectURL(nextUrl);
              return;
            }
            if (currentUrl) {
              URL.revokeObjectURL(currentUrl);
            }
            currentUrl = nextUrl;
            setState({ url: nextUrl, error: "", updatedAt: Date.now(), ok: true });
          } catch (err) {
            if (!cancelled) {
              setState((prev) => ({ ...prev, error: String(err), updatedAt: Date.now(), ok: false }));
            }
          }
        }

        load();
        const timer = setInterval(load, intervalMs);
        return () => {
          cancelled = true;
          clearInterval(timer);
          if (currentUrl) {
            URL.revokeObjectURL(currentUrl);
          }
        };
      }, [path, intervalMs]);

      return state;
    }

    function parseEvents(raw) {
      if (!raw) return [];
      return raw
        .split("\\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          try {
            return JSON.parse(line);
          } catch (_err) {
            return null;
          }
        })
        .filter(Boolean);
    }

    function deriveMetrics(events) {
      const rounds = new Map();
      let bestRank = null;
      let bestRound = null;
      let activeRound = null;

      for (const event of events) {
        const round = Number.isInteger(event.round) ? event.round : null;
        if (round !== null && !rounds.has(round)) {
          rounds.set(round, {
            round,
            ticks: 0,
            bestRank: null,
            lastMode: null,
            panicTicks: 0,
            eventCount: 0,
          });
        }

        if (round !== null) {
          const entry = rounds.get(round);
          entry.eventCount += 1;
          if (event.event === "tick") {
            entry.ticks = Math.max(entry.ticks, event.tick || 0);
            entry.lastMode = event.mode || entry.lastMode;
            if (event.mode === "panic") {
              entry.panicTicks += 1;
            }
          }
          if (typeof event.rank === "number" && event.rank > 0) {
            if (entry.bestRank === null || event.rank < entry.bestRank) {
              entry.bestRank = event.rank;
            }
            if (bestRank === null || event.rank < bestRank) {
              bestRank = event.rank;
              bestRound = round;
            }
          }
          activeRound = round;
        }
      }

      const roundRows = Array.from(rounds.values()).sort((a, b) => a.round - b.round);
      const lastEvents = events.slice(-8).reverse();
      return { roundRows, bestRank, bestRound, activeRound, lastEvents };
    }

    function StatCard({ label, value, hint }) {
      return html`
        <div className="panel stat-card">
          <div className="stat-label">${label}</div>
          <div className="stat-value">${value ?? "—"}</div>
          <div className="tiny stat-hint">${hint ?? ""}</div>
        </div>
      `;
    }

    function App() {
      const live = useBlobAsset(ASSETS.live, 800);
      const latestGif = useBlobAsset(ASSETS.gif, 3000);
      const bestGif = useBlobAsset(ASSETS.bestGif, 5000);
      const bestPng = useBlobAsset(ASSETS.bestPng, 5000);
      const longestGif = useBlobAsset(ASSETS.longestGif, 5000);
      const latestSummary = useTextFile(ASSETS.summary, 1500);
      const batchSummary = useTextFile(ASSETS.batchSummary, 3500);
      const statusLog = useTextFile(ASSETS.status, 1500);

      const events = useMemo(() => parseEvents(statusLog.text), [statusLog.text]);
      const metrics = useMemo(() => deriveMetrics(events), [events]);
      const summaryText = (batchSummary.text || "").trim();
      const latestSummaryText = (latestSummary.text || "").trim();
      const freshnessTone = live.ok ? "ok" : "warn";

      return html`
        <div className="shell">
          <div className="hero">
            <div className="topbar">
              <div className="hero-title">
                <h1>Slither Hermes Dashboard</h1>
                <div className="meta">Live control-room view for the active run, with best-batch artifacts, round telemetry, and session summary.</div>
              </div>
              <div className="pill">${metrics.activeRound ? "Tracking round r" + String(metrics.activeRound).padStart(2, "0") : "Waiting for run"}</div>
            </div>
            <div className="cards">
              <${StatCard} label="Best Rank" value=${metrics.bestRank} hint=${metrics.bestRound ? "Best round r" + String(metrics.bestRound).padStart(2, "0") : "No ranked ticks yet"} />
              <${StatCard} label="Active Round" value=${metrics.activeRound ? "r" + String(metrics.activeRound).padStart(2, "0") : "—"} hint=${latestSummaryText || "Waiting for summary"} />
              <${StatCard} label="Live Frame" value=${live.ok ? "Fresh" : "Stale"} hint=${live.updatedAt ? "Updated " + stampNow(live.updatedAt) : live.error || "Waiting"} />
              <${StatCard} label="Latest GIF" value=${latestGif.ok ? "Fresh" : "Stale"} hint=${latestGif.updatedAt ? "Updated " + stampNow(latestGif.updatedAt) : latestGif.error || "Waiting"} />
              <${StatCard} label="Longest GIF" value=${longestGif.ok ? "Ready" : "Waiting"} hint=${longestGif.updatedAt ? "Updated " + stampNow(longestGif.updatedAt) : longestGif.error || "Waiting"} />
            </div>
          </div>

          <div className="layout">
            <div className="media-stack">
              <div className="panel media-panel">
                <div className="panel-head">
                  <h2>Live Frame</h2>
                  <div className=${"subpill " + freshnessTone}>${live.ok ? "Live stream" : "Waiting"}</div>
                </div>
                <div className="media-frame">
                  <img src=${live.url} alt="Live slither frame" />
                </div>
                <div className=${"tiny " + (live.error ? "bad" : "ok")}>
                  ${live.error ? "Live frame error: " + live.error : "Live frame refreshed at " + (live.updatedAt ? stampNow(live.updatedAt) : "—")}
                </div>
              </div>

              <div className="panel media-panel">
                <div className="panel-head">
                  <h2>Latest GIF</h2>
                  <div className="subpill">Auto-updating</div>
                </div>
                <div className="media-frame">
                  <img src=${latestGif.url} alt="Latest slither gif" />
                </div>
                <div className=${"tiny " + (latestGif.error ? "bad" : "ok")}>
                  ${latestGif.error ? "Latest GIF error: " + latestGif.error : "Latest GIF refreshed at " + (latestGif.updatedAt ? stampNow(latestGif.updatedAt) : "—")}
                </div>
              </div>

              <div className="panel media-panel">
                <div className="panel-head">
                  <h2>Best Batch Artifacts</h2>
                  <div className="subpill">Highlight reel</div>
                </div>
                ${bestGif.ok ? html`<div className="media-frame"><img src=${bestGif.url} alt="Best batch gif" /></div>` : html`<div className="empty">Best GIF not available yet.</div>`}
                <div className="links">
                  <a href=${ASSETS.bestGif} target="_blank" rel="noreferrer">Open best GIF</a>
                  <a href=${ASSETS.bestPng} target="_blank" rel="noreferrer">Open best PNG</a>
                  <a href=${ASSETS.batchSummary} target="_blank" rel="noreferrer">Open summary.md</a>
                </div>
                <div className="tiny">${bestGif.updatedAt ? "Best artifacts refreshed at " + stampNow(bestGif.updatedAt) : "Waiting for batch summary"}</div>
              </div>

              <div className="panel media-panel">
                <div className="panel-head">
                  <h2>Longest GIF</h2>
                  <div className="subpill">Longest captured clip</div>
                </div>
                ${longestGif.ok ? html`<div className="media-frame"><img src=${longestGif.url} alt="Longest captured gif" /></div>` : html`<div className="empty">Longest GIF not available yet.</div>`}
                <div className="links">
                  <a href=${ASSETS.longestGif} target="_blank" rel="noreferrer">Open longest GIF</a>
                  <a href=${ASSETS.batchSummary} target="_blank" rel="noreferrer">Open summary.md</a>
                </div>
                <div className="tiny">${longestGif.updatedAt ? "Longest GIF refreshed at " + stampNow(longestGif.updatedAt) : "Waiting for clip history"}</div>
              </div>
            </div>

            <div className="side-stack">
              <div className="panel">
                <h2>Latest Summary</h2>
                <div className="summary-box">${latestSummaryText || "Waiting for latest_summary.txt..."}</div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>Round Table</h2>
                  <div className="subpill">Best round highlighted</div>
                </div>
                ${metrics.roundRows.length ? html`
                  <table>
                    <thead>
                      <tr>
                        <th>Round</th>
                        <th>Best</th>
                        <th>Ticks</th>
                        <th>Panic</th>
                        <th>Last Mode</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${metrics.roundRows.map((row) => html`
                        <tr key=${row.round} className=${row.round === metrics.bestRound ? "best-row" : ""}>
                          <td>${"r" + String(row.round).padStart(2, "0")}</td>
                          <td>${row.bestRank ?? "—"}</td>
                          <td>${row.ticks}</td>
                          <td>${row.panicTicks}</td>
                          <td><span className="mode-chip">${row.lastMode ?? "—"}</span></td>
                        </tr>
                      `)}
                    </tbody>
                  </table>
                ` : html`<div className="empty">No round data yet.</div>`}
              </div>

              <div className="panel">
                <h2>Batch Summary</h2>
                <div className="summary-box">${summaryText || "Waiting for summary.md..."}</div>
              </div>

              <div className="panel">
                <h2>Recent Events</h2>
                ${metrics.lastEvents.length ? html`
                  <div className="status-box">${metrics.lastEvents.map((event) => JSON.stringify(event)).join("\\n\\n")}</div>
                ` : html`<div className="empty">No status events yet.</div>`}
              </div>
            </div>
          </div>
        </div>
      `;
    }

    createRoot(document.getElementById("root")).render(html`<${App} />`);
  </script>
</body>
</html>
"""
    html = (
        html.replace("%LIVE_SRC%", f"{asset_prefix}live.png")
        .replace("%GIF_SRC%", f"{asset_prefix}latest.gif")
        .replace("%SUMMARY_SRC%", f"{asset_prefix}latest_summary.txt")
        .replace("%STATUS_SRC%", f"{asset_prefix}status.jsonl")
        .replace("%BATCH_SUMMARY_SRC%", f"{asset_prefix}summary.md")
        .replace("%BEST_GIF_SRC%", f"{asset_prefix}best.gif")
        .replace("%BEST_PNG_SRC%", f"{asset_prefix}best.png")
        .replace("%LONGEST_GIF_SRC%", f"{asset_prefix}longest.gif")
    )
    (run_dir / "peek.html").write_text(html, encoding="utf-8")


def write_peek_redirect(base_output_dir: Path) -> None:
    write_peek_dashboard(base_output_dir, asset_prefix="current/")


def make_run_dir(base_output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_output_dir / f"run_{timestamp}"
    ensure_dir(run_dir)
    return run_dir


def update_current_pointer(base_output_dir: Path, run_dir: Path) -> None:
    current_path = base_output_dir / "current"
    if current_path.exists() or current_path.is_symlink():
        if current_path.is_symlink() or current_path.is_file():
            current_path.unlink()
        else:
            return
    current_path.symlink_to(run_dir.name)


def detect_chromium() -> Optional[Path]:
    env_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    browser_roots = [
        Path.cwd() / ".playwright-browsers",
        Path.home() / ".cache" / "ms-playwright",
    ]
    suffixes = [
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-headless-shell-mac-arm64/chrome-headless-shell",
        "chrome-headless-shell-mac-x64/chrome-headless-shell",
        "chrome-linux/chrome",
        "chrome",
    ]

    for root in browser_roots:
        if not root.exists():
            continue
        for suffix in suffixes:
            matches = sorted(root.rglob(suffix))
            if matches:
                return matches[0]
    return None


class Logger:
    def __init__(self, output_dir: Path, *, verbose_stdout: bool = False) -> None:
        self.output_dir = output_dir
        self.log_path = output_dir / "status.jsonl"
        self.latest_summary_path = output_dir / "latest_summary.txt"
        self.verbose_stdout = verbose_stdout
        self.terminal_progress = sys.stdout.isatty() and not verbose_stdout
        self.total_rounds: Optional[int] = None

    def emit(self, event: str, **data: Any) -> None:
        payload = {"ts": utc_now(), "event": event, **data}
        line = json.dumps(payload, sort_keys=True)
        if event == "session_start" and isinstance(data.get("rounds"), int):
            self.total_rounds = int(data["rounds"])
        if self.verbose_stdout:
            print(line, flush=True)
        elif self.terminal_progress:
            progress_line = format_terminal_progress(
                event,
                data,
                total_rounds=self.total_rounds,
            )
            if progress_line:
                print(progress_line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        summary = data.get("telegram_summary")
        if summary:
            self.latest_summary_path.write_text(str(summary).strip() + "\n", encoding="utf-8")


def format_telegram_summary(
    *,
    rank: Optional[Any] = None,
    mode: Optional[str] = None,
    boost: Optional[bool] = None,
    hazard: Optional[Any] = None,
    prefix: Optional[str] = None,
) -> str:
    parts: List[str] = []
    if prefix:
        parts.append(prefix)
    if rank is not None:
        parts.append(f"rank={rank}")
    if mode:
        parts.append(f"mode={mode}")
    if boost is not None:
        parts.append(f"boost={'on' if boost else 'off'}")
    if hazard is not None:
        parts.append(f"hazard={hazard}")
    return " | ".join(parts)


def format_terminal_progress(
    event: str,
    data: Dict[str, Any],
    *,
    total_rounds: Optional[int] = None,
) -> Optional[str]:
    round_idx = data.get("round")
    round_label = f"r{int(round_idx):02d}" if isinstance(round_idx, int) else None

    if event == "session_start":
        return (
            "slither-hermes start"
            f" | rounds={data.get('rounds')}"
            f" | clip={data.get('clip_duration')}s"
            f" | frame={data.get('frame_interval')}s"
            f" | interval={data.get('clip_interval')}s"
            f" | session={data.get('duration')}s"
        )

    if event == "round_start" and round_label:
        if total_rounds:
            return f"{round_label} starting ({round_idx}/{total_rounds})"
        return f"{round_label} starting"

    if event == "joined_game" and round_label:
        rank = data.get("rank")
        return f"{round_label} joined | rank={rank if rank is not None else '—'}"

    if event == "tick" and round_label:
        movement = data.get("movement") or {}
        parts = [
            round_label,
            f"tick={data.get('tick')}",
            f"rank={data.get('rank')}",
            f"mode={data.get('mode')}",
        ]
        hazard = movement.get("nearest_hazard")
        if hazard is not None:
            parts.append(f"hazard={hazard}")
        parts.append(f"boost={'on' if movement.get('boost') else 'off'}")
        return " | ".join(parts)

    if event == "died" and round_label:
        rank = data.get("rank")
        return f"{round_label} died | rank={rank if rank is not None else 0}"

    if event == "round_timeout" and round_label:
        return f"{round_label} timeout"

    if event == "round_error" and round_label:
        return f"{round_label} error | {data.get('error')}"

    if event == "strategy_update" and round_label:
        summary = data.get("telegram_summary")
        if summary:
            return str(summary)
        adjustments = data.get("adjustments") or []
        if adjustments:
            return f"{round_label} learned | {', '.join(str(item) for item in adjustments[:3])}"
        return f"{round_label} strategy updated"

    if event == "session_summary":
        headline = data.get("telegram_summary")
        if headline:
            return headline
        return "session summary ready"

    return None


def parse_event_ts(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ).timestamp()
    except ValueError:
        return None


def median_value(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def dist_point_to_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Distance from point (px, py) to segment (ax, ay) -> (bx, by)."""
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    seg_sq = abx * abx + aby * aby
    if seg_sq <= 1e-6:
        return math.hypot(apx, apy)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / seg_sq))
    qx = ax + t * abx
    qy = ay + t * aby
    return math.hypot(px - qx, py - qy)


def make_strategy_memory() -> Dict[str, float]:
    return {
        "opening_seconds": 10.0,
        "panic_close_threshold": 170.0,
        "panic_combo_hazard_threshold": 220.0,
        "panic_combo_enemy_threshold": 260.0,
        "evade_distance": 340.0,
        "cluster_threshold": 160.0,
        "cluster_bias": 1.0,
        "food_bias": 1.0,
        "hazard_penalty_bias": 1.0,
        "repulsion_bias": 1.0,
        "boost_bias": 1.0,
    }


def summarize_strategy_memory(strategy_memory: Dict[str, float]) -> Dict[str, float]:
    return {key: round(value, 3) for key, value in strategy_memory.items()}


def build_round_report(
    *,
    round_idx: int,
    result: str,
    tick: int,
    best_rank: Optional[int],
    mode_samples: Dict[str, int],
    last_mode: Optional[str],
    min_hazard: float,
    boost_samples: int,
    decision_samples: int,
) -> Dict[str, Any]:
    dominant_mode = None
    if mode_samples:
        dominant_mode = max(mode_samples.items(), key=lambda item: item[1])[0]
    return {
        "round": round_idx,
        "result": result,
        "ticks": tick,
        "best_rank": best_rank,
        "dominant_mode": dominant_mode,
        "ended_in_mode": last_mode,
        "min_hazard": round(min_hazard, 2) if min_hazard != float("inf") else None,
        "boost_ratio": round(boost_samples / max(1, decision_samples), 3),
    }


def learn_from_round(
    strategy_memory: Dict[str, float],
    report: Dict[str, Any],
) -> Dict[str, Any]:
    adjustments: List[str] = []
    result = str(report.get("result") or "unknown")
    ticks = int(report.get("ticks") or 0)
    best_rank = report.get("best_rank")
    dominant_mode = report.get("dominant_mode")
    ended_in_mode = report.get("ended_in_mode")
    min_hazard = safe_float(report.get("min_hazard"), float("inf"))
    boost_ratio = safe_float(report.get("boost_ratio"))

    if result in {"died", "error"} and ticks <= 3:
        strategy_memory["opening_seconds"] = clamp(
            strategy_memory["opening_seconds"] + 1.2, 8.0, 15.0
        )
        strategy_memory["repulsion_bias"] = clamp(
            strategy_memory["repulsion_bias"] + 0.12, 0.9, 1.7
        )
        strategy_memory["boost_bias"] = clamp(
            strategy_memory["boost_bias"] - 0.12, 0.65, 1.2
        )
        strategy_memory["panic_close_threshold"] = clamp(
            strategy_memory["panic_close_threshold"] + 8.0, 120.0, 175.0
        )
        strategy_memory["panic_combo_enemy_threshold"] = clamp(
            strategy_memory["panic_combo_enemy_threshold"] + 12.0, 190.0, 320.0
        )
        adjustments.extend(
            ["longer opening", "stronger avoidance", "less early boost"]
        )

    if dominant_mode == "panic" or min_hazard < 120.0:
        strategy_memory["hazard_penalty_bias"] = clamp(
            strategy_memory["hazard_penalty_bias"] + 0.08, 0.9, 1.7
        )
        strategy_memory["repulsion_bias"] = clamp(
            strategy_memory["repulsion_bias"] + 0.06, 0.9, 1.7
        )
        if "more hazard spacing" not in adjustments:
            adjustments.append("more hazard spacing")

    if ended_in_mode == "mass_cluster" and result == "died":
        strategy_memory["cluster_bias"] = clamp(
            strategy_memory["cluster_bias"] - 0.08, 0.75, 1.45
        )
        strategy_memory["cluster_threshold"] = clamp(
            strategy_memory["cluster_threshold"] + 18.0, 120.0, 260.0
        )
        adjustments.append("safer cluster selection")
    elif dominant_mode == "mass_cluster" and isinstance(best_rank, int) and best_rank <= 80:
        strategy_memory["cluster_bias"] = clamp(
            strategy_memory["cluster_bias"] + 0.08, 0.75, 1.45
        )
        strategy_memory["cluster_threshold"] = clamp(
            strategy_memory["cluster_threshold"] - 10.0, 120.0, 260.0
        )
        adjustments.append("lean into dense clusters")

    if dominant_mode == "food" and isinstance(best_rank, int) and best_rank <= 120:
        strategy_memory["food_bias"] = clamp(
            strategy_memory["food_bias"] + 0.08, 0.8, 1.4
        )
        adjustments.append("favor safe food lanes")

    if boost_ratio > 0.35 and result == "died":
        strategy_memory["boost_bias"] = clamp(
            strategy_memory["boost_bias"] - 0.08, 0.65, 1.2
        )
        if "trim boost aggression" not in adjustments:
            adjustments.append("trim boost aggression")
    elif (
        boost_ratio < 0.12
        and isinstance(best_rank, int)
        and best_rank <= 70
        and result != "error"
    ):
        strategy_memory["boost_bias"] = clamp(
            strategy_memory["boost_bias"] + 0.04, 0.65, 1.2
        )
        adjustments.append("allow cleaner boosts")

    if not adjustments:
        adjustments.append("keep strategy steady")

    round_idx = int(report.get("round") or 0)
    summary = f"learned r{round_idx:02d} | " + ", ".join(adjustments[:3])
    return {
        "summary": summary,
        "adjustments": adjustments,
        "strategy_memory": summarize_strategy_memory(strategy_memory),
    }


def copy_pointer(target_path: Optional[str], pointer_path: Path) -> Optional[str]:
    if not target_path:
        return None
    source = Path(target_path)
    if not source.exists():
        return None
    shutil.copyfile(source, pointer_path)
    return str(pointer_path)


def write_session_summary(run_dir: Path) -> Optional[Dict[str, Any]]:
    log_path = run_dir / "status.jsonl"
    if not log_path.exists():
        return None

    rows: List[Dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not rows:
        return None

    rounds: Dict[int, Dict[str, Any]] = {}
    strategy_notes: List[str] = []
    longest_clip_path: Optional[str] = None
    longest_clip_frames = 0
    longest_clip_round: Optional[int] = None

    def get_round(round_idx: int) -> Dict[str, Any]:
        if round_idx not in rounds:
            rounds[round_idx] = {
                "round": round_idx,
                "ticks": 0,
                "best_rank": None,
                "joined_at": None,
                "ended_at": None,
                "best_screenshot": None,
                "best_gif": None,
                "best_gif_rank": None,
            }
        return rounds[round_idx]

    for row in rows:
        round_idx = row.get("round")
        event = row.get("event")
        if event == "strategy_update":
            note = row.get("telegram_summary")
            if isinstance(note, str) and note.strip():
                strategy_notes.append(note.strip())
        if not isinstance(round_idx, int):
            continue

        entry = get_round(round_idx)
        event_ts = parse_event_ts(row.get("ts"))
        if event == "joined_game":
            entry["joined_at"] = event_ts
        elif event in {"died", "round_timeout", "round_error"}:
            entry["ended_at"] = event_ts

        if event == "tick":
            entry["ticks"] = max(entry["ticks"], int(row.get("tick", 0)))

        rank = row.get("rank")
        numeric_rank = (
            int(rank) if isinstance(rank, (int, float)) and rank > 0 else None
        )
        if numeric_rank is not None:
            if entry["best_rank"] is None or numeric_rank < entry["best_rank"]:
                entry["best_rank"] = numeric_rank
                screenshot = row.get("screenshot")
                if screenshot:
                    entry["best_screenshot"] = screenshot

        if event == "clip" and row.get("gif"):
            frame_count = (
                int(row["frame_count"])
                if isinstance(row.get("frame_count"), (int, float))
                else 0
            )
            if frame_count > longest_clip_frames:
                longest_clip_frames = frame_count
                longest_clip_path = row["gif"]
                longest_clip_round = round_idx
            clip_rank = (
                int(row["rank"])
                if isinstance(row.get("rank"), (int, float)) and row["rank"] > 0
                else None
            )
            if entry["best_gif"] is None:
                entry["best_gif"] = row["gif"]
                entry["best_gif_rank"] = clip_rank
            elif clip_rank is not None and (
                entry["best_gif_rank"] is None or clip_rank < entry["best_gif_rank"]
            ):
                entry["best_gif"] = row["gif"]
                entry["best_gif_rank"] = clip_rank

    round_rows = [rounds[idx] for idx in sorted(rounds)]
    if not round_rows:
        return None

    survival_seconds: List[float] = []
    tick_counts: List[float] = []
    best_round: Optional[Dict[str, Any]] = None
    best_rank: Optional[int] = None

    for entry in round_rows:
        joined_at = entry.get("joined_at")
        ended_at = entry.get("ended_at")
        if joined_at is not None and ended_at is not None and ended_at >= joined_at:
            duration = round(ended_at - joined_at, 1)
            entry["survival_seconds"] = duration
            survival_seconds.append(duration)
        else:
            entry["survival_seconds"] = None

        tick_counts.append(float(entry["ticks"]))

        if entry.get("best_rank") is not None and (
            best_rank is None or entry["best_rank"] < best_rank
        ):
            best_rank = entry["best_rank"]
            best_round = entry

    median_survival = median_value(survival_seconds)
    median_ticks = median_value(tick_counts)

    best_gif_pointer = copy_pointer(
        best_round.get("best_gif") if best_round else None,
        run_dir / "best.gif",
    )
    best_png_pointer = copy_pointer(
        best_round.get("best_screenshot") if best_round else None,
        run_dir / "best.png",
    )
    longest_gif_pointer = copy_pointer(longest_clip_path, run_dir / "longest.gif")

    round_lines = [
        "| Round | Best Rank | Ticks | Survival |",
        "|-------|-----------|-------|----------|",
    ]
    for entry in round_rows:
        rank_label = (
            str(entry["best_rank"]) if entry.get("best_rank") is not None else "—"
        )
        if best_round is not None and entry["round"] == best_round["round"]:
            rank_label += " ⭐"
        survival_label = (
            f"{entry['survival_seconds']:.1f}s"
            if entry.get("survival_seconds") is not None
            else "—"
        )
        round_lines.append(
            f"| r{entry['round']:02d} | {rank_label} | {entry['ticks']} | {survival_label} |"
        )

    headline = (
        f"{len(round_rows)} rounds done! Best rank this session: {best_rank} "
        f"(r{best_round['round']:02d})"
        if best_round is not None and best_rank is not None
        else f"{len(round_rows)} rounds done!"
    )
    stats_line = " | ".join(
        part
        for part in [
            f"Median survival: {median_survival:.1f}s"
            if median_survival is not None
            else None,
            f"Median ticks: {median_ticks:.1f}"
            if median_ticks is not None
            else None,
        ]
        if part
    )

    summary_lines = [headline]
    if stats_line:
        summary_lines.append("")
        summary_lines.append(stats_line)
    summary_lines.append("")
    summary_lines.extend(round_lines)
    if best_gif_pointer or best_png_pointer:
        summary_lines.append("")
        summary_lines.append("## Best Artifacts")
        if best_gif_pointer:
            summary_lines.append(f"- GIF: `{best_gif_pointer}`")
        if best_png_pointer:
            summary_lines.append(f"- PNG: `{best_png_pointer}`")
        if longest_gif_pointer:
            longest_label = f"`{longest_gif_pointer}`"
            if longest_clip_round is not None and longest_clip_frames > 0:
                longest_label += (
                    f" (r{longest_clip_round:02d}, {longest_clip_frames} frames)"
                )
            summary_lines.append(f"- Longest GIF: {longest_label}")
    if strategy_notes:
        summary_lines.append("")
        summary_lines.append("## Strategy Adaptation")
        for note in strategy_notes:
            summary_lines.append(f"- {note}")

    summary_text = "\n".join(summary_lines) + "\n"
    summary_path = run_dir / "summary.md"
    summary_path.write_text(summary_text, encoding="utf-8")

    return {
        "summary_path": str(summary_path),
        "headline": headline,
        "median_survival_seconds": round(median_survival, 1)
        if median_survival is not None
        else None,
        "median_ticks": round(median_ticks, 1) if median_ticks is not None else None,
        "best_round": best_round["round"] if best_round is not None else None,
        "best_rank": best_rank,
        "best_gif": best_gif_pointer,
        "best_png": best_png_pointer,
        "longest_gif": longest_gif_pointer,
        "longest_gif_frames": longest_clip_frames if longest_clip_frames > 0 else None,
        "longest_gif_round": longest_clip_round,
        "rounds": [
            {
                "round": entry["round"],
                "best_rank": entry.get("best_rank"),
                "ticks": entry["ticks"],
                "survival_seconds": entry.get("survival_seconds"),
            }
            for entry in round_rows
        ],
    }


def save_screenshot(
    page: Any,
    output_dir: Path,
    name: str,
    latest_root: Optional[Path] = None,
) -> str:
    path = output_dir / name
    page.screenshot(path=str(path), full_page=True)
    latest_dir = latest_root or output_dir
    latest = latest_dir / "latest.png"
    shutil.copyfile(path, latest)
    return str(path)


def save_live_frame(page: Any, frame_path: Path, live_root: Path) -> None:
    page.screenshot(path=str(frame_path), full_page=False)
    shutil.copyfile(frame_path, live_root / "live.png")


def build_gif(
    frame_paths: List[Path],
    output_path: Path,
    frame_interval: float,
    latest_root: Optional[Path] = None,
) -> Optional[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or len(frame_paths) < 2:
        return None

    temp_dir = output_path.parent / f".{output_path.stem}_frames"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, frame_path in enumerate(frame_paths):
            shutil.copyfile(frame_path, temp_dir / f"frame_{idx:04d}.png")

        fps = max(1.0, min(16.0, 1.0 / max(frame_interval, 0.08)))
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            f"{fps:.2f}",
            "-i",
            str(temp_dir / "frame_%04d.png"),
            "-vf",
            "scale=720:-1:flags=lanczos",
            "-loop",
            "0",
            str(output_path),
        ]
        subprocess.run(command, check=True)
    except Exception:
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    latest_dir = latest_root or output_path.parent
    latest = latest_dir / "latest.gif"
    shutil.copyfile(output_path, latest)
    return str(output_path)


def page_state(page: Any) -> Dict[str, Any]:
    return page.evaluate(
        """() => {
        const centerX = window.view_xx ?? 0;
        const centerY = window.view_yy ?? 0;
        const foods = Array.isArray(window.foods)
          ? window.foods.filter(Boolean).slice(0, 200).map((f) => ({
              xx: f.xx ?? null,
              yy: f.yy ?? null,
              sz: f.sz ?? 0,
              rsp: f.rsp ?? 0
            }))
          : [];
        const snakes = window.os && typeof window.os === "object"
          ? Object.values(window.os)
              .filter(Boolean)
              .sort((a, b) => {
                const adx = (a.xx ?? 0) - centerX;
                const ady = (a.yy ?? 0) - centerY;
                const bdx = (b.xx ?? 0) - centerX;
                const bdy = (b.yy ?? 0) - centerY;
                return adx * adx + ady * ady - (bdx * bdx + bdy * bdy);
              })
              .slice(0, 12)
              .map((s) => ({
                id: s.id ?? null,
                xx: s.xx ?? null,
                yy: s.yy ?? null,
                ang: s.ang ?? null,
                eang: s.eang ?? null,
                wang: s.wang ?? null,
                sp: s.sp ?? null,
                sc: s.sc ?? null,
                fam: s.fam ?? null,
                nk: s.nk ?? null,
                na: s.na ?? null,
                dead: !!s.dead,
                alive_amt: s.alive_amt ?? null,
                body_points: Array.isArray(s.pts)
                  ? s.pts.slice(0, 8).map((pt) => ({
                      xx: pt.xx ?? null,
                      yy: pt.yy ?? null,
                      dying: !!pt.dying,
                    }))
                  : [],
              }))
          : [];
        return {
          href: location.href,
          title: document.title,
          playing: !!window.playing,
          connected: !!window.connected,
          my_nick: window.my_nick || null,
          rank: window.rank ?? null,
          best_rank: window.best_rank ?? null,
          view_xx: window.view_xx ?? null,
          view_yy: window.view_yy ?? null,
          xm: window.xm ?? null,
          ym: window.ym ?? null,
          ang: window.ang ?? null,
          want_e: !!window.want_e,
          fps: window.fps ?? null,
          dead_mtm: window.dead_mtm ?? null,
          foods,
          snakes,
        };
      }"""
    )


def get_visible_text_on_death(page: Any) -> List[str]:
    """Query visible DOM text only when we're about to log death (not in hot loop)."""
    result = page.evaluate(
        """() => {
        return Array.from(document.querySelectorAll("div, span, a"))
          .filter((el) => el.offsetParent !== null)
          .map((el) => (el.innerText || "").trim())
          .filter(Boolean)
          .slice(0, 20);
        }"""
    )
    return result if isinstance(result, list) else []


def enrich_state(state: Dict[str, Any]) -> Dict[str, Any]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    snakes = state.get("snakes") or []

    def dist_sq(snake: Dict[str, Any]) -> float:
        dx = safe_float(snake.get("xx")) - center_x
        dy = safe_float(snake.get("yy")) - center_y
        return dx * dx + dy * dy

    self_snake: Optional[Dict[str, Any]] = None
    enemy_snakes: List[Dict[str, Any]] = []
    if snakes:
        ordered = sorted(snakes, key=dist_sq)
        self_snake = ordered[0]
        enemy_snakes = ordered[1:]

    state["self_snake"] = self_snake
    state["enemy_snakes"] = enemy_snakes
    return state


def project_snake_head(snake: Dict[str, Any], frames: float = 28.0) -> Tuple[float, float]:
    angle = safe_float(
        snake.get("eang")
        if snake.get("eang") is not None
        else snake.get("ang")
    )
    speed = safe_float(snake.get("sp"), 5.8)
    xx = safe_float(snake.get("xx"))
    yy = safe_float(snake.get("yy"))
    distance = max(60.0, min(220.0, speed * frames))
    return (
        xx + math.cos(angle) * distance,
        yy + math.sin(angle) * distance,
    )


def nearest_enemy_summary(
    center_x: float,
    center_y: float,
    enemies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    nearest: Dict[str, Any] = {
        "dist": float("inf"),
        "dx": 0.0,
        "dy": 0.0,
        "snake": None,
    }
    for enemy in enemies:
        ex = safe_float(enemy.get("xx"))
        ey = safe_float(enemy.get("yy"))
        dx = ex - center_x
        dy = ey - center_y
        dist = math.hypot(dx, dy)
        if dist < nearest["dist"]:
            nearest = {
                "dist": dist,
                "dx": dx,
                "dy": dy,
                "snake": enemy,
            }
    return nearest


def angle_delta(a: float, b: float) -> float:
    return math.atan2(math.sin(a - b), math.cos(a - b))


def collect_hazard_points(
    state: Dict[str, Any],
) -> List[Tuple[float, float, float, str]]:
    enemies = state.get("enemy_snakes") or []
    hazards: List[Tuple[float, float, float, str]] = []

    for enemy in enemies[:12]:
        pred_x, pred_y = project_snake_head(enemy, frames=28.0)
        hazards.append((pred_x, pred_y, 3.2, "enemy_head"))
        hazards.append(
            (
                safe_float(enemy.get("xx")),
                safe_float(enemy.get("yy")),
                2.0,
                "enemy_core",
            )
        )
        for pt in (enemy.get("body_points") or [])[:12]:
            hazards.append(
                (
                    safe_float(pt.get("xx")),
                    safe_float(pt.get("yy")),
                    1.2,
                    "enemy_body",
                )
            )

    return hazards


def nearest_hazard_summary(
    center_x: float,
    center_y: float,
    hazards: List[Tuple[float, float, float, str]],
) -> Dict[str, Any]:
    nearest = {
        "dist": float("inf"),
        "xx": None,
        "yy": None,
        "weight": 0.0,
        "kind": None,
    }
    for hx, hy, weight, kind in hazards:
        dist = math.hypot(hx - center_x, hy - center_y)
        if dist < nearest["dist"]:
            nearest = {
                "dist": dist,
                "xx": hx,
                "yy": hy,
                "weight": weight,
                "kind": kind,
            }
    return nearest


def choose_opening_lane(
    state: Dict[str, Any],
    hazards: List[Tuple[float, float, float, str]],
    *,
    elapsed_seconds: float,
    opening_window_seconds: float = 10.0,
) -> Tuple[float, float, Dict[str, Any]]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    current_heading = safe_float(state.get("ang"))
    best_score = float("-inf")
    best_angle = current_heading
    best_clearance = 0.0

    for idx in range(18):
        angle = current_heading + (idx / 18.0) * (2 * math.pi)
        dir_x = math.cos(angle)
        dir_y = math.sin(angle)
        score = 0.0
        min_clearance = 1200.0

        for hx, hy, weight, _kind in hazards:
            rel_x = hx - center_x
            rel_y = hy - center_y
            dist = math.hypot(rel_x, rel_y)
            if dist <= 1:
                score -= 5000.0
                min_clearance = 0.0
                continue

            forward = rel_x * dir_x + rel_y * dir_y
            if forward <= -40.0:
                continue

            lateral = abs((-dir_y * rel_x) + (dir_x * rel_y))
            corridor = 105.0 + min(150.0, dist * 0.18)

            if lateral <= corridor:
                alignment = max(0.0, min(1.0, forward / dist))
                score -= weight * alignment * 1850.0 / max(40.0, dist)
                min_clearance = min(min_clearance, dist)
            elif forward > 0:
                score -= weight * 90.0 / max(dist + lateral, 120.0)

        score += min(min_clearance, 950.0) * 0.03
        score -= abs(angle_delta(angle, current_heading)) * 20.0

        if score > best_score:
            best_score = score
            best_angle = angle
            best_clearance = min_clearance

    target_distance = 960.0
    return (
        center_x + math.cos(best_angle) * target_distance,
        center_y + math.sin(best_angle) * target_distance,
        {
            "mode": "opening",
            "lane_score": round(best_score, 2),
            "opening_remaining": round(
                max(0.0, opening_window_seconds - elapsed_seconds), 2
            ),
            "lane_clearance": round(best_clearance, 2),
        },
    )


def choose_panic_escape(
    state: Dict[str, Any],
    hazards: List[Tuple[float, float, float, str]],
    *,
    nearest_enemy_dist: float,
) -> Tuple[float, float, Dict[str, Any]]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    current_heading = safe_float(state.get("ang"))
    force_x = math.cos(current_heading) * 0.15
    force_y = math.sin(current_heading) * 0.15
    nearest_hazard = float("inf")

    for hx, hy, weight, kind in hazards:
        dx = center_x - hx
        dy = center_y - hy
        dist = math.hypot(dx, dy)
        nearest_hazard = min(nearest_hazard, dist)
        if dist <= 1 or dist >= 430.0:
            continue
        scale = weight * ((430.0 - dist) / 430.0) ** 2
        if kind == "enemy_head":
            scale *= 1.35
        if dist < 150.0:
            scale *= 1.6
        force_x += dx / dist * scale
        force_y += dy / dist * scale

    force_mag = math.hypot(force_x, force_y)
    if force_mag <= 0.05:
        escape_angle = current_heading + math.pi
        force_x = math.cos(escape_angle)
        force_y = math.sin(escape_angle)
        force_mag = 1.0

    force_x /= force_mag
    force_y /= force_mag
    return (
        center_x + force_x * 1100.0,
        center_y + force_y * 1100.0,
        {
            "mode": "panic",
            "nearest_enemy_dist": round(nearest_enemy_dist, 2)
            if nearest_enemy_dist != float("inf")
            else None,
            "nearest_hazard": round(nearest_hazard, 2)
            if nearest_hazard != float("inf")
            else None,
        },
    )


def choose_target(
    state: Dict[str, Any],
    *,
    elapsed_seconds: float,
    strategy_memory: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, Dict[str, Any]]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    foods = state.get("foods") or []
    enemies = state.get("enemy_snakes") or []
    hazards = collect_hazard_points(state)
    strategy_memory = strategy_memory or {}
    panic_close_threshold = safe_float(
        strategy_memory.get("panic_close_threshold"), 190.0
    )
    panic_combo_hazard_threshold = safe_float(
        strategy_memory.get("panic_combo_hazard_threshold"), 250.0
    )
    panic_combo_enemy_threshold = safe_float(
        strategy_memory.get("panic_combo_enemy_threshold"), 300.0
    )
    opening_seconds = safe_float(strategy_memory.get("opening_seconds"), 10.0)
    evade_distance = safe_float(strategy_memory.get("evade_distance"), 390.0)
    food_bias = safe_float(strategy_memory.get("food_bias"), 1.0)
    hazard_penalty_bias = safe_float(
        strategy_memory.get("hazard_penalty_bias"), 1.0
    )

    nearest_enemy = nearest_enemy_summary(center_x, center_y, enemies)
    nearest_enemy_dist = nearest_enemy["dist"]
    nearest_hazard = nearest_hazard_summary(center_x, center_y, hazards)

    if (
        nearest_hazard["dist"] < panic_close_threshold
        or (
            nearest_hazard["dist"] < panic_combo_hazard_threshold
            and nearest_enemy_dist < panic_combo_enemy_threshold
        )
    ):
        return choose_panic_escape(
            state,
            hazards,
            nearest_enemy_dist=nearest_enemy_dist,
        )

    if elapsed_seconds < opening_seconds:
        return choose_opening_lane(
            state,
            hazards,
            elapsed_seconds=elapsed_seconds,
            opening_window_seconds=opening_seconds,
        )

    if nearest_enemy_dist < evade_distance and nearest_enemy["snake"] is not None:
        pred_x, pred_y = project_snake_head(nearest_enemy["snake"], frames=26.0)
        dx = pred_x - center_x
        dy = pred_y - center_y
        return (
            center_x - dx * 1.9,
            center_y - dy * 1.9,
            {
                "mode": "evade",
                "nearest_enemy_dist": round(nearest_enemy_dist, 2),
                "predicted_enemy_x": round(pred_x, 2),
                "predicted_enemy_y": round(pred_y, 2),
            },
        )

    candidate_rows: List[Tuple[float, Dict[str, Any], float]] = []
    for food in foods:
        fx = safe_float(food.get("xx"))
        fy = safe_float(food.get("yy"))
        dist = math.hypot(fx - center_x, fy - center_y)
        if dist <= 1 or dist > 2200:
            continue
        local_score = (safe_float(food.get("sz")) * 36.0 - dist) * food_bias
        candidate_rows.append((local_score, food, dist))

    candidate_rows.sort(key=lambda item: item[0], reverse=True)
    best_food: Optional[Dict[str, Any]] = None
    best_meta: Dict[str, Any] = {"mode": "wander"}
    best_score = float("-inf")

    for local_score, food, dist in candidate_rows[:15]:
        fx = safe_float(food.get("xx"))
        fy = safe_float(food.get("yy"))

        blocked_by_enemy = False
        enemy_penalty = 0.0
        for enemy in enemies[:12]:
            ex = safe_float(enemy.get("xx"))
            ey = safe_float(enemy.get("yy"))
            enemy_dist = math.hypot(fx - ex, fy - ey)
            if enemy_dist < 210:
                blocked_by_enemy = True
                break
            if enemy_dist < 230:
                enemy_penalty += 950 * hazard_penalty_bias
            elif enemy_dist < 320:
                enemy_penalty += 280 * hazard_penalty_bias

            for pt in (enemy.get("body_points") or [])[:4]:
                px = safe_float(pt.get("xx"))
                py = safe_float(pt.get("yy"))
                body_dist = math.hypot(fx - px, fy - py)
                if body_dist < 165:
                    blocked_by_enemy = True
                    break
                if body_dist < 200:
                    enemy_penalty += 260 * hazard_penalty_bias
            if blocked_by_enemy:
                break

        if blocked_by_enemy:
            continue

        score = local_score - enemy_penalty
        if score > best_score:
            best_score = score
            best_food = food
            best_meta = {
                "mode": "food",
                "score": round(score, 2),
                "nearest_enemy_dist": round(nearest_enemy_dist, 2)
                if nearest_enemy_dist != float("inf")
                else None,
                "target_distance": round(dist, 2),
            }

    if best_food:
        return (
            safe_float(best_food.get("xx")),
            safe_float(best_food.get("yy")),
            best_meta,
        )

    angle = time.time() % (2 * math.pi)
    return (
        center_x + math.cos(angle) * 800,
        center_y + math.sin(angle) * 800,
        {"mode": "wander"},
    )


def resolve_steering(
    state: Dict[str, Any],
    target_x: float,
    target_y: float,
    target_meta: Dict[str, Any],
    *,
    elapsed_seconds: float,
    strategy_memory: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, Dict[str, Any]]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    enemies = state.get("enemy_snakes") or []
    strategy_memory = strategy_memory or {}
    repulsion_bias = safe_float(strategy_memory.get("repulsion_bias"), 1.0)
    boost_bias = clamp(safe_float(strategy_memory.get("boost_bias"), 1.0), 0.65, 1.2)

    target_dx = target_x - center_x
    target_dy = target_y - center_y
    target_mag = math.hypot(target_dx, target_dy) or 1.0
    force_x = target_dx / target_mag
    force_y = target_dy / target_mag
    mode = target_meta.get("mode")
    if mode == "panic":
        force_scale = 0.25
        repulsion_scale = 1.45
    elif mode == "opening":
        force_scale = 0.6
        repulsion_scale = 1.15
    elif mode == "evade":
        force_scale = 0.45
        repulsion_scale = 1.2
    else:
        force_scale = 1.15
        repulsion_scale = 1.0
    repulsion_scale *= repulsion_bias
    force_x *= force_scale
    force_y *= force_scale

    nearest_hazard = float("inf")

    def add_repulsion(
        hx: float,
        hy: float,
        radius: float,
        weight: float,
    ) -> None:
        nonlocal force_x, force_y, nearest_hazard
        dx = center_x - hx
        dy = center_y - hy
        dist = math.hypot(dx, dy)
        nearest_hazard = min(nearest_hazard, dist)
        if dist <= 1 or dist >= radius:
            return
        scale = weight * ((radius - dist) / radius) ** 2
        force_x += dx / dist * scale
        force_y += dy / dist * scale

    for enemy in enemies[:10]:
        pred_x, pred_y = project_snake_head(enemy, frames=28.0)
        add_repulsion(
            pred_x,
            pred_y,
            radius=420.0,
            weight=2.8 * repulsion_scale,
        )
        add_repulsion(
            safe_float(enemy.get("xx")),
            safe_float(enemy.get("yy")),
            radius=280.0,
            weight=1.8 * repulsion_scale,
        )
        for pt in (enemy.get("body_points") or [])[:10]:
            add_repulsion(
                safe_float(pt.get("xx")),
                safe_float(pt.get("yy")),
                radius=165.0,
                weight=1.1 * repulsion_scale,
            )

    final_mag = math.hypot(force_x, force_y)
    if final_mag <= 0.05:
        final_x = target_dx
        final_y = target_dy
        final_mag = math.hypot(final_x, final_y) or 1.0
    else:
        final_x = force_x / final_mag
        final_y = force_y / final_mag

    nearest_enemy_dist = safe_float(target_meta.get("nearest_enemy_dist"), 9999.0)
    desired_angle = math.atan2(final_y, final_x)
    current_angle = safe_float(state.get("ang"))
    turn_angle = abs(angle_delta(desired_angle, current_angle))
    should_boost = False
    boost_confidence = max(0.65, boost_bias)
    boost_clearance = 1.0 + max(0.0, 1.0 - boost_bias)
    if (
        mode == "evade"
        and nearest_enemy_dist < 210
        and nearest_hazard > 260 * boost_clearance
        and turn_angle < 0.32
    ):
        should_boost = True
    elif (
        mode == "food"
        and target_meta.get("target_distance", 0) > 1050 / boost_confidence
        and nearest_enemy_dist > 1100 * boost_clearance
        and nearest_hazard > 520 * boost_clearance
        and turn_angle < 0.24
    ):
        should_boost = True

    if (
        elapsed_seconds < 14.0
        or mode in {"opening", "panic"}
        or nearest_hazard < 260
        or nearest_enemy_dist < 650
        or turn_angle > 0.48
    ):
        should_boost = False

    steering_distance = 920.0 if not should_boost else 1200.0
    return (
        center_x + final_x * steering_distance,
        center_y + final_y * steering_distance,
        {
            "boost": should_boost,
            "nearest_hazard": round(nearest_hazard, 2)
            if nearest_hazard != float("inf")
            else None,
            "turn_angle": round(turn_angle, 3),
        },
    )


def set_boost(page: Any, boosting: bool, want_boost: bool) -> bool:
    if want_boost and not boosting:
        page.mouse.down()
        return True
    if boosting and not want_boost:
        page.mouse.up()
        return False
    return boosting


def move_toward(
    page: Any,
    state: Dict[str, Any],
    target_x: float,
    target_y: float,
    width: int,
    height: int,
) -> Dict[str, Any]:
    center_x = safe_float(state.get("view_xx"))
    center_y = safe_float(state.get("view_yy"))
    dx = target_x - center_x
    dy = target_y - center_y
    magnitude = math.hypot(dx, dy) or 1.0
    reach = max(140.0, min(360.0, magnitude / 4.0))
    mouse_x = width / 2 + dx / magnitude * reach
    mouse_y = height / 2 + dy / magnitude * reach
    mouse_x = max(40.0, min(width - 40.0, mouse_x))
    mouse_y = max(40.0, min(height - 40.0, mouse_y))
    page.mouse.move(mouse_x, mouse_y, steps=2)
    return {
        "mouse_x": round(mouse_x, 2),
        "mouse_y": round(mouse_y, 2),
        "world_dx": round(dx, 2),
        "world_dy": round(dy, 2),
    }


def run_round(
    page: Any,
    args: argparse.Namespace,
    logger: Logger,
    run_dir: Path,
    round_idx: int,
    strategy_memory: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    round_tag = f"{round_idx:02d}"
    round_dir = run_dir / f"round_{round_tag}"
    ensure_dir(round_dir)
    frames_dir = round_dir / "frames"
    ensure_dir(frames_dir)
    boosting = False
    strategy_memory = strategy_memory or {}
    mode_samples: Dict[str, int] = {}
    best_rank: Optional[int] = None
    min_hazard = float("inf")
    last_mode: Optional[str] = None
    boost_samples = 0
    decision_samples = 0
    logger.emit(
        "round_start",
        round=round_idx,
        nickname=args.nickname,
        round_dir=str(round_dir),
    )

    response = page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(args.join_wait_ms)
    page.locator("#nick").fill(args.nickname)

    landing_name = f"landing_round_{round_tag}.png"
    landing_path = save_screenshot(page, round_dir, landing_name, latest_root=run_dir)
    logger.emit(
        "landing_ready",
        round=round_idx,
        status=response.status if response else None,
        screenshot=landing_path,
    )

    page.locator("#playh").click(force=True, timeout=10000)
    page.wait_for_function(
        "() => !!window.playing && !!window.connected", timeout=15000
    )
    page.wait_for_timeout(1800)

    joined_name = f"joined_round_{round_tag}.png"
    joined_path = save_screenshot(page, round_dir, joined_name, latest_root=run_dir)
    state = enrich_state(page_state(page))
    joined_rank = state.get("rank")
    if isinstance(joined_rank, (int, float)) and joined_rank > 0:
        best_rank = int(joined_rank)
    logger.emit(
        "joined_game",
        round=round_idx,
        screenshot=joined_path,
        rank=state.get("rank"),
        my_nick=state.get("my_nick"),
        telegram_summary=format_telegram_summary(
            prefix=f"joined r{round_idx}",
            rank=state.get("rank"),
        ),
    )
    live_started_at = time.time()

    recent_frames: List[Dict[str, Any]] = []
    frame_index = 0
    clip_index = 0
    next_frame_capture = time.time()
    next_capture = time.time() + args.interval
    next_clip = time.time() + args.clip_interval
    tick = 0
    while True:
        now = time.time()
        state = enrich_state(page_state(page))
        elapsed_seconds = now - live_started_at
        if not state.get("playing") or not state.get("connected"):
            boosting = set_boost(page, boosting, False)
            clip_frames = [
                Path(frame["path"])
                for frame in recent_frames
                if frame["ts"] >= time.time() - args.clip_duration
            ]
            if clip_frames:
                clip_index += 1
                clip_name = f"clip_{round_tag}_{clip_index:04d}.gif"
                clip_path = build_gif(
                    clip_frames,
                    round_dir / clip_name,
                    args.frame_interval,
                    latest_root=run_dir,
                )
                if clip_path:
                    logger.emit(
                        "clip",
                        round=round_idx,
                        clip=clip_index,
                        gif=clip_path,
                        frame_count=len(clip_frames),
                        phase="death",
                        rank=state.get("rank"),
                        telegram_summary=format_telegram_summary(
                            prefix=f"gif r{round_idx}",
                            rank=state.get("rank"),
                            mode="death",
                        ),
                    )
            died_name = f"died_round_{round_tag}.png"
            died_path = save_screenshot(page, round_dir, died_name, latest_root=run_dir)
            visible_text = get_visible_text_on_death(page)
            logger.emit(
                "died",
                round=round_idx,
                screenshot=died_path,
                rank=state.get("rank"),
                visible_text=visible_text,
                telegram_summary=format_telegram_summary(
                    prefix=f"died r{round_idx}",
                    rank=state.get("rank"),
                ),
            )
            return build_round_report(
                round_idx=round_idx,
                result="died",
                tick=tick,
                best_rank=best_rank,
                mode_samples=mode_samples,
                last_mode=last_mode,
                min_hazard=min_hazard,
                boost_samples=boost_samples,
                decision_samples=decision_samples,
            )

        if now >= next_frame_capture:
            frame_index += 1
            frame_path = frames_dir / f"frame_{round_tag}_{frame_index:04d}.png"
            save_live_frame(page, frame_path, run_dir)
            recent_frames.append({"path": frame_path, "ts": now})
            keep_after = now - max(args.clip_duration + 2.0, args.frame_interval * 4.0)
            kept_frames: List[Dict[str, Any]] = []
            for frame in recent_frames:
                if frame["ts"] >= keep_after:
                    kept_frames.append(frame)
                else:
                    Path(frame["path"]).unlink(missing_ok=True)
            recent_frames = kept_frames
            next_frame_capture = now + args.frame_interval

        target_x, target_y, target_meta = choose_target(
            state,
            elapsed_seconds=elapsed_seconds,
            strategy_memory=strategy_memory,
        )
        steer_x, steer_y, steering_meta = resolve_steering(
            state,
            target_x,
            target_y,
            target_meta,
            elapsed_seconds=elapsed_seconds,
            strategy_memory=strategy_memory,
        )
        boosting = set_boost(page, boosting, steering_meta.get("boost", False))
        movement = move_toward(page, state, steer_x, steer_y, args.width, args.height)
        movement["boost"] = boosting
        movement["nearest_hazard"] = steering_meta.get("nearest_hazard")
        movement["turn_angle"] = steering_meta.get("turn_angle")
        mode_name = str(target_meta.get("mode") or "wander")
        mode_samples[mode_name] = mode_samples.get(mode_name, 0) + 1
        last_mode = mode_name
        decision_samples += 1
        if boosting:
            boost_samples += 1
        hazard_value = steering_meta.get("nearest_hazard")
        if isinstance(hazard_value, (int, float)):
            min_hazard = min(min_hazard, float(hazard_value))
        rank_value = state.get("rank")
        if isinstance(rank_value, (int, float)) and rank_value > 0:
            rank_int = int(rank_value)
            if best_rank is None or rank_int < best_rank:
                best_rank = rank_int

        if now >= next_capture:
            tick += 1
            shot_name = f"tick_{round_tag}_{tick:04d}.png"
            shot_path = save_screenshot(page, round_dir, shot_name, latest_root=run_dir)
            logger.emit(
                "tick",
                round=round_idx,
                tick=tick,
                screenshot=shot_path,
                rank=state.get("rank"),
                mode=target_meta.get("mode"),
                target=target_meta,
                movement=movement,
                steering=steering_meta,
                telegram_summary=format_telegram_summary(
                    prefix=f"tick {tick}",
                    rank=state.get("rank"),
                    mode=target_meta.get("mode"),
                    boost=movement.get("boost"),
                    hazard=movement.get("nearest_hazard"),
                ),
            )
            next_capture = now + args.interval

        if now >= next_clip:
            clip_frames = [
                Path(frame["path"])
                for frame in recent_frames
                if frame["ts"] >= now - args.clip_duration
            ]
            if len(clip_frames) >= 2:
                clip_index += 1
                clip_name = f"clip_{round_tag}_{clip_index:04d}.gif"
                clip_path = build_gif(
                    clip_frames,
                    round_dir / clip_name,
                    args.frame_interval,
                    latest_root=run_dir,
                )
                if clip_path:
                    logger.emit(
                        "clip",
                        round=round_idx,
                        clip=clip_index,
                        gif=clip_path,
                        frame_count=len(clip_frames),
                        rank=state.get("rank"),
                        mode=target_meta.get("mode"),
                        steering=steering_meta,
                        telegram_summary=format_telegram_summary(
                            prefix=f"gif {clip_index}",
                            rank=state.get("rank"),
                            mode=target_meta.get("mode"),
                            boost=steering_meta.get("boost"),
                            hazard=steering_meta.get("nearest_hazard"),
                        ),
                    )
            next_clip = now + args.clip_interval

        page.wait_for_timeout(args.tick_ms)

def main() -> int:
    args = parse_args()
    if args.clip_interval is None:
        args.clip_interval = args.interval
    base_output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_dir(base_output_dir)
    run_dir = make_run_dir(base_output_dir)
    update_current_pointer(base_output_dir, run_dir)
    write_peek_dashboard(run_dir)
    write_peek_redirect(base_output_dir)
    logger = Logger(run_dir, verbose_stdout=args.verbose_stdout)
    strategy_memory = make_strategy_memory()

    executable = detect_chromium()
    logger.emit(
        "session_start",
        output_dir=str(run_dir),
        base_output_dir=str(base_output_dir),
        nickname=args.nickname,
        duration=args.duration,
        rounds=args.rounds,
        clip_interval=args.clip_interval,
        clip_duration=args.clip_duration,
        executable=str(executable) if executable else None,
        headless=not args.headed,
        telegram_summary=(
            "start"
            f" | rounds={args.rounds}"
            f" | clip={args.clip_duration:g}s"
            f" | frame={args.frame_interval:g}s"
            f" | interval={args.interval:g}s"
        ),
    )

    session_deadline = time.time() + args.duration if args.duration > 0 else None
    launch_kwargs: Dict[str, Any] = {"headless": not args.headed}
    if executable:
        launch_kwargs["executable_path"] = str(executable)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_kwargs)
        try:
            for round_idx in range(1, args.rounds + 1):
                if session_deadline is not None and time.time() >= session_deadline:
                    break
                page = browser.new_page(
                    viewport={"width": args.width, "height": args.height}
                )
                round_report: Dict[str, Any]
                try:
                    round_report = run_round(
                        page,
                        args,
                        logger,
                        run_dir,
                        round_idx,
                        strategy_memory=strategy_memory,
                    )
                except PlaywrightTimeoutError as exc:
                    logger.emit("round_error", round=round_idx, error=f"timeout: {exc}")
                    round_report = {
                        "round": round_idx,
                        "result": "error",
                        "ticks": 0,
                        "best_rank": None,
                        "dominant_mode": None,
                        "ended_in_mode": None,
                        "min_hazard": None,
                        "boost_ratio": 0.0,
                    }
                except PlaywrightError as exc:
                    logger.emit("round_error", round=round_idx, error=str(exc))
                    round_report = {
                        "round": round_idx,
                        "result": "error",
                        "ticks": 0,
                        "best_rank": None,
                        "dominant_mode": None,
                        "ended_in_mode": None,
                        "min_hazard": None,
                        "boost_ratio": 0.0,
                    }
                finally:
                    page.close()
                learning = learn_from_round(strategy_memory, round_report)
                logger.emit(
                    "strategy_update",
                    round=round_idx,
                    round_report=round_report,
                    adjustments=learning.get("adjustments"),
                    strategy_memory=learning.get("strategy_memory"),
                    telegram_summary=learning.get("summary"),
                )
        finally:
            browser.close()

    summary = write_session_summary(run_dir)
    if summary is not None:
        logger.emit(
            "session_summary",
            summary_path=summary.get("summary_path"),
            best_round=summary.get("best_round"),
            best_rank=summary.get("best_rank"),
            median_survival_seconds=summary.get("median_survival_seconds"),
            median_ticks=summary.get("median_ticks"),
            best_gif=summary.get("best_gif"),
            best_png=summary.get("best_png"),
            longest_gif=summary.get("longest_gif"),
            longest_gif_frames=summary.get("longest_gif_frames"),
            longest_gif_round=summary.get("longest_gif_round"),
            rounds=summary.get("rounds"),
            telegram_summary=summary.get("headline"),
        )
    logger.emit(
        "session_end",
        output_dir=str(run_dir),
        summary_path=summary.get("summary_path") if summary else None,
        best_gif=summary.get("best_gif") if summary else None,
        longest_gif=summary.get("longest_gif") if summary else None,
    )
    if not args.verbose_stdout:
        print(
            f"slither-hermes finished. Artifacts: {run_dir} | Peek: {base_output_dir / 'peek.html'}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
