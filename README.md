# AI Employee Digital FTE — Bronze Tier

## Project Overview

The Bronze Tier is a lightweight AI workflow orchestrator that automates inbound file task triage inside an Obsidian-like vault (`AI_Employee_Vault`).
It supports:
- Inbox file ingestion (`/Inbox`)
- Action item generation (`/Needs_Action`)
- Approval handling (`/Pending_Approval`, `/Approved`)
- Completion tracking (`/Done`)
- Dashboard updates (`Dashboard.md`)
- Logging (`/Logs/*.jsonl`)

### Goals
- Simulate “AI employee” task processing
- Enable human-in-the-loop approval
- Keep simple, filesystem-driven state
- Provide template skills for higher tiers (Silver/Gold)

## Repo Layout

- `.claude/skills/`:
  - `process-inbox.md`
  - `triage-task.md`
  - `update-dashboard.md`
- `AI_Employee_Vault/`:
  - `Business_Goals.md`, `Company_Handbook.md`, `Dashboard.md`
  - operation folders: `Inbox`, `Needs_Action`, `Pending_Approval`, `Approved`, `Done`, `Plans`, `Rejected`, `Logs`
- `watchers/`:
  - `base_watcher.py`
  - `filesystem_watcher.py`
  - `orchestrator.py`
- `requirements.txt`
- `.env.example`

## Core Components

### `watchers/base_watcher.py`
Abstract base class:
- Vault path validation
- `check_for_updates()`
- `create_action_file(item)`
- logging to `Logs/YYYY-MM-DD.jsonl`
- runtime loop for polling watchers

### `watchers/filesystem_watcher.py`
File-based watcher:
- Watches `AI_Employee_Vault/Inbox`
- Filters hidden files + `.gitkeep`
- Copies incoming file into `/Needs_Action`
- Creates companion `.md` action file with metadata and suggested actions
- Detects priority from filename (`urgent`, `invoice`, etc.)
- Logs with `BaseWatcher.log_action`

### `watchers/orchestrator.py`
Coordinator:
- Monitors `/Needs_Action` and `/Approved` via watchdog
- Debounces and triggers autopilot
- `trigger_claude(...)` with user prompt
- `DRY_RUN` default true
- updates `Dashboard.md`
- writes event logs

## Vault Workflow

1. Drop a file into `/AI_Employee_Vault/Inbox`
2. `filesystem_watcher` copies it and generates `/Needs_Action/FILE_<name>_<ts>.md`
3. `orchestrator` detects `.md` in `/Needs_Action` and triggers Claude or Dry Run
4. Human moves files to `/Approved` / `/Done` / `/Rejected`
5. `orchestrator` logs events and updates dashboard

## Skills-defined behavior

- `process-inbox.md`: scans `Needs_Action`, auto/approval decision, moves files, updates dashboard
- `triage-task.md`: deep task classification per file, creates plan or approval file
- `update-dashboard.md`: refreshes counts and activity in `Dashboard.md`

## Install

```bash
cd "AI-Employee-Digital-FTE/Bronze Tier"
python -m pip install -r requirements.txt
```

Optional:
- Create `.env` from `.env.example`

## Usage

### Start Filesystem Watcher

```bash
python watchers/filesystem_watcher.py --vault path/to/AI_Employee_Vault
```

### Start Orchestrator

```bash
python watchers/orchestrator.py --vault path/to/AI_Employee_Vault --dry-run
```

Disable dry-run:

```bash
python watchers/orchestrator.py --vault path/to/AI_Employee_Vault
```

## Dashboard behavior

- `update_dashboard(vault)` updates inventory counts in `Dashboard.md`:
  - `/Inbox`, `/Needs_Action`, `/Pending_Approval`, `/Done`
  - sets `last_updated`

## Folder semantics

- `Inbox`: raw incoming files
- `Needs_Action`: pending action task files
- `Pending_Approval`: human approval requests
- `Approved`: approved tasks
- `Done`: completed tasks
- `Rejected`: rejected tasks
- `Plans`: multi-step plans
- `Logs`: day-based JSONL events

## Troubleshooting

- `Vault not found`: verify `--vault` path
- `claude command not found`: use `--dry-run` or add Claude CLI to PATH
- no actions: confirm `watchdog` and folder files

## Quick start example

1. `python watchers/filesystem_watcher.py --vault AI_Employee_Vault`
2. `python watchers/orchestrator.py --vault AI_Employee_Vault --dry-run`
3. Drop `invoice_urgent.pdf` into `AI_Employee_Vault/Inbox`
4. Verify `/Needs_Action/FILE_invoice_urgent_<ts>.md`
5. Approve by moving to `/Approved`
6. Check dashboard and logs update

