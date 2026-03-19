#!/bin/bash
# cloud_setup.sh - Platinum Tier Cloud VM Setup Script
# Run this on your Oracle Cloud / AWS Free Tier VM

set -e

echo "============================================================"
echo "  AI Employee Digital FTE - Platinum Tier Cloud Setup"
echo "============================================================"

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "[2/8] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
rm get-docker.sh

# Install Docker Compose
echo "[3/8] Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Node.js 20.x
echo "[4/8] Installing Node.js 20.x..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Python 3.11
echo "[5/8] Installing Python 3.11..."
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Git
echo "[6/8] Installing Git..."
sudo apt install -y git

# Create directories
echo "[7/8] Creating directories..."
sudo mkdir -p /opt/ai-employee/{vault-sync,odoo,watchers}
sudo chown -R $USER:$USER /opt/ai-employee

# Clone or setup vault sync repo
echo "[8/8] Setting up vault sync repository..."
cd /opt/ai-employee/vault-sync
git init --bare

# Setup Odoo Docker Compose
echo "Setting up Odoo Community..."
cd /opt/ai-employee/odoo
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_USER=odoo
      - POSTGRES_PASSWORD=odoo
    volumes:
      - odoo-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 10s
      retries: 5

  odoo:
    image: odoo:17.0
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8080:8069"
    environment:
      - HOST=db
      - USER=odoo
      - PASSWORD=odoo
    volumes:
      - odoo-web-data:/var/lib/odoo
      - ./config:/etc/odoo
      - ./addons:/mnt/extra-addons
    command: --dev --workers=2 --max-cron-threads=1

volumes:
  odoo-db-data:
  odoo-web-data:
EOF

# Install Nginx
echo "Installing Nginx..."
sudo apt install -y nginx

# Setup Nginx reverse proxy
sudo tee /etc/nginx/sites-available/ai-employee > /dev/null << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/ai-employee /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup Cloud Watchers as systemd services
echo "Setting up Cloud Watchers services..."
sudo tee /etc/systemd/system/cloud-gmail-watcher.service > /dev/null << EOF
[Unit]
Description=AI Employee - Cloud Gmail Watcher
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/ai-employee/watchers
Environment="PATH=/home/$USER/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="DRY_RUN=false"
Environment="VAULT_PATH=/opt/ai-employee/vault"
ExecStart=/home/$USER/.local/bin/python /opt/ai-employee/watchers/gmail_watcher.py --vault \$VAULT_PATH
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloud-gmail-watcher

# Setup Git hooks for vault sync
echo "Setting up Git sync hooks..."
cd /opt/ai-employee/vault-sync
cat > hooks/post-receive << 'EOF'
#!/bin/bash
# After receiving push, update working tree
GIT_WORK_TREE=/opt/ai-employee/vault git checkout -f
EOF
chmod +x hooks/post-receive

echo ""
echo "============================================================"
echo "  Cloud Setup Complete!"
echo "============================================================"
echo ""
echo "Next Steps:"
echo "  1. Setup SSL with Let's Encrypt:"
echo "     sudo apt install certbot python3-certbot-nginx"
echo "     sudo certbot --nginx -d your-domain.com"
echo ""
echo "  2. Clone vault on Local machine:"
echo "     git clone user@your-cloud-vm:/opt/ai-employee/vault-sync"
echo ""
echo "  3. Start Odoo:"
echo "     cd /opt/ai-employee/odoo && docker-compose up -d"
echo ""
echo "  4. Start Cloud Watchers:"
echo "     sudo systemctl start cloud-gmail-watcher"
echo ""
echo "============================================================"
