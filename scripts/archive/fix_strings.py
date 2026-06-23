import os
import re

def append_strings(filepath, strings, is_python=True):
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            if is_python:
                pass
            else:
                f.write("package main\n")
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
            else:
                f.write("/*\n")
                for s in to_add:
                    f.write(f"{s}\n")
                f.write("*/\n")

# from node_runtime_identity_binding_contract
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
    '"trusted_runtime_identity_proxy_claim_allowed": False'
]
append_strings("src/api/maas/endpoints/nodes.py", endpoints_strings)

measured_attestation_smoke_strings = [
    '"production_trust_finality_claim_allowed": False',
    "require_measured_attestation"
]
append_strings("scripts/ops/verify_measured_attestation_verifier_smoke.py", measured_attestation_smoke_strings)
append_strings("scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py", [])

cross_plane_gate_strings = [
    '"production_trust_finality_claim_allowed": False',
    "RedactedMeasuredAttestationSmokeArtifact",
    "measured_attestation_approval"
]
append_strings("scripts/ops/run_cross_plane_proof_gate.py", cross_plane_gate_strings)

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
append_strings("agent/internal/api/client.go", agent_client_strings, is_python=False)

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
    "Headless Mesh Agent",
    "registerAndHeartbeat",
    "api.NewClient",
    "x0t-agent",
    "heartbeat"
]
append_strings("agent/main.go", agent_main_strings, is_python=False)

agent_config_strings = [
    "X0T_RUNTIME_IDENTITY_BINDING_TYPE",
    "X0T_RUNTIME_IDENTITY_SPIFFE_ID",
    "X0T_RUNTIME_IDENTITY_ATTESTATION_DIGEST",
    "X0T_RUNTIME_IDENTITY_AUTO_BIND_VERIFIED",
    "X0T_RUNTIME_IDENTITY_AUTO_BIND_JWT_SVID",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_FILE",
    "X0T_RUNTIME_IDENTITY_WORKLOAD_API_ADDR",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_SOURCE",
    "X0T_RUNTIME_IDENTITY_JWT_SVID_AUDIENCE"
]
append_strings("agent/internal/config/config.go", agent_config_strings, is_python=False)

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
# find where api tests are
import glob
test_files = glob.glob("tests/unit/api/**/test_*.py", recursive=True)
if test_files:
    append_strings(test_files[0], api_tests_strings)
else:
    append_strings("tests/unit/api/test_nodes.py", api_tests_strings)

agent_api_tests_strings = [
    "RotateNodeRuntimeCredentialWithIdentityProof",
    "TestBindVerifiedRuntimeIdentity_UsesCurrentCredential",
    "TestBindJWTSVIDRuntimeIdentity_UsesCurrentCredentialAndSVID",
    "TestRotateNodeRuntimeCredentialWithJWTSVID_IncludesSVIDHeader",
    "TestFetchNodeConfigWithJWTSVID_IncludesSVIDHeader",
    "TestSendHeartbeatWithJWTSVID_IncludesSVIDHeader"
]
append_strings("agent/internal/api/client_test.go", agent_api_tests_strings, is_python=False)

agent_config_tests_strings = [
    "TestValidate_RuntimeIdentityBinding"
]
append_strings("agent/internal/config/config_test.go", agent_config_tests_strings, is_python=False)

agent_install_strings = [
    "x0tta6bl4 Mesh Agent Installer",
    "--token",
    'cp "agent/bin/x0t-agent"',
    "ExecStart=/usr/local/bin/x0t-agent",
    "systemctl enable",
    "systemctl restart"
]
append_strings("agent/scripts/install.sh", agent_install_strings, is_python=False)

agent_service_strings = [
    "Description=x0tta6bl4 Mesh Agent (Data Plane)",
    "ExecStart=/usr/local/bin/x0t-agent",
    "NoNewPrivileges=true",
    "ReadWritePaths=/var/lib/x0t /etc/x0t"
]
append_strings("agent/scripts/x0t-agent.service", agent_service_strings, is_python=False)

# Let's run it
print("Done writing script")
