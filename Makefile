CHART := charts/agent-app
API_VERSIONS := --api-versions monitoring.coreos.com/v1/ServiceMonitor --api-versions cilium.io/v2/CiliumNetworkPolicy

.PHONY: docs schema lint ct-lint unittest contract template lint-values-coverage test generated-check

# External tooling is not authorized in this local implementation. These targets
# fail explicitly rather than producing substitutes or claiming a drift check.
docs schema ct-lint:
	@echo "$@: blocked pending authorization of the pinned upstream tool" >&2
	@exit 1

lint:
	@for f in $(CHART)/ci/*-values.yaml; do helm lint $(CHART) -f "$$f" || exit 1; done
	yamllint -c .github/configs/lintconf.yaml $(CHART)/Chart.yaml $(CHART)/values.yaml

unittest:
	helm unittest $(CHART)

contract:
	python3 -m unittest discover -s scripts/tests -v

template:
	@for f in $(CHART)/ci/*-values.yaml $(CHART)/ci/render/*-values.yaml; do \
	  [ -f "$$f" ] || continue; \
	  echo "=== $$f"; helm template test $(CHART) -n agents -f "$$f" $(API_VERSIONS) >/dev/null || exit 1; \
	done
	@echo "all ci values render"

lint-values-coverage:
	python3 scripts/check-values-coverage.py $(CHART)

generated-check:
	test -s $(CHART)/values.schema.json
	test -s $(CHART)/README.md

# Local behavior only. Release acceptance requires generated-check and drift,
# plus chart-testing installation and live smoke tests.
test: lint unittest contract template lint-values-coverage
