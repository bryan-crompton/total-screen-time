#!/usr/bin/env bash
set -euo pipefail
CONTAINER_NAME="${SCREENTIME_CONTAINER_NAME:-screentime-server}"
docker rm -f "${CONTAINER_NAME}"
