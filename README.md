# cicd-workflow

![API tests](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/study-tracker-api-tests.yaml/badge.svg)
![Web tests](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/study-tracker-web-tests.yaml/badge.svg)
![Release Please](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/release-please.yaml/badge.svg)
![Build & Push](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/docker-build-push.yaml/badge.svg)
![Dependency Review](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/dependency-review.yaml/badge.svg)
![Gitleaks](https://github.com/RamonCollazo/cicd-workflow/actions/workflows/gitleaks.yaml/badge.svg)

Repo for CI/CD workflow learning project. Houses two Python apps under `apps/study-tracker/` (FastAPI `api`, Flask `web`) wired up to a full GitHub-Actions pipeline.

## Pipeline overview

- **PR opened/updated** — for each touched app, a reusable test workflow runs lint (ruff), tests (pytest, ≥ 80% coverage), Docker build, and a Trivy scan (advisory, non-blocking). A `tests-required` aggregator job is the stable signal for branch protection. `Dependency Review` and `Gitleaks` also run on every PR.
- **Push to `main`** — `Gitleaks` re-runs across full history. `release-please` opens (or updates) a per-component release PR (`study-tracker-api`, `study-tracker-web`).
- **Release PR merged** — release-please cuts a per-component tag (`study-tracker-api-vX.Y.Z` or `study-tracker-web-vX.Y.Z`).
- **Tag pushed** — `docker-build-push` builds the affected app and pushes to GHCR with build cache (linux/amd64 only):
  - `ghcr.io/RamonCollazo/study-tracker-api:vX.Y.Z` and `:latest`
  - `ghcr.io/RamonCollazo/study-tracker-web:vX.Y.Z` and `:latest`

## Repo-managed security features

The following are enabled via repo settings rather than committed workflow files:

- **CodeQL** — default setup, scans Python on PRs, pushes to `main`, and on a schedule. Findings: Security → Code scanning.
- **Dependabot security updates** — opens PRs only when a published CVE matches a dep in your tree. (Routine version-update PRs intentionally not configured.)

## Branch protection

Required status checks on `main` (configure in Settings → Rules → Rulesets):

- `Study Tracker API Tests / tests-required`
- `Study Tracker Web Tests / tests-required`
- `Dependency Review / Dependency Review`
- `Gitleaks / Gitleaks scan`
- `CodeQL`

## Local development

Tooling is managed by [mise](https://mise.jdx.dev/) (see `mise.toml`).

```bash
mise install                                # one-time tool setup
cd apps/study-tracker/api                   # or apps/study-tracker/web
uv sync --locked --dev                      # install deps
uv run pytest                               # tests + 80% coverage gate (config in pyproject.toml)
uv run ruff check && uv run ruff format --check
```

Commits go through a pre-commit hook that runs `ruff` and validates the message against [Conventional Commits](https://www.conventionalcommits.org/) via commitizen.

## Notes

- Image builds are linux/amd64 only.
- Trivy scan is advisory; it surfaces CRITICAL/HIGH OS and library findings but does not fail the PR.
- Action versions are pinned to major versions (e.g. `@v6`); upgrades are manual until/unless Dependabot version updates are added.
