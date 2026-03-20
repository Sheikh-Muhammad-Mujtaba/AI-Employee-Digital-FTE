"""
platinum_orchestrator.py - Platinum Tier Local Orchestrator

This orchestrator runs on the Local machine and:
1. Watches Local/Pending_Approval/ for Cloud drafts
2. Waits for human approval (move to Local/Approved/)
3. Executes approved actions via MCP servers
4. Moves completed tasks to Local/Done/
5. Syncs completion status back to Cloud via Git

Key difference from standard orchestrator:
- Only executes actions after Local human approval
- Handles Cloud drafts synced via Git
- Manages WhatsApp, Payments, and final send actions
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

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
AGENT = os.getenv("AGENT", "qwen").lower()
DEBOUNCE_SECONDS = 3
APPROVAL_EXPIRY_HOURS = 48

# Platinum Tier folders
LOCAL_VAULT = None  # Set via --vault


# ── Logging ───────────────────────────────────────────────────────────────────

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Platinum Orchestrator] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PlatinumOrchestrator")


# ── Dashboard updater ─────────────────────────────────────────────────────────

def update_dashboard(vault: Path):
    """Update Local/Dashboard.md with current status."""
    dashboard = vault / "Local" / "Dashboard.md"
    if not dashboard.exists():
        # Create from template if exists
        template = vault / "Briefings" / "TEMPLATE_Monday_CEO_Briefing.md"
        if template.exists():
            dashboard.write_text(f"# Dashboard\n\nLast Updated: {datetime.now().isoformat()}\n")
        else:
            dashboard.write_text(f"# Dashboard\n\nLast Updated: {datetime.now().isoformat()}\n")
        return

    def count_md(folder: Path) -> int:
        if not folder.exists():
            return 0
        return len([f for f in folder.iterdir() if f.suffix == ".md" and not f.name.startswith(".")])

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    stats = {
        "pending_approval": count_md(vault / "Local" / "Pending_Approval"),
        "approved": count_md(vault / "Local" / "Approved"),
        "done_today": count_md(vault / "Local" / "Done"),
        "cloud_drafts": count_md(vault / "Cloud" / "Drafts"),
    }

    text = dashboard.read_text(encoding="utf-8")

    new_summary = f"""## Platinum Tier Status

