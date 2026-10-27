# Architecture

`charts/agent-app` deploys any chamvi agent app image; it has no `appVersion` (the image tag is the app version).
The rules below are load-bearing. Each has a helm-unittest suite or a contract test; change the test first.

## Invariants

1. **args, never command.** The value `command` (default `[node, node_modules/@chamvi/cli/dist/cli.mjs]`) renders into
   the container `args`, so the image's `ENTRYPOINT ["/usr/bin/tini", "--"]` stays PID 1. Deployment args
   `command + [start]`, CronJob args `command + [run-job, <agent>, <subscription>?]`, the helm test pod
   `[node, -e, <fetch of /readyz>]`. No shell in any rendered command.
2. **Owned env names.** The chart renders `PORT=3000`, `CHAMVI_BASE_PATH`, `CHAMVI_SCHEDULER=false` (with `cronJobs`),
   `CHAMVI_SANDBOX_NAMESPACE` (with `sandbox.enabled`) and refuses an `env` entry naming one of them.
   `CHAMVI_PUBLIC_URL` is derived from the Ingress (`https://<host>` with `tls.secretName`, else `http://<host>`) only
   when `env.CHAMVI_PUBLIC_URL` is unset or empty; it is the origin only, since the app's `approvalUrlOf()` appends
   `CHAMVI_BASE_PATH` itself. `CHAMVI_DEPLOYMENT` is the release's full name with `sandbox.enabled`, unless
   `env.CHAMVI_DEPLOYMENT` is set and non-empty. `env` follows in sorted key order, values as strings.
3. **Shutdown budget.** preStop `sleep.seconds: 5`, `terminationGracePeriodSeconds: 120`, the CLI's force exit 90 s.
   The render fails unless `preStopSleepSeconds * 1000 + CHAMVI_FORCE_EXIT_MS < terminationGracePeriodSeconds * 1000`
   (only `env.CHAMVI_FORCE_EXIT_MS` is visible to Helm). Probes: startup `<basePath>/healthz` 2 s x 60, liveness
   `<basePath>/healthz` 10 s x 3, readiness `<basePath>/readyz` 5 s x 2, all on the named port `http`.
4. **basePath.** Empty or `^(/[a-z0-9._~-]+)+$`, the app's `BASE_PATH_PATTERN` (lower case, routup matches paths
   case-insensitively), so every value the chart accepts is one the app starts with.
5. **CronJobs.** `concurrencyPolicy: Forbid`, `restartPolicy: Never`, `backoffLimit: 0`: a retried Job fires at a new
   time and gets a new `<subscription>@<scheduledAt>` idempotency key, i.e. a duplicate run. Any entry sets
   `CHAMVI_SCHEDULER=false` on the Deployment (its cron channel validates but never fires), so every cron subscription
   needs an entry. `subscription` is one argv element (spaces included) and may not start with `-`.
6. **Egress union rule.** NetworkPolicies are allow-lists whose union applies. With `sandbox.networkPolicy.cilium.enabled`
   the portable NetworkPolicy (`networkPolicy.ports`, 443 and 80, to every public address) must not render, or the FQDN list restricts nothing.
   Cilium on a cluster without `cilium.io/v2/CiliumNetworkPolicy` fails the render (an egress control that silently
   disappears is worse than a failed release); the ServiceMonitor is skipped without its API instead.
7. **Sandbox apart.** `sandbox.namespace` must differ from the release namespace. The Role lives there (never a
   ClusterRole) with `pods` `create, get, list, delete` and `pods/exec` `get, create`; the RoleBinding names the
   release namespace's ServiceAccount. The policies select `app.kubernetes.io/managed-by: chamvi` +
   `app.kubernetes.io/component: sandbox`; app pods are `component: app`, job pods `job`, the sandbox objects
   `sandbox-policy`, so the chart never labels its own pods as sandbox pods.
8. **Tokens.** `automountServiceAccountToken` is true only with `sandbox.enabled` (app and job pods), never for the test pod.
9. **Names.** Every name is a DNS label of at most 63 characters, CronJob names at most 52 (the controller appends 11).
   `agent-app.componentName` truncates the base before suffixing and inserts a hash of `(base, suffix)` when it had to
   cut, so suffixes survive and two long names do not collide.
10. **SSA-clean.** Flux 2.8+ applies with Helm 4 server-side apply: one container port, no duplicate env names, maps
    rendered with `range` (sorted). No `imagePullSecrets` in defaults or examples (`ghcr.io/chamvi/*` is public).
11. **Pod Security restricted.** uid/gid 1000, `runAsNonRoot`, `fsGroup: 1000`, seccomp `RuntimeDefault`, read-only
    root, no privilege escalation, every capability dropped, an `emptyDir` at `/tmp`.

## Guards

`templates/validations.yaml` and `templates/security-validations.yaml` render nothing and `fail` with a message naming
the value and the fix, never echoing a value (it may be a credential). They duplicate part of `values.schema.json` on
purpose: `helm template --skip-schema-validation` still meets them. No guard may block a valid Flux render (Flux renders
with the cluster's capabilities; local renders pass `--api-versions`).

## Release flow

release-please (`release-please-config.json`): root package `.` (`simple`, component `root`) linked with
`charts/agent-app` (`helm`, `skip-github-release: true`) through `linked-versions`. The root package is load-bearing: it
creates the one real GitHub release per cycle that clears the release PR's `autorelease: pending` label (authup/helm
learned this the hard way). The `publish` job runs `tada5hi/hevi@v2` on every master push, ungated, and is idempotent
(`cr --skip-existing`, `push-skip-existing`); `workflow_dispatch` re-runs it as the recovery path.
