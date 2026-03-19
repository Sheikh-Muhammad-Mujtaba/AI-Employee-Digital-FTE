#!/bin/bash
# local_sync.sh - Platinum Tier Local Vault Sync Script
# Run this on your local machine to sync with Cloud VM

set -e

VAULT_PATH="${VAULT_PATH:-./AI_Employee_Vault}"
CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_HOST="${CLOUD_HOST:-your-cloud-vm-ip}"
CLOUD_REPO="/opt/ai-employee/vault-sync"

echo "============================================================"
echo "  AI Employee Digital FTE - Platinum Tier Local Sync"
echo "============================================================"
echo ""
echo "  Vault: $VAULT_PATH"
echo "  Cloud: $CLOUD_USER@$CLOUD_HOST:$CLOUD_REPO"
echo ""

# Check if vault exists
if [ ! -d "$VAULT_PATH" ]; then
    echo "[ERROR] Vault not found at: $VAULT_PATH"
    echo "Creating new vault structure..."
    mkdir -p "$VAULT_PATH"
fi

cd "$VAULT_PATH"

# Initialize git if not already
if [ ! -d ".git" ]; then
    echo "[1/4] Initializing Git repository..."
    git init
    git config user.name "AI Employee Local"
    git config user.email "local@ai-employee.local"
fi

# Add cloud remote if not exists
if ! git remote | grep -q "cloud"; then
    echo "[2/4] Adding cloud remote..."
    git remote add cloud "$CLOUD_USER@$CLOUD_HOST:$CLOUD_REPO"
fi

# Fetch from cloud
echo "[3/4] Fetching from cloud..."
git fetch cloud || echo "No cloud repo yet, will create on first push"

# Sync Cloud/ folders (read from cloud)
echo "[4/4] Syncing Cloud/ folders..."
git pull cloud main --no-edit || true

# Copy Cloud/Drafts to Local/Pending_Approval for review
echo ""
echo "Syncing drafts to Pending_Approval..."
if [ -d "Cloud/Drafts" ]; then
    for draft in Cloud/Drafts/*/*.md; do
        if [ -f "$draft" ]; then
            filename=$(basename "$draft")
            cp "$draft" "Local/Pending_Approval/$filename"
            echo "  → Copied: $filename"
        fi
    done
fi

echo ""
echo "============================================================"
echo "  Sync Complete!"
echo "============================================================"
echo ""
echo "To push changes back to cloud:"
echo "  git add Local/Done/"
echo "  git commit -m 'Sync completed tasks'"
echo "  git push cloud main"
echo ""
echo "To pull new drafts from cloud:"
echo "  ./local_sync.sh"
echo ""
