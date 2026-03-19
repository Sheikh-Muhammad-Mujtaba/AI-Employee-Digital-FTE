"""
orchestrator.py - Master process for the AI Employee (Gold Tier).

Gold upgrades over Silver:
  ✅ All Silver functionality
  🆕 Twitter/X post publisher — calls twitter_poster.py for approved tweets
  🆕 Facebook post publisher — calls meta_poster.py --platform facebook
  🆕 Instagram post publisher — calls meta_poster.py --platform instagram

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

# ── Agent selection (claude | gemini | qwen) ──────────────────────────────────

AGENT = os.getenv("AGENT", "claude").lower().strip()

# Agent CLI configs: { name: { cmd: [...], prompt_flag: str, extra_flags: [...] } }
AGENT_CONFIGS: dict[str, dict] = {
    "claude": {
        "cmd": ["claude"],
        "prompt_flag": "--print",
        "extra_flags": ["--dangerously-skip-permissions"],
        "mcp_flag": "--mcp-config",
    },
    "gemini": {
        "cmd": ["gemini"],
        "prompt_flag": "-p",
        "extra_flags": [],
        "mcp_flag": None,  # gemini reads from ~/.gemini/settings.json
    },
    "qwen": {
        "cmd": ["qwen"],
        "prompt_flag": "--prompt",
        "extra_flags": [],
        "mcp_flag": "--mcp-config",
    },
}

def _resolve_agent_cmd(agent_name: str) -> list[str]:
    """Resolve the agent CLI command, checking common install locations on Windows."""
    config = AGENT_CONFIGS.get(agent_name)
    if not config:
        raise ValueError(f"Unknown AGENT: {agent_name}. Must be one of: {', '.join(AGENT_CONFIGS.keys())}")

    base_cmd = config["cmd"][0]

    # Check if available on PATH first
    import shutil
    resolved = shutil.which(base_cmd)
    if resolved:
        return [resolved]

    # Windows: check common npm global install locations
    npm_paths = [
        os.path.expandvars(rf"%APPDATA%\npm\{base_cmd}.cmd"),
        os.path.expandvars(rf"%USERPROFILE%\AppData\Roaming\npm\{base_cmd}.cmd"),
    ]
    for p in npm_paths:
        if os.path.isfile(p):
            return [p]

    # Fallback: return bare command and let subprocess raise FileNotFoundError
    return [base_cmd]

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

    now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
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

    # Recent Activity (last 10 events from logs)
    logs_dir = vault / "Logs"
    recent_events = []
    if logs_dir.exists():
        # Get last 2 log files (today and yesterday)
        log_files = sorted([f for f in logs_dir.glob("*.jsonl")], reverse=True)[:2]
        for lf in log_files:
            try:
                content = lf.read_text(encoding="utf-8").strip()
                if content:
                    lines = content.splitlines()
                    for line in reversed(lines):
                        try:
                            evt = json.loads(line)
                            recent_events.append(evt)
                        except: continue
                        if len(recent_events) >= 10: break
            except: pass
            if len(recent_events) >= 10: break

    act_md = "## Recent Activity\n\n| Time | Event | Details |\n|------|-------|---------|\n"
    for e in recent_events:
        t = e.get("timestamp", "")[:16].replace("T", " ")
        ev = e.get("action_type", e.get("event", "event")).replace("_", " ").title()
        # Build details string from other fields
        ignore = ["timestamp", "actor", "action_type", "event"]
        det = ", ".join([f"{k}={v}" for k, v in e.items() if k not in ignore])
        act_md += f"| {t} | {ev} | {det} |\n"
    
    text = re.sub(
        r"## Recent Activity.*?(?=\n---|\Z)",
        lambda _: act_md + "\n",
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
    today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_event(vault: Path, action_type: str, **kwargs):
    write_log(vault, {
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "actor": "orchestrator",
        "action_type": action_type,
        **kwargs,
    })


# ── Agent trigger (multi-agent: claude / gemini / qwen) ──────────────────────

SILVER_PROMPT_TEMPLATE = """You are the AI Employee (Silver Tier). You work autonomously to process tasks.

