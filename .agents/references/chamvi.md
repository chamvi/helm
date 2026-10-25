# chamvi monorepo correspondence

Source: `chamvi/chamvi` master at `fbb1d11` (2026-10-25, release 0.2.1), packages published on npm at 0.2.1. Verify
against the source, never against the 011 plans, whose quoted contract predates the channels rewrite.

| chamvi | Path in the monorepo | Chart counterpart |
|---|---|---|
| `PORT` default 3000, `CHAMVI_BASE_PATH` rule `BASE_PATH_PATTERN` `^(?:\/[a-z0-9._~-]+)+$` | `packages/app/src/config/{module,constants}.ts` | container port 3000 `http`, owned env, the `basePath` guard in `templates/validations.yaml` |
| `approvalUrlOf()`: `<CHAMVI_PUBLIC_URL><basePath>/ui/approvals?run=&approval=` | `packages/app/src/config/helpers.ts` | `agent-app.publicUrl` derives the origin only (no basePath) |
| `CHAMVI_SCHEDULER=false` in start mode: a `cron` channel that validates but never fires | `packages/app/src/modules/scheduler/module.ts` | set on every pod whenever `cronJobs` is non-empty |
| `chamvi run-job <agent> [subscriptionId]` | `packages/cli/src/commands/run-job.ts` | CronJob args `command + [run-job, agent, subscription?]` |
| cron subscription id `cron:<expression>`, idempotency key `<subscriptionId>@<scheduledAt ISO>` | `packages/channel-cron/src/subscription/module.ts`, `packages/channel-cron/src/tick/module.ts` | `backoffLimit: 0`, `restartPolicy: Never`, `Forbid` |
| `CHAMVI_FORCE_EXIT_MS` 90 000 (dev 15 000) | `packages/cli/src/commands/constants.ts` | the shutdown guard's default |
| drain 30 s, close 5 s, readiness delay 0 | `packages/app/src/config/constants.ts` | grace 120 s, preStop 5 s |
| `/healthz`, `/readyz`, `/metrics` under `basePath`, unauthenticated | `packages/http/src/health/module.ts`, `packages/http/src/plugins/` | probes, the test hook, the ServiceMonitor path |
| GitHub deliveries at `<basePath>/channels/github`, webhooks at `<basePath>/channels/webhook/<agent><path>` | `packages/http/src/channels/`, `packages/github/src/webhook/` | README only (one Service port serves all) |
| `SANDBOX_LABELS` `app.kubernetes.io/managed-by: chamvi`, `app.kubernetes.io/component: sandbox` | `packages/sandbox/src/provider/constants.ts` | policy selectors; app pods are `component: app` |
| pods create/get/list/delete, pods/exec get/create (websocket exec) | `packages/sandbox-k8s/src/client/helpers.ts` | the sandbox Role |
| `CHAMVI_SANDBOX_PROVIDER` (`local`/`docker`/`kubernetes`), `CHAMVI_SANDBOX_NAMESPACE` required for kubernetes, `CHAMVI_SANDBOX_IMAGE` | `packages/sandbox/src/module/module.ts` | the chart sets the namespace only; the provider is the app's choice (`env`) |
| `CHAMVI_AGENTS_DIR` (default `./agents` when a directory), entry-less app `createApp({})` | `packages/app/src/modules/agents/`, `packages/cli/src/entry/` | none: agents ship in the image (`/app`) |
| provider keys `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `MISTRAL_API_KEY`, `XAI_API_KEY` for `'<provider>/<model>'` strings | `packages/app/src/models/constants.ts` | README Secrets table |
| `GITHUB_APP_*`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_INSTALLATION_ID`, `GITHUB_API_URL` | `packages/github/src/module/` | README Secrets table |
| `OPENCLAW_*` | `packages/channel-openclaw/src/module/` | README Secrets table |
| image `ghcr.io/chamvi/node:24`: tini entrypoint, uid 1000, workdir `/app` | `images/node/Dockerfile` | `args` not `command`, the security contexts, `ci/app/Dockerfile` |

Fixed: 0.2.0 double-converted string models in `installDefaultProvider`; chamvi PR #41 fixed it and 0.2.1 (published)
ships the fix. The fixture app passes a model object, so it never depended on that fix; its `^0.2.0` range resolves to
0.2.1.
