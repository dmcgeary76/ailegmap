#!/bin/bash
# Keep a VPS copy of the map in step with GitHub main.
#
# Fast-forwards the checkout to origin/main and, when it moved (or the map
# container is not running), rebuilds the `map` image and restarts it. Quiet
# and a no-op when nothing changed, so it is safe to run from a timer:
#
#   sudo cp deploy/ailegmap-refresh.service deploy/ailegmap-refresh.timer /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now ailegmap-refresh.timer
#   systemctl list-timers ailegmap-refresh.timer      # next run
#   journalctl -u ailegmap-refresh.service -n 20      # what the last run did
#
# The units assume the checkout lives at /docker/ailegmap; edit WorkingDirectory
# and ExecStart if yours is elsewhere. Run it by hand any time: ./deploy/vps-refresh.sh
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch -q origin main
current=$(git rev-parse HEAD)
target=$(git rev-parse origin/main)
running=$(docker compose ps --status running -q map 2>/dev/null || true)

if [ "$current" = "$target" ] && [ -n "$running" ]; then
  exit 0
fi

if [ "$current" != "$target" ]; then
  # --ff-only: a checkout with local commits is left alone (and the run fails
  # loudly in the journal) rather than silently merged.
  git merge -q --ff-only origin/main
fi

docker compose build --pull -q map
docker compose up -d map

sync=$(grep -o '"last_sync": "[^"]*"' docs/data.json | cut -d'"' -f4)
echo "ailegmap map refreshed: $(git rev-parse --short HEAD), data.json last_sync ${sync:-unknown}"
