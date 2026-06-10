#!/usr/bin/env bash
#
# Aggregate gate for path-filtered required status checks.
#
# A required branch-protection check must always report. These gate jobs run on
# every PR; this script decides pass/fail:
#   - if the component's paths did not change -> pass through (skipped upstream)
#   - else require the upstream job to have succeeded
#
# Reads from the environment:
#   LABEL    Display name for logs, e.g. "API", "Web", "E2E"
#   CHANGED  "true" when the component's paths changed, else anything else
#   RESULT   Upstream job result: success | failure | cancelled | skipped
#
# Example (local):
#   LABEL=API CHANGED=true  RESULT=success scripts/ci/required-gate.sh   # passes
#   LABEL=API CHANGED=true  RESULT=failure scripts/ci/required-gate.sh   # fails
#   LABEL=API CHANGED=false RESULT=skipped scripts/ci/required-gate.sh   # passes
set -euo pipefail

label="${LABEL:-component}"
changed="${CHANGED:-false}"
result="${RESULT:-}"

if [[ "$changed" != "true" ]]; then
  echo "${label} unchanged; passing through."
  exit 0
fi

if [[ "$result" == "success" ]]; then
  echo "${label} checks passed."
  exit 0
fi

echo "${label} checks did not pass: ${result}"
exit 1
