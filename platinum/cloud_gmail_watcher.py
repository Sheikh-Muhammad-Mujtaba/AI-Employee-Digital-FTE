"""
cloud_gmail_watcher.py - Platinum Tier Cloud Gmail Watcher

This watcher runs on the Cloud VM and:
1. Polls Gmail for new emails
2. Creates action files in Cloud/Needs_Action/
3. Cloud Agent processes and creates drafts in Cloud/Drafts/Email/
4. Writes approval signals to Cloud/Updates/

Key difference from local watcher:
- Does NOT send emails directly
- Writes drafts to Cloud/Drafts/ for Local approval
- Uses Git sync to transfer drafts to Local

Usage:
    python cloud_gmail_watcher.py --vault /opt/ai-employee/vault
"""

import argparse
import os
import sys
import base64
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Gmail OAuth config
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")

# Platinum Tier folders
CLOUD_VAULT = None  # Set via --vault argument
DRAFTS_FOLDER = None
UPDATES_FOLDER = None

URGENT_KEYWORDS = ["urgent", "asap", "emergency", "critical", "immediate"]
HIGH_KEYWORDS = ["invoice", "payment", "contract", "legal", "deadline", "client", "proposal"]


def _detect_priority(subject: str, snippet: str) -> str:
    text = (subject + " " + snippet).lower()
    if any(kw in text for kw in URGENT_KEYWORDS):
        return "urgent"
    if any(kw in text for kw in HIGH_KEYWORDS):
        return "high"
    return "normal"


