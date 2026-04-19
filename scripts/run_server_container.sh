#!/usr/bin/env bash
set -euo pipefail
IMAGE_NAME="${1:-screentime-server:latest}"
CONTAINER_NAME="${SCREENTIME_CONTAINER_NAME:-screentime-server}"
PORT="${SCREENTIME_SERVER_PORT:-7777}"
DATA_DIR="${SCREENTIME_SERVER_DATA_DIR:-$PWD/server_data}"
mkdir -p "${DATA_DIR}"
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:7777" \
  -v "${DATA_DIR}:/data" \
  -e SCREENTIME_SERVER_DB_PATH=/data/server.db \
  -e SCREENTIME_SERVER_HOST=0.0.0.0 \
  -e SCREENTIME_SERVER_PORT=7777 \
  --restart unless-stopped \
  "${IMAGE_NAME}"

echo "Container: ${CONTAINER_NAME}"
echo "Port: ${PORT}"
echo "Data dir: ${DATA_DIR}"
echo "Health: curl http://127.0.0.1:${PORT}/health"
