"""
facebook_watcher.py - Facebook + Instagram Queue Watcher (Gold Tier).

Watches both:
  - AI_Employee_Vault/Social_Queue/Facebook_Queue.md
  - AI_Employee_Vault/Social_Queue/Instagram_Queue.md

When a post's scheduled_for time arrives, creates a /Needs_Action trigger.

Usage:
    python facebook_watcher.py --vault /path/to/AI_Employee_Vault

Requirements:
    pip install python-dotenv
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

DRY_RUN           = os.getenv("DRY_RUN", "true").lower() == "true"
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "3"))

QUEUE_FILES = {
    "facebook":  Path("Social_Queue") / "Facebook_Queue.md",
    "instagram": Path("Social_Queue") / "Instagram_Queue.md",
}


def _parse_queue(vault: Path, platform: str) -> list:
    queue_file = vault / QUEUE_FILES[platform]
    if not queue_file.exists():
        return []

    text = queue_file.read_text(encoding="utf-8")
    entries = []
    blocks = re.split(r"^### (.+)$", text, flags=re.MULTILINE)

    for i in range(1, len(blocks), 2):
        title = blocks[i].strip()
        body  = blocks[i + 1] if i + 1 < len(blocks) else ""

        def extract(field):
            m = re.search(rf"- {field}:\s*(.+)", body)
            return m.group(1).strip() if m else ""

        # Multi-line content block
        content_match = re.search(r"- content:\s*\|\s*\n((?:    .+\n?)+)", body)
        content = content_match.group(1).strip() if content_match else extract("content")

        entries.append({
            "title":         title,
            "platform":      platform,
            "status":        extract("status"),
            "scheduled_for": extract("scheduled_for"),
            "content":       content,
            "hashtags":      extract("hashtags"),
            "image_url":     extract("image_url"),
        })

    return entries


def _mark_triggered(vault: Path, platform: str, title: str):
    queue_file = vault / QUEUE_FILES[platform]
    if not queue_file.exists():
        return
    text = queue_file.read_text(encoding="utf-8")
    pattern = rf"(### {re.escape(title)}.*?- status: )scheduled"
    updated = re.sub(pattern, r"\1triggered", text, count=1, flags=re.DOTALL)
    queue_file.write_text(updated, encoding="utf-8")


class FacebookWatcher(BaseWatcher):
    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=300)
        self._posts_today = 0
        self._posts_today_date = ""

    def _reset_daily_counter(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._posts_today_date:
            self._posts_today = 0
            self._posts_today_date = today

    def check_for_updates(self) -> list:
        self._reset_daily_counter()
        if self._posts_today >= MAX_POSTS_PER_DAY:
            self.logger.warning(f"Daily post limit reached ({MAX_POSTS_PER_DAY}). Skipping.")
            return []

        now = datetime.now()
        due = []

        for platform in ("facebook", "instagram"):
            entries = _parse_queue(self.vault_path, platform)
            for entry in entries:
                if entry["status"] != "scheduled":
                    continue
                if not entry["scheduled_for"]:
                    continue
                try:
                    sched = datetime.strptime(entry["scheduled_for"], "%Y-%m-%d %H:%M")
                except ValueError:
                    self.logger.warning(f"Bad scheduled_for for '{entry['title']}': {entry['scheduled_for']}")
                    continue
                if sched <= now:
                    due.append(entry)

        self.logger.info(f"Meta queue: {len(due)} post(s) due.")
        return due

    def create_action_file(self, post: dict) -> Path:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        platform = post["platform"].upper()
        safe_title = re.sub(r"[^a-zA-Z0-9_]", "_", post["title"])[:40]
        md_path = self.needs_action / f"{platform}_{safe_title}_{ts}.md"

        full_content = post["content"]
        if post["hashtags"]:
            full_content = f"{full_content}\n{post['hashtags']}"

        image_line = f"**Image URL:** {post['image_url']}" if post["image_url"] else "_No image (Facebook text post)_"

        content = f"""---
type: {post['platform']}_post
title: {post['title']}
platform: {post['platform']}
scheduled_for: {post['scheduled_for']}
status: pending
created: {datetime.utcnow().isoformat()}Z
---

## {platform} Post Due for Publishing

**Title:** {post['title']}
**Scheduled:** {post['scheduled_for']}
{image_line}

**Draft Content:**
{full_content}

---

## Instructions for Claude

1. Review the draft content above.
2. Refine using the `/post-{post['platform']}` skill if needed.
3. Save approved draft to `/Pending_Approval/{platform}_{safe_title}_{ts}.md`.
4. Do NOT post directly — human approval required.
5. Update Dashboard.md when done.

---

## Checklist

- [ ] Review / refine content
- [ ] Confirm image_url is accessible (Instagram only)
- [ ] Move to /Pending_Approval
"""

        if DRY_RUN:
            self.logger.info(f"[DRY_RUN] Would create: {md_path.name}")
        else:
            md_path.write_text(content, encoding="utf-8")
            _mark_triggered(self.vault_path, post["platform"], post["title"])

        self._posts_today += 1
        self.log_action(f"{post['platform']}_post_triggered", {
            "title": post["title"],
            "platform": post["platform"],
            "file": md_path.name,
            "dry_run": DRY_RUN,
        })
        return md_path


def main():
    parser = argparse.ArgumentParser(description="AI Employee — Facebook/Instagram Watcher (Gold)")
    parser.add_argument("--vault", default=str(Path(__file__).parent.parent / "AI_Employee_Vault"))
    args = parser.parse_args()

    if DRY_RUN:
        print("[DRY_RUN] Facebook/Instagram Watcher — no real posts will be made.")

    watcher = FacebookWatcher(vault_path=args.vault)
    watcher.run()


if __name__ == "__main__":
    main()
