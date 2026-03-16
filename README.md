# AI Employee Digital FTE — Gold Tier

## Overview

This is the Gold Tier documentation for the AI Employee Digital FTE project (AI-Employee-Digital-FTE).

Gold Tier adds full social posting automation + CRM/ERP integration on top of Silver behavior. It supports:
- Inbox file ingestion (`/Inbox`)
- Task generation (`/Needs_Action`)
- AI processing via Claude (`orchestrator.py`)
- Approval pipeline (`/Pending_Approval`, `/Approved`)
- Complete action executor flow via API and headless browser
- LinkedIn, Twitter/X, Facebook, Instagram publishing
- Gmail ingestion
- ERPNext watcher integration
- Dashboard and structured logs

## Repository structure

- `.claude/skills/` – skill templates for AI-generated tasks and automations
- `AI_Employee_Vault/` – vault state and website content
  - core docs: `Company_Handbook.md`, `Dashboard.md`, `Business_Goals.md`
  - workflow folders: `Inbox`, `Needs_Action`, `Pending_Approval`, `Approved`, `Done`, `Plans`, `Rejected`, `Logs`, `Briefings`
- `watchers/` – automation scripts:
  - `base_watcher.py`
  - `filesystem_watcher.py`
  - `orchestrator.py` (Gold orchestration)
  - `gmail_watcher.py`
  - `linkedin_watcher.py`
  - `linkedin_poster.py`
  - `twitter_watcher.py`
  - `twitter_poster.py`
  - `facebook_watcher.py` / `meta_poster.py`
  - `erpnext_watcher.py`
  - `scheduler.py`
  - `log_summary.py`
- `email-mcp/` – email microservice for `send_email` actions
- `requirements.txt`, `.env.example`, `mcp.json`, `start.bat`

## Gold Tier behavior (from Gold orchestrator)

### Orchestrator core

- Watches `Needs_Action` and `Approved` using `watchdog`.
- Debounces file creation events.
- `trigger_claude()` runs a comprehensive prompt expecting `TASK_COMPLETE`.
- `update_dashboard()` changes `AI_Employee_Vault/Dashboard.md`, refreshing an inbox summary and `last_updated`.
- `expire_stale_approvals()`: moves old `/Pending_Approval` files to `/Rejected` after 48 hours.

### Task types handled by Claude prompt

- `email`
- `briefing`
- `linkedin_post`
- `twitter_post`
- `facebook_post`
- `instagram_post`
- `erpnext_audit`
- generic type tasks

### Approved action executor

Supported action types:
- `send_email` → runs `email-mcp` (via `node` command)
- `post_linkedin` → runs `watchers/linkedin_poster.py`
- `post_twitter` → runs `watchers/twitter_poster.py`
- `post_facebook` → runs `watchers/meta_poster.py --platform facebook`
- `post_instagram` → run `watchers/meta_poster.py --platform instagram`

Behavior:
- When an `Approved` file is created, it is executed, logged, and moved to `/Done`.
- Supports Dry-Run mode via `DRY_RUN=true`.

### Social posting subsystems

- `linkedin_poster.py`: Playwright automation to login + post on LinkedIn. Supports cookies persistence.
- `twitter_poster.py`: Playwright automation to login + post a tweet.
- `meta_poster.py`: Posts to Facebook/Instagram via Playwright.

### Inbox ingestion

- `filesystem_watcher.py`: local `Inbox` folder watchers for dropped files.
- `gmail_watcher.py`: Gmail API polling for important/unread emails, writes `EMAIL_*` tasks.
- `linkedin_watcher.py`: watches LinkedIn interactions and queue.
- `twitter_watcher.py`: polls/monitors for Twitter triggers.
- `facebook_watcher.py`: polls Facebook interactions.
- `erpnext_watcher.py`: polls ERPNext API for accounting/CRM updates.

## Setup

1. Install Python dependencies:

```bash
cd "AI-Employee-Digital-FTE"
python -m pip install -r requirements.txt
```

2. Install browser tooling for Playwright:

```bash
python -m pip install playwright
python -m playwright install chromium
```

3. Copy `.env.example` to `.env` and set keys:
- `DRY_RUN=true|false`
- `EMAIL_MCP_PATH` (path to `email-mcp/index.js`)
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
- `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, `LINKEDIN_HEADLESS` (true/false)
- `MAX_EMAILS_PER_HOUR` (e.g., 10)
- social API tokens as needed

4. (Optional) Install copy of Claude CLI:

```bash
npm install -g @anthropic/claude-code
```

## Run commands

- Start orchestrator:

```bash
python watchers/orchestrator.py --vault ./AI_Employee_Vault --dry-run
```

- Start filesystem ingest:

```bash
python watchers/filesystem_watcher.py --vault ./AI_Employee_Vault
```

- Start Gmail watch:

```bash
python watchers/gmail_watcher.py --vault ./AI_Employee_Vault --interval 120
```

- Start social watchers: `linkedin`, `twitter`, `facebook` as needed.

## Workflow example

1. Drop `invoice_urgent.pdf` in `AI_Employee_Vault/Inbox`.
2. Filesystem watcher creates `Needs_Action/FILE_invoice_urgent_...md`.
3. Orchestrator triggers Claude to create an action (e.g., `send_email` to `Pending_Approval`).
4. Human moves generated approval file to `/Approved`.
5. Orchestrator executes, sends email or posts social media.
6. Orchestrator moves approved file to `/Done`, updates dashboard and logs.

## Logs

- `AI_Employee_Vault/Logs/YYYY-MM-DD.jsonl` for actions and events.
- `AI_Employee_Vault/Logs/.linkedin_cookies.json` for LinkedIn session persistence.

## Troubleshooting

- `Vault not found`: verify `--vault` path.
- `claude` not found: ensure Claude CLI installed or use `--dry-run`.
- `Gmail auth failed`: re-run `python watchers/gmail_watcher.py --get-token`.
- `Playwright` auth flow fail: run `watchers/linkedin_poster.py --test-login`, update `.env`.
- `page content extraction issue`: inspect Watcher console logs and `AI_Employee_Vault/Logs`

## Notes

- This Gold Tier README assumes full Silver feature parity plus social and ERP watchers in this repository.
- Keep `Company_Handbook.md` up-to-date for AI rules of engagement.
- Use `DRY_RUN` initially while validating workflow.
