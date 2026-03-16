"""
scheduler.py - Cron-like task scheduler for the AI Employee (Silver Tier).

Runs alongside the Orchestrator and triggers scheduled tasks by writing
trigger files into /Needs_Action/ at the configured times.

Built-in schedules:
  - Daily Briefing    : Every day at DAILY_BRIEFING_HOUR (default 8 AM)
  - Weekly CEO Briefing: Every Monday at WEEKLY_BRIEFING_HOUR (default 7 AM)
  - LinkedIn Post Queue: Handled by linkedin_watcher.py (not here)

Trigger files created:
  - SCHEDULED_daily_briefing_YYYYMMDD.md
  - SCHEDULED_weekly_briefing_YYYYMMDD.md

Usage:
    python scheduler.py --vault /path/to/AI_Employee_Vault

Requirements:
    pip install python-dotenv
    (optionally: pip install schedule   — falls back to built-in loop if missing)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Scheduler] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Scheduler")

DRY_RUN                = os.getenv("DRY_RUN", "true").lower() == "true"
DAILY_BRIEFING_HOUR    = int(os.getenv("DAILY_BRIEFING_HOUR", "8"))
WEEKLY_BRIEFING_HOUR   = int(os.getenv("WEEKLY_BRIEFING_HOUR", "7"))
WEEKLY_BRIEFING_DAY    = os.getenv("WEEKLY_BRIEFING_DAY", "monday").lower()

# Map day names to weekday numbers (Monday = 0)
WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ── Task definitions ──────────────────────────────────────────────────────────

def _make_daily_briefing_trigger(needs_action: Path) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    path = needs_action / f"SCHEDULED_daily_briefing_{today}.md"
    content = f"""---
type: scheduled_task
task: daily_briefing
scheduled_for: {datetime.now().strftime("%Y-%m-%d")} {DAILY_BRIEFING_HOUR:02d}:00
created: {datetime.utcnow().isoformat()}Z
status: pending
---

## Scheduled Task: Daily Briefing

It is {datetime.now().strftime("%A, %B %d, %Y")} at {DAILY_BRIEFING_HOUR:02d}:00.
Generate today's morning briefing.

## Instructions for Claude

1. Read `Dashboard.md` for current system status.
2. Read `Business_Goals.md` for active objectives.
3. Scan `/Needs_Action/` for pending items.
4. Scan `/Pending_Approval/` for items awaiting review.
5. Write a concise daily briefing to `Briefings/{datetime.now().strftime("%Y-%m-%d")}_Daily_Briefing.md`.
6. Update Dashboard.md with today's priorities.
7. Move this file to /Done when complete.

## Briefing Should Cover

- [ ] Items requiring your attention today
- [ ] Pending approvals (if any)
- [ ] Progress toward weekly/monthly goals
- [ ] Any overdue items
"""
    return path, content


def _make_weekly_briefing_trigger(needs_action: Path) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    path = needs_action / f"SCHEDULED_weekly_briefing_{today}.md"
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = datetime.now().strftime("%Y-%m-%d")
    content = f"""---
type: scheduled_task
task: weekly_briefing
scheduled_for: {datetime.now().strftime("%Y-%m-%d")} {WEEKLY_BRIEFING_HOUR:02d}:00
created: {datetime.utcnow().isoformat()}Z
status: pending
period_start: {week_start}
period_end: {week_end}
---

## Scheduled Task: Monday CEO Briefing

Generate this week's Monday Morning CEO Briefing.

## Instructions for Claude

Use the `/weekly-briefing` skill to:
1. Audit tasks completed this week (scan `/Done/` for files from {week_start} to {week_end}).
2. Read `Business_Goals.md` for revenue targets and KPIs.
3. Check `Logs/` for the past 7 days of activity.
4. Identify bottlenecks and generate proactive suggestions.
5. Write the briefing to `Briefings/{datetime.now().strftime("%Y-%m-%d")}_Monday_CEO_Briefing.md`.
6. Update Dashboard.md with the briefing summary.
7. Move this file to /Done when complete.
"""
    return path, content


# ── State tracking ─────────────────────────────────────────────────────────────

class SchedulerState:
    """Tracks which scheduled tasks have already fired today/this week."""

    def __init__(self, vault: Path):
        self.state_file = vault / "Logs" / ".scheduler_state.json"
        self.state = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def has_fired_today(self, task: str) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.state.get(task) == today

    def mark_fired(self, task: str):
        today = datetime.now().strftime("%Y-%m-%d")
        self.state[task] = today
        self._save()


# ── Main scheduler loop ────────────────────────────────────────────────────────

def run_scheduler(vault: Path):
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    state = SchedulerState(vault)
    weekly_day = WEEKDAY_MAP.get(WEEKLY_BRIEFING_DAY, 0)

    logger.info(
        f"Scheduler started | Daily briefing: {DAILY_BRIEFING_HOUR:02d}:00 | "
        f"Weekly briefing: {WEEKLY_BRIEFING_DAY.capitalize()} {WEEKLY_BRIEFING_HOUR:02d}:00"
    )
    if DRY_RUN:
        logger.info("[DRY RUN] Scheduler — trigger files will be logged but not written.")

    def _write_trigger(path: Path, content: str, task_name: str):
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would write trigger: {path.name}")
        elif not path.exists():
            path.write_text(content, encoding="utf-8")
            logger.info(f"Trigger created: {path.name}")
        else:
            logger.debug(f"Trigger already exists (skipping): {path.name}")

        state.mark_fired(task_name)

    while True:
        now = datetime.now()

        # ── Daily Briefing ───────────────────────────────────────────────────
        if now.hour == DAILY_BRIEFING_HOUR and now.minute < 5:
            if not state.has_fired_today("daily_briefing"):
                path, content = _make_daily_briefing_trigger(needs_action)
                _write_trigger(path, content, "daily_briefing")

        # ── Weekly CEO Briefing ──────────────────────────────────────────────
        if now.weekday() == weekly_day and now.hour == WEEKLY_BRIEFING_HOUR and now.minute < 5:
            if not state.has_fired_today("weekly_briefing"):
                path, content = _make_weekly_briefing_trigger(needs_action)
                _write_trigger(path, content, "weekly_briefing")

        time.sleep(60)  # check every minute


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Scheduler (Silver)")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    parser.add_argument(
        "--test-daily",
        action="store_true",
        help="Immediately write a daily briefing trigger and exit (for testing)",
    )
    parser.add_argument(
        "--test-weekly",
        action="store_true",
        help="Immediately write a weekly briefing trigger and exit (for testing)",
    )
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    if not vault.exists():
        logger.error(f"Vault not found: {vault}")
        sys.exit(1)

    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    if args.test_daily:
        path, content = _make_daily_briefing_trigger(needs_action)
        if not DRY_RUN:
            path.write_text(content, encoding="utf-8")
        print(f"Test trigger written: {path.name}")
        return

    if args.test_weekly:
        path, content = _make_weekly_briefing_trigger(needs_action)
        if not DRY_RUN:
            path.write_text(content, encoding="utf-8")
        print(f"Test trigger written: {path.name}")
        return

    run_scheduler(vault)


if __name__ == "__main__":
    main()
