# Conventions

## Commits & versioning

- Conventional Commits, scope `agent-app` for chart changes (`feat(agent-app): ...`), no scope or `ci:`/`docs:`/
  `chore:`/`build:`/`test:` for repo-level files. Pre-1.0: `feat` and `fix` bump the patch, a breaking change the minor.
- release-please owns `Chart.yaml` `version`, `CHANGELOG.md`, `.release-please-manifest.json` and `version.txt`.
- No AI-attribution trailers or lines in commits, issues or PRs. No em dashes in commits, PR text, docs or comments.
- Breaking value changes: a fail-loud tripwire for the old key in `templates/validations.yaml` plus a migration note.

## Releases & publishing

- `tada5hi/hevi@v2` (>= v2.0.2) packages every chart on every master push and publishes a version that has no release
  yet: GitHub release `agent-app-<version>`, `index.yaml` on the `gh-pages` branch (must exist), OCI push to
  `ghcr.io/chamvi/helm`. The job is ungated on release-please outputs (the chart sets `skip-github-release`, so they
  never report it) and idempotent; `workflow_dispatch` is the recovery path.
- **Bootstrap.** The first merge publishes `agent-app-0.1.0` straight from master while release-please, on the same push,
  sees `feat(agent-app)` commits and no release tag and would open a 0.1.1 release PR. The first PR after that merge
  (owner's go) is `chore(agent-app): pin release-please bootstrap`, setting `"bootstrap-sha"` in
  `release-please-config.json` to the chart PR's squash-merge commit, as authup/helm did; close an already opened
  0.1.1 release PR. The pin goes inert once a `root-<version>` release exists.
- The OCI package is flipped to public in the GitHub UI after the first publish.

## Generated files

- `charts/agent-app/README.md` (helm-docs v1.14.2) and `charts/agent-app/values.schema.json` (dadav/helm-schema 0.18.1)
  are compiler output: `make generate`, then commit. CI runs `make drift`.
- Comment layout per value: the optional `# @schema ... # @schema` block first, then the `# --` helm-docs line, directly
  above the key (the other order leaks the schema block into the README).
- Every value has a `# --` line; every non-scalar value a `# @schema` block.

## Dependencies

- Dependabot (`github-actions` only); the chart pins no images in `values.yaml`.
- Tool images are pinned in the `Makefile` (helm-docs, helm-schema, chart-testing, shellcheck, actionlint) and the
  workflows (Helm v4.3.1, helm-unittest 1.2.1, PyYAML, yamllint, artifacthub `ah`).

## References

External project mappings live in `.agents/references/`, one file per project; record the source path, this repo's
counterpart and any behavioural difference whenever you consult one:

- [chamvi.md](references/chamvi.md): the chamvi monorepo (the app contract the chart encodes)
- [authup-helm.md](references/authup-helm.md): authup/helm (repo tooling template)
- [cilium.md](references/cilium.md): Cilium policy docs behind `sandbox-ciliumnetworkpolicy.yaml`
