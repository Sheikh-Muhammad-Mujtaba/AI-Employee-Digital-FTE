"""base_watcher.py - Abstract base class for all AI Employee watchers."""
import time
import logging
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime

# Configure logging to stdout + rotating file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)


class BaseWatcher(ABC):
    """
    Base class for all Watcher scripts. Subclass this and implement:
      - check_for_updates() -> list of new items
      - create_action_file(item) -> Path of the created .md file
    """

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path).resolve()
        self.needs_action = self.vault_path / "Needs_Action"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)
        self._validate_vault()

    def _validate_vault(self):
        """Ensure the vault and required folders exist."""
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault not found at: {self.vault_path}")
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return a list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create a .md action file in /Needs_Action and return its path."""
        pass

    def log_action(self, action_type: str, details: dict):
        """Append a JSON log entry to today's log file."""
        import json
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.jsonl"
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "watcher": self.__class__.__name__,
            "action_type": action_type,
            **details,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def run(self):
        """Main loop: poll for updates every check_interval seconds."""
        self.logger.info(f"Starting {self.__class__.__name__} — vault: {self.vault_path}")
        self.logger.info(f"Polling every {self.check_interval}s. Press Ctrl+C to stop.")
        while True:
            try:
                items = self.check_for_updates()
                if items:
                    self.logger.info(f"Found {len(items)} new item(s) to process.")
                for item in items:
                    path = self.create_action_file(item)
                    self.logger.info(f"Created action file: {path.name}")
                    self.log_action("action_file_created", {"file": str(path)})
            except KeyboardInterrupt:
                self.logger.info("Watcher stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(self.check_interval)
