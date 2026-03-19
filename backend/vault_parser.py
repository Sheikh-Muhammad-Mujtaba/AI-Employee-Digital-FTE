"""Vault parser – reads Obsidian markdown files and returns structured data."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import VAULT_PATH
from schemas import (
    AccountingMetric,
    ActivityEvent,
    BusinessGoals,
    ComponentStatus,
    DashboardResponse,
    InboxSummary,
    SocialQueueItem,
    TaskFile,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body) from YAML-ish frontmatter."""
    fm: dict[str, str] = {}
    body = text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip()
        body = text[match.end():]
    return fm, body


def _parse_md_table(text: str, header_pattern: str) -> list[dict[str, str]]:
    """Parse a markdown table that starts after a line matching *header_pattern*.
    Returns list of dicts keyed by header names."""
    rows: list[dict[str, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.search(header_pattern, lines[i], re.IGNORECASE):
            # next line is header row
            i += 1
            if i >= len(lines):
                break
            headers = [h.strip() for h in lines[i].split("|") if h.strip()]
            i += 1  # skip separator
            if i < len(lines) and re.match(r"^\s*\|[-| ]+\|\s*$", lines[i]):
                i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].split("|") if c.strip()]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                i += 1
            break
        i += 1
    return rows


# ── Dashboard Parser ──────────────────────────────────────────────────────────

def parse_dashboard() -> DashboardResponse:
    """Parse AI_Employee_Vault/Dashboard.md into structured data."""
    path = VAULT_PATH / "Dashboard.md"
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    fm, body = _parse_frontmatter(raw)

    # System Status table
    sys_rows = _parse_md_table(body, r"## System Status")
    system_status = [
        ComponentStatus(name=r.get("Component", ""), status=r.get("Status", ""), last_check=r.get("Last Check", ""))
        for r in sys_rows
    ]

    # Social Queue Status
    sq_rows = _parse_md_table(body, r"## Social Queue Status")
    social_queue = [
        SocialQueueItem(
            platform=r.get("Platform", ""),
            queued=int(r.get("Queued", "0")),
            posted=int(r.get("Posted", "0")),
            last_post=r.get("Last Post", "—"),
        )
        for r in sq_rows
    ]

    # Accounting
    acc_rows = _parse_md_table(body, r"## Accounting")
    accounting = [
        AccountingMetric(metric=r.get("Metric", ""), value=r.get("Value", ""), last_sync=r.get("Last Sync", ""))
        for r in acc_rows
    ]

    # Inbox Summary (bullet style)
    inbox = InboxSummary()
    for line in body.splitlines():
        if "Pending items in /Inbox" in line:
            m = re.search(r"(\d+)", line)
            if m:
                inbox.pending_inbox = int(m.group(1))
        elif "Items in /Needs_Action" in line:
            m = re.search(r"(\d+)", line)
            if m:
                inbox.needs_action = int(m.group(1))
        elif "Items in /Pending_Approval" in line:
            m = re.search(r"(\d+)", line)
            if m:
                inbox.pending_approval = int(m.group(1))
        elif "Active Plans" in line:
            m = re.search(r"(\d+)", line)
            if m:
                inbox.active_plans = int(m.group(1))
        elif "Completed today" in line:
            m = re.search(r"(\d+)", line)
            if m:
                inbox.completed_today = int(m.group(1))

    # Recent Activity table
    act_rows = _parse_md_table(body, r"## Recent Activity")
    recent_activity = [
        ActivityEvent(time=r.get("Time", ""), event=r.get("Event", ""), details=r.get("Details", ""))
        for r in act_rows
    ]

    # Upcoming Actions (bullet list)
    upcoming: list[str] = []
    capture = False
    for line in body.splitlines():
        if re.match(r"## Upcoming Actions", line):
            capture = True
            continue
        if capture:
            if line.startswith("##") or line.startswith("---"):
                break
            stripped = line.strip().lstrip("- ").strip()
            if stripped:
                upcoming.append(stripped)

    # Quick Stats table
    qs_rows = _parse_md_table(body, r"## Quick Stats")
    quick_stats = {r.get("Metric", ""): r.get("Value", "") for r in qs_rows}

    # Alerts (blockquote lines with ⚠️)
    alerts: list[str] = []
    for line in body.splitlines():
        if line.strip().startswith(">") and "⚠️" in line:
            alerts.append(line.strip().lstrip("> ").strip())

    return DashboardResponse(
        last_updated=fm.get("last_updated", "unknown"),
        version=fm.get("version", "unknown"),
        tier=fm.get("tier", "unknown"),
        system_status=system_status,
        social_queue=social_queue,
        accounting=accounting,
        inbox_summary=inbox,
        recent_activity=recent_activity,
        upcoming_actions=upcoming,
        quick_stats=quick_stats,
        alerts=alerts,
    )


