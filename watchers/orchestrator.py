"""
orchestrator.py - Master process for the AI Employee (Silver Tier).

Silver upgrades over Bronze:
  ✅ All Bronze functionality (Needs_Action watcher, dashboard updater, Claude trigger)
  🆕 Approved action executor — parses /Approved files and calls MCP/API
  🆕 Plan.md reasoning loop — Claude is prompted to create plans for complex tasks
  🆕 LinkedIn post publisher — calls LinkedIn API for approved posts
  🆕 Email sender — calls Email MCP for approved emails
  🆕 Approval expiry handler — moves stale approvals to /Rejected automatically
  🆕 Silver-tier structured logging with action_type taxonomy

Usage:
    python orchestrator.py --vault /path/to/AI_Employee_Vault [--dry-run]

Requirements:
    pip install watchdog python-dotenv requests
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── Config ────────────────────────────────────────────────────────────────────

DRY_RUN              = os.getenv("DRY_RUN", "true").lower() == "true"
DEBOUNCE_SECONDS     = 3
APPROVAL_EXPIRY_HOURS = 48
EMAIL_MCP_PATH       = os.getenv("EMAIL_MCP_PATH", "")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN  = os.getenv("LINKEDIN_PERSON_URN", "")
MAX_EMAILS_PER_HOUR  = int(os.getenv("MAX_EMAILS_PER_HOUR", "10"))

# ── Logging ───────────────────────────────────────────────────────────────────

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orchestrator] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Orchestrator")


# ── Frontmatter parser ────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    """Extract YAML-style frontmatter fields from a markdown file."""
    fields = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return fields
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields


# ── Dashboard updater ─────────────────────────────────────────────────────────

def update_dashboard(vault: Path):
    dashboard = vault / "Dashboard.md"
    if not dashboard.exists():
        return

    def count_md(folder: Path) -> int:
        if not folder.exists():
            return 0
        return len([f for f in folder.iterdir() if f.suffix == ".md" and not f.name.startswith(".")])

    def count_files(folder: Path) -> int:
        if not folder.exists():
            return 0
        return len([f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")])

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    stats = {
        "inbox":            count_files(vault / "Inbox"),
        "needs_action":     count_md(vault / "Needs_Action"),
        "pending_approval": count_md(vault / "Pending_Approval"),
        "done_today":       count_md(vault / "Done"),
        "plans_active":     count_md(vault / "Plans"),
    }

    text = dashboard.read_text(encoding="utf-8")

    new_summary = f"""## Inbox Summary

- **Pending items in /Inbox:** {stats['inbox']}
- **Items in /Needs_Action:** {stats['needs_action']}
- **Items in /Pending_Approval:** {stats['pending_approval']}
- **Active Plans:** {stats['plans_active']}
- **Completed today:** {stats['done_today']}"""

    text = re.sub(
        r"## Inbox Summary.*?(?=\n---|\Z)",
        new_summary + "\n\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"last_updated: .*", f"last_updated: {now}", text)

    dashboard.write_text(text, encoding="utf-8")
    logger.info(
        f"Dashboard updated — Needs_Action: {stats['needs_action']}, "
        f"Pending: {stats['pending_approval']}, Plans: {stats['plans_active']}"
    )


# ── Log writer ────────────────────────────────────────────────────────────────

def write_log(vault: Path, entry: dict):
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_event(vault: Path, action_type: str, **kwargs):
    write_log(vault, {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": "orchestrator",
        "action_type": action_type,
        **kwargs,
    })


# ── Claude trigger ────────────────────────────────────────────────────────────

SILVER_PROMPT_TEMPLATE = """You are the AI Employee (Silver Tier). You work autonomously to process tasks.

Your vault is at: {vault}
Task file to process: {action_file}

## Your job

1. Read the task file at {action_file} to understand what is needed.
2. Read {vault}/Company_Handbook.md for rules of engagement.
3. Act based on the task type:

