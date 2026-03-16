# AI Employee — Gold Tier Architecture

> Local-first, agent-driven, human-in-the-loop.
> Built with Claude Code + Obsidian + Python + Playwright.

---

## What It Does

A Digital FTE (Full-Time Equivalent) that runs 24/7 and autonomously:
- Reads and triages Gmail
- Posts to LinkedIn, Twitter/X, Facebook, and Instagram
- Monitors ERPNext for open invoices and accounting events
- Generates a Monday Morning CEO Briefing
- Asks for human approval before any real-world action

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        WATCHERS (Python)                        │
│                                                                 │
│  gmail_watcher.py     → polls Gmail API every 2 min            │
│  filesystem_watcher.py→ monitors /Inbox for new files          │
│  linkedin_watcher.py  → reads Plans/LinkedIn_Queue.md          │
│  twitter_watcher.py   → reads Social_Queue/Twitter_Queue.md    │
│  facebook_watcher.py  → reads Social_Queue/Facebook+IG Queue   │
│  erpnext_watcher.py   → polls ERPNext REST API every 15 min    │
│  scheduler.py         → cron-like triggers (daily/weekly)      │
└───────────────────┬─────────────────────────────────────────────┘
                    │ writes .md trigger files
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI_Employee_Vault/                           │
│                                                                 │
│  /Inbox            raw inputs (files, emails)                  │
│  /Needs_Action     trigger files → Claude processes these      │
│  /Pending_Approval drafts waiting for human review             │
│  /Approved         human-approved → Orchestrator executes      │
│  /Rejected         denied or expired (>48h)                    │
│  /Done             completed items archive                     │
│  /Plans            multi-step plans (in_progress tracking)     │
│  /Briefings        weekly CEO reports                          │
│  /Social_Queue     Twitter / Facebook / Instagram queues       │
│  /Accounting       ERPNext snapshots                           │
│  /Audit_Reports    weekly business audit outputs               │
│  /Logs             JSONL activity logs (one file per day)      │
└───────────────────┬─────────────────────────────────────────────┘
                    │ /Needs_Action detected
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (orchestrator.py)                 │
│                                                                 │
│  Watchdog on /Needs_Action → triggers Claude Code              │
│  Watchdog on /Approved     → executes action                   │
│  Hourly: expires stale approvals → moves to /Rejected          │
└──────┬──────────────────────────────────────────┬──────────────┘
       │ claude --print                            │ execute
       ▼                                           ▼
┌─────────────────┐                  ┌─────────────────────────────┐
│  CLAUDE CODE    │                  │  ACTION EXECUTORS           │
│                 │                  │                             │
│  Reads task     │                  │  send_email                 │
│  Runs /skill    │                  │    → node email-mcp/        │
│  Writes draft   │                  │  post_linkedin              │
│  → /Pending_    │                  │    → linkedin_poster.py     │
│    Approval/    │                  │  post_twitter               │
│                 │                  │    → twitter_poster.py      │
│  Stop hook:     │                  │  post_facebook              │
│  Ralph Wiggum   │                  │    → meta_poster.py --fb    │
│  loop until     │                  │  post_instagram             │
│  TASK_COMPLETE  │                  │    → meta_poster.py --ig    │
└─────────────────┘                  └─────────────────────────────┘
```

---

## MCP Servers (`mcp.json`)

| Server | Purpose | Transport |
|--------|---------|-----------|
| `email` | Send/draft Gmail via Google API | node stdio |
| `erpnext` | Full CRUD on ERPNext doctypes | python stdio |
| `browser` | Ad-hoc web automation | npx stdio |

Start with: `claude --mcp-config mcp.json`

---

## Agent Skills (`.claude/skills/`)

| Skill | Trigger | Output |
|-------|---------|--------|
| `process-inbox` | Any file in /Needs_Action | Triage + draft reply |
| `update-dashboard` | After any action | Dashboard.md refresh |
| `triage-task` | Unknown task type | Categorise + route |
| `create-plan` | Complex multi-step task | Plan file in /Plans |
| `send-email` | EMAIL_* in /Needs_Action | Draft in /Pending_Approval |
| `post-linkedin` | LINKEDIN_* in /Needs_Action | Draft in /Pending_Approval |
| `post-twitter` | TWITTER_* in /Needs_Action | Draft in /Pending_Approval |
| `post-facebook` | FACEBOOK_* in /Needs_Action | Draft in /Pending_Approval |
| `post-instagram` | INSTAGRAM_* in /Needs_Action | Draft in /Pending_Approval |
| `accounting-audit` | ERPNEXT_* in /Needs_Action | Accounting/latest_snapshot.md |
| `weekly-briefing` | SCHEDULED_weekly_* trigger | Briefings/YYYY-MM-DD_CEO.md |

---

## Human-in-the-Loop (HITL) Flow

```
Watcher detects event
       ↓
