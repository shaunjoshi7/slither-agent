# slither-agent

An autonomous, **self-improving** slither.io agent. It plays the game, learns from each round, and adapts its strategy — getting better over time without human intervention.

Built as a [Hermes](https://github.com/shaunjoshi7) skill: the LLM drives a real browser via Playwright, observes live game state, steers the snake, and narrates what's happening through GIF clips and Telegram updates.

## How it works

- **Browser automation** — Playwright controls a headless Chromium instance and injects lightweight JavaScript to read live game state (position, rank, nearby snakes, food density) directly from the page.
- **Autonomous steering** — on every tick the agent evaluates its surroundings and picks a direction: chase food, avoid heads, boost to cut off targets, or panic-escape when cornered.
- **Self-improvement** — after each round ends, the agent reads its own performance log, identifies what killed it, and writes a strategy update that carries forward into the next round. No retraining, no checkpoints — just in-context reasoning over the session history.
- **Live dashboard** — a local `peek.html` dashboard updates in real time with a live frame, GIF clips, round telemetry, and session summary.
- **GIF clips & Telegram** — every 10 seconds a GIF clip is rendered and optionally sent to Telegram so you can watch the agent play from your phone.

## Self-improvement loop

```
round ends → agent reads status.jsonl → reasons about cause of death
           → writes strategy_update event → next round inherits updated heuristics
```

Each round the agent can adjust: aggression level, boost thresholds, food-vs-kill priority, edge avoidance radius, and panic sensitivity. Over a long session it converges toward a playstyle suited to the current server conditions.

## Quick start

```bash
python3 -m venv .venv
./.venv/bin/pip install playwright
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python -m playwright install chromium

PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python slither-hermes/scripts/slither_hermes.py \
  --nickname hermetic --output-dir slither-run --rounds 10
```

Open `slither-run/peek.html` (or `slither-run/current/peek.html`) in a browser to watch the live dashboard.

## Key flags

| Flag | Default | Description |
|---|---|---|
| `--nickname` | `hermetic` | In-game name |
| `--output-dir` | `slither-run` | Where artifacts are saved |
| `--rounds` | `1` | How many rounds to play |
| `--interval` | `5` | Seconds between ticks |
| `--clip-duration` | `10` | GIF clip length in seconds |
| `--duration` | `21600` | Session ceiling in seconds |

## Skill path

`slither-hermes/` — installable under `~/.hermes/skills/gaming/slither-hermes/` for use with the Hermes agent CLI.

See `slither-hermes/SKILL.md` for the full Hermes procedure and `slither-hermes/references/usage.md` for example prompts and Telegram setup.
