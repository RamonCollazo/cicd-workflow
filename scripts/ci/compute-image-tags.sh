#!/usr/bin/env bash
#
# Compute the GHCR image name and tags from a release tag.
#
# Reads from the environment (so it is injection-safe and locally testable):
#   REGISTRY     Container registry host, e.g. "ghcr.io"
#   OWNER        Repository owner, e.g. "RamonCollazo" (lowercased for GHCR)
#   GIT_TAG      Full git tag, e.g. "study-tracker-api-v0.3.1"
#   TAG_PREFIX   Prefix to strip, e.g. "study-tracker-api-v"
#   IMAGE_NAME   Image basename, e.g. "study-tracker-api"
#
# Writes name/version_tag/latest_tag to $GITHUB_OUTPUT when set, else stdout.
#
# Example (local):
#   REGISTRY=ghcr.io OWNER=RamonCollazo GIT_TAG=study-tracker-api-v0.3.1 \
#     TAG_PREFIX=study-tracker-api-v IMAGE_NAME=study-tracker-api \
#     scripts/ci/compute-image-tags.sh
set -euo pipefail

: "${REGISTRY:?REGISTRY is required}"
: "${OWNER:?OWNER is required}"
: "${GIT_TAG:?GIT_TAG is required}"
: "${TAG_PREFIX:?TAG_PREFIX is required}"
: "${IMAGE_NAME:?IMAGE_NAME is required}"

# GHCR requires the owner segment to be lowercase.
owner_lower="$(echo "$OWNER" | tr '[:upper:]' '[:lower:]')"
image="${REGISTRY}/${owner_lower}/${IMAGE_NAME}"

# Strip the "<...>-v" prefix to get bare semver, then re-prefix with "v".
#   study-tracker-api-v0.3.1 -> 0.3.1 -> v0.3.1
bare="${GIT_TAG#"${TAG_PREFIX}"}"
version_tag="v${bare}"

out="${GITHUB_OUTPUT:-/dev/stdout}"
{
  echo "name=${image}"
  echo "version_tag=${version_tag}"
  echo "latest_tag=latest"
} >>"$out"
