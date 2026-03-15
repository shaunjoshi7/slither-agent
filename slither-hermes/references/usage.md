## Example Hermes CLI Commands

Run a one-shot demo from the current directory:

```bash
hermes chat --toolsets "skills,terminal,file" -q \
  "Use the slither-hermes skill. Join slither.io as hermetic, render 10-second GIF clips, learn from each round, and tell me when the run dies."
```

Run the default single-round demo:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
./.venv/bin/python ~/.hermes/skills/gaming/slither-hermes/scripts/slither_hermes.py \
  --nickname hermetic \
  --output-dir slither-wow \
  --interval 5 \
  --clip-duration 10 \
  --duration 21600 \
  --rounds 1
```

Run with a visible browser for local debugging:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
./.venv/bin/python ~/.hermes/skills/gaming/slither-hermes/scripts/slither_hermes.py \
  --nickname hermetic \
  --output-dir slither-debug \
  --interval 5 \
  --clip-duration 10 \
  --duration 21600 \
  --rounds 1 \
  --headed
```

Send GIF clips back over Telegram:

```bash
hermes chat --provider openrouter -m anthropic/claude-sonnet-4 \
  --toolsets "skills,terminal,file" -q \
  "Use the slither-hermes skill. Join slither.io as hermetic, render 10-second GIF clips, send each latest GIF back to telegram, post short progress updates for every tick, and mention how the strategy adapts after each round."
```

## Output Files

- `run_YYYYMMDD_HHMMSS/`: one folder per execution
- `run_YYYYMMDD_HHMMSS/status.jsonl`: one JSON object per event for easy narration
- `run_YYYYMMDD_HHMMSS/latest_summary.txt`: short Telegram-friendly update line
- `run_YYYYMMDD_HHMMSS/summary.md`: end-of-batch recap with median survival and round table
- `run_YYYYMMDD_HHMMSS/status.jsonl` also includes `strategy_update` events with cross-round heuristic adjustments
- `run_YYYYMMDD_HHMMSS/best.gif`: stable pointer to the best round GIF in the batch
- `run_YYYYMMDD_HHMMSS/best.png`: stable pointer to the best still frame in the batch
- `run_YYYYMMDD_HHMMSS/longest.gif`: stable pointer to the longest captured GIF clip in the batch
- `run_YYYYMMDD_HHMMSS/latest.png`: pointer to the newest still image across the run
- `run_YYYYMMDD_HHMMSS/latest.gif`: pointer to the newest GIF clip across the run
- `run_YYYYMMDD_HHMMSS/live.png`: live-updating frame for local peeking
- `run_YYYYMMDD_HHMMSS/peek.html`: simple local dashboard that auto-refreshes
- `run_YYYYMMDD_HHMMSS/round_01/`: round-specific folder
- `run_YYYYMMDD_HHMMSS/round_01/clip_XX_XXXX.gif`: longer gameplay clip for that round
- `run_YYYYMMDD_HHMMSS/round_01/frames/`: raw captured frames used to build GIFs

## Local Peek

From the parent output directory:

```bash
cd slither-wow/current
python3 -m http.server 8765
```

Then open:

```text
http://localhost:8765/peek.html
```

`current/` always points at the newest `run_YYYYMMDD_HHMMSS/` folder.
You can also serve the parent output directory and open its root `peek.html`,
which follows `current/` directly.

## Better Telegram Updates

Tell Hermes to read only the compact summary:

```text
Use the slither-hermes skill. For Telegram updates, read only current/latest_summary.txt or the newest telegram_summary in status.jsonl. Keep each text update under 180 characters and attach only the newest GIF.
```

At the start of the run, Hermes should also send one settings echo using the
resolved values it will actually use, for example:

```text
start | rounds=10 | clip=10s | frame=0.25s | interval=5s
```

`--duration` is only a whole-session cap. It should not interrupt an active
round mid-run.

For multi-round sessions, Hermes should also watch for lines like:

```text
learned r03 | stronger avoidance, less early boost
```

and mention that later rounds are adapting from earlier ones.

## Obey Round Count

If the Telegram prompt includes a round count, Hermes should pass it through
exactly with `--rounds N`.

Examples:

```text
Use slither-hermes for 1 round only.
```

This should run with:

```bash
--rounds 1
```

```text
Use slither-hermes for 10 rounds.
```

This should run with:

```bash
--rounds 10
```

Do not rely on the script default when the user provided a round count.

The runner is quiet on stdout by default so Hermes does not forward raw JSON
events back to Telegram. Use `--verbose-stdout` only for local debugging.

At the end of a multi-round run, use `summary.md` plus `best.gif` for the
final scorecard instead of the moving `latest.gif` pointer.

## Tuning Notes

- Shorter `--interval` means more screenshots and better storytelling.
- `--clip-duration 10` is the default hackathon-friendly setting.
- `--duration 21600` gives long multi-round runs enough room to finish naturally.
- `--frame-interval 0.25` captures denser frames for smoother GIFs.
- Keep `--rounds 1` unless you explicitly want retries.
- Use `--headed` for debugging, `headless` for the actual demo.
