# Contributing

The [chamvi contributing guide](https://github.com/chamvi/chamvi/blob/master/CONTRIBUTING.md) applies; this repo adds:

1. Conventional Commits with the chart as scope for chart changes (`feat(agent-app): ...`, `fix(agent-app): ...`), no
   scope or `ci:`/`docs:`/`chore:` for repo-level files. release-please owns `Chart.yaml` `version`, `CHANGELOG.md`,
   `.release-please-manifest.json` and `version.txt`: never bump them by hand.
2. `charts/agent-app/README.md` and `charts/agent-app/values.schema.json` are generated. Edit the `values.yaml` comments
   (`# @schema` block first, then the `# --` line) or `README.md.gotmpl`, then run `make generate`. CI fails on drift.
3. Write the failing test first: a helm-unittest suite in `charts/agent-app/tests/` or a contract test in
   `scripts/tests/`.
4. Before pushing: `make test`, `make drift` and `make ct-lint` (docker), plus `make fixture` when `ci/app` changes.

## Local tooling

- Helm 4 with helm-unittest 1.2.1 (`helm plugin install --verify=false https://github.com/helm-unittest/helm-unittest/releases/download/v1.2.1/unittest-1.2.1.tgz`)
- Python 3 with PyYAML, yamllint
- Docker (helm-docs, helm-schema, chart-testing, shellcheck and actionlint run from pinned images)