Your vault is at: {vault}
Task file to process: {action_file}

## Your job

1. Read the task file at {action_file} to understand what is needed.
2. Read {vault}/Company_Handbook.md for rules of engagement.
3. Act based on the task type:

### If type == "email":
   - If the sender asks for a quotation, invoice, or financial document, you MUST first use your ERPNext tools to search for or generate the requested document BEFORE drafting your reply. Include the relevant details in your drafted reply.
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

### If type == "whatsapp":
   - If the sender asks for a quotation, invoice, or financial document, you MUST first use your ERPNext tools to search for or generate the requested document BEFORE drafting your reply. Include the relevant details in your drafted reply.
   - Draft a helpful and extremely concise reply to the WhatsApp message.
   - If there is a `## User Feedback` section present at the bottom of the file, strongly follow those instructions to revise your previous draft.
   - Create a file in {vault}/Pending_Approval/ named REPLY_WA_<timestamp>.md with this exact format:
     ```
     ---
     action: send_whatsapp
     jid: <sender's jid from the task file>
     created: <current UTC datetime in ISO format>
     ---

     <your drafted whatsapp reply here>
     ---
     ```
   - Move the original task file from {action_file} to {vault}/Done/

### If type == "linkedin_post":
   - Use the /post-linkedin skill to draft the post.
   - Create a file in {vault}/Pending_Approval/ with action: post_linkedin in frontmatter.
   - Move the original task file to {vault}/Done/

### If type == "twitter_post":
   - Use the /post-twitter skill to draft the tweet (max 280 chars).
   - Create a file in {vault}/Pending_Approval/ with action: post_twitter in frontmatter.
   - Move the original task file to {vault}/Done/

### If type == "facebook_post":
   - Use the /post-facebook skill to draft the post.
   - Create a file in {vault}/Pending_Approval/ with action: post_facebook in frontmatter.
   - Move the original task file to {vault}/Done/

### If type == "instagram_post":
   - Use the /post-instagram skill to draft the post.
   - Include image_url in the frontmatter of the Pending_Approval file.
   - Create a file in {vault}/Pending_Approval/ with action: post_instagram in frontmatter.
   - Move the original task file to {vault}/Done/

### If type == "erpnext_audit":
   - Use the /accounting-audit skill to pull data and write a snapshot.
   - Move the original task file to {vault}/Done/

### If type == "generate_plan":
   - Read the user's prompt in the task file to understand what plan needs to be created.
   - Draft a comprehensive plan with a Title, Description, Steps, and Due Date if applicable.
   - Create a file in {vault}/Pending_Approval/ named PLAN_DRAFT_<timestamp>.md with this exact format:
     ```
     ---
     action: save_plan
     title: <Drafted Title>
     created: <current UTC datetime>
     due_date: <Drafted Due Date or TBD>
     status: draft
     ---

     <your drafted plan body containing Description and Steps>
     ```
   - Move the original task file from {action_file} to {vault}/Done/

### If type == "accounting_request":
   - Read the user's prompt in the task file to understand the accounting task (e.g. review invoices, create invoice).
   - Use your ERPNext skills/tools to perform the requested actions.
   - Draft a summary of your actions and findings.
   - Create a file in {vault}/Pending_Approval/ named ACCOUNTING_REPORT_<timestamp>.md with this exact format:
     ```
     ---
     action: save_accounting_report
     title: Accounting Task Report
     created: <current UTC datetime>
     ---

     <your drafted summary body>
     ```
   - Move the original task file from {action_file} to {vault}/Done/

### For any other task:
   - Handle it appropriately and move the file to {vault}/Done/

## Rules
- NEVER send emails or post to LinkedIn directly — always write to /Pending_Approval/ first.
- Always move the processed action file to /Done/ when complete.
- Update {vault}/Dashboard.md last_updated field when done.

