"""
log_summary.py - Activity Log Reader (Gold Tier).

Reads JSONL logs from the last N days and prints a structured summary.
Used by the weekly-briefing and accounting-audit skills.

Usage:
    python log_summary.py --vault /path/to/AI_Employee_Vault
    python log_summary.py --vault /path/to/AI_Employee_Vault --days 7
    python log_summary.py --vault /path/to/AI_Employee_Vault --json
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def read_logs(vault: Path, days: int = 7) -> list:
    """Read all JSONL log entries from the last N days."""
    logs_dir = vault / "Logs"
    entries = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        log_file = logs_dir / f"{date}.jsonl"
        if not log_file.exists():
            continue
        for line in log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def summarise(entries: list) -> dict:
    """Group entries by action_type and count them."""
    counts = defaultdict(int)
    errors = []

    for e in entries:
        action = e.get("action_type") or e.get("event") or "unknown"
        counts[action] += 1
        if "error" in e or action.endswith("_failed") or action.endswith("_error"):
            errors.append(e)

    # Build clean summary
    summary = {
        "period_days":       len(set(e.get("timestamp", "")[:10] for e in entries)),
        "total_events":      len(entries),
        "emails_sent":       counts.get("email_sent", 0),
        "emails_failed":     counts.get("email_failed", 0),
        "linkedin_posted":   counts.get("linkedin_posted", 0),
        "twitter_posted":    counts.get("twitter_posted", 0),
        "facebook_posted":   counts.get("facebook_posted", 0),
        "instagram_posted":  counts.get("instagram_posted", 0),
        "erpnext_polls":     counts.get("erpnext_poll", 0),
        "erpnext_errors":    counts.get("erpnext_poll_error", 0),
        "briefings":         counts.get("weekly_briefing_generated", 0),
        "approvals_expired": counts.get("approval_expired", 0),
        "action_failures":   len(errors),
        "all_counts":        dict(counts),
        "recent_errors":     errors[-5:],   # last 5 errors only
    }
    return summary


def format_summary(s: dict) -> str:
    lines = [
        f"Activity Summary (last {s['period_days']} day(s) — {s['total_events']} total events)",
        "─" * 55,
        f"  Emails sent:        {s['emails_sent']}  (failed: {s['emails_failed']})",
        f"  LinkedIn posts:     {s['linkedin_posted']}",
        f"  Twitter posts:      {s['twitter_posted']}",
        f"  Facebook posts:     {s['facebook_posted']}",
        f"  Instagram posts:    {s['instagram_posted']}",
        f"  ERPNext polls:      {s['erpnext_polls']}  (errors: {s['erpnext_errors']})",
        f"  Briefings:          {s['briefings']}",
        f"  Expired approvals:  {s['approvals_expired']}",
        f"  Action failures:    {s['action_failures']}",
    ]
    if s["recent_errors"]:
        lines.append("\nRecent Errors:")
        for e in s["recent_errors"]:
            ts = e.get("timestamp", "")[:19]
            err = e.get("error") or e.get("action_type") or "unknown"
            lines.append(f"  [{ts}] {err}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AI Employee — Log Summary")
    parser.add_argument("--vault", default=str(Path(__file__).parent.parent / "AI_Employee_Vault"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    entries = read_logs(vault, args.days)
    summary = summarise(entries)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_summary(summary))


if __name__ == "__main__":
    main()
