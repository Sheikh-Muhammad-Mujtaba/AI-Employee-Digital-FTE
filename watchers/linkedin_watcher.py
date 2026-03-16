"""
linkedin_watcher.py - LinkedIn Content Scheduler (Silver Tier).

This watcher manages a LinkedIn post queue stored in the vault. It:
  1. Reads AI_Employee_Vault/Plans/LinkedIn_Queue.md for scheduled posts
  2. When a post's scheduled time arrives, creates a /Needs_Action file
  3. Claude processes it → drafts/refines the post → creates a /Pending_Approval file
  4. Human approves → Orchestrator calls LinkedIn API to publish

LinkedIn API Setup:
  1. Go to linkedin.com/developers → Create App (select your company page)
  2. Request "Share on LinkedIn" + "w_member_social" OAuth scopes
  3. Complete LinkedIn app review (required for posting)
  4. Generate access token and set LINKEDIN_ACCESS_TOKEN in .env
  5. Set LINKEDIN_PERSON_URN to your member URN (urn:li:person:XXXXX)

Usage:
    python linkedin_watcher.py --vault /path/to/AI_Employee_Vault

Requirements:
    pip install requests python-dotenv
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN   = os.getenv("LINKEDIN_PERSON_URN", "")
MAX_POSTS_PER_DAY     = int(os.getenv("MAX_POSTS_PER_DAY", "3"))

# ── Queue file format ─────────────────────────────────────────────────────────
#
# AI_Employee_Vault/Plans/LinkedIn_Queue.md should contain entries like:
#
# ## Post: Project Launch Announcement
# - scheduled: 2026-02-24T08:00:00
# - topic: We just shipped a major feature for Project Alpha...
# - tone: professional
# - status: pending
#
# ## Post: Weekly Insights
# - scheduled: 2026-02-26T09:00:00
# - topic: Three things I learned about AI automation this week...
# - tone: thought-leadership
# - status: pending


QUEUE_FILE_NAME = "LinkedIn_Queue.md"
QUEUE_FOLDER    = "Plans"


def _parse_queue(vault: Path) -> list[dict]:
    """Parse LinkedIn_Queue.md and return a list of post entries."""
    queue_file = vault / QUEUE_FOLDER / QUEUE_FILE_NAME
    if not queue_file.exists():
        return []

    text = queue_file.read_text(encoding="utf-8")
    entries = []

    # Split on ## Post: headers
    blocks = re.split(r"^## Post: (.+)$", text, flags=re.MULTILINE)

    # blocks = [preamble, title1, body1, title2, body2, ...]
    for i in range(1, len(blocks), 2):
        title = blocks[i].strip()
        body  = blocks[i + 1] if i + 1 < len(blocks) else ""

        def extract(field: str) -> str:
            m = re.search(rf"- {field}:\s*(.+)", body)
            return m.group(1).strip() if m else ""

        entries.append({
            "title":     title,
            "scheduled": extract("scheduled"),
            "topic":     extract("topic"),
            "tone":      extract("tone") or "professional",
            "status":    extract("status") or "pending",
        })

    return entries


def _mark_post_triggered(vault: Path, title: str):
    """Update the post status to 'triggered' in LinkedIn_Queue.md."""
    queue_file = vault / QUEUE_FOLDER / QUEUE_FILE_NAME
    if not queue_file.exists():
        return
    text = queue_file.read_text(encoding="utf-8")
    # Replace status only within the block matching this title
    pattern = rf"(## Post: {re.escape(title)}.*?- status: )pending"
    updated = re.sub(pattern, r"\1triggered", text, count=1, flags=re.DOTALL)
    queue_file.write_text(updated, encoding="utf-8")


# ── LinkedIn API ──────────────────────────────────────────────────────────────

def post_to_linkedin(content: str) -> dict:
    """
    Publish a text post to LinkedIn via the UGC Posts API.
    Returns the API response dict or raises on failure.
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests not installed. Run: pip install requests")

    if not LINKEDIN_ACCESS_TOKEN:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN not set in .env")
    if not LINKEDIN_PERSON_URN:
        raise RuntimeError("LINKEDIN_PERSON_URN not set in .env")

    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── LinkedInWatcher ───────────────────────────────────────────────────────────