Output <promise>TASK_COMPLETE</promise> when finished.
"""

def trigger_agent(vault: Path, action_file: Path):
    """Trigger the selected AI agent (AGENT env var) to process a task file.

    Supported agents:
      - claude  → claude --print --dangerously-skip-permissions <prompt>
      - gemini  → gemini -p <prompt>
      - qwen    → qwen --prompt <prompt>
    """
    prompt = SILVER_PROMPT_TEMPLATE.format(
        vault=str(vault),
        action_file=str(action_file),
    )

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would trigger {AGENT} for: {action_file.name}")
        return

    config = AGENT_CONFIGS.get(AGENT)
    if not config:
        logger.error(f"Unknown AGENT='{AGENT}'. Supported: {', '.join(AGENT_CONFIGS.keys())}")
        return

    agent_cmd = _resolve_agent_cmd(AGENT)
    cmd = [*agent_cmd, *config["extra_flags"]]

    # Add MCP config if the agent supports it
    mcp_json = Path(__file__).parent.parent / "mcp.json"
    if config["mcp_flag"] and mcp_json.exists():
        cmd.extend([config["mcp_flag"], str(mcp_json)])

    # Write prompt to a temporary file to avoid Windows CMD length limits (8192 chars)
    prompt_file = vault / f".temp_prompt_{action_file.name}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    short_prompt = f"Please read and perfectly execute the instructions strictly written in the file: {prompt_file.absolute()}"

    # Add prompt
    cmd.extend([config["prompt_flag"], short_prompt])

    logger.info(f"Triggering {AGENT.upper()} for: {action_file.name}")
    try:
        try:
            result = subprocess.run(
                cmd,
                cwd=str(vault),
                capture_output=True,
                text=True,
                timeout=600,
                encoding="utf-8",
                errors="replace",
            )
        finally:
            # Cleanup temporary prompt file
            if prompt_file.exists():
                prompt_file.unlink()

        if result.returncode == 0:
            logger.info(f"{AGENT.upper()} completed: {action_file.name}")
            # Log a snippet of the agent's thought process/output
            snippet = result.stdout[:500].strip() + ("..." if len(result.stdout) > 500 else "")
            log_event(vault, "agent_processed", agent=AGENT, file=action_file.name, output_snippet=snippet)

            # QWEN robustness: sometimes it skips the tag but outputs the files.
            # We check if the files were created in /Pending_Approval or /Done
            # But safer to just look for common completion strings.
            output_lower = result.stdout.lower()
            if "task_complete" not in output_lower and "done" not in output_lower:
                logger.warning(f"{AGENT.upper()} finished but completion marker not found in output for: {action_file.name}")
            
            # Safety fallback: if the agent didn't move the file (common fail), 
            # we move it to Done if we see evidence of work.
            if action_file.exists() and ("pending_approval" in output_lower or "done" in output_lower):
                logger.info(f"Safety move for {action_file.name} to /Done")
                done_dir = vault / "Done"
                done_dir.mkdir(exist_ok=True)
                action_file.rename(done_dir / action_file.name)

        else:
            logger.error(f"{AGENT.upper()} error (code {result.returncode}): {result.stderr[:300]}")
    except FileNotFoundError:
        install_hints = {
            "claude": "npm install -g @anthropic/claude-code",
            "gemini": "npm install -g @google/gemini-cli",
            "qwen": "npm install -g @qwen-code/qwen-code@latest",
        }
        hint = install_hints.get(AGENT, f"Install the {AGENT} CLI")
        logger.error(f"'{AGENT}' CLI not found. Install with: {hint}")
    except subprocess.TimeoutExpired:
        logger.error(f"{AGENT.upper()} timed out (10 min) for: {action_file.name}")


# ── Approved action executor ──────────────────────────────────────────────────

class ApprovedActionExecutor:
    """
    Reads an approved file, determines the action type, and executes it.

    Supported action types:
      - send_email      → calls Email MCP server
      - send_whatsapp   → calls WhatsApp Baileys API directly
      - post_linkedin   → calls linkedin_poster.py
      - post_twitter    → calls twitter_poster.py
      - post_facebook   → calls meta_poster.py --platform facebook
      - post_instagram  → calls meta_poster.py --platform instagram
      - (others)        → logged and moved to Done
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
        action_type = "unknown"
        try:
            text = approved_file.read_text(encoding="utf-8")
            fields = parse_frontmatter(text)
            action_type = fields.get("action", "") or fields.get("type", "unknown")
            
            # Normalise type → action name
            type_map = {
                "linkedin_post": "post_linkedin", 
                "twitter_post": "post_twitter", 
                "facebook_post": "post_facebook", 
                "instagram_post": "post_instagram",
                "save_plan": "save_plan",
                "save_accounting_report": "save_accounting_report",
                "whatsapp": "send_whatsapp",
                "email": "send_email",
                "erpnext_audit": "acknowledge_only"
            }
            action_type = type_map.get(action_type, action_type)

            logger.info(f"Executing approved action: {action_type} — {approved_file.name}")

            done_dir = self.vault / "Done"
            done_dir.mkdir(exist_ok=True)

            if action_type == "acknowledge_only":
                logger.info(f"Action '{action_type}' manually acknowledged — skipping automation.")
                log_event(self.vault, "manual_acknowledgement", file=approved_file.name)
            elif action_type == "send_email":
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
            elif action_type == "save_plan":
                dest_dir = self.vault / "Plans"
                dest_dir.mkdir(exist_ok=True)
                dest = dest_dir / approved_file.name
                approved_file.rename(dest)
                logger.info(f"Plan saved to /Plans: {approved_file.name}")
                update_dashboard(self.vault)
                return
            elif action_type == "save_accounting_report":
                dest_dir = self.vault / "Accounting"
                dest_dir.mkdir(exist_ok=True)
                dest = dest_dir / approved_file.name
                approved_file.rename(dest)
                logger.info(f"Accounting report saved to /Accounting: {approved_file.name}")
                update_dashboard(self.vault)
                return
            else:
                logger.info(f"Action type '{action_type}' acknowledged — no automated execution defined.")
                log_event(self.vault, "action_acknowledged", file=approved_file.name, action=action_type)

            # Move to Done (add suffix if filename already exists)
            dest = done_dir / approved_file.name
            if dest.exists():
                ts = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%H%M%S")
                dest = done_dir / f"{approved_file.stem}_{ts}{approved_file.suffix}"
            try:
                approved_file.rename(dest)
                logger.info(f"Moved to /Done: {approved_file.name}")
            except FileNotFoundError:
                pass  # already moved by a duplicate event

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
                logger.error(f"Email MCP failed: {result.stderr[:2000]}")
                log_event(self.vault, "email_failed", to=to, error=result.stderr[:2000])
                raise RuntimeError(f"Email failed: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            logger.error("Email MCP timed out.")
            raise RuntimeError("Email timeout")

    def _execute_send_whatsapp(self, approved_file: Path, fields: dict, text: str):
        import requests
        
        jid = fields.get("jid", "")
        # Extract body after ---
        body_match = re.search(r"---\n\n(.+?)(?:\n\n---|$)", text, re.DOTALL)
        body = body_match.group(1).strip() if body_match else ""

        if not jid or not body:
            logger.error(f"WhatsApp missing jid or body in {approved_file.name}")
            raise ValueError("WhatsApp missing jid or body")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send WA to {jid}:\n{body[:100]}")
            log_event(self.vault, "whatsapp_sent_dry_run", jid=jid, text=body[:100])
            return

        try:
            # Baileys default port is 3001
            resp = requests.post("http://localhost:3001/send", json={"jid": jid, "text": body}, timeout=10)
            if resp.status_code == 200:
                logger.info(f"WhatsApp sent to {jid}")
                log_event(self.vault, "whatsapp_sent", jid=jid, approved_by="human", result="success")
            else:
                logger.error(f"WhatsApp sending failed: {resp.text}")
                log_event(self.vault, "whatsapp_failed", jid=jid, error=resp.text)
                raise RuntimeError(f"WhatsApp failed: {resp.text}")
        except Exception as e:
            logger.error(f"WhatsApp Baileys connection error: {e}")
            log_event(self.vault, "whatsapp_failed", jid=jid, error=str(e))
            raise RuntimeError(f"WhatsApp connection error: {e}")

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
                [sys.executable, str(poster_script), "--post"],
                input=json.dumps({"content": post_content}),
                capture_output=True,
                text=True,
                timeout=300, # Increased to 5 mins for manual login
                encoding="utf-8",
            )
            # Log script stdout/stderr for debugging
            if result.stdout: logger.info(f"LinkedIn Output: {result.stdout.strip()}")
            if result.stderr: logger.warning(f"LinkedIn Error: {result.stderr.strip()}")

            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("LinkedIn post published via Playwright.")
                log_event(self.vault, "linkedin_posted", approved_by="human", result="success")
            else:
                err = output.get("error", "Unknown error")
                logger.error(f"LinkedIn post failed: {err}")
                log_event(self.vault, "linkedin_failed", error=err)
                raise RuntimeError(f"LinkedIn failed: {err}")
                err = output.get("error", result.stderr[:2000])
                logger.error(f"LinkedIn poster failed: {err}")
                log_event(self.vault, "linkedin_failed", error=err)
                raise RuntimeError(f"LinkedIn failed: {err}")
        except subprocess.TimeoutExpired:
            logger.error("LinkedIn poster timed out.")
            log_event(self.vault, "linkedin_failed", error="timeout")
            raise RuntimeError("LinkedIn timeout")
        except Exception as e:
            logger.error(f"LinkedIn poster error: {e}")
            log_event(self.vault, "linkedin_failed", error=str(e))
            raise RuntimeError(f"LinkedIn poster error: {e}")


    def _execute_post_twitter(self, approved_file: Path, fields: dict, text: str):
        parts = text.split("---")
        post_content = parts[3].strip() if len(parts) > 3 else ""

        if not post_content:
            logger.error("Twitter: post content is empty — check the approval file format.")
            raise ValueError("Twitter: post content is empty")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Twitter:\n{post_content[:280]}")
            log_event(self.vault, "twitter_post_dry_run", content_preview=post_content[:100])
            return

        poster_script = Path(__file__).parent / "twitter_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--post"],
                input=json.dumps({"content": post_content}),
                capture_output=True,
                text=True,
                timeout=300, # Increased to 5 mins for manual login
                encoding="utf-8",
                errors="replace",
            )
            # Log script stdout/stderr for debugging
            if result.stdout: logger.info(f"Twitter Output: {result.stdout.strip()}")
            if result.stderr: logger.warning(f"Twitter Error: {result.stderr.strip()}")

            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Twitter post published via Playwright.")
                log_event(self.vault, "twitter_posted", approved_by="human", result="success")
            else:
                err = output.get("error", result.stderr[:2000])
                logger.error(f"Twitter poster failed: {err}")
                log_event(self.vault, "twitter_failed", error=err)
                raise RuntimeError(f"Twitter failed: {err}")
        except subprocess.TimeoutExpired:
            logger.error("Twitter poster timed out.")
            log_event(self.vault, "twitter_failed", error="timeout")
            raise RuntimeError("Twitter timeout")
        except Exception as e:
            logger.error(f"Twitter poster error: {e}")
            log_event(self.vault, "twitter_failed", error=str(e))
            raise RuntimeError(f"Twitter poster error: {e}")

    def _execute_post_facebook(self, approved_file: Path, fields: dict, text: str):
        parts = text.split("---")
        post_content = parts[3].strip() if len(parts) > 3 else ""

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Facebook:\n{post_content[:200]}")
            log_event(self.vault, "facebook_post_dry_run", content_preview=post_content[:100])
            return

        poster_script = Path(__file__).parent / "meta_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--platform", "facebook", "--post"],
                input=json.dumps({"content": post_content}),
                capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
            )
            # Log script stdout/stderr for debugging
            if result.stdout: logger.info(f"Facebook Output: {result.stdout.strip()}")
            if result.stderr: logger.warning(f"Facebook Error: {result.stderr.strip()}")

            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Facebook post published via Playwright.")
                log_event(self.vault, "facebook_posted", approved_by="human", result="success")
            else:
                err = output.get("error", result.stderr[:2000])
                logger.error(f"Facebook poster failed: {err}")
                log_event(self.vault, "facebook_failed", error=err)
                raise RuntimeError(f"Facebook failed: {err}")
        except subprocess.TimeoutExpired:
            logger.error("Facebook poster timed out.")
            log_event(self.vault, "facebook_failed", error="timeout")
            raise RuntimeError("Facebook timeout")
        except Exception as e:
            logger.error(f"Facebook poster error: {e}")
            log_event(self.vault, "facebook_failed", error=str(e))
            raise RuntimeError(f"Facebook poster error: {e}")

    def _execute_post_instagram(self, approved_file: Path, fields: dict, text: str):
        parts = text.split("---")
        post_content = parts[3].strip() if len(parts) > 3 else ""
        image_url = fields.get("image_url", "")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to Instagram (image: {image_url}):\n{post_content[:200]}")
            log_event(self.vault, "instagram_post_dry_run", content_preview=post_content[:100])
            return

        if not image_url:
            logger.error("Instagram post missing image_url in frontmatter — skipping.")
            log_event(self.vault, "instagram_failed", error="missing_image_url", file=approved_file.name)
            raise ValueError("Instagram missing image_url")

        poster_script = Path(__file__).parent / "meta_poster.py"
        try:
            result = subprocess.run(
                [sys.executable, str(poster_script), "--platform", "instagram", "--post"],
                input=json.dumps({"content": post_content, "image_url": image_url}),
                capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
            )
            # Log script stdout/stderr for debugging
            if result.stdout: logger.info(f"Instagram Output: {result.stdout.strip()}")
            if result.stderr: logger.warning(f"Instagram Error: {result.stderr.strip()}")

            output = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
            if output.get("success"):
                logger.info("Instagram post published via Playwright.")
                log_event(self.vault, "instagram_posted", approved_by="human", result="success")
            else:
                err = output.get("error", result.stderr[:2000])
                logger.error(f"Instagram poster failed: {err}")
                log_event(self.vault, "instagram_failed", error=err)
                raise RuntimeError(f"Instagram failed: {err}")
        except subprocess.TimeoutExpired:
            logger.error("Instagram poster timed out.")
            log_event(self.vault, "instagram_failed", error="timeout")
            raise RuntimeError("Instagram timeout")
        except Exception as e:
            logger.error(f"Instagram poster error: {e}")
            log_event(self.vault, "instagram_failed", error=str(e))
            raise RuntimeError(f"Instagram poster error: {e}")