# ── Task File Helpers ─────────────────────────────────────────────────────────

def list_folder_tasks(folder_name: str) -> list[TaskFile]:
    """List markdown files in a vault sub-folder."""
    folder = VAULT_PATH / folder_name
    if not folder.exists():
        return []
    tasks: list[TaskFile] = []
    for f in sorted(folder.iterdir(), reverse=True): # Newest first makes more sense for logs & tasks
        if f.suffix in (".md", ".txt", ".jsonl"):
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            fm, body = _parse_frontmatter(raw)
            stat = f.stat()
            tasks.append(TaskFile(
                filename=f.name,
                folder=folder_name,
                frontmatter=fm,
                body=body.strip(),
                raw=raw,
                created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            ))
    return tasks


def move_task_file(filename: str, src_folder: str, dest_folder: str) -> Path:
    """Move a file between vault sub-folders. Returns new path."""
    src = VAULT_PATH / src_folder / filename
    dest_dir = VAULT_PATH / dest_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    src.rename(dest)
    return dest


# ── Business Goals Parser ────────────────────────────────────────────────────

def parse_business_goals() -> BusinessGoals:
    path = VAULT_PATH / "Business_Goals.md"
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    fm, body = _parse_frontmatter(raw)

    revenue_target = ""
    revenue_mtd = ""
    for line in body.splitlines():
        if "Monthly goal" in line:
            m = re.search(r"\$[\d,]+", line)
            if m:
                revenue_target = m.group(0)
        if "Current MTD" in line:
            m = re.search(r"\$[\d,]+", line)
            if m:
                revenue_mtd = m.group(0)

    metrics = _parse_md_table(body, r"### Key Metrics")
    projects: list[str] = []
    capture = False
    for line in body.splitlines():
        if "### Active Projects" in line:
            capture = True
            continue
        if capture:
            if line.startswith("###") or line.startswith("---"):
                break
            stripped = line.strip()
            if stripped and stripped != "":
                projects.append(stripped.lstrip("0123456789. "))

    audit_rules: list[str] = []
    capture_audit = False
    for line in body.splitlines():
        if "### Subscription Audit" in line:
            capture_audit = True
            continue
        if capture_audit:
            if line.startswith("###") or line.startswith("---"):
                break
            stripped = line.strip().lstrip("- ").strip()
            if stripped and "Flag for review" not in stripped:
                audit_rules.append(stripped)

    return BusinessGoals(
        last_updated=fm.get("last_updated", "unknown"),
        review_frequency=fm.get("review_frequency", "unknown"),
        revenue_target_monthly=revenue_target or "$0",
        revenue_current_mtd=revenue_mtd or "$0",
        key_metrics=metrics,
        active_projects=projects,
        subscription_audit_rules=audit_rules,
    )


def create_plan_file(title: str, description: str, steps: list[str], due_date: str | None) -> Path:
    """Write a new plan markdown file into AI_Employee_Vault/Plans/."""
    plans_dir = VAULT_PATH / "Plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^\w\s-]", "", title).replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"PLAN_{safe_title}_{ts}.md"
    steps_md = "\n".join(f"- [ ] {s}" for s in steps)
    content = f"""---
type: plan
title: {title}
created: {datetime.now().isoformat()}
due_date: {due_date or 'TBD'}
status: in_progress
---

# {title}

## Description
{description}

## Steps
{steps_md}

## Notes
_Created via Dashboard UI._
"""
    path = plans_dir / filename
    path.write_text(content, encoding="utf-8")
    return path
