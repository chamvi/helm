# Structure

```
chamvi/helm
├── AGENTS.md, CLAUDE.md, .agents/                 # agent docs; .agents/plans/ is gitignored
├── README.md, CONTRIBUTING.md, SECURITY.md, LICENSE, NOTICE
├── Makefile                                       # docs, schema, generate, drift, lint, ct-lint, unittest, contract,
│                                                  # fixture, template, lint-values-coverage, shellcheck, actionlint, test
├── release-please-config.json, .release-please-manifest.json, version.txt, CHANGELOG.md (release-please)
├── scripts/
│   ├── check-values-coverage.py                   # every .Values.* a template reads exists in values.yaml (from authup/helm)
│   ├── kind-smoke.sh                              # CI: CronJob run + sandbox NetworkPolicy enforcement on kind
│   └── tests/                                     # Python contract tests (unittest + PyYAML over helm template)
├── ci/app/                                        # fixture agent app image (published @chamvi packages, mock model)
├── .github/
│   ├── configs/{ct.yaml,lintconf.yaml}
│   ├── workflows/{lint-test.yaml,release.yaml}
│   └── dependabot.yml                             # github-actions only
└── charts/agent-app/
    ├── Chart.yaml, .helmignore, values.yaml, README.md.gotmpl
    ├── README.md, values.schema.json              # GENERATED
    ├── ci/{default,cronjob,sandbox,ingress}-values.yaml   # ct lint + ct install on kind
    ├── ci/render/cilium-values.yaml               # render only (needs the Cilium API)
    ├── ci/manifests/secret.yaml                   # pre-applied into every ct install namespace
    ├── templates/
    │   ├── _helpers.tpl                           # names, labels, image, env, envFrom, pod and container commons
    │   ├── _validation-helpers.tpl                # integer, DNS name, string map guards
    │   ├── validations.yaml, security-validations.yaml   # fail-fast guards, render nothing
    │   ├── deployment.yaml, service.yaml, serviceaccount.yaml, ingress.yaml
    │   ├── cronjob.yaml                           # one CronJob per cronJobs entry
    │   ├── sandbox-rbac.yaml, sandbox-networkpolicy.yaml, sandbox-ciliumnetworkpolicy.yaml
    │   ├── servicemonitor.yaml, NOTES.txt
    │   └── tests/test-readyz.yaml                 # helm test hook
    └── tests/                                     # helm-unittest suites, values/base.yaml
```

`.helmignore` drops `ci/`, `README.md.gotmpl` and the anchored `/tests/`: a bare `tests/` would also match
`templates/tests/` and strip the helm test hook from packages, renders and helm-unittest.
