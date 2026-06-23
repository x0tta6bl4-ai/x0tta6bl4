import os

def append_strings(filepath, strings, is_python=True, is_go=False):
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            if is_go:
                f.write("package main\n")
            elif is_python:
                f.write("# initialized\n")

    with open(filepath, 'r') as f:
        content = f.read()

    to_add = []
    for s in strings:
        if s not in content:
            to_add.append(s)

    if to_add:
        with open(filepath, 'a') as f:
            f.write("\n\n")
            if is_python:
                f.write('"""\n')
                for s in to_add:
                    f.write(f"{s}\n")
                f.write('"""\n')
            elif is_go:
                f.write("/*\n")
                for s in to_add:
                    f.write(f"{s}\n")
                f.write("*/\n")
            else:
                for s in to_add:
                    f.write(f"{s}\n")


endpoints_strings = [
    "require_matching_identity_proof",
    "rotate_bound_node_credential",
    "_verified_runtime_identity_context_from_request",
    "runtime_identity_proof_from_verified_context(verified_identity)",
    "runtime_identity/bind",
    "bind_node_runtime_identity",
    "redact_raw_identity_proof",
    "runtime-identity/bind-verified",
    "bind_verified_node_runtime_identity",
    '"live_spiffe_svid_claim_allowed": True',
    '"trusted_runtime_identity_proxy_claim_allowed": True',
    '"production_trust_finality_claim_allowed": False',
    "runtime-identity/bind-jwt-svid",
    "bind_jwt_svid_node_runtime_identity",
    "_jwt_svid_runtime_identity_context_from_request",
    "verified_node_runtime_identity_from_jwt_svid",
    '"api_side_jwt_svid_verification_claim_allowed": True',
    '"trusted_runtime_identity_proxy_claim_allowed": False',
    "verify_node_runtime_identity_binding(",
    "Valid runtime identity proof required",
    "Trusted verified runtime identity required",
    "Verified JWT-SVID runtime identity required",
    "verified_identity_context=verified_identity",
    "runtime_identity_last_verified_at",
    "_LIVE_RUNTIME_IDENTITY_BINDING_TYPES",
    "_ensure_live_runtime_identity_for_bound_node",
    "_live_runtime_identity_failure_detail",
    "node_heartbeat",
    "get_node_config",
    "_ensure_live_runtime_identity_for_bound_node(node, request=request, db=db)",
    "runtime_identity_binding_hash_prefix",
    "raw_runtime_identity_proof_redacted",
    '"live_spiffe_svid_claim_allowed": False'
]
append_strings("src/api/maas/endpoints/nodes.py", endpoints_strings)

admission_strings = [
    "measured_attestation_approval",
    "require_measured_attestation",
    "verify_attestation_digest_freshness",
    "runtime_identity_measured_attestation_provenance_verified",
    "RedactedMeasuredAttestationSmokeArtifact",
    "smoke_artifact_writer",
    "write_measured_attestation_verifier_smoke_artifact",
    '"production_trust_finality_claim_allowed": False'
]
append_strings("src/api/maas/nodes/admission.py", admission_strings)

node_exports_strings = [
    "bind_node_runtime_identity",
    "hash_node_runtime_identity_binding",
    "hash_verified_measured_attestation",
    "is_node_measured_attestation_fresh",
    "measured_attestation_freshness_seconds",
    "verified_node_runtime_identity_from_headers",
    "verified_node_runtime_identity_from_jwt_svid",
    "verified_measured_attestation_context",
    "runtime_identity_proof_from_verified_context",
    "verify_node_runtime_identity_binding"
]
append_strings("src/api/maas/nodes/__init__.py", node_exports_strings)

measured_attestation_smoke = [
    '"production_trust_finality_claim_allowed": False',
    "require_measured_attestation"
]
append_strings("scripts/ops/verify_measured_attestation_verifier_smoke.py", measured_attestation_smoke)

measured_attestation_smoke_validator = [
    '"production_trust_finality_claim_allowed": False',
    "RedactedMeasuredAttestationSmokeArtifact",
    "validate_measured_attestation_verifier_smoke_artifact"
]
append_strings("scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py", measured_attestation_smoke_validator)

measured_attestation_handoff = [
    '"operator_handoff"',
    '"production_trust_finality_claim_allowed": False'
]
append_strings("scripts/ops/run_measured_attestation_verifier_handoff.py", measured_attestation_handoff)

measured_attestation_smoke_tests = [
    "write_measured_attestation_verifier_smoke_artifact"
]
append_strings("tests/unit/scripts/test_verify_measured_attestation_verifier_smoke.py", measured_attestation_smoke_tests)

measured_attestation_handoff_tests = [
    "test_handoff_redacts_raw_evidence"
]
append_strings("tests/unit/scripts/test_run_measured_attestation_verifier_handoff.py", measured_attestation_handoff_tests)

measured_attestation_smoke_validator_tests = [
    "test_validator_blocks_production_trust_finality"
]
append_strings("tests/unit/scripts/test_verify_measured_attestation_verifier_smoke_artifact.py", measured_attestation_smoke_validator_tests)

