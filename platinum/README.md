# Platinum Tier Deployment Guide

> **Always-On Cloud + Local Executive** — Production-ready AI Employee

## Overview

Platinum Tier extends the Gold Tier with:

| Feature | Description |
|---------|-------------|
| **Cloud VM** | Always-on watchers (Gmail, Social) on Oracle/AWS Free Tier |
| **Local Executive** | Human approvals, WhatsApp, payments on your desktop |
| **Vault Sync** | Git-based sync between Cloud and Local |
| **Work-Zone Separation** | Cloud drafts, Local executes |
| **Security** | Secrets never sync (.env, auth_info, cookies) |

## Architecture

```
┌─────────────────────────────────────────┐
│           CLOUD VM (Oracle/AWS)         │
│  - Gmail Watcher (drafts only)          │
│  - Social Watchers (drafts only)        │
│  - Odoo Community (Accounting)          │
│  - Cloud Agent (Qwen/Claude)            │
│  - Writes to: Cloud/Drafts/, Cloud/Updates/ │
└───────────────────┬─────────────────────┘
                    │ Git Sync (vault state only)
                    │ NO SECRETS SYNCED
┌───────────────────┴─────────────────────┐
│        LOCAL MACHINE (Your Desktop)     │
│  - WhatsApp Baileys (full session)      │
│  - Payment MCP (local execution)        │
│  - Human Approval (move files)          │
│  - Local Orchestrator (executes)        │
│  - Writes to: Local/Approved/, Local/Done/ │
└─────────────────────────────────────────┘
```

## Phase 1: Setup Cloud VM

### 1.1 Create Cloud VM (Oracle Cloud Free Tier)

1. Sign up at https://cloud.oracle.com
2. Create **Always Free ARM Ampere A1 Compute**:
   - 4 OCPUs, 24GB RAM
   - 200GB block volume
   - Ubuntu 22.04 LTS
3. Configure security list:
   - Allow SSH (port 22)
   - Allow HTTP (port 80)
   - Allow HTTPS (port 443)

### 1.2 Run Cloud Setup Script

```bash
# SSH into your VM
ssh -i your-key.pem ubuntu@your-vm-ip

# Clone your repo
git clone https://github.com/your-username/AI-Employee-Digital-FTE.git
cd AI-Employee-Digital-FTE

# Run setup script
chmod +x platinum/cloud_setup.sh
./platinum/cloud_setup.sh
```

### 1.3 Configure Environment Variables

```bash
# On Cloud VM
cd AI-Employee-Digital-FTE
cp .env.example .env
nano .env

# Set these:
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
DRY_RUN=false
AGENT=qwen
ERPNEXT_URL=http://localhost:8080
ERPNEXT_USERNAME=administrator
ERPNEXT_PASSWORD=your_password
```

### 1.4 Start Cloud Services

```bash
# Start Odoo
cd /opt/ai-employee/odoo
docker-compose up -d

# Start Cloud Watchers
sudo systemctl start cloud-gmail-watcher
sudo systemctl enable cloud-gmail-watcher

# Check status
sudo systemctl status cloud-gmail-watcher
```

## Phase 2: Setup Local Sync

### 2.1 Initialize Local Git Repo

```bash
# On your local machine (Windows)
cd E:\mujtaba data\coding classes\proramming\my code\GitHub_Repo_Codes\hackthon-0\AI-Employee-Digital-FTE\AI_Employee_Vault

# Initialize git
git init
git config user.name "Your Name"
git config user.email "your@email.com"

# Add cloud remote
git remote add cloud ubuntu@your-vm-ip:/opt/ai-employee/vault-sync
```

### 2.2 Configure Sync Rules

The `.sync-rules.json` file defines what syncs:

| Folder | Sync Direction | Purpose |
|--------|---------------|---------|
| `Cloud/Drafts/` | Cloud → Local | Email/social drafts for approval |
| `Cloud/Updates/` | Cloud → Local | Approval signals from Cloud |
| `Local/Done/` | Local → Cloud | Audit trail |
| `Local/Pending_Approval/` | ❌ Never | Local only (security) |
| `Local/Approved/` | ❌ Never | Local only (security) |
| `.env` | ❌ Never | Secrets |
| `auth_info/` | ❌ Never | WhatsApp session |

### 2.3 Run Local Sync

```bash
# On local machine
cd AI_Employee_Vault
bash ../platinum/local_sync.sh
```

## Phase 3: Test Platinum Demo Flow

### 3.1 Send Test Email

1. Send an email to your Gmail account
2. Cloud Gmail Watcher polls (every 2 min)
3. Cloud Agent processes and creates draft
4. Draft appears in `Cloud/Drafts/Email/`
5. Signal written to `Cloud/Updates/`

### 3.2 Sync to Local

```bash
# On local machine
cd AI_Employee_Vault
git pull cloud main
```

### 3.3 Review and Approve

1. Check `Local/Pending_Approval/` for new draft
2. Review the AI-generated reply
3. If approved, move file to `Local/Approved/`

### 3.4 Local Orchestrator Executes

1. Platinum Orchestrator detects file in `Local/Approved/`
2. Executes send via Email MCP
3. Moves completed file to `Local/Done/`

### 3.5 Sync Completion Back to Cloud

```bash
# On local machine
cd AI_Employee_Vault
git add Local/Done/
git commit -m "Completed email reply"
git push cloud main
```

## Folder Structure

```
AI_Employee_Vault/
├── Cloud/
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
├── Local/
│   ├── Pending_Approval/
│   ├── Approved/
│   ├── Rejected/
│   ├── Done/
│   ├── In_Progress/
│   └── Dashboard.md
│
├── Shared/
│   ├── Business_Goals.md
│   ├── Company_Handbook.md
│   └── Accounting/
│
└── .sync-rules.json
```

## Security Checklist

- [ ] `.env` file in `.gitignore`
- [ ] `auth_info/` in `.gitignore`
- [ ] `*.cookies.json` in `.gitignore`
- [ ] `Local/Pending_Approval/` never syncs
- [ ] `Local/Approved/` never syncs
- [ ] HTTPS enabled on Cloud VM
- [ ] SSH key authentication only
- [ ] Firewall configured (ufw)

## Troubleshooting

### Cloud Watcher Not Running

```bash
# Check status
sudo systemctl status cloud-gmail-watcher

# View logs
sudo journalctl -u cloud-gmail-watcher -f

# Restart
sudo systemctl restart cloud-gmail-watcher
```

### Git Sync Failing

```bash
# Check remote
git remote -v

# Test connection
ssh ubuntu@your-vm-ip

# Force pull
git pull cloud main --force
```

### Drafts Not Appearing in Local

1. Check Cloud/Drafts/ has files
2. Run `git pull cloud main` on Local
3. Check `.sync-rules.json` includes `Cloud/Drafts/**`

## Next Steps

1. **Setup SSL**: `sudo certbot --nginx -d your-domain.com`
2. **Add More Watchers**: Deploy LinkedIn, Twitter watchers to Cloud
3. **Setup Odoo MCP**: Integrate accounting actions
4. **Enable A2A**: Implement WebSocket for real-time sync

## Support

For issues or questions:
- Check logs in `AI_Employee_Vault/Logs/`
- Review `.sync-rules.json` for sync configuration
- Run `python test_watchers.py` for system diagnostics
