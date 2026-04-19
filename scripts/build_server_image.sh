#!/usr/bin/env bash
set -euo pipefail
IMAGE_NAME="${1:-screentime-server:latest}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"
docker build -t "${IMAGE_NAME}" .
echo "Built ${IMAGE_NAME}"
