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

kind's default CNI does not enforce NetworkPolicy on GitHub runners: kindnet's kube-network-policies queues
packets with `queue flags bypass` and accepts them unread. The install job therefore creates the cluster from
`.github/configs/kind.yaml` (no default CNI, pod subnet `192.168.0.0/16`) and installs Calico v3.32.2.
`kind-smoke.sh` starts a target pod listening on TCP 443 and 8080 at a cluster pod IP; a control pod without the
sandbox labels must reach it, and a sandbox-labelled curl pod must reach `https://github.com` and reach neither
port. The API server is no target: on a single-node cluster it is the pod's own node, and NetworkPolicy
implementations do not police pod-to-node traffic. ct 3.15 with Helm 4.3.1 is verified for `ct lint`; `ct install`
on Helm 4 is first exercised by CI (fallback: Helm v3.22.1 for that job).

The Cilium policy is render-tested only (no Cilium cluster in CI); applying it on a real Cilium cluster is a manual check.
