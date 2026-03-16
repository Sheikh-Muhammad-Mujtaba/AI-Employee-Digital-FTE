"""
erpnext_watcher.py - ERPNext Accounting Watcher (Gold Tier).

Polls ERPNext every ERPNEXT_INTERVAL seconds (default 15 min) and writes a
trigger to /Needs_Action when there are open invoices or new GL entries.
Claude then runs the accounting-audit skill to generate a snapshot.

Usage:
    python erpnext_watcher.py --vault /path/to/AI_Employee_Vault
    python erpnext_watcher.py --vault /path/to/AI_Employee_Vault --once

Requirements:
    pip install httpx python-dotenv
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

DRY_RUN            = os.getenv("DRY_RUN", "true").lower() == "true"
ERPNEXT_URL        = os.getenv("ERPNEXT_URL", "")
ERPNEXT_USERNAME   = os.getenv("ERPNEXT_USERNAME", "")
ERPNEXT_PASSWORD   = os.getenv("ERPNEXT_PASSWORD", "")
ERPNEXT_API_KEY    = os.getenv("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")
POLL_INTERVAL      = int(os.getenv("ERPNEXT_INTERVAL", "900"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ERPNextWatcher] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ERPNextWatcher")


# ── ERPNext API ────────────────────────────────────────────────────────────────

def get_auth_headers() -> dict:
    if ERPNEXT_API_KEY and ERPNEXT_API_SECRET:
        return {"Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}"}
    return {}


def check_open_invoices() -> dict:
    """Returns count and total of unpaid Sales Invoices via ERPNext REST API."""
    try:
        import httpx
        headers = get_auth_headers()
        url = f"{ERPNEXT_URL}/api/resource/Sales Invoice"
        params = {
            "filters": json.dumps([["status", "in", ["Unpaid", "Overdue"]]]),
            "fields": json.dumps(["name", "grand_total", "outstanding_amount", "due_date"]),
            "limit": 50,
        }
        cookies = {}
        if ERPNEXT_USERNAME and ERPNEXT_PASSWORD and not headers:
            login_resp = httpx.post(
                f"{ERPNEXT_URL}/api/method/login",
                json={"usr": ERPNEXT_USERNAME, "pwd": ERPNEXT_PASSWORD},
                timeout=15,
            )
            login_resp.raise_for_status()
            cookies = login_resp.cookies

        resp = httpx.get(url, headers=headers, params=params, cookies=cookies, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        total_outstanding = sum(float(d.get("outstanding_amount", 0)) for d in data)
        return {"count": len(data), "total_outstanding": total_outstanding, "invoices": data}
    except Exception as e:
        return {"error": str(e)}


# ── Watcher ────────────────────────────────────────────────────────────────────

class ERPNextWatcher:
    def __init__(self, vault_path: Path):
        self.vault_path      = vault_path.resolve()
        self.needs_action    = self.vault_path / "Needs_Action"
        self.logs_dir        = self.vault_path / "Logs"
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _write_log(self, entry: dict):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": datetime.utcnow().isoformat() + "Z",
                                "watcher": "ERPNextWatcher", **entry}) + "\n")

    def run_once(self):
        if not ERPNEXT_URL:
            logger.warning("ERPNEXT_URL not set — skipping poll")
            return

        logger.info("Polling ERPNext for open invoices...")
        result = check_open_invoices()

        if "error" in result:
            logger.error(f"ERPNext poll failed: {result['error']}")
            self._write_log({"event": "erpnext_poll_error", "error": result["error"]})
            return

        count = result["count"]
        total = result["total_outstanding"]
        logger.info(f"ERPNext: {count} open invoices, total outstanding: {total:.2f}")

        if count == 0:
            return

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        trigger_file = self.needs_action / f"ERPNEXT_audit_{ts}.md"
        content = f"""---
type: erpnext_audit
created: {datetime.now(timezone.utc).isoformat()}
open_invoices: {count}
total_outstanding: {total:.2f}
dry_run: {DRY_RUN}
---

# ERPNext Accounting Trigger

**Open Invoices:** {count}
**Total Outstanding:** {total:.2f}

## Action Required
Run the `accounting-audit` skill to pull a full snapshot from ERPNext and
update `AI_Employee_Vault/Accounting/latest_snapshot.md`.

## Raw Data
```json
{json.dumps(result.get("invoices", [])[:10], indent=2)}
```
"""
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would write trigger: {trigger_file.name}")
        else:
            trigger_file.write_text(content, encoding="utf-8")
            logger.info(f"Trigger written: {trigger_file.name}")

        self._write_log({
            "event": "erpnext_poll",
            "open_invoices": count,
            "total_outstanding": total,
            "trigger": trigger_file.name if not DRY_RUN else None,
            "dry_run": DRY_RUN,
        })

    def run(self):
        logger.info(f"ERPNext watcher started. Polling every {POLL_INTERVAL}s. DRY_RUN={DRY_RUN}")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("ERPNext watcher stopped.")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ERPNext Accounting Watcher")
    parser.add_argument("--vault", default=str(Path(__file__).parent.parent / "AI_Employee_Vault"))
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    watcher = ERPNextWatcher(Path(args.vault))
    if args.once:
        watcher.run_once()
    else:
        watcher.run()


if __name__ == "__main__":
    main()