class CloudGmailWatcher(BaseWatcher):
    """
    Platinum Tier Cloud Gmail Watcher.
    
    Unlike the local watcher, this:
    - Only creates drafts (never sends)
    - Writes to Cloud/Drafts/Email/
    - Signals Local via Cloud/Updates/
    """

    def __init__(self, vault_path: str, interval: int = 120):
        # Override to use Cloud folders
        self.cloud_vault = Path(vault_path)
        self.drafts_folder = self.cloud_vault / "Drafts" / "Email"
        self.updates_folder = self.cloud_vault / "Updates"
        self.drafts_folder.mkdir(parents=True, exist_ok=True)
        self.updates_folder.mkdir(parents=True, exist_ok=True)
        
        super().__init__(vault_path, check_interval=interval)
        self.service = None
        self._partial_auth = False
        self._processed_ids: set[str] = set()
        self._load_processed_ids()

    def _processed_ids_file(self) -> Path:
        return self.vault_path / "Logs" / ".gmail_processed_ids.txt"

    def _load_processed_ids(self):
        cache = self._processed_ids_file()
        if cache.exists():
            self._processed_ids = set(cache.read_text().splitlines())

    def _save_processed_ids(self):
        cache = self._processed_ids_file()
        cache.write_text("\n".join(self._processed_ids))

    def _build_service(self):
        """Build Gmail API service."""
        if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
            self.logger.error("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set")
            self._partial_auth = True
            return

        if not GMAIL_REFRESH_TOKEN:
            self.logger.warning("Gmail running in partial auth mode")
            self._partial_auth = True
            return

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            self.logger.error("Google API libraries not installed")
            self._partial_auth = True
            return

        try:
            creds = Credentials(
                token=None,
                refresh_token=GMAIL_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GMAIL_CLIENT_ID,
                client_secret=GMAIL_CLIENT_SECRET,
                scopes=SCOPES,
            )
            creds.refresh(Request())
            self.service = build("gmail", "v1", credentials=creds)
            self._partial_auth = False
            self.logger.info("Gmail API authenticated")
        except Exception as e:
            self.logger.error(f"Gmail auth failed: {e}")
            self._partial_auth = True

    def check_for_updates(self) -> list:
        """Fetch unread emails not yet processed."""
        if self.service is None:
            self._build_service()

        if self._partial_auth:
            return []

        try:
            query = "is:unread -in:sent"
            result = self.service.users().messages().list(
                userId="me", q=query, maxResults=20
            ).execute()
        except Exception as e:
            self.logger.error(f"Gmail API error: {e}")
            return []

        messages = result.get("messages", [])
        new = [m for m in messages if m["id"] not in self._processed_ids]
        self.logger.info(f"Gmail: {len(new)} new messages")
        return new

    def create_action_file(self, message: dict) -> Path:
        """
        Create action file in Cloud/Needs_Action/ and draft in Cloud/Drafts/Email/.
        
        Platinum Tier: Creates both the trigger file AND the draft response.
        """
        msg_id = message["id"]
        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            self.logger.error(f"Failed to fetch message: {e}")
            self._processed_ids.add(msg_id)
            self._save_processed_ids()
            raise

        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(No Subject)")
        sender = headers.get("From", "Unknown")
        date = headers.get("Date", datetime.utcnow().isoformat())
        snippet = msg.get("snippet", "")
        priority = _detect_priority(subject, snippet)
        body = self._extract_body(msg["payload"])

        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", msg_id)[:20]
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Create action file in Cloud/Needs_Action/
        action_path = self.needs_action / f"EMAIL_{safe_id}_{ts}.md"
        action_content = f"""---
type: email
message_id: {msg_id}
from: {sender}
subject: {subject}
date_received: {date}
priority: {priority}
status: pending
cloud_processed: true
---

## Email Received (Cloud Processed)

**From:** {sender}
**Subject:** {subject}
**Received:** {date}
**Priority:** {priority}

---

## Snippet

{snippet}

---

## Full Body

{body if body else "_(Body not extractable)_"}

---

## Cloud Agent Actions

- [ ] Draft reply created in Cloud/Drafts/Email/
- [ ] Approval signal written to Cloud/Updates/
- [ ] Awaiting Local approval to send
"""
        if not DRY_RUN:
            action_path.write_text(action_content, encoding="utf-8")

        # Create draft reply in Cloud/Drafts/Email/
        draft_path = self.drafts_folder / f"DRAFT_REPLY_{safe_id}_{ts}.md"
        draft_content = f"""---
action: send_email
to: {sender}
subject: Re: {subject}
created: {datetime.now(timezone.utc).isoformat()}
priority: {priority}
cloud_draft: true
requires_local_approval: true
---

## Draft Reply (Cloud Generated)

Dear Sender,

Thank you for your email regarding "{subject}".

[AI Agent: Insert contextual reply based on Company_Handbook.md and Business_Goals.md]

Best regards,
AI Employee

---

## Processing Notes

- Generated by: Cloud Agent (Platinum Tier)
- Requires: Local approval before sending
- Sync: Will appear in Local/Pending_Approval/ after Git sync
"""
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create draft: {draft_path.name}")
        else:
            draft_path.write_text(draft_content, encoding="utf-8")

        # Write approval signal to Cloud/Updates/
        signal_path = self.updates_folder / f"APPROVAL_EMAIL_{safe_id}_{ts}.md"
        signal_content = f"""---
type: approval_signal
source: cloud_gmail_watcher
draft_file: {draft_path.name}
action_type: send_email
priority: {priority}
created: {datetime.now(timezone.utc).isoformat()}
---

## Approval Required

Cloud Agent has processed an email and created a draft reply.

**Draft:** `{draft_path.name}`
**Action:** Send email reply
**Priority:** {priority}

## Local Action Required

1. Review draft in Local/Pending_Approval/
2. If approved, move to Local/Approved/
3. Local Orchestrator will send via Email MCP
"""
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create signal: {signal_path.name}")
        else:
            signal_path.write_text(signal_content, encoding="utf-8")

        self._processed_ids.add(msg_id)
        self._save_processed_ids()

        self.logger.info(f"Created draft and signal for email from {sender}")
        return action_path

    def _extract_body(self, payload: dict) -> str:
        """Extract plain-text body from Gmail payload."""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result
        return ""


def main():
    parser = argparse.ArgumentParser(description="Platinum Tier - Cloud Gmail Watcher")
    parser.add_argument(
        "--vault",
        required=True,
        help="Path to Cloud vault (e.g., /opt/ai-employee/vault)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=120,
        help="Poll interval in seconds",
    )
    args = parser.parse_args()

    watcher = CloudGmailWatcher(vault_path=args.vault, interval=args.interval)

    if DRY_RUN:
        watcher.logger.info("Running in DRY RUN mode")

    watcher.run()


if __name__ == "__main__":
    main()
