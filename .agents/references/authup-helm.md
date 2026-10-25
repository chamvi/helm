# authup/helm correspondence

Source: `authup/helm` at `552459b` (2026-10-21).

| authup/helm | This repo | Difference |
|---|---|---|
| `Makefile` (`docs`, `schema`, `lint`, `template`, `lint-values-coverage`, `test`) | `Makefile` | same helm-docs v1.14.2 and helm-schema 0.18.1 images; adds `generate`, `drift`, dockerized `ct-lint` (mounts a worktree's git dir), `unittest`, `contract`, `fixture`, `shellcheck`, `actionlint` |
| `.github/configs/{ct.yaml,lintconf.yaml}` | same files | `ct.yaml` points at `charts`, `upgrade: false` until a release exists |
| `scripts/check-values-coverage.py` | same file | default chart `charts/agent-app` |
| `scripts/check-beta64-contract.py` (PyYAML contract over `helm template`) | helm-unittest suites plus `scripts/tests/*.py` | unit suites per template; the Python tests cover what helm-unittest cannot (schema-free renders, duplicate keys, packaging, the fixture image) |
| `.github/workflows/lint-test.yaml` (`lint`, `lint-artifacthub`, `install`) | same jobs plus `fixture` | Helm v4.3.1, helm-unittest, `make drift`, shellcheck, actionlint; `install` builds the fixture image, loads it into kind and runs `scripts/kind-smoke.sh` |
| `.github/workflows/release.yaml` (release-please, ungated hevi publish, `workflow_dispatch`) | same | `azure/setup-helm@v5` with `version: v4.3.1`, `actions/checkout@v7` |
| `release-please-config.json` (root `simple` + chart `helm`, `linked-versions`, `bootstrap-sha`) | same shape | no `bootstrap-sha` yet (added after the first merge) and no `extra-files` |
| Renovate | Dependabot (`github-actions`) | the chamvi org runs Dependabot; the chart pins no images |
| built-in PostgreSQL, MySQL, Valkey | none | the agent app brings `DATABASE_URL` through a Secret |
