#!/usr/bin/env bash
# Smoke test on kind, after `ct install`: a CronJob-triggered run-job completes, and the
# sandbox NetworkPolicy lets a sandbox-labelled pod reach https://github.com but not the
# Kubernetes API server. Needs: the chamvi-ci/app:ci image loaded into kind and the
# namespace chamvi-sandbox-ci (the lint-test workflow creates both).
set -euo pipefail

CHART=charts/agent-app
NAMESPACE=smoke
SANDBOX_NAMESPACE=chamvi-sandbox-ci
RELEASE=smoke
CURL_IMAGE=curlimages/curl:8.22.0

dump() {
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
    fi
}
trap dump EXIT

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

echo "3. the sandbox NetworkPolicy allows https://github.com and blocks the API server"
kubectl -n "$SANDBOX_NAMESPACE" apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: egress-probe
  labels:
    app.kubernetes.io/managed-by: chamvi
    app.kubernetes.io/component: sandbox
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
      command:
        - sh
        - -c
        - >-
          curl -fsS -m 10 -o /dev/null https://github.com &&
          ! curl -sk -m 5 -o /dev/null https://kubernetes.default.svc.cluster.local &&
          echo NP_OK
EOF
kubectl -n "$SANDBOX_NAMESPACE" wait pod/egress-probe --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s || {
    echo "The egress probe did not succeed: either github.com was unreachable or the API server was reachable." >&2
    echo "kind enforces NetworkPolicy through kube-network-policies since v0.24.0; check the kind version and CNI." >&2
    exit 1
}
kubectl -n "$SANDBOX_NAMESPACE" logs pod/egress-probe | grep -x NP_OK

echo "4. uninstall"
kubectl -n "$SANDBOX_NAMESPACE" delete pod egress-probe --wait=false
helm uninstall "$RELEASE" -n "$NAMESPACE" --wait

echo "kind smoke OK"