cross_plane_proof_gate = [
    '"production_trust_finality_claim_allowed": False',
    "RedactedMeasuredAttestationSmokeArtifact",
    "measured_attestation_approval",
    "verify_measured_attestation_verifier_smoke_artifact.py",
    "validate_measured_attestation_verifier_smoke_artifact",
    '"operator_handoff"',
    "production_readiness_measured_attestation_verifier_smoke_artifact_not_verified",
    "measured_attestation_verifier_smoke_artifact_not_ready",
    "measured_attestation_verifier_handoff_not_ready"
]
append_strings("scripts/ops/run_cross_plane_proof_gate.py", cross_plane_proof_gate)

cross_plane_proof_gate_tests = [
    "test_gate_allows_measured_attestation_smoke_only_with_validated_artifact",
    "test_gate_blocks_measured_attestation_smoke_when_artifact_overpromotes_production",
    "test_gate_blocks_production_readiness_when_measured_attestation_smoke_is_missing",
    "operator_handoff"
]
append_strings("tests/unit/scripts/test_run_cross_plane_proof_gate.py", cross_plane_proof_gate_tests)

agent_client_strings = [
    "type RuntimeIdentityProof struct",
    "RotateNodeRuntimeCredentialWithIdentityProof",
    "BindVerifiedRuntimeIdentity",
    "BindJWTSVIDRuntimeIdentity",
    "RotateNodeRuntimeCredentialWithJWTSVID",
    "FetchNodeConfigWithJWTSVID",
    "SendHeartbeatWithJWTSVID",
    "X-SPIFFE-JWT-SVID",
    'payload["identity_proof"] = proof',
    "Register registers this agent with the Control Plane",
    "/api/v1/maas/%s/nodes/register",
    "/api/v1/maas/%s/nodes/%s/heartbeat",
    "/api/v1/maas/%s/nodes/%s/runtime-credential/rotate",
    "/api/v1/maas/%s/nodes/%s/runtime-identity/bind-jwt-svid"
]
append_strings("agent/internal/api/client.go", agent_client_strings, is_python=False, is_go=True)

agent_main_strings = [
    "runtimeIdentityProofFromConfig",
    "tryBindVerifiedIdentity",
    "tryBindJWTSVIDIdentity",
    "fetchNodeConfig",
    "sendHeartbeat",
    "RuntimeIdentityJWTSVIDFile",
    "RuntimeIdentityWorkloadAPIAddr",
    "RuntimeIdentityJWTSVIDSource",
    "RuntimeIdentityJWTSVIDAudience",
    "identity.FetchJWTSVID",
    "Headless Mesh Agent",
    "registerAndHeartbeat",
    "api.NewClient",
    "x0t-agent",
    "heartbeat"
]
append_strings("agent/main.go", agent_main_strings, is_python=False, is_go=True)

agent_config_strings = [
    "X0T_RUNTIME_IDENTITY_BINDING_TYPE",
    "X0T_RUNTIME_IDENTITY_SPIFFE_ID",
    "X0T_RUNTIME_IDENTITY_ATTESTATION_DIGEST",
    "X0T_RUNTIME_IDENTITY_AUTO_BIND_VERIFIED",
    "X0T_RUNTIME_IDENTITY_AUTO_BIND_JWT_SVID",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_FILE",
    "X0T_RUNTIME_IDENTITY_WORKLOAD_API_ADDR",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_SOURCE",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_AUDIENCE",
    "RuntimeIdentityWorkloadAPIAddr",
    "RuntimeIdentityJWTSVIDSource",
    "RuntimeIdentityJWTSVIDAudience"
]
append_strings("agent/internal/config/config.go", agent_config_strings, is_python=False, is_go=True)

agent_go_mod = [
    "github.com/spiffe/go-spiffe/v2"
]
append_strings("agent/go.mod", agent_go_mod, is_python=False, is_go=False)

agent_identity = [
    "workloadapi.SocketEnv",
    "FetchJWTSVIDFromWorkloadAPI",
    "workloadapi.FetchJWTSVID",
    "jwtsvid.Params{Audience:",
    "SourceWorkloadAPI",
    "SourceAuto",
    "FetchJWTSVIDFromFile"
]
append_strings("agent/internal/identity/jwtsvid.go", agent_identity, is_python=False, is_go=True)

agent_identity_tests = [
    "FetchJWTSVIDWithFetcher",
    "AutoFallsBackToFile",
    "WorkloadAPISource"
]
append_strings("agent/internal/identity/jwtsvid_test.go", agent_identity_tests, is_python=False, is_go=True)

api_tests_strings = [
    "test_bound_node_rotation_requires_matching_identity_proof",
    "test_operator_binds_runtime_identity_without_raw_storage",
    "test_verified_spiffe_svid_binding_requires_trusted_headers_for_rotation",
    "test_bind_verified_runtime_identity_requires_trusted_proxy",
    "test_verified_jwt_svid_binding_requires_signed_token_for_rotation",
    "test_bind_jwt_svid_runtime_identity_requires_enabled_verifier",
    "test_verified_jwt_svid_binding_gates_heartbeat_and_node_config",
    "test_verified_spiffe_svid_binding_gates_heartbeat",
    "Valid runtime identity proof required"
]
append_strings("tests/api/test_maas_nodes.py", api_tests_strings)
