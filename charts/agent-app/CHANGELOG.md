# Changelog

## [0.1.1](https://github.com/chamvi/helm/compare/agent-app-0.1.0...agent-app-0.1.1) (2026-10-25)


### Features

* **agent-app:** add the agent-app chart ([cb1996a](https://github.com/chamvi/helm/commit/cb1996a574d3c177975e802e4ca146e29717730a))
* **agent-app:** generate the values schema and the chart README ([7d2e74d](https://github.com/chamvi/helm/commit/7d2e74d52d5f8cafe104a8c9a1bde9adad9c462d))
* **agent-app:** initial chart ([ca6bb19](https://github.com/chamvi/helm/commit/ca6bb196217cdb2a28dbe0f553b5f6194c9fc03a))


### Bug Fixes

* **agent-app:** keep values.yaml schema annotations intact in values.schema.json ([559e0bc](https://github.com/chamvi/helm/commit/559e0bc1c995c57a6caf336ebafdae6d8c2f1c85))
* **agent-app:** label the sandbox RoleBinding and refresh the install notes ([83170c0](https://github.com/chamvi/helm/commit/83170c0d5a4580b4d97d28e4569c6e64b4022c7f))
* **agent-app:** let the sandbox policy list IPv6 ranges and DNS addresses, refuse empty CIDR lists ([79ee86c](https://github.com/chamvi/helm/commit/79ee86cbc2a4df7255505f0369c67edd27d9785d))
* **agent-app:** refuse a /0 entry in sandbox.networkPolicy.clusterCIDRs ([949e1d6](https://github.com/chamvi/helm/commit/949e1d66ac662f65fc031bf6a7a7137193e12a06))
* **agent-app:** refuse a HOST the probes cannot reach and document :: for IPv6 clusters ([c1fc562](https://github.com/chamvi/helm/commit/c1fc56235ecd783344a8899ad48f3839fa565d6f))
* **agent-app:** render and validate whole numbers of a million or more from values files ([a189ba3](https://github.com/chamvi/helm/commit/a189ba3fa35d2e9eb47ba642d2a1b2f0c45ac7ee))
* **agent-app:** render whole-number env values from values files without exponent notation ([7c9bbf0](https://github.com/chamvi/helm/commit/7c9bbf00021e33a956f654a5de0301f4984d4183))
