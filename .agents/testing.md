# Testing

| Layer | Command | What it covers |
|---|---|---|
| helm-unittest | `make unittest` | one suite per template or concern in `charts/agent-app/tests/`, against `values.schema.json` |
| contract tests | `make contract` | `scripts/tests/*.py`: hostile values without schema (`--skip-schema-validation`), duplicate YAML keys, long names, packaged hook, ci matrix, release wiring, docs |
| fixture | `make fixture` | builds `ci/app` (the published `@chamvi/app`/`@chamvi/cli` on `ghcr.io/chamvi/node:24`) and runs the CronJob args and the approval-link origin against it (`AGENT_APP_CI_IMAGE`) |
| render matrix | `make template` | every `ci/*-values.yaml` and `ci/render/*-values.yaml` with the ServiceMonitor and Cilium APIs |
| lint | `make lint`, `make ct-lint` | `helm lint` per ci file, yamllint, chart-testing (dockerized `quay.io/helmpack/chart-testing:v3.15.0`) |
| coverage | `make lint-values-coverage` | every `.Values.*` path a template reads exists in `values.yaml` |
| drift | `make drift` | regenerated README and schema equal the committed ones |
| kind | CI `install` job | `ct install` of the four ci files (pods Ready, `helm test` on `/readyz`), then `scripts/kind-smoke.sh` |

## helm-unittest

- Every suite sets `release: { name: demo, namespace: agents }` and `values: [values/base.yaml]`.
- `failedTemplate.errorMessage` is an exact match, `errorPattern` a regex; a schema violation reads as a failed template.
- A `path` holding `[` inside a flow mapping must be quoted (`{ path: 'spec.containers[0].image', value: x }`): go-yaml
  refuses `[` in a flow plain scalar and the parse error takes the whole suite down.
- `lengthEqual` counts arrays only; assert a map with `equal` on the whole map.
- Helm 4 verifies plugin signatures: install the plugin with `--verify=false`.

## kind

kind enforces NetworkPolicy with its default CNI since v0.24.0 (kube-network-policies). `kind-smoke.sh` runs a
sandbox-labelled curl pod that must reach `https://github.com` and must not reach `kubernetes.default.svc`; the API
server's ClusterIP and kind's node network both lie inside the default `clusterCIDRs`. Should a kind release stop
enforcing, create the cluster with `disableDefaultCNI: true` and install Calico. ct 3.15 with Helm 4.3.1 is verified for
`ct lint`; `ct install` on Helm 4 is first exercised by CI (fallback: Helm v3.22.1 for that job).

The Cilium policy is render-tested only (no Cilium cluster in CI); applying it on a real Cilium cluster is a manual check.
