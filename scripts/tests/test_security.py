"""Security render contracts: removing policies, RBAC or guards must fail."""
import ipaddress
import unittest

from test_chart import documents, render

SANDBOX = {"enabled": True, "namespace": "sandboxes"}
LABELS = {"app.kubernetes.io/managed-by": "chamvi", "app.kubernetes.io/component": "sandbox"}


class SecurityContract(unittest.TestCase):
    def test_rbac_is_namespaced_and_exact(self):
        docs = documents(render({"sandbox": SANDBOX}))
        role = next(d for d in docs if d["kind"] == "Role")
        binding = next(d for d in docs if d["kind"] == "RoleBinding")
        self.assertEqual(role["metadata"]["namespace"], "sandboxes")
        self.assertEqual(role["rules"], [
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["create", "get", "list", "delete"]},
            {"apiGroups": [""], "resources": ["pods/exec"], "verbs": ["get", "create"]},
        ])
        self.assertEqual(binding["metadata"]["namespace"], "sandboxes")
        self.assertEqual(binding["subjects"], [{"kind": "ServiceAccount", "name": "demo-agent-app", "namespace": "agents"}])
        self.assertEqual(binding["roleRef"], {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": role["metadata"]["name"]})
        self.assertFalse(any(d["kind"] in ["ClusterRole", "Namespace"] for d in docs))

    def test_portable_policy_is_deny_ingress_and_public_https_only(self):
        policy = next(d for d in documents(render({"sandbox": SANDBOX})) if d["kind"] == "NetworkPolicy")
        spec = policy["spec"]
        self.assertEqual(spec["podSelector"]["matchLabels"], LABELS)
        self.assertEqual(spec["policyTypes"], ["Ingress", "Egress"])
        self.assertNotIn("ingress", spec)
        self.assertEqual(spec["egress"][0], {
            "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}, "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
            "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
        })
        https = spec["egress"][1]
        self.assertEqual(https["ports"], [{"protocol": "TCP", "port": 443}])
        self.assertEqual(len(spec["egress"]), 2)
        for peer in https["to"]:
            block = peer["ipBlock"]
            for excluded in block["except"]:
                self.assertTrue(ipaddress.ip_network(excluded).subnet_of(ipaddress.ip_network(block["cidr"])))
        ipv4 = https["to"][0]["ipBlock"]["except"]
        for address in ["10.96.0.1", "172.18.0.1", "192.168.1.1", "100.64.0.1", "169.254.169.254"]:
            self.assertTrue(any(ipaddress.ip_address(address) in ipaddress.ip_network(cidr) for cidr in ipv4))

    def test_missing_capability_and_unsafe_security_values_fail_closed(self):
        cases = [
            ({"enabled": True}, "sandbox.namespace"),
            ({"enabled": True, "namespace": "agents"}, "sandbox.namespace"),
            ({**SANDBOX, "networkPolicy": {"clusterCIDRs": ["::/0"]}}, "clusterCIDRs"),
            ({**SANDBOX, "networkPolicy": {"clusterCIDRs": ["999.0.0.0/8"]}}, "clusterCIDRs"),
            ({**SANDBOX, "networkPolicy": {"clusterCIDRs": ["0.0.0.0/0"]}}, "clusterCIDRs[0] must be narrower than 0.0.0.0/0"),
            ({**SANDBOX, "networkPolicy": {"clusterCIDRs": ["10.0.0.0/8", "10.0.0.0/0"]}}, "clusterCIDRs[1] must be narrower than 0.0.0.0/0"),
            ({**SANDBOX, "networkPolicy": {"cilium": {"enabled": True}}}, "CiliumNetworkPolicy"),
            ({**SANDBOX, "networkPolicy": {"enabled": False, "cilium": {"enabled": True}}}, "cilium.enabled"),
        ]
        for sandbox, field in cases:
            with self.subTest(sandbox=sandbox):
                result = render({"sandbox": sandbox})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(field, result.stderr)
        result = render({"sandbox": SANDBOX, "serviceAccount": {"create": False}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ServiceAccount", result.stderr)

    def test_ipv6_cluster_ranges_are_configurable(self):
        values = {"sandbox": {**SANDBOX, "networkPolicy": {"clusterCIDRsIPv6": ["fc00::/7", "fe80::/10", "2600:1f14::/48"]}}}
        policy = next(d for d in documents(render(values)) if d["kind"] == "NetworkPolicy")
        ipv6 = policy["spec"]["egress"][1]["to"][1]["ipBlock"]
        self.assertEqual(ipv6["cidr"], "::/0")
        self.assertEqual(ipv6["except"], ["fc00::/7", "fe80::/10", "2600:1f14::/48"])

    def test_empty_or_invalid_cluster_ranges_fail(self):
        cases = [
            ({"clusterCIDRs": []}, "clusterCIDRs must not be empty"),
            ({"clusterCIDRsIPv6": []}, "clusterCIDRsIPv6 must not be empty"),
            ({"clusterCIDRsIPv6": ["10.0.0.0/8"]}, "clusterCIDRsIPv6[0] must be an IPv6 CIDR"),
            ({"clusterCIDRsIPv6": ["::/0"]}, "clusterCIDRsIPv6[0] must be narrower than ::/0"),
            ({"clusterCIDRsIPv6": ["fc00::/129"]}, "clusterCIDRsIPv6[0] must be an IPv6 CIDR"),
            ({"dns": {"ipBlocks": ["dns"]}}, "dns.ipBlocks[0] must be an IPv4 or IPv6 CIDR"),
        ]
        for policy, message in cases:
            with self.subTest(policy=policy):
                result = render({"sandbox": {**SANDBOX, "networkPolicy": policy}})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_dns_ip_blocks_reach_node_local_dns(self):
        values = {"sandbox": {**SANDBOX, "networkPolicy": {"dns": {"ipBlocks": ["169.254.20.10/32"]}}}}
        policy = next(d for d in documents(render(values)) if d["kind"] == "NetworkPolicy")
        dns = policy["spec"]["egress"][0]
        self.assertIn({"ipBlock": {"cidr": "169.254.20.10/32"}}, dns["to"])
        self.assertEqual(dns["ports"], [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}])
        cilium = {"sandbox": {**SANDBOX, "networkPolicy": {"cilium": {"enabled": True}, "dns": {"ipBlocks": ["169.254.20.10/32"]}}}}
        result = render(cilium, extra=("--api-versions", "cilium.io/v2/CiliumNetworkPolicy"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dns.ipBlocks applies to the portable policy only", result.stderr)

    def test_dns_selectors_accept_other_label_keys(self):
        values = {"sandbox": {**SANDBOX, "networkPolicy": {"dns": {
            "namespaceSelector": {"kubernetes.io/metadata.name": None, "name": "dns"},
            "podSelector": {"k8s-app": None, "app.kubernetes.io/name": "coredns"},
        }}}}
        policy = next(d for d in documents(render(values)) if d["kind"] == "NetworkPolicy")
        self.assertEqual(policy["spec"]["egress"][0]["to"][0], {
            "namespaceSelector": {"matchLabels": {"name": "dns"}},
            "podSelector": {"matchLabels": {"app.kubernetes.io/name": "coredns"}},
        })

    def test_disabled_sandbox_creates_no_security_resources(self):
        docs = documents(render())
        self.assertFalse(any(d["kind"] in ["Role", "RoleBinding", "NetworkPolicy", "CiliumNetworkPolicy"] for d in docs))


if __name__ == "__main__":
    unittest.main()
