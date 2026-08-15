#!/usr/bin/env bash
# Install nginx on the Raspberry Pi and serve tournaments.json.
# Run from a desktop session so pkexec can prompt for the password.
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_ROOT="/var/www/tracker"

echo "==> Installing nginx"
pkexec apt-get update
pkexec apt-get install -y nginx

echo "==> Copying tracker server to /opt/tracker"
pkexec mkdir -p /opt/tracker
pkexec cp -r "$SERVER_DIR"/. /opt/tracker/

echo "==> Configuring nginx site"
pkexec tee /etc/nginx/sites-available/tracker > /dev/null < "$SERVER_DIR/nginx.conf"
pkexec ln -sf /etc/nginx/sites-available/tracker /etc/nginx/sites-enabled/tracker
pkexec rm -f /etc/nginx/sites-enabled/default

echo "==> Creating web root and building the feed"
pkexec mkdir -p "$WEB_ROOT"
pkexec bash -c "cd /opt/tracker && python3 -m venv .venv 2>/dev/null; .venv/bin/pip install -q -r requirements.txt"
pkexec bash -c "cd /opt/tracker && .venv/bin/python build_json.py --output '$WEB_ROOT/tournaments.json'"

echo "==> Testing and reloading nginx"
pkexec nginx -t
pkexec systemctl reload nginx

echo "==> Setting up systemd timer (boot + daily 05:00 refresh)"
pkexec cp "$SERVER_DIR/tracker.service" /etc/systemd/system/tracker.service
pkexec cp "$SERVER_DIR/tracker.timer" /etc/systemd/system/tracker.timer
pkexec rm -f /etc/cron.d/tracker
pkexec systemctl daemon-reload
pkexec systemctl enable --now tracker.timer
pkexec systemctl start tracker.service

echo
echo "Done. The feed is at:"
IP=$(hostname -I | awk '{print $1}')
echo "  http://$IP/tournaments.json"
echo "Put this URL into the Mac app (default is http://raspberrypi.local/tournaments.json)."
