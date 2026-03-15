# slither-agent

Autonomous slither.io agent — Playwright browser control, GIF clip capture, cross-round strategy adaptation, and Telegram updates.

## Slither Hermes skill

- **Skill path:** `slither-hermes/` (also installable under `~/.hermes/skills/gaming/slither-hermes/`)
- Run from a directory that will hold artifacts (e.g. `slither-run/`). The script creates timestamped run folders and a `current/` symlink.
- Defaults: 10s GIF clips, 10 rounds possible, no per-round timer, session cap 21600s. Rounds end on death; strategy adapts between rounds.

### Quick run

```bash
python3 -m venv .venv
./.venv/bin/pip install playwright
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python -m playwright install chromium

PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python slither-hermes/scripts/slither_hermes.py \
  --nickname hermetic --output-dir slither-run --rounds 1
```

See `slither-hermes/SKILL.md` and `slither-hermes/references/usage.md` for Hermes procedure and Telegram prompts.

---

[github.com/shaunjoshi7/slither-agent](https://github.com/shaunjoshi7/slither-agent)
