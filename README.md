# AI Employee Digital FTE — Silver Tier

## Overview

This document explains the Silver Tier implementation in `AI-Employee-Digital-FTE`.
It is built on top of the Bronze Tier core and permanently includes advanced automation:
- automated file ingestion and task generation
- Claude-driven task processing
- Gmail + LinkedIn watchers
- human approval loop
- email & social action executors
- dashboard and structured JSONL logs

## Directory layout

- `.claude/skills/` – workflow and prompt guidance skills
- `AI_Employee_Vault/` – working vault containing data and folder states
  - subfolders: `Inbox`, `Needs_Action`, `Pending_Approval`, `Approved`, `Done`, `Plans`, `Rejected`, `Logs`, `Briefings`
- `watchers/` – automation scripts:
  - `base_watcher.py`
  - `filesystem_watcher.py`
  - `orchestrator.py`
  - `gmail_watcher.py`
  - `linkedin_watcher.py`
  - `linkedin_poster.py`
  - `scheduler.py`
- `email-mcp/` – node-based email microservice
- `requirements.txt`, `.env.example`, `mcp.json`, `start.bat`

## Core components

### 1. base_watcher.py
- base class for watchers
- vault and folder validation
- logging and action file creation interface
- polling loop handled here

### 2. filesystem_watcher.py
- watches `AI_Employee_Vault/Inbox` with `watchdog`
- creates `Needs_Action` tasks for dropped files
- writes metadata `.md` and copies source file
- auto-detects priority from file name

### 3. orchestrator.py
- watches `Needs_Action` and `Approved`
- debounces events to avoid duplicate triggers
- triggers Claude prompt processing (`trigger_claude`)
- updates dashboard counts and logs
- executes approved actions if human moved tasks to `Approved`
- stale approval expiry (48h to `Rejected`)

### 4. gmail_watcher.py
- polls Gmail via API using OAuth env vars
- extracts important unread emails to `Needs_Action` as `type: email`
- one-time token flow: `--get-token`
- runs interval polling (default 120 sec)

### 5. linkedin_watcher.py
- watch LinkedIn source (feed/queue) for approvals and posting requests

### 6. linkedin_poster.py
- uses Playwright to post approved content to LinkedIn
- supports --test-login and --post
- saves session cookies to `AI_Employee_Vault/Logs/.linkedin_cookies.json`

## Silver-grade workflow

1. **Input**: file dropped into `AI_Employee_Vault/Inbox` or email arrives via Gmail watcher.
2. **Task creation**: `filesystem_watcher`/`gmail_watcher` creates a `.md` action file in `Needs_Action`.
3. **Processing**: `orchestrator` picks up `Needs_Action`, triggers Claude with the Silver prompt template.
4. **Triage**: AI generates proposed action files in `Pending_Approval` (`send_email`, `post_linkedin`, etc.) or moves tasks to `Done` after internal completion.
5. **Approval**: human reviews pending files and moves to `Approved`.
6. **Execution**: `orchestrator` detects `Approved`, executes action with email or LinkedIn mcp logic, then moves to `Done`.
7. **Dashboard**: `orchestrator` updates `Dashboard.md` with counts and last_updated.
8. **Logging**: JSONL entries are stored in `AI_Employee_Vault/Logs/YYYY-MM-DD.jsonl`.

## Environment variables

Copy `.env.example` and set values:

- `DRY_RUN` (true/false)
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
- `EMAIL_MCP_PATH` (path to `email-mcp/index.js` or runner)
- `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, `LINKEDIN_HEADLESS=true/false`
- `MAX_EMAILS_PER_HOUR` (e.g., 10)

## Installation

```bash
python -m pip install -r requirements.txt
python -m pip install playwright
python -m playwright install chromium
```

Clone `.env`:

```bash
copy .env.example .env    # Windows
```

## Start commands

1. Orchestrator:

```bash
python watchers/orchestrator.py --vault ./AI_Employee_Vault --dry-run
```

2. Filesystem watcher:

```bash
python watchers/filesystem_watcher.py --vault ./AI_Employee_Vault
```

3. Gmail watcher:

```bash
python watchers/gmail_watcher.py --vault ./AI_Employee_Vault --interval 120
```

4. LinkedIn watcher:

```bash
python watchers/linkedin_watcher.py --vault ./AI_Employee_Vault
```

5. LinkedIn poster test:

```bash
python watchers/linkedin_poster.py --test-login
```

## Recommended usage

- Maintain `Company_Handbook.md` with system rules and priorities.
- Update `Dashboard.md` manually only if needed (orchestration does it automatically).
- Use `.claude/skills/` templates for AI behavior and prompt retrieval.

## Troubleshooting

- `Vault not found`: validate `--vault` path.
- `claude not found`: install Anthropic Claude CLI or set correct binary path.
- `Gmail auth failed`: re-run `python watchers/gmail_watcher.py --get-token`, copy refresh token.
- LinkedIn posting issue: check login flow with `--test-login`, update `.env`.

## Notes

- Operate in `DRY_RUN=true` until local behavior is validated.
- Ensure URLs and API credentials are kept securely.
- `Pending_Approval` works as a hand-off gate to avoid accidental external actions.
