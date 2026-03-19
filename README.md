# AI Employee Digital FTE — Platinum Tier

> Your life and business on autopilot. Always-On Cloud + Local Executive. Agent-driven, human-in-the-loop.

---

## Overview

A **Platinum Tier** Digital FTE (Full-Time Equivalent) that runs 24/7 with Cloud + Local architecture:

### Local Machine (Your Desktop)
- **Dashboard** — Web-based control panel (Next.js + FastAPI)
- **WhatsApp Automation** — Baileys v7 with full session control
- **Human Approval** — Review and approve all Cloud drafts
- **Payment MCP** — Execute payments locally (secure)
- **Local Orchestrator** — Executes approved actions

### Cloud VM (Oracle/AWS Free Tier)
- **Gmail Watcher** — Polls Gmail, creates drafts (never sends)
- **Social Watchers** — LinkedIn, Twitter/X, Facebook, Instagram (drafts only)
- **Odoo Community** — Accounting ERP (read-only snapshots)
- **Cloud Agent** — Qwen/Claude for draft generation
- **Always-On** — 24/7 monitoring and draft creation

### Key Features
- **Work-Zone Separation** — Cloud drafts, Local executes
- **Git Vault Sync** — Secure sync between Cloud and Local
- **Security First** — Secrets never sync (.env, auth_info, cookies)
- **Human-in-the-loop** — Nothing executes without Local approval

---

