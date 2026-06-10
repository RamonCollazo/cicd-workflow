#!/usr/bin/env bash
#
# Best-effort cluster diagnostics, printed when the e2e suite fails.
# Never fails the step (set +e): this is observability, not a gate.
#
# Reads from the environment (all optional, with sensible defaults):
#   CONTEXT       kubectl context           (default: k3d-study-tracker-cluster)
#   NAMESPACE     namespace to inspect       (default: study-tracker)
#   API_SELECTOR  label selector for api    (default: component=study-tracker-api)
#   WEB_SELECTOR  label selector for web    (default: component=study-tracker-web)
set +e

context="${CONTEXT:-k3d-study-tracker-cluster}"
namespace="${NAMESPACE:-study-tracker}"
api_selector="${API_SELECTOR:-component=study-tracker-api}"
web_selector="${WEB_SELECTOR:-component=study-tracker-web}"

echo "=== resources in ${namespace} namespace ==="
kubectl --context "$context" get all -n "$namespace"
echo ""
echo "=== pod descriptions ==="
kubectl --context "$context" describe pods -n "$namespace"
echo ""
echo "=== api logs ==="
kubectl --context "$context" logs -n "$namespace" -l "$api_selector" --tail=200
echo ""
echo "=== web logs ==="
kubectl --context "$context" logs -n "$namespace" -l "$web_selector" --tail=200
