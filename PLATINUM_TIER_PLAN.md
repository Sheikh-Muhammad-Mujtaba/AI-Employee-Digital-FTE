# Platinum Tier Implementation Plan

> **Tagline**: Always-On Cloud + Local Executive — Production-ready AI Employee

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLOUD VM (Oracle/AWS Free Tier)                   │
│  Ubuntu 22.04 LTS | Docker | Odoo Community | Always-On Watchers           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  Gmail Watcher  │  │ LinkedIn Watcher│  │  ERPNext Watcher│            │
│  │  (Draft Only)   │  │  (Draft Only)   │  │  (Read Only)    │            │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              Synced Vault (/Vault/Cloud/)                       │       │
│  │  - /Inbox/          (raw inputs)                                │       │
│  │  - /Needs_Action/   (triggers for Cloud Agent)                  │       │
│  │  - /Plans/          (social media queues)                       │       │
│  │  - /Drafts/         (email drafts, social drafts) ← CLOUD WRITES│       │
│  │  - /Updates/        (signals to Local)                          │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │   Odoo ERP      │  │   Git Server    │  │  Cloud Agent    │            │
│  │   (Accounting)  │  │   (Vault Sync)  │  │  (Qwen/Claude)  │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Git Push/Pull (vault state only)
                                    │ NO SECRETS SYNCED
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE (Your Desktop)                             │
│  Windows 10/11 | WhatsApp Session | Payment MCP | Human Approval           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │ WhatsApp Watcher│  │  Payment MCP    │  │  Browser MCP    │            │
│  │  (Local Only)   │  │  (Local Only)   │  │  (Local Only)   │            │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              Local Vault (/Vault/Local/)                        │       │
│  │  - /Pending_Approval/ (from Cloud drafts)                       │       │
│  │  - /Approved/       (human decisions)                           │       │
│  │  - /Done/           (completed tasks)                           │       │
│  │  - /In_Progress/    (claim-by-move tracking)                    │       │
│  │  - /Dashboard.md    (single writer: Local only)                 │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  Local Agent    │  │  Orchestrator   │  │  Dashboard UI   │            │
│  │  (Qwen/Claude)  │  │  (Execution)    │  │  (Next.js)      │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Work-Zone Specialization

| Domain | Cloud Owns | Local Owns |
|--------|-----------|------------|
| **Email** | Poll Gmail, draft replies | Review + send via MCP |
| **Social** | Monitor queues, draft posts | Approve + publish |
| **WhatsApp** | ❌ Never | Full session + replies |
| **Payments** | ❌ Never | Full approval + execution |
| **Accounting** | Read-only snapshots | Invoice creation + payments |
| **Dashboard** | Write to /Updates/ | Merge to Dashboard.md |

## Security Rules

1. **Secrets Never Sync**: `.env`, `auth_info/`, `*.cookies.json` are in `.gitignore`
2. **Single-Writer Rule**: Only Local writes to `Dashboard.md`
3. **Claim-by-Move**: First agent to move file from `/Needs_Action/` to `/In_Progress/<agent>/` owns it
4. **Approval Expiry**: Files in `/Pending_Approval/` > 48 hours → `/Rejected/`

## Implementation Phases

### Phase 1: Vault Sync via Git

**Cloud Setup:**
```bash
# On Cloud VM
git init --bare /opt/vault-sync.git
```

**Local Setup:**
```bash
# On Local machine
cd AI_Employee_Vault
git remote add cloud user@cloud-vm:/opt/vault-sync.git
git push -u cloud main
```

**Folders to Sync:**
- `/Inbox/`
- `/Needs_Action/`
- `/Plans/`
- `/Drafts/`
- `/Updates/`
- `/Done/` (for audit trail)

**Folders NEVER to Sync:**
- `.env`
- `auth_info/`
- `Logs/.twitter_cookies.json`
- `Logs/.gmail_processed_ids.txt`
- `Logs/.meta_profile/`
- `Logs/chrome_profile/`