## Quick Start (One Command)

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.13+ | [python.org](https://python.org) |
| Node.js | v24+ LTS | [nodejs.org](https://nodejs.org) |
| Obsidian | v1.10.6+ | [obsidian.md](https://obsidian.md) |
| **AI Agent** (pick one) | | |
| ↳ Claude Code | Latest | `npm i -g @anthropic/claude-code` |
| ↳ Gemini CLI | Latest | `npm i -g @google/gemini-cli` |
| ↳ Qwen Code | Latest | `npm i -g @qwen-code/qwen-code@latest` |

### 1. Clone and configure

```bash
git clone https://github.com/Sheikh-Muhammad-Mujtaba/AI-Employee-Digital-FTE.git
cd AI-Employee-Digital-FTE
cp .env.example .env
# Edit .env — fill in your API keys, credentials, etc.
```

### 2. Install all dependencies

```bash
# Backend (FastAPI)
cd backend
pip install -r requirements.txt
cd ..

# Frontend (Next.js Dashboard)
cd frontend
npm install
cd ..

# WhatsApp Baileys
cd whatsapp-baileys
npm install
cd ..

# Email MCP
cd email-mcp
npm install
cd ..

# ERPNext MCP
cd ERP_Next-MCP
uv sync
cd ..

# Playwright browsers (for social media posting)
python -m playwright install chromium
```

### 3. Start everything

```bash
start.bat
```

This launches **9 services** in separate terminal windows:

| # | Service | Port | Description |
|---|---------|------|-------------|
| 1 | Dashboard API | `:8000` | FastAPI backend (auto-creates SQLite DB) |
| 2 | Dashboard UI | `:3000` | Next.js frontend |
| 3 | WhatsApp Baileys | `:3001` | WhatsApp watcher + HTTP API |
| 4 | Orchestrator | — | Watches `Needs_Action/` and `Approved/` |
| 5 | Gmail Watcher | — | Polls Gmail API every 2 min |
| 6 | LinkedIn Watcher | — | Monitors LinkedIn queue |
| 7 | Twitter Watcher | — | Monitors Twitter/X queue |
| 8 | Facebook Watcher | — | Monitors Facebook + Instagram |
| 9 | ERPNext Watcher | — | Polls ERPNext API every 15 min |

### 4. First-time dashboard login

1. Open **http://localhost:3000**
2. Click **"First time? Create admin user"**
3. Login: `admin` / `admin123`
4. Navigate to **WhatsApp** tab → scan QR code to link your WhatsApp

---

## Repository Structure

```
AI-Employee-Digital-FTE/
├── backend/                  # FastAPI dashboard API
│   ├── main.py               # App entry point
│   ├── config.py              # Environment config
│   ├── database.py            # SQLAlchemy 2.0 + SQLite
│   ├── models.py              # User model
│   ├── auth.py                # JWT authentication
│   ├── schemas.py             # Pydantic request/response models
│   ├── vault_parser.py        # Markdown parser for vault files
│   ├── requirements.txt
│   └── routers/
│       ├── auth_router.py     # Login + seed admin
│       ├── vault_router.py    # Dashboard status endpoint
│       ├── tasks_router.py    # Task approve/reject/list
│       ├── projects_router.py # Business goals + plans
│       └── whatsapp_router.py # Proxy to Baileys HTTP API
├── frontend/                  # Next.js 15 dashboard UI
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx     # Root layout
│   │   │   ├── page.tsx       # Root redirect
│   │   │   ├── login/         # Login page
│   │   │   ├── dashboard/     # Dashboard overview
│   │   │   ├── tasks/         # Task review (approve/reject)
│   │   │   ├── projects/      # Projects & plans
│   │   │   └── whatsapp/      # WhatsApp status + send
│   │   ├── components/
│   │   │   └── Sidebar.tsx    # Navigation sidebar
│   │   └── lib/
│   │       └── api.ts         # Typed API client with JWT
│   ├── package.json
│   └── tsconfig.json
├── whatsapp-baileys/          # WhatsApp watcher (Baileys v7)
│   ├── index.js               # Main service
│   ├── package.json
│   └── auth_info/             # (auto-created) WhatsApp credentials
├── AI_Employee_Vault/         # Obsidian vault (data layer)
│   ├── Dashboard.md           # Real-time status summary
│   ├── Business_Goals.md      # Q1 objectives & metrics
│   ├── Company_Handbook.md    # AI rules of engagement
│   ├── Inbox/                 # Raw input files drop here
│   ├── Needs_Action/          # Triggers for Claude processing
│   ├── Pending_Approval/      # Drafts awaiting human review
│   ├── Approved/              # Human-approved → execute
│   ├── Rejected/              # Denied or expired
│   ├── Done/                  # Completed archive
│   ├── Plans/                 # Multi-step project plans
│   ├── Briefings/             # Weekly CEO reports
│   ├── Social_Queue/          # Platform-specific post queues
│   ├── Accounting/            # ERPNext snapshots
│   ├── Audit_Reports/         # Weekly business audits
│   └── Logs/                  # JSONL activity logs
├── watchers/                  # Python automation scripts
│   ├── orchestrator.py        # Core — watches folders, triggers Claude
│   ├── base_watcher.py        # Abstract base class
│   ├── filesystem_watcher.py  # Local file drop monitor
│   ├── gmail_watcher.py       # Gmail API polling
│   ├── linkedin_watcher.py    # LinkedIn queue monitor
│   ├── linkedin_poster.py     # Playwright LinkedIn poster
│   ├── twitter_watcher.py     # Twitter/X monitor
│   ├── twitter_poster.py      # Playwright Twitter poster
│   ├── facebook_watcher.py    # Facebook monitor
│   ├── meta_poster.py         # Playwright FB/IG poster
│   ├── erpnext_watcher.py     # ERPNext API polling
│   ├── scheduler.py           # Cron-like daily/weekly triggers
│   └── log_summary.py         # Log aggregation
├── email-mcp/                 # Email MCP server (Node.js)
├── ERP_Next-MCP/              # ERPNext MCP server (Python)
├── .claude/skills/            # Agent skill templates
├── .env.example               # Environment template
├── mcp.json                   # Claude Code MCP config
├── start.bat                  # ⚡ One-command startup
├── ARCHITECTURE.md            # System architecture diagram
└── README.md                  # This file
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│              DASHBOARD (Next.js :3000 + FastAPI :8000)                  │
│  Login → Overview → Tasks → Projects → WhatsApp                       │
└───────────────────┬─────────────────────────────────────────────────────┘
                    │ reads/writes
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI_Employee_Vault/ (Obsidian)                        │
│  /Inbox → /Needs_Action → /Pending_Approval → /Approved → /Done       │
└───────────┬─────────────────────────────┬───────────────────────────────┘
            │ watchdog events              │ file moves
            ▼                              ▼
┌───────────────────────┐    ┌────────────────────────────────────────────┐
│  WATCHERS (Python)    │    │  ORCHESTRATOR (orchestrator.py)            │
│  Gmail, LinkedIn,     │    │  Watchdog on /Needs_Action → Claude Code  │
│  Twitter, Facebook,   │    │  Watchdog on /Approved → Action Executors │
│  ERPNext, Scheduler   │    └────────────────────────────────────────────┘
└───────────────────────┘
┌───────────────────────┐    ┌────────────────────────────────────────────┐
│  WhatsApp Baileys     │    │  ACTION EXECUTORS                         │
│  (:3001) — keyword    │    │  send_email → email-mcp                   │
│  filtering, QR pair,  │    │  post_linkedin → linkedin_poster.py       │
│  send/receive msgs    │    │  post_twitter → twitter_poster.py         │
└───────────────────────┘    │  post_facebook/ig → meta_poster.py        │
                             └────────────────────────────────────────────┘
```

---

## Platinum Tier Deployment

For production deployment with Cloud VM + Local sync:

```bash
# 1. Setup Cloud VM (Oracle/AWS Free Tier)
ssh ubuntu@your-cloud-vm
./platinum/cloud_setup.sh

# 2. Configure Local sync
cd AI_Employee_Vault
git remote add cloud ubuntu@your-cloud-vm:/opt/ai-employee/vault-sync
bash ../platinum/local_sync.sh

# 3. Test Platinum flow
python ../platinum/test_platinum_tier.py
```

See [`platinum/README.md`](platinum/README.md) for full deployment guide.

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `DRY_RUN` | ✅ | `true` = log-only mode (default), `false` = live |
| `AGENT` | ✅ | AI agent CLI: `claude`, `gemini`, or `qwen` (default: `claude`) |
| `GMAIL_CLIENT_ID` | For Gmail | Google OAuth client ID |
| `GMAIL_CLIENT_SECRET` | For Gmail | Google OAuth client secret |
| `GMAIL_REFRESH_TOKEN` | For Gmail | Run `gmail_watcher.py --get-token` |
| `LINKEDIN_EMAIL` | For LinkedIn | Playwright login email |
| `LINKEDIN_PASSWORD` | For LinkedIn | Playwright login password |
| `TWITTER_EMAIL` | For Twitter | X.com login email |
| `TWITTER_PASSWORD` | For Twitter | X.com login password |
| `FACEBOOK_EMAIL` | For Facebook | Meta login email |
| `FACEBOOK_PASSWORD` | For Facebook | Meta login password |
| `ERPNEXT_URL` | For ERPNext | ERPNext instance URL |
| `DASHBOARD_SECRET_KEY` | Dashboard | JWT signing key (change in prod!) |
| `DASHBOARD_FRONTEND_ORIGIN` | Dashboard | Default: `http://localhost:3000` |
| `WA_KEYWORDS` | WhatsApp | Comma-separated trigger keywords |
| `WA_HTTP_PORT` | WhatsApp | Baileys HTTP API port (default: 3001) |

---

## Workflow Example

1. An email arrives → **Gmail Watcher** creates `Needs_Action/EMAIL_abc123.md`
2. **Orchestrator** detects the file → triggers **Claude Code** to process it
3. Claude drafts a reply → writes to `Pending_Approval/REPLY_John.md`
4. You open the **Dashboard** → go to **Tasks** → click **✓ Approve**
5. File moves to `Approved/` → Orchestrator sends the email via `email-mcp`
6. File archived to `Done/` → Dashboard updates

Same flow for WhatsApp messages, social media posts, and ERPNext actions.

---

## MCP Servers

Configured in `mcp.json` for Claude Code:

| Server | Purpose | Transport |
|--------|---------|-----------|
| `email` | Send/draft Gmail | node stdio |
| `erpnext` | ERPNext CRUD | python stdio |
| `browser` | Ad-hoc web automation | npx stdio |
| `windows-mcp` | Windows desktop UI automation | uvx stdio |

Start Claude with: `claude --mcp-config mcp.json`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Vault not found` | Verify `--vault` path or check `start.bat` paths |
| `claude` not found | Install Claude CLI: `npm i -g @anthropic/claude-code` |
| Gmail auth failed | Re-run `python watchers/gmail_watcher.py --get-token` |
| Dashboard login fails | Hit `POST /api/auth/seed` first to create admin user |
| WhatsApp QR expired | Restart the Baileys service — QR auto-regenerates |
| Playwright auth fail | Run poster with `--test-login`, check `.env` creds |
| `pydantic-core` build fail | You need `pydantic>=2.11.0` for Python 3.14 support |

---

## Security

- **DRY_RUN=true** is the default — flip to `false` only when ready
- **HITL** — Every external action goes through `/Pending_Approval/` first
- **48h expiry** — Stale approvals auto-move to `/Rejected/`
- **Credentials** — All secrets in `.env`, never in the vault. `.env` is gitignored
- **Audit logs** — Every action logged to `Logs/YYYY-MM-DD.jsonl`

---

## Notes

- Keep `Company_Handbook.md` updated for AI behavioral rules
- Dashboard reads directly from the Obsidian vault — changes are live
- WhatsApp Baileys stores credentials in `whatsapp-baileys/auth_info/` (gitignored)
- The Ralph Wiggum loop (`.claude/hooks/`) caps at 5 iterations per task

---

_Built for Hackathon 0 — Personal AI Employee · Gold Tier_
