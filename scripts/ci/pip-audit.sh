#!/usr/bin/env bash
#
# Audit a service's locked PRODUCTION dependencies for known CVEs.
#
# Run from the service directory (the one containing pyproject.toml + uv.lock).
# Exports the locked, non-dev, non-editable deps to a requirements file (so the
# audit matches what ships in the --no-dev image), then runs pip-audit. Using
# -r is required because --disable-pip only works with a requirements file.
#
# Reads from the environment (optional):
#   REQ_FILE   Output requirements file. If set, it is kept; if unset, a
#              temp file is used and removed on exit (no stray files locally).
#
# Example (local):
#   cd apps/study-tracker/api && /path/to/scripts/ci/pip-audit.sh
set -euo pipefail

if [[ -n "${REQ_FILE:-}" ]]; then
  req_file="$REQ_FILE"
else
  req_file="$(mktemp -t pip-audit-reqs.XXXXXX)"
  trap 'rm -f "$req_file"' EXIT
fi

uv export --frozen --no-emit-project --no-dev --no-editable -o "$req_file"
uv run pip-audit -r "$req_file" --disable-pip --strict
