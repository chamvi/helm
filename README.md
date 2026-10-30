<p align="center">
    <img src="https://raw.githubusercontent.com/chamvi/chamvi/master/.github/assets/logo.svg" alt="chamvi" width="128" height="128" />
</p>

<h1 align="center">chamvi Helm charts</h1>

<p align="center">
    <b>Deploy a chamvi agent app to Kubernetes with one chart and a few values.</b>
</p>

<p align="center">
    <a href="https://github.com/chamvi/helm/actions/workflows/lint-test.yaml"><img src="https://github.com/chamvi/helm/actions/workflows/lint-test.yaml/badge.svg" alt="lint-test" /></a>
    <a href="https://github.com/chamvi/helm/actions/workflows/release.yaml"><img src="https://github.com/chamvi/helm/actions/workflows/release.yaml/badge.svg" alt="release" /></a>
    <a href="https://github.com/chamvi/helm/blob/master/LICENSE"><img src="https://img.shields.io/github/license/chamvi/helm" alt="License" /></a>
</p>

## Charts

| Chart | OCI reference | Deploys |
|---|---|---|
| [`agent-app`](charts/agent-app/README.md) | `oci://ghcr.io/chamvi/helm/agent-app` | one [chamvi](https://github.com/chamvi/chamvi) agent app image: Deployment, Service, optional Ingress, run-job CronJobs, sandbox RBAC and egress policy, ServiceMonitor |

## Install

Application images must use Node.js **24.3.0 or newer** for the current chamvi runtime. Node 22 is no longer supported.
The chart accepts custom images and cannot enforce their Node version; rebuild older images before upgrading chamvi.
The CI fixture declares the same minimum and already uses Node 24 base images.

```sh
helm install triage oci://ghcr.io/chamvi/helm/agent-app --version 0.1.0 -n agents \
    --set image.repository=ghcr.io/acme/triage \
    --set image.tag=main-abc1234-1792540800 \
    --set 'secrets[0]=triage-env'
```

With Flux, point an `OCIRepository` at the chart and a `HelmRelease` at the repository. Both live in the app's namespace,
so the `chartRef` works under helm-controller's `--no-cross-namespace-refs=true` too:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
    name: agent-app
    namespace: agents
spec:
    interval: 1h
    url: oci://ghcr.io/chamvi/helm/agent-app
    ref:
        semver: '>=0.1.0 <0.2.0'
    layerSelector:
        mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
        operation: copy
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
    name: triage
    namespace: agents
spec:
    interval: 10m
    chartRef:
        kind: OCIRepository
        name: agent-app
        namespace: agents
    values:
        image:
            repository: ghcr.io/acme/triage
            tag: main-abc1234-1792540800
        secrets: [triage-env]
```

The [chart README](charts/agent-app/README.md) covers every value, the Secrets an app needs, CronJob mode, sandbox
pods and the shutdown timeline.

## Development

```sh
make test       # helm lint, helm-unittest, contract tests, render matrix, values coverage
make generate   # regenerate the chart README and values.schema.json (pinned docker images)
make ct-lint    # chart-testing lint (pinned docker image)
make fixture    # build the fixture app on the published @chamvi packages and test against it
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [Apache-2.0](LICENSE).