### If type == "email":
   - Draft a professional reply to the email.
   - Create a file in {vault}/Pending_Approval/ named REPLY_<timestamp>.md with this exact format:
     ```
     ---
     action: send_email
     to: <sender's email address>
     subject: Re: <original subject>
     created: <current UTC datetime in ISO format>
     ---

     <your drafted email reply body here>

     ---
     ```
   - Move the original task file from {action_file} to {vault}/Done/

### If type == "briefing":
   - Generate the briefing content.
   - Write it to {vault}/Briefings/ with filename BRIEFING_<date>.md
   - Move the original task file to {vault}/Done/

### If type == "linkedin":
   - Draft the LinkedIn post.
   - Create a file in {vault}/Pending_Approval/ named POST_<timestamp>.md with this exact format:
     ```
     ---
     action: post_linkedin
     created: <current UTC datetime in ISO format>
     ---

     <your drafted post content here>

     ---
     ```
   - Move the original task file to {vault}/Done/

### For any other task:
   - Handle it appropriately and move the file to {vault}/Done/

## Rules
- NEVER send emails or post to LinkedIn directly — always write to /Pending_Approval/ first.
- Always move the processed action file to /Done/ when complete.
- Update {vault}/Dashboard.md last_updated field when done.

Output <promise>TASK_COMPLETE</promise> when finished.
"""

def trigger_claude(vault: Path, action_file: Path):
    prompt = SILVER_PROMPT_TEMPLATE.format(
        vault=str(vault),
        action_file=str(action_file),
    )

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would trigger Claude for: {action_file.name}")
        return

    logger.info(f"Triggering Claude Code (Silver) for: {action_file.name}")
    try:
        result = subprocess.run(
            [r"C:\Users\Khali\AppData\Roaming\npm\claude.cmd", "--print", "--dangerously-skip-permissions", prompt],
            cwd=str(vault),
            capture_output=True,
            text=True,
            timeout=600,  # Silver tasks can take longer (planning + multi-step)
            encoding="utf-8",
        )
        if result.returncode == 0:
            logger.info(f"Claude completed: {action_file.name}")
            if "TASK_COMPLETE" not in result.stdout:
                logger.warning(f"Claude finished but TASK_COMPLETE not found in output for: {action_file.name}")
        else:
            logger.error(f"Claude error (code {result.returncode}): {result.stderr[:300]}")
    except FileNotFoundError:
        logger.error("'claude' not found. Ensure Claude Code is installed: npm install -g @anthropic/claude-code")
    except subprocess.TimeoutExpired:
        logger.error(f"Claude timed out (10 min) for: {action_file.name}")


# ── Approved action executor ──────────────────────────────────────────────────

class ApprovedActionExecutor:
    """
    Reads an approved file, determines the action type, and executes it.

    Supported action types:
      - send_email    → calls Email MCP server
      - post_linkedin → calls LinkedIn UGC Posts API
      - (others)      → logged and moved to Done
    """

    def __init__(self, vault: Path):
        self.vault = vault
        self._emails_this_hour: list[datetime] = []

    def _check_email_rate_limit(self) -> bool:
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        self._emails_this_hour = [t for t in self._emails_this_hour if t > cutoff]
        if len(self._emails_this_hour) >= MAX_EMAILS_PER_HOUR:
            logger.warning(f"Email rate limit reached ({MAX_EMAILS_PER_HOUR}/hour). Skipping.")
            return False
        return True

    def execute(self, approved_file: Path):
        text = approved_file.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        action_type = fields.get("action", "unknown")

        logger.info(f"Executing approved action: {action_type} — {approved_file.name}")

        done_dir = self.vault / "Done"
        done_dir.mkdir(exist_ok=True)

        try:
            if action_type == "send_email":
                self._execute_send_email(approved_file, fields, text)
            elif action_type == "post_linkedin":
                self._execute_post_linkedin(approved_file, fields, text)
            else:
                logger.info(f"Action type '{action_type}' acknowledged — no automated execution defined.")
                log_event(self.vault, "action_acknowledged", file=approved_file.name, action=action_type)

            # Move to Done (add suffix if filename already exists)
            dest = done_dir / approved_file.name
            if dest.exists():
                ts = datetime.utcnow().strftime("%H%M%S")
                dest = done_dir / f"{approved_file.stem}_{ts}{approved_file.suffix}"
            approved_file.rename(dest)
            logger.info(f"Moved to /Done: {approved_file.name}")

        except Exception as e:
            logger.error(f"Failed to execute {action_type} for {approved_file.name}: {e}", exc_info=True)
            log_event(self.vault, "action_failed", file=approved_file.name, action=action_type, error=str(e))

        update_dashboard(self.vault)

    def _execute_send_email(self, approved_file: Path, fields: dict, text: str):
        if not self._check_email_rate_limit():
            return

        # Try frontmatter first, then fall back to markdown body fields
        to      = fields.get("to", "")
        subject = fields.get("subject", "")

        if not to:
            m = re.search(r"\*\*To:\*\*\s*(.+)", text)
            if m:
                to = m.group(1).strip()

        if not subject:
            m = re.search(r"\*\*Subject:\*\*\s*(.+)", text)
            if m:
                subject = m.group(1).strip()

        # Extract body after **Body:** marker, or between --- delimiters
        body = ""
        body_match = re.search(r"\*\*Body:\*\*\s*\n\n(.+?)(?:\n\n---|$)", text, re.DOTALL)
        if body_match:
            body = body_match.group(1).strip()
        else:
            body_match = re.search(r"---\n\n(.+?)\n\n---", text, re.DOTALL)
            body = body_match.group(1).strip() if body_match else ""

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send email to: {to} | Subject: {subject}")
            log_event(self.vault, "email_sent_dry_run", to=to, subject=subject)
            return

        if not EMAIL_MCP_PATH:
            logger.warning("EMAIL_MCP_PATH not set. Cannot send email. Set it in .env")
            log_event(self.vault, "email_skipped", reason="EMAIL_MCP_PATH_not_set", to=to)
            return

        # Call Email MCP via subprocess (node process)
        mcp_input = json.dumps({"action": "send", "to": to, "subject": subject, "body": body})
        try:
            result = subprocess.run(
                ["node", EMAIL_MCP_PATH, "--send"],
                input=mcp_input, capture_output=True, text=True, timeout=60,
                encoding="utf-8",
            )
            if result.returncode == 0:
                logger.info(f"Email sent to: {to} | Subject: {subject}")
                self._emails_this_hour.append(datetime.utcnow())
                log_event(
                    self.vault, "email_sent",
                    to=to, subject=subject, approved_by="human",
                    result="success",
                )
            else:
                logger.error(f"Email MCP failed: {result.stderr[:200]}")
                log_event(self.vault, "email_failed", to=to, error=result.stderr[:200])
        except subprocess.TimeoutExpired:
            logger.error("Email MCP timed out.")

    def _execute_post_linkedin(self, approved_file: Path, fields: dict, text: str):
        # Extract post content between the --- delimiters
        body_match = re.search(r"---\n\n(.+?)\n\n---", text, re.DOTALL)
        post_content = body_match.group(1).strip() if body_match else ""

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to LinkedIn:\n{post_content[:200]}...")
            log_event(self.vault, "linkedin_post_dry_run", content_preview=post_content[:100])
            return

        poster_script = Path(__file__).parent / "linkedin_poster.py"
        try:
            result = subprocess.run(
                ["py", "-3.13", str(poster_script), "--post"],
                input=json.dumps({"content": post_content}),
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
            )
            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("LinkedIn post published via Playwright.")
                log_event(self.vault, "linkedin_posted", approved_by="human", result="success")
            else:
                err = output.get("error", result.stderr[:200])
                logger.error(f"LinkedIn poster failed: {err}")
                log_event(self.vault, "linkedin_failed", error=err)
        except subprocess.TimeoutExpired:
            logger.error("LinkedIn poster timed out.")
            log_event(self.vault, "linkedin_failed", error="timeout")
        except Exception as e:
            logger.error(f"LinkedIn poster error: {e}")
            log_event(self.vault, "linkedin_failed", error=str(e))


# ── Approval expiry handler ───────────────────────────────────────────────────

def expire_stale_approvals(vault: Path):
    """Move Pending_Approval files older than APPROVAL_EXPIRY_HOURS to /Rejected."""
    pending_dir = vault / "Pending_Approval"
    rejected_dir = vault / "Rejected"
    if not pending_dir.exists():
        return

    rejected_dir.mkdir(exist_ok=True)
    cutoff = datetime.utcnow() - timedelta(hours=APPROVAL_EXPIRY_HOURS)

    for f in pending_dir.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            fields = parse_frontmatter(text)
            created_str = fields.get("created", "")
            if not created_str:
                continue
            created = datetime.fromisoformat(created_str.rstrip("Z"))
            if created < cutoff:
                dest = rejected_dir / f.name
                f.rename(dest)
                logger.info(f"Expired approval moved to /Rejected: {f.name}")
                log_event(vault, "approval_expired", file=f.name, created=created_str)
        except Exception as e:
            logger.debug(f"Could not check expiry for {f.name}: {e}")


# ── Watchdog handlers ─────────────────────────────────────────────────────────

class NeedsActionHandler(FileSystemEventHandler):
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
        self._pending[str(path)] = time.time()

    def flush_pending(self):
        now = time.time()
        ready = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for p in ready:
            del self._pending[p]
            action_file = Path(p)
            if not action_file.exists():
                continue
            log_event(self.vault, "needs_action_detected", file=action_file.name)
            trigger_claude(self.vault, action_file)
            update_dashboard(self.vault)


class ApprovedHandler(FileSystemEventHandler):
    def __init__(self, vault: Path, executor: ApprovedActionExecutor):
        super().__init__()
        self.vault = vault
        self.executor = executor
        self._pending: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name.startswith("."):
            return
        self._pending[str(path)] = time.time()

    def flush_pending(self):
        now = time.time()
        ready = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for p in ready:
            del self._pending[p]
            approved_file = Path(p)
            if not approved_file.exists():
                continue
            logger.info(f"Human approved: {approved_file.name}")
            log_event(self.vault, "action_approved", file=approved_file.name, approved_by="human")
            self.executor.execute(approved_file)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Orchestrator (Silver)")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log actions without executing")
    args = parser.parse_args()

    global DRY_RUN
    if args.dry_run:
        DRY_RUN = True

    vault = Path(args.vault).resolve()
    if not vault.exists():
        logger.error(f"Vault not found: {vault}")
        sys.exit(1)

    # Ensure required directories exist
    for folder in ["Needs_Action", "Approved", "Pending_Approval", "Rejected", "Done", "Plans", "Logs"]:
        (vault / folder).mkdir(exist_ok=True)

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    logger.info(f"Orchestrator (Silver) starting [{mode}] — vault: {vault}")

    executor = ApprovedActionExecutor(vault)

    needs_handler    = NeedsActionHandler(vault)
    approved_handler = ApprovedHandler(vault, executor)

    observer = Observer()
    observer.schedule(needs_handler, str(vault / "Needs_Action"), recursive=False)
    observer.schedule(approved_handler, str(vault / "Approved"), recursive=False)
    observer.start()

    update_dashboard(vault)

    EXPIRY_CHECK_INTERVAL = 3600  # check for stale approvals every hour
    last_expiry_check = time.time()

    try:
        while True:
            needs_handler.flush_pending()
            approved_handler.flush_pending()

            # Periodic expiry check
            if time.time() - last_expiry_check > EXPIRY_CHECK_INTERVAL:
                expire_stale_approvals(vault)
                last_expiry_check = time.time()

            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopping...")
        observer.stop()
    observer.join()
    logger.info("Orchestrator (Silver) stopped.")


if __name__ == "__main__":
    main()
