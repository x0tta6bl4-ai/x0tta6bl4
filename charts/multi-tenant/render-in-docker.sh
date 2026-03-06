#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHART_DIR="${ROOT_DIR}/charts/multi-tenant"
VALUES_FILE="${CHART_DIR}/values-enterprise.yaml"
OUTPUT_DIR="${CHART_DIR}/out"
RENDERED_FILE="${OUTPUT_DIR}/values-enterprise.rendered.yaml"
RUNTIME="${CONTAINER_RUNTIME:-docker}"
HELM_IMAGE="${HELM_IMAGE:-alpine/helm:3.14.4}"

mkdir -p "${OUTPUT_DIR}"

command -v "${RUNTIME}" >/dev/null 2>&1 || {
  echo "container runtime not found: ${RUNTIME}" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required for rendered output assertions" >&2
  exit 1
}

if grep -q '^dependencies:' "${CHART_DIR}/Chart.yaml"; then
  "${RUNTIME}" run --rm \
    -v "${ROOT_DIR}:/workspace" \
    -w /workspace/charts/multi-tenant \
    "${HELM_IMAGE}" dependency build
fi

"${RUNTIME}" run --rm \
  -v "${ROOT_DIR}:/workspace" \
  -w /workspace \
  "${HELM_IMAGE}" template multi-tenant ./charts/multi-tenant -f ./charts/multi-tenant/values-enterprise.yaml > "${RENDERED_FILE}"

python3 - "${VALUES_FILE}" "${RENDERED_FILE}" <<'PY'
import sys
import yaml

values_path, rendered_path = sys.argv[1:3]
with open(values_path, "r", encoding="utf-8") as fh:
    values = yaml.safe_load(fh)
with open(rendered_path, "r", encoding="utf-8") as fh:
    docs = [doc for doc in yaml.safe_load_all(fh) if doc]

tenants = values.get("tenants", [])
expected = {
    "Namespace": set(),
    "NetworkPolicy": set(),
    "CiliumNetworkPolicy": set(),
    "Role": set(),
    "RoleBinding": set(),
    "ServiceAccount": set(),
}

for tenant in tenants:
    expected["Namespace"].add((tenant["namespace"], tenant["namespace"]))
    expected["Namespace"].add((tenant["pqcKeyNamespace"], tenant["pqcKeyNamespace"]))
    expected["NetworkPolicy"].add(("tenant-default-deny", tenant["namespace"]))
    expected["CiliumNetworkPolicy"].add(("tenant-zero-lateral-movement", tenant["namespace"]))
    expected["Role"].add(("mesh-node-runtime", tenant["namespace"]))
    expected["Role"].add(("pqc-key-reader", tenant["pqcKeyNamespace"]))
    expected["RoleBinding"].add(("mesh-node-runtime", tenant["namespace"]))
    expected["RoleBinding"].add(("pqc-key-reader", tenant["pqcKeyNamespace"]))
    expected["ServiceAccount"].add((tenant["serviceAccountName"], tenant["namespace"]))

seen = {kind: set() for kind in expected}
for doc in docs:
    kind = doc.get("kind")
    metadata = doc.get("metadata") or {}
    name = metadata.get("name")
    namespace = metadata.get("namespace", name)
    if kind in seen:
        seen[kind].add((name, namespace))

missing = []
for kind, required in expected.items():
    for item in sorted(required - seen[kind]):
        missing.append(f"{kind} missing: {item[0]} in {item[1]}")

if missing:
    raise SystemExit("\n".join(missing))

print(f"render-ok docs={len(docs)} tenants={len(tenants)}")
PY

echo "Rendered chart written to ${RENDERED_FILE}"
