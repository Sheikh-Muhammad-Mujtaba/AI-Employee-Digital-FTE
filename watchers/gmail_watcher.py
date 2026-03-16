"""
gmail_watcher.py - Polls Gmail for important unread emails (Silver Tier).

When a matching email arrives, this watcher creates a structured .md action
file in /Needs_Action/ so the Orchestrator can trigger Claude to process it.

Auth (env-var driven — no credential files required):
  1. Go to console.cloud.google.com → New Project → Enable Gmail API
  2. Create OAuth 2.0 credentials (Desktop App type) — note Client ID and Secret
  3. Set in .env:
       GMAIL_CLIENT_ID=your_client_id
       GMAIL_CLIENT_SECRET=your_client_secret
  4. Run once to get your refresh token:
       python gmail_watcher.py --get-token
     Copy the printed GMAIL_REFRESH_TOKEN value into your .env file.
  5. Subsequent runs use GMAIL_REFRESH_TOKEN from .env automatically.

Usage:
    python gmail_watcher.py --vault /path/to/AI_Employee_Vault
    python gmail_watcher.py --vault /path/to/AI_Employee_Vault --interval 120
    python gmail_watcher.py --get-token   # one-time OAuth flow → prints refresh token

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv
"""

import argparse
import os
import sys
import base64
import re
from datetime import datetime
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# ── Gmail OAuth config (from env only) ────────────────────────────────────────

SCOPES             = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
GMAIL_CLIENT_ID    = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")

# ── Priority keyword detection ────────────────────────────────────────────────

URGENT_KEYWORDS = ["urgent", "asap", "emergency", "critical", "immediate"]
HIGH_KEYWORDS   = ["invoice", "payment", "contract", "legal", "deadline", "client", "proposal"]


def _detect_priority(subject: str, snippet: str) -> str:
    text = (subject + " " + snippet).lower()
    if any(kw in text for kw in URGENT_KEYWORDS):
        return "urgent"
    if any(kw in text for kw in HIGH_KEYWORDS):
        return "high"
    return "normal"


# ── One-time token flow ────────────────────────────────────────────────────────

