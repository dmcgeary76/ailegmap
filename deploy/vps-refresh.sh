#!/bin/bash
# Keep the VPS copy of the map in step with GitHub main.
#
# The public map (map.edtecharchitect.com) is the `ailegmap` service of a
# separate compose project (DEPLOY_DIR, default /docker/ailegmap-deploy) that
# runs the locally built image `ailegmap:static` behind Traefik. That image
# copies docs/data.json in at build time, so every publish needs a rebuild.
#
# This script fast-forwards the repo checkout to origin/main and, when it
# moved (or the container is not running), rebuilds the image from this
# checkout and recreates the service. Quiet no-op otherwise, so it is safe on
# a timer:
#
#   sudo cp deploy/ailegmap-refresh.service deploy/ailegmap-refresh.timer /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now ailegmap-refresh.timer
#   systemctl list-timers ailegmap-refresh.timer      # next run
#   journalctl -u ailegmap-refresh.service -n 20      # what the last run did
#
# Paths: the units assume this checkout is /docker/ailegmap; override the
# deploy project with DEPLOY_DIR=... and the image tag with IMAGE=....
set -euo pipefail
cd "$(dirname "$0")/.."

DEPLOY_DIR=${DEPLOY_DIR:-/docker/ailegmap-deploy}
SERVICE=${SERVICE:-ailegmap}
IMAGE=${IMAGE:-ailegmap:static}

git fetch -q origin main
current=$(git rev-parse HEAD)
target=$(git rev-parse origin/main)
running=$(docker compose --project-directory "$DEPLOY_DIR" ps --status running -q "$SERVICE" 2>/dev/null || true)

if [ "$current" = "$target" ] && [ -n "$running" ]; then
  exit 0
fi

if [ "$current" != "$target" ]; then
  # --ff-only: a checkout with local commits is left alone (and the run fails
  # loudly in the journal) rather than silently merged.
  git merge -q --ff-only origin/main
fi

docker build --pull -q -f frontend/Dockerfile -t "$IMAGE" . >/dev/null
docker compose --project-directory "$DEPLOY_DIR" up -d --force-recreate "$SERVICE"

sync=$(grep -o '"last_sync": "[^"]*"' docs/data.json | cut -d'"' -f4)
echo "ailegmap refreshed: $(git rev-parse --short HEAD), image $IMAGE, data.json last_sync ${sync:-unknown}"
