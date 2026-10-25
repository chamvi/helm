# Cilium correspondence

Pinned source: cilium/cilium v1.18.0, checked read-only on 2026-10-25.

- `Documentation/security/policy/intro.rst` lines 43-54: selecting an endpoint and specifying an ingress/egress section enables default deny for that direction. Lines 118-124: omitted directions have no effect.
- `examples/policies/l3/egress-default-deny/egress-default-deny.yaml` uses `egress: [{}]`. The chart's `templates/sandbox-ciliumnetworkpolicy.yaml` uses the analogous `ingress: [{}]` deny-all rule.
- `Documentation/security/policy/language.rst` lines 80-86 and 112-120: an empty EndpointSelector *inside* an allow rule selects all endpoints. `ingress: [{}]` is not `ingress: [{fromEndpoints: [{}]}]`.
- `examples/policies/l3/fqdn/fqdn.yaml`: DNS proxy endpoints use `k8s:io.kubernetes.pod.namespace` and `k8s:k8s-app`, port 53 protocol ANY, `rules.dns: [{matchPattern: '*'}]`. The chart translates the DNS namespace name and pod labels into those endpoint labels.
- `examples/policies/l7/dns/dns.yaml`: FQDN selectors and port restrictions belong in the same egress rule. The chart restricts the configured names/patterns to TCP 443.

Cilium replaces the portable NetworkPolicy; rendering both would union the portable public HTTPS permission with the FQDN allowlist. Missing Cilium API fails closed. No Cilium cluster application or network enforcement has been verified. The guessed ingress-default-deny example path returned 404 and is not evidence.
