#!/usr/bin/env bash
#
# Patch a kustomization's image tag with `kustomize edit set image`.
#
# Usage:
#   patch-kustomization.sh <kustomization-dir>
#
# Reads from the environment:
#   OWNER      Repository owner, e.g. "RamonCollazo" (lowercased for GHCR)
#   IMAGE      Image basename, e.g. "study-tracker-api"
#   TAG        New image tag, e.g. "v1.2.3"
#   REGISTRY   Container registry host (optional, default: ghcr.io)
#
# Example (local):
#   OWNER=RamonCollazo IMAGE=study-tracker-api TAG=v1.2.3 \
#     scripts/ci/patch-kustomization.sh /tmp/gitops/apps/dev
set -euo pipefail

dir="${1:?usage: patch-kustomization.sh <kustomization-dir>}"
: "${OWNER:?OWNER is required}"
: "${IMAGE:?IMAGE is required}"
: "${TAG:?TAG is required}"
registry="${REGISTRY:-ghcr.io}"

owner_lower="$(echo "$OWNER" | tr '[:upper:]' '[:lower:]')"
image_ref="${registry}/${owner_lower}/${IMAGE}"

echo "Patching ${image_ref} -> ${TAG} in ${dir}"
(
  cd "$dir"
  kustomize edit set image "${image_ref}=${image_ref}:${TAG}"
  echo "--- result ---"
  cat kustomization.yaml
)
