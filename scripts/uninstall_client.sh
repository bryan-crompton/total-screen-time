#!/usr/bin/env bash
set -euo pipefail

APP_NAME="screentime"
SERVICE_NAME="screentime.service"
SERVICE_FILE="${HOME}/.config/systemd/user/${SERVICE_NAME}"

systemctl --user disable --now "${SERVICE_NAME}" 2>/dev/null || true
rm -f "${SERVICE_FILE}"
systemctl --user daemon-reload || true
pipx uninstall "${APP_NAME}" || true

echo "Removed service and pipx app."
