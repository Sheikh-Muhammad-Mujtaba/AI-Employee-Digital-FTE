"""
orchestrator.py - Master process for the AI Employee (Bronze Tier).

Responsibilities:
  1. Watch /Needs_Action for new .md files
  2. Trigger Claude Code to process them
  3. Watch /Approved for approved action files and log them
  4. Keep Dashboard.md updated

Usage:
    python orchestrator.py --vault /path/to/AI_Employee_Vault [--dry-run]

Requirements:
    pip install watchdog python-dotenv
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── Config ────────────────────────────────────────────────────────────────────

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# How many seconds to wait after detecting a new file before triggering Claude
# (gives time for multi-file drops to settle)
DEBOUNCE_SECONDS = 3


# ── Logging ───────────────────────────────────────────────────────────────────

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orchestrator] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Orchestrator")


# ── Dashboard updater ─────────────────────────────────────────────────────────

def update_dashboard(vault: Path):
    """Rewrite the stats section of Dashboard.md based on current folder counts."""
    dashboard = vault / "Dashboard.md"
    if not dashboard.exists():
        logger.warning("Dashboard.md not found — skipping update.")
        return

    needs_action = vault / "Needs_Action"
    pending_approval = vault / "Pending_Approval"
    done = vault / "Done"
    inbox = vault / "Inbox"

    def count_md(folder: Path) -> int:
        if not folder.exists():
            return 0
        return len([f for f in folder.iterdir() if f.suffix == ".md" and f.name != ".gitkeep"])

    def count_files(folder: Path) -> int:
        if not folder.exists():
            return 0
        return len([f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")])

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    stats = {
        "inbox": count_files(inbox),
        "needs_action": count_md(needs_action),
        "pending_approval": count_md(pending_approval),
        "done_today": count_md(done),
    }

    text = dashboard.read_text(encoding="utf-8")

    # Replace the Inbox Summary block
    new_summary = f"""## Inbox Summary

- **Pending items in /Inbox:** {stats['inbox']}
- **Items in /Needs_Action:** {stats['needs_action']}
- **Items in /Pending_Approval:** {stats['pending_approval']}
- **Completed today:** {stats['done_today']}"""

    import re
    text = re.sub(
        r"## Inbox Summary.*?(?=\n---|\Z)",
        new_summary + "\n\n",
        text,
        flags=re.DOTALL,
    )

    # Update last_updated in frontmatter
    text = re.sub(r"last_updated: .*", f"last_updated: {now}", text)

    dashboard.write_text(text, encoding="utf-8")
    logger.info(f"Dashboard updated — Needs_Action: {stats['needs_action']}, Pending: {stats['pending_approval']}")


# ── Log writer ────────────────────────────────────────────────────────────────

def write_log(vault: Path, entry: dict):
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Claude trigger ────────────────────────────────────────────────────────────

def trigger_claude(vault: Path, action_file: Path):
    """
    Invoke Claude Code to process a single Needs_Action file.
    In DRY_RUN mode, only logs the intended action.
    """
    prompt = f"""You are the AI Employee. Read the Company_Handbook.md and then process this task:

File: {action_file.name}
Vault: {vault}

Steps:
1. Read {action_file} to understand the task.
2. Read Company_Handbook.md for rules of engagement.
3. Determine the appropriate action.
4. If the action requires approval, create a file in /Pending_Approval/.
5. If no approval is needed, complete the task and move the file to /Done/.
6. Update Dashboard.md when done.

Output <promise>TASK_COMPLETE</promise> when finished.
"""

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would trigger Claude for: {action_file.name}")
        logger.info(f"[DRY RUN] Prompt preview:\n{prompt[:200]}...")
        return

    logger.info(f"Triggering Claude Code for: {action_file.name}")
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            cwd=str(vault),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info(f"Claude completed task for: {action_file.name}")
        else:
            logger.error(f"Claude exited with code {result.returncode}: {result.stderr[:200]}")
    except FileNotFoundError:
        logger.error("'claude' command not found. Ensure Claude Code is installed and in PATH.")
    except subprocess.TimeoutExpired:
        logger.error(f"Claude timed out processing: {action_file.name}")


# ── Watchdog event handler ────────────────────────────────────────────────────

class NeedsActionHandler(FileSystemEventHandler):
    """Triggers Claude when a new .md file appears in /Needs_Action."""

    def __init__(self, vault: Path):
        super().__init__()
        self.vault = vault
        self._pending: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".md" or path.name.startswith("."):
            return
        # Debounce: record time seen
        self._pending[str(path)] = time.time()

    def flush_pending(self):
        """Process files that have been stable for DEBOUNCE_SECONDS."""
        now = time.time()
        ready = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for p in ready:
            del self._pending[p]
            action_file = Path(p)
            if not action_file.exists():
                continue
            write_log(
                self.vault,
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "event": "needs_action_detected",
                    "file": action_file.name,
                },
            )
            trigger_claude(self.vault, action_file)
            update_dashboard(self.vault)


class ApprovedHandler(FileSystemEventHandler):
    """Logs when files are moved to /Approved (human gave the go-ahead)."""

    def __init__(self, vault: Path):
        super().__init__()
        self.vault = vault

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name.startswith("."):
            return
        logger.info(f"Approved action detected: {path.name}")
        write_log(
            self.vault,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event": "action_approved",
                "file": path.name,
                "approved_by": "human",
            },
        )
        # Future: trigger the actual MCP action here (Silver/Gold tier)
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would execute approved action: {path.name}")
        update_dashboard(self.vault)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Orchestrator (Bronze)")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended actions without executing them",
    )
    args = parser.parse_args()

    global DRY_RUN
    if args.dry_run:
        DRY_RUN = True

    vault = Path(args.vault).resolve()
    if not vault.exists():
        logger.error(f"Vault not found: {vault}")
        sys.exit(1)

    needs_action_dir = vault / "Needs_Action"
    approved_dir = vault / "Approved"
    needs_action_dir.mkdir(exist_ok=True)
    approved_dir.mkdir(exist_ok=True)

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    logger.info(f"Orchestrator starting [{mode}] — vault: {vault}")

    needs_handler = NeedsActionHandler(vault)
    approved_handler = ApprovedHandler(vault)

    observer = Observer()
    observer.schedule(needs_handler, str(needs_action_dir), recursive=False)
    observer.schedule(approved_handler, str(approved_dir), recursive=False)
    observer.start()

    update_dashboard(vault)

    try:
        while True:
            needs_handler.flush_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopping...")
        observer.stop()
    observer.join()
    logger.info("Orchestrator stopped.")


if __name__ == "__main__":
    main()
