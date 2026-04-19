#!/usr/bin/env bash
set -euo pipefail

APP_NAME="screentime"
ENTRYPOINT="screentime-ubuntu-monitor"
SERVICE_NAME="screentime.service"
SERVER_PORT_DEFAULT="7777"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
DATA_DIR="${HOME}/.local/share/screentime"

command -v pipx >/dev/null 2>&1 || {
    echo "pipx not found on PATH" >&2
    exit 1
}

mkdir -p "${USER_SYSTEMD_DIR}"
mkdir -p "${DATA_DIR}"

read -r -p "Sync server IP or hostname: " SERVER_HOST
SERVER_PORT="${SCREENTIME_SERVER_PORT:-$SERVER_PORT_DEFAULT}"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"

cd "${REPO_DIR}"
pipx install -e . --force

PIPX_HOME="$(pipx environment --value PIPX_HOME)"
PIPX_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR)"
PIPX_VENV="${PIPX_HOME}/venvs/${APP_NAME}"

[[ -x "${PIPX_BIN_DIR}/${ENTRYPOINT}" ]] || {
    echo "Missing entrypoint: ${PIPX_BIN_DIR}/${ENTRYPOINT}" >&2
    exit 1
}

"${PIPX_VENV}/bin/python" -c "import screentime, screentime.ubuntu.monitor; print('import ok:', screentime.__file__)"

cat > "${SERVICE_FILE}" <<EOF2
[Unit]
Description=Screen time monitor
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
Environment=PATH=${PIPX_BIN_DIR}:/usr/bin:/bin
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus
Environment=SCREENTIME_DB_PATH=%h/.local/share/screentime/screentime.db
Environment=SCREENTIME_SERVER_URL=${SERVER_URL}
Environment=SCREENTIME_ACTIVITY_THRESHOLD=15
Environment=SCREENTIME_POLL_INTERVAL=5
Environment=SCREENTIME_GAP_TIMEOUT=30
Environment=SCREENTIME_SYNC_INTERVAL=30
ExecStart=${PIPX_BIN_DIR}/${ENTRYPOINT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF2

systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}"

echo
systemctl --user --no-pager --full status "${SERVICE_NAME}" || true

echo
journalctl --user -u "${SERVICE_NAME}" -n 30 --no-pager || true
