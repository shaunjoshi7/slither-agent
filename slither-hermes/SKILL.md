---
name: slither-hermes
description: Autonomously play slither.io from the Hermes CLI using Playwright, longer GIF clips, lightweight in-page state, and cross-round strategy adaptation. Use when the user mentions slither.io, a Hermes game demo, hermetic, Telegram gameplay clips, or a hackathon browser-agent showcase.
version: 1.0.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [gaming, slither, playwright, browser-automation, screenshots, demo]
    category: gaming
    requires_toolsets: [terminal, file]
---
# Slither Hermes

Drive `slither.io` from the Hermes CLI with a local Playwright script.

The script joins the game, steers toward nearby food using in-page state,
captures periodic screenshots, renders 10-second GIF clips, writes a JSONL
status log for narration, and adapts strategy between rounds.

Default demo behavior:
- single round only
- 5-second update cadence
- 10-second GIF clips
- denser frame capture at 0.25s per frame
- one timestamped run folder per execution, with `round_XX/` subfolders
- live local peek via `peek.html` and `live.png`
- stable `current/` symlink to the newest run
- no per-round timer; active rounds end naturally

## When to Use
- The user asks Hermes to play `slither.io`
- The user wants a hackathon demo or "wow factor" browser-agent workflow
- The user mentions `hermetic`
- The user wants periodic screenshots or longer GIFs while the agent plays
- The user wants Telegram gameplay updates

## Procedure
1. Run from the directory where artifacts should be saved.
   The value of `--output-dir` is treated as a parent folder. Each execution
   creates `run_YYYYMMDD_HHMMSS/`, and each round goes into `round_XX/`.
2. If Playwright is not set up in the current directory, bootstrap it:

```bash
python3 -m venv .venv
./.venv/bin/pip install playwright
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python -m playwright install chromium
```

3. Start the demo:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
./.venv/bin/python ~/.hermes/skills/gaming/slither-hermes/scripts/slither_hermes.py \
  --nickname hermetic \
  --output-dir slither-run \
  --interval 5 \
  --clip-duration 10 \
  --duration 21600 \
  --rounds 1
```

4. Prefer the run folder's `status.jsonl` and `latest_summary.txt` for status.
   Use `--verbose-stdout` only for local debugging.
5. Treat `--duration` as a whole-session ceiling only. It should not stop an
   active round mid-run.
6. Watch `status.jsonl` in the run folder for `clip` events. Each event
   includes a GIF path and a compact `telegram_summary`.
7. On messaging platforms, send the newest GIF clip back to the user by
   including `MEDIA:/absolute/path/to/clip_XX_XXXX.gif` in the reply.
8. Post more frequent Telegram updates: acknowledge join, then send a short
   status update for every `tick` and every new GIF clip.
   Prefer `latest_summary.txt` or the newest `telegram_summary` field from
   `status.jsonl`. Do not paste terminal output or long process logs.
9. For local monitoring, open either `<output-dir>/peek.html` or the stable
   path `<output-dir>/current/peek.html`.
10. Show the user the latest PNG or GIF files in the run folder.
11. Do not automatically start a second round unless the user explicitly asks.
12. For multi-round runs, read `strategy_update` events from `status.jsonl`
    and tell the user how later rounds adapted from earlier ones.

## Recommended Hermes Prompt

```text
Use the slither-hermes skill. Join slither.io as hermetic, play autonomously,
render 10-second GIF clips, learn from each round, and send me the latest GIF
while keeping me updated.
```

More examples: [references/usage.md](references/usage.md)

## Strategy reference

When explaining how the skill works or when suggesting improvements, use the community guide as authority: [references/strategy-guide.md](references/strategy-guide.md). It describes head-vs-body rules, boosting trade-offs, edge death, early-game caution, circling when big, and avoiding tunnel vision. The runner’s heuristics are designed to align with these rules; an LLM (e.g. GPT-5) can read this file to reason about or refine behavior.

## Pitfalls
- On some machines Playwright's default Chromium path is wrong. The script
  auto-detects a browser under `.playwright-browsers`, or you can set
  `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.
- The Play control is `#playh`, not a semantic button.
- `slither.io` sessions can die quickly. Default to one round; only use more
  rounds when the user explicitly asks.
- `--duration` is a session ceiling, not a per-round timer.
- The script uses lightweight in-page state plus browser input, not full RL.
- Cross-round learning is heuristic adaptation exposed via `strategy_update`
  events.
- GIF delivery on Telegram depends on Hermes routing local `.gif` media as
  animations. If GIF delivery fails, fall back to sending the generated file.

## Verification
- The output directory should contain a `run_YYYYMMDD_HHMMSS/` folder.
- The output directory should contain `current -> run_YYYYMMDD_HHMMSS` when symlinks are supported.
- The output directory should contain a root `peek.html` dashboard following `current/`.
- Each run folder should contain `status.jsonl`, `latest_summary.txt`, `summary.md`, `best.gif`, `best.png`, `longest.gif`, `latest.png`, `latest.gif`, `live.png`, and `peek.html`.
- Each `round_XX/` folder should contain that round's screenshots, clips, and `frames/`.
- Stdout is quiet by default unless `--verbose-stdout` is used.