### Phase 2: Cloud VM Deployment

**VM Requirements:**
- 2 vCPU, 4GB RAM minimum
- 20GB SSD storage
- Ubuntu 22.04 LTS
- Public IP with HTTPS (Let's Encrypt)

**Services to Deploy:**
1. Docker + Docker Compose
2. Odoo Community (via Docker)
3. PostgreSQL (for Odoo)
4. Nginx (reverse proxy)
5. Cloud Watchers (systemd services)

**Oracle Cloud Free Tier (Recommended):**
- Always Free ARM Ampere A1 Compute
- 4 OCPUs, 24GB RAM
- 200GB block volume
- Free public IP

### Phase 3: Work-Zone Implementation

**Cloud Watchers:**
- `gmail_watcher.py` → writes drafts to `/Drafts/Email/`
- `linkedin_watcher.py` → writes drafts to `/Drafts/LinkedIn/`
- `twitter_watcher.py` → writes drafts to `/Drafts/Twitter/`
- `facebook_watcher.py` → writes drafts to `/Drafts/Facebook/`
- `instagram_watcher.py` → writes drafts to `/Drafts/Instagram/`
- `erpnext_watcher.py` → writes snapshots to `/Accounting/`

**Local Watchers:**
- `whatsapp_baileys/` → writes to `/Needs_Action/WhatsApp/`
- `orchestrator.py` → executes approved actions
- `payment_mcp/` → handles payment approvals

### Phase 4: A2A Communication (Optional Upgrade)

Replace some file handoffs with direct agent-to-agent messages:

```python
# Cloud Agent writes to A2A queue
a2a_message = {
    "from": "cloud_agent",
    "to": "local_agent",
    "type": "draft_ready",
    "payload": {
        "draft_type": "email_reply",
        "file": "/Drafts/Email/REPLY_abc123.md",
        "priority": "high",
        "summary": "Client asking for invoice - draft reply ready"
    }
}

# Local Agent polls /Updates/ or receives via WebSocket
```

## Platinum Demo Flow (Minimum Passing Gate)

1. **Email arrives** while Local is offline
2. **Cloud polls Gmail** → creates `/Needs_Action/EMAIL_abc123.md`
3. **Cloud Agent processes** → writes `/Drafts/Email/REPLY_abc123.md`
4. **Cloud writes approval file** → `/Updates/APPROVAL_abc123.md`
5. **Cloud pushes to Git** → vault syncs to Local
6. **Local comes online** → sees `/Pending_Approval/REPLY_abc123.md`
7. **User approves** → moves to `/Approved/`
8. **Local Orchestrator executes** → sends email via MCP
9. **Local moves to `/Done/`** → syncs back to Cloud
10. **Audit log complete**

## Folder Structure for Platinum Tier

```
AI_Employee_Vault/
├── Cloud/                    # Cloud-owned folders
│   ├── Inbox/
│   ├── Needs_Action/
│   ├── Plans/
│   ├── Drafts/
│   │   ├── Email/
│   │   ├── LinkedIn/
│   │   ├── Twitter/
│   │   ├── Facebook/
│   │   └── Instagram/
│   └── Updates/
│
├── Local/                    # Local-owned folders
│   ├── Pending_Approval/
│   ├── Approved/
│   ├── Rejected/
│   ├── Done/
│   ├── In_Progress/
│   │   └── local_agent/
│   └── Dashboard.md
│
├── Shared/                   # Synced both ways
│   ├── Business_Goals.md
│   ├── Company_Handbook.md
│   └── Accounting/
│
└── .sync-rules.json          # Git sync configuration
```

## Next Steps

1. [ ] Create `.sync-rules.json` for Git sync
2. [ ] Update `.gitignore` to exclude secrets
3. [ ] Create cloud deployment scripts
4. [ ] Setup Odoo Docker Compose
5. [ ] Migrate existing watchers to Cloud/Local structure
6. [ ] Test end-to-end Platinum demo flow
