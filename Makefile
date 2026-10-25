HELM_DOCS_VERSION := v1.14.2
HELM_SCHEMA_VERSION := 0.18.1
CT_VERSION := v3.15.0
SHELLCHECK_VERSION := v0.11.0
ACTIONLINT_VERSION := 1.7.12
CHART := charts/agent-app
# Render-only APIs: the ServiceMonitor and Cilium templates are gated on them.
API_VERSIONS := --api-versions monitoring.coreos.com/v1/ServiceMonitor --api-versions cilium.io/v2/CiliumNetworkPolicy

.PHONY: docs schema generate drift lint ct-lint unittest contract fixture template lint-values-coverage shellcheck actionlint test

## Generate the chart README.md from README.md.gotmpl and the values.yaml comments.
docs:
	docker run --rm -v "$(CURDIR):/helm-docs" -u $(shell id -u) jnorwood/helm-docs:$(HELM_DOCS_VERSION) -c charts

## Generate values.schema.json from the values.yaml # @schema blocks.
schema:
	docker run --rm -v "$(CURDIR)/charts:/charts" -u $(shell id -u) -w /charts ghcr.io/dadav/helm-schema:$(HELM_SCHEMA_VERSION) -c /charts

generate: schema docs

## Fail when the generated README.md or values.schema.json differ from their sources.
drift: generate
	@if [ -n "$$(git status --porcelain -- $(CHART)/README.md $(CHART)/values.schema.json)" ]; then \
	  echo 'Generated files outdated: run "make generate" and commit the result.' >&2; \
	  git status --porcelain -- $(CHART)/README.md $(CHART)/values.schema.json >&2; \
	  git --no-pager diff -- $(CHART)/README.md $(CHART)/values.schema.json >&2; \
	  exit 1; \
	fi
	@echo "generated files up to date"

lint:
	@for f in $(CHART)/ci/*-values.yaml; do helm lint $(CHART) -f "$$f" || exit 1; done
	yamllint -c .github/configs/lintconf.yaml $(CHART)/Chart.yaml $(CHART)/values.yaml

# The repo and its git dir mount at their own paths, so a git worktree (a .git file) works too.
GIT_COMMON_DIR := $(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)

ct-lint:
	docker run --rm -v "$(CURDIR):$(CURDIR)" -v "$(GIT_COMMON_DIR):$(GIT_COMMON_DIR)" -w "$(CURDIR)" \
	  quay.io/helmpack/chart-testing:$(CT_VERSION) \
	  sh -c 'git config --global --add safe.directory "*" && ct lint --config .github/configs/ct.yaml --all'

unittest:
	helm unittest $(CHART)

contract:
	python3 -m unittest discover -s scripts/tests -v

## Build the fixture app image (published @chamvi packages) and run the contract suite against it.
fixture:
	docker build -t chamvi-ci/app:ci ci/app
	AGENT_APP_CI_IMAGE=chamvi-ci/app:ci python3 -m unittest discover -s scripts/tests -v

template:
	@for f in $(CHART)/ci/*-values.yaml $(CHART)/ci/render/*-values.yaml; do \
	  echo "=== $$f"; helm template test $(CHART) -n agents -f "$$f" $(API_VERSIONS) >/dev/null || exit 1; \
	done
	@echo "all ci values render"

lint-values-coverage:
	python3 scripts/check-values-coverage.py $(CHART)

shellcheck:
	docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck:$(SHELLCHECK_VERSION) scripts/kind-smoke.sh

actionlint:
	docker run --rm -v "$(CURDIR):/repo" -w /repo rhysd/actionlint:$(ACTIONLINT_VERSION) -color

test: lint unittest contract template lint-values-coverage
