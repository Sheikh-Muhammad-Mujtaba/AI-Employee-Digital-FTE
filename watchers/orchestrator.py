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

# Agent CLI configs: 
# - "cmd": base command to invoke agent
# - "prompt_flag": flag to pass prompt content (--print, -p, --prompt)
# - "extra_flags": YOLO mode flags to auto-approve all actions without permission
# - "mcp_flag": flag to load MCP servers for skills (email, erpnext, browser, etc.)
#
# YOLO MODE: All agents run with flags to auto-accept actions (skip permission prompts)
# ✓ claude: uses --dangerously-skip-permissions + --permission-mode bypassPermissions
# ✓ qwen:   uses --approval-mode=yolo (combined flag, not separate --yolo)
# ✓ gemini: uses --approval-mode=yolo (combined flag, not separate --yolo)
#
# SKILLS: Loaded via mcp.json if it exists (copy from example.mcp.json)
# ✓ email: Gmail integration (send/draft emails)
# ✓ erpnext: ERPNext API for accounting/business data
# ✓ browser: Web automation (forms, scraping, RPA)
# ✓ windows: Desktop UI automation (click, type, screenshot, shell)

AGENT_CONFIGS: dict[str, dict] = {
    "claude": {
        "cmd": ["claude"],
        "prompt_flag": "--print",
        "extra_flags": ["--dangerously-skip-permissions", "--permission-mode", "bypassPermissions"],
        "mcp_flag": "--mcp-config",
    },
    "gemini": {
        "cmd": ["gemini"],
        "prompt_flag": "-p",
        "extra_flags": ["--approval-mode=yolo"],
        "mcp_flag": None,  # gemini reads from ~/.gemini/settings.json
    },
    "qwen": {
        "cmd": ["qwen"],
        "prompt_flag": "--prompt",
        "extra_flags": ["--approval-mode=yolo"],
        "mcp_flag": None,  # qwen uses 'qwen mcp' command, not a flag
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


def extract_body_content(text: str) -> str:
    """Return text after frontmatter, or full text if no frontmatter."""
    if not text:
        return ""
    trimmed = text.strip()
    if trimmed.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)$", trimmed, re.DOTALL)
        if m:
            return m.group(1).strip()
    return trimmed


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

SILVER_PROMPT_TEMPLATE = r"""You are the AI Employee. You process tasks in TWO stages.

**Vault Location:** .\\AI_Employee_Vault\\

**CURRENT STAGE:** Check which folder the file is in:
- **Needs_Action\\** = STAGE 1 (DRAFTING) - Create a draft ONLY
- **Pending_Approval\\** = STAGE 2 (EXECUTION) - Execute the action

─────────────────────────────────────────────────────────────────

## STAGE 1: DRAFTING (File in Needs_Action/)

**YOUR TASK:** Read the input file and CREATE A DRAFT reply/post.

**IMPORTANT:** 
- DO NOT send emails
- DO NOT post to social media  
- DO NOT send WhatsApp messages
- ONLY create a draft file in Pending_Approval/

**After creating the draft:**
1. Save draft to: .\Pending_Approval\\
2. Move original file to: .\Done\\
3. Output: <promise>TASK_COMPLETE</promise>

─────────────────────────────────────────────────────────────────

## STAGE 2: EXECUTION (File in Pending_Approval/)

**YOUR TASK:** Read the draft and EXECUTE the action.

**Actions to execute:**
- If action: send_email → Send the email
- If action: send_whatsapp → Send the WhatsApp message
- If action: post_linkedin → Post to LinkedIn
- If action: post_twitter → Post to Twitter
- If action: post_facebook → Post to Facebook
- If action: post_instagram → Post to Instagram

**After executing:**
1. Perform the action (send/post)
2. Move file to: .\AI_Employee_Vault\\Done\\
3. Output: <promise>TASK_COMPLETE</promise>

─────────────────────────────────────────────────────────────────

## Task Type Instructions

### EMAIL (type: email)

**STAGE 1 (Drafting):**
- Read the email from sender
- Draft a professional reply
- Extract sender email from the "from" field in frontmatter
- Use current timestamp in ISO format (e.g., 2026-03-20T17:48:15Z)
- Create file: .\Pending_Approval\\REPLY_{{sender_name}}_{{timestamp}}.md
- Format:
```markdown
---
action: send_email
to: sender@email.com
subject: Re: Original Subject
created: 2026-03-19T19:00:00Z
---

Dear Sender,

[Your drafted reply here]

Best regards,
AI Employee
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use email MCP to SEND the email
- Move file to Done/

### WHATSAPP (type: whatsapp)

**STAGE 1 (Drafting):**
- Read the WhatsApp message
- Draft a concise and context-aware reply
- Extract sender name from the "from" field in frontmatter
- Extract JID from the "jid" field in frontmatter (e.g., 923xxxx@g.us or 923xxxx@s.whatsapp.net)
- Use current timestamp in ISO format (e.g., 2026-03-20T17:48:15Z)
- Create file: .\Pending_Approval\\REPLY_WA_{{sender_name}}_{{timestamp}}.md
- Format:
```markdown
---
action: send_whatsapp
jid: 1234567890@s.whatsapp.net
created: 2026-03-19T19:00:00Z
---

[Your drafted WhatsApp reply]
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use WhatsApp Baileys API to SEND the message
- Move file to Done/

### LINKEDIN POST (type: linkedin_post)

**STAGE 1 (Drafting):**
- Read the topic from the file
- Draft a professional LinkedIn post
- Create file: .\Pending_Approval\\LINKEDIN_{{title}}_{{timestamp}}.md
- Format:
```markdown
---
action: post_linkedin
created: 2026-03-19T19:00:00Z
---

[Your drafted LinkedIn post with hashtags]
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use LinkedIn poster to PUBLISH the post
- Move file to Done/

### TWITTER POST (type: twitter_post)

**STAGE 1 (Drafting):**
- Read the topic from the file
- Draft a tweet (MAX 200 characters Importand else the post will fail)
- Include character count at end
- Create file: .\Pending_Approval\\TWITTER_{{title}}_{{timestamp}}.md
- Format:
```markdown
---
action: post_twitter
created: 2026-03-19T19:00:00Z
---

[Your drafted tweet - max 200 chars (Strict)]

Characters: 185
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use Twitter poster to PUBLISH the tweet
- Move file to Done/

### FACEBOOK POST (type: facebook_post)

**STAGE 1 (Drafting):**
- Read the topic from the file
- Draft a Facebook post
- Create file: .\Pending_Approval\\FACEBOOK_{{title}}_{{timestamp}}.md
- Format:
```markdown
---
action: post_facebook
created: 2026-03-19T19:00:00Z
---

[Your drafted Facebook post with hashtags]
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use Facebook poster to PUBLISH the post
- Move file to Done/

### INSTAGRAM POST (type: instagram_post)

**STAGE 1 (Drafting):**
- Read the topic from the file
- Draft an Instagram caption
- Include image_url in frontmatter
- Create file: .\AI_Employee_Vault\\Pending_Approval\\INSTAGRAM_{{title}}_{{timestamp}}.md
- Format:
```markdown
---
action: post_instagram
image_url: https://example.com/image.png
created: 2026-03-19T19:00:00Z
---

[Your drafted Instagram caption with hashtags]
```

**STAGE 2 (Execution):**
- Read the draft from Pending_Approval/
- Use Instagram poster to PUBLISH the post
- Move file to Done/

─────────────────────────────────────────────────────────────────

**REMEMBER:**
- Check folder to determine stage
- Stage 1 (Needs_Action/) = CREATE DRAFT ONLY
- Stage 2 (Pending_Approval/) = EXECUTE ACTION
- Always output <promise>TASK_COMPLETE</promise> when done
"""

def _action_requires_approval(action_file: Path, output_lower: str) -> bool:
    name = action_file.name.upper()
    if any(name.startswith(prefix) for prefix in ["EMAIL_", "WHATSAPP_", "LINKEDIN_", "TWITTER_", "FACEBOOK_", "INSTAGRAM_"]):
        return True
    if any(token in output_lower for token in ["action: send_email", "action: send_whatsapp", "action: post_linkedin", "action: post_twitter", "action: post_facebook", "action: post_instagram"]):
        return True
    return False


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
        logger.debug(f"MCP config loaded: {mcp_json}")
    elif config["mcp_flag"] and not mcp_json.exists():
        logger.warning(f"MCP config not found at {mcp_json}. Skills may be unavailable.")

    # Write prompt to a temporary file to avoid Windows CMD length limits (8192 chars)
    prompt_file = vault / f".temp_prompt_{action_file.name}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    short_prompt = f"Please read and perfectly execute the instructions strictly written in the file: {prompt_file.absolute()}"

    # Add prompt
    cmd.extend([config["prompt_flag"], short_prompt])

    pending_before = set()
    pending_approval_dir = vault / "Pending_Approval"
    if pending_approval_dir.exists():
        pending_before = {f.name for f in pending_approval_dir.iterdir() if f.is_file()}

    logger.info(f"Triggering {AGENT.upper()} for: {action_file.name} [YOLO mode enabled]")
    logger.debug(f"Command: {' '.join(cmd)}")
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

        if result.returncode != 0:
            logger.error(f"{AGENT.upper()} error (code {result.returncode}): {result.stderr[:300]}")
            log_event(vault, "agent_failed", agent=AGENT, file=action_file.name, error=result.stderr[:300])
            return

        logger.info(f"{AGENT.upper()} completed: {action_file.name}")
        snippet = result.stdout[:500].strip() + ("..." if len(result.stdout) > 500 else "")
        log_event(vault, "agent_processed", agent=AGENT, file=action_file.name, output_snippet=snippet)

        pending_after = {f.name for f in pending_approval_dir.iterdir() if f.is_file()} if pending_approval_dir.exists() else set()
        new_drafts = list(pending_after - pending_before)

        output_lower = result.stdout.lower()
        requires_approval = _action_requires_approval(action_file, output_lower)

        if requires_approval and not new_drafts:
            logger.warning(f"⚠️ {AGENT.upper()} processed {action_file.name} but no new /Pending_Approval draft was detected")
            logger.warning("Action requires approval but agent output did not create a draft; moving file to Needs_Action_Failed for manual review.")

            failed_dir = vault / "Needs_Action_Failed"
            failed_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fail_dest = failed_dir / f"{action_file.stem}_failed_{ts}{action_file.suffix}"
            action_file.rename(fail_dest)
            logger.error(f"❌ Moved {action_file.name} to /Needs_Action_Failed/ (as {fail_dest.name})")
            log_event(vault, "task_failed_no_draft", file=action_file.name, action_file=fail_dest.name)
            return

        if action_file.exists():
            done_dir = vault / "Done"
            done_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%H%M%S")
            dest = done_dir / f"{action_file.stem}_{ts}{action_file.suffix}"
            action_file.rename(dest)
            logger.info(f"✅ Moved {action_file.name} to /Done/ (as {dest.name})")
            log_event(vault, "task_completed", file=action_file.name, drafts_created=len(new_drafts), requires_approval=requires_approval)

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
        log_event(vault, "agent_timeout", agent=AGENT, file=action_file.name)


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
        now = datetime.now(timezone.utc)
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
                "erpnext_audit": "acknowledge_only",
                "accounting_audit": "run_accounting_audit",
                "run_accounting_audit": "run_accounting_audit"
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
            elif action_type == "run_accounting_audit":
                self._execute_run_accounting_audit(approved_file, fields, text)
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

        # Extract body using unified helper (strips frontmatter)
        body = extract_body_content(text)

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send email to: {to} | Subject: {subject}")
            log_event(self.vault, "email_sent_dry_run", to=to, subject=subject)
            return

        if not to or not subject:
            logger.error(f"Email draft is missing required fields: to='{to}' subject='{subject}' in {approved_file.name}")
            log_event(self.vault, "email_failed_missing_fields", file=approved_file.name, to=to, subject=subject)
            raise ValueError("Email missing required fields: to and subject")

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
                self._emails_this_hour.append(datetime.now(timezone.utc))
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

    def _is_whatsapp_connected(self) -> bool:
        import requests
        try:
            resp = requests.get("http://localhost:3001/status", timeout=5)
            if resp.ok:
                data = resp.json()
                return data.get("status") == "connected"
        except Exception as e:
            logger.warning(f"Failed to get WhatsApp status: {e}")
        return False

    def _execute_send_whatsapp(self, approved_file: Path, fields: dict, text: str):
        import requests

        jid = fields.get("jid", "")
        # Extract body after ---
        body_match = re.search(r"---\n\n(.+?)(?:\n\n---|$)", text, re.DOTALL)
        body = body_match.group(1).strip() if body_match else ""

        if not jid or not body:
            logger.error(f"WhatsApp missing jid or body in {approved_file.name}")
            raise ValueError("WhatsApp missing jid or body")

        if not self._is_whatsapp_connected():
            logger.warning("WhatsApp connector is not connected (status != connected)")
            log_event(self.vault, "whatsapp_not_connected", file=approved_file.name, jid=jid)
            raise RuntimeError("WhatsApp not connected")

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would send WA to {{jid}}:\n{body[:100]}")
            log_event(self.vault, "whatsapp_sent_dry_run", jid=jid, text=body[:100])
            return

        try:
            # Baileys default port is 3001
            resp = requests.post("http://localhost:3001/send", json={"jid": jid, "text": body}, timeout=30)
            if resp.status_code == 200:
                logger.info(f"WhatsApp sent to {jid}")
                log_event(self.vault, "whatsapp_sent", jid=jid, approved_by="human", result="success")
            else:
                logger.error(f"WhatsApp sending failed: {resp.text}")
                log_event(self.vault, "whatsapp_failed", jid=jid, error=resp.text)
                raise RuntimeError(f"WhatsApp failed: {resp.text}")
        except requests.exceptions.ConnectTimeout as e:
            logger.error(f"WhatsApp connection timeout: {e}")
            log_event(self.vault, "whatsapp_connection_timeout", jid=jid, error=str(e))
            raise RuntimeError("WhatsApp connection timeout")
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"WhatsApp read timeout: {e}")
            log_event(self.vault, "whatsapp_read_timeout", jid=jid, error=str(e))
            raise RuntimeError("WhatsApp read timeout")
        except Exception as e:
            logger.error(f"WhatsApp failed with exception: {e}")
            log_event(self.vault, "whatsapp_failed", jid=jid, error=str(e))
            raise
        except Exception as e:
            logger.error(f"WhatsApp Baileys connection error: {e}")
            log_event(self.vault, "whatsapp_failed", jid=jid, error=str(e))
            raise RuntimeError(f"WhatsApp connection error: {e}")

    def _execute_post_linkedin(self, approved_file: Path, fields: dict, text: str):
        post_content = extract_body_content(text)

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
        post_content = extract_body_content(text)

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
        post_content = extract_body_content(text)

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
        post_content = extract_body_content(text)
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

    def _execute_run_accounting_audit(self, approved_file: Path, fields: dict, text: str):
        """Execute accounting audit using ERPNext MCP server."""
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would run accounting audit for: {approved_file.name}")
            log_event(self.vault, "accounting_audit_dry_run", file=approved_file.name)
            return

        # Check if ERPNext MCP is available
        erpnext_mcp_path = os.getenv("ERPNEXT_MCP_PATH", "")
        if not erpnext_mcp_path:
            logger.warning("ERPNEXT_MCP_PATH not set. Cannot run accounting audit. Set it in .env")
            log_event(self.vault, "accounting_audit_skipped", reason="ERPNEXT_MCP_PATH_not_set", file=approved_file.name)
            return

        # Extract audit parameters from frontmatter or body
        audit_type = fields.get("audit_type", "general")
        period = fields.get("period", "current_month")
        company = fields.get("company", "default")

        # Prepare audit request
        audit_request = {
            "action": "run_audit",
            "audit_type": audit_type,
            "period": period,
            "company": company,
            "source_file": str(approved_file.name)
        }

        try:
            # Call ERPNext MCP server
            result = subprocess.run(
                ["python", "-m", "ERP_Next-MCP.src.server"],
                input=json.dumps(audit_request),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for audit
                encoding="utf-8",
                cwd=Path(erpnext_mcp_path).parent if erpnext_mcp_path else None
            )

            if result.returncode == 0:
                try:
                    audit_result = json.loads(result.stdout.strip())
                    logger.info(f"Accounting audit completed: {audit_result.get('summary', 'Success')}")
                    log_event(self.vault, "accounting_audit_complete",
                             file=approved_file.name,
                             audit_type=audit_type,
                             period=period,
                             result="success")
                except json.JSONDecodeError:
                    logger.info("Accounting audit completed (no detailed results)")
                    log_event(self.vault, "accounting_audit_complete",
                             file=approved_file.name,
                             audit_type=audit_type,
                             result="success")
            else:
                logger.error(f"Accounting audit failed: {result.stderr[:1000]}")
                log_event(self.vault, "accounting_audit_failed",
                         file=approved_file.name,
                         error=result.stderr[:1000])
                raise RuntimeError(f"Accounting audit failed: {result.stderr[:500]}")

        except subprocess.TimeoutExpired:
            logger.error("Accounting audit timed out (5 minutes)")
            log_event(self.vault, "accounting_audit_timeout", file=approved_file.name)
            raise RuntimeError("Accounting audit timeout")
        except Exception as e:
            logger.error(f"Accounting audit error: {e}")
            log_event(self.vault, "accounting_audit_error", file=approved_file.name, error=str(e))
            raise RuntimeError(f"Accounting audit error: {e}")


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

    # Check MCP config availability
    mcp_json = Path(__file__).parent.parent / "mcp.json"
    mcp_example = Path(__file__).parent.parent / "example.mcp.json"
    if not mcp_json.exists() and mcp_example.exists():
        logger.warning(f"⚠️  MCP config not found: {mcp_json}")
        logger.warning(f"   To enable skills for email, social posts, and accounting:")
        logger.warning(f"   1. Copy: cp {mcp_example} {mcp_json}")
        logger.warning(f"   2. Update environment variables in .env (GMAIL_CLIENT_ID, ERPNEXT_URL, etc.)")
        logger.warning(f"   3. Restart orchestrator")
        logger.info(f"   Proceeding without skills — agents will run with limited capabilities.")
    elif mcp_json.exists():
        logger.info(f"✓ MCP config loaded: {mcp_json}")
        logger.info(f"  Available skills: email, erpnext, browser, windows")

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    logger.info(f"Orchestrator (Gold) starting [{mode}] — Agent: {AGENT.upper()} [YOLO MODE: auto-approve all actions] — vault: {vault}")


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
