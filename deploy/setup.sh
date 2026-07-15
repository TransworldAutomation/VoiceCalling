#!/usr/bin/env bash
#
# One-shot installer for the Oracle Cloud (Ubuntu) VM.
# Run it from INSIDE the project folder after cloning:
#
#     bash deploy/setup.sh your-name.duckdns.org
#
set -e

DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
  echo "Usage: bash deploy/setup.sh YOUR_DOMAIN.duckdns.org"
  exit 1
fi

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
echo "Project folder: $APP_DIR"

echo "== [1/6] System packages =="
sudo apt-get update -y
sudo apt-get install -y git curl python3.12 python3.12-venv 2>/dev/null || {
  echo "python3.12 not in default repos; adding deadsnakes..."
  sudo apt-get install -y software-properties-common
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -y
  sudo apt-get install -y python3.12 python3.12-venv
}

echo "== [2/6] Caddy (auto-HTTPS) =="
if ! command -v caddy >/dev/null; then
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

echo "== [3/6] Python virtual env + dependencies (this takes a few minutes) =="
python3.12 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements-server.txt

echo "== [4/6] systemd services =="
sudo cp deploy/voice-dashboard.service /etc/systemd/system/
sudo cp deploy/voice-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-dashboard voice-server

echo "== [5/6] Caddy site config for $DOMAIN =="
sudo sed "s/YOUR_DOMAIN/$DOMAIN/" deploy/Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl restart caddy

echo "== [6/6] Open firewall ports 80 + 443 =="
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
sudo netfilter-persistent save 2>/dev/null || (sudo apt-get install -y iptables-persistent && sudo netfilter-persistent save) || true

echo ""
echo "=========================================================="
echo " Almost done. Now:"
echo "  1. Create your .env in $APP_DIR with your API keys and:"
echo "        PUBLIC_URL=https://$DOMAIN"
echo "  2. Start the app:"
echo "        sudo systemctl restart voice-dashboard voice-server"
echo "  3. Open https://$DOMAIN in your browser."
echo "=========================================================="