class LinkedInWatcher(BaseWatcher):
    """
    Polls LinkedIn_Queue.md for posts due to be published.
    When a post is due, creates a Needs_Action file for Claude to draft/refine.
    """

    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=300)  # check every 5 min
        self._posts_today: int = 0
        self._posts_today_date: str = ""

    def _reset_daily_counter(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._posts_today_date:
            self._posts_today = 0
            self._posts_today_date = today

    def check_for_updates(self) -> list:
        """Return posts from the queue whose scheduled time has passed."""
        self._reset_daily_counter()
        if self._posts_today >= MAX_POSTS_PER_DAY:
            self.logger.warning(f"Daily LinkedIn post limit reached ({MAX_POSTS_PER_DAY}). Skipping.")
            return []

        entries = _parse_queue(self.vault_path)
        now = datetime.now()
        due = []
        for entry in entries:
            if entry["status"] != "pending":
                continue
            if not entry["scheduled"]:
                continue
            try:
                sched = datetime.fromisoformat(entry["scheduled"])
            except ValueError:
                self.logger.warning(f"Invalid scheduled time for post '{entry['title']}': {entry['scheduled']}")
                continue
            if sched <= now:
                due.append(entry)

        self.logger.info(f"LinkedIn queue: {len(entries)} total, {len(due)} due.")
        return due

    def create_action_file(self, post: dict) -> Path:
        """Create a Needs_Action file for a due LinkedIn post."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r"[^a-zA-Z0-9_]", "_", post["title"])[:40]
        md_path = self.needs_action / f"LINKEDIN_{safe_title}_{ts}.md"

        content = f"""---
type: linkedin_post
title: {post['title']}
scheduled: {post['scheduled']}
topic: {post['topic']}
tone: {post['tone']}
status: pending
created: {datetime.utcnow().isoformat()}Z
---

## LinkedIn Post Due for Publishing

A scheduled LinkedIn post is ready to be drafted and published.

**Title:** {post['title']}
**Scheduled:** {post['scheduled']}
**Topic:** {post['topic']}
**Tone:** {post['tone']}

---

## Instructions for Claude

1. Read `Business_Goals.md` for context about the business.
2. Read recent files in `/Done/` for recent accomplishments to reference.
3. Use the `/post-linkedin` skill to generate a compelling post on this topic.
4. Save the draft to `/Pending_Approval/LINKEDIN_{safe_title}_{ts}.md`.
5. Do NOT publish directly — human approval is required.
6. Update Dashboard.md when done.

---

## Suggested Actions

- [ ] Draft post content (use /post-linkedin)
- [ ] Move to /Pending_Approval for review
- [ ] After approval, Orchestrator will publish via LinkedIn API
"""
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create: {md_path.name}")
        else:
            md_path.write_text(content, encoding="utf-8")
            _mark_post_triggered(self.vault_path, post["title"])

        self._posts_today += 1
        return md_path


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — LinkedIn Watcher (Silver)")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    args = parser.parse_args()

    import logging
    log = logging.getLogger("LinkedInWatcher")

    # Safely bypass LinkedIn if credentials are not configured
    if not LINKEDIN_ACCESS_TOKEN or LINKEDIN_ACCESS_TOKEN.startswith("PASTE_"):
        log.warning(
            "LinkedIn integration disabled — LINKEDIN_ACCESS_TOKEN not set in .env. "
            "Queue monitoring and post scheduling will be skipped. "
            "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in .env to enable."
        )
        log.info("LinkedIn Watcher exiting (no credentials). Safe to ignore this message.")
        return

    if DRY_RUN:
        log.info("[DRY RUN] LinkedIn Watcher — no real posts will be made.")

    watcher = LinkedInWatcher(vault_path=args.vault)
    watcher.run()


if __name__ == "__main__":
    main()
