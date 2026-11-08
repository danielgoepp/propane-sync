#!/usr/bin/env bash
# Build the propane-sync image on this host and push it to GitHub Container Registry.
#
# One-time setup (needs a GitHub PAT with write:packages scope):
#   echo "$GHCR_TOKEN" | docker login ghcr.io -u danielgoepp --password-stdin
#
# Usage:
#   ./build-and-push.sh            # build + push :latest and :<git-sha>
#   NO_PUSH=1 ./build-and-push.sh  # build only
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/danielgoepp/propane-sync}"
cd "$(dirname "$0")"

SHA="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  SHA="${SHA}-dirty"
fi

docker build \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "${IMAGE}:latest" \
  -t "${IMAGE}:${SHA}" \
  .

if [[ -n "${NO_PUSH:-}" ]]; then
  echo "Built ${IMAGE}:latest and ${IMAGE}:${SHA} (not pushed)"
  exit 0
fi

docker push "${IMAGE}:${SHA}"
docker push "${IMAGE}:latest"
echo "Pushed ${IMAGE}:latest and ${IMAGE}:${SHA}"
