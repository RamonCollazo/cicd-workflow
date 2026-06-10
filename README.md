# cicd-workflow

![API Tests](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/api-tests.yaml/badge.svg)
![Web Tests](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/web-tests.yaml/badge.svg)
![E2E Tests](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/e2e-tests.yaml/badge.svg)
![Manifests Lint](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/manifests-lint.yaml/badge.svg)
![Build & Push](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/docker-build-push.yaml/badge.svg)
![Release Please](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/release-please.yaml/badge.svg)
![Dependency Review](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/dependency-review.yaml/badge.svg)
![Gitleaks](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/gitleaks.yaml/badge.svg)

Repo for CI/CD workflow learning project. Houses two Python apps under `apps/study-tracker/` (FastAPI `api`, Flask `web`) wired up to a full GitHub-Actions pipeline.

## Pipeline overview

**On every PR** — each pipeline triggers on all PRs and filters paths
*internally* (`dorny/paths-filter`), so its required status check always
reports. Each ends in an aggregator gate (`*-required`) that passes through when
the relevant paths weren't touched.

- **`API Tests` / `Web Tests`** — when the respective app changes, run the
  reusable `_python-service-tests.yaml` quality gate: ruff lint + format check,
  mypy, bandit, pip-audit (locked production deps), pytest with ≥ 80 % coverage,
  a Docker image build, and a **blocking** Trivy scan (fixable CRITICAL/HIGH).
  Each ends in `api-required` / `web-required`.
- **`E2E Tests`** — when either app changes, spins up k3d on the runner, builds
  + imports both images, applies the dev overlay, and runs the HTTP integration
  suite once (`kubernetes/`, pytest). Ends in `e2e-required`.
- **`Manifests Lint`** — when `kubernetes/manifests/**` changes: `kustomize build`
  the dev overlay → `kubeconform` schema validation → `checkov` misconfig scan.
- **`Dependency Review`** and **`Gitleaks`** run on every PR.

**Push to `main`** — `Gitleaks` re-runs across full history. `release-please`
opens (or updates) a per-component release PR (`study-tracker-api`,
`study-tracker-web`).

**Release PR merged** — release-please cuts a per-component tag
(`study-tracker-api-vX.Y.Z` or `study-tracker-web-vX.Y.Z`).

**Tag pushed** — `docker-build-push` builds the affected app for
**linux/amd64 + linux/arm64**, pushes to GHCR with build cache, attaches an
**SBOM + provenance** attestation, and **signs the image with cosign** (keyless
/ OIDC). It then calls `Update GitOps`, which opens a PR in
`cicd-workflow-gitops` bumping the dev image tag (auto-merged).
  - `ghcr.io/RamonCollazo/study-tracker-{api,web}:vX.Y.Z`, `:latest`, and `:sha-<commit>`

## CI scripts

The shell logic used by the workflows lives in `scripts/ci/` so it is version
controlled, shellcheck-linted (pre-commit + `mise run lint-scripts`), and
testable standalone — no need to rerun the pipeline to validate a change. Each
script reads its inputs from environment variables / arguments (never inline
`${{ }}` interpolation):

| Script | Used by | Inputs |
| --- | --- | --- |
| `compute-image-tags.sh` | `docker-build-push` | env `REGISTRY OWNER GIT_TAG TAG_PREFIX IMAGE_NAME` |
| `required-gate.sh` | the `*-required` gates | env `LABEL CHANGED RESULT` |
| `cluster-diagnostics.sh` | `e2e-tests` (on failure) | env `CONTEXT NAMESPACE API_SELECTOR WEB_SELECTOR` |
| `pip-audit.sh` | reusable test gate | runs in the service dir |
| `patch-kustomization.sh` | `update-gitops` | arg: overlay dir; env `OWNER IMAGE TAG` |

Example — reproduce the gitops image bump locally:

```bash
OWNER=RamonCollazo IMAGE=study-tracker-api TAG=v1.2.3 \
  scripts/ci/patch-kustomization.sh /path/to/gitops/apps/dev
```

## Repo-managed security features

The following are enabled via repo settings rather than committed workflow files:

- **CodeQL** — default setup, scans Python on PRs, pushes to `main`, and on a schedule. Findings: Security → Code scanning.
- **Dependabot security updates** — opens PRs only when a published CVE matches a dep in your tree. (Routine version-update PRs intentionally not configured.)

## Branch protection

Required status checks on `main` (configure in Settings → Rules → Rulesets):

- `API Tests / api-required`
- `Web Tests / web-required`
- `E2E Tests / e2e-required`
- `Dependency Review / Dependency Review`
- `Gitleaks / Gitleaks scan`
- `CodeQL`

> **Do not** add `Manifests Lint` as a required check. It is path-filtered at the
> trigger level (`on.pull_request.paths`), so on PRs that don't touch
> `kubernetes/manifests/**` it never runs — a required check that never reports
> would block the merge. The test/e2e pipelines avoid this by triggering on all
> PRs and filtering internally, which is why their `*-required` gates are safe to
> require.

## Local development

Tooling is managed by [mise](https://mise.jdx.dev/) (see `mise.toml`).

```bash
mise install            # one-time tool setup

mise run check          # run all local gates (mirrors CI)
mise run check-api      # just the api quality gate
mise run check-web      # just the web quality gate
mise run lint-workflows # actionlint over .github/workflows
mise run lint-scripts   # shellcheck over scripts/ci
mise run e2e-tests      # spin up k3d + run the e2e suite
```

Or work directly in a service:

```bash
cd apps/study-tracker/api          # or apps/study-tracker/web
uv sync --locked --dev             # install deps
uv run pytest                      # tests + 80% coverage gate (config in pyproject.toml)
uv run ruff check && uv run ruff format --check
```

Commits go through a pre-commit hook that runs `ruff`, `actionlint`,
`shellcheck`, and validates the message against
[Conventional Commits](https://www.conventionalcommits.org/) via commitizen.

## Notes

- Image builds are multi-arch (`linux/amd64`, `linux/arm64`).
- Trivy scan is **blocking** — it fails the PR on fixable CRITICAL/HIGH OS and library findings (`ignore-unfixed` keeps it from blocking on CVEs with no upstream fix).
- Published images are cosign-signed and ship SBOM + provenance attestations.
- Action versions are pinned to major versions (e.g. `@v6`); upgrades are manual until/unless Dependabot version updates are added.