def run_get_token_flow():
    """
    Interactive OAuth flow using GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET from env.
    Prints the refresh token to stdout in a copyable format.
    Does NOT write any files.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib")
        sys.exit(1)

    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
        print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env before running --get-token")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }

    print("\nStarting Gmail OAuth flow. A browser window will open...")
    print("Grant access, then return here.\n")

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 64)
    print("  GMAIL REFRESH TOKEN — copy this into your .env file:")
    print("=" * 64)
    print(f"\nGMAIL_REFRESH_TOKEN={creds.refresh_token}\n")
    print("=" * 64)
    print("OAuth setup complete. Token NOT saved to any file (by design).")
    print("Add GMAIL_REFRESH_TOKEN to your .env and restart the watcher.\n")


# ── GmailWatcher ──────────────────────────────────────────────────────────────

class GmailWatcher(BaseWatcher):
    """
    Polls Gmail for unread important emails and writes action files to /Needs_Action.

    Auth is driven entirely from env vars:
      GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN

    If GMAIL_REFRESH_TOKEN is absent, the watcher starts in partial auth mode:
    the polling loop runs but no API calls are made until the token is provided.

    Filters applied when fully authenticated:
      - is:unread
      - is:important  (Gmail's smart priority inbox)
      - NOT in:sent   (to avoid processing sent mail)
    """

    def __init__(self, vault_path: str, interval: int = 120):
        super().__init__(vault_path, check_interval=interval)
        self.service = None
        self._partial_auth = False
        self._processed_ids: set[str] = set()
        self._load_processed_ids()

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _build_service(self):
        """Build the Gmail API service using env-var credentials. No file I/O."""
        if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
            self.logger.error(
                "GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env. "
                "See setup instructions at the top of this file."
            )
            self._partial_auth = True
            return

        if not GMAIL_REFRESH_TOKEN:
            self.logger.warning(
                "Gmail running in partial auth mode – refresh token not provided. "
                "Run `python gmail_watcher.py --get-token` to obtain one, "
                "then add GMAIL_REFRESH_TOKEN to your .env file."
            )
            self._partial_auth = True
            return

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            self.logger.error(
                "Google API libraries not installed. Run:\n"
                "  pip install google-auth google-auth-oauthlib google-api-python-client"
            )
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
            self.logger.info("Gmail API authenticated successfully (env-var credentials).")
        except Exception as e:
            self.logger.error(
                f"Gmail auth failed: {e}. "
                "Check GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN in .env. "
                "If the refresh token has expired, run `python gmail_watcher.py --get-token` again."
            )
            self._partial_auth = True

    # ── Processed ID cache ───────────────────────────────────────────────────

    def _processed_ids_file(self) -> Path:
        return self.vault_path / "Logs" / ".gmail_processed_ids.txt"

    def _load_processed_ids(self):
        cache = self._processed_ids_file()
        if cache.exists():
            self._processed_ids = set(cache.read_text().splitlines())
            self.logger.info(f"Loaded {len(self._processed_ids)} previously processed message IDs.")

    def _save_processed_ids(self):
        cache = self._processed_ids_file()
        cache.write_text("\n".join(self._processed_ids))

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Fetch unread important emails not yet processed."""
        if self.service is None:
            self._build_service()

        if self._partial_auth:
            self.logger.warning(
                "Gmail running in partial auth mode — skipping poll. "
                "Provide GMAIL_REFRESH_TOKEN in .env to enable full polling."
            )
            return []

        try:
            result = self.service.users().messages().list(
                userId="me",
                q="is:unread is:important -in:sent",
                maxResults=20,
            ).execute()
        except Exception as e:
            self.logger.error(f"Gmail API list error: {e}")
            return []

        messages = result.get("messages", [])
        new = [m for m in messages if m["id"] not in self._processed_ids]
        self.logger.info(f"Gmail: {len(messages)} unread important, {len(new)} new.")
        return new

    def create_action_file(self, message: dict) -> Path:
        """Fetch full message and write a .md action file to /Needs_Action."""
        msg_id = message["id"]
        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            self.logger.error(f"Failed to fetch message {msg_id}: {e}")
            self._processed_ids.add(msg_id)
            self._save_processed_ids()
            raise

        headers  = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject  = headers.get("Subject", "(No Subject)")
        sender   = headers.get("From", "Unknown")
        date     = headers.get("Date", datetime.utcnow().isoformat())
        snippet  = msg.get("snippet", "")
        priority = _detect_priority(subject, snippet)

        body = self._extract_body(msg["payload"])

        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", msg_id)[:20]
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        md_path = self.needs_action / f"EMAIL_{safe_id}_{ts}.md"

        content = f"""---
type: email
message_id: {msg_id}
from: {sender}
subject: {subject}
date_received: {date}
priority: {priority}
status: pending
---

## Email Received

**From:** {sender}
**Subject:** {subject}
**Received:** {date}
**Priority:** {priority}

---

## Snippet

{snippet}

---

## Full Body

{body if body else "_(Body not extractable — view in Gmail)_"}

---

## Suggested Actions

- [ ] Draft a reply (use /send-email skill)
- [ ] Forward to relevant party if needed
- [ ] Create a Plan if this requires multi-step work (use /create-plan)
- [ ] Archive / move to Done when complete

## Notes

_(Add context here after review.)_
"""
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create: {md_path.name}")
        else:
            md_path.write_text(content, encoding="utf-8")

        self._processed_ids.add(msg_id)
        self._save_processed_ids()
        return md_path

    # ── Body extractor ────────────────────────────────────────────────────────

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain-text body from Gmail message payload."""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result
        return ""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Gmail Watcher (Silver)")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("GMAIL_INTERVAL", "120")),
        help="Poll interval in seconds (default: 120)",
    )
    parser.add_argument(
        "--get-token",
        action="store_true",
        help=(
            "Run one-time OAuth flow using GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET from .env. "
            "Prints the refresh token to console. Does NOT write any files."
        ),
    )
    args = parser.parse_args()

    if args.get_token:
        run_get_token_flow()
        return

    watcher = GmailWatcher(vault_path=args.vault, interval=args.interval)

    if DRY_RUN:
        watcher.logger.info("Running in DRY RUN mode — no files will be written.")

    watcher.run()


if __name__ == "__main__":
    main()
