#!/usr/bin/env bash
#
# Read the image tag currently pinned in a kustomization overlay.
#
# Used by the dev->prod promotion workflow to discover exactly which tag is
# running in dev, so prod is promoted to the same (proven) artifact instead of
# an operator-typed version.
#
# Uses `kustomize build` (the same tool patch-kustomization.sh writes with):
# the resolved tag appears on the rendered container `image:` line, and
# matching the full image ref disambiguates between the api and web images.
#
# Usage:
#   read-image-tag.sh <kustomization-dir>
#
# Reads from the environment:
#   OWNER      Repository owner, e.g. "RamonCollazo" (lowercased for GHCR)
#   IMAGE      Image basename, e.g. "study-tracker-api"
#   REGISTRY   Container registry host (optional, default: ghcr.io)
#
# Writes "tag=<value>" to $GITHUB_OUTPUT when set, else stdout. Exits non-zero
# if no matching image / tag is found.
#
# Example (local):
#   OWNER=RamonCollazo IMAGE=study-tracker-api \
#     scripts/ci/read-image-tag.sh /path/to/gitops/apps/dev
set -euo pipefail

dir="${1:?usage: read-image-tag.sh <kustomization-dir>}"
: "${OWNER:?OWNER is required}"
: "${IMAGE:?IMAGE is required}"
registry="${REGISTRY:-ghcr.io}"

owner_lower="$(echo "$OWNER" | tr '[:upper:]' '[:lower:]')"
image_ref="${registry}/${owner_lower}/${IMAGE}"

# Escape regex metacharacters (dots) in the ref before matching.
ref_re="${image_ref//./\\.}"

# Render the overlay and grab "<image_ref>:<tag>" off the container image line.
match="$(kustomize build "$dir" | grep -oE "${ref_re}:[A-Za-z0-9_.-]+" | head -n1)"
tag="${match##*:}"

if [[ -z "$tag" ]]; then
  echo "no image tag found for ${image_ref} in overlay ${dir}" >&2
  exit 1
fi

echo "Resolved ${image_ref} -> ${tag} (from ${dir})" >&2
echo "tag=${tag}" >>"${GITHUB_OUTPUT:-/dev/stdout}"