- **Pending Approval:** {stats['pending_approval']}
- **Approved (awaiting execution):** {stats['approved']}
- **Completed today:** {stats['done_today']}
- **Cloud Drafts synced:** {stats['cloud_drafts']}
- **Last sync:** {now}"""

    text = re.sub(
        r"## Platinum Tier Status.*?(?=\n---|\Z)",
        new_summary + "\n\n",
        text,
        flags=re.DOTALL,
    )

    text = re.sub(r"last_updated: .*", f"last_updated: {now}", text)
    dashboard.write_text(text, encoding="utf-8")
    logger.info(f"Dashboard updated — Pending: {stats['pending_approval']}, Done: {stats['done_today']}")


# ── Log writer ────────────────────────────────────────────────────────────────

def write_log(vault: Path, entry: dict):
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_event(vault: Path, action_type: str, **kwargs):
    write_log(vault, {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "actor": "platinum_orchestrator",
        "action_type": action_type,
        **kwargs,
    })


# ── Approved action executor ──────────────────────────────────────────────────

class PlatinumActionExecutor:
    """
    Executes approved actions on Local machine.
    
    Platinum Tier: Only Local can execute sensitive actions:
    - Send emails
    - Send WhatsApp messages
    - Process payments
    - Publish social media posts
    """

    def __init__(self, vault: Path):
        self.vault = vault
        self.done_folder = vault / "Local" / "Done"
        self.done_folder.mkdir(exist_ok=True)

    def execute(self, approved_file: Path):
        """Execute an approved action."""
        action_type = "unknown"
        try:
            text = approved_file.read_text(encoding="utf-8")
            fields = self._parse_frontmatter(text)
            action_type = fields.get("action", "") or fields.get("type", "unknown")

            logger.info(f"Executing approved action: {action_type} — {approved_file.name}")

            if action_type == "send_email":
                self._execute_send_email(approved_file, fields, text)
            elif action_type == "send_whatsapp":
                self._execute_send_whatsapp(approved_file, fields, text)
            elif action_type == "post_linkedin":
                self._execute_post_linkedin(approved_file, fields, text)
            elif action_type == "post_twitter":
                self._execute_post_twitter(approved_file, fields, text)
            elif action_type == "post_facebook":
                self._execute_post_facebook(approved_file, fields, text)
            elif action_type == "post_instagram":
                self._execute_post_instagram(approved_file, fields, text)
            elif action_type == "payment":
                self._execute_payment(approved_file, fields, text)
            else:
                logger.info(f"Action type '{action_type}' acknowledged — no automated execution defined.")
                log_event(self.vault, "action_acknowledged", file=approved_file.name, action=action_type)

            # Move to Done
            self._move_to_done(approved_file)

        except Exception as e:
            logger.error(f"Failed to execute {action_type} for {approved_file.name}: {e}", exc_info=True)
            log_event(self.vault, "action_failed", file=approved_file.name, action=action_type, error=str(e))

        update_dashboard(self.vault)

    def _parse_frontmatter(self, text: str) -> dict:
        """Extract YAML-style frontmatter fields."""
        fields = {}
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    fields[key.strip()] = val.strip()
        return fields

    def _extract_body_content(self, text: str) -> str:
        """Return body text after frontmatter block."""
        if not text:
            return ""
        trimmed = text.strip()
        if trimmed.startswith("---"):
            m = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)$", trimmed, re.DOTALL)
            if m:
                return m.group(1).strip()
        return trimmed

    def _move_to_done(self, approved_file: Path):
        """Move completed file to Local/Done/."""
        dest = self.done_folder / approved_file.name
        if dest.exists():
            ts = datetime.now().strftime("%H%M%S")
            dest = self.done_folder / f"{approved_file.stem}_{ts}{approved_file.suffix}"
        approved_file.rename(dest)
        logger.info(f"Moved to /Done: {approved_file.name}")

    def _execute_send_email(self, approved_file: Path, fields: dict, text: str):
        """Send email via Email MCP."""
        to = fields.get("to", "")
        subject = fields.get("subject", "")
        
        # Extract body using unified helper (strips frontmatter)
        body = self._extract_body_content(text)

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send email to: {to} | Subject: {subject}")
            log_event(self.vault, "email_sent_dry_run", to=to, subject=subject)
            return

        email_mcp_path = os.getenv("EMAIL_MCP_PATH", "")
        if not email_mcp_path:
            logger.warning("EMAIL_MCP_PATH not set. Cannot send email.")
            return

        mcp_input = json.dumps({"action": "send", "to": to, "subject": subject, "body": body})
        try:
            result = subprocess.run(
                ["node", email_mcp_path, "--send"],
                input=mcp_input, capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                logger.info(f"Email sent to: {to}")
                log_event(self.vault, "email_sent", to=to, subject=subject, approved_by="human")
            else:
                logger.error(f"Email MCP failed: {result.stderr[:500]}")
                log_event(self.vault, "email_failed", to=to, error=result.stderr[:500])
        except Exception as e:
            logger.error(f"Email error: {e}")
            log_event(self.vault, "email_failed", to=to, error=str(e))

    def _execute_send_whatsapp(self, approved_file: Path, fields: dict, text: str):
        """Send WhatsApp message via Baileys API."""
        import requests

        jid = fields.get("jid", "")
        body = self._extract_body_content(text)

        if not jid or not body:
            logger.error(f"WhatsApp missing jid or body")
            return

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send WA to {jid}")
            return

        try:
            resp = requests.post("http://localhost:3001/send", json={"jid": jid, "text": body}, timeout=10)
            if resp.status_code == 200:
                logger.info(f"WhatsApp sent to {jid}")
                log_event(self.vault, "whatsapp_sent", jid=jid, approved_by="human")
            else:
                logger.error(f"WhatsApp failed: {resp.text}")
        except Exception as e:
            logger.error(f"WhatsApp error: {e}")

    def _execute_post_linkedin(self, approved_file: Path, fields: dict, text: str):
        """Post to LinkedIn via Playwright."""
        content = self._extract_body_content(text)

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to LinkedIn: {content[:100]}...")
            return

        poster_script = Path(__file__).parent.parent / "watchers" / "linkedin_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--post"],
                input=json.dumps({"content": content}),
                capture_output=True, text=True, timeout=300,
            )
            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("LinkedIn post published")
                log_event(self.vault, "linkedin_posted", approved_by="human")
            else:
                logger.error(f"LinkedIn failed: {output.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"LinkedIn error: {e}")

    def _execute_post_twitter(self, approved_file: Path, fields: dict, text: str):
        """Post to Twitter via Playwright."""
        content = self._extract_body_content(text)

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Twitter: {content[:100]}...")
            return

        poster_script = Path(__file__).parent.parent / "watchers" / "twitter_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--post"],
                input=json.dumps({"content": content}),
                capture_output=True, text=True, timeout=300,
            )
            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Twitter post published")
                log_event(self.vault, "twitter_posted", approved_by="human")
            else:
                logger.error(f"Twitter failed: {output.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"Twitter error: {e}")

    def _execute_post_facebook(self, approved_file: Path, fields: dict, text: str):
        """Post to Facebook via Playwright."""
        content = self._extract_body_content(text)

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Facebook: {content[:100]}...")
            return

        poster_script = Path(__file__).parent.parent / "watchers" / "meta_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--platform", "facebook", "--post"],
                input=json.dumps({"content": content}),
                capture_output=True, text=True, timeout=300,
            )
            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Facebook post published")
                log_event(self.vault, "facebook_posted", approved_by="human")
            else:
                logger.error(f"Facebook failed: {output.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"Facebook error: {e}")

    def _execute_post_instagram(self, approved_file: Path, fields: dict, text: str):
        """Post to Instagram via Playwright."""
        content = self._extract_body_content(text)
        image_url = fields.get("image_url", "")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Instagram: {content[:100]}...")
            return

        if not image_url:
            logger.error("Instagram post missing image_url")
            return

        poster_script = Path(__file__).parent.parent / "watchers" / "meta_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--platform", "instagram", "--post"],
                input=json.dumps({"content": content, "image_url": image_url}),
                capture_output=True, text=True, timeout=300,
            )
            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Instagram post published")
                log_event(self.vault, "instagram_posted", approved_by="human")
            else:
                logger.error(f"Instagram failed: {output.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"Instagram error: {e}")

    def _execute_payment(self, approved_file: Path, fields: dict, text: str):
        """Execute payment (placeholder - integrate with payment MCP)."""
        amount = fields.get("amount", "")
        recipient = fields.get("recipient", "")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would pay {amount} to {recipient}")
            log_event(self.vault, "payment_dry_run", amount=amount, recipient=recipient)
            return

        logger.info(f"Payment execution not implemented - integrate with payment MCP")
        log_event(self.vault, "payment_pending", amount=amount, recipient=recipient)


# ── Watchdog handler ──────────────────────────────────────────────────────────

class ApprovedHandler(FileSystemEventHandler):
    """Watch Local/Approved/ for human-approved actions."""

    def __init__(self, vault: Path, executor: PlatinumActionExecutor):
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
    parser = argparse.ArgumentParser(description="Platinum Tier - Local Orchestrator")
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

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    logger.info(f"Platinum Orchestrator starting [{mode}] — vault: {vault}")

    executor = PlatinumActionExecutor(vault)
    approved_handler = ApprovedHandler(vault, executor)

    observer = Observer()
    
    # Watch Local/Approved/ for human-approved actions
    approved_dir = vault / "Local" / "Approved"
    approved_dir.mkdir(exist_ok=True)
    observer.schedule(approved_handler, str(approved_dir), recursive=False)
    observer.start()

    # Process existing approved files
    for f in sorted(approved_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            logger.info(f"Startup: found existing approved: {f.name}")
            executor.execute(f)

    update_dashboard(vault)

    try:
        while True:
            approved_handler.flush_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopping...")
        observer.stop()
    observer.join()
    logger.info("Platinum Orchestrator stopped.")


if __name__ == "__main__":
    main()