Claude drafts action → /Pending_Approval/
       ↓
Human reviews (move file to /Approved/ or /Rejected/)
       ↓
Orchestrator executes (email sent / tweet posted / etc.)
       ↓
File archived to /Done/
```

**Nothing executes without human approval.** The only exception is the CEO Briefing (read-only, no external actions).

---

## Playwright Posters

All social media posting uses browser automation — no API keys required:

| Script | Platform | Profile dir |
|--------|----------|-------------|
| `linkedin_poster.py` | LinkedIn | `Logs/.linkedin_profile/` (wait, uses chrome_profile) |
| `twitter_poster.py` | Twitter/X | `Logs/.twitter_profile/` |
| `meta_poster.py --platform facebook` | Facebook | `Logs/.meta_profile/` |
| `meta_poster.py --platform instagram` | Instagram | `Logs/.meta_profile/` |

Each uses a **persistent Chrome profile** — log in once, stays logged in.

---

## Ralph Wiggum Loop (`.claude/hooks/`)

```
Claude tries to stop
       ↓
stop_hook.py checks transcript for "TASK_COMPLETE"
       ↓
Found?  → exit 0  (Claude stops cleanly)
Not found + iterations < 5? → exit 2 (Claude keeps going)
Not found + iterations ≥ 5? → exit 0  (safety cap, force stop)
```

---

## Starting the System

```bash
# 1. Copy and fill env vars
cp .env.example .env

# 2. Install Python dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 3. Install ERPNext MCP
cd ERP_Next-MCP && uv sync

# 4. Start all watchers
start.bat

# 5. Start Claude with MCP servers
claude --mcp-config mcp.json
```

---

## File Naming Conventions

| Prefix | Source | Example |
|--------|--------|---------|
| `EMAIL_` | Gmail watcher | `EMAIL_abc123_20260315.md` |
| `LINKEDIN_` | LinkedIn watcher | `LINKEDIN_Post_Title_20260315.md` |
| `TWITTER_` | Twitter watcher | `TWITTER_Post_Title_20260315.md` |
| `FACEBOOK_` | Facebook watcher | `FACEBOOK_Post_Title_20260315.md` |
| `INSTAGRAM_` | Facebook watcher | `INSTAGRAM_Post_Title_20260315.md` |
| `ERPNEXT_` | ERPNext watcher | `ERPNEXT_audit_20260315.md` |
| `SCHEDULED_` | Scheduler | `SCHEDULED_weekly_briefing_20260315.md` |
| `REPLY_` | Claude (email draft) | `REPLY_John_Doe_20260315.md` |
| `FLAG_` | Claude (escalation) | `FLAG_Urgent_matter_20260315.md` |

---

## Lessons Learned

1. **Playwright over APIs for social media.** Twitter, Facebook, Instagram APIs are either paid, restricted, or require lengthy app review. Playwright with persistent Chrome profiles works reliably and needs only a username + password.

2. **`data-testid` and `aria-label` selectors are stable.** Class names change with every UI deploy. Attribute selectors tied to accessibility or test IDs survive much longer.

3. **ERPNext over Odoo.** Same open-source ERP category, better REST API, purpose-built MCP server available, runs locally via Docker.

4. **DRY_RUN=true as the default.** Every watcher, poster, and orchestrator respects this flag. Develop safely, flip to false only when ready to go live.

5. **HITL is non-negotiable.** Every external action (email, post, payment) goes through `/Pending_Approval/` first. The 48-hour expiry on approvals prevents stale actions from executing days later.

6. **One persistent Chrome profile per platform.** Sharing a profile between LinkedIn and Twitter causes session conflicts. Each platform gets its own profile directory.

7. **The Ralph Wiggum loop needs a hard cap.** Without `MAX_ITERATIONS = 5`, a broken task prompt will loop forever and consume API credits. Always set a ceiling.
