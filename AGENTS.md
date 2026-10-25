<!-- NOTE: keep this file and .agents/*.md updated as the project evolves. -->

# chamvi/helm: Agent Guide

Helm charts for [chamvi](https://github.com/chamvi/chamvi), the TypeScript framework for self-hosted, channel-driven AI
agents. One application chart: `charts/agent-app` deploys one agent app image (`chamvi start`) as a Deployment with a
Service, an optional Ingress, optional run-job CronJobs, the RBAC and egress policy for Kubernetes sandbox pods and an
optional ServiceMonitor. Published to `oci://ghcr.io/chamvi/helm/agent-app`.

## Quick Reference

```bash
make test                    # helm lint + yamllint, helm-unittest, contract tests, render matrix, values coverage
make unittest                # helm-unittest suites only (charts/agent-app/tests)
make generate                # make schema docs: values.schema.json (helm-schema) and README.md (helm-docs), dockerized
make drift                   # generate, then fail when the outputs differ from git
make ct-lint                 # chart-testing lint (dockerized)
make fixture                 # build ci/app on the published @chamvi packages, run the contract tests against it
make shellcheck actionlint   # dockerized linters for scripts/kind-smoke.sh and the workflows

helm unittest -f 'tests/deployment_test.yaml' charts/agent-app
helm template test charts/agent-app -f charts/agent-app/ci/sandbox-values.yaml
```

- Helm 4 with the helm-unittest 1.2.1 plugin (`--verify=false`), Python 3 with PyYAML, yamllint, Docker.
- `charts/agent-app/README.md` and `charts/agent-app/values.schema.json` are GENERATED: edit `values.yaml` comments or
  `README.md.gotmpl` and run `make generate`. CI fails on drift.

## Detailed Guides

- **[Structure](.agents/structure.md)**: repo layout, templates, tests
- **[Architecture](.agents/architecture.md)**: the chart invariants and the chamvi contract they encode
- **[Testing](.agents/testing.md)**: helm-unittest, contract tests, render matrix, fixture app, kind install
- **[Conventions](.agents/conventions.md)**: commits, releases, generated files, references

## Commits & Releases

- Conventional Commits with the chart as scope (`feat(agent-app): ...`); repo-level files use no scope or
  `ci:`/`docs:`/`chore:`. release-please owns `Chart.yaml` `version`, `CHANGELOG.md`, the manifest and `version.txt`.
- hevi publishes on every master push once `Chart.yaml` holds an unreleased version: GitHub release
  `agent-app-<version>`, `index.yaml` on `gh-pages`, `oci://ghcr.io/chamvi/helm/agent-app:<version>`.
- Do NOT add `Co-Authored-By: Claude ...` or any AI-attribution trailer to commits, issues or PRs, and no em dashes in
  commits, PR text, docs or comments.

## Cross-referenced projects

The chart encodes facts about the chamvi app (env names, ports, probe paths, sandbox labels, RBAC verbs). Verify them
against the monorepo source before changing them and update `.agents/references/`:
[chamvi](.agents/references/chamvi.md), [authup/helm](.agents/references/authup-helm.md),
[Cilium](.agents/references/cilium.md).
