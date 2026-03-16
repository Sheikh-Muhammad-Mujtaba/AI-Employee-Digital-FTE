"""
filesystem_watcher.py - Monitors the /Inbox folder for new files.

When a file is dropped into AI_Employee_Vault/Inbox/, this watcher:
  1. Copies it to /Needs_Action/
  2. Creates a companion .md action file describing the task
  3. Logs the event

Usage:
    python filesystem_watcher.py --vault /path/to/AI_Employee_Vault

Requirements:
    pip install watchdog
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher, logging


class InboxEventHandler(FileSystemEventHandler):
    """Handles file creation events inside /Inbox."""

    def __init__(self, watcher: "FilesystemWatcher"):
        super().__init__()
        self.watcher = watcher

    def on_created(self, event):
        if event.is_directory:
            return
        source = Path(event.src_path)
        # Skip hidden files and .gitkeep
        if source.name.startswith(".") or source.name == ".gitkeep":
            return
        self.watcher.logger.info(f"New file detected in Inbox: {source.name}")
        self.watcher.process_file(source)


class FilesystemWatcher(BaseWatcher):
    """
    Watches the /Inbox folder using watchdog (event-driven, no polling).
    Converts dropped files into structured .md action items in /Needs_Action.
    """

    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=0)  # event-driven, no interval needed
        self.inbox = self.vault_path / "Inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self._processed: set[str] = set()

    # ── BaseWatcher interface ────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Not used — event-driven via watchdog."""
        return []

    def create_action_file(self, source: Path) -> Path:
        """
        Copy the source file to /Needs_Action and create a companion .md file.
        Returns the path of the .md action file.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = source.stem.replace(" ", "_")
        dest_name = f"FILE_{safe_name}_{timestamp}{source.suffix}"
        dest = self.needs_action / dest_name
        md_path = self.needs_action / f"FILE_{safe_name}_{timestamp}.md"

        # Copy the original file
        shutil.copy2(source, dest)

        # Detect a rough priority based on filename keywords
        priority = self._detect_priority(source.name)

        content = f"""---
type: file_drop
source_name: {source.name}
copied_to: {dest.name}
received: {datetime.utcnow().isoformat()}Z
size_bytes: {source.stat().st_size}
priority: {priority}
status: pending
---

## New File Dropped for Processing

**Original filename:** `{source.name}`
**Stored as:** `{dest.name}`
**Size:** {source.stat().st_size:,} bytes
**Received:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC

## Suggested Actions

- [ ] Review the file contents
- [ ] Determine the required action
- [ ] Create a Plan if multi-step work is needed
- [ ] Move this file to /Done when complete

## Notes

_(Add any context or notes here after review.)_
"""
        md_path.write_text(content, encoding="utf-8")
        return md_path

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _detect_priority(self, filename: str) -> str:
        name_lower = filename.lower()
        urgent_keywords = ["urgent", "asap", "critical", "emergency"]
        high_keywords = ["invoice", "payment", "contract", "legal", "client"]
        if any(kw in name_lower for kw in urgent_keywords):
            return "urgent"
        if any(kw in name_lower for kw in high_keywords):
            return "high"
        return "normal"

    def process_file(self, source: Path):
        """Called by the event handler when a new file appears in Inbox."""
        key = str(source)
        if key in self._processed:
            return
        self._processed.add(key)
        try:
            md_path = self.create_action_file(source)
            self.log_action(
                "inbox_file_received",
                {
                    "source": source.name,
                    "action_file": md_path.name,
                    "priority": self._detect_priority(source.name),
                },
            )
            self.logger.info(f"Action file created: {md_path.name}")
        except Exception as e:
            self.logger.error(f"Failed to process {source.name}: {e}", exc_info=True)

    # ── Run loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Start the watchdog observer on /Inbox."""
        self.logger.info(f"FilesystemWatcher watching: {self.inbox}")
        self.logger.info("Drop files into /Inbox to create action items. Ctrl+C to stop.")

        # Process any files already sitting in Inbox at startup
        existing = [f for f in self.inbox.iterdir() if f.is_file() and not f.name.startswith(".")]
        if existing:
            self.logger.info(f"Processing {len(existing)} existing file(s) in Inbox...")
            for f in existing:
                self.process_file(f)

        handler = InboxEventHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.inbox), recursive=False)
        observer.start()

        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Stopping watcher...")
            observer.stop()
        observer.join()
        self.logger.info("FilesystemWatcher stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Filesystem Watcher")
    parser.add_argument(
        "--vault",
        type=str,
        default=str(Path(__file__).parent.parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault (default: ../AI_Employee_Vault)",
    )
    args = parser.parse_args()

    watcher = FilesystemWatcher(vault_path=args.vault)
    watcher.run()


if __name__ == "__main__":
    main()
