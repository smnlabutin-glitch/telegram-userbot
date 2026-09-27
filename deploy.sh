#!/usr/bin/env bash
set -e

# ========================================================
# Telegram Userbot 24/7 Server Deployment Script
# Supports: Ubuntu, Debian, CentOS, Rocky Linux, AlmaLinux
# ========================================================

echo "========================================================"
echo "   TELEGRAM USERBOT // 24/7 SERVER INSTALLER"
echo "========================================================"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="telegram-userbot"

echo "[1/5] Detecting package manager & installing requirements..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-venv python3-pip ca-certificates curl
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3 python3-pip ca-certificates curl
elif command -v yum &>/dev/null; then
    sudo yum install -y python3 python3-pip ca-certificates curl
fi

echo "[2/5] Setting up Python virtual environment..."
cd "$APP_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/5] Verifying environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[!] Created .env from .env.example."
        echo "[!] Please edit $APP_DIR/.env with your TELEGRAM_API_ID and TELEGRAM_API_HASH before starting!"
    fi
fi

# Ensure logs directory exists
mkdir -p "$APP_DIR/logs"

echo "[4/5] Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Telegram Aesthetic Userbot 24/7 Daemon
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP_DIR/venv/bin/python main.py

# 24/7 Autorestart policy
Restart=always
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s

# Resource limits
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "[5/5] Checking session authorization..."
# Check if session exists
SESSION_FILE=$(find "$APP_DIR" -maxdepth 1 -name "*.session" | head -n 1)

if [ -z "$SESSION_FILE" ]; then
    echo "--------------------------------------------------------"
    echo "✦ FIRST LAUNCH: Telegram Phone & Code Authentication ✦"
    echo "Please log in now to save your session file."
    echo "--------------------------------------------------------"
    python main.py || true
fi

echo "--------------------------------------------------------"
echo "[+] Starting systemd service for 24/7 operation..."
sudo systemctl restart "${SERVICE_NAME}"

echo "========================================================"
echo "   DEPLOYMENT SUCCESSFUL! USERBOT RUNNING 24/7"
echo "========================================================"
echo "Useful commands:"
echo "  • Check status : sudo systemctl status ${SERVICE_NAME}"
echo "  • View logs    : sudo journalctl -u ${SERVICE_NAME} -f"
echo "  • File logs    : tail -f $APP_DIR/logs/userbot.log"
echo "  • Restart bot  : sudo systemctl restart ${SERVICE_NAME}"
echo "  • Stop bot     : sudo systemctl stop ${SERVICE_NAME}"
echo "========================================================"
