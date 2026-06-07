# Kubernetes / e2e tests

End-to-end tests for the Study Tracker app on a local [k3d](https://k3d.io) cluster.
The suite stands up a cluster, builds the API and Web Docker images, imports them into
the cluster, applies kustomize, waits for both Deployments to roll out, and runs HTTP
checks against the LoadBalancer-exposed services.

## Prerequisites

- `k3d`, `kubectl`, `docker`, `uv`, and `mise` available on `PATH` (all pinned in `mise.toml`).
- `mise install` once at the repo root sets up the right versions.

## One-shot run (default)

```bash
cd kubernetes
uv sync --group dev
uv run pytest
```

This creates the cluster, deploys the app, runs all tests, and tears the cluster
down on session end.

## Fast iteration

When debugging tests, avoid recreating the cluster on every run.

```bash
# 1) First run — bring up the cluster, leave it running:
uv run pytest --keep-cluster

# 2) Subsequent runs — assume cluster + app are already deployed:
uv run pytest --no-cluster-setup

# 3) When done — clean up manually:
k3d cluster delete study-tracker-cluster
```

`--no-cluster-setup` skips image build, image import, and `kubectl apply` entirely; it
only resolves the LoadBalancer URLs and runs the HTTP tests. Typical run time is
< 1 second.

## Debugging a single failing test

```bash
uv run pytest -v -s --tb=long --no-cluster-setup -k <test_name>
```

`-s` disables output capture so `print` statements and logging surface in real time.

## CLI options

| Option | Effect |
|---|---|
| `--no-cluster-setup` | Assume cluster + app are already deployed. Errors out if the cluster does not exist. |
| `--keep-cluster` | Don't delete the cluster on session teardown. |
| `--cluster-name NAME` | Override the default `study-tracker-cluster`. |

## Layout

```
kubernetes/
├── conftest.py                # pytest options + fixtures (cluster, deployed_app, api_url, web_url, http, unique_tag)
├── helpers/
│   ├── cluster.py             # subprocess wrappers for k3d / kubectl / docker
│   └── service_url.py         # LoadBalancer IP discovery via `kubectl wait --for=jsonpath`
├── tests/
│   ├── test_health.py         # /health + / on api and web
│   ├── test_api_sessions.py   # POST/GET /sessions + tag normalization + filtering
│   ├── test_api_validation.py # 422 cases for invalid payloads
│   ├── test_api_stats.py      # /stats aggregation (asserts on per-tag slices only)
│   └── test_integration.py    # web form submission persists through to api
├── manifests/                 # base + dev kustomize overlays
├── k3d-config.yaml            # cluster shape (1 server, 1 agent, no traefik)
├── setup_cluster_local        # bash convenience: cluster + deploy without pytest
├── setup_cluster_minimal      # bash convenience: cluster only
└── pyproject.toml             # pytest, ruff, e2e marker
```

## State isolation

Tests that mutate state always create rows tagged with a per-test unique tag
(`e2e-<8 hex>`) and assert only on that tag's slice. They never assert on
`total_sessions` or other global aggregates, so the suite is correct even when the
cluster has leftover data from earlier runs.

## Relationship to `setup_cluster_local`

`setup_cluster_local` is a small bash convenience for "bring up a cluster and deploy
the app so I can poke at it" — no tests, no fixtures. It does the same cluster
bringup as the pytest fixtures but they're independent implementations. The
duplication is small (a handful of `k3d`, `docker`, `kubectl` calls) and the two
evolve independently.

If both will ever drift in dangerous ways, the bash script is the canonical user
entry point and the test suite owns its own setup; cross-reference rather than
share code.
