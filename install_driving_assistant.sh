#!/bin/bash
set -euo pipefail

APP_SOURCE="${1:-$HOME/driving_assistant_allinone.py}"
APP_DEST="/home/driver/driving_assistant_allinone.py"
SERVICE_DEST="/etc/systemd/system/driving-assistant-allinone.service"

if [ ! -f "$APP_SOURCE" ]; then
  echo "Could not find app file: $APP_SOURCE"
  echo "Put driving_assistant_allinone.py in /home/driver, then run:"
  echo "  sudo bash install_driving_assistant.sh /home/driver/driving_assistant_allinone.py"
  exit 1
fi

sudo install -m 755 "$APP_SOURCE" "$APP_DEST"
sudo tee "$SERVICE_DEST" >/dev/null <<'UNIT'
[Unit]
Description=Driving Assistant Sensor, Buzzer and Phone Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/driver
ExecStart=/usr/bin/python3 /home/driver/driving_assistant_allinone.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

# Stop the earlier services so that two processes do not claim the same GPIO pins
# or both try to listen on port 5000.
sudo systemctl disable --now driving-assistant.service 2>/dev/null || true
sudo systemctl disable --now driving-dashboard.service 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl enable --now driving-assistant-allinone.service
echo
echo "Installed and started. Check status with:"
echo "  sudo systemctl status driving-assistant-allinone.service --no-pager"
echo "View live logs with:"
echo "  sudo journalctl -u driving-assistant-allinone.service -f"
echo "Open the dashboard at http://<PI-IP-ADDRESS>:5000"
