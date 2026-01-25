#!/usr/bin/env bash
# Simple mTLS handshake test through Envoy sidecar.
# Requirements: pod name, namespace, target cluster address.
# Usage: ./mtls-handshake-test.sh mtls-demo service-a service-b:8080
set -euo pipefail
NS=${1:-mtls-demo}
SOURCE_APP=${2:-service-a}
TARGET=${3:-service-b:8080}
# Get source pod name
POD=$(kubectl get pods -n "$NS" -l app="$SOURCE_APP" -o jsonpath='{.items[0].metadata.name}')
echo "Source pod: $POD"
# Exec curl through Envoy inbound listener (assuming envoy maps 15443 to app mTLS cluster)
set +e
kubectl exec -n "$NS" "$POD" -c envoy -- curl -s -v "https://$TARGET" --resolve "$TARGET:15443:127.0.0.1" 2>&1 | tee handshake.log
set -e
# Extract certificate info
echo "--- Parsed certificate subjects (if available) ---"
grep -E "subject:|issuer:" handshake.log || echo "Cert details not found (pod may not be ready)"

echo "\n--- Extracting SAN / SPIFFE ID via openssl ---"
# Use openssl against the Envoy listener directly (assuming 15443). We map target to localhost.
kubectl exec -n "$NS" "$POD" -c envoy -- openssl s_client -connect "$TARGET" -servername "$TARGET" -alpn h2 -showcerts < /dev/null 2>&1 | tee openssl.log || true
SPIFFE=$(grep -Eo 'spiffe://[^ ,]+' openssl.log | head -1 || true)
if [ -n "$SPIFFE" ]; then
	echo "Detected SPIFFE ID: $SPIFFE"
else
	echo "SPIFFE ID not detected (handshake may have failed or cert not yet issued)."
fi
