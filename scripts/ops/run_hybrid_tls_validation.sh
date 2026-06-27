#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMESTAMP_ID="$(date -u +%Y%m%dT%H%M%SZ)"

REPORT_DIR="${REPORT_DIR:-$REPO_ROOT/docs/verification}"
ARTIFACT_JSON="$REPORT_DIR/hybrid_tls_validation_${TIMESTAMP_ID}.json"
ARTIFACT_MD="$REPORT_DIR/hybrid_tls_validation_${TIMESTAMP_ID}.md"
LATEST_JSON="$REPORT_DIR/HYBRID_TLS_VALIDATION_LATEST.json"
LATEST_MD="$REPORT_DIR/HYBRID_TLS_VALIDATION_LATEST.md"

mkdir -p "$REPORT_DIR"

PYTHONPATH="$REPO_ROOT" python3 - "$TIMESTAMP_UTC" "$ARTIFACT_JSON" "$ARTIFACT_MD" "$LATEST_JSON" "$LATEST_MD" <<'PY'
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys

generated_at, artifact_json, artifact_md, latest_json, latest_md = sys.argv[1:]

from src.security.pqc.adapter import is_liboqs_available
from src.security.pqc.hybrid_tls import (
    HybridTLSContext,
    authenticated_hybrid_handshake,
    hybrid_handshake,
    hybrid_sign,
    hybrid_verify,
)

if not is_liboqs_available():
    raise RuntimeError("liboqs runtime is not available; cannot produce VERIFIED HERE hybrid TLS evidence")

client = HybridTLSContext("client")
server = HybridTLSContext("server")
session_key_client, session_key_server = hybrid_handshake(client, server)
basic_match = session_key_client == session_key_server == client.session_key == server.session_key

auth_client = HybridTLSContext("client")
auth_server = HybridTLSContext("server")
auth_result = authenticated_hybrid_handshake(auth_client, auth_server)
authenticated_match = auth_client.session_key == auth_server.session_key == auth_result.session_key

verify_client = HybridTLSContext("client")
verify_server = HybridTLSContext("server")
verify_client.set_peer_public_bundle(verify_server.get_public_bundle())
message = b"transcript"
signature = hybrid_sign(verify_server, message)
verify_ok = hybrid_verify(verify_client, message, signature)

report = {
    "generated_at_utc": generated_at,
    "claim_boundary": "Real local liboqs-backed hybrid TLS handshake and transcript-signature validation in this environment. This is still local runtime evidence, not production traffic proof.",
    "algorithms": {
        "kem": "ML-KEM-768",
        "classical_kex": "ECDHE P-256",
        "signature": "ML-DSA-65 transcript binding",
        "transport_cipher": "AES session key derived via HKDF-SHA256",
    },
    "results": {
        "basic_session_keys_match": basic_match,
        "authenticated_session_keys_match": authenticated_match,
        "session_key_length": len(auth_result.session_key),
        "ciphertext_length": len(auth_result.ciphertext),
        "transcript_sha256": auth_result.transcript_sha256,
        "client_signature_length": len(auth_result.client_signature),
        "server_signature_length": len(auth_result.server_signature),
        "peer_signature_verification": verify_ok,
        "liboqs_runtime": True,
        "client_sig_public_key_length": len(auth_client.sig_public_key),
        "server_sig_public_key_length": len(auth_server.sig_public_key),
    },
}

artifact_json_path = Path(artifact_json)
artifact_md_path = Path(artifact_md)
latest_json_path = Path(latest_json)
latest_md_path = Path(latest_md)

artifact_json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
latest_json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

artifact_md_path.write_text(
    "\n".join(
        [
            "# Hybrid TLS Validation",
            "",
            f"- Generated at: `{generated_at}`",
            f"- KEM: `{report['algorithms']['kem']}`",
            f"- Classical KEX: `{report['algorithms']['classical_kex']}`",
            f"- Signature binding: `{report['algorithms']['signature']}`",
            f"- Real liboqs runtime: `{report['results']['liboqs_runtime']}`",
            f"- Basic session keys match: `{report['results']['basic_session_keys_match']}`",
            f"- Authenticated session keys match: `{report['results']['authenticated_session_keys_match']}`",
            f"- Session key length: `{report['results']['session_key_length']}`",
            f"- Ciphertext length: `{report['results']['ciphertext_length']}`",
            f"- Client signature length: `{report['results']['client_signature_length']}`",
            f"- Server signature length: `{report['results']['server_signature_length']}`",
            f"- Peer signature verification: `{report['results']['peer_signature_verification']}`",
            f"- Transcript SHA256: `{report['results']['transcript_sha256']}`",
            "",
            "## Claim Boundary",
            report["claim_boundary"],
        ]
    )
    + "\n",
    encoding="utf-8",
)
latest_md_path.write_text(artifact_md_path.read_text(encoding="utf-8"), encoding="utf-8")

print(artifact_json_path)
print(artifact_md_path)
PY

echo
echo "Hybrid TLS validation PASS"
echo "Report JSON: $ARTIFACT_JSON"
echo "Report MD:   $ARTIFACT_MD"
