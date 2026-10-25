#!/usr/bin/env bash
# Smoke test on kind, after `ct install`: a CronJob-triggered run-job completes, and the
# sandbox NetworkPolicy lets a sandbox-labelled pod reach https://github.com but not a
# cluster pod on TCP 443. Needs: the chamvi-ci/app:ci image loaded into kind and the
# namespace chamvi-sandbox-ci (the lint-test workflow creates both).
set -euo pipefail

CHART=charts/agent-app
NAMESPACE=smoke
SANDBOX_NAMESPACE=chamvi-sandbox-ci
RELEASE=smoke
CURL_IMAGE=curlimages/curl:8.22.0
APP_IMAGE=chamvi-ci/app:ci

on_exit() {
    local status=$?
    if [ "$status" -ne 0 ]; then
        echo "kind-smoke failed (exit $status); pods, logs and events follow." >&2
        for ns in "$NAMESPACE" "$SANDBOX_NAMESPACE"; do
            kubectl -n "$ns" get pods,jobs,cronjobs,networkpolicies -o wide >&2 || true
            for pod in $(kubectl -n "$ns" get pods -o name 2>/dev/null); do
                echo "--- logs $ns/$pod" >&2
                kubectl -n "$ns" logs "$pod" --all-containers >&2 || true
            done
            kubectl -n "$ns" get events --sort-by=.lastTimestamp >&2 || true
        done
        # kind enforces NetworkPolicy in kindnet (kube-network-policies).
        kubectl -n kube-system get pods -o wide >&2 || true
        kubectl -n kube-system logs -l app=kindnet --tail=200 >&2 || true
    fi
    # Clean up on success and failure, so a rerun in the same cluster starts fresh.
    kubectl -n "$SANDBOX_NAMESPACE" delete pod control-probe egress-probe --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "$NAMESPACE" delete pod tls-target --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "$NAMESPACE" delete job ping-now --ignore-not-found --wait=false >/dev/null 2>&1 || true
    helm uninstall "$RELEASE" -n "$NAMESPACE" --wait >/dev/null 2>&1 || true
    return "$status"
}
trap on_exit EXIT

echo "1. install the chart in CronJob mode with the sandbox policy"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$SANDBOX_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" apply -f "$CHART/ci/manifests/"
helm install "$RELEASE" "$CHART" -n "$NAMESPACE" \
    -f "$CHART/ci/cronjob-values.yaml" \
    --set sandbox.enabled=true \
    --set "sandbox.namespace=$SANDBOX_NAMESPACE" \
    --wait --timeout 300s

echo "2. run the CronJob once: run-job must complete the fixture run and exit 0"
kubectl -n "$NAMESPACE" create job ping-now --from="cronjob/$RELEASE-agent-app-ping"
kubectl -n "$NAMESPACE" wait --for=condition=complete job/ping-now --timeout=180s
kubectl -n "$NAMESPACE" logs job/ping-now | grep -E '^ping: completed \(run [0-9a-f-]+\)$'

echo "3. the sandbox NetworkPolicy allows https://github.com and blocks cluster addresses"
# The negative target is a pod IP on TCP 443 (inside 10.0.0.0/8 on kind), not the API
# server: on a single-node cluster the API server is the pod's own node, and NetworkPolicy
# implementations do not police pod-to-node traffic. A control pod without the sandbox
# labels must reach the target, so a target that never came up cannot pass the check.
kubectl -n "$NAMESPACE" apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: tls-target
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    sysctls:
      - name: net.ipv4.ip_unprivileged_port_start
        value: "0"
  containers:
    - name: target
      image: $APP_IMAGE
      imagePullPolicy: Never
      args: [node, -e, "require('node:http').createServer((q, s) => s.end('ok')).listen(443)"]
      readinessProbe:
        tcpSocket:
          port: 443
        periodSeconds: 1
EOF
kubectl -n "$NAMESPACE" wait pod/tls-target --for=condition=Ready --timeout=120s
TARGET="http://$(kubectl -n "$NAMESPACE" get pod tls-target -o jsonpath='{.status.podIP}'):443"

# probe <name> <sandbox: true|false> <shell command>: runs curl in the sandbox namespace and
# succeeds when the command printed PROBE_OK.
probe() {
    local labels=""
    if [ "$2" = true ]; then
        labels="app.kubernetes.io/managed-by: chamvi
    app.kubernetes.io/component: sandbox"
    else
        labels="app.kubernetes.io/name: control"
    fi
    kubectl -n "$SANDBOX_NAMESPACE" apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $1
  labels:
    $labels
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 100
    runAsGroup: 101
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: probe
      image: $CURL_IMAGE
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
      command: [sh, -c, "$3; echo PROBE_OK"]
EOF
    kubectl -n "$SANDBOX_NAMESPACE" wait "pod/$1" --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s || return 1
    kubectl -n "$SANDBOX_NAMESPACE" logs "pod/$1" | grep -qx PROBE_OK
}

probe control-probe false "curl -fsS -m 10 -o /dev/null $TARGET || exit 1" || {
    echo "The control pod could not reach $TARGET: the negative check below would prove nothing." >&2
    exit 1
}
probe egress-probe true "curl -fsS -m 10 -o /dev/null https://github.com || { echo GITHUB_UNREACHABLE; exit 1; }; if curl -s -m 5 -o /dev/null $TARGET; then echo TARGET_REACHABLE; exit 1; fi" || {
    echo "The sandbox probe failed: github.com was unreachable or $TARGET (a cluster pod on TCP 443) was reachable." >&2
    echo "kind enforces NetworkPolicy through kube-network-policies since v0.24.0; check the kind version and CNI." >&2
    exit 1
}

echo "kind smoke OK"
