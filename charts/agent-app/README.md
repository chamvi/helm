# agent-app

![Version](https://img.shields.io/badge/Version-0.1.2?style=flat-square&color=informational) <!-- x-release-please-version -->
![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square)

Deploys a chamvi agent app (one image running `chamvi start`), with optional run-job CronJobs and the RBAC and egress policy for Kubernetes sandbox pods.

One image, one Deployment: the chart runs a [chamvi](https://github.com/chamvi/chamvi) agent app built with `chamvi build`
(or an entry-less app loading `agents/` folders) behind a Service, with an optional Ingress, optional run-job CronJobs,
the RBAC and egress policy for Kubernetes sandbox pods, and an optional ServiceMonitor.

## Model settings

With chamvi 0.3.1 or newer, agents without their own model inherit the app-wide default. Named providers allow separate keys and endpoints:

```yaml
model: team-a/claude-sonnet-5-5
providers:
    team-a:
        type: anthropic
        apiKey: { secretName: model-credentials, key: api-key }
        headers:
            x-team: { value: platform }
            authorization:
                valueFrom:
                    secretKeyRef: { name: model-credentials, key: authorization }
```

API keys and credential headers are Secret references only. Provider keys may also come from `secrets` (envFrom), so a provider need not declare `apiKey`. An `openai-compatible` provider requires `baseURL` and its SDK provider package in the application image. `model` renders `CHAMVI_MODEL`; provider names and header names map to upper-case env segments with hyphens replaced by underscores. Explicit chart-generated names cannot also appear in `env`.

No config-file volume or remote-agent configuration is created. Use the existing generic env and Secret mechanisms for advanced app settings. The readiness test hook receives none of these model credentials.

## Install

<!-- x-release-please-start-version -->
```sh
helm install triage oci://ghcr.io/chamvi/helm/agent-app --version 0.1.2 -n agents -f values.yaml
```
<!-- x-release-please-end -->

The smallest values file names the agent image and the Secret holding its credentials:

```yaml
image:
    repository: ghcr.io/acme/triage
    tag: main-abc1234-1792540800
secrets: [triage-env]
```

### Flux

The chart is a public OCI artifact, so the `OCIRepository` needs no `secretRef`. It lives next to the `HelmRelease` in
the app's namespace, so the `chartRef` works under helm-controller's `--no-cross-namespace-refs=true` too:

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
        semver: '0.1.x'
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
            repository: ghcr.io/acme/triage # {"$imagepolicy": "flux-system:triage:name"}
            tag: main-abc1234-1792540800 # {"$imagepolicy": "flux-system:triage:tag"}
            digest: ''
        imagePullSecrets: []
        replicas: 1
        command: [node, node_modules/@chamvi/cli/dist/cli.mjs]
        basePath: ''
        env: {}
        secrets: [triage-env]
        ingress: { enabled: true, className: '', host: agents.example.com, tls: { secretName: agents-tls } }
        sandbox: { enabled: false }
        cronJobs: []
        serviceMonitor: { enabled: false }
        resources: {}
```

## The app and its image

The image is the agent repository's own (stage 2 `FROM ghcr.io/chamvi/node:24`, workdir `/app`, user 1000,
`ENTRYPOINT ["/usr/bin/tini", "--"]`). The value `command` renders into the container **args**, never `command:`,
so tini stays PID 1: the Deployment runs `command + ["start"]`, each CronJob `command + ["run-job", agent, subscription]`.
The CLI loads `dist/index.mjs`, or, without an entry, builds the default app from the `agents/` folder
(`CHAMVI_AGENTS_DIR`, relative to `/app`); either way the agents ship inside the image.

### Approved skills (optional)

Adoption requires a chamvi release exporting `gitSkills` and `loadSkillBundle` from `@chamvi/skills`.
Install `@chamvi/skills` as an application runtime dependency, using a compatible released version.
`gitSkills` comes from the main entry, with no `/module` entry or app helper imports. The factory does no I/O;
startup installs and verifies required sources. Configure reviewed sources in app code:

```ts
import { createApp, defineAgent } from '@chamvi/app';
import { gitSkills } from '@chamvi/skills';

// These source/full-commit values and name/version/sha256 arrays are reviewed app configuration.
const common = gitSkills({
    source: reviewedSource,
    revision: reviewedFullCommit,
    directory: '/tmp/chamvi-skills/common',
    approved: reviewedCommonPins,
});
const extras = gitSkills({
    source: reviewedSource,
    revision: reviewedFullCommit,
    directory: '/tmp/chamvi-skills/maintainer',
    approved: reviewedMaintainerPins,
});
const maintainer = defineAgent({
    name: 'maintainer', instructions: 'Maintain the approved repository.', skills: [extras],
});
export default createApp({ agents: [maintainer], skills: [common], model: configuredModel });
```

App defaults apply to every code/folder agent; agent skills add extras. Direct `Engine({ skills })` accepts the same
inputs. Chamvi appends metadata and supplies a scoped `load_skill` automatically. Computing a digest with
`hashSkillBundle` is a review aid, never approval; pin both a full source commit and independently reviewed content.
Failed verification aborts startup before channels, HTTP or model work, including on `run-job`. Globals/code sources
prepare before `engineCreated`; folder-agent extras prepare later, before serving. `chamvi start --check` remains a
static skill check: it does not load skill providers, install sources or verify remote bytes/availability.

Runtime Git preparation requires Node >=22.20 and Git. The unchanged `ghcr.io/chamvi/node:24` base has no Git;
add it in the application's runtime image, preserving the final uid 1000 (insert after the existing pinned `FROM`):

```dockerfile
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
USER 1000:1000
# Keep the existing runtime COPY, EXPOSE and CMD instructions.
```

Both Deployment and CronJobs run uid/gid 1000 with a read-only root and a writable `/tmp` emptyDir.
Use distinct absolute managed corpora such as `/tmp/chamvi-skills/common` and `/tmp/chamvi-skills/maintainer`;
`/app` cannot be a startup destination. No new chart mount, value or RBAC is needed. Each pod/job prepares its own
corpus; a container restart may retain the emptyDir, but startup still re-verifies the configured source and pins.

Source fetching happens in the application pod. Supply working source credentials and network access there and in
every CronJob. `secrets` supplies envFrom, but a generic token variable alone does not configure the clone SDK's
credential flow. `sandbox.networkPolicy` and sandbox FQDN policy select sandbox pods only; external app egress
policies must allow DNS and the configured source/auth endpoints. Budget startup fetch/verification time in the
[probes](#probes-and-shutdown). Stop joins owned cleanup and can wait for a clone that ignores cancellation.

Ready snapshots remain an alternative: copy approved passive bundles into the runtime image, readable by uid 1000,
and pass `loadSkillBundle({ name, version, sha256, directory: '/app/approved-skills/audit' })` in `skills`.
The starter image copies JS/dependencies only, so add an explicit final-stage asset `COPY`. Manual
`loadSkillBundles` catalogs remain supported with explicit instruction/tool composition. The chart does not approve
content or grant tool permissions.

Upgrade reviewed source commits/content pins together. Saved load results keep their original checkpoint bytes;
pending/future loads use the new verified snapshot. Global pin changes do not change folder revisions: finish or
cancel unsettled runs first if mixed-version disclosure is unacceptable. External bundle directories are not watched;
changed bytes under an old pin fail verification after restart. See [approved skills](https://chamvi.dev/guide/skills).

## Secrets and env

`secrets` names existing Secrets; each becomes an `envFrom` `secretRef` on the Deployment and the CronJobs
(the helm test pod gets none). The chart creates no Secret: create them with SOPS or External Secrets. Typical keys:

| Variable | When |
|---|---|
| `DATABASE_URL` | a shared PostgreSQL store: more than one replica, any `cronJobs`, runs that survive a restart |
| `CHAMVI_TOKENS` | static API tokens (`[{"value", "id", "permissions"}]`), unless another authenticator is configured |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `MISTRAL_API_KEY`, `XAI_API_KEY` | an agent's `'<provider>/<model>'` model string (or the default `CHAMVI_MODEL`) names that implicit provider |
| `CHAMVI_PROVIDER_<NAME>_API_KEY` | a provider declared by name (with `CHAMVI_PROVIDER_<NAME>_TYPE` and `_BASE_URL` in `env`); it replaces the implicit provider of the same name |
| `CHAMVI_GIT_TOKENS` | git tokens for sandbox checkouts and pushes (`[{"host", "path"?, "username"?, "token"}]`) |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` | `githubModule()` |
| `OPENCLAW_HOOKS_TOKEN` (with `OPENCLAW_BASE_URL`, `OPENCLAW_CHANNEL`, `OPENCLAW_TO`) | `openclawModule()` |
| `AUTHUP_CLIENT_SECRET` (with `AUTHUP_URL`, `AUTHUP_CLIENT_ID`) | `authupModule()` |

`env` holds plain, non-secret values (`CHAMVI_LOG_LEVEL`, `CHAMVI_MAX_CONCURRENT_RUNS`, `CHAMVI_MODEL`, `CHAMVI_SANDBOX_PROVIDER`, ...),
rendered in name order after the variables the chart owns. The chart refuses an `env` entry that names one of its own:

| Variable | Value | When |
|---|---|---|
| `PORT` | `3000` | always |
| `CHAMVI_BASE_PATH` | `basePath` | always |
| `CHAMVI_SCHEDULER` | `false` | `cronJobs` is not empty |
| `CHAMVI_SANDBOX_NAMESPACE` | `sandbox.namespace` | `sandbox.enabled` |
| `CHAMVI_PUBLIC_URL` | `https://<ingress.host>` with `tls.secretName`, else `http://<ingress.host>` | `ingress.enabled` and no `env.CHAMVI_PUBLIC_URL` (yours wins) |
| `CHAMVI_DEPLOYMENT` | the release's full name (`<release>-agent-app`, or `fullnameOverride`) | `sandbox.enabled` and no `env.CHAMVI_DEPLOYMENT` (yours wins) |

The app listens on `HOST` `0.0.0.0` (IPv4 only). On an IPv6-only cluster (EKS IPv6 mode) set `env.HOST: "::"`, which
listens dual-stack where the node kernel has IPv6; the chart refuses any other `HOST`, since the kubelet probes the pod
address.

The derived `CHAMVI_PUBLIC_URL` is the origin only: the app appends `basePath` once when it builds approval links
(`<origin><basePath>/ui/approvals?run=<id>&approval=<id>`, ids only, never a credential). When TLS terminates outside
the Ingress (a load balancer, a default certificate), set `env.CHAMVI_PUBLIC_URL` to the `https://` origin.

## HTTP

One container port, `3000` named `http`; the Service maps `service.port` (80) to it. Every path lives under `basePath`
(`""`, or lower-case `/segment` paths without a trailing slash, the app's own rule): `/healthz`, `/readyz`, `/metrics`,
`/ui` (with `uiModule()`), the GitHub App webhook at `<basePath>/channels/github` (with `githubModule()`) and generic
webhooks at `<basePath>/channels/webhook/<agent><path>`. The Ingress routes `<basePath>` (or `/`) with `pathType: Prefix`.

## Probes and shutdown

| | Path | Period | Failures |
|---|---|---|---|
| startup | `<basePath>/healthz` | 2 s | 60 (120 s for startup) |
| liveness | `<basePath>/healthz` | 10 s | 3 |
| readiness | `<basePath>/readyz` | 5 s | 2 |

Required skill preparation finishes before HTTP starts, so `/healthz` stays unavailable while sources are fetched
and verified. Budget migrations plus source fetch and verification from measured latency. For example, these
existing values allow approximately 300 seconds (CronJobs have no HTTP probe but still prepare skills):

```yaml
probes:
    startup:
        periodSeconds: 2
        timeoutSeconds: 2
        failureThreshold: 150
```

On termination the pod sleeps `preStopSleepSeconds` (5, the native `sleep` action) so the endpoints drop it, then the
CLI gets SIGTERM: readiness 503, channels stopped, HTTP closed, runs drained (30 s), the store closed. The CLI exits
by force `CHAMVI_FORCE_EXIT_MS` (90 s) after the signal and the kubelet kills at `terminationGracePeriodSeconds` (120).
The chart refuses a render where `preStopSleepSeconds * 1000 + CHAMVI_FORCE_EXIT_MS >= terminationGracePeriodSeconds * 1000`.
It reads `env.CHAMVI_FORCE_EXIT_MS` only: a value set through a Secret escapes the check.
Skill preparation owns its clone/cleanup work; cancellation can wait for clone settlement before drain.
The CLI force-exit and pod grace period remain the operator bounds, so allow for this work when sizing them.

## CronJob mode

```yaml
cronJobs:
    - name: digest
      schedule: '0 7 * * *'
      timeZone: Europe/Berlin
      agent: digest
      subscription: 'cron:0 7 * * *'
```

Each entry fires one `cron.on()` subscription of an agent through `chamvi run-job <agent> [subscription]`. The
`subscription` id defaults to `cron:<expression>` (spaces included; it stays one argv element) and may be left out for
an agent with exactly one cron subscription. Any entry sets `CHAMVI_SCHEDULER=false` on the Deployment, whose cron
channel then validates but never fires, so give **every** cron subscription an entry with the same schedule.
The Jobs need the Deployment's store: put a PostgreSQL `DATABASE_URL` in a Secret.

CronJobs use `concurrencyPolicy: Forbid`, `restartPolicy: Never` and `backoffLimit: 0`: a retried Job would fire at a
new time, get a new `<subscription>@<time>` idempotency key and start a duplicate run. `cronJob.resources` overrides the
Deployment's `resources` (empty inherits them).

Since chamvi 0.3.0 a Job never reloads an agent folder. When the folder changed and the store still has unsettled
runs of that agent at the older revision, the Job does not register the agent and exits 1 (`invalid_run_state`),
leaving the runs alone; the Deployment applies the change, after which the Jobs run again. Roll the Deployment before
the CronJobs pick up a changed folder; a CronJob-only install with unsettled runs never applies one. Code agents are
not affected.

## Sandbox pods

With `sandbox.enabled` the app may run `@chamvi/sandbox-k8s` workspaces in `sandbox.namespace`. Select the provider in
the app (`env.CHAMVI_SANDBOX_PROVIDER: kubernetes` or `sandboxModule({ provider: 'kubernetes' })`); the chart sets
`CHAMVI_SANDBOX_NAMESPACE`.

- Sandbox env for `env`: `CHAMVI_SANDBOX_IMAGE` (default `ghcr.io/chamvi/sandbox-dev:trixie`; `sandbox-node` is
  deprecated, pin a digest in production), `CHAMVI_SANDBOX_IMAGES` (the images the model may pick, a comma list),
  `CHAMVI_GIT_CREDENTIAL_MODE`. `CHAMVI_GIT_TOKENS` belongs in a Secret.
- The chart sets `CHAMVI_DEPLOYMENT` (the workspaces' `chamvi.dev/deployment` label) to the release's full name, so
  releases sharing a sandbox namespace never see each other's workspaces, and the app removes workspaces of runs its
  store no longer knows (under chamvi's `default` they wait for their 7 day lifetime). Workspaces created under another
  value (`default`, before the chart set it) are no longer found by the app: a waiting run gets a fresh workspace, and the old
  pods stop at their deadline. Set `env.CHAMVI_DEPLOYMENT` to keep a value, e.g. `default` across this upgrade.
- Create the namespace first, apart from the release namespace (the chart refuses the same one), and label it for
  Pod Security `baseline`: since chamvi 027 workspace pods run as root with a writable root filesystem and a few added
  capabilities, so `apt` and toolchain installs work. The provider's `user` and `readOnlyRoot` options restore a pod
  that `restricted` admits.
- A `Role` there grants `pods` `create`, `get`, `list`, `delete` and `pods/exec` `get`, `create`; a `RoleBinding`
  binds the app's ServiceAccount (release namespace). The app and job pods mount its token only with
  `sandbox.enabled`; the helm test pod never does, and the provider's sandbox pods mount none.
- The egress policy selects pods labelled `app.kubernetes.io/managed-by: chamvi` and `app.kubernetes.io/component: sandbox`
  (the app pod is `component: app`). The portable `NetworkPolicy` denies all ingress and allows DNS to the pods of
  `networkPolicy.dns` (kube-dns by default, selected by any labels; NodeLocal DNSCache runs on the host network, so add
  its address to `networkPolicy.dns.ipBlocks`, e.g. `169.254.20.10/32`) plus the TCP `networkPolicy.ports` (443 and
  80 by default) to every address outside
  `networkPolicy.clusterCIDRs` and `169.254.169.254/32` (IPv6: outside `networkPolicy.clusterCIDRsIPv6`, default
  `fc00::/7`, `fe80::/10`). Both lists must hold at least one range.
- Limits of the portable policy: it needs an enforcing CNI, cannot name hosts, and how `ipBlock` treats pod and service
  addresses is CNI-defined. Most CNIs evaluate egress after service translation, so a managed cluster's public API
  endpoint is not covered by private ranges; sandbox pods mount no token, which leaves anonymous access only. List every
  pod, service and node range of your cluster in `clusterCIDRs`; on IPv6 or dual-stack clusters with globally routable
  pod or node addresses (EKS IPv6 mode, GKE external IPv6), add those ranges to `clusterCIDRsIPv6` too.
- `networkPolicy.cilium.enabled` renders a `CiliumNetworkPolicy` **instead of** the portable policy (policies are
  allow-lists whose union applies, so both together would void the FQDN list): deny-all ingress, the DNS proxy rule
  and the TCP `networkPolicy.ports` to `cilium.fqdns` only. The render fails when the cluster serves no `cilium.io/v2`
  API.
- Port 80 is there for Debian's default apt sources, which `sandbox-dev` keeps: they are plain HTTP (apt checks the
  package signatures). The default `cilium.fqdns` cover GitHub (also its release downloads), npm, `deb.debian.org` and
  mise (`mise.jdx.dev`, `mise-versions.jdx.dev`, `nodejs.org` for node); add the other registries and toolchain hosts
  your workspaces install from. `networkPolicy.ports: [443]` drops plain HTTP.

## Monitoring and tests

`serviceMonitor.enabled` renders a `monitoring.coreos.com/v1` ServiceMonitor (port `http`, path `<basePath>/metrics`)
when the cluster serves that API and skips it otherwise. `helm test` runs a pod with the app image's own `node` that
fetches `<basePath>/readyz` through the Service (`tests.enabled`).

## Security

Every pod runs as uid and gid 1000 (`runAsNonRoot`, `fsGroup: 1000`, seccomp `RuntimeDefault`) with a read-only root
filesystem, no privilege escalation, every capability dropped and an `emptyDir` at `/tmp`: the Pod Security
`restricted` profile. `imagePullSecrets` stays empty for public images; a private agent image names its pull Secret there.

## Requirements

Kubernetes: `>=1.30.0-0`

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | Kubernetes scheduling affinity. |
| basePath | string | `""` | HTTP prefix, empty or lower-case /segment paths without a trailing slash. |
| command | list | `["node","node_modules/@chamvi/cli/dist/cli.mjs"]` | CLI prefix. Rendered as the container args (never `command:`), so the image's tini entrypoint stays PID 1: the Deployment runs `command + [start]`, a CronJob `command + [run-job, agent, subscription]`. |
| cronJob | object | `{"activeDeadlineSeconds":0,"failedJobsHistoryLimit":3,"resources":{},"startingDeadlineSeconds":300,"successfulJobsHistoryLimit":3}` | Defaults shared by every run-job CronJob. |
| cronJob.activeDeadlineSeconds | int | `0` | Job lifetime limit; zero leaves it unset. |
| cronJob.failedJobsHistoryLimit | int | `3` | Failed Jobs retained. |
| cronJob.resources | object | `{}` | Job resources; empty inherits application resources. |
| cronJob.startingDeadlineSeconds | int | `300` | Deadline for starting a missed schedule. |
| cronJob.successfulJobsHistoryLimit | int | `3` | Completed Jobs retained. |
| cronJobs | list | `[]` | run-job CronJobs, one per agent `cron.on()` subscription (`name`, `schedule`, `agent`, optional `subscription` id such as `cron:0 7 * * *`, `timeZone`, `suspend`). Any entry sets `CHAMVI_SCHEDULER=false` on the Deployment, so mirror every cron subscription. |
| env | object | `{}` | Plain environment values, never credentials; use secrets for sensitive values. |
| fullnameOverride | string | `""` | Override the resource name (DNS label starting with a letter, at most 63 characters). |
| global | object | `{}` | Free-form umbrella chart values. |
| image | object | `{"digest":"","pullPolicy":"IfNotPresent","repository":"","tag":""}` | Agent application image; no default application is supplied. |
| image.digest | string | `""` | Optional sha256 digest, preferred over the tag. |
| image.pullPolicy | string | `"IfNotPresent"` | Image pull policy. |
| image.repository | string | `""` | Required application image repository. |
| image.tag | string | `""` | Required image tag unless digest is set. Quote numeric tags. |
| imagePullSecrets | list | `[]` | Existing registry credentials for private agent images only. |
| ingress | object | `{"annotations":{},"className":"","enabled":false,"host":"","tls":{"secretName":""}}` | Optional Ingress and public URL derivation. |
| ingress.annotations | object | `{}` | Ingress controller annotations. |
| ingress.className | string | `""` | Ingress class name. |
| ingress.enabled | bool | `false` | Create an Ingress. |
| ingress.host | string | `""` | Concrete DNS host, required when ingress is enabled. |
| ingress.tls | object | `{"secretName":""}` | TLS settings. |
| ingress.tls.secretName | string | `""` | TLS Secret name; enables HTTPS origin derivation. |
| model | string | `""` | App-wide default model, provider/model-id. Empty keeps the app's code default. |
| nameOverride | string | `""` | Override the chart name (DNS label, at most 63 characters). |
| nodeSelector | object | `{}` | Node selector for application and job pods. |
| podAnnotations | object | `{}` | Annotations for application and job pods. |
| podLabels | object | `{}` | Extra pod labels; chart labels and the cron-job label are reserved. |
| preStopSleepSeconds | int | `5` | Native preStop sleep on the Deployment; zero omits the lifecycle. |
| probes | object | `{"liveness":{"failureThreshold":3,"periodSeconds":10,"timeoutSeconds":2},"readiness":{"failureThreshold":2,"periodSeconds":5,"timeoutSeconds":2},"startup":{"failureThreshold":60,"periodSeconds":2,"timeoutSeconds":2}}` | HTTP probes share the basePath and named http port. |
| probes.liveness | object | `{"failureThreshold":3,"periodSeconds":10,"timeoutSeconds":2}` | Liveness HTTP probe timings; additional Kubernetes timing fields are accepted. |
| probes.liveness.failureThreshold | int | `3` | Consecutive failures before restarting the container. |
| probes.liveness.periodSeconds | int | `10` | Seconds between liveness checks. |
| probes.liveness.timeoutSeconds | int | `2` | Liveness request timeout in seconds. |
| probes.readiness | object | `{"failureThreshold":2,"periodSeconds":5,"timeoutSeconds":2}` | Readiness HTTP probe timings; additional Kubernetes timing fields are accepted. |
| probes.readiness.failureThreshold | int | `2` | Consecutive failures before removing the pod from endpoints. |
| probes.readiness.periodSeconds | int | `5` | Seconds between readiness checks. |
| probes.readiness.timeoutSeconds | int | `2` | Readiness request timeout in seconds. |
| probes.startup | object | `{"failureThreshold":60,"periodSeconds":2,"timeoutSeconds":2}` | Startup HTTP probe timings; additional Kubernetes timing fields are accepted. |
| probes.startup.failureThreshold | int | `60` | Consecutive failures allowed during initialization. |
| probes.startup.periodSeconds | int | `2` | Seconds between startup checks. |
| probes.startup.timeoutSeconds | int | `2` | Startup request timeout in seconds. |
| providers | object | `{}` | Named model providers. API keys use {secretName, key}; headers use {value} or {valueFrom: {secretKeyRef: {name, key}}}. |
| replicas | int | `1` | Application replicas; more than one requires a shared database. |
| resources | object | `{}` | Application resource requests and limits. |
| sandbox | object | `{"enabled":false,"namespace":"","networkPolicy":{"cilium":{"enabled":false,"fqdns":["github.com","*.github.com","*.githubusercontent.com","registry.npmjs.org","deb.debian.org","mise.jdx.dev","mise-versions.jdx.dev","nodejs.org"]},"clusterCIDRs":["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16","100.64.0.0/10"],"clusterCIDRsIPv6":["fc00::/7","fe80::/10"],"dns":{"ipBlocks":[],"namespaceSelector":{"kubernetes.io/metadata.name":"kube-system"},"podSelector":{"k8s-app":"kube-dns"}},"enabled":true,"ports":[443,80]}}` | Kubernetes sandbox pods (the chamvi sandbox-k8s provider): a Role and RoleBinding in `sandbox.namespace`, the egress policy, and `CHAMVI_SANDBOX_NAMESPACE` on the app. |
| sandbox.enabled | bool | `false` | Grant the app's ServiceAccount the sandbox Role and mount its token. Select the provider in the app (`env.CHAMVI_SANDBOX_PROVIDER: kubernetes` or the module option). |
| sandbox.namespace | string | `""` | Namespace of the sandbox pods; must exist and differ from the release namespace. |
| sandbox.networkPolicy | object | `{"cilium":{"enabled":false,"fqdns":["github.com","*.github.com","*.githubusercontent.com","registry.npmjs.org","deb.debian.org","mise.jdx.dev","mise-versions.jdx.dev","nodejs.org"]},"clusterCIDRs":["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16","100.64.0.0/10"],"clusterCIDRsIPv6":["fc00::/7","fe80::/10"],"dns":{"ipBlocks":[],"namespaceSelector":{"kubernetes.io/metadata.name":"kube-system"},"podSelector":{"k8s-app":"kube-dns"}},"enabled":true,"ports":[443,80]}` | Sandbox egress controls. |
| sandbox.networkPolicy.cilium | object | `{"enabled":false,"fqdns":["github.com","*.github.com","*.githubusercontent.com","registry.npmjs.org","deb.debian.org","mise.jdx.dev","mise-versions.jdx.dev","nodejs.org"]}` | Optional Cilium replacement policy. |
| sandbox.networkPolicy.cilium.enabled | bool | `false` | Use FQDN policy instead of the portable NetworkPolicy. |
| sandbox.networkPolicy.cilium.fqdns | list | `["github.com","*.github.com","*.githubusercontent.com","registry.npmjs.org","deb.debian.org","mise.jdx.dev","mise-versions.jdx.dev","nodejs.org"]` | Allowed DNS names and patterns (on `networkPolicy.ports`): GitHub, npm, Debian's apt sources and mise with its default node downloads. |
| sandbox.networkPolicy.clusterCIDRs | list | `["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16","100.64.0.0/10"]` | IPv4 cluster CIDRs (pod, service and node ranges) excluded from portable public egress; at least one. |
| sandbox.networkPolicy.clusterCIDRsIPv6 | list | `["fc00::/7","fe80::/10"]` | IPv6 cluster CIDRs excluded from portable public egress; add globally routable pod, service and node ranges (EKS IPv6, dual-stack); at least one. |
| sandbox.networkPolicy.dns | object | `{"ipBlocks":[],"namespaceSelector":{"kubernetes.io/metadata.name":"kube-system"},"podSelector":{"k8s-app":"kube-dns"}}` | Selectors of DNS pods reachable by sandboxes. |
| sandbox.networkPolicy.dns.ipBlocks | list | `[]` | Extra DNS server CIDRs for the portable policy, e.g. NodeLocal DNSCache's `169.254.20.10/32` (a hostNetwork DaemonSet no pod selector matches). |
| sandbox.networkPolicy.dns.namespaceSelector | object | `{"kubernetes.io/metadata.name":"kube-system"}` | DNS namespace labels. |
| sandbox.networkPolicy.dns.podSelector | object | `{"k8s-app":"kube-dns"}` | DNS pod labels. |
| sandbox.networkPolicy.enabled | bool | `true` | Create sandbox policy resources when sandbox is enabled. |
| sandbox.networkPolicy.ports | list | `[443,80]` | TCP ports sandboxes may reach on public addresses (portable policy) or on `cilium.fqdns` (Cilium). 80 is for Debian's apt sources, which are plain HTTP (apt checks signatures). |
| secrets | list | `[]` | Existing Secret names, each mounted through envFrom on every pod (DATABASE_URL, CHAMVI_TOKENS, provider API keys, GITHUB_*); this chart creates no Secret. |
| service | object | `{"annotations":{},"port":80,"type":"ClusterIP"}` | Application Service settings. |
| service.annotations | object | `{}` | Service annotations. |
| service.port | int | `80` | Service port, targeting the named http container port. |
| service.type | string | `"ClusterIP"` | Service type. |
| serviceAccount | object | `{"annotations":{},"create":true,"name":""}` | Application ServiceAccount settings. |
| serviceAccount.annotations | object | `{}` | ServiceAccount annotations. |
| serviceAccount.create | bool | `true` | Create a dedicated ServiceAccount. |
| serviceAccount.name | string | `""` | Existing or custom ServiceAccount name; empty chooses the release name or default. |
| serviceMonitor | object | `{"enabled":false,"interval":"","labels":{},"scrapeTimeout":""}` | Optional Prometheus monitoring integration. |
| serviceMonitor.enabled | bool | `false` | Create a ServiceMonitor when its API is available. |
| serviceMonitor.interval | string | `""` | Prometheus scrape interval; empty uses its default. |
| serviceMonitor.labels | object | `{}` | Additional ServiceMonitor labels. |
| serviceMonitor.scrapeTimeout | string | `""` | Prometheus scrape timeout; empty uses its default. |
| strategy | object | `{"type":"Recreate"}` | Deployment strategy; RollingUpdate may set rollingUpdate options. |
| strategy.type | string | `"Recreate"` | Recreate by default; RollingUpdate supports rollingUpdate options. |
| terminationGracePeriodSeconds | int | `120` | Pod shutdown grace; must exceed preStop plus CLI force-exit timeout. |
| tests | object | `{"enabled":true}` | Enable the Helm readiness test hook. |
| tests.enabled | bool | `true` | Render the helm test pod that fetches `<basePath>/readyz` through the Service. |
| tolerations | list | `[]` | Kubernetes tolerations. |