# ── Approval expiry handler ───────────────────────────────────────────────────

def expire_stale_approvals(vault: Path):
    """Move Pending_Approval files older than APPROVAL_EXPIRY_HOURS to /Rejected."""
    pending_dir = vault / "Pending_Approval"
    rejected_dir = vault / "Rejected"
    if not pending_dir.exists():
        return

    rejected_dir.mkdir(exist_ok=True)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=APPROVAL_EXPIRY_HOURS)

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
            trigger_agent(self.vault, action_file)
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
    logger.info(f"Orchestrator (Gold) starting [{mode}] — Agent: {AGENT.upper()} — vault: {vault}")

    executor = ApprovedActionExecutor(vault)

    needs_handler    = NeedsActionHandler(vault)
    approved_handler = ApprovedHandler(vault, executor)

    observer = Observer()
    observer.schedule(needs_handler, str(vault / "Needs_Action"), recursive=False)
    observer.schedule(approved_handler, str(vault / "Approved"), recursive=False)
    observer.start()

    # Process any files already sitting in /Needs_Action/ before we started
    needs_action_dir = vault / "Needs_Action"
    for f in sorted(needs_action_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            logger.info(f"Startup: found existing needs_action file: {f.name}")
            log_event(vault, "needs_action_detected", file=f.name)
            trigger_agent(vault, f)

    # Process any files already sitting in /Approved/ before we started
    approved_dir = vault / "Approved"
    for f in sorted(approved_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            logger.info(f"Startup: found existing approved file: {f.name}")
            log_event(vault, "action_approved", file=f.name, approved_by="human")
            executor.execute(f)

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
