from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.network.firstparty_vpn import (
    Frame,
    CamouflageError,
    CamouflagePolicy,
    CamouflageProfile,
    CommandPlanEvidence,
    FrameAuthError,
    FrameCrypto,
    FrameCryptoError,
    FrameType,
    FragmentError,
    FullVpnProductionReadinessEvidence,
    FullVpnProductionReadinessError,
    FullVpnProductionReadinessRequirements,
    DataplaneEndpointCandidate,
    DataplaneProbeResult,
    DataplaneProbeSpec,
    DataplaneSelectionError,
    DataplaneValidationError,
    DataplaneValidationPlan,
    DevicePosturePolicy,
    DurableIdentityBackend,
    DurableIdentityBackendStore,
    DurableIdentitySignerManifestStore,
    DurablePolicyStore,
    DurablePolicySequenceStore,
    DurablePqcManifestStore,
    ExternalPolicySnapshotSource,
    ExternalPolicySnapshotSourceEvidence,
    FirstPartyAntiDpiProfile,
    FirstPartyDataplaneClientError,
    FirstPartyDataplaneBind,
    FirstPartyDataplaneServiceError,
    FirstPartyDataplaneSelector,
    FirstPartyGenevaAction,
    FirstPartyGenevaStrategy,
    FirstPartyThreadedDataplaneServiceResource,
    FirstPartyHandshakeAccept,
    FirstPartyHandshakeError,
    FirstPartyHandshakeHello,
    FirstPartyHandshakeSecretStore,
    FirstPartyIdentitySignerAttestation,
    FirstPartyIdentitySignerManifest,
    FirstPartyMlKemImplementation,
    FirstPartyPqcProvider,
    FirstPartyReferenceMlDsaIdentitySignatureProvider,
    FirstPartyEndpoint,
    FirstPartyLoopbackProbeRunner,
    FirstPartyManagedTunClientBridge,
    FirstPartyRemoteMtuProbeRunner,
    FirstPartyRemoteProbeRunner,
    FirstPartyRemoteTunProbeRunner,
    FirstPartyRekeyAccept,
    FirstPartyRekeyCadencePolicy,
    FirstPartyRekeyError,
    FirstPartyRekeyPolicyDecision,
    FirstPartyRekeyRequest,
    FirstPartyRekeyRollbackEvidence,
    FirstPartyRekeySecretStore,
    FirstPartyRekeyServerProcessor,
    FirstPartyRekeyTelemetry,
    FirstPartySessionAdmissionError,
    FirstPartySessionAdmissionRegistry,
    FirstPartySourceAuditError,
    FirstPartySourceAuditEvidence,
    FirstPartySharedTunAdmissionReturnPump,
    FirstPartyTeslaAuthenticator,
    FirstPartyTeslaPolicy,
    FirstPartyThreadedAdmissionTunServerResource,
    FirstPartyThreadedSharedTunAdmissionServerResource,
    FirstPartyAdmissionTunServerHandler,
    FirstPartyAdmissionTunServerReturnPump,
    FirstPartyAdmissionTunServerReturnPumpManager,
    FirstPartyTunClientBridge,
    FirstPartyTunDataplaneSelector,
    FirstPartyTunLoopbackProbeRunner,
    FirstPartyTunClientPump,
    FirstPartyMultiSessionTunServerHandler,
    FirstPartyMultiSessionTunServerPump,
    FirstPartyThreadedMultiSessionTunServerResource,
    FirstPartyThreadedTunClientResource,
    FirstPartyThreadedTunServerResource,
    FirstPartyTunPumpError,
    FirstPartyTunServerPump,
    FirstPartyTunServerHandler,
    FirstPartyVpnDataplaneActivationResult,
    open_threaded_firstparty_shared_tun_admission_server,
    FirstPartyVpnDeploymentConfig,
    FirstPartyVpnDeploymentEvidence,
    FirstPartyVpnDeploymentError,
    FirstPartyVpnDeploymentExecutionEvidence,
    FirstPartyVpnDeploymentExecutor,
    FirstPartyVpnDeploymentMutationBlocked,
    FirstPartyVpnDeploymentPacket,
    FirstPartyVpnTunActivationResult,
    IdentityAuthority,
    IdentityBackendError,
    IdentityIssueRequest,
    IdentitySignerConformanceEvidence,
    IdentitySignerKatResult,
    IdentitySignerKnownAnswerVector,
    IdentitySigningKey,
    IdentityClaims,
    LinuxHostFacts,
    LinuxAppliedStateEvidence,
    LinuxAppliedStateSnapshot,
    LinuxLeakProtectionEvidence,
    LinuxNetworkPolicyConfig,
    LinuxNetworkPolicyMutationBlocked,
    LinuxNetworkPolicyPlanner,
    LinuxPreflightConfig,
    LinuxPreflightEvidence,
    LinuxServerNatConfig,
    LinuxServerNatPlanner,
    LinuxServerVpnListener,
    LinuxTunConfig,
    LinuxTunDevice,
    LinuxTunMutationBlocked,
    LocalTestPqcProvider,
    LocalIdentitySignatureProvider,
    ManifestBackedIdentitySignatureProvider,
    MemoryTunDevice,
    ML_DSA_D,
    ML_DSA_KEY_BYTES,
    ML_DSA_KEYGEN_SEED_BYTES,
    ML_DSA_N,
    ML_DSA_Q,
    ML_DSA_RHO_PRIME_BYTES,
    ML_DSA_RHO_BYTES,
    ML_DSA_T0_BITS,
    ML_DSA_T0_BOUND,
    ML_DSA_T1_BITS,
    ML_DSA_TR_BYTES,
    ML_KEM_N,
    ML_KEM_Q,
    ML_KEM_SEED_BYTES,
    ML_KEM_SHARED_SECRET_BYTES,
    MlDsaShapeError,
    MlKemPrimitiveError,
    mlkem_add,
    mlkem_byte_decode,
    mlkem_byte_encode,
    mlkem_compress,
    mlkem_decode_vector,
    mlkem_decode_poly,
    mlkem_decompress,
    mlkem_decapsulate,
    mlkem_encapsulate,
    mlkem_encapsulate_from_message,
    mlkem_encode_vector,
    mlkem_encode_poly,
    mlkem_hash_g,
    mlkem_hash_h,
    mlkem_hash_j,
    mlkem_inv_ntt,
    mlkem_keygen,
    mlkem_keygen_from_seeds,
    mlkem_kpke_decode_ciphertext,
    mlkem_kpke_decrypt,
    mlkem_kpke_encrypt,
    mlkem_kpke_keygen_from_seed,
    mlkem_matrix_vector_ntt,
    mlkem_mul,
    mlkem_multiply_ntts,
    mlkem_ntt,
    mlkem_parameter_set,
    mlkem_poly_add,
    mlkem_poly_compress,
    mlkem_poly_decompress,
    mlkem_poly_negacyclic_mul,
    mlkem_poly_sub,
    mlkem_prf,
    mlkem_reduce,
    mlkem_sample_matrix_ntt,
    mlkem_sample_poly_cbd,
    mlkem_sample_ntt,
    mlkem_sub,
    mlkem_vector_dot_ntt,
    mlkem_vector_inv_ntt,
    mlkem_vector_ntt,
    mlkem_xof,
    mldsa_add,
    mldsa_bit_pack,
    mldsa_bit_unpack,
    mldsa_centered_reduce,
    mldsa_decode_bounded_poly,
    mldsa_decode_hint_vector,
    mldsa_decode_poly,
    mldsa_decode_signature,
    mldsa_decode_signature_z_poly,
    mldsa_decode_signing_key,
    mldsa_decode_t0_poly,
    mldsa_decode_t1_poly,
    mldsa_decode_verification_key,
    mldsa_decompose,
    mldsa_derive_reference_keypair,
    mldsa_derive_verification_key_from_signing_key,
    mldsa_encode_bounded_poly,
    mldsa_encode_hint_vector,
    mldsa_encode_poly,
    mldsa_encode_signature,
    mldsa_encode_signature_z_poly,
    mldsa_encode_signing_key,
    mldsa_encode_t0_poly,
    mldsa_encode_t1_poly,
    mldsa_encode_verification_key,
    mldsa_expand_matrix_ntt,
    mldsa_expand_keygen_seed,
    mldsa_expand_short_vector,
    mldsa_high_bits,
    mldsa_low_bits,
    mldsa_make_hint,
    mldsa_key_equation_reference,
    mldsa_matrix_vector_mul,
    mldsa_mul,
    mldsa_parameter_set,
    mldsa_poly_add,
    mldsa_poly_negacyclic_mul,
    mldsa_poly_sub,
    mldsa_power2round,
    mldsa_power2round_vector,
    mldsa_reduce,
    mldsa_rejection_sample_ntt_poly,
    mldsa_reference_sign,
    mldsa_reference_verify,
    mldsa_sample_in_ball,
    mldsa_sample_bounded_poly,
    mldsa_shake128,
    mldsa_shake256,
    mldsa_sub,
    mldsa_use_hint,
    mldsa_vector_add,
    mldsa_vector_dot,
    mldsa_validate_signature,
    mldsa_validate_signing_key,
    mldsa_validate_verification_key,
    MtuPathProbeResult,
    MtuProbeAttempt,
    MtuProbePolicy,
    MtuProbeResult,
    MtuValidationEvidence,
    MetricsSnapshot,
    OperationalEvidenceError,
    OperatorApproval,
    PacketFragment,
    PacketFragmenter,
    PacketReassembler,
    PathMtuCache,
    POLICY_SNAPSHOT_REQUEST,
    PolicyDistributionError,
    PolicyRefreshClient,
    PolicySnapshot,
    PolicySnapshotDistributor,
    PolicySnapshotFetchClient,
    PolicySnapshotReceiver,
    PolicySnapshotServerHandler,
    PolicyStoreError,
    PrivacySafeAuditEvent,
    PrivacySafeAuditLog,
    PqcEncapsulationResult,
    PqcImplementationManifest,
    PqcKatResult,
    PqcKnownAnswerVector,
    PqcManifestProductionGate,
    PqcSessionMaterial,
    PqcProductionGate,
    PqcProviderAttestation,
    PqcProviderError,
    PqcProviderGateDecision,
    PqcSessionSecretMaterial,
    pqc_kem_profile,
    ProductionControlPlaneError,
    ProductionIdentitySignerGate,
    ProductionIdentitySignerGateDecision,
    ReplayWindow,
    RemoteEndpoint,
    RevocationList,
    ReadOnlyIdentityVerifier,
    RuntimeDrop,
    RuntimeStats,
    StreamRecordError,
    RolloutGateDecision,
    RolloutPlan,
    TeslaAuthError,
    TestEvidence,
    TunBridgeStats,
    TunDataplaneProbeResult,
    TunDataplaneValidationEvidence,
    TunPacketError,
    TunPumpStats,
    WireCodec,
    ZeroTrustAdmissionError,
    ZeroTrustPolicy,
    ZeroTrustPolicyEvidence,
    accept_firstparty_handshake,
    accept_firstparty_rekey,
    assert_privacy_safe,
    audit_firstparty_source_tree,
    complete_firstparty_handshake,
    complete_firstparty_rekey,
    build_firstparty_admission_vpn_activators,
    build_firstparty_admission_tun_client_activators,
    build_firstparty_admission_tun_server_activator,
    build_firstparty_admission_tun_server_activators,
    build_firstparty_admission_tun_server_pool_activator,
    build_firstparty_dataplane_activator,
    build_linux_post_apply_validator,
    build_linux_tun_activator,
    build_firstparty_vpn_deployment_packet,
    collect_linux_applied_state_snapshot,
    collect_linux_host_facts,
    compose_firstparty_dataplane_activators,
    compose_firstparty_tun_activators,
    create_firstparty_handshake_hello,
    create_firstparty_rekey_request,
    create_production_identity_authority,
    derive_session_keys,
    encode_camouflage_admission_request,
    encode_camouflage_request,
    encode_stream_record,
    establish_firstparty_session,
    establish_firstparty_session_from_pqc_provider,
    establish_firstparty_session_from_pqc_provider_and_signed_identities,
    establish_firstparty_session_from_signed_identities,
    establish_firstparty_session_from_policy_snapshot,
    evaluate_dataplane_validation,
    evaluate_firstparty_vpn_deployment_host_fingerprint,
    evaluate_firstparty_vpn_deployment_plan_hashes,
    evaluate_firstparty_vpn_deployment_rollout_gate,
    evaluate_tun_dataplane_validation,
    evaluate_full_vpn_production_readiness,
    evaluate_mtu_validation,
    evaluate_firstparty_rekey_policy,
    evaluate_linux_applied_state,
    evaluate_linux_deployment_preflight,
    evaluate_linux_leak_protection,
    evaluate_rollout_gate,
    hash_identifier,
    identity_binding_hash,
    mtu_path_id,
    open_tcp_admission_client,
    open_tcp_admission_server,
    open_tcp_client,
    open_tcp_multi_session_server,
    open_tcp_server,
    open_camouflage_admission_client,
    open_camouflage_admission_server,
    open_camouflage_client,
    open_camouflage_multi_session_server,
    open_camouflage_server,
    open_firstparty_admission_dataplane_client,
    open_firstparty_dataplane_client,
    open_firstparty_admission_dataplane_service,
    open_firstparty_dataplane_service,
    open_firstparty_multi_session_dataplane_service,
    open_firstparty_admission_tun_client_bridge,
    open_firstparty_admission_tun_client_pump,
    open_threaded_firstparty_dataplane_service,
    open_firstparty_tun_client_bridge,
    open_firstparty_tun_client_pump,
    open_threaded_firstparty_admission_tun_server,
    open_threaded_firstparty_admission_tun_client_pump,
    open_threaded_firstparty_tun_client_pump,
    open_threaded_firstparty_multi_session_tun_server,
    open_threaded_firstparty_tun_server,
    open_udp_admission_client,
    open_udp_admission_server,
    open_udp_client,
    open_udp_multi_session_server,
    open_udp_server,
    perform_firstparty_transport_rekey,
    probe_firstparty_mtu,
    redact_command,
    run_pqc_known_answer_tests,
    run_identity_signer_known_answer_tests,
)


NOW = 1_800_000_000


def claims(workload: str = "vpn-client", tenant: str = "team-a") -> IdentityClaims:
    return IdentityClaims(
        spiffe_id=f"spiffe://x0tta6bl4.mesh/workload/{workload}/node-1",
        did="did:mesh:pqc:node-1:key-1",
        workload=workload,
        tenant=tenant,
        device_id="device-1",
        pqc_kem_algorithm="ML-KEM-768",
        pqc_signature_algorithm="ML-DSA-65",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
        policy_epoch="epoch-1",
    )


def signing_key(key_id: str = "id-key-1") -> IdentitySigningKey:
    return IdentitySigningKey(
        key_id=key_id,
        signature_algorithm="ML-DSA-65",
        secret=f"{key_id}-secret".encode("utf-8").ljust(32, b"-"),
    )


def deterministic_mldsa_signing_key_bytes(key_id: str) -> bytes:
    seed = hashlib.shake_256(
        f"{key_id}-firstparty-mldsa-reference-keygen".encode("utf-8")
    ).digest(ML_DSA_KEYGEN_SEED_BYTES)
    return mldsa_derive_reference_keypair(seed, "ML-DSA-65").signing_key


def deterministic_mldsa_signature_bytes(
    signature_algorithm: str,
    seed_material: bytes,
) -> bytes:
    params = mldsa_parameter_set(signature_algorithm)
    seed = hashlib.shake_256(
        b"x0vpn-test-mldsa-signature-shape-v1" + seed_material
    ).digest(64)
    challenge = hashlib.shake_256(b"challenge" + seed).digest(
        params.signature_challenge_bytes
    )
    bound = params.gamma1 - params.beta
    z_stream = hashlib.shake_256(b"z" + seed).digest(params.l * ML_DSA_N * 4)
    z = tuple(
        tuple(
            (
                int.from_bytes(
                    z_stream[
                        (row * ML_DSA_N + coefficient)
                        * 4 : (row * ML_DSA_N + coefficient + 1)
                        * 4
                    ],
                    "little",
                )
                % (2 * bound + 1)
            )
            - bound
            for coefficient in range(ML_DSA_N)
        )
        for row in range(params.l)
    )
    hints = tuple((0,) * ML_DSA_N for _ in range(params.k))
    return mldsa_encode_signature(challenge, z, hints, params)


def production_signing_key(key_id: str = "prod-id-key-1") -> IdentitySigningKey:
    return IdentitySigningKey(
        key_id=key_id,
        signature_algorithm="ML-DSA-65",
        secret=deterministic_mldsa_signing_key_bytes(key_id),
    )


def identity_authority() -> IdentityAuthority:
    return IdentityAuthority(
        issuer="x0tta6bl4-test-issuer",
        policy_epoch="epoch-1",
        signing_keys=(signing_key("id-key-1"),),
        active_key_id="id-key-1",
    )


def issue_request(
    workload: str = "vpn-client",
    *,
    attributes: dict[str, str] | None = None,
) -> IdentityIssueRequest:
    return IdentityIssueRequest(
        spiffe_id=f"spiffe://x0tta6bl4.mesh/workload/{workload}/node-1",
        did=f"did:mesh:pqc:{workload}:key-1",
        workload=workload,
        tenant="team-a",
        device_id=f"{workload}-device-1",
        attributes=attributes or {},
    )


def session_material() -> PqcSessionMaterial:
    client = claims("vpn-client")
    server = claims("vpn-server")
    return PqcSessionMaterial.create(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        transcript=b"hello|accept|pqc-ciphertext",
        client_identity_hash=identity_binding_hash(client),
        server_identity_hash=identity_binding_hash(server),
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )


class FakeProbeClient:
    def __init__(self, *, fail_sizes: set[int] | None = None) -> None:
        self.fail_sizes = fail_sizes or set()
        self.last_payload = b""

    def send_ping(self, payload: bytes = b"") -> None:
        self.last_payload = payload

    async def recv(self, timeout: float = 1.0) -> Frame:
        if len(self.last_payload) in self.fail_sizes:
            raise TimeoutError("probe failed")
        return Frame(
            frame_type=FrameType.PONG,
            session_id=0,
            sequence=0,
            payload=self.last_payload,
        )


class FakeTunClient:
    def __init__(self) -> None:
        self.sent_payloads: tuple[bytes, ...] = ()

    def send_data_fragments(self, payloads: tuple[bytes, ...]) -> None:
        self.sent_payloads = payloads

    async def recv(self, timeout: float = 1.0) -> Frame:
        raise TimeoutError("not used")

    async def drain(self) -> None:
        return None


def ip_like_response(prefix: bytes, packet: bytes) -> bytes:
    return ipv4_packet(prefix + packet[20:])


def ip_like_response_from_probe(packet: bytes) -> bytes:
    payload = packet[20:]
    return b"".join(
        (
            b"\x45\x00",
            (20 + len(payload)).to_bytes(2, "big"),
            b"\x00\x00",
            b"\x00\x00",
            b"\x40",
            b"\x11",
            b"\x00\x00",
            b"\x0a\x4d\x00\x02",
            b"\x0a\x4d\x00\x01",
            bytes([payload[0] ^ 0xFF]) + payload[1:],
        )
    )


def ipv4_packet(payload: bytes = b"") -> bytes:
    total_length = 20 + len(payload)
    return b"".join(
        (
            b"\x45\x00",
            total_length.to_bytes(2, "big"),
            b"\x00\x00",
            b"\x00\x00",
            b"\x40",
            b"\x11",
            b"\x00\x00",
            b"\x0a\x00\x00\x01",
            b"\x0a\x00\x00\x02",
            payload,
        )
    )


def ipv6_packet(payload: bytes = b"") -> bytes:
    return b"".join(
        (
            b"\x60\x00\x00\x00",
            len(payload).to_bytes(2, "big"),
            b"\x11",
            b"\x40",
            b"\x20\x01\x0d\xb8" + b"\x00" * 12,
            b"\x20\x01\x0d\xb8" + b"\x00" * 11 + b"\x01",
            payload,
        )
    )


class FakePolicySnapshotTransport:
    def __init__(self, response: Frame) -> None:
        self.response = response
        self.sent_payloads: tuple[bytes, ...] = ()

    def send_data(self, payload: bytes) -> None:
        self.sent_payloads = (*self.sent_payloads, payload)

    async def drain(self) -> None:
        return None

    async def recv(self, timeout: float = 1.0) -> Frame:
        return self.response


async def _successful_probe_result(probe: DataplaneProbeSpec) -> DataplaneProbeResult:
    return DataplaneProbeResult.success_result(
        probe,
        latency_millis=7,
        rx_frames=1,
        tx_frames=1,
        rx_bytes=64,
        tx_bytes=64,
    )


def _successful_tun_probe_result(probe: DataplaneProbeSpec) -> TunDataplaneProbeResult:
    return TunDataplaneProbeResult.success_result(
        probe,
        packets_from_tun=1,
        packets_to_tun=1,
        bytes_from_tun=80,
        bytes_to_tun=80,
        tx_fragments=1,
        rx_fragments=1,
    )


def _successful_mtu_probe_result(probe: DataplaneProbeSpec) -> MtuPathProbeResult:
    return MtuPathProbeResult.success_result(
        probe,
        MtuProbeResult(
            selected_payload_size=1200,
            selected_fragment_payload_size=1136,
            attempts=(
                MtuProbeAttempt(payload_size=1400, success=False, error="timeout"),
                MtuProbeAttempt(payload_size=1200, success=True),
            ),
        ),
    )


async def complete_deployment_evidence(
    tmp_path: Path,
    *,
    target: str = "nl",
    approval: bool = True,
    required_paths: frozenset[str] = frozenset(
        {"lan", "vps", "mobile", "restricted-work-wifi"}
    ),
) -> FirstPartyVpnDeploymentEvidence:
    probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"deploy-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"deploy-remote-{path_label}",
        )
        for path_label, transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "camouflage"),
        )
        if path_label in required_paths
    )
    dataplane = await evaluate_dataplane_validation(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_paths,
            min_successful_probes=len(probes),
        ),
        runner=_successful_probe_result,
        captured_at=NOW,
    )
    tun_dataplane = TunDataplaneValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_paths,
            min_successful_probes=len(probes),
        ),
        results=tuple(_successful_tun_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )
    mtu_validation = MtuValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_paths,
            min_successful_probes=len(probes),
        ),
        results=tuple(_successful_mtu_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )
    snapshot = PolicySnapshot(policy_epoch="epoch-prod", issued_at=NOW)
    source_path = tmp_path / "deployment-policy.json"
    source_path.write_text(json.dumps(snapshot.to_json_dict()), encoding="utf-8")
    policy_source = ExternalPolicySnapshotSource(
        source_id="deployment-policy-control-plane",
        path=source_path,
        expected_snapshot_hash=snapshot.snapshot_hash(),
        allowed_policy_epochs=frozenset({"epoch-prod"}),
        minimum_issued_at=NOW,
        now_provider=lambda: NOW,
    )
    policy_source.load()
    assert policy_source.last_evidence is not None
    rollback = FirstPartyRekeyRollbackEvidence.from_session_bindings(
        rollback_id="deployment-rollback",
        previous_session_id=1,
        previous_transcript_hash=hashlib.sha256(b"deploy-previous").hexdigest(),
        next_session_id=2,
        next_transcript_hash=hashlib.sha256(b"deploy-next").hexdigest(),
        rollback_plan_id="deployment-rollback-plan",
        generated_at=NOW,
    )
    rekey = evaluate_firstparty_rekey_policy(
        FirstPartyRekeyCadencePolicy(max_session_age_seconds=1),
        FirstPartyRekeyTelemetry(session_started_at=NOW - 10, now=NOW, generation=2),
        requested_reason="scheduled-rotation",
        rollback_evidence=rollback,
    )
    operator_approval = (
        OperatorApproval(
            approval_id="deployment-approval",
            approved_by_hash=hash_identifier("operator-1", namespace="operator"),
            scope=target,
            issued_at=NOW - 60,
            expires_at=NOW + 600,
        )
        if approval
        else None
    )
    (
        identity_signer_manifest,
        identity_signer_kat,
        identity_signer_gate,
    ) = reviewed_identity_signer_evidence()
    identity_signer_conformance = reviewed_identity_signer_conformance_evidence(
        identity_signer_manifest,
        identity_signer_kat,
    )
    pqc_kat = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"deployment-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    pqc_manifest = reviewed_pqc_manifest(kat_hashes=(pqc_kat.suite_hash,))
    return FirstPartyVpnDeploymentEvidence(
        test_evidence=TestEvidence(
            command=("pytest", "tests/unit/network/test_firstparty_vpn_protocol_unit.py"),
            passed=99,
            failed=0,
            collected=99,
            generated_at=NOW,
        ),
        approval=operator_approval,
        policy_snapshot_hash=snapshot.snapshot_hash(),
        dataplane_validation=dataplane,
        tun_dataplane_validation=tun_dataplane,
        mtu_validation=mtu_validation,
        pqc_provider_gate=PqcProviderGateDecision(
            allowed=True,
            reasons=(),
            attestation_hash=pqc_manifest.to_attestation().attestation_hash(),
            provider_id="reviewed-firstparty-pqc",
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            implementation_hash="a" * 64,
        ),
        pqc_manifest=pqc_manifest,
        pqc_kat=pqc_kat,
        identity_signer_gate=identity_signer_gate,
        identity_signer_manifest=identity_signer_manifest,
        identity_signer_kat=identity_signer_kat,
        identity_signer_conformance=identity_signer_conformance,
        external_policy_source=policy_source.last_evidence,
        rekey_policy=rekey,
        zero_trust_policy=ZeroTrustPolicyEvidence.from_policy(
            ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
        ),
        source_audit=audit_firstparty_source_tree(
            Path(__file__).resolve().parents[3] / "src/network/firstparty_vpn",
            captured_at=NOW,
        ),
    )


async def build_test_deployment_packet(
    tmp_path: Path,
    *,
    approval: bool = True,
    ready_host: bool = True,
) -> FirstPartyVpnDeploymentPacket:
    evidence = await complete_deployment_evidence(tmp_path, approval=approval)
    config = FirstPartyVpnDeploymentConfig(
        client_network=LinuxNetworkPolicyConfig(dns_servers=("9.9.9.9",)),
        expected_test_count=99,
        dataplane_probe_matrix_hash=evidence.dataplane_validation.probe_matrix_hash(),
        pqc_manifest_hash=evidence.pqc_manifest.manifest_hash(),
        identity_signer_manifest_hash=evidence.identity_signer_manifest.manifest_hash(),
        external_policy_source_hash=evidence.external_policy_source.evidence_hash(),
        policy_snapshot_hash=evidence.policy_snapshot_hash,
        zero_trust_policy_hash=evidence.zero_trust_policy.policy_hash,
        source_audit_root_hash=evidence.source_audit.root_hash,
        source_audit_tree_hash=evidence.source_audit.source_tree_hash,
        rekey_rollback_plan_hash=evidence.rekey_policy.rollback_plan_hash,
    )
    plan_hashes = evaluate_firstparty_vpn_deployment_plan_hashes(config)
    facts = LinuxHostFacts(
        os_name="Linux",
        kernel_release="6.8.0-x0vpn",
        effective_uid=0 if ready_host else 1000,
        has_net_admin=ready_host,
    )
    path_exists = lambda _path: ready_host
    binary_exists = lambda _binary: ready_host
    config = replace(
        config,
        linux_host_fingerprint=evaluate_firstparty_vpn_deployment_host_fingerprint(
            config=config,
            facts=facts,
            path_exists=path_exists,
            binary_exists=binary_exists,
        ),
        apply_plan_hash=plan_hashes.apply_plan_hash,
        rollback_plan_hash=plan_hashes.rollback_plan_hash,
        leak_protection_plan_hash=plan_hashes.leak_protection_plan_hash,
    )
    rollout_decision = evaluate_firstparty_vpn_deployment_rollout_gate(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )
    return build_firstparty_vpn_deployment_packet(
        config=replace(
            config,
            rollout_gate_hash=rollout_decision.decision_hash(),
        ),
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )


def successful_post_apply_evidence() -> LinuxAppliedStateEvidence:
    return LinuxAppliedStateEvidence(
        controls=(
            "client_tun_observed",
            "server_tun_observed",
            "full_tunnel_route_observed",
            "tun_dns_observed",
            "kill_switch_observed",
            "server_forwarding_observed",
            "server_vpn_listener_observed",
            "server_nat_observed",
        ),
        reasons=(),
        snapshot_hash=hashlib.sha256(b"successful-post-apply").hexdigest(),
        captured_at=NOW,
    )


class InMemoryTunActivationResource:
    def close(self) -> None:
        return None


class InMemoryDataplaneActivationResource:
    def close(self) -> None:
        return None


def successful_tun_activation(
    _packet: FirstPartyVpnDeploymentPacket,
) -> FirstPartyVpnTunActivationResult:
    return FirstPartyVpnTunActivationResult(
        count=1,
        resources=(InMemoryTunActivationResource(),),
    )


def successful_dataplane_activation(
    _packet: FirstPartyVpnDeploymentPacket,
) -> FirstPartyVpnDataplaneActivationResult:
    return FirstPartyVpnDataplaneActivationResult(
        count=1,
        resources=(InMemoryDataplaneActivationResource(),),
    )


class FakeReviewedIdentitySignatureProvider:
    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        seed = hmac.new(
            key.secret,
            b"x0vpn-reviewed-fake-identity-signer-v1"
            + key.key_id.encode("utf-8")
            + payload,
            hashlib.sha256,
        ).digest()
        return deterministic_mldsa_signature_bytes(key.signature_algorithm, seed)

    def verify(
        self,
        key: IdentitySigningKey,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        return hmac.compare_digest(self.sign(key, payload), signature)


class ShortReviewedIdentitySignatureProvider(FakeReviewedIdentitySignatureProvider):
    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        return hmac.new(
            key.secret,
            b"x0vpn-reviewed-short-identity-signer-v1" + payload,
            hashlib.sha256,
        ).digest()


class MalformedReviewedIdentitySignatureProvider(FakeReviewedIdentitySignatureProvider):
    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        return b"\x00" * mldsa_parameter_set(key.signature_algorithm).signature_bytes


class FakeProductionPqcProvider:
    def __init__(
        self,
        *,
        provider_id: str = "reviewed-firstparty-pqc",
        implementation_hash: str = "pqc-implementation-hash-1",
    ) -> None:
        self.attestation = PqcProviderAttestation(
            provider_id=provider_id,
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            mode="production",
            reviewed=True,
            issued_at=NOW - 60,
            expires_at=NOW + 3600,
            implementation_hash=implementation_hash,
        )

    def create_session_material(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcSessionSecretMaterial:
        secret = hashlib.sha256(
            b"reviewed-production-pqc-secret"
            + transcript
            + client_identity_hash
            + server_identity_hash
        ).digest()
        ciphertext = hashlib.shake_256(
            b"reviewed-production-pqc-ciphertext"
            + secret
            + transcript
            + client_identity_hash
            + server_identity_hash
        ).digest(pqc_kem_profile("ML-KEM-768").ciphertext_bytes)
        return PqcSessionSecretMaterial(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            shared_secret=secret,
            ciphertext=ciphertext,
            attestation=self.attestation,
        )


class FakeFirstPartyPqcImplementation:
    provider_id = "reviewed-firstparty-pqc"
    implementation_hash = "a" * 64
    kem_algorithm = "ML-KEM-768"
    signature_algorithm = "ML-DSA-65"

    def encapsulate(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcEncapsulationResult:
        secret = hmac.new(
            b"fake-firstparty-pqc-implementation".ljust(32, b"-"),
            b"kat"
            + transcript
            + client_identity_hash
            + server_identity_hash,
            hashlib.sha256,
        ).digest()
        ciphertext = hashlib.shake_256(
            b"kat-ciphertext" + secret + transcript
        ).digest(pqc_kem_profile(self.kem_algorithm).ciphertext_bytes)
        return PqcEncapsulationResult(shared_secret=secret, ciphertext=ciphertext)


def reviewed_pqc_manifest(
    *,
    implementation_hash: str = "a" * 64,
    kat_hashes: tuple[str, ...] = ("c" * 64,),
) -> PqcImplementationManifest:
    return PqcImplementationManifest(
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        mode="production",
        reviewed=True,
        implementation_hash=implementation_hash,
        source_hashes=("b" * 64,),
        kat_hashes=kat_hashes,
        review_evidence_hash="d" * 64,
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
    )


def identity_signer_kat_vector(
    signature_provider: FakeReviewedIdentitySignatureProvider,
    signing_key: IdentitySigningKey,
    *,
    expected_signature_hash: str | None = None,
) -> IdentitySignerKnownAnswerVector:
    payload = b"firstparty-identity-signer-kat-payload-v1"
    signature = signature_provider.sign(signing_key, payload)
    return IdentitySignerKnownAnswerVector(
        vector_id="identity-signer-kat-1",
        key_id=signing_key.key_id,
        signature_algorithm=signing_key.signature_algorithm,
        payload=payload,
        expected_signature_hash=(
            expected_signature_hash or hashlib.sha256(signature).hexdigest()
        ),
    )


def reviewed_identity_signer_manifest(
    *,
    key_id: str = "prod-id-key-1",
    implementation_hash: str | None = None,
    kat_hashes: tuple[str, ...] = ("e" * 64,),
) -> FirstPartyIdentitySignerManifest:
    return FirstPartyIdentitySignerManifest(
        provider_id="reviewed-firstparty-identity-signer",
        key_id=key_id,
        signature_algorithm="ML-DSA-65",
        mode="production",
        reviewed=True,
        implementation_hash=(
            implementation_hash
            or hashlib.sha256(b"reviewed-identity-signer").hexdigest()
        ),
        source_hashes=(hashlib.sha256(b"identity-signer-source").hexdigest(),),
        kat_hashes=kat_hashes,
        review_evidence_hash=hashlib.sha256(
            b"identity-signer-review-evidence"
        ).hexdigest(),
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
    )


def reviewed_identity_signer_evidence(
    *,
    key_id: str = "prod-id-key-1",
    implementation_hash: str | None = None,
) -> tuple[
    FirstPartyIdentitySignerManifest,
    IdentitySignerKatResult,
    ProductionIdentitySignerGateDecision,
]:
    key = production_signing_key(key_id)
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    vector = identity_signer_kat_vector(provider, key)
    kat_result = run_identity_signer_known_answer_tests(
        provider,
        key,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_identity_signer_manifest(
        key_id=key.key_id,
        implementation_hash=implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({manifest.provider_id}),
        trusted_implementation_hashes=frozenset({manifest.implementation_hash}),
    )
    decision = gate.evaluate(manifest.to_attestation(), signing_key=key, now=NOW)
    return manifest, kat_result, decision


def reviewed_identity_signer_conformance_evidence(
    manifest: FirstPartyIdentitySignerManifest,
    kat_result: IdentitySignerKatResult,
    *,
    profile: str = "fips204-production",
    passed: bool = True,
    vector_count: int | None = None,
    reasons: tuple[str, ...] = (),
) -> IdentitySignerConformanceEvidence:
    return IdentitySignerConformanceEvidence(
        provider_id=manifest.provider_id,
        key_id=manifest.key_id,
        signature_algorithm=manifest.signature_algorithm,
        implementation_hash=manifest.implementation_hash,
        manifest_hash=manifest.manifest_hash(),
        kat_suite_hash=kat_result.suite_hash,
        profile=profile,  # type: ignore[arg-type]
        passed=passed,
        vector_count=kat_result.vector_count if vector_count is None else vector_count,
        review_evidence_hash=manifest.review_evidence_hash,
        reasons=reasons,
    )


def pqc_kat_vector(
    implementation: PqcAlgorithmImplementation,
    *,
    expected_shared_secret_hash: str | None = None,
) -> PqcKnownAnswerVector:
    transcript = b"firstparty-pqc-kat-transcript-v1"
    client_hash = b"c" * 32
    server_hash = b"s" * 32
    result = implementation.encapsulate(
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    return PqcKnownAnswerVector(
        vector_id="kat-1",
        kem_algorithm=implementation.kem_algorithm,
        signature_algorithm=implementation.signature_algorithm,
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
        expected_shared_secret_hash=(
            expected_shared_secret_hash
            or hashlib.sha256(result.shared_secret).hexdigest()
        ),
        expected_ciphertext_hash=hashlib.sha256(result.ciphertext).hexdigest(),
    )


def test_zero_trust_policy_allows_valid_pqc_identity() -> None:
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    decision = policy.evaluate(claims(), now=NOW)

    assert decision.allowed is True
    assert decision.reasons == ()
    assert len(decision.identity_hash) == 32


def test_zero_trust_policy_evidence_is_privacy_safe_and_hashed() -> None:
    evidence = ZeroTrustPolicyEvidence.from_policy(
        ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    )
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.allowed_tenant_count == 1
    assert len(evidence.policy_hash) == 64
    assert len(evidence.evidence_hash()) == 64
    assert "team-a" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


def test_zero_trust_policy_fails_closed_for_bad_domain_and_expiry() -> None:
    bad = IdentityClaims(
        spiffe_id="spiffe://other.mesh/workload/vpn-client/node-1",
        did="did:mesh:pqc:node-1:key-1",
        workload="vpn-client",
        tenant="team-a",
        device_id="device-1",
        pqc_kem_algorithm="ML-KEM-768",
        pqc_signature_algorithm="ML-DSA-65",
        issued_at=NOW - 7200,
        expires_at=NOW - 1,
        policy_epoch="epoch-1",
    )

    decision = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})).evaluate(
        bad,
        now=NOW,
    )

    assert decision.allowed is False
    assert "spiffe_trust_domain_mismatch" in decision.reasons
    assert "identity_expired" in decision.reasons


def test_identity_authority_issues_and_verifies_signed_identity() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    token = authority.issue(issue_request("vpn-client"), now=NOW)
    decision = authority.verify(token, policy=policy, now=NOW)

    assert decision.allowed is True
    assert decision.reasons == ()
    assert token.claims.issued_at == NOW
    assert token.claims.expires_at == NOW + 600
    assert token.claims.policy_epoch == "epoch-1"
    assert token.key_id == "id-key-1"


def test_identity_authority_fails_closed_for_bad_signature_and_revocation() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    revocations = RevocationList()
    token = authority.issue(issue_request("vpn-client"), now=NOW)
    tampered = replace(token, signature=b"\x00" * 32)

    bad_signature = authority.verify(tampered, policy=policy, now=NOW)
    assert bad_signature.allowed is False
    assert "identity_signature_invalid" in bad_signature.reasons

    revocations.revoke_identity(token)
    revoked = authority.verify(
        token,
        policy=policy,
        revocations=revocations,
        now=NOW,
    )
    assert revoked.allowed is False
    assert "identity_revoked" in revoked.reasons


def test_readonly_identity_verifier_has_no_issuance_or_rotation_surface() -> None:
    key = signing_key("id-key-1")
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(key,),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    token = authority.issue(issue_request("vpn-client"), now=NOW)

    decision = verifier.verify(token, policy=policy, now=NOW)
    tampered = verifier.verify(
        replace(token, signature=b"\x00" * len(token.signature)),
        policy=policy,
        now=NOW,
    )

    assert decision.allowed is True
    assert tampered.allowed is False
    assert "identity_signature_invalid" in tampered.reasons
    assert not hasattr(verifier, "issue")
    assert not hasattr(verifier, "rotate_signing_key")
    assert not hasattr(verifier, "rotate_policy_epoch")
    assert not hasattr(verifier, "revoke_identity")


def test_identity_authority_rotates_key_and_policy_epoch() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    revocations = RevocationList()
    old_token = authority.issue(issue_request("vpn-client"), now=NOW)

    previous_key = authority.rotate_signing_key(
        signing_key("id-key-2"),
        revoke_previous=False,
    )
    new_token = authority.issue(issue_request("vpn-client"), now=NOW + 1)

    assert previous_key == "id-key-1"
    assert new_token.key_id == "id-key-2"
    assert authority.verify(old_token, policy=policy, now=NOW + 1).allowed is True
    assert authority.verify(new_token, policy=policy, now=NOW + 1).allowed is True

    authority.rotate_signing_key(
        signing_key("id-key-3"),
        revoke_previous=True,
        revocations=revocations,
    )
    key_revoked = authority.verify(
        new_token,
        policy=policy,
        revocations=revocations,
        now=NOW + 2,
    )
    assert "identity_key_revoked" in key_revoked.reasons

    token_before_policy_rotate = authority.issue(issue_request("vpn-client"), now=NOW + 2)
    previous_epoch = authority.rotate_policy_epoch(
        "epoch-2",
        revoke_previous=True,
        revocations=revocations,
    )
    token_after_policy_rotate = authority.issue(issue_request("vpn-client"), now=NOW + 3)

    assert previous_epoch == "epoch-1"
    assert token_after_policy_rotate.claims.policy_epoch == "epoch-2"
    epoch_revoked = authority.verify(
        token_before_policy_rotate,
        policy=policy,
        revocations=revocations,
        now=NOW + 3,
    )
    assert "policy_epoch_revoked" in epoch_revoked.reasons


def test_durable_identity_backend_restores_serial_counter_after_restart(
    tmp_path: Path,
) -> None:
    store = DurableIdentityBackendStore(tmp_path / "identity-backend.json")
    key = signing_key("id-key-1")
    backend = DurableIdentityBackend(
        store=store,
        issuer="x0tta6bl4-test-issuer",
        signing_keys=(key,),
        active_key_id="id-key-1",
        policy_epoch="epoch-1",
    )
    first_token = backend.issue(issue_request("vpn-client"), now=NOW)

    restarted = DurableIdentityBackend(
        store=store,
        issuer="x0tta6bl4-test-issuer",
        signing_keys=(key,),
        active_key_id="id-key-1",
        policy_epoch="ignored-if-state-exists",
    )
    second_token = restarted.issue(issue_request("vpn-client"), now=NOW + 1)

    assert first_token.serial != second_token.serial
    assert restarted.state.serial_counter == 2
    assert store.load().serial_counter == 2
    assert restarted.verify(
        second_token,
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW + 1,
    ).allowed is True


def test_durable_identity_backend_persists_rotation_and_revocations(
    tmp_path: Path,
) -> None:
    store = DurableIdentityBackendStore(tmp_path / "identity-backend.json")
    key1 = signing_key("id-key-1")
    key2 = signing_key("id-key-2")
    backend = DurableIdentityBackend(
        store=store,
        issuer="x0tta6bl4-test-issuer",
        signing_keys=(key1,),
        active_key_id="id-key-1",
        policy_epoch="epoch-1",
    )
    old_token = backend.issue(issue_request("vpn-client"), now=NOW)
    backend.rotate_signing_key(key2, revoke_previous=True)
    backend.rotate_policy_epoch("epoch-2", revoke_previous=True)
    new_token = backend.issue(issue_request("vpn-client"), now=NOW + 1)
    backend.revoke_identity(new_token)

    restarted = DurableIdentityBackend(
        store=store,
        issuer="x0tta6bl4-test-issuer",
        signing_keys=(key1, key2),
        active_key_id="id-key-1",
        policy_epoch="ignored-if-state-exists",
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    assert restarted.authority.active_key_id == "id-key-2"
    assert restarted.authority.policy_epoch == "epoch-2"
    assert "identity_key_revoked" in restarted.verify(
        old_token,
        policy=policy,
        now=NOW + 2,
    ).reasons
    assert "identity_revoked" in restarted.verify(
        new_token,
        policy=policy,
        now=NOW + 2,
    ).reasons


def test_durable_identity_backend_rejects_tampered_state(tmp_path: Path) -> None:
    store = DurableIdentityBackendStore(tmp_path / "identity-backend.json")
    key = signing_key("id-key-1")
    backend = DurableIdentityBackend(
        store=store,
        issuer="x0tta6bl4-test-issuer",
        signing_keys=(key,),
        active_key_id="id-key-1",
        policy_epoch="epoch-1",
    )
    backend.issue(issue_request("vpn-client"), now=NOW)

    raw = store.path.read_text(encoding="utf-8")
    store.path.write_text(
        raw.replace('"serial_counter":1', '"serial_counter":0'),
        encoding="utf-8",
    )

    with pytest.raises(IdentityBackendError, match="state hash mismatch"):
        DurableIdentityBackend(
            store=store,
            issuer="x0tta6bl4-test-issuer",
            signing_keys=(key,),
            active_key_id="id-key-1",
            policy_epoch="epoch-1",
        )


def test_manifest_backed_identity_signer_runs_kat_and_creates_authority(
    tmp_path: Path,
) -> None:
    key = production_signing_key("prod-id-key-1")
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    vector = identity_signer_kat_vector(provider, key)
    kat_result = run_identity_signer_known_answer_tests(
        provider,
        key,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_identity_signer_manifest(
        key_id=key.key_id,
        kat_hashes=(kat_result.suite_hash,),
    )
    store = DurableIdentitySignerManifestStore(tmp_path / "identity-signer.json")

    store.save_all((manifest,))
    loaded = store.find(
        provider_id=manifest.provider_id,
        implementation_hash=manifest.implementation_hash,
        key_id=manifest.key_id,
    )
    wrapped = ManifestBackedIdentitySignatureProvider(
        signature_provider=provider,
        signing_key=key,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({manifest.provider_id}),
        trusted_implementation_hashes=frozenset({manifest.implementation_hash}),
    )
    authority = create_production_identity_authority(
        issuer="x0tta6bl4-prod-identity-authority",
        policy_epoch="epoch-prod",
        signing_key=key,
        signature_provider=wrapped,
        signer_attestation=wrapped.attestation,
        gate=gate,
        now=NOW,
    )
    token = authority.issue(issue_request("vpn-client"), now=NOW)

    assert kat_result.passed is True
    assert kat_result.reasons == ()
    assert loaded == manifest
    assert wrapped.kat_result.suite_hash == kat_result.suite_hash
    assert authority.verify(
        token,
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
    ).allowed is True

    raw = store.path.read_text(encoding="utf-8")
    store.path.write_text(
        raw.replace('"reviewed":true', '"reviewed":false'),
        encoding="utf-8",
    )
    with pytest.raises(ProductionControlPlaneError, match="manifest hash mismatch"):
        store.load_all()
    bad_vector = identity_signer_kat_vector(
        provider,
        key,
        expected_signature_hash="0" * 64,
    )
    with pytest.raises(ProductionControlPlaneError, match="KAT failed"):
        ManifestBackedIdentitySignatureProvider(
            signature_provider=provider,
            signing_key=key,
            manifest=manifest,
            kat_vectors=(bad_vector,),
        )
    with pytest.raises(ProductionControlPlaneError, match="local provider forbidden"):
        ManifestBackedIdentitySignatureProvider(
            signature_provider=LocalIdentitySignatureProvider(),
            signing_key=key,
            manifest=manifest,
            kat_vectors=(vector,),
        )


def test_production_identity_authority_rejects_local_signer_and_issues_with_attestation() -> None:
    implementation_hash = hashlib.sha256(b"reviewed-identity-signer").hexdigest()
    key = production_signing_key("prod-id-key-1")
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    vector = identity_signer_kat_vector(provider, key)
    kat_result = run_identity_signer_known_answer_tests(
        provider,
        key,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_identity_signer_manifest(
        key_id=key.key_id,
        implementation_hash=implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    wrapped = ManifestBackedIdentitySignatureProvider(
        signature_provider=provider,
        signing_key=key,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    attestation = wrapped.attestation
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({"reviewed-firstparty-identity-signer"}),
        trusted_implementation_hashes=frozenset({implementation_hash}),
    )
    decision = gate.evaluate(attestation, signing_key=key, now=NOW)

    assert isinstance(decision, ProductionIdentitySignerGateDecision)
    assert decision.allowed is True
    assert decision.reasons == ()
    assert_privacy_safe(attestation.to_json_dict())
    assert_privacy_safe(decision.to_json_dict())

    with pytest.raises(
        ProductionControlPlaneError,
        match="identity_signer_local_provider_forbidden",
    ):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=LocalIdentitySignatureProvider(),
            signer_attestation=attestation,
            gate=gate,
            now=NOW,
        )

    with pytest.raises(
        ProductionControlPlaneError,
        match="identity_signer_manifest_wrapper_required",
    ):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=provider,
            signer_attestation=attestation,
            gate=gate,
            now=NOW,
        )

    authority = create_production_identity_authority(
        issuer="x0tta6bl4-prod-identity-authority",
        policy_epoch="epoch-prod",
        signing_key=key,
        signature_provider=wrapped,
        signer_attestation=attestation,
        gate=gate,
        now=NOW,
    )
    token = authority.issue(issue_request("vpn-client"), now=NOW)

    assert authority.verify(
        token,
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
    ).allowed is True


def test_production_identity_authority_rechecks_manifest_wrapper_kat() -> None:
    implementation_hash = hashlib.sha256(b"reviewed-identity-signer").hexdigest()
    key = production_signing_key("prod-id-key-1")
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    vector = identity_signer_kat_vector(provider, key)
    kat_result = run_identity_signer_known_answer_tests(
        provider,
        key,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_identity_signer_manifest(
        key_id=key.key_id,
        implementation_hash=implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({manifest.provider_id}),
        trusted_implementation_hashes=frozenset({manifest.implementation_hash}),
    )
    wrapped = ManifestBackedIdentitySignatureProvider(
        signature_provider=provider,
        signing_key=key,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    wrapped.kat_result = replace(
        wrapped.kat_result,
        implementation_hash="f" * 64,
    )

    with pytest.raises(
        ProductionControlPlaneError,
        match="identity_signer_kat_implementation_mismatch",
    ):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=wrapped,
            signer_attestation=wrapped.attestation,
            gate=gate,
            now=NOW,
        )

    stale = ManifestBackedIdentitySignatureProvider(
        signature_provider=provider,
        signing_key=key,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW - 3601,
    )
    future = ManifestBackedIdentitySignatureProvider(
        signature_provider=provider,
        signing_key=key,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW + 1,
    )
    with pytest.raises(ProductionControlPlaneError, match="identity_signer_kat_stale"):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=stale,
            signer_attestation=stale.attestation,
            gate=gate,
            now=NOW,
        )
    with pytest.raises(
        ProductionControlPlaneError,
        match="identity_signer_kat_from_future",
    ):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=future,
            signer_attestation=future.attestation,
            gate=gate,
            now=NOW,
        )
    with pytest.raises(ProductionControlPlaneError, match="KAT max age"):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=key,
            signature_provider=future,
            signer_attestation=future.attestation,
            gate=gate,
            max_kat_age_seconds=0,
            now=NOW,
        )


def test_production_identity_signer_gate_rejects_invalid_mldsa_shapes() -> None:
    implementation_hash = hashlib.sha256(b"reviewed-identity-signer").hexdigest()
    short_key = signing_key("prod-id-key-1")
    production_key = production_signing_key("prod-id-key-1")
    attestation = FirstPartyIdentitySignerAttestation(
        provider_id="reviewed-firstparty-identity-signer",
        key_id=short_key.key_id,
        signature_algorithm=short_key.signature_algorithm,
        mode="production",
        reviewed=True,
        implementation_hash=implementation_hash,
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({"reviewed-firstparty-identity-signer"}),
        trusted_implementation_hashes=frozenset({implementation_hash}),
    )

    decision = gate.evaluate(attestation, signing_key=short_key, now=NOW)

    assert decision.allowed is False
    assert "identity_signing_key_length_invalid" in decision.reasons
    malformed_secret = bytearray(production_key.secret)
    malformed_secret[ML_DSA_RHO_BYTES + ML_DSA_KEY_BYTES + ML_DSA_TR_BYTES] = 0xFF
    malformed_key = replace(production_key, secret=bytes(malformed_secret))
    malformed_decision = gate.evaluate(
        replace(attestation, key_id=malformed_key.key_id),
        signing_key=malformed_key,
        now=NOW,
    )
    assert malformed_decision.allowed is False
    assert "identity_signing_key_format_invalid" in malformed_decision.reasons
    with pytest.raises(ProductionControlPlaneError, match="signature_length_invalid"):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=production_key,
            signature_provider=ShortReviewedIdentitySignatureProvider(),
            signer_attestation=replace(attestation, key_id=production_key.key_id),
            gate=gate,
            now=NOW,
        )
    with pytest.raises(ProductionControlPlaneError, match="signature_format_invalid"):
        create_production_identity_authority(
            issuer="x0tta6bl4-prod-identity-authority",
            policy_epoch="epoch-prod",
            signing_key=production_key,
            signature_provider=MalformedReviewedIdentitySignatureProvider(),
            signer_attestation=replace(attestation, key_id=production_key.key_id),
            gate=gate,
            now=NOW,
        )


def test_production_identity_signer_gate_fails_closed_for_untrusted_attestation() -> None:
    key = production_signing_key("prod-id-key-1")
    attestation = FirstPartyIdentitySignerAttestation(
        provider_id="unreviewed-identity-signer",
        key_id=key.key_id,
        signature_algorithm=key.signature_algorithm,
        mode="test",
        reviewed=False,
        implementation_hash=None,
        issued_at=NOW - 60,
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({"reviewed-firstparty-identity-signer"}),
        trusted_implementation_hashes=frozenset({hashlib.sha256(b"trusted").hexdigest()}),
    )
    decision = gate.evaluate(attestation, signing_key=key, now=NOW)

    assert decision.allowed is False
    assert "identity_signer_not_production" in decision.reasons
    assert "identity_signer_not_reviewed" in decision.reasons
    assert "identity_signer_implementation_hash_missing" in decision.reasons
    assert "identity_signer_provider_not_trusted" in decision.reasons


def test_durable_policy_store_round_trips_snapshot_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    revocations = RevocationList(
        identity_serials={"identity-1"},
        key_ids={"key-1"},
        policy_epochs={"epoch-old"},
    )
    snapshot = PolicySnapshot(
        policy_epoch="epoch-2",
        issued_at=NOW,
        revocations=revocations,
        posture_policy=DevicePosturePolicy(
            required_attributes={"posture_status": "healthy", "edr": "enabled"},
            max_posture_age_seconds=300,
        ),
    )
    store = DurablePolicyStore(tmp_path / "policy.json")

    store.save(snapshot)
    loaded = store.load()

    assert loaded.policy_epoch == "epoch-2"
    assert loaded.snapshot_hash() == snapshot.snapshot_hash()
    assert loaded.revocations.identity_serials == {"identity-1"}
    assert loaded.posture_policy.required_attributes["edr"] == "enabled"

    raw = store.path.read_text(encoding="utf-8")
    store.path.write_text(raw.replace("epoch-2", "epoch-x"), encoding="utf-8")
    with pytest.raises(PolicyStoreError):
        store.load()


def test_policy_refresh_client_persists_snapshot_and_blocks_time_rollback(
    tmp_path: Path,
) -> None:
    store = DurablePolicyStore(tmp_path / "policy.json")
    refresh = PolicyRefreshClient(store=store)
    newer = PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW + 10)
    older = PolicySnapshot(policy_epoch="epoch-1", issued_at=NOW)

    refresh.refresh_once(lambda: newer)
    loaded = refresh.load_current()

    assert loaded.policy_epoch == "epoch-2"
    with pytest.raises(PolicyStoreError):
        refresh.refresh_once(lambda: older)


def test_external_policy_snapshot_source_loads_privacy_safe_verified_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = PolicySnapshot(
        policy_epoch="epoch-prod",
        issued_at=NOW,
        revocations=RevocationList(key_ids={"old-prod-key"}),
        posture_policy=DevicePosturePolicy(
            required_attributes={"posture_status": "healthy"},
            max_posture_age_seconds=300,
        ),
    )
    source_path = tmp_path / "external-policy.json"
    source_path.write_text(json.dumps(snapshot.to_json_dict()), encoding="utf-8")
    source = ExternalPolicySnapshotSource(
        source_id="prod-policy-control-plane",
        path=source_path,
        expected_snapshot_hash=snapshot.snapshot_hash(),
        allowed_policy_epochs=frozenset({"epoch-prod"}),
        minimum_issued_at=NOW - 10,
        now_provider=lambda: NOW + 1,
    )

    loaded = source.load()

    assert loaded.snapshot_hash() == snapshot.snapshot_hash()
    assert loaded.revocations.key_ids == {"old-prod-key"}
    assert isinstance(source.last_evidence, ExternalPolicySnapshotSourceEvidence)
    assert source.last_evidence.snapshot_hash == snapshot.snapshot_hash()
    assert len(source.last_evidence.evidence_hash()) == 64
    assert_privacy_safe(source.last_evidence.to_json_dict())
    encoded = json.dumps(source.last_evidence.to_json_dict(), sort_keys=True)
    assert "prod-policy-control-plane" not in encoded
    assert str(source_path) not in encoded
    assert "epoch-prod" not in encoded


def test_external_policy_snapshot_source_fails_closed_for_hash_epoch_and_staleness(
    tmp_path: Path,
) -> None:
    snapshot = PolicySnapshot(policy_epoch="epoch-prod", issued_at=NOW)
    source_path = tmp_path / "external-policy.json"
    source_path.write_text(json.dumps(snapshot.to_json_dict()), encoding="utf-8")

    with pytest.raises(ProductionControlPlaneError, match="unexpected hash"):
        ExternalPolicySnapshotSource(
            source_id="prod-policy-control-plane",
            path=source_path,
            expected_snapshot_hash=hashlib.sha256(b"wrong").hexdigest(),
        ).load()

    with pytest.raises(ProductionControlPlaneError, match="epoch is not allowed"):
        ExternalPolicySnapshotSource(
            source_id="prod-policy-control-plane",
            path=source_path,
            allowed_policy_epochs=frozenset({"epoch-other"}),
        ).load()

    with pytest.raises(ProductionControlPlaneError, match="snapshot is stale"):
        ExternalPolicySnapshotSource(
            source_id="prod-policy-control-plane",
            path=source_path,
            minimum_issued_at=NOW + 1,
        ).load()


def test_firstparty_source_audit_passes_current_vpn_core() -> None:
    root = Path(__file__).resolve().parents[3] / "src/network/firstparty_vpn"

    evidence = audit_firstparty_source_tree(root)
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.passed is True
    assert evidence.reasons == ()
    assert evidence.scanned_files > 1
    assert len(evidence.source_tree_hash) == 64
    assert str(root) not in encoded
    assert_privacy_safe(evidence.to_json_dict())


def test_firstparty_source_audit_rejects_foreign_vpn_or_pqc_backend(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "bad_backend.py").write_text(
        "import oqs\n"
        "import importlib as dynamic_imports\n"
        "from importlib import import_module as import_backend\n"
        "client = __import__('requests')\n"
        "wg = dynamic_imports.import_module('wireguard.crypto')\n"
        "vpn = import_backend('pywireguard')\n"
        "BACKEND = 'wireguard-go'\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("requests" in item for item in evidence.external_imports)
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)


def test_firstparty_source_audit_rejects_split_literal_foreign_markers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "split_backend.py").write_text(
        "backend = __import__('wire' + 'guard.crypto')\n"
        "marker = 'open' + 'vpn'\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("openvpn" in item for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_constant_bound_dynamic_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "constant_backend.py").write_text(
        "from importlib import import_module\n"
        "import importlib as dynamic_imports\n"
        "WIREGUARD_BACKEND = 'wire' + 'guard.crypto'\n"
        "CLIENT_BACKEND: str = 'requests'\n"
        "PQC_BACKEND = 'lib' + 'oqs'\n"
        "wg = __import__(WIREGUARD_BACKEND)\n"
        "client = import_module(CLIENT_BACKEND)\n"
        "pqc = dynamic_imports.import_module(PQC_BACKEND)\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_builtin_import_aliases_and_fstrings(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "aliased_imports.py").write_text(
        "import builtins as runtime_imports\n"
        "from builtins import __import__ as import_backend\n"
        "WIRE_PREFIX = 'wire'\n"
        "WIREGUARD_BACKEND = f'{WIRE_PREFIX}guard.crypto'\n"
        "PQC_ROOT: str = 'lib'\n"
        "PQC_SUFFIX = 'oqs'\n"
        "PQC_BACKEND = f'{PQC_ROOT}{PQC_SUFFIX}'\n"
        "REQUESTS_PREFIX = 're'\n"
        "CLIENT_BACKEND = f'{REQUESTS_PREFIX}quests'\n"
        "SHADOW = b'shadow'\n"
        "SOCKS = b'socks'\n"
        "shadow_marker = SHADOW + SOCKS\n"
        "wg = runtime_imports.__import__(WIREGUARD_BACKEND)\n"
        "pqc = import_backend(PQC_BACKEND)\n"
        "client = __builtins__.__import__(CLIENT_BACKEND)\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)
    assert any("shadowsocks" in item for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_getattr_dynamic_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "getattr_imports.py").write_text(
        "import builtins as runtime_imports\n"
        "import importlib as dynamic_imports\n"
        "WIRE_PREFIX = 'wire'\n"
        "IMPORT_MODULE = 'import_' + 'module'\n"
        "BUILTIN_IMPORT = '__' + 'import__'\n"
        "import_module = getattr(dynamic_imports, IMPORT_MODULE)\n"
        "builtin_import = getattr(runtime_imports, BUILTIN_IMPORT)\n"
        "wireguard = import_module(f'{WIRE_PREFIX}guard.crypto')\n"
        "pqc = getattr(dynamic_imports, IMPORT_MODULE)('lib' + 'oqs')\n"
        "client = builtin_import('requests')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_keyword_dynamic_import_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "keyword_imports.py").write_text(
        "import builtins as runtime_imports\n"
        "import importlib as dynamic_imports\n"
        "from importlib import import_module as import_backend\n"
        "WIRE_ROOT = 'wire'\n"
        "WIREGUARD_BACKEND = f'{WIRE_ROOT}guard.crypto'\n"
        "REQUESTS_ROOT = 're'\n"
        "CLIENT_BACKEND = f'{REQUESTS_ROOT}quests'\n"
        "wg = import_backend(name=WIREGUARD_BACKEND)\n"
        "pqc = dynamic_imports.import_module(name='lib' + 'oqs')\n"
        "client = __import__(name=CLIENT_BACKEND)\n"
        "other_client = runtime_imports.__import__(name='requests')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_relative_dynamic_import_packages(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "relative_dynamic_imports.py").write_text(
        "import importlib as dynamic_imports\n"
        "from importlib import import_module as import_backend\n"
        "WIRE_PACKAGE = 'wire' + 'guard'\n"
        "PQC_PACKAGE = 'lib' + 'oqs'\n"
        "CLIENT_PACKAGE = 're' + 'quests'\n"
        "IMPORT_MODULE = 'import_' + 'module'\n"
        "relative_importer = getattr(dynamic_imports, IMPORT_MODULE)\n"
        "dict_importer = dynamic_imports.__dict__[IMPORT_MODULE]\n"
        "wg = import_backend('.crypto', WIRE_PACKAGE)\n"
        "pqc = dynamic_imports.import_module(name='.native', package=PQC_PACKAGE)\n"
        "client = relative_importer('.sessions', package=CLIENT_PACKAGE)\n"
        "wg2 = dict_importer('.crypto', 'py' + 'wireguard')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs.native" in item for item in evidence.forbidden_imports)
    assert any("pywireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("requests.sessions" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_importlib_star_dynamic_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "star_imports.py").write_text(
        "from importlib import *\n"
        "WIRE_ROOT = 'wire'\n"
        "WIREGUARD_BACKEND = f'{WIRE_ROOT}guard.crypto'\n"
        "PQC_BACKEND = 'lib' + 'oqs'\n"
        "CLIENT_BACKEND = 're' + 'quests'\n"
        "wg = import_module(WIREGUARD_BACKEND)\n"
        "pqc = import_module(name=PQC_BACKEND)\n"
        "client = import_module(CLIENT_BACKEND)\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_module_dict_dynamic_callables(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "dict_callables.py").write_text(
        "import builtins as runtime_builtins\n"
        "import importlib as dynamic_imports\n"
        "WIRE_ROOT = 'wire'\n"
        "IMPORT_MODULE = 'import_' + 'module'\n"
        "BUILTIN_IMPORT = '__' + 'import__'\n"
        "COMPILE_NAME = 'com' + 'pile'\n"
        "dict_import = dynamic_imports.__dict__[IMPORT_MODULE]\n"
        "vars_import = vars(dynamic_imports)[IMPORT_MODULE]\n"
        "builtin_import = runtime_builtins.__dict__[BUILTIN_IMPORT]\n"
        "exec_runner = runtime_builtins.__dict__['exec']\n"
        "eval_runner = vars(runtime_builtins)['eval']\n"
        "compile_runner = __builtins__[COMPILE_NAME]\n"
        "wg = dict_import(f'{WIRE_ROOT}guard.crypto')\n"
        "pqc = vars_import('lib' + 'oqs')\n"
        "client = builtin_import('requests')\n"
        "exec_runner('import requests')\n"
        "eval_runner(\"__import__('lib' + 'oqs')\")\n"
        "compiled = compile_runner('import wireguard.crypto', filename='<firstparty>', mode='exec')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_python_module_process_invocations(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "process_modules.py").write_text(
        "import os as shell_os\n"
        "import subprocess as process\n"
        "import sys as runtime_sys\n"
        "from os import system as shell_run\n"
        "from subprocess import check_call as run_module\n"
        "PYTHON = 'python' + '3'\n"
        "MODULE_FLAG = '-' + 'm'\n"
        "RUN_NAME = 'r' + 'un'\n"
        "CHECK_OUTPUT = 'check_' + 'output'\n"
        "runner = getattr(process, RUN_NAME)\n"
        "dict_runner = process.__dict__[CHECK_OUTPUT]\n"
        "runner([runtime_sys.executable, MODULE_FLAG, 'wire' + 'guard.crypto'])\n"
        "process.Popen(('/usr/bin/env', PYTHON, MODULE_FLAG, 'lib' + 'oqs'))\n"
        "run_module([PYTHON, '-m', 'py' + 'wireguard'])\n"
        "dict_runner(args=[PYTHON, '-m', 're' + 'quests'])\n"
        "shell_os.system('python3 -m oqs.native')\n"
        "shell_run('python3 -m requests.sessions')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_python_inline_process_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "process_inline_imports.py").write_text(
        "import os as shell_os\n"
        "import subprocess as process\n"
        "import sys as runtime_sys\n"
        "from os import system as shell_run\n"
        "from subprocess import run as process_run\n"
        "PYTHON = 'python' + '3'\n"
        "INLINE_FLAG = '-' + 'c'\n"
        "RUN_NAME = 'r' + 'un'\n"
        "CHECK_CALL = 'check_' + 'call'\n"
        "inline_runner = getattr(process, RUN_NAME)\n"
        "dict_runner = process.__dict__[CHECK_CALL]\n"
        "inline_runner([runtime_sys.executable, INLINE_FLAG, 'import wire' + 'guard.crypto'])\n"
        "process_run([PYTHON, '-c', \"__import__('lib' + 'oqs')\"])\n"
        "dict_runner(args=[PYTHON, '-c', 'import py' + 'wireguard'])\n"
        "process.Popen(('/usr/bin/env', PYTHON, INLINE_FLAG, 'import oqs.native'))\n"
        "shell_os.system('python3 -c \"import requests.sessions\"')\n"
        "shell_run('python3 -c \"__import__(\\'requests\\')\"')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_os_exec_spawn_python_invocations(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "os_process_imports.py").write_text(
        "import os as process_os\n"
        "import sys as runtime_sys\n"
        "from os import execv as run_execv\n"
        "from os import spawnl as spawn_list\n"
        "PYTHON = 'python' + '3'\n"
        "EXECVP = 'exec' + 'vp'\n"
        "SPAWNV = 'spawn' + 'v'\n"
        "execvp_runner = getattr(process_os, EXECVP)\n"
        "spawnv_runner = process_os.__dict__[SPAWNV]\n"
        "run_execv(runtime_sys.executable, [runtime_sys.executable, '-m', 'wire' + 'guard.crypto'])\n"
        "execvp_runner(PYTHON, [PYTHON, '-c', \"__import__('lib' + 'oqs')\"])\n"
        "spawnv_runner(process_os.P_NOWAIT, PYTHON, [PYTHON, '-m', 'py' + 'wireguard'])\n"
        "spawn_list(process_os.P_WAIT, PYTHON, PYTHON, '-c', 'import oqs.native')\n"
        "process_os.execl(PYTHON, PYTHON, '-m', 're' + 'quests')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_package_manager_backend_installs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "runtime_installs.py").write_text(
        "import os as shell_os\n"
        "import subprocess as process\n"
        "import sys as runtime_sys\n"
        "from os import spawnv as spawn_package_install\n"
        "from subprocess import run as run_package_install\n"
        "PYTHON = 'python' + '3'\n"
        "INSTALL = 'in' + 'stall'\n"
        "RUN = 'r' + 'un'\n"
        "runner = getattr(process, RUN)\n"
        "dict_runner = process.__dict__['check_' + 'call']\n"
        "runner([runtime_sys.executable, '-m', 'pip', INSTALL, 'crypto' + 'graphy==42.0.0'])\n"
        "process.check_call(['uv', 'pip', INSTALL, 'lib' + 'oqs'])\n"
        "run_package_install(['npm', INSTALL, 'py' + 'wireguard'])\n"
        "dict_runner(args=['poetry', 'add', 'na' + 'cl'])\n"
        "shell_os.system('apt-get install wireguard-tools')\n"
        "shell_os.popen('go get github.com/WireGuard/wireguard-go')\n"
        "spawn_package_install(shell_os.P_WAIT, PYTHON, [PYTHON, '-m', 'pip', INSTALL, 'sod' + 'ium'])\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_external_import_detected" in evidence.reasons
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("pip" in item for item in evidence.external_imports)
    assert any("cryptography" in item for item in evidence.forbidden_markers)
    assert any("liboqs" in item for item in evidence.forbidden_markers)
    assert any("pywireguard" in item for item in evidence.forbidden_markers)
    assert any("nacl" in item for item in evidence.forbidden_markers)
    assert any("wireguard" in item for item in evidence.forbidden_markers)
    assert any("sodium" in item for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_downloader_backend_fetches(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "runtime_downloads.py").write_text(
        "import os as shell_os\n"
        "import subprocess as process\n"
        "from os import spawnv as spawn_download\n"
        "from subprocess import run as run_download\n"
        "CURL = 'cu' + 'rl'\n"
        "WGET = 'w' + 'get'\n"
        "runner = getattr(process, 'r' + 'un')\n"
        "dict_runner = process.__dict__['check_' + 'call']\n"
        "runner([CURL, '-L', 'https://example.invalid/crypto' + 'graphy.tar.gz'])\n"
        "process.check_call([WGET, 'https://example.invalid/lib' + 'oqs.zip'])\n"
        "run_download(['git', 'clone', 'https://example.invalid/py' + 'wireguard.git'])\n"
        "dict_runner(args=['git', 'submodule', 'add', 'https://example.invalid/na' + 'cl.git'])\n"
        "shell_os.system('gh repo clone example/wireguard-go')\n"
        "shell_os.popen('svn checkout https://example.invalid/sodium/trunk')\n"
        "spawn_download(shell_os.P_WAIT, CURL, [CURL, 'https://example.invalid/Open' + 'SSL.tar.gz'])\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("cryptography" in item for item in evidence.forbidden_markers)
    assert any("liboqs" in item for item in evidence.forbidden_markers)
    assert any("pywireguard" in item for item in evidence.forbidden_markers)
    assert any("nacl" in item for item in evidence.forbidden_markers)
    assert any("wireguard" in item for item in evidence.forbidden_markers)
    assert any("sodium" in item for item in evidence.forbidden_markers)
    assert any("openssl" in item.lower() for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_importlib_loader_module_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "loader_imports.py").write_text(
        "import importlib.util\n"
        "import importlib.machinery as machinery\n"
        "from importlib.util import spec_from_loader as load_spec\n"
        "from importlib.machinery import SourceFileLoader as source_loader\n"
        "WIRE_ROOT = 'wire'\n"
        "WIREGUARD_BACKEND = f'{WIRE_ROOT}guard.crypto'\n"
        "PQC_BACKEND = 'lib' + 'oqs'\n"
        "CLIENT_BACKEND = 're' + 'quests'\n"
        "spec = importlib.util.spec_from_file_location(WIREGUARD_BACKEND, '/tmp/wg.py')\n"
        "pqc_spec = load_spec(name=PQC_BACKEND, loader=None)\n"
        "client_loader = machinery.SourcelessFileLoader(CLIENT_BACKEND, '/tmp/requests.pyc')\n"
        "wg_loader = source_loader('py' + 'wireguard', '/tmp/wg.py')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_aliased_importlib_loader_callables(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "loader_aliases.py").write_text(
        "import importlib.util as load_util\n"
        "from importlib import machinery as load_machinery\n"
        "SPEC_NAME = 'spec_from_' + 'file_location'\n"
        "SPEC_FROM_LOADER = 'spec_from_' + 'loader'\n"
        "SOURCE_LOADER = 'Source' + 'FileLoader'\n"
        "spec_factory = getattr(load_util, SPEC_NAME)\n"
        "spec_from_loader = load_util.__dict__[SPEC_FROM_LOADER]\n"
        "source_loader = getattr(load_machinery, SOURCE_LOADER)\n"
        "bytecode_loader = vars(load_machinery)['SourcelessFileLoader']\n"
        "extension_loader = load_machinery.ExtensionFileLoader\n"
        "spec = spec_factory('wire' + 'guard.crypto', '/tmp/wg.py')\n"
        "pqc_spec = spec_from_loader(name='lib' + 'oqs', loader=None)\n"
        "client_loader = bytecode_loader('re' + 'quests', '/tmp/requests.pyc')\n"
        "wg_loader = source_loader('py' + 'wireguard', '/tmp/wg.py')\n"
        "native_loader = extension_loader('oqs.native', '/tmp/oqs.so')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_pkgutil_runpy_module_resolution(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "module_resolution.py").write_text(
        "import pkgutil as package_tools\n"
        "import runpy as module_runner\n"
        "from pkgutil import resolve_name as resolve_backend\n"
        "from runpy import run_module as run_backend\n"
        "WIRE_ROOT = 'wire'\n"
        "WIREGUARD_BACKEND = f'{WIRE_ROOT}guard.crypto'\n"
        "PQC_BACKEND = 'lib' + 'oqs'\n"
        "CLIENT_BACKEND = 're' + 'quests'\n"
        "RUN_MODULE = 'run_' + 'module'\n"
        "get_loader = getattr(package_tools, 'get_' + 'loader')\n"
        "find_loader = package_tools.__dict__['find_loader']\n"
        "run_module = vars(module_runner)[RUN_MODULE]\n"
        "wg = resolve_backend(WIREGUARD_BACKEND)\n"
        "pqc = get_loader(module_or_name=PQC_BACKEND)\n"
        "client = find_loader(fullname=CLIENT_BACKEND)\n"
        "runner = run_module(mod_name='py' + 'wireguard')\n"
        "other_runner = run_backend('oqs.native')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_importlib_resources_package_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "resource_backends.py").write_text(
        "import importlib.resources\n"
        "import importlib.resources as resource_api\n"
        "from importlib import resources as resource_tools\n"
        "from importlib.resources import *\n"
        "from importlib.resources import files as resource_files\n"
        "from importlib.resources import read_text as resource_read_text\n"
        "WIRE_ROOT = 'wire'\n"
        "FILES_NAME = 'fi' + 'les'\n"
        "READ_BINARY = 'read_' + 'binary'\n"
        "resource_reader = getattr(resource_api, READ_BINARY)\n"
        "resource_files_alias = resource_tools.__dict__[FILES_NAME]\n"
        "resource_text = vars(resource_tools)['read_text']\n"
        "star_reader = read_binary\n"
        "wg = importlib.resources.files(f'{WIRE_ROOT}guard.crypto')\n"
        "pqc = resource_files_alias('lib' + 'oqs')\n"
        "client = resource_reader(package='re' + 'quests', resource='client.bin')\n"
        "wg2 = resource_files(anchor='py' + 'wireguard')\n"
        "native = resource_text(package='oqs.native', resource='native.txt')\n"
        "client2 = star_reader('requests.adapters', 'adapter.bin')\n"
        "pqc2 = resource_read_text('liboqs.bindings', resource='init.txt')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("pywireguard" in item for item in evidence.forbidden_imports)
    assert any("oqs.native" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_literal_runtime_code_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "runtime_code.py").write_text(
        "WIRE_ROOT = 'wire'\n"
        "WIRE_IMPORT = f'import {WIRE_ROOT}guard.crypto'\n"
        "PQC_IMPORT = \"__import__('lib' + 'oqs')\"\n"
        "CLIENT_IMPORT = 'import ' + 'requests'\n"
        "exec(CLIENT_IMPORT)\n"
        "eval(PQC_IMPORT)\n"
        "compiled = compile(source=WIRE_IMPORT, filename='<firstparty>', mode='exec')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_aliased_runtime_code_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "runtime_code_aliases.py").write_text(
        "import builtins as runtime_builtins\n"
        "from builtins import eval as runtime_eval\n"
        "EXEC_NAME = 'ex' + 'ec'\n"
        "WIRE_ROOT = 'wire'\n"
        "WIRE_IMPORT = f'import {WIRE_ROOT}guard.crypto'\n"
        "PQC_IMPORT = \"__import__('lib' + 'oqs')\"\n"
        "CLIENT_IMPORT = 'import ' + 'requests'\n"
        "runtime_exec = getattr(runtime_builtins, EXEC_NAME)\n"
        "runtime_compile = runtime_builtins.compile\n"
        "run_eval = runtime_eval\n"
        "runtime_exec(CLIENT_IMPORT)\n"
        "run_eval(PQC_IMPORT)\n"
        "compiled = runtime_compile(object=WIRE_IMPORT, filename='<firstparty>', mode='exec')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_forbidden_import_detected" in evidence.reasons
    assert "firstparty_external_import_detected" in evidence.reasons
    assert any("wireguard.crypto" in item for item in evidence.forbidden_imports)
    assert any("liboqs" in item for item in evidence.forbidden_imports)
    assert any("requests" in item for item in evidence.external_imports)


def test_firstparty_source_audit_rejects_native_library_backend_loads(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "native_libraries.py").write_text(
        "import cffi as native_ffi\n"
        "import ctypes as native\n"
        "import ctypes.util as native_util\n"
        "from ctypes import CDLL as load_shared\n"
        "from ctypes import cdll as native_cdll\n"
        "from ctypes.util import find_library as find_shared\n"
        "CDLL_NAME = 'C' + 'DLL'\n"
        "LOAD_LIBRARY = 'Load' + 'Library'\n"
        "ffi = native_ffi.FFI()\n"
        "direct_loader = getattr(native, CDLL_NAME)\n"
        "dict_finder = native_util.__dict__['find_' + 'library']\n"
        "dict_loader = native_cdll.__dict__[LOAD_LIBRARY]\n"
        "ffi_loader = getattr(ffi, 'dl' + 'open')\n"
        "direct_loader('o' + 'qs')\n"
        "native.PyDLL('/usr/lib/lib' + 'oqs.so.0')\n"
        "load_shared('na' + 'cl')\n"
        "dict_finder('sod' + 'ium')\n"
        "dict_loader('wire' + 'guard')\n"
        "find_shared('lib' + 'ssl')\n"
        "ffi_loader('lib' + 'crypto.so')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_external_import_detected" in evidence.reasons
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("cffi" in item for item in evidence.external_imports)
    assert any("oqs" in item for item in evidence.forbidden_markers)
    assert any("liboqs" in item for item in evidence.forbidden_markers)
    assert any("nacl" in item for item in evidence.forbidden_markers)
    assert any("sodium" in item for item in evidence.forbidden_markers)
    assert any("wireguard" in item for item in evidence.forbidden_markers)
    assert any("libssl" in item for item in evidence.forbidden_markers)
    assert any("libcrypto" in item for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_byte_literal_foreign_markers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "byte_markers.py").write_text(
        "wire_marker = b'wire' + b'guard'\n"
        "shadow_marker = b'shadow' + b'socks'\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("wireguard" in item for item in evidence.forbidden_markers)
    assert any("shadowsocks" in item for item in evidence.forbidden_markers)


def test_firstparty_source_audit_rejects_forbidden_dependency_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "core.py").write_text(
        "from . import local_protocol\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text(
        "cryptography==42.0.0\n"
        "wireguard-tools==1.0.0\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = ['liboqs==0.10.0']\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("requirements.txt:cryptography" in item for item in evidence.forbidden_markers)
    assert any("requirements.txt:wireguard" in item for item in evidence.forbidden_markers)
    assert any("pyproject.toml:liboqs" in item for item in evidence.forbidden_markers)
    assert evidence.scanned_files == 4


def test_firstparty_source_audit_rejects_foreign_runtime_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    unit_dir = root / "systemd"
    scripts_dir = root / "scripts"
    unit_dir.mkdir(parents=True)
    scripts_dir.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "core.py").write_text(
        "from . import local_protocol\n",
        encoding="utf-8",
    )
    (unit_dir / "vpn.service").write_text(
        "[Service]\n"
        "ExecStart=/usr/bin/wg-quick up office0\n",
        encoding="utf-8",
    )
    (scripts_dir / "fallback.sh").write_text(
        "#!/bin/sh\n"
        "exec xray run -config /etc/xray/config.json\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("systemd/vpn.service:wg-quick" in item for item in evidence.forbidden_markers)
    assert any("scripts/fallback.sh:xray" in item for item in evidence.forbidden_markers)
    assert evidence.scanned_files == 4


def test_firstparty_source_audit_rejects_foreign_binary_backend_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    vendor_dir = root / "vendor"
    vendor_dir.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "core.py").write_text("LOCAL_ONLY = True\n", encoding="utf-8")
    (vendor_dir / "liboqs.so").write_bytes(b"\x7fELF\x00\xffoqs")
    (vendor_dir / "wireguard.ko").write_bytes(b"\x00wireguard\xff")
    (vendor_dir / "cryptography_backend.whl").write_bytes(b"PK\x03\x04\xff")
    (vendor_dir / "nacl_backend.pyd").write_bytes(b"MZ\x00\xff")

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_foreign_protocol_marker_detected" in evidence.reasons
    assert any("vendor/liboqs.so:liboqs" in item for item in evidence.forbidden_markers)
    assert any("vendor/wireguard.ko:wireguard" in item for item in evidence.forbidden_markers)
    assert any(
        "vendor/cryptography_backend.whl:cryptography" in item
        for item in evidence.forbidden_markers
    )
    assert any("vendor/nacl_backend.pyd:nacl" in item for item in evidence.forbidden_markers)
    assert evidence.scanned_files == 6


def test_firstparty_source_audit_rejects_cross_tree_src_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "cross_tree.py").write_text(
        "from src.network.firstparty_vpn.crypto import FrameCrypto\n"
        "from src.network.vpn_obfuscation_manager import VpnObfuscationManager\n"
        "legacy = __import__('src.libx0t.network.pqc_tunnel')\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_external_import_detected" in evidence.reasons
    assert not any(
        "src.network.firstparty_vpn.crypto" in item
        for item in evidence.external_imports
    )
    assert any(
        "src.network.vpn_obfuscation_manager" in item
        for item in evidence.external_imports
    )
    assert any(
        "src.libx0t.network.pqc_tunnel" in item
        for item in evidence.external_imports
    )


def test_firstparty_source_audit_rejects_cross_tree_relative_imports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty_vpn"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "crypto.py").write_text("class FrameCrypto: pass\n", encoding="utf-8")
    (nested / "__init__.py").write_text("", encoding="utf-8")
    (nested / "cross_tree.py").write_text(
        "from ..crypto import FrameCrypto\n"
        "from ...vpn_obfuscation_manager import VpnObfuscationManager\n"
        "from ... import pqc_tunnel\n",
        encoding="utf-8",
    )

    evidence = audit_firstparty_source_tree(root)

    assert evidence.passed is False
    assert "firstparty_external_import_detected" in evidence.reasons
    assert not any(
        "src.network.firstparty_vpn.crypto" in item
        for item in evidence.external_imports
    )
    assert any(
        "src.network.vpn_obfuscation_manager" in item
        for item in evidence.external_imports
    )
    assert any(
        "src.network.pqc_tunnel" in item
        for item in evidence.external_imports
    )


def test_firstparty_source_audit_requires_python_source_tree(tmp_path: Path) -> None:
    with pytest.raises(FirstPartySourceAuditError, match="root is missing"):
        audit_firstparty_source_tree(tmp_path / "missing")

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FirstPartySourceAuditError, match="found no Python files"):
        audit_firstparty_source_tree(empty)


def test_firstparty_mlkem_parameter_sets_match_required_shapes() -> None:
    mlkem768 = mlkem_parameter_set("ML-KEM-768")
    mlkem1024 = mlkem_parameter_set("ML-KEM-1024")

    assert mlkem768.security_category == 3
    assert mlkem768.k == 3
    assert mlkem768.eta1 == 2
    assert mlkem768.eta2 == 2
    assert mlkem768.du == 10
    assert mlkem768.dv == 4
    assert mlkem768.encapsulation_key_bytes == 1184
    assert mlkem768.decapsulation_key_bytes == 2400
    assert mlkem768.ciphertext_bytes == 1088
    assert mlkem768.shared_secret_bytes == 32
    assert mlkem1024.security_category == 5
    assert mlkem1024.k == 4
    assert mlkem1024.du == 11
    assert mlkem1024.dv == 5
    assert mlkem1024.encapsulation_key_bytes == 1568
    assert mlkem1024.decapsulation_key_bytes == 3168
    assert mlkem1024.ciphertext_bytes == 1568
    with pytest.raises(MlKemPrimitiveError, match="unsupported ML-KEM"):
        mlkem_parameter_set("ML-KEM-512")


def test_firstparty_mldsa_parameter_sets_match_required_shapes() -> None:
    mldsa65 = mldsa_parameter_set("ML-DSA-65")
    mldsa87 = mldsa_parameter_set("ML-DSA-87")
    signing_key65 = deterministic_mldsa_signing_key_bytes("shape-key")
    verification_key65 = mldsa_encode_verification_key(
        b"r" * ML_DSA_RHO_BYTES,
        tuple(
            tuple(
                (coefficient + row) % (1 << ML_DSA_T1_BITS)
                for coefficient in range(ML_DSA_N)
            )
            for row in range(mldsa65.k)
        ),
        mldsa65,
    )
    signature65 = deterministic_mldsa_signature_bytes(
        "ML-DSA-65",
        b"shape-signature",
    )

    assert mldsa65.security_category == 3
    assert mldsa65.k == 6
    assert mldsa65.l == 5
    assert mldsa65.eta == 4
    assert mldsa65.tau == 49
    assert mldsa65.beta == 196
    assert mldsa65.gamma1 == 1 << 19
    assert mldsa65.gamma2 == (ML_DSA_Q - 1) // 32
    assert mldsa65.omega == 55
    assert mldsa65.signing_key_bytes == 4032
    assert mldsa65.verification_key_bytes == 1952
    assert mldsa65.signature_bytes == 3309
    assert mldsa65.signature_challenge_bytes == 48
    assert mldsa87.security_category == 5
    assert mldsa87.k == 8
    assert mldsa87.l == 7
    assert mldsa87.eta == 2
    assert mldsa87.tau == 60
    assert mldsa87.beta == 120
    assert mldsa87.gamma1 == 1 << 19
    assert mldsa87.gamma2 == (ML_DSA_Q - 1) // 32
    assert mldsa87.omega == 75
    assert mldsa87.signing_key_bytes == 4896
    assert mldsa87.verification_key_bytes == 2592
    assert mldsa87.signature_bytes == 4627
    assert mldsa87.signature_challenge_bytes == 64
    mldsa_validate_signing_key("ML-DSA-65", signing_key65)
    mldsa_validate_verification_key("ML-DSA-65", verification_key65)
    mldsa_validate_signature("ML-DSA-65", signature65)
    with pytest.raises(MlDsaShapeError, match="unsupported ML-DSA"):
        mldsa_parameter_set("ML-DSA-44")
    with pytest.raises(MlDsaShapeError, match="signing key length"):
        mldsa_validate_signing_key("ML-DSA-65", signing_key65[:-1])
    with pytest.raises(MlDsaShapeError, match="verification key length"):
        mldsa_validate_verification_key("ML-DSA-65", verification_key65[:-1])
    with pytest.raises(MlDsaShapeError, match="signature length"):
        mldsa_validate_signature("ML-DSA-65", signature65[:-1])


def test_firstparty_mldsa_expanded_key_codecs_round_trip() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    rho = hashlib.sha3_256(b"mldsa-rho").digest()
    key_seed = hashlib.sha3_256(b"mldsa-key-seed").digest()
    public_key_hash = hashlib.shake_256(b"mldsa-tr").digest(ML_DSA_TR_BYTES)
    short_seed = hashlib.sha3_256(b"mldsa-short-seed").digest()
    s1 = mldsa_expand_short_vector(short_seed, params, vector_length=params.l)
    s2 = mldsa_expand_short_vector(
        short_seed,
        params,
        vector_length=params.k,
        start_nonce=params.l,
    )
    t0 = tuple(
        tuple(
            ((coefficient + row * 31) % (2 * ML_DSA_T0_BOUND))
            - (ML_DSA_T0_BOUND - 1)
            for coefficient in range(ML_DSA_N)
        )
        for row in range(params.k)
    )
    t1 = tuple(
        tuple(
            (coefficient * 3 + row) % (1 << ML_DSA_T1_BITS)
            for coefficient in range(ML_DSA_N)
        )
        for row in range(params.k)
    )

    signing_key = mldsa_encode_signing_key(
        rho,
        key_seed,
        public_key_hash,
        s1,
        s2,
        t0,
        params,
    )
    verification_key = mldsa_encode_verification_key(rho, t1, params)
    decoded_signing_key = mldsa_decode_signing_key(params.name, signing_key)
    decoded_verification_key = mldsa_decode_verification_key(
        params.name,
        verification_key,
    )

    assert len(signing_key) == params.signing_key_bytes
    assert len(verification_key) == params.verification_key_bytes
    assert decoded_signing_key.encode() == signing_key
    assert decoded_signing_key.rho == rho
    assert decoded_signing_key.key_seed == key_seed
    assert decoded_signing_key.public_key_hash == public_key_hash
    assert decoded_signing_key.s1 == s1
    assert decoded_signing_key.s2 == s2
    assert decoded_signing_key.t0 == t0
    assert decoded_verification_key.encode() == verification_key
    assert decoded_verification_key.rho == rho
    assert decoded_verification_key.t1 == t1
    assert len(mldsa_encode_t1_poly(t1[0])) == (
        ML_DSA_N * ML_DSA_T1_BITS + 7
    ) // 8
    assert len(mldsa_encode_t0_poly(t0[0])) == (
        ML_DSA_N * ML_DSA_T0_BITS + 7
    ) // 8
    assert mldsa_decode_t1_poly(mldsa_encode_t1_poly(t1[0])) == t1[0]
    assert mldsa_decode_t0_poly(mldsa_encode_t0_poly(t0[0])) == t0[0]
    assert mldsa_decode_signing_key(params.name, signing_key).encode() == signing_key
    mldsa_validate_verification_key(params.name, verification_key)

    malformed_signing_key = bytearray(signing_key)
    malformed_signing_key[
        ML_DSA_RHO_BYTES + ML_DSA_KEY_BYTES + ML_DSA_TR_BYTES
    ] = 0xFF
    with pytest.raises(MlDsaShapeError, match="bounded coefficient"):
        mldsa_decode_signing_key(params.name, bytes(malformed_signing_key))
    with pytest.raises(MlDsaShapeError, match="rho length"):
        mldsa_encode_verification_key(rho[:-1], t1, params)
    with pytest.raises(MlDsaShapeError, match="t1 coefficient"):
        mldsa_encode_t1_poly((1 << ML_DSA_T1_BITS,) + (0,) * (ML_DSA_N - 1))
    with pytest.raises(MlDsaShapeError, match="t0 coefficient"):
        mldsa_encode_t0_poly((-(ML_DSA_T0_BOUND),) + (0,) * (ML_DSA_N - 1))


def test_firstparty_mldsa_reference_keypair_derivation_is_self_consistent() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    seed = hashlib.sha3_256(b"firstparty-mldsa-reference-keypair").digest()
    other_seed = hashlib.sha3_256(b"firstparty-mldsa-reference-keypair-other").digest()

    rho, rho_prime, key_seed = mldsa_expand_keygen_seed(seed, params)
    keypair = mldsa_derive_reference_keypair(seed, params)
    same_keypair = mldsa_derive_reference_keypair(seed, params)
    other_keypair = mldsa_derive_reference_keypair(other_seed, params)
    derived_verification_key = mldsa_derive_verification_key_from_signing_key(
        params.name,
        keypair.signing_key,
    )

    assert len(rho) == ML_DSA_RHO_BYTES
    assert len(rho_prime) == ML_DSA_RHO_PRIME_BYTES
    assert len(key_seed) == ML_DSA_KEY_BYTES
    assert keypair.signing_key == same_keypair.signing_key
    assert keypair.verification_key == same_keypair.verification_key
    assert keypair.signing_key != other_keypair.signing_key
    assert keypair.verification_key != other_keypair.verification_key
    assert len(keypair.signing_key) == params.signing_key_bytes
    assert len(keypair.verification_key) == params.verification_key_bytes
    assert keypair.signing_key_components.encode() == keypair.signing_key
    assert keypair.verification_key_components.encode() == keypair.verification_key
    assert derived_verification_key == keypair.verification_key
    assert keypair.signing_key_components.public_key_hash == mldsa_shake256(
        keypair.verification_key,
        ML_DSA_TR_BYTES,
    )
    t1, t0 = mldsa_power2round_vector(
        mldsa_key_equation_reference(
            mldsa_expand_matrix_ntt(rho, params),
            tuple(
                tuple(coefficient % ML_DSA_Q for coefficient in poly)
                for poly in keypair.signing_key_components.s1
            ),
            tuple(
                tuple(coefficient % ML_DSA_Q for coefficient in poly)
                for poly in keypair.signing_key_components.s2
            ),
        )
    )
    assert t1 == keypair.verification_key_components.t1
    assert t0 == keypair.signing_key_components.t0
    mldsa_validate_signing_key(params.name, keypair.signing_key)
    mldsa_validate_verification_key(params.name, keypair.verification_key)

    tampered_t0 = bytearray(keypair.signing_key)
    tampered_t0[-1] ^= 0x01
    with pytest.raises(MlDsaShapeError, match="t0 mismatch"):
        mldsa_validate_signing_key(params.name, bytes(tampered_t0))
    tampered_hash = bytearray(keypair.signing_key)
    tampered_hash[ML_DSA_RHO_BYTES + ML_DSA_KEY_BYTES] ^= 0x01
    with pytest.raises(MlDsaShapeError, match="public key hash mismatch"):
        mldsa_validate_signing_key(params.name, bytes(tampered_hash))
    with pytest.raises(MlDsaShapeError, match="keygen seed length"):
        mldsa_derive_reference_keypair(seed[:-1], params)


def test_firstparty_mldsa_signature_codec_round_trips_and_rejects_malformed_shapes() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    signature = deterministic_mldsa_signature_bytes(
        params.name,
        b"firstparty-mldsa-signature-shape",
    )
    signature87 = deterministic_mldsa_signature_bytes(
        "ML-DSA-87",
        b"firstparty-mldsa-signature-shape-87",
    )
    decoded = mldsa_decode_signature(params.name, signature)
    z_poly_bytes = (ML_DSA_N * params.gamma1.bit_length() + 7) // 8

    assert len(signature) == params.signature_bytes
    assert len(signature87) == mldsa_parameter_set("ML-DSA-87").signature_bytes
    assert decoded.encode() == signature
    assert len(decoded.challenge) == params.signature_challenge_bytes
    assert len(decoded.z) == params.l
    assert len(decoded.hints) == params.k
    assert all(len(poly) == ML_DSA_N for poly in decoded.z)
    assert all(
        -(params.gamma1 - params.beta) <= value <= params.gamma1 - params.beta
        for poly in decoded.z
        for value in poly
    )
    assert mldsa_decode_signature_z_poly(
        mldsa_encode_signature_z_poly(decoded.z[0], params),
        params,
    ) == decoded.z[0]
    mldsa_validate_signature(params.name, signature)
    mldsa_validate_signature("ML-DSA-87", signature87)

    with pytest.raises(MlDsaShapeError, match="challenge length"):
        mldsa_encode_signature(
            decoded.challenge[:-1],
            decoded.z,
            decoded.hints,
            params,
        )
    malformed_z = bytearray(signature)
    malformed_z[params.signature_challenge_bytes] = 0
    malformed_z[params.signature_challenge_bytes + 1] = 0
    malformed_z[params.signature_challenge_bytes + 2] &= 0xF0
    with pytest.raises(MlDsaShapeError, match="signature z coefficient"):
        mldsa_decode_signature(params.name, bytes(malformed_z))
    malformed_hint = bytearray(signature)
    malformed_hint[
        params.signature_challenge_bytes + params.l * z_poly_bytes
    ] = 1
    with pytest.raises(MlDsaShapeError, match="hint"):
        mldsa_decode_signature(params.name, bytes(malformed_hint))


def test_firstparty_reference_mldsa_identity_signature_provider_signs_structured_payloads() -> None:
    key = production_signing_key("prod-id-key-1")
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    payload = b"firstparty-reference-mldsa-identity-payload-v1"

    signature = provider.sign(key, payload)
    same_signature = provider.sign(key, payload)
    decoded = mldsa_decode_signature(key.signature_algorithm, signature)

    assert signature == same_signature
    assert decoded.encode() == signature
    assert provider.verify(key, payload, signature) is True
    assert provider.verify(key, payload + b"-tampered", signature) is False
    tampered_signature = bytearray(signature)
    tampered_signature[-1] ^= 0x01
    assert provider.verify(key, payload, bytes(tampered_signature)) is False
    with pytest.raises(MlDsaShapeError, match="signing key length"):
        provider.sign(signing_key("dev-key"), payload)


def test_firstparty_reference_mldsa_verifies_with_public_key_only() -> None:
    key = production_signing_key("prod-id-key-1")
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    payload = b"firstparty-reference-mldsa-public-verify-v1"
    verification_key = mldsa_derive_verification_key_from_signing_key(
        key.signature_algorithm,
        key.secret,
    )
    public_key = replace(key, secret=verification_key)

    signature = provider.sign(key, payload)
    direct_signature = mldsa_reference_sign(key.signature_algorithm, key.secret, payload)
    authority = IdentityAuthority(
        issuer="x0tta6bl4-prod-identity-authority",
        policy_epoch="epoch-prod",
        signing_keys=(key,),
        active_key_id=key.key_id,
        signature_provider=provider,
    )
    token = authority.issue(issue_request("vpn-client"), now=NOW)
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(public_key,),
        signature_provider=provider,
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    assert len(public_key.secret) == mldsa_parameter_set(
        key.signature_algorithm
    ).verification_key_bytes
    assert signature == direct_signature
    assert mldsa_reference_verify(
        key.signature_algorithm,
        verification_key,
        payload,
        signature,
    )
    assert provider.verify(public_key, payload, signature) is True
    assert provider.verify(public_key, payload + b"-tampered", signature) is False
    with pytest.raises(MlDsaShapeError, match="signing key length"):
        provider.sign(public_key, payload)

    assert verifier.verify(token, policy=policy, now=NOW).allowed is True
    tampered = verifier.verify(
        replace(token, signature=b"\x00" * len(token.signature)),
        policy=policy,
        now=NOW,
    )
    assert tampered.allowed is False
    assert "identity_signature_invalid" in tampered.reasons


def test_firstparty_mldsa_arithmetic_rounding_and_hints_are_bounded() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    value = ML_DSA_Q * 3 + 12345

    assert ML_DSA_N == 256
    assert ML_DSA_D == 13
    assert ML_DSA_Q == 8_380_417
    assert mldsa_reduce(value) == 12345
    assert mldsa_centered_reduce(ML_DSA_Q - 5) == -5
    assert mldsa_add(ML_DSA_Q - 1, 2) == 1
    assert mldsa_sub(1, 2) == ML_DSA_Q - 1
    assert mldsa_mul(123, 456) == (123 * 456) % ML_DSA_Q

    high, low = mldsa_power2round(value)
    assert high * (1 << ML_DSA_D) + low == mldsa_reduce(value)
    assert -(1 << (ML_DSA_D - 1)) < low <= (1 << (ML_DSA_D - 1))

    decomposed_high, decomposed_low = mldsa_decompose(value, params.gamma2)
    assert mldsa_high_bits(value, params.gamma2) == decomposed_high
    assert mldsa_low_bits(value, params.gamma2) == decomposed_low
    assert -params.gamma2 < decomposed_low <= params.gamma2
    assert mldsa_reduce(
        decomposed_high * 2 * params.gamma2 + decomposed_low
    ) == mldsa_reduce(value)

    hint_delta = params.gamma2 + 7
    hint = mldsa_make_hint(hint_delta, value, params.gamma2)
    assert hint in (0, 1)
    assert mldsa_use_hint(hint, value, params.gamma2) == mldsa_high_bits(
        value + hint_delta,
        params.gamma2,
    )
    with pytest.raises(MlDsaShapeError, match="hint must be 0 or 1"):
        mldsa_use_hint(2, value, params.gamma2)
    with pytest.raises(MlDsaShapeError, match="gamma2"):
        mldsa_decompose(value, 123)


def test_firstparty_mldsa_polynomial_ring_arithmetic_is_bounded() -> None:
    left = tuple((index * 17 + 3) % ML_DSA_Q for index in range(ML_DSA_N))
    right = tuple((index * index + 11) % ML_DSA_Q for index in range(ML_DSA_N))
    product = mldsa_poly_negacyclic_mul(left, right)

    assert mldsa_poly_add(left, right) == tuple(
        (a + b) % ML_DSA_Q for a, b in zip(left, right)
    )
    assert mldsa_poly_sub(left, right) == tuple(
        (a - b) % ML_DSA_Q for a, b in zip(left, right)
    )
    assert len(product) == ML_DSA_N
    assert all(0 <= value < ML_DSA_Q for value in product)
    identity_product = mldsa_poly_negacyclic_mul(
        (1,) + (0,) * (ML_DSA_N - 1),
        right,
    )
    assert identity_product == right
    x_poly = (0, 1) + (0,) * (ML_DSA_N - 2)
    x_times_x_255 = mldsa_poly_negacyclic_mul(
        x_poly,
        (0,) * (ML_DSA_N - 1) + (1,),
    )
    assert x_times_x_255 == (ML_DSA_Q - 1,) + (0,) * (ML_DSA_N - 1)
    with pytest.raises(MlDsaShapeError, match="256 coefficients"):
        mldsa_poly_add((1, 2, 3), right)


def test_firstparty_mldsa_matrix_vector_key_equation_reference() -> None:
    one = (1,) + (0,) * (ML_DSA_N - 1)
    x_poly = (0, 1) + (0,) * (ML_DSA_N - 2)
    two = (2,) + (0,) * (ML_DSA_N - 1)
    s1 = (one, x_poly)
    s2 = (two, one)
    matrix = ((one, x_poly), (x_poly, one))

    product = mldsa_matrix_vector_mul(matrix, s1)
    summed = mldsa_key_equation_reference(matrix, s1, s2)

    assert product == (
        mldsa_poly_add(one, mldsa_poly_negacyclic_mul(x_poly, x_poly)),
        mldsa_poly_add(x_poly, x_poly),
    )
    assert summed == mldsa_vector_add(product, s2)
    assert mldsa_vector_dot(matrix[0], s1) == product[0]
    with pytest.raises(MlDsaShapeError, match="dimensions do not match"):
        mldsa_matrix_vector_mul(matrix, s1[:-1])
    with pytest.raises(MlDsaShapeError, match="dimensions do not match"):
        mldsa_vector_add(product, product[:-1])


def test_firstparty_mldsa_bit_packing_round_trips_polynomials() -> None:
    poly = tuple((index * 65537 + 19) % ML_DSA_Q for index in range(ML_DSA_N))
    encoded = mldsa_encode_poly(poly, 23)

    assert len(encoded) == (ML_DSA_N * 23 + 7) // 8
    assert mldsa_decode_poly(encoded, 23) == poly
    values = tuple(index % 16 for index in range(17))
    packed = mldsa_bit_pack(values, 4)
    assert mldsa_bit_unpack(packed, bits=4, count=len(values)) == values
    with pytest.raises(MlDsaShapeError, match="out of range"):
        mldsa_bit_pack((16,), 4)
    with pytest.raises(MlDsaShapeError, match="packed length"):
        mldsa_bit_unpack(packed[:-1], bits=4, count=len(values))
    with pytest.raises(MlDsaShapeError, match="256 coefficients"):
        mldsa_encode_poly((1, 2, 3), 23)


def test_firstparty_mldsa_bounded_polynomial_codec_round_trips() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    poly = tuple(
        (index % (2 * params.eta + 1)) - params.eta
        for index in range(ML_DSA_N)
    )

    encoded = mldsa_encode_bounded_poly(poly, params.eta)
    decoded = mldsa_decode_bounded_poly(encoded, params.eta)

    assert decoded == poly
    assert len(encoded) == (ML_DSA_N * (2 * params.eta).bit_length() + 7) // 8
    with pytest.raises(MlDsaShapeError, match="out of range"):
        mldsa_encode_bounded_poly((params.eta + 1,) * ML_DSA_N, params.eta)
    with pytest.raises(MlDsaShapeError, match="bound must be positive"):
        mldsa_encode_bounded_poly(poly, 0)
    with pytest.raises(MlDsaShapeError, match="packed length"):
        mldsa_decode_bounded_poly(encoded[:-1], params.eta)


def test_firstparty_mldsa_hint_vector_codec_round_trips() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    first = [0] * ML_DSA_N
    second = [0] * ML_DSA_N
    first[3] = 1
    first[17] = 1
    second[9] = 1
    hints = (tuple(first), tuple(second))

    encoded = mldsa_encode_hint_vector(hints, params.omega)
    decoded = mldsa_decode_hint_vector(
        encoded,
        omega=params.omega,
        vector_count=len(hints),
    )

    assert decoded == hints
    assert len(encoded) == params.omega + len(hints)
    with pytest.raises(MlDsaShapeError, match="exceeds omega"):
        mldsa_encode_hint_vector(hints, 2)
    tampered_padding = bytearray(encoded)
    tampered_padding[5] = 99
    with pytest.raises(MlDsaShapeError, match="padding"):
        mldsa_decode_hint_vector(
            bytes(tampered_padding),
            omega=params.omega,
            vector_count=len(hints),
        )
    unsorted = bytes([17, 3] + [0] * (params.omega - 2) + [2, 2])
    with pytest.raises(MlDsaShapeError, match="not sorted"):
        mldsa_decode_hint_vector(
            unsorted,
            omega=params.omega,
            vector_count=len(hints),
        )


def test_firstparty_mldsa_matrix_expansion_is_deterministic_and_bounded() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    seed = hashlib.sha3_256(b"firstparty-mldsa-matrix").digest()

    first_poly = mldsa_rejection_sample_ntt_poly(seed, 0, 0)
    same_poly = mldsa_rejection_sample_ntt_poly(seed, 0, 0)
    other_poly = mldsa_rejection_sample_ntt_poly(seed, 0, 1)
    matrix = mldsa_expand_matrix_ntt(seed, params)

    assert first_poly == same_poly
    assert first_poly != other_poly
    assert len(first_poly) == ML_DSA_N
    assert all(0 <= value < ML_DSA_Q for value in first_poly)
    assert len(matrix) == params.k
    assert all(len(row) == params.l for row in matrix)
    assert matrix[0][0] == first_poly
    assert all(
        len(poly) == ML_DSA_N and all(0 <= value < ML_DSA_Q for value in poly)
        for row in matrix
        for poly in row
    )
    with pytest.raises(MlDsaShapeError, match="seed is required"):
        mldsa_rejection_sample_ntt_poly(b"", 0, 0)
    with pytest.raises(MlDsaShapeError, match="row must fit"):
        mldsa_rejection_sample_ntt_poly(seed, 256, 0)
    with pytest.raises(MlDsaShapeError, match="column must fit"):
        mldsa_rejection_sample_ntt_poly(seed, 0, -1)


def test_firstparty_mldsa_short_vector_sampling_is_deterministic() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    seed = hashlib.sha3_256(b"firstparty-mldsa-short-vector").digest()

    poly = mldsa_sample_bounded_poly(seed, 3, params.eta)
    same_poly = mldsa_sample_bounded_poly(seed, 3, params.eta)
    other_poly = mldsa_sample_bounded_poly(seed, 4, params.eta)
    vector = mldsa_expand_short_vector(seed, params, vector_length=params.l)

    assert poly == same_poly
    assert poly != other_poly
    assert len(poly) == ML_DSA_N
    assert all(-params.eta <= value <= params.eta for value in poly)
    assert len(vector) == params.l
    assert all(len(item) == ML_DSA_N for item in vector)
    assert all(
        -params.eta <= value <= params.eta
        for item in vector
        for value in item
    )
    with pytest.raises(MlDsaShapeError, match="seed is required"):
        mldsa_sample_bounded_poly(b"", 0, params.eta)
    with pytest.raises(MlDsaShapeError, match="nonce must fit"):
        mldsa_sample_bounded_poly(seed, 256, params.eta)
    with pytest.raises(MlDsaShapeError, match="eta must be 2 or 4"):
        mldsa_sample_bounded_poly(seed, 0, 3)
    with pytest.raises(MlDsaShapeError, match="length must be positive"):
        mldsa_expand_short_vector(seed, params, vector_length=0)
    with pytest.raises(MlDsaShapeError, match="nonce range"):
        mldsa_expand_short_vector(seed, params, vector_length=2, start_nonce=255)


def test_firstparty_mldsa_challenge_sampling_is_deterministic() -> None:
    params = mldsa_parameter_set("ML-DSA-65")
    seed = hashlib.sha3_256(b"firstparty-mldsa-challenge").digest()

    challenge = mldsa_sample_in_ball(seed, params.tau)
    same_challenge = mldsa_sample_in_ball(seed, params.tau)
    other_challenge = mldsa_sample_in_ball(seed + b"other", params.tau)

    assert challenge == same_challenge
    assert challenge != other_challenge
    assert len(challenge) == ML_DSA_N
    assert sum(1 for value in challenge if value != 0) == params.tau
    assert set(challenge).issubset({-1, 0, 1})
    with pytest.raises(MlDsaShapeError, match="seed is required"):
        mldsa_sample_in_ball(b"", params.tau)
    with pytest.raises(MlDsaShapeError, match="tau is invalid"):
        mldsa_sample_in_ball(seed, 0)


def test_firstparty_mldsa_shake_helpers_are_deterministic() -> None:
    data = b"firstparty-mldsa-shake"

    assert mldsa_shake128(data, 64) == hashlib.shake_128(data).digest(64)
    assert mldsa_shake256(data, 64) == hashlib.shake_256(data).digest(64)
    assert mldsa_shake128(data, 64) != mldsa_shake128(data + b"x", 64)
    with pytest.raises(MlDsaShapeError, match="length must be positive"):
        mldsa_shake128(data, 0)
    with pytest.raises(MlDsaShapeError, match="length must be positive"):
        mldsa_shake256(data, 0)


def test_firstparty_mlkem_field_arithmetic_and_compression_are_bounded() -> None:
    assert ML_KEM_N == 256
    assert ML_KEM_Q == 3329
    assert mlkem_reduce(ML_KEM_Q + 7) == 7
    assert mlkem_add(3328, 2) == 1
    assert mlkem_sub(1, 2) == 3328
    assert mlkem_mul(123, 456) == (123 * 456) % ML_KEM_Q

    for d in (1, 4, 5, 10, 11, 12):
        compressed = tuple(
            mlkem_compress(value, d)
            for value in (0, 1, ML_KEM_Q // 2, ML_KEM_Q - 1)
        )
        assert all(0 <= value < (1 << d) for value in compressed)
        decompressed = tuple(mlkem_decompress(value, d) for value in compressed)
        assert all(0 <= value <= ML_KEM_Q for value in decompressed)

    with pytest.raises(MlKemPrimitiveError, match="between 1 and 12"):
        mlkem_compress(1, 13)
    with pytest.raises(MlKemPrimitiveError, match="outside d-bit range"):
        mlkem_decompress(16, 4)


def test_firstparty_mlkem_byte_codec_round_trips_polynomials() -> None:
    poly = tuple((index * 17) % ML_KEM_Q for index in range(ML_KEM_N))

    encoded12 = mlkem_encode_poly(poly, 12)
    assert len(encoded12) == 384
    assert mlkem_decode_poly(encoded12, 12) == poly

    compressed10 = mlkem_poly_compress(poly, 10)
    encoded10 = mlkem_byte_encode(compressed10, 10)
    assert len(encoded10) == 320
    assert mlkem_byte_decode(encoded10, 10) == compressed10
    assert len(mlkem_poly_decompress(compressed10, 10)) == ML_KEM_N

    message_bits = tuple(index % 2 for index in range(ML_KEM_N))
    encoded1 = mlkem_byte_encode(message_bits, 1)
    assert len(encoded1) == 32
    assert mlkem_byte_decode(encoded1, 1) == message_bits

    with pytest.raises(MlKemPrimitiveError, match="256 coefficients"):
        mlkem_encode_poly((1, 2, 3), 12)
    with pytest.raises(MlKemPrimitiveError, match="out of range"):
        mlkem_byte_encode((ML_KEM_Q,), 12)


def test_firstparty_mlkem_cbd_sampler_is_deterministic_and_bounded() -> None:
    zero_eta2 = mlkem_sample_poly_cbd(bytes(128), eta=2)
    assert zero_eta2 == (0,) * ML_KEM_N

    shaped = mlkem_sample_poly_cbd(bytes([0b11000011]) + bytes(127), eta=2)
    assert shaped[0] == 2
    assert shaped[1] == ML_KEM_Q - 2
    assert all(0 <= value < ML_KEM_Q for value in shaped)

    zero_eta3 = mlkem_sample_poly_cbd(bytes(192), eta=3)
    assert zero_eta3 == (0,) * ML_KEM_N
    with pytest.raises(MlKemPrimitiveError, match="eta must be 2 or 3"):
        mlkem_sample_poly_cbd(bytes(64), eta=1)
    with pytest.raises(MlKemPrimitiveError, match="seed length is invalid"):
        mlkem_sample_poly_cbd(bytes(64), eta=2)


def test_firstparty_mlkem_hash_xof_and_prf_are_deterministic() -> None:
    seed = bytes(range(ML_KEM_SEED_BYTES))
    message = b"x0tta6bl4-firstparty-mlkem"

    left, right = mlkem_hash_g(message)

    assert mlkem_hash_h(message) == hashlib.sha3_256(message).digest()
    assert left + right == hashlib.sha3_512(message).digest()
    assert len(left) == ML_KEM_SEED_BYTES
    assert len(right) == ML_KEM_SEED_BYTES
    assert mlkem_hash_j(message) == hashlib.shake_256(message).digest(32)
    assert mlkem_prf(seed, 7, eta=2) == hashlib.shake_256(seed + b"\x07").digest(128)
    assert len(mlkem_prf(seed, 7, eta=3)) == 192
    assert mlkem_xof(seed, 1, 2, 64) == hashlib.shake_128(
        seed + b"\x01\x02"
    ).digest(64)
    assert mlkem_xof(seed, 1, 2, 64) != mlkem_xof(seed, 2, 1, 64)

    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_prf(bytes(31), 0, eta=2)
    with pytest.raises(MlKemPrimitiveError, match="counter must fit"):
        mlkem_prf(seed, 256, eta=2)
    with pytest.raises(MlKemPrimitiveError, match="eta must be 2 or 3"):
        mlkem_prf(seed, 0, eta=1)
    with pytest.raises(MlKemPrimitiveError, match="length must be positive"):
        mlkem_xof(seed, 0, 0, 0)


def test_firstparty_mlkem_sample_ntt_is_deterministic_and_in_field() -> None:
    seed = hashlib.sha3_256(b"sample-ntt-seed").digest()

    first = mlkem_sample_ntt(seed, 0, 0)
    second = mlkem_sample_ntt(seed, 0, 0)
    different_index = mlkem_sample_ntt(seed, 0, 1)

    assert first == second
    assert first != different_index
    assert len(first) == ML_KEM_N
    assert all(0 <= value < ML_KEM_Q for value in first)
    assert mlkem_byte_decode(mlkem_byte_encode(first, 12), 12) == first

    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_sample_ntt(bytes(31), 0, 0)
    with pytest.raises(MlKemPrimitiveError, match="row must fit"):
        mlkem_sample_ntt(seed, 256, 0)
    with pytest.raises(MlKemPrimitiveError, match="column must fit"):
        mlkem_sample_ntt(seed, 0, -1)


def test_firstparty_mlkem_ntt_round_trip_and_multiply_matches_ring() -> None:
    left = tuple((index * 17 + 5) % ML_KEM_Q for index in range(ML_KEM_N))
    right = tuple((index * index + 11) % ML_KEM_Q for index in range(ML_KEM_N))

    left_ntt = mlkem_ntt(left)
    right_ntt = mlkem_ntt(right)

    assert mlkem_inv_ntt(left_ntt) == left
    assert mlkem_poly_add(left, right) == tuple(
        (a + b) % ML_KEM_Q for a, b in zip(left, right)
    )
    assert mlkem_poly_sub(left, right) == tuple(
        (a - b) % ML_KEM_Q for a, b in zip(left, right)
    )
    assert mlkem_inv_ntt(mlkem_multiply_ntts(left_ntt, right_ntt)) == (
        mlkem_poly_negacyclic_mul(left, right)
    )

    vector = (left, right)
    assert mlkem_vector_inv_ntt(mlkem_vector_ntt(vector)) == vector


def test_firstparty_mlkem_matrix_vector_ntt_operations_are_deterministic() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    seed = hashlib.sha3_256(b"matrix-seed").digest()
    matrix = mlkem_sample_matrix_ntt(seed, params)
    transposed = mlkem_sample_matrix_ntt(seed, params, transposed=True)
    vector = tuple(mlkem_sample_ntt(seed, index, params.k) for index in range(params.k))

    product = mlkem_matrix_vector_ntt(matrix, vector)
    manual_first = mlkem_vector_dot_ntt(matrix[0], vector)
    encoded = mlkem_encode_vector(product, 12)

    assert len(matrix) == params.k
    assert all(len(row) == params.k for row in matrix)
    assert matrix != transposed
    assert product[0] == manual_first
    assert len(product) == params.k
    assert all(len(poly) == ML_KEM_N for poly in product)
    assert all(0 <= value < ML_KEM_Q for poly in product for value in poly)
    assert len(encoded) == 384 * params.k
    assert mlkem_decode_vector(encoded, k=params.k, d=12) == product

    with pytest.raises(MlKemPrimitiveError, match="dimensions do not match"):
        mlkem_matrix_vector_ntt(matrix, vector[:-1])
    with pytest.raises(MlKemPrimitiveError, match="encoded vector length is invalid"):
        mlkem_decode_vector(encoded[:-1], k=params.k, d=12)


def test_firstparty_mlkem_kpke_keygen_from_seed_has_fips_shapes() -> None:
    seed = hashlib.sha3_256(b"kpke-keygen-seed").digest()
    other_seed = hashlib.sha3_256(b"kpke-keygen-other-seed").digest()
    params768 = mlkem_parameter_set("ML-KEM-768")
    params1024 = mlkem_parameter_set("ML-KEM-1024")

    keypair = mlkem_kpke_keygen_from_seed(params768, seed)
    same_keypair = mlkem_kpke_keygen_from_seed("ML-KEM-768", seed)
    other_keypair = mlkem_kpke_keygen_from_seed("ML-KEM-768", other_seed)
    keypair1024 = mlkem_kpke_keygen_from_seed(params1024, seed)

    assert keypair == same_keypair
    assert keypair.encryption_key != other_keypair.encryption_key
    assert keypair.parameter_set == "ML-KEM-768"
    assert len(keypair.rho) == 32
    assert len(keypair.t_hat) == params768.k
    assert len(keypair.s_hat) == params768.k
    assert len(keypair.encryption_key) == params768.encapsulation_key_bytes
    assert len(keypair.decryption_key) == 384 * params768.k
    assert keypair.encryption_key[-32:] == keypair.rho
    assert mlkem_decode_vector(
        keypair.encryption_key[:-32],
        k=params768.k,
        d=12,
    ) == keypair.t_hat
    assert mlkem_decode_vector(
        keypair.decryption_key,
        k=params768.k,
        d=12,
    ) == keypair.s_hat
    assert len(keypair1024.encryption_key) == params1024.encapsulation_key_bytes
    assert len(keypair1024.decryption_key) == 384 * params1024.k
    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_kpke_keygen_from_seed("ML-KEM-768", bytes(31))


def test_firstparty_mlkem_kpke_encrypt_decrypt_round_trips_message() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    keypair = mlkem_kpke_keygen_from_seed(
        params,
        hashlib.sha3_256(b"kpke-roundtrip-key").digest(),
    )
    message = hashlib.sha3_256(b"kpke-message").digest()
    randomness = hashlib.sha3_256(b"kpke-randomness").digest()

    encrypted = mlkem_kpke_encrypt(
        params,
        keypair.encryption_key,
        message,
        randomness,
    )
    same_encrypted = mlkem_kpke_encrypt(
        "ML-KEM-768",
        keypair.encryption_key,
        message,
        randomness,
    )
    different_encrypted = mlkem_kpke_encrypt(
        "ML-KEM-768",
        keypair.encryption_key,
        message,
        hashlib.sha3_256(b"other-randomness").digest(),
    )
    decoded = mlkem_kpke_decode_ciphertext(params, encrypted.ciphertext)

    assert encrypted == same_encrypted
    assert encrypted.ciphertext != different_encrypted.ciphertext
    assert encrypted.parameter_set == "ML-KEM-768"
    assert len(encrypted.ciphertext) == params.ciphertext_bytes
    assert len(encrypted.u) == params.k
    assert len(encrypted.v) == ML_KEM_N
    assert all(0 <= value < ML_KEM_Q for poly in encrypted.u for value in poly)
    assert all(0 <= value < ML_KEM_Q for value in encrypted.v)
    assert len(decoded.u) == params.k
    assert len(decoded.v) == ML_KEM_N
    assert all(0 <= value < ML_KEM_Q for poly in decoded.u for value in poly)
    assert all(0 <= value < ML_KEM_Q for value in decoded.v)
    assert mlkem_kpke_decrypt(
        params,
        keypair.decryption_key,
        encrypted.ciphertext,
    ) == message


def test_firstparty_mlkem_kpke_encrypt_decrypt_shapes_for_1024() -> None:
    params = mlkem_parameter_set("ML-KEM-1024")
    keypair = mlkem_kpke_keygen_from_seed(
        params,
        hashlib.sha3_256(b"kpke-1024-key").digest(),
    )
    message = hashlib.sha3_256(b"kpke-1024-message").digest()
    randomness = hashlib.sha3_256(b"kpke-1024-randomness").digest()

    encrypted = mlkem_kpke_encrypt(
        params,
        keypair.encryption_key,
        message,
        randomness,
    )

    assert len(encrypted.ciphertext) == params.ciphertext_bytes
    assert len(encrypted.u) == params.k
    assert mlkem_kpke_decrypt(
        params,
        keypair.decryption_key,
        encrypted.ciphertext,
    ) == message


def test_firstparty_mlkem_kpke_fails_closed_for_invalid_lengths() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    keypair = mlkem_kpke_keygen_from_seed(
        params,
        hashlib.sha3_256(b"kpke-invalid-length-key").digest(),
    )
    message = hashlib.sha3_256(b"kpke-invalid-message").digest()
    randomness = hashlib.sha3_256(b"kpke-invalid-randomness").digest()
    ciphertext = mlkem_kpke_encrypt(
        params,
        keypair.encryption_key,
        message,
        randomness,
    ).ciphertext

    with pytest.raises(MlKemPrimitiveError, match="encryption key length"):
        mlkem_kpke_encrypt(params, keypair.encryption_key[:-1], message, randomness)
    with pytest.raises(MlKemPrimitiveError, match="message must be 32 bytes"):
        mlkem_kpke_encrypt(params, keypair.encryption_key, message[:-1], randomness)
    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_kpke_encrypt(params, keypair.encryption_key, message, bytes(31))
    with pytest.raises(MlKemPrimitiveError, match="decryption key length"):
        mlkem_kpke_decrypt(params, keypair.decryption_key[:-1], ciphertext)
    with pytest.raises(MlKemPrimitiveError, match="ciphertext length"):
        mlkem_kpke_decrypt(params, keypair.decryption_key, ciphertext[:-1])


def test_firstparty_mlkem_keygen_from_seeds_has_fips_shapes() -> None:
    d = hashlib.sha3_256(b"mlkem-keygen-d").digest()
    z = hashlib.sha3_256(b"mlkem-keygen-z").digest()
    other_z = hashlib.sha3_256(b"mlkem-keygen-other-z").digest()
    params768 = mlkem_parameter_set("ML-KEM-768")
    params1024 = mlkem_parameter_set("ML-KEM-1024")

    keypair = mlkem_keygen_from_seeds(params768, d, z)
    same_keypair = mlkem_keygen_from_seeds("ML-KEM-768", d, z)
    other_keypair = mlkem_keygen_from_seeds("ML-KEM-768", d, other_z)
    keypair1024 = mlkem_keygen_from_seeds(params1024, d, z)
    random_keypair = mlkem_keygen(params768)

    assert keypair == same_keypair
    assert keypair.decapsulation_key != other_keypair.decapsulation_key
    assert keypair.parameter_set == "ML-KEM-768"
    assert len(keypair.encapsulation_key) == params768.encapsulation_key_bytes
    assert len(keypair.decapsulation_key) == params768.decapsulation_key_bytes
    assert len(keypair.kpke_decryption_key) == 384 * params768.k
    assert len(keypair.public_key_hash) == ML_KEM_SEED_BYTES
    assert len(keypair.z) == ML_KEM_SEED_BYTES
    assert keypair.public_key_hash == mlkem_hash_h(keypair.encapsulation_key)
    assert keypair.decapsulation_key.startswith(keypair.kpke_decryption_key)
    assert keypair.encapsulation_key in keypair.decapsulation_key
    assert keypair.decapsulation_key.endswith(keypair.public_key_hash + z)
    assert len(keypair1024.encapsulation_key) == params1024.encapsulation_key_bytes
    assert len(keypair1024.decapsulation_key) == params1024.decapsulation_key_bytes
    assert len(random_keypair.encapsulation_key) == params768.encapsulation_key_bytes
    assert len(random_keypair.decapsulation_key) == params768.decapsulation_key_bytes
    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_keygen_from_seeds(params768, d[:-1], z)
    with pytest.raises(MlKemPrimitiveError, match="seed must be 32 bytes"):
        mlkem_keygen_from_seeds(params768, d, z[:-1])


def test_firstparty_mlkem_encapsulate_decapsulate_round_trips_secret() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    keypair = mlkem_keygen_from_seeds(
        params,
        hashlib.sha3_256(b"mlkem-roundtrip-d").digest(),
        hashlib.sha3_256(b"mlkem-roundtrip-z").digest(),
    )
    message = hashlib.sha3_256(b"mlkem-roundtrip-message").digest()

    encapsulated = mlkem_encapsulate_from_message(
        params,
        keypair.encapsulation_key,
        message,
    )
    same_encapsulated = mlkem_encapsulate_from_message(
        "ML-KEM-768",
        keypair.encapsulation_key,
        message,
    )
    random_encapsulated = mlkem_encapsulate(params, keypair.encapsulation_key)

    assert encapsulated == same_encapsulated
    assert encapsulated.parameter_set == "ML-KEM-768"
    assert len(encapsulated.shared_secret) == ML_KEM_SHARED_SECRET_BYTES
    assert len(encapsulated.ciphertext) == params.ciphertext_bytes
    assert len(random_encapsulated.shared_secret) == ML_KEM_SHARED_SECRET_BYTES
    assert len(random_encapsulated.ciphertext) == params.ciphertext_bytes
    assert mlkem_decapsulate(
        params,
        keypair.decapsulation_key,
        encapsulated.ciphertext,
    ) == encapsulated.shared_secret


def test_firstparty_mlkem_decapsulation_uses_implicit_rejection() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    keypair = mlkem_keygen_from_seeds(
        params,
        hashlib.sha3_256(b"mlkem-reject-d").digest(),
        hashlib.sha3_256(b"mlkem-reject-z").digest(),
    )
    encapsulated = mlkem_encapsulate_from_message(
        params,
        keypair.encapsulation_key,
        hashlib.sha3_256(b"mlkem-reject-message").digest(),
    )
    tampered = bytearray(encapsulated.ciphertext)
    tampered[0] ^= 0x01
    tampered_ciphertext = bytes(tampered)

    rejected_secret = mlkem_decapsulate(
        params,
        keypair.decapsulation_key,
        tampered_ciphertext,
    )

    assert rejected_secret == mlkem_hash_j(keypair.z + tampered_ciphertext)
    assert rejected_secret != encapsulated.shared_secret


def test_firstparty_mlkem_fails_closed_for_invalid_lengths_and_key_hash() -> None:
    params = mlkem_parameter_set("ML-KEM-768")
    keypair = mlkem_keygen_from_seeds(
        params,
        hashlib.sha3_256(b"mlkem-invalid-d").digest(),
        hashlib.sha3_256(b"mlkem-invalid-z").digest(),
    )
    encapsulated = mlkem_encapsulate_from_message(
        params,
        keypair.encapsulation_key,
        hashlib.sha3_256(b"mlkem-invalid-message").digest(),
    )
    tampered_key = bytearray(keypair.decapsulation_key)
    public_key_hash_index = 384 * params.k + params.encapsulation_key_bytes
    tampered_key[public_key_hash_index] ^= 0x01

    with pytest.raises(MlKemPrimitiveError, match="encryption key length"):
        mlkem_encapsulate_from_message(
            params,
            keypair.encapsulation_key[:-1],
            bytes(32),
        )
    with pytest.raises(MlKemPrimitiveError, match="message must be 32 bytes"):
        mlkem_encapsulate_from_message(
            params,
            keypair.encapsulation_key,
            bytes(31),
        )
    with pytest.raises(MlKemPrimitiveError, match="decapsulation key length"):
        mlkem_decapsulate(
            params,
            keypair.decapsulation_key[:-1],
            encapsulated.ciphertext,
        )
    with pytest.raises(MlKemPrimitiveError, match="ciphertext length"):
        mlkem_decapsulate(
            params,
            keypair.decapsulation_key,
            encapsulated.ciphertext[:-1],
        )
    with pytest.raises(MlKemPrimitiveError, match="key hash is invalid"):
        mlkem_decapsulate(params, bytes(tampered_key), encapsulated.ciphertext)


@pytest.mark.asyncio
async def test_full_vpn_production_readiness_allows_only_complete_evidence(
    tmp_path: Path,
) -> None:
    required_dataplane_paths = FullVpnProductionReadinessRequirements().required_dataplane_paths
    linux_preflight = evaluate_linux_deployment_preflight(
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        config=LinuxPreflightConfig(),
        apply_commands=(("ip", "link", "set", "x0vpn0", "up"),),
        rollback_commands=(("ip", "link", "delete", "x0vpn0"),),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
    )
    probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"probe-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"remote-{path_label}",
        )
        for path_label, transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "camouflage"),
        )
    )
    dataplane = await evaluate_dataplane_validation(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_dataplane_paths,
            min_successful_probes=len(probes),
        ),
        runner=lambda probe: _successful_probe_result(probe),
        captured_at=NOW,
    )
    tun_dataplane = TunDataplaneValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_dataplane_paths,
            min_successful_probes=len(probes),
        ),
        results=tuple(_successful_tun_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )
    mtu_validation = MtuValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=probes,
            required_path_labels=required_dataplane_paths,
            min_successful_probes=len(probes),
        ),
        results=tuple(_successful_mtu_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )
    snapshot = PolicySnapshot(policy_epoch="epoch-prod", issued_at=NOW)
    source_path = tmp_path / "external-policy.json"
    source_path.write_text(json.dumps(snapshot.to_json_dict()), encoding="utf-8")
    policy_source = ExternalPolicySnapshotSource(
        source_id="prod-policy-control-plane",
        path=source_path,
        expected_snapshot_hash=snapshot.snapshot_hash(),
        allowed_policy_epochs=frozenset({"epoch-prod"}),
        minimum_issued_at=NOW,
        now_provider=lambda: NOW + 1,
    )
    policy_source.load()
    assert policy_source.last_evidence is not None
    rollback = FirstPartyRekeyRollbackEvidence.from_session_bindings(
        rollback_id="readiness-rollback",
        previous_session_id=1,
        previous_transcript_hash=hashlib.sha256(b"previous").hexdigest(),
        next_session_id=2,
        next_transcript_hash=hashlib.sha256(b"next").hexdigest(),
        rollback_plan_id="readiness-rollback-plan",
        generated_at=NOW,
    )
    rekey_decision = evaluate_firstparty_rekey_policy(
        FirstPartyRekeyCadencePolicy(max_session_age_seconds=1),
        FirstPartyRekeyTelemetry(
            session_started_at=NOW - 10,
            now=NOW,
            generation=2,
        ),
        requested_reason="scheduled-rotation",
        rollback_evidence=rollback,
    )
    leak_config = LinuxNetworkPolicyConfig(dns_servers=("9.9.9.9",))
    leak_evidence = evaluate_linux_leak_protection(
        config=leak_config,
        commands=LinuxNetworkPolicyPlanner(config=leak_config).planned_commands(),
    )
    source_audit = audit_firstparty_source_tree(
        Path(__file__).resolve().parents[3] / "src/network/firstparty_vpn"
    )
    rollout_gate = RolloutGateDecision(
        allowed=True,
        reasons=(),
        evidence_hash=hashlib.sha256(b"rollout-gate").hexdigest(),
    )
    pqc_kat = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"readiness-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    pqc_manifest = reviewed_pqc_manifest(kat_hashes=(pqc_kat.suite_hash,))
    pqc_gate = PqcProviderGateDecision(
        allowed=True,
        reasons=(),
        attestation_hash=pqc_manifest.to_attestation().attestation_hash(),
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    zero_trust_evidence = ZeroTrustPolicyEvidence.from_policy(
        ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    )
    requirements = FullVpnProductionReadinessRequirements(
        required_dataplane_probe_matrix_hash=dataplane.probe_matrix_hash(),
        required_linux_host_fingerprint=linux_preflight.host_fingerprint,
        required_pqc_manifest_hash=pqc_manifest.manifest_hash(),
        required_apply_plan_hash=linux_preflight.apply_plan.evidence_hash(),
        required_rollback_plan_hash=linux_preflight.rollback_plan.evidence_hash(),
        required_leak_protection_plan_hash=leak_evidence.command_plan.evidence_hash(),
        required_external_policy_source_hash=policy_source.last_evidence.evidence_hash(),
        required_policy_snapshot_hash=snapshot.snapshot_hash(),
        required_source_audit_root_hash=source_audit.root_hash,
        required_source_audit_tree_hash=source_audit.source_tree_hash,
        required_rekey_rollback_plan_hash=rollback.rollback_plan_hash,
        required_rollout_gate_hash=rollout_gate.decision_hash(),
        required_zero_trust_policy_hash=zero_trust_evidence.policy_hash,
    )
    (
        identity_signer_manifest,
        identity_signer_kat,
        identity_signer_gate,
    ) = reviewed_identity_signer_evidence()
    identity_signer_conformance = reviewed_identity_signer_conformance_evidence(
        identity_signer_manifest,
        identity_signer_kat,
    )
    requirements = replace(
        requirements,
        required_identity_signer_manifest_hash=identity_signer_manifest.manifest_hash(),
    )
    evidence = FullVpnProductionReadinessEvidence(
        target="nl",
        linux_preflight=linux_preflight,
        leak_protection=leak_evidence,
        dataplane_validation=dataplane,
        tun_dataplane_validation=tun_dataplane,
        mtu_validation=mtu_validation,
        pqc_provider_gate=pqc_gate,
        pqc_manifest=pqc_manifest,
        pqc_kat=pqc_kat,
        identity_signer_gate=identity_signer_gate,
        identity_signer_manifest=identity_signer_manifest,
        identity_signer_kat=identity_signer_kat,
        identity_signer_conformance=identity_signer_conformance,
        external_policy_source=policy_source.last_evidence,
        rekey_policy=rekey_decision,
        rollout_gate=rollout_gate,
        source_audit=source_audit,
        zero_trust_policy=zero_trust_evidence,
        policy_snapshot_hash=snapshot.snapshot_hash(),
    )

    decision = evaluate_full_vpn_production_readiness(requirements, evidence)

    assert decision.allowed is True
    assert decision.reasons == ()
    assert len(decision.evidence_hash) == 64
    assert_privacy_safe(decision.to_json_dict())


@pytest.mark.asyncio
async def test_full_vpn_production_readiness_fails_closed_for_missing_or_weak_evidence(
    tmp_path: Path,
) -> None:
    requirements = FullVpnProductionReadinessRequirements()
    partial_probe = DataplaneProbeSpec(
        probe_id="probe-lan",
        path_label="lan",
        transport="udp",
        remote_ref="remote-lan",
    )
    partial_dataplane = await evaluate_dataplane_validation(
        plan=DataplaneValidationPlan(
            probes=(partial_probe,),
            required_path_labels=frozenset({"lan"}),
            min_successful_probes=1,
        ),
        runner=lambda probe: _successful_probe_result(probe),
        captured_at=NOW,
    )
    snapshot = PolicySnapshot(policy_epoch="epoch-prod", issued_at=NOW)
    source_path = tmp_path / "external-policy.json"
    source_path.write_text(json.dumps(snapshot.to_json_dict()), encoding="utf-8")
    policy_source = ExternalPolicySnapshotSource(
        source_id="prod-policy-control-plane",
        path=source_path,
        expected_snapshot_hash=snapshot.snapshot_hash(),
    )
    policy_source.load()
    assert policy_source.last_evidence is not None
    evidence = FullVpnProductionReadinessEvidence(
        target="wrong-target",
        dataplane_validation=partial_dataplane,
        pqc_provider_gate=PqcProviderGateDecision(
            allowed=False,
            reasons=("pqc_provider_not_production",),
            attestation_hash=hashlib.sha256(b"pqc-gate").hexdigest(),
        ),
        identity_signer_gate=ProductionIdentitySignerGateDecision(
            allowed=False,
            reasons=("identity_signer_not_production",),
            attestation_hash=hashlib.sha256(b"identity-gate").hexdigest(),
        ),
        external_policy_source=policy_source.last_evidence,
        rekey_policy=FirstPartyRekeyPolicyDecision(
            required=True,
            allowed=False,
            trigger_reasons=("session_age_exceeded",),
            block_reasons=("rekey_rollback_evidence_missing",),
            evidence_hash=hashlib.sha256(b"rekey").hexdigest(),
            rollback_evidence_hash=None,
        ),
        rollout_gate=RolloutGateDecision(
            allowed=False,
            reasons=("operator_approval_missing",),
            evidence_hash=hashlib.sha256(b"rollout-gate").hexdigest(),
        ),
        source_audit=FirstPartySourceAuditEvidence(
            root_hash=hashlib.sha256(b"source-root").hexdigest(),
            source_tree_hash=hashlib.sha256(b"source-tree").hexdigest(),
            scanned_files=1,
            forbidden_imports=("bad.py:oqs",),
        ),
        policy_snapshot_hash=hashlib.sha256(b"wrong-policy").hexdigest(),
    )

    decision = evaluate_full_vpn_production_readiness(requirements, evidence)

    assert decision.allowed is False
    assert "readiness_target_mismatch" in decision.reasons
    assert "linux_preflight_missing" in decision.reasons
    assert "leak_protection_missing" in decision.reasons
    assert "dataplane_required_path_missing:vps" in decision.reasons
    assert "dataplane_required_path_missing:mobile" in decision.reasons
    assert "dataplane_required_path_missing:restricted-work-wifi" in decision.reasons
    assert "tun_dataplane_validation_missing" in decision.reasons
    assert "mtu_validation_missing" in decision.reasons
    assert "pqc_provider_gate_failed" in decision.reasons
    assert "pqc_kat_missing" in decision.reasons
    assert "identity_signer_gate_failed" in decision.reasons
    assert "identity_signer_manifest_missing" in decision.reasons
    assert "identity_signer_kat_missing" in decision.reasons
    assert "identity_signer_conformance_missing" in decision.reasons
    assert "external_policy_snapshot_hash_mismatch" in decision.reasons
    assert "rekey_policy_failed" in decision.reasons
    assert "rekey_rollback_evidence_missing" in decision.reasons
    assert "rollout_gate_failed" in decision.reasons
    assert "firstparty_source_audit_failed" in decision.reasons
    assert "zero_trust_policy_missing" in decision.reasons
    assert_privacy_safe(decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_weak_zero_trust_policy() -> None:
    requirements = FullVpnProductionReadinessRequirements()
    weak_policy = ZeroTrustPolicy(
        allowed_workloads=frozenset({"vpn-client"}),
        allowed_tenants=frozenset(),
        required_kem_algorithms=frozenset({"RSA-2048"}),
        required_signature_algorithms=frozenset(),
        max_token_lifetime_seconds=7200,
    )

    decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            zero_trust_policy=ZeroTrustPolicyEvidence.from_policy(weak_policy),
        ),
    )

    assert decision.allowed is False
    assert "zero_trust_tenant_allowlist_missing" in decision.reasons
    assert "zero_trust_required_workload_missing:vpn-server" in decision.reasons
    assert "zero_trust_pqc_kem_not_supported:RSA-2048" in decision.reasons
    assert "zero_trust_pqc_signature_allowlist_missing" in decision.reasons
    assert "zero_trust_identity_lifetime_too_long" in decision.reasons


def test_full_vpn_production_readiness_rejects_zero_trust_policy_hash_gaps() -> None:
    policy_evidence = ZeroTrustPolicyEvidence.from_policy(
        ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            zero_trust_policy=policy_evidence,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_zero_trust_policy_hash="f" * 64,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            zero_trust_policy=policy_evidence,
        ),
    )

    assert missing_requirement.allowed is False
    assert "zero_trust_policy_hash_requirement_missing" in missing_requirement.reasons
    assert mismatch.allowed is False
    assert "zero_trust_policy_hash_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(required_zero_trust_policy_hash="bad")


def test_full_vpn_production_readiness_rejects_source_audit_time_gaps(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "core.py").write_text("VALUE = 'first-party'\n", encoding="utf-8")
    requirements = FullVpnProductionReadinessRequirements(
        evaluated_at=NOW,
        max_source_audit_age_seconds=60,
    )
    stale_source_audit = audit_firstparty_source_tree(
        root,
        captured_at=NOW - 61,
    )
    future_source_audit = audit_firstparty_source_tree(
        root,
        captured_at=NOW + 1,
    )

    stale_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            source_audit=stale_source_audit,
        ),
    )
    future_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            source_audit=future_source_audit,
        ),
    )

    assert stale_decision.allowed is False
    assert "firstparty_source_audit_stale" in stale_decision.reasons
    assert future_decision.allowed is False
    assert "firstparty_source_audit_from_future" in future_decision.reasons
    assert_privacy_safe(stale_decision.to_json_dict())
    assert_privacy_safe(future_decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_source_audit_binding_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "core.py").write_text("VALUE = 'first-party'\n", encoding="utf-8")
    source_audit = audit_firstparty_source_tree(root, captured_at=NOW)

    missing_requirements = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            source_audit=source_audit,
        ),
    )
    root_mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_source_audit_root_hash="f" * 64,
            required_source_audit_tree_hash=source_audit.source_tree_hash,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            source_audit=source_audit,
        ),
    )
    tree_mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_source_audit_root_hash=source_audit.root_hash,
            required_source_audit_tree_hash="f" * 64,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            source_audit=source_audit,
        ),
    )

    assert missing_requirements.allowed is False
    assert (
        "firstparty_source_audit_root_requirement_missing"
        in missing_requirements.reasons
    )
    assert (
        "firstparty_source_audit_tree_requirement_missing"
        in missing_requirements.reasons
    )
    assert root_mismatch.allowed is False
    assert "firstparty_source_audit_root_mismatch" in root_mismatch.reasons
    assert tree_mismatch.allowed is False
    assert "firstparty_source_audit_tree_mismatch" in tree_mismatch.reasons
    assert_privacy_safe(missing_requirements.to_json_dict())
    assert_privacy_safe(root_mismatch.to_json_dict())
    assert_privacy_safe(tree_mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(
            required_source_audit_root_hash="not-a-sha256"
        )


def test_full_vpn_production_readiness_rejects_command_plan_hash_gaps() -> None:
    preflight = successful_preflight()
    leak_config = LinuxNetworkPolicyConfig(dns_servers=("9.9.9.9",))
    leak_evidence = evaluate_linux_leak_protection(
        config=leak_config,
        commands=LinuxNetworkPolicyPlanner(config=leak_config).planned_commands(),
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(),
        FullVpnProductionReadinessEvidence(
            target="nl",
            linux_preflight=preflight,
            leak_protection=leak_evidence,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_apply_plan_hash="f" * 64,
            required_rollback_plan_hash="f" * 64,
            required_leak_protection_plan_hash="f" * 64,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            linux_preflight=preflight,
            leak_protection=leak_evidence,
        ),
    )

    assert missing_requirement.allowed is False
    assert "apply_plan_hash_requirement_missing" in missing_requirement.reasons
    assert "rollback_plan_hash_requirement_missing" in missing_requirement.reasons
    assert (
        "leak_protection_plan_hash_requirement_missing"
        in missing_requirement.reasons
    )
    assert mismatch.allowed is False
    assert "apply_plan_hash_mismatch" in mismatch.reasons
    assert "rollback_plan_hash_mismatch" in mismatch.reasons
    assert "leak_protection_plan_hash_mismatch" in mismatch.reasons
    for field in (
        "required_apply_plan_hash",
        "required_rollback_plan_hash",
        "required_leak_protection_plan_hash",
    ):
        with pytest.raises(FullVpnProductionReadinessError, match=field):
            FullVpnProductionReadinessRequirements(**{field: "bad"})
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())


def test_full_vpn_production_readiness_rejects_linux_host_fingerprint_gaps() -> None:
    preflight = successful_preflight()

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_apply_plan_hash=preflight.apply_plan.evidence_hash(),
            required_rollback_plan_hash=preflight.rollback_plan.evidence_hash(),
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            linux_preflight=preflight,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_linux_host_fingerprint="f" * 64,
            required_apply_plan_hash=preflight.apply_plan.evidence_hash(),
            required_rollback_plan_hash=preflight.rollback_plan.evidence_hash(),
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            linux_preflight=preflight,
        ),
    )

    assert missing_requirement.allowed is False
    assert (
        "linux_host_fingerprint_requirement_missing"
        in missing_requirement.reasons
    )
    assert mismatch.allowed is False
    assert "linux_host_fingerprint_mismatch" in mismatch.reasons
    with pytest.raises(
        FullVpnProductionReadinessError,
        match="required_linux_host_fingerprint",
    ):
        FullVpnProductionReadinessRequirements(
            required_linux_host_fingerprint="bad",
        )
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())


def test_full_vpn_production_readiness_rejects_rollout_gate_hash_gaps() -> None:
    rollout_gate = RolloutGateDecision(
        allowed=True,
        reasons=(),
        evidence_hash=hashlib.sha256(b"rollout-gate").hexdigest(),
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rollout_gate=rollout_gate,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_rollout_gate_hash="f" * 64,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rollout_gate=rollout_gate,
        ),
    )

    assert missing_requirement.allowed is False
    assert "rollout_gate_hash_requirement_missing" in missing_requirement.reasons
    assert mismatch.allowed is False
    assert "rollout_gate_hash_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(required_rollout_gate_hash="bad")


def test_full_vpn_production_readiness_binds_rollout_gate_decision_state() -> None:
    allowed = RolloutGateDecision(
        allowed=True,
        reasons=(),
        evidence_hash=hashlib.sha256(b"rollout-gate").hexdigest(),
    )
    tampered = RolloutGateDecision(
        allowed=True,
        reasons=("operator_approval_missing",),
        evidence_hash=allowed.evidence_hash,
    )

    decision = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_rollout_gate_hash=allowed.decision_hash(),
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rollout_gate=tampered,
        ),
    )

    assert allowed.decision_hash() != tampered.decision_hash()
    assert decision.allowed is False
    assert "rollout_gate_hash_mismatch" in decision.reasons
    assert_privacy_safe(decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_rekey_rollback_plan_hash_gaps() -> None:
    rollback_plan_hash = hash_identifier(
        "rekey-rollback-plan",
        namespace="rekey-rollback-plan",
    )
    rekey = FirstPartyRekeyPolicyDecision(
        required=True,
        allowed=True,
        trigger_reasons=("session_age_exceeded",),
        block_reasons=(),
        evidence_hash=hashlib.sha256(b"rekey").hexdigest(),
        rollback_evidence_hash=hashlib.sha256(b"rollback-evidence").hexdigest(),
        rollback_plan_hash=rollback_plan_hash,
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rekey_policy=rekey,
        ),
    )
    missing_hash = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_rekey_rollback_plan_hash=rollback_plan_hash,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rekey_policy=replace(rekey, rollback_plan_hash=None),
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_rekey_rollback_plan_hash="f" * 64,
            evaluated_at=NOW,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            rekey_policy=rekey,
        ),
    )

    assert missing_requirement.allowed is False
    assert "rekey_rollback_plan_requirement_missing" in missing_requirement.reasons
    assert missing_hash.allowed is False
    assert "rekey_rollback_plan_hash_missing" in missing_hash.reasons
    assert mismatch.allowed is False
    assert "rekey_rollback_plan_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(missing_hash.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(
            required_rekey_rollback_plan_hash="bad"
        )


def test_full_vpn_production_readiness_rejects_identity_signer_kat_time_gaps() -> None:
    requirements = FullVpnProductionReadinessRequirements(
        evaluated_at=NOW,
        max_identity_signer_kat_age_seconds=60,
    )
    _manifest, kat_result, _gate = reviewed_identity_signer_evidence()

    stale_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_kat=replace(kat_result, captured_at=NOW - 61),
        ),
    )
    future_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_kat=replace(kat_result, captured_at=NOW + 1),
        ),
    )

    assert stale_decision.allowed is False
    assert "identity_signer_kat_stale" in stale_decision.reasons
    assert future_decision.allowed is False
    assert "identity_signer_kat_from_future" in future_decision.reasons
    assert_privacy_safe(stale_decision.to_json_dict())
    assert_privacy_safe(future_decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_identity_signer_kat_binding_mismatch() -> None:
    requirements = FullVpnProductionReadinessRequirements()
    manifest, kat_result, gate = reviewed_identity_signer_evidence()

    for field, value, reason in (
        (
            "provider_id",
            "other-firstparty-identity-signer",
            "identity_signer_kat_provider_mismatch",
        ),
        ("key_id", "other-key", "identity_signer_kat_key_mismatch"),
        ("signature_algorithm", "ML-DSA-87", "identity_signer_kat_algorithm_mismatch"),
        (
            "implementation_hash",
            "f" * 64,
            "identity_signer_kat_implementation_mismatch",
        ),
    ):
        decision = evaluate_full_vpn_production_readiness(
            requirements,
            FullVpnProductionReadinessEvidence(
                target="nl",
                identity_signer_gate=gate,
                identity_signer_manifest=manifest,
                identity_signer_kat=replace(kat_result, **{field: value}),
            ),
        )

        assert decision.allowed is False
        assert reason in decision.reasons
        assert_privacy_safe(decision.to_json_dict())

    for field, value, reason in (
        (
            "provider_id",
            "other-firstparty-identity-signer",
            "identity_signer_gate_kat_provider_mismatch",
        ),
        ("key_id", "other-key", "identity_signer_gate_kat_key_mismatch"),
        ("signature_algorithm", "ML-DSA-87", "identity_signer_gate_kat_algorithm_mismatch"),
        (
            "implementation_hash",
            "f" * 64,
            "identity_signer_gate_kat_implementation_mismatch",
        ),
    ):
        decision = evaluate_full_vpn_production_readiness(
            requirements,
            FullVpnProductionReadinessEvidence(
                target="nl",
                identity_signer_gate=replace(gate, **{field: value}),
                identity_signer_manifest=manifest,
                identity_signer_kat=kat_result,
            ),
        )

        assert decision.allowed is False
        assert reason in decision.reasons
        assert_privacy_safe(decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_pqc_kat_time_gaps() -> None:
    requirements = FullVpnProductionReadinessRequirements(
        evaluated_at=NOW,
        max_pqc_kat_age_seconds=60,
    )
    kat_result = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"readiness-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
    )

    stale_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            pqc_kat=replace(kat_result, captured_at=NOW - 61),
        ),
    )
    future_decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            pqc_kat=replace(kat_result, captured_at=NOW + 1),
        ),
    )

    assert stale_decision.allowed is False
    assert "pqc_kat_stale" in stale_decision.reasons
    assert future_decision.allowed is False
    assert "pqc_kat_from_future" in future_decision.reasons
    assert_privacy_safe(stale_decision.to_json_dict())
    assert_privacy_safe(future_decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_pqc_manifest_hash_gaps() -> None:
    kat = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"readiness-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    manifest = reviewed_pqc_manifest(kat_hashes=(kat.suite_hash,))
    gate = PqcProviderGateDecision(
        allowed=True,
        reasons=(),
        attestation_hash=manifest.to_attestation().attestation_hash(),
        provider_id=manifest.provider_id,
        kem_algorithm=manifest.kem_algorithm,
        signature_algorithm=manifest.signature_algorithm,
        implementation_hash=manifest.implementation_hash,
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(),
        FullVpnProductionReadinessEvidence(
            target="nl",
            pqc_provider_gate=gate,
            pqc_manifest=manifest,
            pqc_kat=kat,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(required_pqc_manifest_hash="f" * 64),
        FullVpnProductionReadinessEvidence(
            target="nl",
            pqc_provider_gate=gate,
            pqc_manifest=manifest,
            pqc_kat=kat,
        ),
    )

    assert missing_requirement.allowed is False
    assert "pqc_manifest_hash_requirement_missing" in missing_requirement.reasons
    assert mismatch.allowed is False
    assert "pqc_manifest_hash_mismatch" in mismatch.reasons
    with pytest.raises(
        FullVpnProductionReadinessError,
        match="required_pqc_manifest_hash",
    ):
        FullVpnProductionReadinessRequirements(required_pqc_manifest_hash="bad")
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())


def test_full_vpn_production_readiness_rejects_pqc_manifest_binding_gaps() -> None:
    kat = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"readiness-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    manifest = reviewed_pqc_manifest(kat_hashes=(kat.suite_hash,))
    gate = PqcProviderGateDecision(
        allowed=True,
        reasons=(),
        attestation_hash=manifest.to_attestation().attestation_hash(),
        provider_id=manifest.provider_id,
        kem_algorithm=manifest.kem_algorithm,
        signature_algorithm=manifest.signature_algorithm,
        implementation_hash=manifest.implementation_hash,
    )
    requirements = FullVpnProductionReadinessRequirements(
        required_pqc_manifest_hash=manifest.manifest_hash(),
    )

    for evidence_patch, reason in (
        (
            {"pqc_provider_gate": replace(gate, attestation_hash="f" * 64)},
            "pqc_manifest_attestation_mismatch",
        ),
        (
            {"pqc_manifest": replace(manifest, reviewed=False)},
            "pqc_manifest_not_reviewed",
        ),
        (
            {"pqc_kat": replace(kat, suite_hash="f" * 64)},
            "pqc_kat_not_in_manifest",
        ),
        (
            {"pqc_kat": replace(kat, provider_id="other-firstparty-pqc")},
            "pqc_kat_provider_mismatch",
        ),
    ):
        evidence_kwargs = {
            "pqc_provider_gate": gate,
            "pqc_manifest": manifest,
            "pqc_kat": kat,
        }
        evidence_kwargs.update(evidence_patch)
        evidence = FullVpnProductionReadinessEvidence(target="nl", **evidence_kwargs)
        decision = evaluate_full_vpn_production_readiness(requirements, evidence)

        assert decision.allowed is False
        assert reason in decision.reasons
        assert_privacy_safe(decision.to_json_dict())


def test_full_vpn_production_readiness_rejects_pqc_gate_kat_mismatch() -> None:
    requirements = FullVpnProductionReadinessRequirements(evaluated_at=NOW)
    gate = PqcProviderGateDecision(
        allowed=True,
        reasons=(),
        attestation_hash=hashlib.sha256(b"pqc-gate").hexdigest(),
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        implementation_hash="a" * 64,
    )
    kat = PqcKatResult(
        passed=True,
        reasons=(),
        suite_hash=hashlib.sha256(b"readiness-pqc-kat-suite").hexdigest(),
        vector_count=1,
        captured_at=NOW,
        provider_id=gate.provider_id,
        kem_algorithm=gate.kem_algorithm,
        signature_algorithm=gate.signature_algorithm,
        implementation_hash=gate.implementation_hash,
    )

    for field, value, reason in (
        (
            "provider_id",
            "other-firstparty-pqc",
            "pqc_provider_gate_kat_provider_mismatch",
        ),
        ("kem_algorithm", "ML-KEM-1024", "pqc_provider_gate_kat_kem_algorithm_mismatch"),
        (
            "signature_algorithm",
            "ML-DSA-87",
            "pqc_provider_gate_kat_signature_algorithm_mismatch",
        ),
        (
            "implementation_hash",
            "b" * 64,
            "pqc_provider_gate_kat_implementation_mismatch",
        ),
    ):
        decision = evaluate_full_vpn_production_readiness(
            requirements,
            FullVpnProductionReadinessEvidence(
                target="nl",
                pqc_provider_gate=gate,
                pqc_kat=replace(kat, **{field: value}),
            ),
        )

        assert decision.allowed is False
        assert reason in decision.reasons
        assert_privacy_safe(decision.to_json_dict())


@pytest.mark.asyncio
async def test_full_vpn_production_readiness_rejects_future_validation_evidence() -> None:
    requirements = FullVpnProductionReadinessRequirements(evaluated_at=NOW)
    probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"probe-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"remote-{path_label}",
        )
        for path_label, transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "camouflage"),
        )
    )
    plan = DataplaneValidationPlan(
        probes=probes,
        required_path_labels=requirements.required_dataplane_paths,
        min_successful_probes=len(probes),
    )
    future_dataplane = await evaluate_dataplane_validation(
        plan=plan,
        runner=_successful_probe_result,
        captured_at=NOW + 60,
    )
    future_tun = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_tun_probe_result(probe) for probe in probes),
        captured_at=NOW + 60,
    )
    future_mtu = MtuValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_mtu_probe_result(probe) for probe in probes),
        captured_at=NOW + 60,
    )

    decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            dataplane_validation=future_dataplane,
            tun_dataplane_validation=future_tun,
            mtu_validation=future_mtu,
        ),
    )

    assert decision.allowed is False
    assert "dataplane_validation_from_future" in decision.reasons
    assert "tun_dataplane_validation_from_future" in decision.reasons
    assert "mtu_validation_from_future" in decision.reasons


@pytest.mark.asyncio
async def test_full_vpn_production_readiness_rejects_dataplane_probe_matrix_hash_gaps() -> None:
    probe = DataplaneProbeSpec(
        probe_id="probe-lan",
        path_label="lan",
        transport="udp",
        remote_ref="remote-lan",
    )
    dataplane = await evaluate_dataplane_validation(
        plan=DataplaneValidationPlan(
            probes=(probe,),
            required_path_labels=frozenset({"lan"}),
            min_successful_probes=1,
        ),
        runner=_successful_probe_result,
        captured_at=NOW,
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            dataplane_validation=dataplane,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            evaluated_at=NOW,
            required_dataplane_probe_matrix_hash="f" * 64,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            dataplane_validation=dataplane,
        ),
    )

    assert missing_requirement.allowed is False
    assert "dataplane_probe_matrix_requirement_missing" in missing_requirement.reasons
    assert mismatch.allowed is False
    assert "dataplane_probe_matrix_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(
            required_dataplane_probe_matrix_hash="bad"
        )


def test_full_vpn_production_readiness_rejects_external_policy_time_gaps() -> None:
    snapshot_hash = hashlib.sha256(b"policy-snapshot").hexdigest()
    requirements = FullVpnProductionReadinessRequirements(
        evaluated_at=NOW,
        required_policy_snapshot_hash=snapshot_hash,
    )

    def policy_evidence(
        *,
        issued_at: int,
        loaded_at: int,
    ) -> ExternalPolicySnapshotSourceEvidence:
        return ExternalPolicySnapshotSourceEvidence(
            source_id_hash=hash_identifier(
                "prod-policy-control-plane",
                namespace="policy-source-id",
            ),
            source_path_hash=hash_identifier(
                "/redacted/external-policy.json",
                namespace="policy-source-path",
            ),
            source_document_hash=hashlib.sha256(b"policy-document").hexdigest(),
            snapshot_hash=snapshot_hash,
            policy_epoch_hash=hash_identifier("epoch-prod", namespace="policy-epoch"),
            issued_at=issued_at,
            loaded_at=loaded_at,
        )

    future = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=policy_evidence(
                issued_at=NOW + 10,
                loaded_at=NOW + 20,
            ),
            policy_snapshot_hash=snapshot_hash,
        ),
    )
    stale = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=policy_evidence(
                issued_at=NOW - 7200,
                loaded_at=NOW - 7200,
            ),
            policy_snapshot_hash=snapshot_hash,
        ),
    )
    inverted = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=policy_evidence(
                issued_at=NOW,
                loaded_at=NOW - 1,
            ),
            policy_snapshot_hash=snapshot_hash,
        ),
    )

    assert future.allowed is False
    assert "external_policy_snapshot_from_future" in future.reasons
    assert "external_policy_source_loaded_from_future" in future.reasons
    assert stale.allowed is False
    assert "external_policy_source_load_stale" in stale.reasons
    assert "external_policy_snapshot_stale" in stale.reasons
    assert inverted.allowed is False
    assert "external_policy_source_loaded_before_snapshot_issue" in inverted.reasons


def test_full_vpn_production_readiness_rejects_policy_snapshot_hash_gaps() -> None:
    snapshot_hash = hashlib.sha256(b"policy-snapshot").hexdigest()
    source_evidence = ExternalPolicySnapshotSourceEvidence(
        source_id_hash=hash_identifier(
            "prod-policy-control-plane",
            namespace="policy-source-id",
        ),
        source_path_hash=hash_identifier(
            "/redacted/external-policy.json",
            namespace="policy-source-path",
        ),
        source_document_hash=hashlib.sha256(b"policy-document").hexdigest(),
        snapshot_hash=snapshot_hash,
        policy_epoch_hash=hash_identifier("epoch-prod", namespace="policy-epoch"),
        issued_at=NOW,
        loaded_at=NOW,
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(evaluated_at=NOW),
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=source_evidence,
            policy_snapshot_hash=snapshot_hash,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            evaluated_at=NOW,
            required_policy_snapshot_hash="f" * 64,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=source_evidence,
            policy_snapshot_hash=snapshot_hash,
        ),
    )

    assert missing_requirement.allowed is False
    assert "policy_snapshot_hash_requirement_missing" in missing_requirement.reasons
    assert mismatch.allowed is False
    assert "policy_snapshot_hash_requirement_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(required_policy_snapshot_hash="bad")


def test_full_vpn_production_readiness_rejects_external_policy_source_hash_gaps() -> None:
    snapshot_hash = hashlib.sha256(b"policy-snapshot").hexdigest()
    source_evidence = ExternalPolicySnapshotSourceEvidence(
        source_id_hash=hash_identifier(
            "prod-policy-control-plane",
            namespace="policy-source-id",
        ),
        source_path_hash=hash_identifier(
            "/redacted/external-policy.json",
            namespace="policy-source-path",
        ),
        source_document_hash=hashlib.sha256(b"policy-document").hexdigest(),
        snapshot_hash=snapshot_hash,
        policy_epoch_hash=hash_identifier("epoch-prod", namespace="policy-epoch"),
        issued_at=NOW,
        loaded_at=NOW,
    )

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            evaluated_at=NOW,
            required_policy_snapshot_hash=snapshot_hash,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=source_evidence,
            policy_snapshot_hash=snapshot_hash,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            evaluated_at=NOW,
            required_external_policy_source_hash="f" * 64,
            required_policy_snapshot_hash=snapshot_hash,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            external_policy_source=source_evidence,
            policy_snapshot_hash=snapshot_hash,
        ),
    )

    assert missing_requirement.allowed is False
    assert (
        "external_policy_source_hash_requirement_missing"
        in missing_requirement.reasons
    )
    assert mismatch.allowed is False
    assert "external_policy_source_hash_mismatch" in mismatch.reasons
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())
    with pytest.raises(FullVpnProductionReadinessError, match="sha256 hex"):
        FullVpnProductionReadinessRequirements(
            required_external_policy_source_hash="bad"
        )


def test_full_vpn_production_readiness_rejects_identity_signer_manifest_hash_gaps() -> None:
    manifest, kat_result, gate = reviewed_identity_signer_evidence()

    missing_requirement = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(),
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
        ),
    )
    mismatch = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            required_identity_signer_manifest_hash="f" * 64,
        ),
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
        ),
    )

    assert missing_requirement.allowed is False
    assert (
        "identity_signer_manifest_hash_requirement_missing"
        in missing_requirement.reasons
    )
    assert mismatch.allowed is False
    assert "identity_signer_manifest_hash_mismatch" in mismatch.reasons
    with pytest.raises(
        FullVpnProductionReadinessError,
        match="required_identity_signer_manifest_hash",
    ):
        FullVpnProductionReadinessRequirements(
            required_identity_signer_manifest_hash="bad",
        )
    assert_privacy_safe(missing_requirement.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())


def test_full_vpn_production_readiness_rejects_identity_signer_manifest_and_kat_gaps() -> None:
    requirements = FullVpnProductionReadinessRequirements()
    manifest, kat_result, gate = reviewed_identity_signer_evidence()

    mismatch = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=ProductionIdentitySignerGateDecision(
                allowed=True,
                reasons=(),
                attestation_hash=hashlib.sha256(b"wrong-identity-gate").hexdigest(),
            ),
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
        ),
    )
    assert "identity_signer_manifest_attestation_mismatch" in mismatch.reasons

    failed_kat = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=replace(
                kat_result,
                passed=False,
                reasons=("identity_signer_kat_signature_mismatch",),
            ),
        ),
    )
    assert "identity_signer_kat_failed" in failed_kat.reasons

    empty_kat = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=replace(kat_result, vector_count=0),
        ),
    )
    assert "identity_signer_kat_vectors_missing" in empty_kat.reasons

    unbound_kat = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=replace(kat_result, suite_hash="f" * 64),
        ),
    )
    assert "identity_signer_kat_not_in_manifest" in unbound_kat.reasons

    test_manifest = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=replace(manifest, mode="test"),
            identity_signer_kat=kat_result,
        ),
    )
    assert "identity_signer_manifest_not_production" in test_manifest.reasons

    reference_conformance = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
            identity_signer_conformance=reviewed_identity_signer_conformance_evidence(
                manifest,
                kat_result,
                profile="reference",
            ),
        ),
    )
    assert "identity_signer_conformance_not_production" in reference_conformance.reasons

    unbound_conformance = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
            identity_signer_conformance=replace(
                reviewed_identity_signer_conformance_evidence(manifest, kat_result),
                kat_suite_hash="f" * 64,
            ),
        ),
    )
    assert "identity_signer_conformance_kat_mismatch" in unbound_conformance.reasons

    mismatched_conformance_review = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
            identity_signer_conformance=replace(
                reviewed_identity_signer_conformance_evidence(manifest, kat_result),
                review_evidence_hash="f" * 64,
            ),
        ),
    )
    assert (
        "identity_signer_conformance_review_evidence_mismatch"
        in mismatched_conformance_review.reasons
    )

    mismatched_conformance_vectors = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target="nl",
            identity_signer_gate=gate,
            identity_signer_manifest=manifest,
            identity_signer_kat=kat_result,
            identity_signer_conformance=reviewed_identity_signer_conformance_evidence(
                manifest,
                kat_result,
                vector_count=kat_result.vector_count + 1,
            ),
        ),
    )
    assert (
        "identity_signer_conformance_vector_count_mismatch"
        in mismatched_conformance_vectors.reasons
    )

    with pytest.raises(ProductionControlPlaneError, match="requires reasons"):
        reviewed_identity_signer_conformance_evidence(
            manifest,
            kat_result,
            passed=False,
        )


def test_policy_distribution_envelope_persists_snapshot(tmp_path: Path) -> None:
    key = signing_key("policy-key-1")
    snapshot = PolicySnapshot(
        policy_epoch="epoch-2",
        issued_at=NOW,
        revocations=RevocationList(key_ids={"id-key-old"}),
    )
    distributor = PolicySnapshotDistributor(
        issuer="x0tta6bl4-policy-authority",
        signing_key=key,
    )
    envelope = distributor.issue(snapshot, sequence=1, now=NOW + 1)
    store = DurablePolicyStore(tmp_path / "policy.json")
    receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=store),
    )

    applied = receiver.accept(envelope.to_bytes())
    loaded = store.load()

    assert applied.snapshot_hash() == snapshot.snapshot_hash()
    assert loaded.revocations.key_ids == {"id-key-old"}
    assert receiver.current_sequence == 1


def test_policy_distribution_rejects_tamper_and_rollback(tmp_path: Path) -> None:
    key = signing_key("policy-key-1")
    distributor = PolicySnapshotDistributor(
        issuer="x0tta6bl4-policy-authority",
        signing_key=key,
    )
    store = DurablePolicyStore(tmp_path / "policy.json")
    receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=store),
    )
    snapshot = PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW + 10)
    envelope = distributor.issue(snapshot, sequence=2, now=NOW + 11)
    tampered = replace(envelope, signature=b"\x00" * 32)

    with pytest.raises(PolicyDistributionError, match="signature invalid"):
        receiver.accept(tampered)

    receiver.accept(envelope)
    lower_sequence = distributor.issue(snapshot, sequence=1, now=NOW + 12)
    with pytest.raises(PolicyDistributionError, match="sequence rollback"):
        receiver.accept(lower_sequence)

    older_snapshot = PolicySnapshot(policy_epoch="epoch-1", issued_at=NOW)
    older_envelope = distributor.issue(older_snapshot, sequence=3, now=NOW + 13)
    with pytest.raises(PolicyDistributionError, match="refresh failed"):
        receiver.accept(older_envelope)


def test_policy_distribution_durable_sequence_blocks_restart_rollback(
    tmp_path: Path,
) -> None:
    key = signing_key("policy-key-1")
    distributor = PolicySnapshotDistributor(
        issuer="x0tta6bl4-policy-authority",
        signing_key=key,
    )
    policy_store = DurablePolicyStore(tmp_path / "policy.json")
    sequence_store = DurablePolicySequenceStore(tmp_path / "policy-sequence.json")
    first_receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=policy_store),
        sequence_store=sequence_store,
    )
    initial_snapshot = PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW + 10)
    first_receiver.accept(
        distributor.issue(initial_snapshot, sequence=7, now=NOW + 11)
    )

    restarted_receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=policy_store),
        sequence_store=sequence_store,
    )
    assert restarted_receiver.current_sequence == 7

    replay = distributor.issue(initial_snapshot, sequence=6, now=NOW + 12)
    with pytest.raises(PolicyDistributionError, match="sequence rollback"):
        restarted_receiver.accept(replay)

    newer_snapshot = PolicySnapshot(policy_epoch="epoch-3", issued_at=NOW + 20)
    applied = restarted_receiver.accept(
        distributor.issue(newer_snapshot, sequence=8, now=NOW + 21)
    )

    assert applied.policy_epoch == "epoch-3"
    assert sequence_store.load().sequence == 8


def test_policy_distribution_sequence_state_fails_closed_when_untrusted(
    tmp_path: Path,
) -> None:
    key = signing_key("policy-key-1")
    distributor = PolicySnapshotDistributor(
        issuer="x0tta6bl4-policy-authority",
        signing_key=key,
    )
    policy_store = DurablePolicyStore(tmp_path / "policy.json")
    sequence_store = DurablePolicySequenceStore(tmp_path / "policy-sequence.json")
    receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=policy_store),
        sequence_store=sequence_store,
    )
    receiver.accept(
        distributor.issue(
            PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW + 10),
            sequence=3,
            now=NOW + 11,
        )
    )

    missing_store = DurablePolicySequenceStore(tmp_path / "missing-sequence.json")
    with pytest.raises(PolicyDistributionError, match="missing for existing snapshot"):
        PolicySnapshotReceiver(
            expected_issuer="x0tta6bl4-policy-authority",
            verification_key=key,
            refresh_client=PolicyRefreshClient(store=policy_store),
            sequence_store=missing_store,
        )

    raw = sequence_store.path.read_text(encoding="utf-8")
    sequence_store.path.write_text(
        raw.replace('"sequence":3', '"sequence":1'),
        encoding="utf-8",
    )
    with pytest.raises(PolicyDistributionError, match="state hash mismatch"):
        PolicySnapshotReceiver(
            expected_issuer="x0tta6bl4-policy-authority",
            verification_key=key,
            refresh_client=PolicyRefreshClient(store=policy_store),
            sequence_store=sequence_store,
        )


def test_policy_snapshot_enforces_device_posture_and_durable_revocation() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    good_token = authority.issue(
        issue_request(
            "vpn-client",
            attributes={
                "posture_status": "healthy",
                "posture_checked_at": str(NOW - 60),
            },
        ),
        now=NOW,
    )
    stale_token = authority.issue(
        issue_request(
            "vpn-client",
            attributes={
                "posture_status": "healthy",
                "posture_checked_at": str(NOW - 7200),
            },
        ),
        now=NOW,
    )
    bad_token = authority.issue(
        issue_request(
            "vpn-client",
            attributes={
                "posture_status": "unknown",
                "posture_checked_at": str(NOW - 60),
            },
        ),
        now=NOW,
    )
    revocations = RevocationList()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    snapshot = PolicySnapshot(
        policy_epoch="epoch-1",
        issued_at=NOW,
        revocations=revocations,
        posture_policy=DevicePosturePolicy(max_posture_age_seconds=300),
    )

    assert snapshot.evaluate_signed_identity(
        verifier,
        good_token,
        policy=policy,
        now=NOW,
    ).allowed is True

    stale = snapshot.evaluate_signed_identity(
        verifier,
        stale_token,
        policy=policy,
        now=NOW,
    )
    assert "device_posture_stale" in stale.reasons

    bad = snapshot.evaluate_signed_identity(
        verifier,
        bad_token,
        policy=policy,
        now=NOW,
    )
    assert "device_posture_mismatch:posture_status" in bad.reasons

    revocations.revoke_identity(good_token)
    revoked = snapshot.evaluate_signed_identity(
        verifier,
        good_token,
        policy=policy,
        now=NOW,
    )
    assert "identity_revoked" in revoked.reasons


def test_pqc_key_schedule_derives_crossed_directional_keys() -> None:
    keys = derive_session_keys(session_material())

    assert keys.client_tx == keys.server_rx
    assert keys.server_tx == keys.client_rx
    assert keys.client_tx != keys.client_rx
    assert keys.session_id > 0


def test_pqc_key_schedule_rejects_non_pqc_algorithm() -> None:
    material = PqcSessionMaterial.create(
        kem_algorithm="classic-only",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        transcript=b"t",
        client_identity_hash=b"c" * 32,
        server_identity_hash=b"s" * 32,
        client_nonce=b"c" * 32,
        server_nonce=b"s" * 32,
    )

    with pytest.raises(FrameCryptoError):
        derive_session_keys(material)


def test_local_pqc_provider_establishes_dev_session() -> None:
    provider = LocalTestPqcProvider(issued_at=0)
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    session = establish_firstparty_session_from_pqc_provider(
        pqc_provider=provider,
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=policy,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    encoded = session.client_codec.encode(
        Frame(
            frame_type=FrameType.PING,
            session_id=session.session_id,
            sequence=1,
            payload=b"pqc-provider",
        )
    )
    assert session.server_codec.decode(encoded).payload == b"pqc-provider"


def test_pqc_provider_session_accepts_only_verified_signed_identities() -> None:
    provider = LocalTestPqcProvider(issued_at=0)
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    revocations = RevocationList()

    session = establish_firstparty_session_from_pqc_provider_and_signed_identities(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        revocations=revocations,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True

    revocations.revoke_identity(client_token)
    with pytest.raises(ZeroTrustAdmissionError) as revoked:
        establish_firstparty_session_from_pqc_provider_and_signed_identities(
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            revocations=revocations,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )
    assert "identity_revoked" in str(revoked.value)

    tampered = replace(server_token, signature=b"\x00" * len(server_token.signature))
    with pytest.raises(ZeroTrustAdmissionError) as bad_signature:
        establish_firstparty_session_from_pqc_provider_and_signed_identities(
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=tampered,
            identity_authority=verifier,
            policy=policy,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )
    assert "identity_signature_invalid" in str(bad_signature.value)


def test_pqc_production_gate_rejects_local_test_provider() -> None:
    provider = LocalTestPqcProvider(issued_at=0)
    transcript = b"test-transcript"
    material = provider.create_session_material(
        transcript=transcript,
        client_identity_hash=b"c" * 32,
        server_identity_hash=b"s" * 32,
    )
    gate = PqcProductionGate(require_production=True)

    decision = gate.evaluate(material, now=NOW)

    assert decision.allowed is False
    assert "pqc_provider_not_production" in decision.reasons
    assert "pqc_provider_not_reviewed" in decision.reasons
    assert "pqc_provider_implementation_hash_missing" in decision.reasons
    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_pqc_provider(
            pqc_provider=provider,
            client_identity=claims("vpn-client"),
            server_identity=claims("vpn-server"),
            policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
            require_production_provider=True,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    assert "pqc_provider_not_production" in str(exc.value)


def test_pqc_kem_profile_uses_strict_mlkem_output_shapes() -> None:
    mlkem768 = pqc_kem_profile("ML-KEM-768")
    mlkem1024 = pqc_kem_profile("ML-KEM-1024")

    assert mlkem768.security_category == 3
    assert mlkem768.encapsulation_key_bytes == 1184
    assert mlkem768.decapsulation_key_bytes == 2400
    assert mlkem768.ciphertext_bytes == 1088
    assert mlkem768.shared_secret_bytes == 32
    assert mlkem1024.security_category == 5
    assert mlkem1024.ciphertext_bytes == 1568
    with pytest.raises(PqcProviderError, match="unsupported PQC KEM profile"):
        pqc_kem_profile("ML-KEM-512")


def test_pqc_production_gate_rejects_short_mlkem_ciphertext_shape() -> None:
    attestation = PqcProviderAttestation(
        provider_id="reviewed-firstparty-pqc",
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        mode="production",
        reviewed=True,
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
        implementation_hash="shape-test-implementation",
    )
    material = PqcSessionSecretMaterial(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        shared_secret=b"s" * 32,
        ciphertext=b"short-ciphertext",
        attestation=attestation,
    )

    decision = PqcProductionGate(require_production=True).evaluate(
        material,
        now=NOW,
    )

    assert decision.allowed is False
    assert "pqc_ciphertext_length_invalid" in decision.reasons
    assert "pqc_shared_secret_length_invalid" not in decision.reasons


def test_pqc_production_gate_accepts_trusted_attested_provider() -> None:
    provider = FakeProductionPqcProvider()
    gate = PqcProductionGate(
        require_production=True,
        trusted_provider_ids=frozenset({"reviewed-firstparty-pqc"}),
        trusted_implementation_hashes=frozenset({"pqc-implementation-hash-1"}),
    )

    session = establish_firstparty_session_from_pqc_provider(
        pqc_provider=provider,
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        production_gate=gate,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True


def test_pqc_manifest_store_round_trips_and_rejects_tamper(tmp_path: Path) -> None:
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    manifest = reviewed_pqc_manifest()

    store.save_all((manifest,))
    loaded = store.load_all()

    assert loaded == (manifest,)
    assert store.find(
        provider_id="reviewed-firstparty-pqc",
        implementation_hash="a" * 64,
    ) == manifest

    raw = store.path.read_text(encoding="utf-8")
    store.path.write_text(
        raw.replace('"reviewed":true', '"reviewed":false'),
        encoding="utf-8",
    )
    with pytest.raises(PqcProviderError, match="manifest hash mismatch"):
        store.load_all()


def test_pqc_manifest_gate_accepts_reviewed_provider_for_session(tmp_path: Path) -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(implementation)
    kat_result = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_pqc_manifest(
        implementation_hash=implementation.implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    provider = FirstPartyPqcProvider(
        implementation=implementation,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((manifest,))
    gate = PqcManifestProductionGate(manifest_store=store)

    session = establish_firstparty_session_from_pqc_provider(
        pqc_provider=provider,
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        production_gate=gate,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True


def test_pqc_manifest_gate_blocks_unmanifested_provider_for_session(
    tmp_path: Path,
) -> None:
    provider = FakeProductionPqcProvider(implementation_hash="e" * 64)
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((reviewed_pqc_manifest(implementation_hash="a" * 64),))
    gate = PqcManifestProductionGate(manifest_store=store)

    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_pqc_provider(
            pqc_provider=provider,
            client_identity=claims("vpn-client"),
            server_identity=claims("vpn-server"),
            policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
            production_gate=gate,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "pqc_manifest_missing" in str(exc.value)


def test_pqc_manifest_gate_blocks_provider_without_kat_result(
    tmp_path: Path,
) -> None:
    implementation_hash = "a" * 64
    provider = FakeProductionPqcProvider(implementation_hash=implementation_hash)
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((reviewed_pqc_manifest(implementation_hash=implementation_hash),))
    gate = PqcManifestProductionGate(manifest_store=store)

    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_pqc_provider(
            pqc_provider=provider,
            client_identity=claims("vpn-client"),
            server_identity=claims("vpn-server"),
            policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
            production_gate=gate,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "pqc_kat_missing" in str(exc.value)


def test_pqc_manifest_gate_blocks_stale_or_future_kat_for_session(
    tmp_path: Path,
) -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(implementation)
    kat_result = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_pqc_manifest(
        implementation_hash=implementation.implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((manifest,))
    gate = PqcManifestProductionGate(
        manifest_store=store,
        max_kat_age_seconds=60,
    )

    for captured_at, reason in (
        (NOW - 61, "pqc_kat_stale"),
        (NOW + 1, "pqc_kat_from_future"),
    ):
        provider = FirstPartyPqcProvider(
            implementation=implementation,
            manifest=manifest,
            kat_vectors=(vector,),
            kat_captured_at=captured_at,
        )
        with pytest.raises(ZeroTrustAdmissionError) as exc:
            establish_firstparty_session_from_pqc_provider(
                pqc_provider=provider,
                client_identity=claims("vpn-client"),
                server_identity=claims("vpn-server"),
                policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
                production_gate=gate,
                now=NOW,
                client_nonce=b"client-nonce".ljust(32, b"c"),
                server_nonce=b"server-nonce".ljust(32, b"s"),
            )

        assert reason in str(exc.value)

    with pytest.raises(PqcProviderError, match="KAT max age"):
        PqcManifestProductionGate(manifest_store=store, max_kat_age_seconds=0)


def test_pqc_manifest_gate_blocks_kat_binding_mismatch_for_session(
    tmp_path: Path,
) -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(implementation)
    kat_result = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_pqc_manifest(
        implementation_hash=implementation.implementation_hash,
        kat_hashes=(kat_result.suite_hash,),
    )
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((manifest,))
    gate = PqcManifestProductionGate(manifest_store=store)

    for field, value, reason in (
        ("provider_id", "other-firstparty-pqc", "pqc_kat_provider_mismatch"),
        ("kem_algorithm", "ML-KEM-1024", "pqc_kat_kem_algorithm_mismatch"),
        (
            "signature_algorithm",
            "ML-DSA-87",
            "pqc_kat_signature_algorithm_mismatch",
        ),
        ("implementation_hash", "b" * 64, "pqc_kat_implementation_mismatch"),
    ):
        provider = FirstPartyPqcProvider(
            implementation=implementation,
            manifest=manifest,
            kat_vectors=(vector,),
            kat_captured_at=NOW,
        )
        provider.kat_result = replace(provider.kat_result, **{field: value})

        with pytest.raises(ZeroTrustAdmissionError) as exc:
            establish_firstparty_session_from_pqc_provider(
                pqc_provider=provider,
                client_identity=claims("vpn-client"),
                server_identity=claims("vpn-server"),
                policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
                production_gate=gate,
                now=NOW,
                client_nonce=b"client-nonce".ljust(32, b"c"),
                server_nonce=b"server-nonce".ljust(32, b"s"),
            )

        assert reason in str(exc.value)


def test_pqc_known_answer_tests_pass_for_matching_firstparty_implementation() -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(implementation)

    result = run_pqc_known_answer_tests(implementation, (vector,))

    assert result.passed is True
    assert result.reasons == ()
    assert result.vector_count == 1
    assert len(result.suite_hash) == 64


def test_pqc_known_answer_tests_fail_closed_for_mismatch() -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(
        implementation,
        expected_shared_secret_hash="0" * 64,
    )

    result = run_pqc_known_answer_tests(implementation, (vector,))

    assert result.passed is False
    assert "kat-1:pqc_kat_shared_secret_mismatch" in result.reasons
    with pytest.raises(PqcProviderError, match="KAT failed"):
        FirstPartyPqcProvider(
            implementation=implementation,
            manifest=reviewed_pqc_manifest(kat_hashes=(result.suite_hash,)),
            kat_vectors=(vector,),
            kat_captured_at=NOW,
        )


def test_pqc_known_answer_tests_fail_closed_for_bad_mlkem_output_shape() -> None:
    class BadShapeImplementation(FakeFirstPartyPqcImplementation):
        def encapsulate(
            self,
            *,
            transcript: bytes,
            client_identity_hash: bytes,
            server_identity_hash: bytes,
        ) -> PqcEncapsulationResult:
            return PqcEncapsulationResult(
                shared_secret=b"s" * 32,
                ciphertext=b"short-ciphertext",
            )

    implementation = BadShapeImplementation()
    vector = pqc_kat_vector(implementation)

    result = run_pqc_known_answer_tests(implementation, (vector,))

    assert result.passed is False
    assert "kat-1:pqc_kat_ciphertext_length_invalid" not in result.reasons
    assert "kat-1:pqc_ciphertext_length_invalid" in result.reasons


def test_firstparty_pqc_provider_requires_manifested_kat_and_admits_session(
    tmp_path: Path,
) -> None:
    implementation = FakeFirstPartyPqcImplementation()
    vector = pqc_kat_vector(implementation)
    kat_result = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=NOW,
    )
    manifest = reviewed_pqc_manifest(kat_hashes=(kat_result.suite_hash,))
    provider = FirstPartyPqcProvider(
        implementation=implementation,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((manifest,))

    assert provider.kat_result.passed is True
    session = establish_firstparty_session_from_pqc_provider(
        pqc_provider=provider,
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        production_gate=PqcManifestProductionGate(manifest_store=store),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True

    with pytest.raises(PqcProviderError, match="KAT suite is not present"):
        FirstPartyPqcProvider(
            implementation=implementation,
            manifest=reviewed_pqc_manifest(kat_hashes=("f" * 64,)),
            kat_vectors=(vector,),
            kat_captured_at=NOW,
        )


def test_firstparty_mlkem_implementation_backs_manifested_pqc_provider_session(
    tmp_path: Path,
) -> None:
    keypair = mlkem_keygen_from_seeds(
        "ML-KEM-768",
        hashlib.sha3_256(b"firstparty-mlkem-provider-d").digest(),
        hashlib.sha3_256(b"firstparty-mlkem-provider-z").digest(),
    )
    transcript = b"firstparty-pqc-kat-transcript-v1"
    client_hash = b"c" * 32
    server_hash = b"s" * 32
    kat_context_id = FirstPartyMlKemImplementation.context_id(
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    implementation = FirstPartyMlKemImplementation(
        provider_id="reviewed-firstparty-pqc",
        encapsulation_key=keypair.encapsulation_key,
        decapsulation_key=keypair.decapsulation_key,
        kat_messages={
            kat_context_id: hashlib.sha3_256(
                b"firstparty-mlkem-provider-kat-message"
            ).digest(),
        },
    )
    vector = pqc_kat_vector(implementation)
    kat_result = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=NOW,
    )
    source_hash = hashlib.sha256(
        Path("src/network/firstparty_vpn/mlkem.py").read_bytes()
    ).hexdigest()
    manifest = PqcImplementationManifest(
        provider_id=implementation.provider_id,
        kem_algorithm=implementation.kem_algorithm,
        signature_algorithm=implementation.signature_algorithm,
        mode="production",
        reviewed=True,
        implementation_hash=implementation.implementation_hash,
        source_hashes=(source_hash,),
        kat_hashes=(kat_result.suite_hash,),
        review_evidence_hash=hashlib.sha256(
            b"local-firstparty-mlkem-review-evidence"
        ).hexdigest(),
        issued_at=NOW - 60,
        expires_at=NOW + 3600,
    )
    provider = FirstPartyPqcProvider(
        implementation=implementation,
        manifest=manifest,
        kat_vectors=(vector,),
        kat_captured_at=NOW,
    )
    store = DurablePqcManifestStore(tmp_path / "pqc-manifests.json")
    store.save_all((manifest,))

    assert kat_result.passed is True
    assert (
        provider.attestation.implementation_hash
        == implementation.implementation_hash
    )
    session = establish_firstparty_session_from_pqc_provider(
        pqc_provider=provider,
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        production_gate=PqcManifestProductionGate(manifest_store=store),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True


def test_firstparty_mlkem_wrong_decapsulation_key_fails_closed() -> None:
    keypair = mlkem_keygen_from_seeds(
        "ML-KEM-768",
        hashlib.sha3_256(b"firstparty-mlkem-good-d").digest(),
        hashlib.sha3_256(b"firstparty-mlkem-good-z").digest(),
    )
    wrong_keypair = mlkem_keygen_from_seeds(
        "ML-KEM-768",
        hashlib.sha3_256(b"firstparty-mlkem-wrong-d").digest(),
        hashlib.sha3_256(b"firstparty-mlkem-wrong-z").digest(),
    )
    transcript = b"firstparty-mlkem-self-check"
    client_hash = b"c" * 32
    server_hash = b"s" * 32
    kat_context_id = FirstPartyMlKemImplementation.context_id(
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    implementation = FirstPartyMlKemImplementation(
        encapsulation_key=keypair.encapsulation_key,
        decapsulation_key=wrong_keypair.decapsulation_key,
        kat_messages={
            kat_context_id: hashlib.sha3_256(
                b"firstparty-mlkem-self-check-message"
            ).digest(),
        },
    )

    with pytest.raises(PqcProviderError, match="self-check failed"):
        implementation.encapsulate(
            transcript=transcript,
            client_identity_hash=client_hash,
            server_identity_hash=server_hash,
        )


def test_wire_codec_round_trip_and_tamper_detection() -> None:
    keys = derive_session_keys(session_material())
    client_codec = WireCodec(
        FrameCrypto(encrypt_key=keys.client_tx, decrypt_key=keys.client_rx)
    )
    server_codec = WireCodec(
        FrameCrypto(encrypt_key=keys.server_tx, decrypt_key=keys.server_rx)
    )

    encoded = client_codec.encode(
        Frame(
            frame_type=FrameType.DATA,
            session_id=keys.session_id,
            sequence=1,
            payload=b"first-party encrypted packet",
        )
    )

    decoded = server_codec.decode(encoded)
    assert decoded.payload == b"first-party encrypted packet"
    assert decoded.frame_type == FrameType.DATA

    tampered = bytearray(encoded)
    tampered[-1] ^= 0x01
    with pytest.raises(FrameAuthError):
        server_codec.decode(bytes(tampered))


def test_replay_window_rejects_duplicate_sequence() -> None:
    window = ReplayWindow(size=8)

    assert window.accept(10) is True
    assert window.accept(10) is False
    assert window.accept(11) is True
    assert window.accept(1) is False


def test_session_factory_requires_zero_trust_before_codecs() -> None:
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))

    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=policy,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )

    encoded = session.client_codec.encode(
        Frame(
            frame_type=FrameType.PING,
            session_id=session.session_id,
            sequence=7,
            payload=b"ping",
        )
    )
    decoded = session.server_codec.decode(encoded)

    assert session.client_decision.allowed is True
    assert session.server_decision.allowed is True
    assert decoded.payload == b"ping"

    with pytest.raises(ZeroTrustAdmissionError) as mismatch:
        establish_firstparty_session(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
            client_identity=replace(
                claims("vpn-client"),
                pqc_kem_algorithm="ML-KEM-1024",
                pqc_signature_algorithm="ML-DSA-87",
            ),
            server_identity=claims("vpn-server"),
            policy=policy,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
            deployment_epoch="test-epoch",
        )

    assert "pqc_kem_algorithm_mismatch" in str(mismatch.value)
    assert "pqc_signature_algorithm_mismatch" in str(mismatch.value)


def test_session_factory_accepts_signed_identities_and_denies_revoked_token() -> None:
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    revocations = RevocationList()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)

    session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        revocations=revocations,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    encoded = session.client_codec.encode(
        Frame(
            frame_type=FrameType.PING,
            session_id=session.session_id,
            sequence=1,
            payload=b"signed",
        )
    )
    assert session.server_codec.decode(encoded).payload == b"signed"

    revocations.revoke_identity(client_token)
    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_signed_identities(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            revocations=revocations,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "identity_revoked" in str(exc.value)


def test_session_factory_rejects_signed_identity_algorithm_downgrade() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(
        IdentityIssueRequest(
            spiffe_id="spiffe://x0tta6bl4.mesh/workload/vpn-client/node-1",
            did="did:mesh:pqc:vpn-client:key-1",
            workload="vpn-client",
            tenant="team-a",
            device_id="vpn-client-device-1",
            pqc_kem_algorithm="ML-KEM-1024",
            pqc_signature_algorithm="ML-DSA-87",
        ),
        now=NOW,
    )
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)

    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_signed_identities(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "pqc_kem_algorithm_mismatch" in str(exc.value)
    assert "pqc_signature_algorithm_mismatch" in str(exc.value)


def test_firstparty_handshake_round_trips_hello_accept_and_session_codecs() -> None:
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)

    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"client-handshake-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    parsed_hello = FirstPartyHandshakeHello.from_frame(hello.to_frame(sequence=7))
    store = FirstPartyHandshakeSecretStore()
    store.add(material)

    server_result = accept_firstparty_handshake(
        hello=parsed_hello,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
        accepted_at=NOW,
    )
    parsed_accept = FirstPartyHandshakeAccept.from_frame(
        server_result.accept.to_frame(sequence=8)
    )
    client_session = complete_firstparty_handshake(
        hello=parsed_hello,
        accept=parsed_accept,
        pqc_material=material,
        identity_authority=verifier,
        policy=policy,
    )
    protected = client_session.client_codec.encode(
        Frame(
            frame_type=FrameType.PING,
            session_id=client_session.session_id,
            sequence=1,
            payload=b"handshake",
        )
    )

    assert server_result.session.session_id == client_session.session_id
    assert parsed_hello.hello_hash() == hello.hello_hash()
    assert parsed_accept.hello_hash == hello.hello_hash()
    assert parsed_accept.session_id == client_session.session_id
    assert server_result.session.server_codec.decode(protected).payload == b"handshake"


def test_firstparty_handshake_production_gate_rejects_unreviewed_pqc_material() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    dev_provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=dev_provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"production-gate-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    strict_gate = PqcProductionGate(require_production=True)

    with pytest.raises(FirstPartyHandshakeError) as server_exc:
        accept_firstparty_handshake(
            hello=hello,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=store.resolve,
            server_nonce=b"production-gate-server".ljust(32, b"s"),
            accepted_at=NOW,
            production_gate=strict_gate,
        )
    assert "PQC production gate failed" in str(server_exc.value)
    assert "pqc_provider_not_production" in str(server_exc.value)
    assert "pqc_provider_not_reviewed" in str(server_exc.value)

    server_result = accept_firstparty_handshake(
        hello=hello,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"production-gate-server".ljust(32, b"s"),
        accepted_at=NOW,
    )
    with pytest.raises(FirstPartyHandshakeError) as client_exc:
        complete_firstparty_handshake(
            hello=hello,
            accept=server_result.accept,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW,
            production_gate=strict_gate,
        )
    assert "pqc_provider_not_production" in str(client_exc.value)

    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"production-gate-server".ljust(32, b"s"),
        accepted_at_provider=lambda _hello: NOW,
        production_gate=strict_gate,
    )
    with pytest.raises(FirstPartyHandshakeError):
        registry.admit(hello)
    assert registry.sessions == ()

    production_provider = FakeProductionPqcProvider()
    production_hello, production_material = create_firstparty_handshake_hello(
        pqc_provider=production_provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"reviewed-production-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    production_store = FirstPartyHandshakeSecretStore()
    production_store.add(production_material)
    trusted_gate = PqcProductionGate(
        require_production=True,
        trusted_provider_ids=frozenset({"reviewed-firstparty-pqc"}),
        trusted_implementation_hashes=frozenset({"pqc-implementation-hash-1"}),
    )

    production_result = accept_firstparty_handshake(
        hello=production_hello,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=production_store.resolve,
        server_nonce=b"reviewed-production-server".ljust(32, b"s"),
        accepted_at=NOW,
        production_gate=trusted_gate,
    )
    production_session = complete_firstparty_handshake(
        hello=production_hello,
        accept=production_result.accept,
        pqc_material=production_material,
        identity_authority=authority,
        policy=policy,
        completed_at=NOW,
        production_gate=trusted_gate,
    )

    assert production_result.session.session_id == production_session.session_id


def test_firstparty_handshake_fails_closed_for_mismatched_material_and_accept() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    wrong_server_token = authority.issue(
        issue_request("vpn-server", attributes={"node": "other"}),
        now=NOW,
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"client-handshake-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )

    with pytest.raises(FirstPartyHandshakeError):
        accept_firstparty_handshake(
            hello=hello,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=FirstPartyHandshakeSecretStore().resolve,
            server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )
    with pytest.raises(FirstPartyHandshakeError):
        accept_firstparty_handshake(
            hello=hello,
            server_identity=wrong_server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=lambda _hello: material,
            server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )

    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    server_result = accept_firstparty_handshake(
        hello=hello,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
        accepted_at=NOW,
    )
    tampered_accept = replace(
        server_result.accept,
        hello_hash="0" * 64,
    )
    with pytest.raises(FirstPartyHandshakeError):
        complete_firstparty_handshake(
            hello=hello,
            accept=tampered_accept,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )


def test_firstparty_handshake_and_admission_reject_stale_or_future_hello() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"client-handshake-freshness".ljust(32, b"c"),
        issued_at=NOW,
    )
    stale_hello = replace(hello, issued_at=NOW - 301)
    future_hello = replace(hello, issued_at=NOW + 1)
    store = FirstPartyHandshakeSecretStore()
    store.add(material)

    with pytest.raises(FirstPartyHandshakeError, match="handshake HELLO is stale"):
        accept_firstparty_handshake(
            hello=stale_hello,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=store.resolve,
            server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )
    with pytest.raises(
        FirstPartyHandshakeError,
        match="handshake HELLO issued in the future",
    ):
        accept_firstparty_handshake(
            hello=future_hello,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=store.resolve,
            server_nonce=b"server-handshake-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )

    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"registry-server-nonce".ljust(32, b"s"),
        accepted_at_provider=lambda hello: max(NOW, hello.issued_at),
        max_hello_age_seconds=120,
    )
    with pytest.raises(FirstPartyHandshakeError, match="handshake HELLO is stale"):
        registry.admit(replace(hello, issued_at=NOW - 121))
    assert registry.sessions == ()
    assert registry.admitted_session_ids == ()


def test_firstparty_handshake_rejects_stale_or_future_accept() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"client-accept-freshness".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    server_result = accept_firstparty_handshake(
        hello=hello,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"server-accept-freshness".ljust(32, b"s"),
        accepted_at=NOW,
    )

    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT predates HELLO"):
        complete_firstparty_handshake(
            hello=hello,
            accept=replace(server_result.accept, accepted_at=NOW - 1),
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )
    with pytest.raises(
        FirstPartyHandshakeError,
        match="ACCEPT is stale for HELLO",
    ):
        complete_firstparty_handshake(
            hello=hello,
            accept=replace(server_result.accept, accepted_at=NOW + 301),
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )
    with pytest.raises(
        FirstPartyHandshakeError,
        match="ACCEPT accepted in the future",
    ):
        complete_firstparty_handshake(
            hello=hello,
            accept=server_result.accept,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW - 1,
        )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT is stale"):
        complete_firstparty_handshake(
            hello=hello,
            accept=server_result.accept,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW + 301,
        )


def test_firstparty_session_admission_registry_admits_and_tracks_sessions() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"registry-client-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"registry-server-nonce".ljust(32, b"s"),
        accepted_at_provider=lambda _hello: NOW,
    )

    result = registry.admit(hello)
    client_session = complete_firstparty_handshake(
        hello=hello,
        accept=result.accept,
        pqc_material=material,
        identity_authority=authority,
        policy=policy,
    )

    assert result.session.session_id == client_session.session_id
    assert registry.sessions == (result.session,)
    assert registry.admitted_session_ids == (result.session.session_id,)
    assert registry.session_for(result.session.session_id) is result.session

    with pytest.raises(
        FirstPartySessionAdmissionError,
        match="handshake HELLO replay refused",
    ):
        registry.admit(hello)
    with pytest.raises(FirstPartySessionAdmissionError, match="session is not admitted"):
        registry.session_for(result.session.session_id + 1)

    registry.forget(result.session)
    assert registry.sessions == ()


def test_firstparty_session_admission_registry_accepts_alternate_server_identity() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    old_server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    new_server_token = authority.issue(issue_request("vpn-server"), now=NOW + 1)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=old_server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"alternate-server-identity".ljust(32, b"c"),
        issued_at=NOW + 2,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)

    fail_closed = FirstPartySessionAdmissionRegistry(
        server_identity=new_server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"new-server-only".ljust(32, b"s"),
        accepted_at_provider=lambda _hello: NOW + 2,
    )
    with pytest.raises(FirstPartyHandshakeError, match="server identity does not match HELLO"):
        fail_closed.admit(hello)

    registry = FirstPartySessionAdmissionRegistry(
        server_identity=new_server_token,
        alternate_server_identities=(old_server_token,),
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"alternate-server-ok".ljust(32, b"s"),
        accepted_at_provider=lambda _hello: NOW + 2,
    )

    result = registry.admit(hello)
    client_session = complete_firstparty_handshake(
        hello=hello,
        accept=result.accept,
        pqc_material=material,
        identity_authority=authority,
        policy=policy,
        completed_at=NOW + 2,
    )

    assert result.accept.server_identity.serial == old_server_token.serial
    assert result.session.session_id == client_session.session_id
    assert registry.sessions == (result.session,)


def test_firstparty_session_admission_registry_enforces_client_allowlist() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"allowlist-registry-client-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)

    empty_allowlist_registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"allowlist-empty-server-nonce".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
        enforce_client_identity_allowlist=True,
    )
    with pytest.raises(
        FirstPartySessionAdmissionError,
        match="client identity is not in server allowlist",
    ):
        empty_allowlist_registry.admit(hello)
    assert empty_allowlist_registry.sessions == ()

    allowed_registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"allowlist-ok-server-nonce".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
        client_identity_hash_allowlist=frozenset(
            {identity_binding_hash(client_token.claims).hex()}
        ),
        enforce_client_identity_allowlist=True,
    )

    result = allowed_registry.admit(hello)

    assert allowed_registry.sessions == (result.session,)
    assert allowed_registry.admitted_session_ids == (result.session.session_id,)


def test_firstparty_session_admission_registry_fails_closed_for_revoked_identity() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"revoked-registry-client-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    revocations = RevocationList()
    revocations.revoke_identity(client_token)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"revoked-registry-server-nonce".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
        revocations=revocations,
    )

    with pytest.raises(ZeroTrustAdmissionError):
        registry.admit(hello)
    assert registry.sessions == ()
    assert registry.admitted_session_ids == ()


@pytest.mark.asyncio
async def test_tcp_admission_server_accepts_hello_then_serves_protected_data() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"tcp-admission-client-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"tcp-admission-server-nonce".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server, protocol, addr = await open_tcp_admission_server(
        registry=registry,
        on_data=lambda payload, _peer: b"admitted:" + payload,
    )
    result = None
    try:
        result = await open_tcp_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=policy,
            completed_at_provider=lambda accept: accept.accepted_at,
        )

        assert result.session.session_id == result.accept.session_id
        assert registry.admitted_session_ids == (result.session.session_id,)
        assert protocol.admitted_session_ids == (result.session.session_id,)

        result.client.send_data(b"packet")
        await result.client.drain()
        response = await result.client.recv(timeout=1.0)
        assert response.frame_type == FrameType.DATA
        assert response.payload == b"admitted:packet"

        await protocol.send_data(b"server-push", session=result.session)
        pushed = await result.client.recv(timeout=1.0)
        assert pushed.frame_type == FrameType.DATA
        assert pushed.payload == b"server-push"
    finally:
        if result is not None:
            result.client.close()
            await result.client.wait_closed()
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_tcp_admission_server_drops_handler_rejections_without_task_error() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"tcp-admission-handler-drop".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"tcp-handler-drop-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )

    def reject_payload(_payload: bytes, _peer: tuple[str, int]) -> bytes:
        raise ValueError("packet must be IPv4 or IPv6")

    server, protocol, addr = await open_tcp_admission_server(
        registry=registry,
        on_data=reject_payload,
    )
    result = None
    try:
        result = await open_tcp_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=policy,
            completed_at_provider=lambda accept: accept.accepted_at,
        )
        result.client.send_data(b"not-an-ip-packet")
        await result.client.drain()
        with pytest.raises((TimeoutError, asyncio.IncompleteReadError)):
            await result.client.recv(timeout=0.5)

        result.client.close()
        await result.client.wait_closed()
        await protocol.wait_client_tasks()
        assert protocol.stats.session_drops == 1
    finally:
        if result is not None and not result.client.writer.is_closing():
            result.client.close()
            await result.client.wait_closed()
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_tcp_admission_server_rejects_replayed_hello_without_second_accept() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"tcp-admission-replay-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"tcp-admission-replay-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server, protocol, addr = await open_tcp_admission_server(registry=registry)
    first = None
    try:
        first = await open_tcp_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=policy,
        )
        with pytest.raises((TimeoutError, asyncio.IncompleteReadError)):
            await open_tcp_admission_client(
                hello=hello,
                pqc_material=material,
                remote_addr=addr,
                identity_authority=authority,
                policy=policy,
                timeout=0.5,
            )
        await asyncio.sleep(0.05)
        assert registry.admitted_session_ids == (first.session.session_id,)
        assert protocol.stats.session_drops >= 1
    finally:
        if first is not None:
            first.client.close()
            await first.client.wait_closed()
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_udp_admission_server_accepts_hello_then_serves_protected_data() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"udp-admission-client-nonce".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"udp-admission-server-nonce".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server_transport, protocol, addr = await open_udp_admission_server(
        registry=registry,
        on_data=lambda payload, _peer: b"udp-admitted:" + payload,
    )
    client_transport = None
    client = None
    try:
        client_transport, client = await open_udp_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=policy,
            completed_at_provider=lambda accept: accept.accepted_at,
        )

        assert client.session is not None
        assert client.accept is not None
        assert client.session.session_id == client.accept.session_id
        assert registry.admitted_session_ids == (client.session.session_id,)
        assert protocol.admitted_session_ids == (client.session.session_id,)

        client.send_data(b"packet")
        response = await client.recv(timeout=1.0)
        assert response.frame_type == FrameType.DATA
        assert response.payload == b"udp-admitted:packet"

        protocol.send_data(b"udp-server-push", session=client.session)
        pushed = await client.recv(timeout=1.0)
        assert pushed.frame_type == FrameType.DATA
        assert pushed.payload == b"udp-server-push"
    finally:
        if client_transport is not None:
            client_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_udp_admission_server_rejects_replayed_hello_without_second_accept() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"udp-admission-replay-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"udp-admission-replay-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server_transport, protocol, addr = await open_udp_admission_server(registry=registry)
    first_transport = None
    second_transport = None
    first = None
    try:
        first_transport, first = await open_udp_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=policy,
        )
        with pytest.raises(TimeoutError):
            second_transport, _second = await open_udp_admission_client(
                hello=hello,
                pqc_material=material,
                remote_addr=addr,
                identity_authority=authority,
                policy=policy,
                timeout=0.2,
            )
        await asyncio.sleep(0.05)
        assert first.session is not None
        assert registry.admitted_session_ids == (first.session.session_id,)
        assert protocol.route_stats.session_drops >= 1
    finally:
        if first_transport is not None:
            first_transport.close()
        if second_transport is not None:
            second_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_camouflage_admission_server_accepts_hello_then_serves_protected_data() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"camouflage-admission-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"camouflage-admission-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    request = encode_camouflage_admission_request(
        hello=hello,
        profile=profile,
        policy=camouflage_policy,
    )
    server, protocol, addr = await open_camouflage_admission_server(
        registry=registry,
        profile=profile,
        policy=camouflage_policy,
        on_data=lambda payload, _peer: b"camouflage-admitted:" + payload,
        on_session_ping=lambda payload, _peer, _session: b"camouflage-ping:" + payload,
    )
    result = None
    try:
        result = await open_camouflage_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=zero_trust_policy,
            profile=profile,
            camouflage_policy=camouflage_policy,
            completed_at_provider=lambda accept: accept.accepted_at,
            timeout=0.5,
        )

        assert request.startswith(b"POST /assets/check HTTP/1.1\r\n")
        assert b"Host: updates.invalid\r\n" in request
        assert b"x0vpn" not in request.lower()
        assert b"vpn" not in request.lower()
        assert result.session.session_id == result.accept.session_id
        assert registry.admitted_session_ids == (result.session.session_id,)
        assert protocol.admitted_session_ids == (result.session.session_id,)

        result.client.send_data(b"packet")
        await result.client.drain()
        response = await result.client.recv(timeout=1.0)
        assert response.frame_type == FrameType.DATA
        assert response.payload == b"camouflage-admitted:packet"

        result.client.send_ping(b"config-sync")
        await result.client.drain()
        pong = await result.client.recv(timeout=1.0)
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"camouflage-ping:config-sync"

        await protocol.send_data(b"camouflage-server-push", session=result.session)
        pushed = await result.client.recv(timeout=1.0)
        assert pushed.frame_type == FrameType.DATA
        assert pushed.payload == b"camouflage-server-push"
    finally:
        if result is not None:
            result.client.close()
            await result.client.wait_closed()
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_camouflage_admission_server_rejects_replayed_hello_without_second_accept() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"camouflage-admission-replay".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"camouflage-admission-replay-s".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(profile_id="restricted-work-wifi")
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    server, protocol, addr = await open_camouflage_admission_server(
        registry=registry,
        profile=profile,
        policy=camouflage_policy,
    )
    first = None
    try:
        first = await open_camouflage_admission_client(
            hello=hello,
            pqc_material=material,
            remote_addr=addr,
            identity_authority=authority,
            policy=zero_trust_policy,
            profile=profile,
            camouflage_policy=camouflage_policy,
            timeout=0.5,
        )
        with pytest.raises((CamouflageError, ConnectionResetError, TimeoutError)):
            await open_camouflage_admission_client(
                hello=hello,
                pqc_material=material,
                remote_addr=addr,
                identity_authority=authority,
                policy=zero_trust_policy,
                profile=profile,
                camouflage_policy=camouflage_policy,
                timeout=0.5,
            )
        await asyncio.sleep(0.05)
        assert registry.admitted_session_ids == (first.session.session_id,)
        assert protocol.stats.session_drops >= 1
    finally:
        if first is not None:
            first.client.close()
            await first.client.wait_closed()
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()


def test_firstparty_rekey_round_trips_inside_protected_session_and_rotates_keys() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    previous_client = FirstPartyEndpoint(session=previous_session, role="client")
    previous_server = FirstPartyEndpoint(session=previous_session, role="server")
    provider = LocalTestPqcProvider(issued_at=NOW - 60)

    request, material = create_firstparty_rekey_request(
        pqc_provider=provider,
        previous_session=previous_session,
        client_identity=client_token,
        server_identity=server_token,
        base_deployment_epoch="test-epoch",
        generation=2,
        reason="scheduled-rotation",
        client_nonce=b"rekey-client-nonce".ljust(32, b"c"),
        requested_at=NOW,
    )
    protected_request = previous_client.next_frame(
        FrameType.DATA,
        request.to_payload(),
    )
    parsed_request = FirstPartyRekeyRequest.from_frame(
        previous_server.open_frame(protected_request)
    )
    store = FirstPartyRekeySecretStore()
    store.add(material)

    server_result = accept_firstparty_rekey(
        request=parsed_request,
        previous_session=previous_session,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"rekey-server-nonce".ljust(32, b"s"),
        accepted_at=NOW,
    )
    protected_accept = previous_server.next_frame(
        FrameType.DATA,
        server_result.accept.to_payload(),
    )
    parsed_accept = FirstPartyRekeyAccept.from_frame(
        previous_client.open_frame(protected_accept)
    )
    client_next_session = complete_firstparty_rekey(
        request=parsed_request,
        accept=parsed_accept,
        previous_session=previous_session,
        pqc_material=material,
        identity_authority=authority,
        policy=policy,
    )
    old_protected = previous_client.next_frame(FrameType.PING, b"old-session")
    previous_client.rotate_session(client_next_session)
    previous_server.rotate_session(server_result.session)
    new_protected = previous_client.next_frame(FrameType.PING, b"next-session")

    assert server_result.session.session_id == client_next_session.session_id
    assert server_result.session.session_id != previous_session.session_id
    assert parsed_request.request_hash() == request.request_hash()
    assert parsed_accept.request_hash == request.request_hash()
    assert previous_server.open_frame(new_protected).payload == b"next-session"
    with pytest.raises(RuntimeDrop):
        previous_server.open_frame(old_protected)


def test_firstparty_rekey_rejects_stale_or_future_accept_freshness() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    request, material = create_firstparty_rekey_request(
        pqc_provider=LocalTestPqcProvider(issued_at=NOW - 60),
        previous_session=previous_session,
        client_identity=client_token,
        server_identity=server_token,
        base_deployment_epoch="test-epoch",
        generation=2,
        reason="scheduled-rotation",
        client_nonce=b"rekey-client-nonce".ljust(32, b"c"),
        requested_at=NOW,
    )
    store = FirstPartyRekeySecretStore()
    store.add(material)
    server_result = accept_firstparty_rekey(
        request=request,
        previous_session=previous_session,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"rekey-server-nonce".ljust(32, b"s"),
        accepted_at=NOW,
    )
    stale_accept = replace(
        server_result.accept,
        accept=replace(server_result.accept.accept, accepted_at=NOW - 1),
    )

    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT predates HELLO"):
        complete_firstparty_rekey(
            request=request,
            accept=stale_accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT accepted in the future"):
        complete_firstparty_rekey(
            request=request,
            accept=server_result.accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW - 1,
        )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT is stale"):
        complete_firstparty_rekey(
            request=request,
            accept=server_result.accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW + 301,
        )


def test_firstparty_rekey_fails_closed_for_missing_material_previous_and_accept() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    wrong_previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"wrong-previous-pqc-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    request, material = create_firstparty_rekey_request(
        pqc_provider=LocalTestPqcProvider(issued_at=NOW - 60),
        previous_session=previous_session,
        client_identity=client_token,
        server_identity=server_token,
        base_deployment_epoch="test-epoch",
        generation=2,
        reason="scheduled-rotation",
        client_nonce=b"rekey-client-nonce".ljust(32, b"c"),
        requested_at=NOW,
    )

    with pytest.raises(FirstPartyRekeyError):
        accept_firstparty_rekey(
            request=request,
            previous_session=previous_session,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=FirstPartyRekeySecretStore().resolve,
            server_nonce=b"rekey-server-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )
    with pytest.raises(FirstPartyRekeyError):
        accept_firstparty_rekey(
            request=request,
            previous_session=wrong_previous_session,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=lambda _request: material,
            server_nonce=b"rekey-server-nonce".ljust(32, b"s"),
            accepted_at=NOW,
        )

    store = FirstPartyRekeySecretStore()
    store.add(material)
    server_result = accept_firstparty_rekey(
        request=request,
        previous_session=previous_session,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        shared_secret_resolver=store.resolve,
        server_nonce=b"rekey-server-nonce".ljust(32, b"s"),
        accepted_at=NOW,
    )
    tampered_accept = replace(server_result.accept, request_hash="0" * 64)
    with pytest.raises(FirstPartyRekeyError):
        complete_firstparty_rekey(
            request=request,
            accept=tampered_accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )
    stale_accept = replace(
        server_result.accept,
        accept=replace(server_result.accept.accept, accepted_at=NOW - 1),
    )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT predates HELLO"):
        complete_firstparty_rekey(
            request=request,
            accept=stale_accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
        )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT accepted in the future"):
        complete_firstparty_rekey(
            request=request,
            accept=server_result.accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW - 1,
        )
    with pytest.raises(FirstPartyHandshakeError, match="ACCEPT is stale"):
        complete_firstparty_rekey(
            request=request,
            accept=server_result.accept,
            previous_session=previous_session,
            pqc_material=material,
            identity_authority=authority,
            policy=policy,
            completed_at=NOW + 301,
        )


def test_firstparty_rekey_policy_requires_rollback_and_safe_evidence() -> None:
    policy = FirstPartyRekeyCadencePolicy(
        max_session_age_seconds=300,
        max_tx_frames=4,
        max_rx_bytes=1024,
        min_seconds_between_rekeys=60,
    )
    telemetry = FirstPartyRekeyTelemetry(
        session_started_at=NOW - 600,
        last_rekey_at=NOW - 120,
        now=NOW,
        generation=3,
        tx_frames=4,
        rx_frames=2,
        tx_bytes=512,
        rx_bytes=2048,
    )

    missing = evaluate_firstparty_rekey_policy(
        policy,
        telemetry,
        requested_reason="scheduled-rotation",
    )

    assert missing.required is True
    assert missing.allowed is False
    assert "rekey_rollback_evidence_missing" in missing.block_reasons

    previous_transcript_hash = hashlib.sha256(b"previous-transcript").hexdigest()
    next_transcript_hash = hashlib.sha256(b"next-transcript").hexdigest()
    rollback = FirstPartyRekeyRollbackEvidence.from_session_bindings(
        rollback_id="rollback-ticket-42",
        previous_session_id=1001,
        previous_transcript_hash=previous_transcript_hash,
        next_session_id=2002,
        next_transcript_hash=next_transcript_hash,
        rollback_plan_id="rollback-plan-prod",
        generated_at=NOW - 30,
    )
    decision = evaluate_firstparty_rekey_policy(
        policy,
        telemetry,
        requested_reason="scheduled-rotation",
        rollback_evidence=rollback,
    )

    assert isinstance(decision, FirstPartyRekeyPolicyDecision)
    assert decision.required is True
    assert decision.allowed is True
    assert decision.trigger_reasons == (
        "session_age_exceeded",
        "tx_frames_exceeded",
        "rx_bytes_exceeded",
    )
    assert decision.block_reasons == ()
    assert decision.rollback_evidence_hash == rollback.evidence_hash()
    assert decision.rollback_plan_hash == rollback.rollback_plan_hash
    assert len(decision.evidence_hash) == 64
    assert len(decision.rollback_evidence_hash or "") == 64
    assert len(decision.rollback_plan_hash or "") == 64

    payload = {
        "decision": decision.to_json_dict(),
        "rollback": rollback.to_json_dict(),
    }
    assert_privacy_safe(payload)
    encoded = json.dumps(payload, sort_keys=True)
    assert "rollback-ticket-42" not in encoded
    assert "rollback-plan-prod" not in encoded
    assert previous_transcript_hash not in encoded
    assert next_transcript_hash not in encoded


def test_firstparty_rekey_policy_fails_closed_for_bad_reason_interval_and_rollback() -> None:
    policy = FirstPartyRekeyCadencePolicy(
        max_tx_bytes=10,
        min_seconds_between_rekeys=120,
        allowed_request_reasons=frozenset({"scheduled-rotation", "manual-operator"}),
        manual_request_reasons=frozenset({"manual-operator"}),
    )
    telemetry = FirstPartyRekeyTelemetry(
        session_started_at=NOW - 300,
        last_rekey_at=NOW - 30,
        now=NOW,
        generation=2,
        tx_bytes=10,
    )
    rollback = FirstPartyRekeyRollbackEvidence.from_session_bindings(
        rollback_id="rollback-ticket-43",
        previous_session_id=3003,
        previous_transcript_hash=hashlib.sha256(b"previous").hexdigest(),
        next_session_id=4004,
        next_transcript_hash=hashlib.sha256(b"next").hexdigest(),
        rollback_plan_id="rollback-plan-stale",
        generated_at=NOW - 400,
    )

    decision = evaluate_firstparty_rekey_policy(
        policy,
        telemetry,
        requested_reason="debug-rotation",
        rollback_evidence=rollback,
    )

    assert decision.required is True
    assert decision.allowed is False
    assert decision.trigger_reasons == ("tx_bytes_exceeded",)
    assert "rekey_reason_not_allowed" in decision.block_reasons
    assert "rekey_min_interval_not_elapsed" in decision.block_reasons
    assert "rekey_rollback_evidence_stale" in decision.block_reasons
    assert_privacy_safe(decision.to_json_dict())

    idle_decision = evaluate_firstparty_rekey_policy(
        policy,
        FirstPartyRekeyTelemetry(
            session_started_at=NOW - 10,
            last_rekey_at=None,
            now=NOW,
            generation=2,
            tx_bytes=1,
        ),
        requested_reason="scheduled-rotation",
    )
    assert idle_decision.required is False
    assert idle_decision.allowed is False
    assert idle_decision.block_reasons == ("rekey_not_required",)


@pytest.mark.asyncio
async def test_firstparty_transport_rekey_rotates_live_udp_endpoint() -> None:
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    server_transport, server_protocol, addr = await open_udp_server(
        session=previous_session,
        rekey_processor=FirstPartyRekeyServerProcessor(
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            shared_secret_resolver=lambda request: create_firstparty_handshake_hello(
                pqc_provider=provider,
                client_identity=request.hello.client_identity,
                server_identity=server_token,
                deployment_epoch=request.hello.deployment_epoch,
                client_nonce=request.hello.client_nonce,
                issued_at=request.hello.issued_at,
            )[1],
            server_nonce_provider=lambda _request: b"live-rekey-server-nonce".ljust(32, b"s"),
            accepted_at_provider=lambda _request: NOW,
        ),
    )
    client_transport, client = await open_udp_client(
        session=previous_session,
        remote_addr=addr,
    )
    try:
        result = await perform_firstparty_transport_rekey(
            transport=client,
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            base_deployment_epoch="test-epoch",
            generation=2,
            reason="scheduled-rotation",
            client_nonce=b"live-rekey-client-nonce".ljust(32, b"c"),
            requested_at=NOW,
            timeout=1.0,
            completed_at_provider=lambda accept: accept.accept.accepted_at,
        )
        client.send_ping(b"after-rekey")
        pong = await client.recv(timeout=1.0)

        assert result.next_session.session_id != previous_session.session_id
        assert client.endpoint.session.session_id == result.next_session.session_id
        assert server_protocol.endpoint.session.session_id == result.next_session.session_id
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"after-rekey"
    finally:
        client_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_firstparty_transport_rekey_rotates_live_tcp_endpoint() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    server, server_protocol, addr = await open_tcp_server(
        session=previous_session,
        rekey_processor=FirstPartyRekeyServerProcessor(
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=lambda request: create_firstparty_handshake_hello(
                pqc_provider=provider,
                client_identity=request.hello.client_identity,
                server_identity=server_token,
                deployment_epoch=request.hello.deployment_epoch,
                client_nonce=request.hello.client_nonce,
                issued_at=request.hello.issued_at,
            )[1],
            server_nonce_provider=lambda _request: b"live-rekey-server-nonce".ljust(32, b"s"),
            accepted_at_provider=lambda _request: NOW,
        ),
    )
    client = await open_tcp_client(session=previous_session, remote_addr=addr)
    try:
        result = await perform_firstparty_transport_rekey(
            transport=client,
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            base_deployment_epoch="test-epoch",
            generation=2,
            reason="scheduled-rotation",
            client_nonce=b"live-rekey-client-nonce".ljust(32, b"c"),
            requested_at=NOW,
            timeout=1.0,
        )
        client.send_ping(b"after-rekey")
        await client.drain()
        pong = await client.recv(timeout=1.0)

        assert result.next_session.session_id != previous_session.session_id
        assert client.endpoint.session.session_id == result.next_session.session_id
        assert server_protocol.session.session_id == result.next_session.session_id
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"after-rekey"
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_firstparty_transport_rekey_rotates_unified_camouflage_client() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    previous_session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    service = await open_firstparty_dataplane_service(
        session=previous_session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        on_data=lambda payload, _addr: b"after-rekey-echo:" + payload,
        rekey_processor=FirstPartyRekeyServerProcessor(
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            shared_secret_resolver=lambda request: create_firstparty_handshake_hello(
                pqc_provider=provider,
                client_identity=request.hello.client_identity,
                server_identity=server_token,
                deployment_epoch=request.hello.deployment_epoch,
                client_nonce=request.hello.client_nonce,
                issued_at=request.hello.issued_at,
            )[1],
            server_nonce_provider=lambda _request: b"live-rekey-server-nonce".ljust(32, b"s"),
            accepted_at_provider=lambda _request: NOW,
        ),
    )
    client = None
    try:
        assert service.camouflage_addr is not None
        client = await open_firstparty_dataplane_client(
            session=previous_session,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="live-rekey-camouflage",
                    path_label="restricted-camouflage",
                    transport="camouflage",
                    remote_ref="live-rekey-camouflage-ref",
                    remote_addr=service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
        )

        result = await perform_firstparty_transport_rekey(
            transport=client,
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=authority,
            policy=policy,
            base_deployment_epoch="test-epoch",
            generation=2,
            reason="scheduled-rotation",
            client_nonce=b"live-rekey-client-nonce".ljust(32, b"c"),
            requested_at=NOW,
            timeout=1.0,
        )
        client.send_data(b"packet")
        await client.drain()
        response = await client.recv(timeout=1.0)

        assert result.next_session.session_id != previous_session.session_id
        assert client.transport == "camouflage"
        assert client.endpoint.session.session_id == result.next_session.session_id
        assert response.frame_type == FrameType.DATA
        assert response.payload == b"after-rekey-echo:packet"
    finally:
        if client is not None:
            await client.close()
        await service.close()


def test_session_factory_uses_policy_snapshot_posture_gate() -> None:
    authority = identity_authority()
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    snapshot = PolicySnapshot(
        policy_epoch="epoch-1",
        issued_at=NOW,
        posture_policy=DevicePosturePolicy(max_posture_age_seconds=300),
    )
    client_token = authority.issue(
        issue_request(
            "vpn-client",
            attributes={
                "posture_status": "healthy",
                "posture_checked_at": str(NOW - 60),
            },
        ),
        now=NOW,
    )
    server_token = authority.issue(
        issue_request(
            "vpn-server",
            attributes={
                "posture_status": "healthy",
                "posture_checked_at": str(NOW - 60),
            },
        ),
        now=NOW,
    )

    session = establish_firstparty_session_from_policy_snapshot(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=authority,
        policy_snapshot=snapshot,
        policy=policy,
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    assert session.client_decision.allowed is True
    stale_client = authority.issue(
        issue_request(
            "vpn-client",
            attributes={
                "posture_status": "healthy",
                "posture_checked_at": str(NOW - 7200),
            },
        ),
        now=NOW,
    )
    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session_from_policy_snapshot(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
            client_identity=stale_client,
            server_identity=server_token,
            identity_authority=authority,
            policy_snapshot=snapshot,
            policy=policy,
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "device_posture_stale" in str(exc.value)


def test_session_factory_denies_untrusted_server_identity() -> None:
    bad_server = IdentityClaims(
        spiffe_id="spiffe://evil.mesh/workload/vpn-server/node-2",
        did="did:mesh:pqc:node-2:key-1",
        workload="vpn-server",
        tenant="team-a",
        device_id="device-2",
        pqc_kem_algorithm="ML-KEM-768",
        pqc_signature_algorithm="ML-DSA-65",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
        policy_epoch="epoch-1",
    )

    with pytest.raises(ZeroTrustAdmissionError) as exc:
        establish_firstparty_session(
            kem_algorithm="ML-KEM-768",
            signature_algorithm="ML-DSA-65",
            pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
            client_identity=claims("vpn-client"),
            server_identity=bad_server,
            policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
            now=NOW,
            client_nonce=b"client-nonce".ljust(32, b"c"),
            server_nonce=b"server-nonce".ljust(32, b"s"),
        )

    assert "spiffe_trust_domain_mismatch" in str(exc.value)


def test_endpoint_rejects_replayed_dataplane_frame() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client = FirstPartyEndpoint(session=session, role="client")
    server = FirstPartyEndpoint(session=session, role="server")
    datagram = client.next_frame(FrameType.DATA, b"packet")

    assert server.open_frame(datagram).payload == b"packet"
    with pytest.raises(RuntimeDrop):
        server.open_frame(datagram)
    assert server.stats.replay_drops == 1


@pytest.mark.asyncio
async def test_udp_runtime_round_trips_data_and_ping() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    server_transport, server_protocol, addr = await open_udp_server(
        session=session,
        on_data=lambda payload, _addr: b"echo:" + payload,
    )
    client_transport, client = await open_udp_client(session=session, remote_addr=addr)
    try:
        client.send_data(b"payload-1")
        response = await client.recv()

        assert response.frame_type == FrameType.DATA
        assert response.payload == b"echo:payload-1"
        assert client.endpoint.stats.rx_data_frames == 1
        assert server_protocol.endpoint.stats.rx_data_frames == 1

        client.send_ping(b"health")
        pong = await client.recv()
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"health"
    finally:
        client_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_udp_multi_session_runtime_routes_two_users_on_one_listener() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce-a".ljust(32, b"c"),
        server_nonce=b"server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce-b".ljust(32, b"c"),
        server_nonce=b"server-nonce-b".ljust(32, b"s"),
    )
    assert session_a.session_id != session_b.session_id
    server_transport, server_protocol, addr = await open_udp_multi_session_server(
        sessions=(session_a, session_b),
        on_data=lambda payload, _addr: b"multi-udp:" + payload,
    )
    client_a_transport, client_a = await open_udp_client(
        session=session_a,
        remote_addr=addr,
    )
    client_b_transport, client_b = await open_udp_client(
        session=session_b,
        remote_addr=addr,
    )
    try:
        client_a.send_data(b"user-a")
        client_b.send_data(b"user-b")
        response_a = await client_a.recv(timeout=1.0)
        response_b = await client_b.recv(timeout=1.0)

        assert response_a.frame_type == FrameType.DATA
        assert response_a.payload == b"multi-udp:user-a"
        assert response_b.frame_type == FrameType.DATA
        assert response_b.payload == b"multi-udp:user-b"
        assert server_protocol.admitted_session_ids == tuple(
            sorted((session_a.session_id, session_b.session_id))
        )
        assert server_protocol.endpoint_for(session_a).stats.rx_data_frames == 1
        assert server_protocol.endpoint_for(session_b).stats.rx_data_frames == 1

        client_a.send_ping(b"health-a")
        client_b.send_ping(b"health-b")
        pong_a = await client_a.recv(timeout=1.0)
        pong_b = await client_b.recv(timeout=1.0)
        assert pong_a.frame_type == FrameType.PONG
        assert pong_a.payload == b"health-a"
        assert pong_b.frame_type == FrameType.PONG
        assert pong_b.payload == b"health-b"
    finally:
        client_a_transport.close()
        client_b_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_mtu_probe_over_firstparty_udp_runtime_selects_payload_size() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    server_transport, _server_protocol, addr = await open_udp_server(session=session)
    client_transport, client = await open_udp_client(session=session, remote_addr=addr)
    try:
        result = await probe_firstparty_mtu(
            client,
            policy=MtuProbePolicy(
                candidates=(900, 700),
                timeout=1.0,
                safety_margin=64,
                minimum_payload_size=576,
            ),
        )

        assert result.selected_payload_size == 900
        assert result.selected_fragment_payload_size == 836
        assert len(result.attempts) == 1
        assert result.attempts[0].payload_size == 900
        assert result.attempts[0].success is True
    finally:
        client_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_mtu_probe_falls_back_to_next_candidate_and_caches_path() -> None:
    result = await probe_firstparty_mtu(
        FakeProbeClient(fail_sizes={900}),
        policy=MtuProbePolicy(
            candidates=(900, 700, 576),
            timeout=0.01,
            safety_margin=32,
            minimum_payload_size=576,
        ),
    )
    cache = PathMtuCache()
    path_id = mtu_path_id(transport="udp", host="203.0.113.10", port=443)

    cache.remember(path_id, result)

    assert result.selected_payload_size == 700
    assert result.selected_fragment_payload_size == 668
    assert result.attempts[0].success is False
    assert result.attempts[1].success is True
    cached_fragmenter = cache.fragmenter_for(path_id)
    assert cached_fragmenter is not None
    assert cached_fragmenter.max_payload_size == 668


@pytest.mark.asyncio
async def test_mtu_validation_evidence_covers_required_paths_privately() -> None:
    plan = dataplane_validation_plan()

    async def mtu_runner(probe: DataplaneProbeSpec) -> MtuPathProbeResult:
        return _successful_mtu_probe_result(probe)

    async def dataplane_runner(probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        return DataplaneProbeResult.success_result(probe, latency_millis=11)

    evidence = await evaluate_mtu_validation(
        plan=plan,
        runner=mtu_runner,
        captured_at=NOW,
    )
    dataplane = await evaluate_dataplane_validation(
        plan=plan,
        runner=dataplane_runner,
        captured_at=NOW,
    )
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.passed is True
    assert set(evidence.covered_path_labels) == set(plan.required_path_labels)
    assert evidence.probe_matrix_hash() == dataplane.probe_matrix_hash()
    assert len(evidence.evidence_hash()) == 64
    assert "203.0.113.10" not in encoded
    assert "192.0.2.10" not in encoded
    assert "restricted-work-wifi-nl" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_remote_mtu_probe_runner_probes_existing_firstparty_endpoint() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    server_transport = None
    try:
        server_transport, _server_protocol, addr = await open_udp_server(session=session)
        probe = DataplaneProbeSpec(
            probe_id="mtu-remote-udp",
            path_label="vps",
            transport="udp",
            remote_ref="mtu-remote-udp-private-ref",
            payload_size=96,
        )
        plan = DataplaneValidationPlan(
            probes=(probe,),
            required_path_labels=frozenset({"vps"}),
            min_successful_probes=1,
        )

        evidence = await evaluate_mtu_validation(
            plan=plan,
            runner=FirstPartyRemoteMtuProbeRunner(
                session=session,
                endpoint_resolver=lambda _probe: addr,
                policy=MtuProbePolicy(
                    candidates=(700,),
                    timeout=1.0,
                    safety_margin=64,
                    minimum_payload_size=576,
                ),
            ),
            captured_at=NOW,
        )
        encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

        assert evidence.passed is True
        assert evidence.results[0].selected_payload_size == 700
        assert evidence.results[0].selected_fragment_payload_size == 636
        assert evidence.results[0].failed_attempt_count == 0
        assert "127.0.0.1" not in encoded
        assert "mtu-remote-udp-private-ref" not in encoded
        assert_privacy_safe(evidence.to_json_dict())
    finally:
        if server_transport is not None:
            server_transport.close()


@pytest.mark.asyncio
async def test_tcp_stream_runtime_round_trips_data_and_ping() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    server, server_protocol, addr = await open_tcp_server(
        session=session,
        on_data=lambda payload, _addr: b"tcp-echo:" + payload,
    )
    client = await open_tcp_client(session=session, remote_addr=addr)
    try:
        client.send_data(b"payload-1")
        await client.drain()
        response = await client.recv()

        assert response.frame_type == FrameType.DATA
        assert response.payload == b"tcp-echo:payload-1"
        assert client.endpoint.stats.rx_data_frames == 1

        client.send_ping(b"health")
        await client.drain()
        pong = await client.recv()
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"health"
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()

    assert server_protocol.stats.rx_data_frames == 1
    assert server_protocol.stats.tx_data_frames == 1


@pytest.mark.asyncio
async def test_tcp_multi_session_runtime_routes_two_users_on_one_listener() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"tcp-pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"tcp-client-nonce-a".ljust(32, b"c"),
        server_nonce=b"tcp-server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"tcp-pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"tcp-client-nonce-b".ljust(32, b"c"),
        server_nonce=b"tcp-server-nonce-b".ljust(32, b"s"),
    )
    assert session_a.session_id != session_b.session_id
    server, server_protocol, addr = await open_tcp_multi_session_server(
        sessions=(session_a, session_b),
        on_data=lambda payload, _addr: b"multi-tcp:" + payload,
    )
    client_a = await open_tcp_client(session=session_a, remote_addr=addr)
    client_b = await open_tcp_client(session=session_b, remote_addr=addr)
    try:
        client_a.send_data(b"user-a")
        client_b.send_data(b"user-b")
        await client_a.drain()
        await client_b.drain()
        response_a = await client_a.recv(timeout=1.0)
        response_b = await client_b.recv(timeout=1.0)

        assert response_a.frame_type == FrameType.DATA
        assert response_a.payload == b"multi-tcp:user-a"
        assert response_b.frame_type == FrameType.DATA
        assert response_b.payload == b"multi-tcp:user-b"
        assert server_protocol.admitted_session_ids == tuple(
            sorted((session_a.session_id, session_b.session_id))
        )

        client_a.send_ping(b"health-a")
        client_b.send_ping(b"health-b")
        await client_a.drain()
        await client_b.drain()
        pong_a = await client_a.recv(timeout=1.0)
        pong_b = await client_b.recv(timeout=1.0)
        assert pong_a.frame_type == FrameType.PONG
        assert pong_a.payload == b"health-a"
        assert pong_b.frame_type == FrameType.PONG
        assert pong_b.payload == b"health-b"
    finally:
        client_a.close()
        client_b.close()
        await client_a.wait_closed()
        await client_b.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()

    assert server_protocol.stats.rx_data_frames == 2
    assert server_protocol.stats.tx_data_frames == 2


@pytest.mark.asyncio
async def test_camouflage_stream_runtime_uses_preface_and_round_trips() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    policy = CamouflagePolicy(allowed_profile_ids=frozenset({"restricted-work-wifi"}))
    request = encode_camouflage_request(
        session=session,
        profile=profile,
        policy=policy,
    )
    server, server_protocol, addr = await open_camouflage_server(
        session=session,
        profile=profile,
        policy=policy,
        on_data=lambda payload, _addr: b"camouflage-echo:" + payload,
    )
    client = await open_camouflage_client(
        session=session,
        remote_addr=addr,
        profile=profile,
        policy=policy,
        timeout=0.5,
    )
    try:
        assert request.startswith(b"POST /assets/check HTTP/1.1\r\n")
        assert b"Host: updates.invalid\r\n" in request
        assert b"x0vpn" not in request.lower()
        assert b"vpn" not in request.lower()

        client.send_data(b"payload-1")
        await client.drain()
        response = await client.recv()

        assert response.frame_type == FrameType.DATA
        assert response.payload == b"camouflage-echo:payload-1"

        client.send_ping(b"health")
        await client.drain()
        pong = await client.recv()
        assert pong.frame_type == FrameType.PONG
        assert pong.payload == b"health"
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()

    assert server_protocol.stats.rx_data_frames == 1
    assert server_protocol.stats.tx_data_frames == 1


@pytest.mark.asyncio
async def test_camouflage_multi_session_runtime_routes_two_users_on_one_listener() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"camouflage-pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"camouflage-client-nonce-a".ljust(32, b"c"),
        server_nonce=b"camouflage-server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"camouflage-pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"camouflage-client-nonce-b".ljust(32, b"c"),
        server_nonce=b"camouflage-server-nonce-b".ljust(32, b"s"),
    )
    assert session_a.session_id != session_b.session_id
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    policy = CamouflagePolicy(allowed_profile_ids=frozenset({"restricted-work-wifi"}))
    server, server_protocol, addr = await open_camouflage_multi_session_server(
        sessions=(session_a, session_b),
        profile=profile,
        policy=policy,
        on_data=lambda payload, _addr: b"multi-camouflage:" + payload,
    )
    client_a = await open_camouflage_client(
        session=session_a,
        remote_addr=addr,
        profile=profile,
        policy=policy,
        timeout=0.5,
    )
    client_b = await open_camouflage_client(
        session=session_b,
        remote_addr=addr,
        profile=profile,
        policy=policy,
        timeout=0.5,
    )
    try:
        assert server_protocol.admitted_session_ids == tuple(
            sorted((session_a.session_id, session_b.session_id))
        )
        client_a.send_data(b"user-a")
        client_b.send_data(b"user-b")
        await client_a.drain()
        await client_b.drain()
        response_a = await client_a.recv(timeout=1.0)
        response_b = await client_b.recv(timeout=1.0)

        assert response_a.frame_type == FrameType.DATA
        assert response_a.payload == b"multi-camouflage:user-a"
        assert response_b.frame_type == FrameType.DATA
        assert response_b.payload == b"multi-camouflage:user-b"

        client_a.send_ping(b"health-a")
        client_b.send_ping(b"health-b")
        await client_a.drain()
        await client_b.drain()
        pong_a = await client_a.recv(timeout=1.0)
        pong_b = await client_b.recv(timeout=1.0)
        assert pong_a.frame_type == FrameType.PONG
        assert pong_a.payload == b"health-a"
        assert pong_b.frame_type == FrameType.PONG
        assert pong_b.payload == b"health-b"
    finally:
        client_a.close()
        client_b.close()
        await client_a.wait_closed()
        await client_b.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()

    assert server_protocol.stats.rx_data_frames == 2
    assert server_protocol.stats.tx_data_frames == 2


@pytest.mark.asyncio
async def test_camouflage_transport_fails_closed_for_policy_and_session_mismatch() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    wrong_session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"wrong-pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    profile = CamouflageProfile(profile_id="restricted-work-wifi")
    policy = CamouflagePolicy(allowed_profile_ids=frozenset({"restricted-work-wifi"}))

    with pytest.raises(CamouflageError):
        encode_camouflage_request(
            session=session,
            profile=profile,
            policy=CamouflagePolicy(allowed_profile_ids=frozenset({"other-profile"})),
        )

    server, server_protocol, addr = await open_camouflage_server(
        session=session,
        profile=profile,
        policy=policy,
    )
    try:
        with pytest.raises(CamouflageError):
            await open_camouflage_client(
                session=wrong_session,
                remote_addr=addr,
                profile=profile,
                policy=policy,
                timeout=0.5,
            )
    finally:
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_policy_distribution_round_trips_over_firstparty_tcp(
    tmp_path: Path,
) -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    key = signing_key("policy-key-1")
    snapshot = PolicySnapshot(
        policy_epoch="epoch-2",
        issued_at=NOW + 20,
        posture_policy=DevicePosturePolicy(max_posture_age_seconds=120),
    )
    envelope = PolicySnapshotDistributor(
        issuer="x0tta6bl4-policy-authority",
        signing_key=key,
    ).issue(snapshot, sequence=9, now=NOW + 21)
    server, server_protocol, addr = await open_tcp_server(
        session=session,
        on_data=lambda payload, _addr: (
            envelope.to_bytes() if payload == POLICY_SNAPSHOT_REQUEST else None
        ),
    )
    client = await open_tcp_client(session=session, remote_addr=addr)
    store = DurablePolicyStore(tmp_path / "policy.json")
    receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(store=store),
    )
    try:
        client.send_data(POLICY_SNAPSHOT_REQUEST)
        await client.drain()
        response = await client.recv()

        assert response.frame_type == FrameType.DATA
        applied = receiver.accept(response.payload)
        assert applied.policy_epoch == "epoch-2"
        assert store.load().snapshot_hash() == snapshot.snapshot_hash()
        assert receiver.current_sequence == 9
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_policy_snapshot_fetch_client_uses_server_handler_and_audits(
    tmp_path: Path,
) -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    key = signing_key("policy-key-1")
    snapshot = PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW + 20)
    server_audit = PrivacySafeAuditLog(tmp_path / "server-audit.jsonl")
    client_audit = PrivacySafeAuditLog(tmp_path / "client-audit.jsonl")
    handler = PolicySnapshotServerHandler(
        distributor=PolicySnapshotDistributor(
            issuer="x0tta6bl4-policy-authority",
            signing_key=key,
        ),
        snapshot_source=lambda: snapshot,
        initial_sequence=40,
        audit_log=server_audit,
        now_provider=lambda: NOW + 21,
    )
    server, server_protocol, addr = await open_tcp_server(
        session=session,
        on_data=handler,
    )
    client = await open_tcp_client(session=session, remote_addr=addr)
    receiver = PolicySnapshotReceiver(
        expected_issuer="x0tta6bl4-policy-authority",
        verification_key=key,
        refresh_client=PolicyRefreshClient(
            store=DurablePolicyStore(tmp_path / "policy.json"),
        ),
        sequence_store=DurablePolicySequenceStore(tmp_path / "policy-sequence.json"),
    )
    fetcher = PolicySnapshotFetchClient(
        transport=client,
        receiver=receiver,
        audit_log=client_audit,
        actor_id="device-1",
        authority_id="x0tta6bl4-policy-authority",
        now_provider=lambda: NOW + 22,
    )
    try:
        applied = await fetcher.fetch_once()

        assert applied.snapshot_hash() == snapshot.snapshot_hash()
        assert handler.current_sequence == 41
        assert receiver.current_sequence == 41
        assert receiver.sequence_store is not None
        assert receiver.sequence_store.load().sequence == 41
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()

    server_events = server_audit.read_events()
    client_events = client_audit.read_events()
    assert server_events[-1]["event_type"] == "policy_snapshot_issue"
    assert server_events[-1]["outcome"] == "succeeded"
    assert server_events[-1]["metadata"]["sequence"] == 41
    assert client_events[-1]["event_type"] == "policy_snapshot_fetch"
    assert client_events[-1]["outcome"] == "succeeded"
    assert client_events[-1]["metadata"]["snapshot_hash"] == snapshot.snapshot_hash()


@pytest.mark.asyncio
async def test_policy_snapshot_fetch_client_fails_closed_and_audits_bad_response(
    tmp_path: Path,
) -> None:
    bad_response = Frame(
        frame_type=FrameType.DATA,
        session_id=1,
        sequence=1,
        payload=b"not-a-policy-envelope",
    )
    key = signing_key("policy-key-1")
    audit = PrivacySafeAuditLog(tmp_path / "client-audit.jsonl")
    fetcher = PolicySnapshotFetchClient(
        transport=FakePolicySnapshotTransport(bad_response),
        receiver=PolicySnapshotReceiver(
            expected_issuer="x0tta6bl4-policy-authority",
            verification_key=key,
            refresh_client=PolicyRefreshClient(
                store=DurablePolicyStore(tmp_path / "policy.json"),
            ),
        ),
        audit_log=audit,
        now_provider=lambda: NOW + 30,
    )

    with pytest.raises(PolicyDistributionError, match="magic mismatch"):
        await fetcher.fetch_once()

    events = audit.read_events()
    assert events[-1]["event_type"] == "policy_snapshot_fetch"
    assert events[-1]["outcome"] == "failed"
    assert "reason_hash" in events[-1]["metadata"]


def test_policy_snapshot_server_handler_rejects_unknown_request_and_audits(
    tmp_path: Path,
) -> None:
    audit = PrivacySafeAuditLog(tmp_path / "server-audit.jsonl")
    handler = PolicySnapshotServerHandler(
        distributor=PolicySnapshotDistributor(
            issuer="x0tta6bl4-policy-authority",
            signing_key=signing_key("policy-key-1"),
        ),
        snapshot_source=lambda: PolicySnapshot(policy_epoch="epoch-2", issued_at=NOW),
        audit_log=audit,
        now_provider=lambda: NOW + 31,
    )

    response = handler(b"unsupported-request", ("127.0.0.1", 443))

    assert response is None
    assert handler.current_sequence == 0
    events = audit.read_events()
    assert events[-1]["event_type"] == "policy_snapshot_request"
    assert events[-1]["outcome"] == "rejected"
    assert events[-1]["metadata"]["reason"] == "unsupported_request"


def test_tcp_stream_record_rejects_empty_or_oversized_frame() -> None:
    with pytest.raises(StreamRecordError):
        encode_stream_record(b"")
    with pytest.raises(StreamRecordError):
        encode_stream_record(b"x" * 70000)


@pytest.mark.asyncio
async def test_tun_bridge_moves_packet_over_firstparty_udp_runtime() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=1400)
    server_tun = MemoryTunDevice(mtu=1400)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"remote:", packet),
    )
    server_transport, _server_protocol, addr = await open_udp_server(
        session=session,
        on_data=server_handler,
    )
    client_transport, client = await open_udp_client(session=session, remote_addr=addr)
    bridge = FirstPartyTunClientBridge(tun=client_tun, client=client)
    try:
        packet = ipv4_packet(b"first-party-ip-packet")
        client_tun.inject_packet(packet)
        await bridge.send_one_from_tun()
        await bridge.receive_one_to_tun()

        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"remote:",
            packet,
        )
        assert bridge.stats.packets_from_tun == 1
        assert bridge.stats.packets_to_tun == 1
        assert server_handler.stats.packets_to_tun == 1
        assert server_handler.stats.packets_from_tun == 1
    finally:
        client_transport.close()
        server_transport.close()


@pytest.mark.asyncio
async def test_tun_bridge_fragments_large_packet_over_firstparty_tcp_runtime() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"tcp-remote:", packet),
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    server, server_protocol, addr = await open_tcp_server(
        session=session,
        on_data=server_handler,
    )
    client = await open_tcp_client(session=session, remote_addr=addr)
    bridge = FirstPartyTunClientBridge(
        tun=client_tun,
        client=client,
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    try:
        packet = ipv4_packet(b"t" * 700)
        client_tun.inject_packet(packet)
        await bridge.send_one_from_tun()
        await bridge.receive_one_to_tun()

        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"tcp-remote:",
            packet,
        )
        assert bridge.stats.tx_fragments > 1
        assert bridge.stats.rx_fragments > 1
        assert server_handler.stats.rx_fragments > 1
        assert server_handler.stats.tx_fragments > 1
    finally:
        client.close()
        await client.wait_closed()
        server.close()
        await server.wait_closed()
        await server_protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_managed_tun_client_bridge_uses_selected_tcp_fallback() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"managed:", packet),
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=server_handler,
    )
    managed = None
    try:
        assert service.tcp_addr is not None
        managed = await open_firstparty_tun_client_bridge(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="managed-udp-blocked",
                    path_label="nl-udp",
                    transport="udp",
                    remote_ref="managed-primary-udp",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="managed-tcp-working",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="managed-fallback-tcp",
                    remote_addr=service.tcp_addr,
                    priority=2,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
        )
        packet = ipv4_packet(b"m" * 700)
        client_tun.inject_packet(packet)
        await managed.send_one_from_tun()
        await managed.receive_one_to_tun()
        encoded = json.dumps(managed.selection_evidence.to_json_dict(), sort_keys=True)

        assert isinstance(managed, FirstPartyManagedTunClientBridge)
        assert managed.client.transport == "tcp"
        assert managed.selection_evidence.passed is True
        assert len(managed.selection_evidence.results) == 2
        assert managed.selection_evidence.results[0].success is False
        assert managed.selection_evidence.results[1].success is True
        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"managed:",
            packet,
        )
        assert managed.stats.packets_from_tun == 1
        assert managed.stats.packets_to_tun == 1
        assert managed.stats.tx_fragments > 1
        assert managed.stats.rx_fragments > 1
        assert "127.0.0.1" not in encoded
        assert "managed-primary-udp" not in encoded
        assert "managed-fallback-tcp" not in encoded
        assert_privacy_safe(managed.selection_evidence.to_json_dict())
    finally:
        if managed is not None:
            await managed.close()
        await service.close()


@pytest.mark.asyncio
async def test_tun_client_pump_runs_bidirectional_selected_tcp_fallback() -> None:
    with pytest.raises(ValueError):
        TunPumpStats(timeouts=-1)
    with pytest.raises(ValueError):
        FirstPartyTunClientPump(
            managed=None,  # type: ignore[arg-type]
            tun_read_timeout=0,
        )

    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"pump:", packet),
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=server_handler,
    )
    pump = None
    try:
        assert service.tcp_addr is not None
        pump = await open_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="pump-udp-blocked",
                    path_label="nl-udp",
                    transport="udp",
                    remote_ref="pump-primary-udp",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="pump-tcp-working",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="pump-fallback-tcp",
                    remote_addr=service.tcp_addr,
                    priority=2,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )
        with pytest.raises(FirstPartyTunPumpError):
            pump.start()

        packet = ipv4_packet(b"p" * 700)
        client_tun.inject_packet(packet)
        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"pump:",
            packet,
        )
        encoded = json.dumps(
            pump.managed.selection_evidence.to_json_dict(),
            sort_keys=True,
        )

        assert pump.running is True
        assert pump.managed.client.transport == "tcp"
        assert pump.managed.selection_evidence.passed is True
        assert pump.stats.tun_to_transport_cycles >= 1
        assert pump.stats.transport_to_tun_cycles >= 1
        assert pump.managed.stats.packets_from_tun == 1
        assert pump.managed.stats.packets_to_tun == 1
        assert pump.managed.stats.tx_fragments > 1
        assert pump.managed.stats.rx_fragments > 1
        assert "127.0.0.1" not in encoded
        assert "pump-primary-udp" not in encoded
        assert "pump-fallback-tcp" not in encoded
        assert_privacy_safe(pump.managed.selection_evidence.to_json_dict())
    finally:
        if pump is not None:
            await pump.stop()
        await service.close()

    assert pump is not None
    assert pump.running is False
    assert pump.stats.cancellations >= 1


@pytest.mark.asyncio
async def test_tun_client_pump_pauses_rekeys_and_resumes_selected_camouflage() -> None:
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"tun-rekey:", packet),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        on_data=server_handler,
        rekey_processor=FirstPartyRekeyServerProcessor(
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            shared_secret_resolver=lambda request: create_firstparty_handshake_hello(
                pqc_provider=provider,
                client_identity=request.hello.client_identity,
                server_identity=server_token,
                deployment_epoch=request.hello.deployment_epoch,
                client_nonce=request.hello.client_nonce,
                issued_at=request.hello.issued_at,
            )[1],
            server_nonce_provider=lambda _request: b"tun-rekey-server-nonce".ljust(32, b"s"),
            accepted_at_provider=lambda _request: NOW,
        ),
    )
    pump = None
    try:
        assert service.camouflage_addr is not None
        pump = await open_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="tun-rekey-camouflage",
                    path_label="restricted-camouflage",
                    transport="camouflage",
                    remote_ref="tun-rekey-camouflage-ref",
                    remote_addr=service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )

        first_packet = ipv4_packet(b"tun-rekey-before")
        client_tun.inject_packet(first_packet)
        assert await server_tun.read_written(timeout=1.0) == first_packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"tun-rekey:",
            first_packet,
        )

        result = await pump.perform_rekey(
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            base_deployment_epoch="test-epoch",
            generation=2,
            reason="scheduled-rotation",
            client_nonce=b"tun-rekey-client-nonce".ljust(32, b"c"),
            requested_at=NOW,
            timeout=1.0,
            completed_at_provider=lambda accept: accept.accept.accepted_at,
        )
        second_packet = ipv4_packet(b"tun-rekey-after")
        client_tun.inject_packet(second_packet)
        assert await server_tun.read_written(timeout=1.0) == second_packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"tun-rekey:",
            second_packet,
        )

        assert pump.running is True
        assert pump.stats.rekeys == 1
        assert result.next_session.session_id != session.session_id
        assert pump.managed.client.transport == "camouflage"
        assert pump.managed.client.endpoint.session.session_id == result.next_session.session_id
        assert service.camouflage_protocol is not None
        assert service.camouflage_protocol.session.session_id == result.next_session.session_id
        assert pump.managed.stats.packets_from_tun == 2
        assert pump.managed.stats.packets_to_tun == 2
    finally:
        if pump is not None:
            await pump.stop()
        await service.close()


@pytest.mark.asyncio
async def test_tun_client_pump_rejects_stale_rekey_accept() -> None:
    authority = identity_authority()
    verifier = ReadOnlyIdentityVerifier(
        issuer=authority.issuer,
        verification_keys=(signing_key("id-key-1"),),
    )
    policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    session = establish_firstparty_session_from_signed_identities(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"previous-pqc-shared-secret".ljust(48, b"-"),
        client_identity=client_token,
        server_identity=server_token,
        identity_authority=verifier,
        policy=policy,
        now=NOW,
        client_nonce=b"previous-client-nonce".ljust(32, b"c"),
        server_nonce=b"previous-server-nonce".ljust(32, b"s"),
        deployment_epoch="test-epoch",
    )
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"tun-stale-rekey:", packet),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        on_data=server_handler,
        rekey_processor=FirstPartyRekeyServerProcessor(
            server_identity=server_token,
            identity_authority=verifier,
            policy=policy,
            shared_secret_resolver=lambda request: create_firstparty_handshake_hello(
                pqc_provider=provider,
                client_identity=request.hello.client_identity,
                server_identity=server_token,
                deployment_epoch=request.hello.deployment_epoch,
                client_nonce=request.hello.client_nonce,
                issued_at=request.hello.issued_at,
            )[1],
            server_nonce_provider=lambda _request: b"tun-stale-rekey-server".ljust(
                32,
                b"s",
            ),
            accepted_at_provider=lambda _request: NOW,
        ),
    )
    pump = None
    try:
        assert service.camouflage_addr is not None
        pump = await open_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="tun-stale-rekey-camouflage",
                    path_label="restricted-camouflage",
                    transport="camouflage",
                    remote_ref="tun-stale-rekey-camouflage-ref",
                    remote_addr=service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )

        with pytest.raises(FirstPartyHandshakeError, match="ACCEPT is stale"):
            await pump.perform_rekey(
                pqc_provider=provider,
                client_identity=client_token,
                server_identity=server_token,
                identity_authority=verifier,
                policy=policy,
                base_deployment_epoch="test-epoch",
                generation=2,
                reason="scheduled-rotation",
                client_nonce=b"tun-stale-rekey-client".ljust(32, b"c"),
                requested_at=NOW,
                timeout=1.0,
                completed_at_provider=lambda _accept: NOW + 301,
            )

        assert pump.stats.rekeys == 0
        assert pump.managed.client.endpoint.session.session_id == session.session_id
    finally:
        if pump is not None:
            await pump.stop()
        await service.close()


@pytest.mark.asyncio
async def test_tun_server_pump_sends_async_tun_reply_to_selected_tcp_client() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=server_handler,
    )
    client_pump = None
    server_pump = None
    try:
        assert service.tcp_addr is not None
        assert service.tcp_protocol is not None
        client_pump = await open_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="async-reply-tcp",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="async-reply-tcp-ref",
                    remote_addr=service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )
        server_pump = FirstPartyTunServerPump(
            tun=server_tun,
            server=service.tcp_protocol,
            fragmenter=PacketFragmenter(max_payload_size=64),
            tun_read_timeout=0.05,
        ).start()
        with pytest.raises(FirstPartyTunPumpError):
            server_pump.start()

        packet = ipv4_packet(b"s" * 700)
        client_tun.inject_packet(packet)
        assert await server_tun.read_written(timeout=1.0) == packet

        reply = ip_like_response(b"server-async:", packet)
        server_tun.inject_packet(reply)
        assert await client_tun.read_written(timeout=1.0) == reply

        assert server_handler.stats.packets_to_tun == 1
        assert server_pump.running is True
        assert server_pump.stats.packets_from_tun == 1
        assert server_pump.stats.tx_fragments > 1
        assert server_pump.pump_stats.tun_to_transport_cycles >= 1
        assert client_pump.managed.stats.packets_to_tun == 1
        assert client_pump.managed.stats.rx_fragments > 1
    finally:
        if server_pump is not None:
            await server_pump.stop()
        if client_pump is not None:
            await client_pump.stop()
        await service.close()


def test_fragmenter_reassembles_out_of_order_fragments() -> None:
    fragmenter = PacketFragmenter(max_payload_size=64)
    reassembler = PacketReassembler()
    packet = ipv4_packet(b"x" * 180)

    fragments = fragmenter.split(packet)

    assert len(fragments) > 1
    for fragment in reversed(fragments[1:]):
        assert reassembler.accept(fragment) is None
    assert reassembler.accept(fragments[0]) == packet
    assert reassembler.pending_packets == 0


def test_fragment_reassembler_rejects_duplicate_fragment_index() -> None:
    fragmenter = PacketFragmenter(max_payload_size=64)
    reassembler = PacketReassembler()
    packet = ipv4_packet(b"x" * 120)
    fragments = fragmenter.split(packet)

    assert reassembler.accept(fragments[0]) is None
    with pytest.raises(FragmentError, match="duplicate fragment index"):
        reassembler.accept(fragments[0])
    assert reassembler.pending_packets == 0


def test_fragment_reassembler_rejects_changed_metadata_and_drops_packet() -> None:
    reassembler = PacketReassembler()
    first = PacketFragment(
        packet_id=7,
        index=0,
        count=2,
        total_len=4,
        chunk=b"ab",
    ).encode()
    changed = PacketFragment(
        packet_id=7,
        index=1,
        count=3,
        total_len=4,
        chunk=b"cd",
    ).encode()

    assert reassembler.accept(first) is None
    with pytest.raises(FragmentError, match="fragment metadata changed"):
        reassembler.accept(changed)
    assert reassembler.pending_packets == 0


def test_fragment_reassembler_rejects_chunks_exceeding_total_length() -> None:
    reassembler = PacketReassembler()
    first = PacketFragment(
        packet_id=9,
        index=0,
        count=2,
        total_len=4,
        chunk=b"abc",
    ).encode()
    second = PacketFragment(
        packet_id=9,
        index=1,
        count=2,
        total_len=4,
        chunk=b"de",
    ).encode()

    assert reassembler.accept(first) is None
    with pytest.raises(FragmentError, match="fragment chunks exceed packet length"):
        reassembler.accept(second)
    assert reassembler.pending_packets == 0


def test_fragment_reassembler_rejects_packet_over_pending_byte_budget() -> None:
    fragmenter = PacketFragmenter(max_payload_size=64)
    packet = ipv4_packet(b"x" * 60)
    fragments = fragmenter.split(packet)
    reassembler = PacketReassembler(max_pending_bytes=len(packet) - 1)

    with pytest.raises(FragmentError, match="pending byte budget"):
        reassembler.accept(fragments[0])
    assert reassembler.pending_packets == 0


def test_fragment_reassembler_evicts_oldest_pending_packet_to_fit_limits() -> None:
    fragmenter = PacketFragmenter(max_payload_size=64)
    reassembler = PacketReassembler(max_pending_packets=1)
    packet_a = ipv4_packet(b"a" * 80)
    packet_b = ipv4_packet(b"b" * 80)
    fragments_a = fragmenter.split(packet_a)
    fragments_b = fragmenter.split(packet_b)

    assert reassembler.accept(fragments_a[0]) is None
    assert reassembler.pending_packets == 1
    assert reassembler.accept(fragments_b[0]) is None
    assert reassembler.pending_packets == 1

    packet: bytes | None = None
    for fragment in fragments_b[1:]:
        packet = reassembler.accept(fragment)

    assert packet == packet_b
    assert reassembler.pending_packets == 0


def test_fragmenter_rejects_invalid_payload_size_and_packet() -> None:
    with pytest.raises(ValueError):
        PacketFragmenter(max_payload_size=1)
    with pytest.raises(FragmentError):
        PacketFragmenter(max_payload_size=64).split(b"")


def test_firstparty_geneva_strategy_selects_safe_fragmenter() -> None:
    strategy = FirstPartyGenevaStrategy(
        actions=(
            FirstPartyGenevaAction("split", 80),
            FirstPartyGenevaAction("duplicate", 2),
            FirstPartyGenevaAction("tamper", 1),
        ),
    )
    profile = FirstPartyAntiDpiProfile(
        transport="camouflage",
        geneva=strategy,
    )
    fragmenter = profile.fragmenter()

    assert strategy.selected_fragment_payload_size() == 80
    assert strategy.unsafe_action_names == ("duplicate", "tamper")
    assert fragmenter is not None
    assert fragmenter.max_payload_size == 80
    assert len(fragmenter.split(ipv4_packet(b"x" * 180))) > 1
    assert profile.to_json_dict()["camouflage"] == {"enabled": True}


def test_firstparty_tesla_delayed_auth_round_trip_and_tamper_reject() -> None:
    auth = FirstPartyTeslaAuthenticator(
        b"tesla-master-secret".ljust(32, b"-"),
        FirstPartyTeslaPolicy(slot_seconds=10, disclosure_delay_slots=2),
    )
    envelope = auth.seal(b"payload", sequence=7, timestamp=25)

    with pytest.raises(TeslaAuthError, match="not due yet"):
        auth.disclose_key(envelope.slot, current_timestamp=39)

    disclosed_key = auth.disclose_key(envelope.slot, current_timestamp=40)
    tampered = replace(envelope, payload=b"tampered")

    assert auth.verify(envelope, disclosed_key) is True
    assert auth.verify(tampered, disclosed_key) is False


@pytest.mark.asyncio
async def test_tun_bridge_applies_mtu_probe_result_to_fragmenter() -> None:
    result = await probe_firstparty_mtu(
        FakeProbeClient(),
        policy=MtuProbePolicy(
            candidates=(700,),
            timeout=0.01,
            safety_margin=32,
            minimum_payload_size=576,
        ),
    )
    tun = MemoryTunDevice(mtu=900)
    client = FakeTunClient()
    bridge = FirstPartyTunClientBridge(tun=tun, client=client)

    bridge.apply_mtu_probe_result(result)
    tun.inject_packet(ipv4_packet(b"x" * 700))
    await bridge.send_one_from_tun()

    assert bridge.stats.mtu_probe_updates == 1
    assert bridge.fragmenter is not None
    assert bridge.fragmenter.max_payload_size == 668
    assert len(client.sent_payloads) > 1
    assert bridge.stats.tx_fragments == len(client.sent_payloads)


@pytest.mark.asyncio
async def test_tun_bridge_fragments_large_packet_over_firstparty_udp_runtime() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_handler = FirstPartyTunServerHandler(
        tun=server_tun,
        response=lambda packet: ip_like_response(b"remote:", packet),
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    server_transport, _server_protocol, addr = await open_udp_server(
        session=session,
        on_data=server_handler,
    )
    client_transport, client = await open_udp_client(session=session, remote_addr=addr)
    bridge = FirstPartyTunClientBridge(
        tun=client_tun,
        client=client,
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
    )
    try:
        packet = ipv4_packet(b"x" * 700)
        client_tun.inject_packet(packet)
        await bridge.send_one_from_tun()
        await bridge.receive_one_to_tun()

        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response(
            b"remote:",
            packet,
        )
        assert bridge.stats.tx_fragments > 1
        assert bridge.stats.rx_fragments > 1
        assert server_handler.stats.rx_fragments > 1
        assert server_handler.stats.tx_fragments > 1
    finally:
        client_transport.close()
        server_transport.close()


def test_memory_tun_rejects_empty_and_oversized_packets() -> None:
    tun = MemoryTunDevice(mtu=576)
    valid_ipv4 = ipv4_packet(b"ok")
    valid_ipv6 = ipv6_packet(b"ok")
    invalid_ipv4_length = bytearray(valid_ipv4)
    invalid_ipv4_length[2:4] = (len(valid_ipv4) + 1).to_bytes(2, "big")
    invalid_ipv6_length = bytearray(valid_ipv6)
    invalid_ipv6_length[4:6] = (len(valid_ipv6)).to_bytes(2, "big")

    tun.inject_packet(valid_ipv4)
    tun.write_packet_nowait(valid_ipv6)

    with pytest.raises(TunPacketError):
        tun.inject_packet(b"")
    with pytest.raises(TunPacketError, match="IPv4 or IPv6"):
        tun.inject_packet(b"x" * 20)
    with pytest.raises(TunPacketError, match="IPv4 packet is too short"):
        tun.inject_packet(b"\x45\x00")
    with pytest.raises(TunPacketError, match="IPv4 total length"):
        tun.inject_packet(bytes(invalid_ipv4_length))
    with pytest.raises(TunPacketError, match="IPv6 payload length"):
        tun.inject_packet(bytes(invalid_ipv6_length))
    with pytest.raises(TunPacketError):
        tun.inject_packet(b"x" * 577)


def test_linux_tun_plans_commands_and_blocks_mutation_by_default() -> None:
    commands: list[tuple[str, ...]] = []
    config = LinuxTunConfig(
        name="x0vpn0",
        mtu=1280,
        address="10.77.0.2/32",
        peer="10.77.0.1",
    )
    device = LinuxTunDevice(config=config, command_runner=commands.append)

    assert device.planned_network_commands() == (
        ("ip", "link", "set", "dev", "x0vpn0", "mtu", "1280"),
        (
            "ip",
            "addr",
            "add",
            "10.77.0.2/32",
            "peer",
            "10.77.0.1",
            "dev",
            "x0vpn0",
        ),
        ("ip", "link", "set", "dev", "x0vpn0", "up"),
    )
    with pytest.raises(LinuxTunMutationBlocked):
        device.apply_network_config()
    with pytest.raises(LinuxTunMutationBlocked):
        device.open_interface()
    assert commands == []


def test_linux_tun_applies_network_config_only_when_explicitly_allowed() -> None:
    commands: list[tuple[str, ...]] = []
    config = LinuxTunConfig(
        name="x0vpn1",
        mtu=1400,
        address="10.77.0.3/32",
        allow_os_mutation=True,
    )
    device = LinuxTunDevice(config=config, command_runner=commands.append)

    device.apply_network_config()

    assert commands == [
        ("ip", "link", "set", "dev", "x0vpn1", "mtu", "1400"),
        ("ip", "addr", "add", "10.77.0.3/32", "dev", "x0vpn1"),
        ("ip", "link", "set", "dev", "x0vpn1", "up"),
    ]


def test_linux_tun_rejects_unsafe_interface_config() -> None:
    with pytest.raises(ValueError):
        LinuxTunConfig(name="x0/vpn0")
    with pytest.raises(ValueError):
        LinuxTunConfig(name="x" * 16)
    with pytest.raises(ValueError):
        LinuxTunConfig(peer="10.77.0.1")


def test_linux_network_policy_plans_full_tunnel_dns_and_kill_switch() -> None:
    endpoint = RemoteEndpoint(host="203.0.113.10", port=443, transport="udp")
    planner = LinuxNetworkPolicyPlanner(
        config=LinuxNetworkPolicyConfig(
            tun_name="x0vpn0",
            remote_endpoints=(endpoint,),
            dns_servers=("9.9.9.9", "149.112.112.112"),
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
        )
    )

    assert planner.planned_commands() == (
        (
            "ip",
            "route",
            "replace",
            "203.0.113.10/32",
            "via",
            "192.0.2.1",
            "dev",
            "eth0",
        ),
        ("ip", "route", "replace", "default", "dev", "x0vpn0"),
        ("resolvectl", "dns", "x0vpn0", "9.9.9.9", "149.112.112.112"),
        ("resolvectl", "domain", "x0vpn0", "~."),
        ("resolvectl", "default-route", "x0vpn0", "yes"),
        ("nft", "add", "table", "inet", "x0vpn"),
        (
            "nft",
            "add",
            "chain",
            "inet",
            "x0vpn",
            "output",
            "{",
            "type",
            "filter",
            "hook",
            "output",
            "priority",
            "0",
            ";",
            "policy",
            "drop",
            ";",
            "}",
        ),
        ("nft", "add", "rule", "inet", "x0vpn", "output", "oifname", "lo", "accept"),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn",
            "output",
            "oifname",
            "x0vpn0",
            "accept",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn",
            "output",
            "ip",
            "daddr",
            "203.0.113.10",
            "udp",
            "dport",
            "443",
            "accept",
        ),
    )
    assert planner.rollback_commands() == (
        ("ip", "route", "replace", "default", "via", "192.0.2.1", "dev", "eth0"),
        (
            "ip",
            "route",
            "delete",
            "203.0.113.10/32",
            "via",
            "192.0.2.1",
            "dev",
            "eth0",
        ),
        ("resolvectl", "revert", "x0vpn0"),
        ("nft", "delete", "table", "inet", "x0vpn"),
    )


def test_linux_network_policy_plans_camouflage_underlay_as_tcp_rule() -> None:
    endpoint = RemoteEndpoint(host="203.0.113.10", port=443, transport="camouflage")
    planner = LinuxNetworkPolicyPlanner(
        config=LinuxNetworkPolicyConfig(
            tun_name="x0vpn0",
            remote_endpoints=(endpoint,),
            dns_servers=("9.9.9.9",),
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
        )
    )

    commands = planner.planned_commands()

    assert endpoint.transport == "camouflage"
    assert endpoint.firewall_protocol == "tcp"
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn",
        "output",
        "ip",
        "daddr",
        "203.0.113.10",
        "tcp",
        "dport",
        "443",
        "accept",
    ) in commands
    assert not any("camouflage" in command for command in commands)
    evidence = evaluate_linux_leak_protection(
        config=planner.config,
        commands=commands,
    )
    assert evidence.passed is True
    assert "underlay_endpoint_kill_switch_allow" in evidence.controls


def test_linux_leak_protection_validates_full_tunnel_dns_and_kill_switch() -> None:
    config = LinuxNetworkPolicyConfig(
        tun_name="x0vpn0",
        remote_endpoints=(RemoteEndpoint(host="203.0.113.10", port=443, transport="udp"),),
        dns_servers=("9.9.9.9", "149.112.112.112"),
        underlay_gateway="192.0.2.1",
        underlay_interface="eth0",
    )
    evidence = evaluate_linux_leak_protection(
        config=config,
        commands=LinuxNetworkPolicyPlanner(config=config).planned_commands(),
    )

    assert isinstance(evidence, LinuxLeakProtectionEvidence)
    assert evidence.passed is True
    assert evidence.reasons == ()
    assert "full_tunnel_default_route" in evidence.controls
    assert "tun_dns_servers" in evidence.controls
    assert "kill_switch_output_drop_policy" in evidence.controls
    assert "underlay_endpoint_route" in evidence.controls
    assert "underlay_endpoint_kill_switch_allow" in evidence.controls
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)
    assert "203.0.113.10" not in encoded
    assert "192.0.2.1" not in encoded
    assert "9.9.9.9" not in encoded
    assert len(evidence.evidence_hash()) == 64
    assert_privacy_safe(evidence.to_json_dict())


def test_linux_leak_protection_fails_closed_for_missing_dns_and_kill_switch() -> None:
    config = LinuxNetworkPolicyConfig(
        route_all_traffic=True,
        enable_kill_switch=False,
        dns_servers=(),
    )
    evidence = evaluate_linux_leak_protection(
        config=config,
        commands=LinuxNetworkPolicyPlanner(config=config).planned_commands(),
    )

    assert evidence.passed is False
    assert "tun_dns_servers_not_configured" in evidence.reasons
    assert "kill_switch_disabled" in evidence.reasons
    assert "full_tunnel_default_route" in evidence.controls


def test_linux_applied_state_validates_routes_dns_kill_switch_and_nat_privately() -> None:
    endpoint = RemoteEndpoint(host="203.0.113.10", port=443, transport="camouflage")
    client_network = LinuxNetworkPolicyConfig(
        tun_name="x0vpn0",
        remote_endpoints=(endpoint,),
        dns_servers=("9.9.9.9",),
        underlay_gateway="192.0.2.1",
        underlay_interface="eth0",
    )
    server_nat = LinuxServerNatConfig(
        tun_name="x0vpn0",
        uplink_interface="eth0",
        client_cidr="10.77.0.0/24",
        vpn_listeners=(
            LinuxServerVpnListener(transport="camouflage", port=443),
            LinuxServerVpnListener(transport="tcp", port=8443),
        ),
    )
    snapshot = LinuxAppliedStateSnapshot(
        interfaces=("lo", "eth0", "x0vpn0"),
        routes=(
            "default dev x0vpn0",
            "203.0.113.10/32 via 192.0.2.1 dev eth0",
        ),
        dns=("Link 7 (x0vpn0) DNS Servers: 9.9.9.9 DNS Domain: ~.",),
        nft_ruleset="""
table inet x0vpn {
  chain output {
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    oifname "x0vpn0" accept
    ip daddr 203.0.113.10 tcp dport 443 accept
  }
}
table inet x0vpn_filter {
  chain input {
    type filter hook input priority 0; policy accept;
    iifname "eth0" tcp dport 443 accept
    iifname "eth0" tcp dport 8443 accept
  }
}
table ip x0vpn_nat {
  chain postrouting {
    type nat hook postrouting priority 100; policy accept;
    ip saddr 10.77.0.0/24 oifname "eth0" masquerade
  }
}
""",
        sysctls={"net.ipv4.ip_forward": "1"},
        captured_at=NOW,
    )
    evidence = evaluate_linux_applied_state(
        client_network=client_network,
        server_nat=server_nat,
        client_tun=LinuxTunConfig(name="x0vpn0"),
        server_tun=LinuxTunConfig(name="x0vpn0"),
        snapshot=snapshot,
    )

    assert isinstance(evidence, LinuxAppliedStateEvidence)
    assert evidence.passed is True
    assert evidence.reasons == ()
    assert "client_tun_present" in evidence.controls
    assert "full_tunnel_route_observed" in evidence.controls
    assert "tun_dns_servers_observed" in evidence.controls
    assert "kill_switch_output_drop_policy_observed" in evidence.controls
    assert "server_masquerade_observed" in evidence.controls
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)
    assert "203.0.113.10" not in encoded
    assert "192.0.2.1" not in encoded
    assert "9.9.9.9" not in encoded
    assert len(evidence.evidence_hash()) == 64
    assert_privacy_safe(evidence.to_json_dict())


def test_linux_applied_state_fails_closed_for_missing_dns_killswitch_and_nat() -> None:
    client_network = LinuxNetworkPolicyConfig(
        remote_endpoints=(RemoteEndpoint(host="203.0.113.10", port=443),),
        dns_servers=("9.9.9.9",),
        underlay_gateway="192.0.2.1",
        underlay_interface="eth0",
    )
    snapshot = LinuxAppliedStateSnapshot(
        interfaces=("lo", "eth0"),
        routes=(),
        dns=(),
        nft_ruleset="table inet other { chain output { policy accept; } }",
        sysctls={"net.ipv4.ip_forward": "0"},
        captured_at=NOW,
    )
    evidence = evaluate_linux_applied_state(
        client_network=client_network,
        server_nat=LinuxServerNatConfig(),
        client_tun=LinuxTunConfig(name="x0vpn0"),
        server_tun=LinuxTunConfig(name="x0vpn0"),
        snapshot=snapshot,
    )

    assert evidence.passed is False
    assert "client_tun_missing" in evidence.reasons
    assert "full_tunnel_route_missing" in evidence.reasons
    assert "tun_dns_servers_missing" in evidence.reasons
    assert "kill_switch_output_drop_policy_missing" in evidence.reasons
    assert "underlay_endpoint_route_missing" in evidence.reasons
    assert "server_ipv4_forwarding_missing" in evidence.reasons
    assert "server_masquerade_missing" in evidence.reasons


def test_collect_linux_applied_state_snapshot_reads_state_privately() -> None:
    outputs = {
        ("ip", "-o", "link", "show"): (
            "1: lo: <LOOPBACK> mtu 65536\n"
            "2: eth0@if3: <BROADCAST> mtu 1500\n"
            "3: x0vpn0: <POINTOPOINT> mtu 1400\n"
        ),
        ("ip", "route", "show", "table", "main"): (
            "default dev x0vpn0\n"
            "203.0.113.10/32 via 192.0.2.1 dev eth0\n"
        ),
        ("ip", "-6", "route", "show", "table", "main"): "",
        ("resolvectl", "status"): (
            "Link 7 (x0vpn0)\n"
            "DNS Servers: 9.9.9.9\n"
            "DNS Domain: ~.\n"
        ),
        ("nft", "list", "ruleset"): "table inet x0vpn { chain output { policy drop; } }",
        ("sysctl", "-n", "net.ipv4.ip_forward"): "1\n",
    }
    seen: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...]) -> str:
        seen.append(command)
        return outputs[command]

    snapshot = collect_linux_applied_state_snapshot(command_runner=runner, now=NOW)

    assert snapshot.interfaces == ("lo", "eth0", "x0vpn0")
    assert snapshot.routes == (
        "default dev x0vpn0",
        "203.0.113.10/32 via 192.0.2.1 dev eth0",
    )
    assert snapshot.sysctls == {"net.ipv4.ip_forward": "1"}
    assert seen == [
        ("ip", "-o", "link", "show"),
        ("ip", "route", "show", "table", "main"),
        ("ip", "-6", "route", "show", "table", "main"),
        ("resolvectl", "status"),
        ("nft", "list", "ruleset"),
        ("sysctl", "-n", "net.ipv4.ip_forward"),
    ]
    encoded = json.dumps(snapshot.to_json_dict(), sort_keys=True)
    assert "203.0.113.10" not in encoded
    assert "192.0.2.1" not in encoded
    assert "9.9.9.9" not in encoded
    assert len(snapshot.state_hash()) == 64
    assert_privacy_safe(snapshot.to_json_dict())


def test_linux_post_apply_validator_collects_and_evaluates_snapshot() -> None:
    config = FirstPartyVpnDeploymentConfig(
        client_network=LinuxNetworkPolicyConfig(dns_servers=("9.9.9.9",)),
        server_nat=LinuxServerNatConfig(vpn_transport="udp", vpn_listen_port=443),
        required_dataplane_transports=(),
    )
    outputs = {
        ("ip", "-o", "link", "show"): "1: lo: <LOOPBACK>\n2: eth0: <UP>\n3: x0vpn0: <UP>\n",
        ("ip", "route", "show", "table", "main"): "default dev x0vpn0\n",
        ("ip", "-6", "route", "show", "table", "main"): "",
        ("resolvectl", "status"): "Link 7 (x0vpn0) DNS Servers: 9.9.9.9 DNS Domain: ~.\n",
        ("nft", "list", "ruleset"): """
table inet x0vpn {
  chain output {
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    oifname "x0vpn0" accept
  }
}
table inet x0vpn_filter {
  chain input {
    type filter hook input priority 0; policy accept;
    iifname "eth0" udp dport 443 accept
  }
}
table ip x0vpn_nat {
  chain postrouting {
    type nat hook postrouting priority 100; policy accept;
    ip saddr 10.77.0.0/24 oifname "eth0" masquerade
  }
}
""",
        ("sysctl", "-n", "net.ipv4.ip_forward"): "1\n",
    }
    validator = build_linux_post_apply_validator(
        config=config,
        command_runner=lambda command: outputs[command],
        now=NOW,
    )

    evidence = validator(None)  # type: ignore[arg-type]

    assert evidence.passed is True
    assert "full_tunnel_route_observed" in evidence.controls
    assert "server_vpn_listener_observed" in evidence.controls
    assert len(evidence.evidence_hash()) == 64
    assert_privacy_safe(evidence.to_json_dict())


def test_linux_network_policy_blocks_mutation_by_default() -> None:
    commands: list[tuple[str, ...]] = []
    planner = LinuxNetworkPolicyPlanner(
        config=LinuxNetworkPolicyConfig(route_all_traffic=False),
        command_runner=commands.append,
    )

    with pytest.raises(LinuxNetworkPolicyMutationBlocked):
        planner.apply()
    with pytest.raises(LinuxNetworkPolicyMutationBlocked):
        planner.rollback()
    assert commands == []


def test_linux_network_policy_applies_only_when_explicitly_allowed() -> None:
    commands: list[tuple[str, ...]] = []
    planner = LinuxNetworkPolicyPlanner(
        config=LinuxNetworkPolicyConfig(
            route_all_traffic=False,
            enable_kill_switch=True,
            allow_os_mutation=True,
        ),
        command_runner=commands.append,
    )

    planner.apply()
    planner.rollback()

    assert commands == [
        ("nft", "add", "table", "inet", "x0vpn"),
        (
            "nft",
            "add",
            "chain",
            "inet",
            "x0vpn",
            "output",
            "{",
            "type",
            "filter",
            "hook",
            "output",
            "priority",
            "0",
            ";",
            "policy",
            "drop",
            ";",
            "}",
        ),
        ("nft", "add", "rule", "inet", "x0vpn", "output", "oifname", "lo", "accept"),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn",
            "output",
            "oifname",
            "x0vpn0",
            "accept",
        ),
        ("nft", "delete", "table", "inet", "x0vpn"),
    ]


def test_linux_network_policy_rejects_unsafe_or_looping_config() -> None:
    with pytest.raises(ValueError):
        RemoteEndpoint(host="203.0.113.10", port=0)
    with pytest.raises(ValueError):
        LinuxNetworkPolicyConfig(tun_name="x0/vpn0")
    with pytest.raises(ValueError):
        LinuxNetworkPolicyConfig(dns_servers=("not-an-ip",))
    with pytest.raises(ValueError):
        LinuxNetworkPolicyConfig(
            remote_endpoints=(RemoteEndpoint(host="203.0.113.10", port=443),)
        )


def test_linux_server_nat_plans_forwarding_masquerade_and_listener() -> None:
    planner = LinuxServerNatPlanner(
        config=LinuxServerNatConfig(
            tun_name="x0vpn0",
            uplink_interface="eth0",
            client_cidr="10.77.0.0/24",
            vpn_listen_port=443,
            vpn_transport="udp",
        )
    )

    assert planner.planned_commands() == (
        ("sysctl", "-w", "net.ipv4.ip_forward=1"),
        ("nft", "add", "table", "inet", "x0vpn_filter"),
        (
            "nft",
            "add",
            "chain",
            "inet",
            "x0vpn_filter",
            "forward",
            "{",
            "type",
            "filter",
            "hook",
            "forward",
            "priority",
            "0",
            ";",
            "policy",
            "drop",
            ";",
            "}",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn_filter",
            "forward",
            "iifname",
            "x0vpn0",
            "oifname",
            "eth0",
            "ip",
            "saddr",
            "10.77.0.0/24",
            "accept",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn_filter",
            "forward",
            "iifname",
            "eth0",
            "oifname",
            "x0vpn0",
            "ct",
            "state",
            "established,related",
            "accept",
        ),
        (
            "nft",
            "add",
            "chain",
            "inet",
            "x0vpn_filter",
            "input",
            "{",
            "type",
            "filter",
            "hook",
            "input",
            "priority",
            "0",
            ";",
            "policy",
            "accept",
            ";",
            "}",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn_filter",
            "input",
            "iifname",
            "eth0",
            "udp",
            "dport",
            "443",
            "accept",
        ),
        ("nft", "add", "table", "ip", "x0vpn_nat"),
        (
            "nft",
            "add",
            "chain",
            "ip",
            "x0vpn_nat",
            "postrouting",
            "{",
            "type",
            "nat",
            "hook",
            "postrouting",
            "priority",
            "100",
            ";",
            "policy",
            "accept",
            ";",
            "}",
        ),
        (
            "nft",
            "add",
            "rule",
            "ip",
            "x0vpn_nat",
            "postrouting",
            "ip",
            "saddr",
            "10.77.0.0/24",
            "oifname",
            "eth0",
            "masquerade",
        ),
    )
    assert planner.rollback_commands() == (
        ("nft", "delete", "table", "ip", "x0vpn_nat"),
        ("nft", "delete", "table", "inet", "x0vpn_filter"),
    )


def test_linux_server_nat_plans_camouflage_listener_as_tcp_rule() -> None:
    config = LinuxServerNatConfig(
        tun_name="x0vpn0",
        uplink_interface="eth0",
        client_cidr="10.77.0.0/24",
        vpn_listen_port=443,
        vpn_transport="camouflage",
    )
    planner = LinuxServerNatPlanner(config=config)

    commands = planner.planned_commands()

    assert config.vpn_transport == "camouflage"
    assert config.listener_firewall_protocol == "tcp"
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "tcp",
        "dport",
        "443",
        "accept",
    ) in commands
    assert not any("camouflage" in command for command in commands)


def test_linux_server_nat_can_add_iptables_compat_forwarding() -> None:
    planner = LinuxServerNatPlanner(
        config=LinuxServerNatConfig(
            tun_name="x0vpn0",
            uplink_interface="eth0",
            client_cidr="10.77.0.0/24",
            enable_iptables_compat=True,
        )
    )

    assert (
        "iptables",
        "-I",
        "FORWARD",
        "1",
        "-i",
        "x0vpn0",
        "-o",
        "eth0",
        "-s",
        "10.77.0.0/24",
        "-j",
        "ACCEPT",
    ) in planner.planned_commands()
    assert (
        "iptables",
        "-t",
        "nat",
        "-D",
        "POSTROUTING",
        "-s",
        "10.77.0.0/24",
        "-o",
        "eth0",
        "-j",
        "MASQUERADE",
    ) in planner.rollback_commands()


def test_linux_server_nat_plans_multiple_firstparty_listeners() -> None:
    config = LinuxServerNatConfig(
        tun_name="x0vpn0",
        uplink_interface="eth0",
        client_cidr="10.77.0.0/24",
        vpn_listeners=(
            LinuxServerVpnListener(transport="udp", port=443),
            LinuxServerVpnListener(transport="camouflage", port=443),
            LinuxServerVpnListener(transport="tcp", port=8443),
        ),
    )
    planner = LinuxServerNatPlanner(config=config)

    commands = planner.planned_commands()

    assert config.listener_transports == frozenset({"udp", "tcp", "camouflage"})
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "udp",
        "dport",
        "443",
        "accept",
    ) in commands
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "tcp",
        "dport",
        "443",
        "accept",
    ) in commands
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "tcp",
        "dport",
        "8443",
        "accept",
    ) in commands


def test_linux_server_nat_blocks_mutation_by_default() -> None:
    commands: list[tuple[str, ...]] = []
    planner = LinuxServerNatPlanner(
        config=LinuxServerNatConfig(),
        command_runner=commands.append,
    )

    with pytest.raises(LinuxNetworkPolicyMutationBlocked):
        planner.apply()
    with pytest.raises(LinuxNetworkPolicyMutationBlocked):
        planner.rollback()
    assert commands == []


def test_linux_server_nat_applies_only_when_explicitly_allowed() -> None:
    commands: list[tuple[str, ...]] = []
    planner = LinuxServerNatPlanner(
        config=LinuxServerNatConfig(
            enable_ipv4_forwarding=False,
            enable_masquerade=False,
            allow_vpn_listener=False,
            allow_os_mutation=True,
        ),
        command_runner=commands.append,
    )

    planner.apply()
    planner.rollback()

    assert commands == [
        ("nft", "add", "table", "inet", "x0vpn_filter"),
        (
            "nft",
            "add",
            "chain",
            "inet",
            "x0vpn_filter",
            "forward",
            "{",
            "type",
            "filter",
            "hook",
            "forward",
            "priority",
            "0",
            ";",
            "policy",
            "drop",
            ";",
            "}",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn_filter",
            "forward",
            "iifname",
            "x0vpn0",
            "oifname",
            "eth0",
            "ip",
            "saddr",
            "10.77.0.0/24",
            "accept",
        ),
        (
            "nft",
            "add",
            "rule",
            "inet",
            "x0vpn_filter",
            "forward",
            "iifname",
            "eth0",
            "oifname",
            "x0vpn0",
            "ct",
            "state",
            "established,related",
            "accept",
        ),
        ("nft", "delete", "table", "ip", "x0vpn_nat"),
        ("nft", "delete", "table", "inet", "x0vpn_filter"),
    ]


def test_linux_server_nat_rejects_unsafe_config() -> None:
    with pytest.raises(ValueError):
        LinuxServerNatConfig(tun_name="x0/vpn0")
    with pytest.raises(ValueError):
        LinuxServerNatConfig(client_cidr="fd00::/64")
    with pytest.raises(ValueError):
        LinuxServerNatConfig(vpn_listen_port=0)
    with pytest.raises(ValueError):
        LinuxServerNatConfig(vpn_transport="icmp")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LinuxServerVpnListener(transport="icmp", port=443)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LinuxServerVpnListener(transport="tcp", port=0)
    with pytest.raises(ValueError):
        LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=443),
                LinuxServerVpnListener(transport="camouflage", port=443),
            ),
        )


def test_firstparty_deployment_rejects_required_transport_without_server_listener() -> None:
    with pytest.raises(
        FirstPartyVpnDeploymentError,
        match="required dataplane transport is not exposed by server NAT",
    ):
        FirstPartyVpnDeploymentConfig(
            server_nat=LinuxServerNatConfig(vpn_transport="udp", vpn_listen_port=443),
            required_dataplane_transports=(("restricted-work-wifi", "camouflage"),),
        )
    with pytest.raises(FirstPartyVpnDeploymentError, match="source audit root hash"):
        FirstPartyVpnDeploymentConfig(source_audit_root_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="rekey rollback plan hash"):
        FirstPartyVpnDeploymentConfig(rekey_rollback_plan_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="zero trust policy hash"):
        FirstPartyVpnDeploymentConfig(zero_trust_policy_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="policy snapshot hash"):
        FirstPartyVpnDeploymentConfig(policy_snapshot_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="external policy source hash"):
        FirstPartyVpnDeploymentConfig(external_policy_source_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="dataplane probe matrix hash"):
        FirstPartyVpnDeploymentConfig(dataplane_probe_matrix_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="Linux host fingerprint"):
        FirstPartyVpnDeploymentConfig(linux_host_fingerprint="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="PQC manifest hash"):
        FirstPartyVpnDeploymentConfig(pqc_manifest_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="identity signer manifest hash"):
        FirstPartyVpnDeploymentConfig(identity_signer_manifest_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="apply plan hash"):
        FirstPartyVpnDeploymentConfig(apply_plan_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="rollback plan hash"):
        FirstPartyVpnDeploymentConfig(rollback_plan_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="leak protection plan hash"):
        FirstPartyVpnDeploymentConfig(leak_protection_plan_hash="not-a-sha256")
    with pytest.raises(FirstPartyVpnDeploymentError, match="rollout gate hash"):
        FirstPartyVpnDeploymentConfig(rollout_gate_hash="not-a-sha256")


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_packet_builds_client_server_readiness(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    facts = LinuxHostFacts(
        os_name="Linux",
        kernel_release="6.8.0-x0vpn",
        effective_uid=0,
        has_net_admin=True,
    )
    path_exists = lambda _path: True
    binary_exists = lambda _binary: True
    config = FirstPartyVpnDeploymentConfig(
        target="nl",
        client_tun=LinuxTunConfig(
            name="x0vpn0",
            address="10.77.0.2/32",
            peer="10.77.0.1",
        ),
        client_network=LinuxNetworkPolicyConfig(
            tun_name="x0vpn0",
            remote_endpoints=(RemoteEndpoint(host="203.0.113.10", port=443, transport="tcp"),),
            dns_servers=("9.9.9.9",),
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
        ),
        server_tun=LinuxTunConfig(name="x0vpn0", address="10.77.0.1/24"),
        server_nat=LinuxServerNatConfig(
            tun_name="x0vpn0",
            uplink_interface="eth0",
            vpn_listeners=(
                LinuxServerVpnListener(transport="camouflage", port=443),
                LinuxServerVpnListener(transport="tcp", port=8443),
            ),
        ),
        expected_test_count=99,
        dataplane_probe_matrix_hash=evidence.dataplane_validation.probe_matrix_hash(),
        pqc_manifest_hash=evidence.pqc_manifest.manifest_hash(),
        identity_signer_manifest_hash=evidence.identity_signer_manifest.manifest_hash(),
        external_policy_source_hash=evidence.external_policy_source.evidence_hash(),
        policy_snapshot_hash=evidence.policy_snapshot_hash,
        zero_trust_policy_hash=evidence.zero_trust_policy.policy_hash,
        source_audit_root_hash=evidence.source_audit.root_hash,
        source_audit_tree_hash=evidence.source_audit.source_tree_hash,
        rekey_rollback_plan_hash=evidence.rekey_policy.rollback_plan_hash,
    )
    plan_hashes = evaluate_firstparty_vpn_deployment_plan_hashes(config)
    config = replace(
        config,
        linux_host_fingerprint=evaluate_firstparty_vpn_deployment_host_fingerprint(
            config=config,
            facts=facts,
            path_exists=path_exists,
            binary_exists=binary_exists,
        ),
        apply_plan_hash=plan_hashes.apply_plan_hash,
        rollback_plan_hash=plan_hashes.rollback_plan_hash,
        leak_protection_plan_hash=plan_hashes.leak_protection_plan_hash,
    )
    rollout_decision = evaluate_firstparty_vpn_deployment_rollout_gate(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )
    config = replace(config, rollout_gate_hash=rollout_decision.decision_hash())
    packet = build_firstparty_vpn_deployment_packet(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )

    assert isinstance(packet, FirstPartyVpnDeploymentPacket)
    assert packet.linux_preflight.passed is True
    assert packet.linux_preflight.host_fingerprint == config.linux_host_fingerprint
    assert packet.linux_preflight.apply_plan.evidence_hash() == plan_hashes.apply_plan_hash
    assert (
        packet.linux_preflight.rollback_plan.evidence_hash()
        == plan_hashes.rollback_plan_hash
    )
    assert (
        packet.leak_protection.command_plan.evidence_hash()
        == plan_hashes.leak_protection_plan_hash
    )
    assert packet.rollout_decision.allowed is True
    assert packet.rollout_decision.evidence_hash == rollout_decision.evidence_hash
    assert packet.readiness_decision.allowed is True
    assert packet.readiness_decision.reasons == ()
    assert ("ip", "link", "set", "dev", "x0vpn0", "up") in packet.client_apply_commands
    assert ("sysctl", "-w", "net.ipv4.ip_forward=1") in packet.server_apply_commands
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "tcp",
        "dport",
        "443",
        "accept",
    ) in packet.server_apply_commands
    assert (
        "nft",
        "add",
        "rule",
        "inet",
        "x0vpn_filter",
        "input",
        "iifname",
        "eth0",
        "tcp",
        "dport",
        "8443",
        "accept",
    ) in packet.server_apply_commands
    assert ("ip", "link", "delete", "x0vpn0") in packet.rollback_commands

    payload = packet.to_json_dict()
    encoded = json.dumps(payload, sort_keys=True)
    assert "203.0.113.10" not in encoded
    assert "192.0.2.1" not in encoded
    assert packet.rollout_plan.apply_commands == packet.apply_commands
    assert packet.rollout_plan.rollback_commands == packet.rollback_commands
    assert_privacy_safe(payload)


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_requires_configured_rollout_gate_hash(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    config = FirstPartyVpnDeploymentConfig(
        expected_test_count=99,
        dataplane_probe_matrix_hash=evidence.dataplane_validation.probe_matrix_hash(),
        pqc_manifest_hash=evidence.pqc_manifest.manifest_hash(),
        identity_signer_manifest_hash=evidence.identity_signer_manifest.manifest_hash(),
        external_policy_source_hash=evidence.external_policy_source.evidence_hash(),
        policy_snapshot_hash=evidence.policy_snapshot_hash,
        zero_trust_policy_hash=evidence.zero_trust_policy.policy_hash,
        source_audit_root_hash=evidence.source_audit.root_hash,
        source_audit_tree_hash=evidence.source_audit.source_tree_hash,
        rekey_rollback_plan_hash=evidence.rekey_policy.rollback_plan_hash,
    )
    plan_hashes = evaluate_firstparty_vpn_deployment_plan_hashes(config)
    facts = LinuxHostFacts(
        os_name="Linux",
        kernel_release="6.8.0-x0vpn",
        effective_uid=0,
        has_net_admin=True,
    )
    path_exists = lambda _path: True
    binary_exists = lambda _binary: True
    config = replace(
        config,
        linux_host_fingerprint=evaluate_firstparty_vpn_deployment_host_fingerprint(
            config=config,
            facts=facts,
            path_exists=path_exists,
            binary_exists=binary_exists,
        ),
        apply_plan_hash=plan_hashes.apply_plan_hash,
        rollback_plan_hash=plan_hashes.rollback_plan_hash,
        leak_protection_plan_hash=plan_hashes.leak_protection_plan_hash,
    )

    missing = build_firstparty_vpn_deployment_packet(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )
    mismatch = build_firstparty_vpn_deployment_packet(
        config=replace(config, rollout_gate_hash="f" * 64),
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=NOW,
    )

    assert missing.rollout_decision.allowed is True
    assert missing.readiness_decision.allowed is False
    assert (
        "rollout_gate_hash_requirement_missing"
        in missing.readiness_decision.reasons
    )
    assert mismatch.rollout_decision.allowed is True
    assert mismatch.readiness_decision.allowed is False
    assert "rollout_gate_hash_mismatch" in mismatch.readiness_decision.reasons
    assert_privacy_safe(missing.to_json_dict())
    assert_privacy_safe(mismatch.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_rejects_source_audit_binding_mismatch(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(
            expected_test_count=99,
            source_audit_root_hash="f" * 64,
            source_audit_tree_hash=evidence.source_audit.source_tree_hash,
        ),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=evidence,
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )

    assert packet.rollout_decision.allowed is True
    assert packet.readiness_decision.allowed is False
    assert "firstparty_source_audit_root_mismatch" in packet.readiness_decision.reasons
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_rejects_mismatched_tun_probe_matrix(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    paths_and_transports = (
        ("lan", "udp"),
        ("vps", "tcp"),
        ("mobile", "camouflage"),
        ("restricted-work-wifi", "camouflage"),
    )
    mismatched_probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"deploy-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"deploy-mismatched-tun-remote-{path_label}",
        )
        for path_label, transport in paths_and_transports
    )
    mismatched_tun = TunDataplaneValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=mismatched_probes,
            required_path_labels=frozenset(path for path, _transport in paths_and_transports),
            min_successful_probes=len(mismatched_probes),
        ),
        results=tuple(_successful_tun_probe_result(probe) for probe in mismatched_probes),
        captured_at=NOW,
    )
    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(expected_test_count=99),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=replace(evidence, tun_dataplane_validation=mismatched_tun),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )
    encoded = json.dumps(packet.to_json_dict(), sort_keys=True)

    assert packet.rollout_decision.allowed is True
    assert packet.readiness_decision.allowed is False
    assert "dataplane_tun_probe_matrix_mismatch" in packet.readiness_decision.reasons
    assert evidence.dataplane_validation.probe_matrix_hash() != (
        mismatched_tun.probe_matrix_hash()
    )
    assert "deploy-mismatched-tun-remote" not in encoded
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_rejects_mismatched_mtu_probe_matrix(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    paths_and_transports = (
        ("lan", "udp"),
        ("vps", "tcp"),
        ("mobile", "camouflage"),
        ("restricted-work-wifi", "camouflage"),
    )
    mismatched_probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"deploy-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"deploy-mismatched-mtu-remote-{path_label}",
        )
        for path_label, transport in paths_and_transports
    )
    mismatched_mtu = MtuValidationEvidence.from_results(
        plan=DataplaneValidationPlan(
            probes=mismatched_probes,
            required_path_labels=frozenset(path for path, _transport in paths_and_transports),
            min_successful_probes=len(mismatched_probes),
        ),
        results=tuple(_successful_mtu_probe_result(probe) for probe in mismatched_probes),
        captured_at=NOW,
    )
    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(expected_test_count=99),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=replace(evidence, mtu_validation=mismatched_mtu),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )
    encoded = json.dumps(packet.to_json_dict(), sort_keys=True)

    assert packet.rollout_decision.allowed is True
    assert packet.readiness_decision.allowed is False
    assert "dataplane_mtu_probe_matrix_mismatch" in packet.readiness_decision.reasons
    assert evidence.dataplane_validation.probe_matrix_hash() != (
        mismatched_mtu.probe_matrix_hash()
    )
    assert "deploy-mismatched-mtu-remote" not in encoded
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_requires_restricted_wifi_camouflage_transport(
    tmp_path: Path,
) -> None:
    evidence = await complete_deployment_evidence(tmp_path)
    probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"deploy-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"deploy-remote-{path_label}",
        )
        for path_label, transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "tcp"),
        )
    )
    plan = DataplaneValidationPlan(
        probes=probes,
        required_path_labels=frozenset(path for path, _transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "tcp"),
        )),
        min_successful_probes=len(probes),
    )
    dataplane = await evaluate_dataplane_validation(
        plan=plan,
        runner=_successful_probe_result,
        captured_at=NOW,
    )
    tun_dataplane = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_tun_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )
    mtu_validation = MtuValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_mtu_probe_result(probe) for probe in probes),
        captured_at=NOW,
    )

    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(expected_test_count=99),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=replace(
            evidence,
            dataplane_validation=dataplane,
            tun_dataplane_validation=tun_dataplane,
            mtu_validation=mtu_validation,
        ),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )

    assert packet.rollout_decision.allowed is True
    assert packet.readiness_decision.allowed is False
    assert (
        "dataplane_required_transport_missing:restricted-work-wifi:camouflage"
        in packet.readiness_decision.reasons
    )
    assert (
        "tun_dataplane_required_transport_missing:restricted-work-wifi:camouflage"
        in packet.readiness_decision.reasons
    )
    assert (
        "mtu_required_transport_missing:restricted-work-wifi:camouflage"
        in packet.readiness_decision.reasons
    )
    assert "dataplane_tun_probe_matrix_mismatch" not in packet.readiness_decision.reasons
    assert "dataplane_mtu_probe_matrix_mismatch" not in packet.readiness_decision.reasons
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_rejects_stale_validation_evidence(
    tmp_path: Path,
) -> None:
    stale_at = NOW - 7200
    evidence = await complete_deployment_evidence(tmp_path)
    probes = tuple(
        DataplaneProbeSpec(
            probe_id=f"deploy-{path_label}",
            path_label=path_label,
            transport=transport,
            remote_ref=f"deploy-remote-{path_label}",
        )
        for path_label, transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "camouflage"),
        )
    )
    plan = DataplaneValidationPlan(
        probes=probes,
        required_path_labels=frozenset(path for path, _transport in (
            ("lan", "udp"),
            ("vps", "tcp"),
            ("mobile", "camouflage"),
            ("restricted-work-wifi", "camouflage"),
        )),
        min_successful_probes=len(probes),
    )
    stale_dataplane = await evaluate_dataplane_validation(
        plan=plan,
        runner=_successful_probe_result,
        captured_at=stale_at,
    )
    stale_tun = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_tun_probe_result(probe) for probe in probes),
        captured_at=stale_at,
    )
    stale_mtu = MtuValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_mtu_probe_result(probe) for probe in probes),
        captured_at=stale_at,
    )

    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(expected_test_count=99),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=replace(
            evidence,
            dataplane_validation=stale_dataplane,
            tun_dataplane_validation=stale_tun,
            mtu_validation=stale_mtu,
        ),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )

    assert packet.rollout_decision.allowed is True
    assert packet.readiness_decision.allowed is False
    assert "dataplane_validation_stale" in packet.readiness_decision.reasons
    assert "tun_dataplane_validation_stale" in packet.readiness_decision.reasons
    assert "mtu_validation_stale" in packet.readiness_decision.reasons
    assert "dataplane_tun_probe_matrix_mismatch" not in packet.readiness_decision.reasons
    assert "dataplane_mtu_probe_matrix_mismatch" not in packet.readiness_decision.reasons
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_packet_fails_closed_before_os_mutation(
    tmp_path: Path,
) -> None:
    packet = build_firstparty_vpn_deployment_packet(
        config=FirstPartyVpnDeploymentConfig(expected_test_count=99),
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=1000,
            has_net_admin=False,
        ),
        evidence=await complete_deployment_evidence(tmp_path, approval=False),
        path_exists=lambda _path: False,
        binary_exists=lambda _binary: False,
        now=NOW,
    )

    assert packet.linux_preflight.passed is False
    assert packet.rollout_decision.allowed is False
    assert packet.readiness_decision.allowed is False
    assert "linux_preflight_failed" in packet.rollout_decision.reasons
    assert "operator_approval_missing" in packet.rollout_decision.reasons
    assert "linux_preflight_failed" in packet.readiness_decision.reasons
    assert "rollout_gate_failed" in packet.readiness_decision.reasons
    assert packet.client_apply_commands
    assert packet.server_apply_commands
    assert_privacy_safe(packet.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_applies_only_after_explicit_gate(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    blocked = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
    )

    with pytest.raises(FirstPartyVpnDeploymentMutationBlocked):
        blocked.apply()

    missing_validator = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
    )
    with pytest.raises(
        FirstPartyVpnDeploymentMutationBlocked,
        match="post-apply validation",
    ):
        missing_validator.apply()
    assert executed == []

    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    )
    evidence = executor.apply()

    assert isinstance(evidence, FirstPartyVpnDeploymentExecutionEvidence)
    assert evidence.succeeded is True
    assert evidence.allowed is True
    assert evidence.executed_count == len(packet.apply_commands)
    assert evidence.rollback_attempted is False
    assert evidence.post_apply_validation_attempted is True
    assert evidence.post_apply_hash == successful_post_apply_evidence().evidence_hash()
    assert evidence.tun_activation_attempted is True
    assert evidence.tun_activation_count == 1
    assert evidence.dataplane_activation_attempted is True
    assert evidence.dataplane_activation_count == 1
    assert executed == list(packet.apply_commands)
    assert len(evidence.evidence_hash()) == 64
    assert_privacy_safe(evidence.to_json_dict())

    missing_tun = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
    )
    with pytest.raises(
        FirstPartyVpnDeploymentMutationBlocked,
        match="TUN activation",
    ):
        missing_tun.apply()
    assert executed == list(packet.apply_commands)

    missing_dataplane = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
    )
    with pytest.raises(
        FirstPartyVpnDeploymentMutationBlocked,
        match="dataplane activation",
    ):
        missing_dataplane.apply()
    assert executed == list(packet.apply_commands)


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_fails_closed_on_zero_tun_activation(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=lambda _packet: 0,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.reasons == ("tun_activation_failed",)
    assert evidence.failure_reason == "FirstPartyVpnDeploymentError"
    assert evidence.executed_count == 0
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is False
    assert executed == list(packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rejects_count_only_tun_activation(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=lambda _packet: 1,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.reasons == ("tun_activation_failed",)
    assert evidence.failure_reason == "FirstPartyVpnDeploymentError"
    assert evidence.executed_count == 0
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is False
    assert executed == list(packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rejects_uncloseable_tun_resource(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    class UncloseableResource:
        pass

    def activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        return FirstPartyVpnTunActivationResult(
            count=1,
            resources=(UncloseableResource(),),  # type: ignore[arg-type]
        )

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=activator,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.reasons == ("tun_activation_failed",)
    assert evidence.failure_reason == "FirstPartyVpnDeploymentError"
    assert evidence.executed_count == 0
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is False
    assert executed == list(packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_activates_tun_before_apply(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    events: list[tuple[str, tuple[str, ...] | str]] = []

    class Resource:
        def close(self) -> None:
            return None

    def activator(
        received: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        assert received is packet
        events.append(("activate_tun", received.target))
        return FirstPartyVpnTunActivationResult(count=1, resources=(Resource(),))

    def dataplane_activator(
        received: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        assert received is packet
        events.append(("activate_dataplane", received.target))
        return FirstPartyVpnDataplaneActivationResult(
            count=1,
            resources=(InMemoryDataplaneActivationResource(),),
        )

    def runner(command: tuple[str, ...]) -> None:
        events.append(("command", command))

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=runner,
        allow_os_mutation=True,
        tun_activator=activator,
        dataplane_activator=dataplane_activator,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is True
    assert evidence.tun_activation_attempted is True
    assert evidence.tun_activation_count == 1
    assert evidence.dataplane_activation_attempted is True
    assert evidence.dataplane_activation_count == 1
    assert events[0] == ("activate_tun", "nl")
    assert events[1] == ("activate_dataplane", "nl")
    assert [event[1] for event in events[2:]] == list(packet.apply_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rolls_back_on_tun_activation_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    def activator(_packet: FirstPartyVpnDeploymentPacket) -> int:
        raise RuntimeError("simulated tun activation failure")

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=activator,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "RuntimeError"
    assert evidence.reasons == ("tun_activation_failed",)
    assert evidence.executed_count == 0
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is False
    assert evidence.tun_activation_attempted is True
    assert evidence.tun_activation_count == 0
    assert executed == list(packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rolls_back_on_dataplane_activation_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    closed: list[str] = []

    class TunResource:
        def close(self) -> None:
            closed.append("tun")

    def dataplane_activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        raise RuntimeError("simulated dataplane activation failure")

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=lambda _packet: FirstPartyVpnTunActivationResult(
            count=1,
            resources=(TunResource(),),
        ),
        dataplane_activator=dataplane_activator,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "RuntimeError"
    assert evidence.reasons == ("dataplane_activation_failed",)
    assert evidence.executed_count == 0
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.tun_activation_attempted is True
    assert evidence.tun_activation_count == 1
    assert evidence.dataplane_activation_attempted is True
    assert evidence.dataplane_activation_count == 0
    assert closed == ["tun"]
    assert executed == list(packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


def test_build_linux_tun_activator_opens_selected_scope_with_mutation_enabled() -> None:
    opened: list[LinuxTunConfig] = []
    closed: list[str] = []
    config = FirstPartyVpnDeploymentConfig(
        client_tun=LinuxTunConfig(name="x0vpn-client", address="10.77.0.2/32"),
        server_tun=LinuxTunConfig(name="x0vpn-server", address="10.77.0.1/24"),
    )

    class FakeTunDevice:
        def __init__(self, tun_config: LinuxTunConfig) -> None:
            self.tun_config = tun_config

        def open_interface(self) -> None:
            opened.append(self.tun_config)

        def close(self) -> None:
            closed.append(self.tun_config.name)

    activator = build_linux_tun_activator(
        config=config,
        scope="server",
        device_factory=FakeTunDevice,
    )
    result = activator(None)  # type: ignore[arg-type]

    assert isinstance(result, FirstPartyVpnTunActivationResult)
    assert result.count == 1
    assert [tun.name for tun in opened] == ["x0vpn-server"]
    assert opened[0].allow_os_mutation is True
    assert len(result.resources) == 1
    result.resources[0].close()
    assert closed == ["x0vpn-server"]


def test_build_linux_tun_activator_closes_partial_resources_on_open_failure() -> None:
    opened: list[str] = []
    closed: list[str] = []
    config = FirstPartyVpnDeploymentConfig(
        client_tun=LinuxTunConfig(name="x0vpn-client"),
        server_tun=LinuxTunConfig(name="x0vpn-server"),
    )

    class FakeTunDevice:
        def __init__(self, tun_config: LinuxTunConfig) -> None:
            self.tun_config = tun_config

        def open_interface(self) -> None:
            if self.tun_config.name == "x0vpn-server":
                raise RuntimeError("simulated open failure")
            opened.append(self.tun_config.name)

        def close(self) -> None:
            closed.append(self.tun_config.name)

    activator = build_linux_tun_activator(
        config=config,
        scope="both",
        device_factory=FakeTunDevice,
    )

    with pytest.raises(RuntimeError, match="simulated open failure"):
        activator(None)  # type: ignore[arg-type]

    assert opened == ["x0vpn-client"]
    assert closed == ["x0vpn-client"]


@pytest.mark.asyncio
async def test_compose_firstparty_tun_activators_combines_resources_in_order(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    events: list[str] = []

    class Resource:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            events.append(f"close:{self.name}")

    first_resource = Resource("first")
    second_resource = Resource("second")

    def first(
        received: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        assert received is packet
        events.append("first")
        return FirstPartyVpnTunActivationResult(
            count=1,
            resources=(first_resource,),
        )

    def noop(_received: FirstPartyVpnDeploymentPacket) -> int:
        events.append("noop")
        return 0

    def second(
        received: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        assert received is packet
        events.append("second")
        return FirstPartyVpnTunActivationResult(
            count=1,
            resources=(second_resource,),
        )

    result = compose_firstparty_tun_activators(first, noop, second)(packet)

    assert result.count == 2
    assert result.resources == (first_resource, second_resource)
    assert events == ["first", "noop", "second"]


@pytest.mark.asyncio
async def test_compose_firstparty_tun_activators_closes_partial_resources_on_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    closed: list[str] = []

    class Resource:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            closed.append(self.name)

    def first(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        return FirstPartyVpnTunActivationResult(
            count=2,
            resources=(Resource("first"), Resource("second")),
        )

    def second(_packet: FirstPartyVpnDeploymentPacket) -> int:
        raise RuntimeError("simulated composed TUN activation failure")

    activator = compose_firstparty_tun_activators(first, second)

    with pytest.raises(RuntimeError, match="simulated composed TUN activation failure"):
        activator(packet)

    assert closed == ["second", "first"]


@pytest.mark.asyncio
async def test_compose_firstparty_dataplane_activators_closes_partial_resources_on_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    closed: list[str] = []

    class Resource:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            closed.append(self.name)

    def first(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        return FirstPartyVpnDataplaneActivationResult(
            count=2,
            resources=(Resource("first"), Resource("second")),
        )

    def second(_packet: FirstPartyVpnDeploymentPacket) -> int:
        raise RuntimeError("simulated composed dataplane activation failure")

    activator = compose_firstparty_dataplane_activators(first, second)

    with pytest.raises(
        RuntimeError,
        match="simulated composed dataplane activation failure",
    ):
        activator(packet)

    assert closed == ["second", "first"]


@pytest.mark.asyncio
async def test_deployment_executor_runs_composed_tun_and_dataplane_activators(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    closed: list[str] = []

    class Resource:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            closed.append(self.name)

    tun_first = Resource("tun-first")
    tun_second = Resource("tun-second")
    dataplane_first = Resource("dataplane-first")
    dataplane_second = Resource("dataplane-second")

    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=compose_firstparty_tun_activators(
            lambda _packet: FirstPartyVpnTunActivationResult(
                count=1,
                resources=(tun_first,),
            ),
            lambda _packet: FirstPartyVpnTunActivationResult(
                count=1,
                resources=(tun_second,),
            ),
        ),
        dataplane_activator=compose_firstparty_dataplane_activators(
            lambda _packet: FirstPartyVpnDataplaneActivationResult(
                count=1,
                resources=(dataplane_first,),
            ),
            lambda _packet: FirstPartyVpnDataplaneActivationResult(
                count=1,
                resources=(dataplane_second,),
            ),
        ),
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    )

    apply_evidence = executor.apply()
    rollback_evidence = executor.rollback()

    assert apply_evidence.succeeded is True
    assert apply_evidence.tun_activation_count == 2
    assert apply_evidence.dataplane_activation_count == 2
    assert rollback_evidence.succeeded is True
    assert closed == [
        "dataplane-second",
        "dataplane-first",
        "tun-second",
        "tun-first",
    ]
    assert executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(apply_evidence.to_json_dict())
    assert_privacy_safe(rollback_evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_keeps_tun_resources_until_rollback(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    closed: list[str] = []

    class Resource:
        def close(self) -> None:
            closed.append("tun")

    class DataplaneResource:
        def close(self) -> None:
            closed.append("dataplane")

    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=lambda _packet: FirstPartyVpnTunActivationResult(
            count=1,
            resources=(Resource(),),
        ),
        dataplane_activator=lambda _packet: FirstPartyVpnDataplaneActivationResult(
            count=1,
            resources=(DataplaneResource(),),
        ),
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    )
    evidence = executor.apply()

    assert evidence.succeeded is True
    assert evidence.tun_activation_count == 1
    assert evidence.dataplane_activation_count == 1
    assert closed == []
    rollback = executor.rollback()
    assert rollback.succeeded is True
    assert closed == ["dataplane", "tun"]


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_reports_tun_resource_close_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    class Resource:
        def close(self) -> None:
            raise RuntimeError("simulated close failure")

    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=lambda _packet: FirstPartyVpnTunActivationResult(
            count=1,
            resources=(Resource(),),
        ),
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    )
    apply_evidence = executor.apply()
    rollback = executor.rollback()

    assert apply_evidence.succeeded is True
    assert rollback.succeeded is False
    assert rollback.failure_reason == "tun_resource_close_failed"
    assert rollback.reasons == ("tun_resource_close_failed",)
    assert rollback.tun_resource_close_attempted is True
    assert rollback.tun_resource_close_count == 0
    assert rollback.tun_resource_close_failed_count == 1
    assert executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(rollback.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_closes_tun_resources_on_apply_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    closed: list[str] = []
    fail_at = packet.apply_commands[0]

    class Resource:
        def close(self) -> None:
            closed.append("tun")

    def runner(command: tuple[str, ...]) -> None:
        executed.append(command)
        if command == fail_at:
            raise RuntimeError("simulated apply failure")

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=runner,
        allow_os_mutation=True,
        tun_activator=lambda _packet: FirstPartyVpnTunActivationResult(
            count=1,
            resources=(Resource(),),
        ),
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "RuntimeError"
    assert evidence.rollback_attempted is True
    assert evidence.post_apply_validation_attempted is False
    assert closed == ["tun"]
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rolls_back_on_post_apply_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    post_apply = LinuxAppliedStateEvidence(
        controls=(),
        reasons=("full_tunnel_route_missing",),
        snapshot_hash="0" * 64,
        captured_at=NOW,
    )

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: post_apply,
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "post_apply_validation_failed"
    assert evidence.reasons == ("full_tunnel_route_missing",)
    assert evidence.executed_count == len(packet.apply_commands)
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is True
    assert evidence.post_apply_hash == post_apply.evidence_hash()
    assert executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rejects_mistimed_post_apply_evidence(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)

    def post_apply(captured_at: int) -> LinuxAppliedStateEvidence:
        return LinuxAppliedStateEvidence(
            controls=("client_tun_present",),
            reasons=(),
            snapshot_hash=hashlib.sha256(
                f"post-apply-{captured_at}".encode()
            ).hexdigest(),
            captured_at=captured_at,
        )

    stale_executed: list[tuple[str, ...]] = []
    stale = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=stale_executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: post_apply(NOW - 1),
        now_provider=lambda: NOW,
    ).apply()
    future_executed: list[tuple[str, ...]] = []
    future = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=future_executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: post_apply(NOW + 1),
        now_provider=lambda: NOW,
    ).apply()

    assert stale.succeeded is False
    assert stale.failure_reason == "post_apply_validation_time_invalid"
    assert "post_apply_validation_before_apply" in stale.reasons
    assert stale.post_apply_validation_attempted is True
    assert stale.post_apply_hash == post_apply(NOW - 1).evidence_hash()
    assert stale_executed == list(packet.apply_commands + packet.rollback_commands)
    assert future.succeeded is False
    assert future.failure_reason == "post_apply_validation_time_invalid"
    assert "post_apply_validation_from_future" in future.reasons
    assert future.post_apply_validation_attempted is True
    assert future.post_apply_hash == post_apply(NOW + 1).evidence_hash()
    assert future_executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(stale.to_json_dict())
    assert_privacy_safe(future.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rolls_back_on_post_apply_error(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []

    def validator(_packet: FirstPartyVpnDeploymentPacket) -> LinuxAppliedStateEvidence:
        raise RuntimeError("simulated collector failure")

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=validator,
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "RuntimeError"
    assert evidence.reasons == ("post_apply_validator_failed",)
    assert evidence.executed_count == len(packet.apply_commands)
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is True
    assert executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_blocks_failed_readiness(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(
        tmp_path,
        approval=False,
        ready_host=False,
    )
    executed: list[tuple[str, ...]] = []
    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
    )

    with pytest.raises(FirstPartyVpnDeploymentMutationBlocked, match="readiness gate"):
        executor.apply()

    assert executed == []


@pytest.mark.asyncio
async def test_firstparty_vpn_deployment_executor_rolls_back_on_apply_failure(
    tmp_path: Path,
) -> None:
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    fail_at = packet.apply_commands[1]

    def runner(command: tuple[str, ...]) -> None:
        executed.append(command)
        if command == fail_at:
            raise RuntimeError("simulated apply failure")

    evidence = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=runner,
        allow_os_mutation=True,
        tun_activator=successful_tun_activation,
        dataplane_activator=successful_dataplane_activation,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    ).apply()

    assert evidence.succeeded is False
    assert evidence.failure_reason == "RuntimeError"
    assert evidence.executed_count == 1
    assert evidence.rollback_attempted is True
    assert evidence.rollback_count == len(packet.rollback_commands)
    assert evidence.post_apply_validation_attempted is False
    assert fail_at in executed
    assert packet.rollback_commands[0] in executed
    assert_privacy_safe(evidence.to_json_dict())


def successful_preflight() -> LinuxPreflightEvidence:
    return evaluate_linux_deployment_preflight(
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-test",
            effective_uid=0,
            has_net_admin=True,
        ),
        config=LinuxPreflightConfig(),
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        path_exists=lambda path: path == "/dev/net/tun",
        binary_exists=lambda binary: binary in {"ip", "nft", "sysctl", "resolvectl"},
    )


def dataplane_validation_plan() -> DataplaneValidationPlan:
    probes = (
        DataplaneProbeSpec(
            probe_id="loopback-udp",
            path_label="loopback",
            transport="udp",
            remote_ref="127.0.0.1:443",
        ),
        DataplaneProbeSpec(
            probe_id="lan-tcp",
            path_label="lan",
            transport="tcp",
            remote_ref="192.0.2.10:443",
        ),
        DataplaneProbeSpec(
            probe_id="vps-udp",
            path_label="vps",
            transport="udp",
            remote_ref="203.0.113.10:443",
        ),
        DataplaneProbeSpec(
            probe_id="mobile-tcp",
            path_label="mobile",
            transport="tcp",
            remote_ref="198.51.100.25:443",
        ),
        DataplaneProbeSpec(
            probe_id="restricted-wifi-tcp",
            path_label="restricted-work-wifi",
            transport="tcp",
            remote_ref="restricted-work-wifi-nl:443",
        ),
    )
    return DataplaneValidationPlan(
        probes=probes,
        required_path_labels=frozenset(probe.path_label for probe in probes),
        min_successful_probes=len(probes),
    )


def test_collect_linux_host_facts_reads_root_capabilities_and_preflight_passes() -> None:
    facts = collect_linux_host_facts(
        os_name_reader=lambda: "Linux",
        kernel_release_reader=lambda: "6.8.0-x0vpn",
        uid_reader=lambda: 0,
        proc_status_reader=lambda: "Name:\tpython\nCapEff:\t0000000000001000\n",
    )

    assert isinstance(facts, LinuxHostFacts)
    assert facts.os_name == "Linux"
    assert facts.kernel_release == "6.8.0-x0vpn"
    assert facts.effective_uid == 0
    assert facts.has_net_admin is True
    evidence = evaluate_linux_deployment_preflight(
        facts=facts,
        config=LinuxPreflightConfig(),
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        path_exists=lambda path: path == "/dev/net/tun",
        binary_exists=lambda binary: binary in {"ip", "nft", "sysctl", "resolvectl"},
    )

    assert evidence.passed is True
    assert evidence.failed_reasons == ()
    assert len(evidence.evidence_hash()) == 64
    assert_privacy_safe(evidence.to_json_dict())


def test_collect_linux_host_facts_fails_closed_without_net_admin_capability() -> None:
    facts = collect_linux_host_facts(
        os_name_reader=lambda: "Linux",
        kernel_release_reader=lambda: "6.8.0-x0vpn",
        uid_reader=lambda: 0,
        proc_status_reader=lambda: "Name:\tpython\nCapEff:\t0000000000000000\n",
    )
    evidence = evaluate_linux_deployment_preflight(
        facts=facts,
        config=LinuxPreflightConfig(),
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        path_exists=lambda path: path == "/dev/net/tun",
        binary_exists=lambda binary: binary in {"ip", "nft", "sysctl", "resolvectl"},
    )

    assert facts.has_net_admin is False
    assert evidence.passed is False
    assert "net_admin_capability_required" in evidence.failed_reasons
    assert "root_required" not in evidence.failed_reasons
    assert_privacy_safe(evidence.to_json_dict())


def test_linux_deployment_preflight_passes_with_required_host_facts() -> None:
    evidence = successful_preflight()

    assert evidence.passed is True
    assert evidence.failed_reasons == ()
    assert len(evidence.evidence_hash()) == 64
    assert evidence.apply_plan.command_count == 1
    assert evidence.rollback_plan.command_count == 1
    assert "x0vpn0" in evidence.to_json_dict()["apply_plan"]["redacted_commands"][0]
    assert_privacy_safe(evidence.to_json_dict())


def test_linux_deployment_preflight_fails_closed_for_missing_requirements() -> None:
    evidence = evaluate_linux_deployment_preflight(
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-test",
            effective_uid=1000,
            has_net_admin=False,
        ),
        config=LinuxPreflightConfig(),
        apply_commands=(),
        rollback_commands=(),
        path_exists=lambda _path: False,
        binary_exists=lambda binary: binary == "ip",
    )

    assert evidence.passed is False
    assert "root_required" in evidence.failed_reasons
    assert "net_admin_capability_required" in evidence.failed_reasons
    assert "tun_device_missing" in evidence.failed_reasons
    assert "required_binary_missing" in evidence.failed_reasons
    assert "apply_plan_too_small" in evidence.failed_reasons
    assert "rollback_plan_too_small" in evidence.failed_reasons
    assert "resolvectl" in evidence.optional_missing


@pytest.mark.asyncio
async def test_dataplane_validation_evidence_covers_required_paths_privately() -> None:
    plan = dataplane_validation_plan()

    async def runner(probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        return DataplaneProbeResult.success_result(
            probe,
            latency_millis=12,
            rx_frames=1,
            tx_frames=1,
            rx_bytes=probe.payload_size + 32,
            tx_bytes=probe.payload_size + 32,
        )

    evidence = await evaluate_dataplane_validation(
        plan=plan,
        runner=runner,
        captured_at=NOW,
    )
    payload = evidence.to_json_dict()
    encoded = json.dumps(payload, sort_keys=True)

    assert evidence.passed is True
    assert set(evidence.covered_path_labels) == set(plan.required_path_labels)
    assert len(evidence.evidence_hash()) == 64
    assert "203.0.113.10" not in encoded
    assert "192.0.2.10" not in encoded
    assert_privacy_safe(payload)


@pytest.mark.asyncio
async def test_dataplane_validation_fails_closed_for_missing_path() -> None:
    plan = dataplane_validation_plan()

    async def runner(probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        if probe.path_label == "mobile":
            return DataplaneProbeResult.failure_result(
                probe,
                reason="timeout",
            )
        return DataplaneProbeResult.success_result(probe, latency_millis=9)

    evidence = await evaluate_dataplane_validation(
        plan=plan,
        runner=runner,
        captured_at=NOW,
    )

    assert evidence.passed is False
    assert "dataplane_required_path_missing:mobile" in evidence.failed_reasons
    assert any("dataplane_probe_failed:mobile-tcp" in item for item in evidence.failed_reasons)


def test_tun_dataplane_validation_requires_packet_roundtrip_evidence() -> None:
    plan = dataplane_validation_plan()

    evidence = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_tun_probe_result(probe) for probe in plan.probes),
        captured_at=NOW,
    )
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.passed is True
    assert set(evidence.covered_path_labels) == set(plan.required_path_labels)
    assert evidence.successful_path_count == len(plan.required_path_labels)
    assert len(evidence.evidence_hash()) == 64
    assert "203.0.113.10" not in encoded
    assert "192.0.2.10" not in encoded
    assert "restricted-work-wifi-nl" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


def test_tun_dataplane_validation_fails_closed_for_missing_packet_path() -> None:
    plan = dataplane_validation_plan()
    results = tuple(
        TunDataplaneProbeResult.failure_result(probe, reason="packet_timeout")
        if probe.path_label == "mobile"
        else _successful_tun_probe_result(probe)
        for probe in plan.probes
    )

    evidence = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=results,
        captured_at=NOW,
    )

    assert evidence.passed is False
    assert "tun_dataplane_required_path_missing:mobile" in evidence.failed_reasons
    assert any(
        "tun_dataplane_probe_failed:mobile-tcp" in item
        for item in evidence.failed_reasons
    )
    with pytest.raises(DataplaneValidationError, match="bidirectional packet evidence"):
        TunDataplaneProbeResult.success_result(
            plan.probes[0],
            packets_from_tun=1,
            packets_to_tun=0,
            bytes_from_tun=80,
            bytes_to_tun=0,
        )


@pytest.mark.asyncio
async def test_tun_dataplane_loopback_runner_carries_real_packets_over_transports() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    probes = (
        DataplaneProbeSpec(
            probe_id="tun-loopback-udp",
            path_label="tun-loopback-udp",
            transport="udp",
            remote_ref="tun-loopback-udp-private-ref",
            payload_size=96,
        ),
        DataplaneProbeSpec(
            probe_id="tun-loopback-tcp",
            path_label="tun-loopback-tcp",
            transport="tcp",
            remote_ref="tun-loopback-tcp-private-ref",
            payload_size=120,
        ),
        DataplaneProbeSpec(
            probe_id="tun-loopback-camouflage",
            path_label="tun-loopback-camouflage",
            transport="camouflage",
            remote_ref="tun-loopback-camouflage-private-ref",
            payload_size=144,
        ),
    )
    plan = DataplaneValidationPlan(
        probes=probes,
        required_path_labels=frozenset(probe.path_label for probe in probes),
        min_successful_probes=len(probes),
    )
    runner = FirstPartyTunLoopbackProbeRunner(
        session=session,
        fragment_payload_size=64,
    )

    results = tuple([await runner(probe) for probe in probes])
    evidence = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=results,
        captured_at=NOW,
    )
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.passed is True
    assert set(evidence.covered_path_labels) == {
        "tun-loopback-camouflage",
        "tun-loopback-tcp",
        "tun-loopback-udp",
    }
    assert all(result.packets_from_tun == 1 for result in evidence.results)
    assert all(result.packets_to_tun == 1 for result in evidence.results)
    assert all(result.tx_fragments >= 1 for result in evidence.results)
    assert all(result.rx_fragments >= 1 for result in evidence.results)
    assert "127.0.0.1" not in encoded
    assert "tun-loopback-udp-private-ref" not in encoded
    assert "tun-loopback-tcp-private-ref" not in encoded
    assert "tun-loopback-camouflage-private-ref" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_tun_dataplane_remote_runner_probes_existing_firstparty_endpoints() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    udp_transport = None
    tcp_server = None
    tcp_protocol = None
    camouflage_server = None
    camouflage_protocol = None
    try:
        udp_tun = MemoryTunDevice(mtu=900)
        tcp_tun = MemoryTunDevice(mtu=900)
        camouflage_tun = MemoryTunDevice(mtu=900)
        udp_transport, _udp_protocol, udp_addr = await open_udp_server(
            session=session,
            on_data=FirstPartyTunServerHandler(
                tun=udp_tun,
                response=ip_like_response_from_probe,
                fragmenter=PacketFragmenter(max_payload_size=64),
                reassembler=PacketReassembler(),
            ),
        )
        tcp_server, tcp_protocol, tcp_addr = await open_tcp_server(
            session=session,
            on_data=FirstPartyTunServerHandler(
                tun=tcp_tun,
                response=ip_like_response_from_probe,
                fragmenter=PacketFragmenter(max_payload_size=64),
                reassembler=PacketReassembler(),
            ),
        )
        (
            camouflage_server,
            camouflage_protocol,
            camouflage_addr,
        ) = await open_camouflage_server(
            session=session,
            on_data=FirstPartyTunServerHandler(
                tun=camouflage_tun,
                response=ip_like_response_from_probe,
                fragmenter=PacketFragmenter(max_payload_size=64),
                reassembler=PacketReassembler(),
            ),
        )
        probes = (
            DataplaneProbeSpec(
                probe_id="remote-tun-udp",
                path_label="nl-udp",
                transport="udp",
                remote_ref="nl-tun-udp-private-ref",
                payload_size=96,
            ),
            DataplaneProbeSpec(
                probe_id="remote-tun-tcp",
                path_label="nl-tcp",
                transport="tcp",
                remote_ref="nl-tun-tcp-private-ref",
                payload_size=120,
            ),
            DataplaneProbeSpec(
                probe_id="remote-tun-camouflage",
                path_label="nl-camouflage",
                transport="camouflage",
                remote_ref="nl-tun-camouflage-private-ref",
                payload_size=144,
            ),
        )
        endpoint_map = {
            "remote-tun-udp": udp_addr,
            "remote-tun-tcp": tcp_addr,
            "remote-tun-camouflage": camouflage_addr,
        }
        plan = DataplaneValidationPlan(
            probes=probes,
            required_path_labels=frozenset(probe.path_label for probe in probes),
            min_successful_probes=len(probes),
        )

        evidence = await evaluate_tun_dataplane_validation(
            plan=plan,
            runner=FirstPartyRemoteTunProbeRunner(
                session=session,
                endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
                tun_mtu=900,
                fragment_payload_size=64,
            ),
            captured_at=NOW,
        )
        encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

        assert evidence.passed is True
        assert set(evidence.covered_path_labels) == {
            "nl-camouflage",
            "nl-tcp",
            "nl-udp",
        }
        assert all(result.packets_from_tun == 1 for result in evidence.results)
        assert all(result.packets_to_tun == 1 for result in evidence.results)
        assert await udp_tun.read_written(timeout=1.0) is not None
        assert await tcp_tun.read_written(timeout=1.0) is not None
        assert await camouflage_tun.read_written(timeout=1.0) is not None
        assert "127.0.0.1" not in encoded
        assert "nl-tun-udp-private-ref" not in encoded
        assert "nl-tun-tcp-private-ref" not in encoded
        assert "nl-tun-camouflage-private-ref" not in encoded
        assert_privacy_safe(evidence.to_json_dict())
    finally:
        if udp_transport is not None:
            udp_transport.close()
        if tcp_server is not None:
            tcp_server.close()
            await tcp_server.wait_closed()
        if tcp_protocol is not None:
            await tcp_protocol.wait_client_tasks()
        if camouflage_server is not None:
            camouflage_server.close()
            await camouflage_server.wait_closed()
        if camouflage_protocol is not None:
            await camouflage_protocol.wait_client_tasks()


@pytest.mark.asyncio
async def test_tun_dataplane_selector_falls_back_after_blocked_udp_privately() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    server_tun = MemoryTunDevice(mtu=900)
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=FirstPartyTunServerHandler(
            tun=server_tun,
            response=ip_like_response_from_probe,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
        ),
    )
    try:
        assert service.tcp_addr is not None
        blocked_udp = DataplaneEndpointCandidate(
            candidate_id="tun-selector-udp-blocked",
            path_label="nl-udp",
            transport="udp",
            remote_ref="tun-selector-primary-udp-private-ref",
            remote_addr=("127.0.0.1", 1),
            priority=1,
            payload_size=96,
            timeout_seconds=0.05,
        )
        working_tcp = DataplaneEndpointCandidate(
            candidate_id="tun-selector-tcp-working",
            path_label="nl-tcp",
            transport="tcp",
            remote_ref="tun-selector-fallback-tcp-private-ref",
            remote_addr=service.tcp_addr,
            priority=2,
            payload_size=120,
            timeout_seconds=0.5,
        )

        outcome = await FirstPartyTunDataplaneSelector(
            session=session,
            candidates=(blocked_udp, working_tcp),
            tun_mtu=900,
            fragment_payload_size=64,
        ).select(captured_at=NOW)
        encoded = json.dumps(outcome.evidence.to_json_dict(), sort_keys=True)
        server_probe_packet = await server_tun.read_written(timeout=1.0)

        assert outcome.passed is True
        assert outcome.selected == working_tcp
        assert outcome.evidence.selected_candidate_hash == working_tcp.candidate_hash
        assert len(outcome.evidence.results) == 2
        assert outcome.evidence.results[0].success is False
        assert outcome.evidence.results[1].success is True
        assert outcome.evidence.results[1].packets_from_tun == 1
        assert outcome.evidence.results[1].packets_to_tun == 1
        assert server_probe_packet[0] >> 4 == 4
        assert "127.0.0.1" not in encoded
        assert "tun-selector-primary-udp-private-ref" not in encoded
        assert "tun-selector-fallback-tcp-private-ref" not in encoded
        assert "tun-selector-udp-blocked" not in encoded
        assert "tun-selector-tcp-working" not in encoded
        assert_privacy_safe(outcome.evidence.to_json_dict())
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_managed_tun_bridge_can_require_verified_tun_dataplane_selection() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=FirstPartyTunServerHandler(
            tun=server_tun,
            response=ip_like_response_from_probe,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
        ),
    )
    managed = None
    try:
        assert service.tcp_addr is not None
        managed = await open_firstparty_tun_client_bridge(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="verified-tun-udp-blocked",
                    path_label="nl-udp",
                    transport="udp",
                    remote_ref="verified-tun-primary-udp-private-ref",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    payload_size=96,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="verified-tun-tcp-working",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="verified-tun-fallback-tcp-private-ref",
                    remote_addr=service.tcp_addr,
                    priority=2,
                    payload_size=120,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            require_tun_dataplane_probe=True,
            tun_probe_mtu=900,
            tun_probe_fragment_payload_size=64,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
        )
        assert managed.tun_selection_evidence is not None
        encoded = json.dumps(
            managed.tun_selection_evidence.to_json_dict(),
            sort_keys=True,
        )
        probe_packet = await server_tun.read_written(timeout=1.0)

        packet = ipv4_packet(b"verified-tun-bridge")
        client_tun.inject_packet(packet)
        await managed.send_one_from_tun()
        await managed.receive_one_to_tun()

        assert managed.client.transport == "tcp"
        assert managed.tun_selection_evidence.passed is True
        assert len(managed.tun_selection_evidence.results) == 2
        assert managed.tun_selection_evidence.results[0].success is False
        assert managed.tun_selection_evidence.results[1].success is True
        assert managed.selection_evidence.passed is True
        assert len(managed.selection_evidence.results) == 1
        assert probe_packet[0] >> 4 == 4
        assert await server_tun.read_written(timeout=1.0) == packet
        assert await client_tun.read_written(timeout=1.0) == ip_like_response_from_probe(
            packet,
        )
        assert "127.0.0.1" not in encoded
        assert "verified-tun-primary-udp-private-ref" not in encoded
        assert "verified-tun-fallback-tcp-private-ref" not in encoded
        assert "verified-tun-udp-blocked" not in encoded
        assert "verified-tun-tcp-working" not in encoded
        assert_privacy_safe(managed.tun_selection_evidence.to_json_dict())
    finally:
        if managed is not None:
            await managed.close()
        await service.close()


@pytest.mark.asyncio
async def test_dataplane_validation_runs_real_firstparty_loopback_udp_and_tcp() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    probes = (
        DataplaneProbeSpec(
            probe_id="loopback-real-udp",
            path_label="loopback-udp",
            transport="udp",
            remote_ref="local-firstparty-loopback-udp",
            payload_size=96,
        ),
        DataplaneProbeSpec(
            probe_id="loopback-real-tcp",
            path_label="loopback-tcp",
            transport="tcp",
            remote_ref="local-firstparty-loopback-tcp",
            payload_size=128,
        ),
        DataplaneProbeSpec(
            probe_id="loopback-real-camouflage",
            path_label="loopback-camouflage",
            transport="camouflage",
            remote_ref="local-firstparty-loopback-camouflage",
            payload_size=144,
        ),
    )
    plan = DataplaneValidationPlan(
        probes=probes,
        required_path_labels=frozenset(probe.path_label for probe in probes),
        min_successful_probes=len(probes),
    )

    evidence = await evaluate_dataplane_validation(
        plan=plan,
        runner=FirstPartyLoopbackProbeRunner(session=session),
        captured_at=NOW,
    )
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

    assert evidence.passed is True
    assert set(evidence.covered_path_labels) == {
        "loopback-camouflage",
        "loopback-tcp",
        "loopback-udp",
    }
    assert all(result.rx_frames >= 1 for result in evidence.results)
    assert all(result.tx_frames >= 1 for result in evidence.results)
    assert all(result.rx_bytes > 0 for result in evidence.results)
    assert all(result.tx_bytes > 0 for result in evidence.results)
    assert "127.0.0.1" not in encoded
    assert "local-firstparty-loopback" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


@pytest.mark.asyncio
async def test_dataplane_validation_runs_remote_firstparty_udp_and_tcp_privately() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    udp_transport = None
    tcp_server = None
    tcp_protocol = None
    camouflage_server = None
    camouflage_protocol = None
    try:
        udp_transport, _udp_protocol, udp_addr = await open_udp_server(session=session)
        tcp_server, tcp_protocol, tcp_addr = await open_tcp_server(session=session)
        (
            camouflage_server,
            camouflage_protocol,
            camouflage_addr,
        ) = await open_camouflage_server(session=session)
        probes = (
            DataplaneProbeSpec(
                probe_id="remote-real-udp",
                path_label="nl-udp",
                transport="udp",
                remote_ref="nl-vpn-udp-primary",
                payload_size=80,
            ),
            DataplaneProbeSpec(
                probe_id="remote-real-tcp",
                path_label="nl-tcp",
                transport="tcp",
                remote_ref="nl-vpn-tcp-primary",
                payload_size=104,
            ),
            DataplaneProbeSpec(
                probe_id="remote-real-camouflage",
                path_label="nl-camouflage",
                transport="camouflage",
                remote_ref="nl-camouflage-primary",
                payload_size=120,
            ),
        )
        endpoint_map = {
            "remote-real-udp": udp_addr,
            "remote-real-tcp": tcp_addr,
            "remote-real-camouflage": camouflage_addr,
        }
        plan = DataplaneValidationPlan(
            probes=probes,
            required_path_labels=frozenset(probe.path_label for probe in probes),
            min_successful_probes=len(probes),
        )

        evidence = await evaluate_dataplane_validation(
            plan=plan,
            runner=FirstPartyRemoteProbeRunner(
                session=session,
                endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
            ),
            captured_at=NOW,
        )
        encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)

        assert evidence.passed is True
        assert set(evidence.covered_path_labels) == {
            "nl-camouflage",
            "nl-tcp",
            "nl-udp",
        }
        assert all(result.rx_frames >= 1 for result in evidence.results)
        assert all(result.tx_frames >= 1 for result in evidence.results)
        assert all(result.rx_bytes > 0 for result in evidence.results)
        assert all(result.tx_bytes > 0 for result in evidence.results)
        assert "127.0.0.1" not in encoded
        assert "nl-vpn-udp-primary" not in encoded
        assert "nl-vpn-tcp-primary" not in encoded
        assert "nl-camouflage-primary" not in encoded
        assert_privacy_safe(evidence.to_json_dict())
    finally:
        if udp_transport is not None:
            udp_transport.close()
        if tcp_server is not None:
            tcp_server.close()
            await tcp_server.wait_closed()
        if tcp_protocol is not None:
            await tcp_protocol.wait_client_tasks()
        if camouflage_server is not None:
            camouflage_server.close()
            await camouflage_server.wait_closed()
        if camouflage_protocol is not None:
            await camouflage_protocol.wait_client_tasks()


def test_firstparty_dataplane_bind_derives_server_nat_listener_ports() -> None:
    bind = FirstPartyDataplaneBind.from_server_nat(
        LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="udp", port=443),
                LinuxServerVpnListener(transport="camouflage", port=443),
                LinuxServerVpnListener(transport="tcp", port=8443),
                LinuxServerVpnListener(transport="tcp", port=9443),
            ),
        ),
        host="127.0.0.1",
    )

    assert bind.host == "127.0.0.1"
    assert bind.enable_udp is True
    assert bind.enable_tcp is True
    assert bind.enable_camouflage is True
    assert bind.udp_port == 443
    assert bind.tcp_port == 8443
    assert bind.tcp_port_candidates == (9443,)
    assert bind.camouflage_port == 443
    assert bind.ports_for("udp") == (443,)
    assert bind.ports_for("tcp") == (8443, 9443)
    assert bind.ports_for("camouflage") == (443,)


def test_firstparty_dataplane_bind_rejects_server_nat_without_listener_rules() -> None:
    with pytest.raises(
        FirstPartyDataplaneServiceError,
        match="server NAT does not expose VPN listeners",
    ):
        FirstPartyDataplaneBind.from_server_nat(
            LinuxServerNatConfig(allow_vpn_listener=False),
        )


@pytest.mark.asyncio
async def test_build_firstparty_dataplane_activator_uses_server_nat_bind(
    tmp_path: Path,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        client_network=LinuxNetworkPolicyConfig(dns_servers=("9.9.9.9",)),
        expected_test_count=99,
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="udp", port=443),
                LinuxServerVpnListener(transport="camouflage", port=443),
                LinuxServerVpnListener(transport="tcp", port=8443),
                LinuxServerVpnListener(transport="tcp", port=9443),
            ),
        ),
    )
    packet = build_firstparty_vpn_deployment_packet(
        config=config,
        facts=LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0-x0vpn",
            effective_uid=0,
            has_net_admin=True,
        ),
        evidence=await complete_deployment_evidence(tmp_path),
        path_exists=lambda _path: True,
        binary_exists=lambda _binary: True,
        now=NOW,
    )
    captured_binds: list[FirstPartyDataplaneBind] = []

    class CapturedDataplaneResource:
        closed = False

        def close(self) -> None:
            self.closed = True

    resource = CapturedDataplaneResource()

    def start_factory(
        bind: FirstPartyDataplaneBind,
    ) -> CapturedDataplaneResource:
        captured_binds.append(bind)
        return resource

    activator = build_firstparty_dataplane_activator(
        config=config,
        start_factory=start_factory,
        host="127.0.0.1",
    )

    result = activator(packet)

    assert result.count == 1
    assert result.resources == (resource,)
    assert len(captured_binds) == 1
    bind = captured_binds[0]
    assert bind.host == "127.0.0.1"
    assert bind.ports_for("udp") == (443,)
    assert bind.ports_for("tcp") == (8443, 9443)
    assert bind.ports_for("camouflage") == (443,)

    result.resources[0].close()
    assert resource.closed is True


@pytest.mark.asyncio
async def test_build_firstparty_dataplane_activator_rejects_disabled_server_listener(
    tmp_path: Path,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(allow_vpn_listener=False),
        required_dataplane_transports=(),
    )
    called = False

    def start_factory(
        _bind: FirstPartyDataplaneBind,
    ) -> InMemoryDataplaneActivationResource:
        nonlocal called
        called = True
        return InMemoryDataplaneActivationResource()

    activator = build_firstparty_dataplane_activator(
        config=config,
        start_factory=start_factory,
    )

    with pytest.raises(
        FirstPartyDataplaneServiceError,
        match="server NAT does not expose VPN listeners",
    ):
        activator(await build_test_deployment_packet(tmp_path))
    assert called is False


@pytest.mark.asyncio
async def test_open_threaded_firstparty_dataplane_service_serves_tcp_and_closes(
    unused_tcp_port: int,
) -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"threaded-pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"threaded-client-nonce".ljust(32, b"c"),
        server_nonce=b"threaded-server-nonce".ljust(32, b"s"),
    )
    resource = open_threaded_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            tcp_port=unused_tcp_port,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        on_data=lambda payload, _addr: b"threaded:" + payload,
    )
    client = None
    try:
        assert resource.running is True
        assert resource.service.tcp_addr == ("127.0.0.1", unused_tcp_port)
        assert resource.bind_evidence.passed is True

        client = await open_tcp_client(
            session=session,
            remote_addr=resource.service.tcp_addr,
        )
        client.send_data(b"packet")
        await client.drain()
        response = await client.recv(timeout=1.0)

        assert response.frame_type == FrameType.DATA
        assert response.payload == b"threaded:packet"
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()
        resource.close()
    assert resource.running is False
    resource.close()


@pytest.mark.asyncio
async def test_build_firstparty_dataplane_activator_starts_threaded_service_from_nat(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"activator-pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"activator-client-nonce".ljust(32, b"c"),
        server_nonce=b"activator-server-nonce".ljust(32, b"s"),
    )

    def start_factory(
        bind: FirstPartyDataplaneBind,
    ) -> FirstPartyThreadedDataplaneServiceResource:
        return open_threaded_firstparty_dataplane_service(
            session=session,
            bind=bind,
            on_data=lambda payload, _addr: b"activated:" + payload,
        )

    activator = build_firstparty_dataplane_activator(
        config=config,
        start_factory=start_factory,
        host="127.0.0.1",
    )
    result = activator(await build_test_deployment_packet(tmp_path))
    resource = result.resources[0]
    client = None
    try:
        assert result.count == 1
        assert isinstance(resource, FirstPartyThreadedDataplaneServiceResource)
        assert resource.running is True
        assert resource.service.tcp_addr == ("127.0.0.1", unused_tcp_port)
        assert resource.bind_evidence.passed is True

        client = await open_tcp_client(
            session=session,
            remote_addr=resource.service.tcp_addr,
        )
        client.send_data(b"packet")
        await client.drain()
        response = await client.recv(timeout=1.0)

        assert response.frame_type == FrameType.DATA
        assert response.payload == b"activated:packet"
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()
        resource.close()
    assert resource.running is False


@pytest.mark.asyncio
async def test_build_firstparty_dataplane_activator_starts_threaded_tun_server_from_nat(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"threaded-tun-pqc-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"threaded-tun-client-nonce".ljust(32, b"c"),
        server_nonce=b"threaded-tun-server-nonce".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)

    def start_factory(
        bind: FirstPartyDataplaneBind,
    ) -> FirstPartyThreadedTunServerResource:
        return open_threaded_firstparty_tun_server(
            session=session,
            tun=server_tun,
            bind=bind,
            return_transport="tcp",
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
        )

    activator = build_firstparty_dataplane_activator(
        config=config,
        start_factory=start_factory,
        host="127.0.0.1",
    )
    result = activator(await build_test_deployment_packet(tmp_path))
    resource = result.resources[0]
    client_pump = None
    try:
        assert result.count == 1
        assert isinstance(resource, FirstPartyThreadedTunServerResource)
        assert resource.running is True
        assert resource.service.tcp_addr == ("127.0.0.1", unused_tcp_port)
        assert resource.bind_evidence.passed is True

        client_pump = await open_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-tun-server-tcp",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="threaded-tun-server-tcp-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )

        packet = ipv4_packet(b"threaded-tun-client-packet" * 8)
        client_tun.inject_packet(packet)
        assert await server_tun.read_written(timeout=1.0) == packet

        reply = ip_like_response(b"threaded-tun-server:", packet)
        server_tun.inject_packet(reply)
        assert await client_tun.read_written(timeout=1.0) == reply

        assert resource.handler.stats.packets_to_tun == 1
        assert resource.pump.stats.packets_from_tun == 1
        assert resource.pump.stats.tx_fragments > 1
        assert client_pump.managed.stats.packets_to_tun == 1
        assert client_pump.managed.stats.rx_fragments > 1
    finally:
        if client_pump is not None:
            await client_pump.stop()
        resource.close()
    assert resource.running is False


@pytest.mark.asyncio
async def test_build_firstparty_admission_tun_server_activator_starts_server_from_nat(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"deployment-admission-tun-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"deployment-admission-tun-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tuns: dict[int, MemoryTunDevice] = {}
    activator = build_firstparty_admission_tun_server_activator(
        config=config,
        registry=registry,
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
        host="127.0.0.1",
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    result = activator(await build_test_deployment_packet(tmp_path))
    resource = result.resources[0]
    managed = None
    try:
        assert result.count == 1
        assert isinstance(resource, FirstPartyThreadedAdmissionTunServerResource)
        assert resource.running is True
        assert resource.service.tcp_addr == ("127.0.0.1", unused_tcp_port)
        assert resource.bind_evidence.passed is True

        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="deployment-admission-tun-tcp",
                    path_label="deployment-admission-tcp",
                    transport="tcp",
                    remote_ref="deployment-admission-tun-tcp-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )

        packet = ipv4_packet(b"deployment-admission-request")
        client_tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)

        session_id = managed.client.session.session_id
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            session_id not in server_tuns
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert session_id in server_tuns
        assert resource.service.active_transport_by_session[session_id] == "tcp"

        server_tun = server_tuns[session_id]
        assert await server_tun.read_written(timeout=1.0) == packet
        reply = ip_like_response(b"deployment-admission-return:", packet)
        server_tun.inject_packet(reply)

        await managed.receive_one_to_tun(timeout=1.0)
        assert await client_tun.read_written(timeout=1.0) == reply
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            resource.return_router.last_transport_by_session.get(session_id) != "tcp"
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert (
            resource.return_router.last_transport_by_session[session_id]
            == "tcp"
        )
        pump = resource.pump_for(managed.client.session)
        assert pump.stats.packets_from_tun == 1
    finally:
        if managed is not None:
            await managed.close()
        resource.close()
    assert resource.running is False


def test_build_firstparty_admission_tun_server_activator_rejects_unexposed_return_transport() -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=8443),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    authority = identity_authority()
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=authority.issue(issue_request("vpn-server"), now=NOW),
        identity_authority=authority,
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        shared_secret_resolver=lambda _hello: None,
        server_nonce_provider=lambda _hello: b"unexposed-return-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )

    with pytest.raises(
        FirstPartyVpnDeploymentError,
        match="admission TUN return transport is not exposed by server NAT",
    ):
        build_firstparty_admission_tun_server_activator(
            config=config,
            registry=registry,
            tun_factory=lambda _session: MemoryTunDevice(mtu=900),
            return_transports=("udp",),
        )


@pytest.mark.asyncio
async def test_build_firstparty_admission_tun_server_activators_open_tun_then_start_server(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_tun=LinuxTunConfig(name="x0vpn-server", address="10.77.0.1/24"),
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    opened: list[LinuxTunConfig] = []
    closed: list[str] = []

    class FakeDeploymentTunDevice:
        def __init__(self, tun_config: LinuxTunConfig) -> None:
            self.tun_config = tun_config
            self.memory = MemoryTunDevice(mtu=900)

        @property
        def mtu(self) -> int:
            return self.memory.mtu

        async def read_packet(self, timeout: float | None = None) -> bytes:
            return await self.memory.read_packet(timeout=timeout)

        async def write_packet(self, packet: bytes) -> None:
            await self.memory.write_packet(packet)

        def write_packet_nowait(self, packet: bytes) -> None:
            self.memory.write_packet_nowait(packet)

        def open_interface(self) -> None:
            opened.append(self.tun_config)

        def close(self) -> None:
            closed.append(self.tun_config.name)

    devices: list[FakeDeploymentTunDevice] = []

    def device_factory(tun_config: LinuxTunConfig) -> FakeDeploymentTunDevice:
        device = FakeDeploymentTunDevice(tun_config)
        devices.append(device)
        return device

    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"deployment-server-pair-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"deployment-server-pair-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    packet = await build_test_deployment_packet(tmp_path)
    tun_activator, dataplane_activator = (
        build_firstparty_admission_tun_server_activators(
            config=config,
            registry=registry,
            device_factory=device_factory,
            host="127.0.0.1",
            return_transports=("tcp",),
            tun_read_timeout=0.02,
        )
    )

    with pytest.raises(
        FirstPartyVpnDeploymentError,
        match="admission TUN server requires activated TUN",
    ):
        dataplane_activator(packet)

    tun_result = tun_activator(packet)
    dataplane_result = dataplane_activator(packet)
    resource = dataplane_result.resources[0]
    client_tun = MemoryTunDevice(mtu=900)
    managed = None
    try:
        assert tun_result.count == 1
        assert dataplane_result.count == 1
        assert isinstance(resource, FirstPartyThreadedAdmissionTunServerResource)
        assert len(devices) == 1
        assert opened[0].name == "x0vpn-server"
        assert opened[0].allow_os_mutation is True
        assert resource.running is True

        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="deployment-server-pair-tcp",
                    path_label="deployment-server-pair-path",
                    transport="tcp",
                    remote_ref="deployment-server-pair-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )

        request = ipv4_packet(b"deployment-server-pair-request")
        client_tun.inject_packet(request)
        await managed.send_one_from_tun(timeout=1.0)
        assert await devices[0].memory.read_written(timeout=1.0) == request

        reply = ip_like_response(b"deployment-server-pair-return:", request)
        devices[0].memory.inject_packet(reply)
        await managed.receive_one_to_tun(timeout=1.0)
        assert await client_tun.read_written(timeout=1.0) == reply
    finally:
        if managed is not None:
            await managed.close()
        resource.close()
        tun_result.resources[0].close()
    assert resource.running is False
    assert closed == ["x0vpn-server"]


@pytest.mark.asyncio
async def test_build_firstparty_admission_tun_server_pool_activator_routes_two_users(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(
        allowed_tenants=frozenset({"team-a"}),
        allowed_workloads=frozenset({"vpn-client-a", "vpn-client-b", "vpn-server"}),
    )
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    store = FirstPartyHandshakeSecretStore()

    def build_hello(client_name: str, nonce_prefix: bytes):
        hello, material = create_firstparty_handshake_hello(
            pqc_provider=provider,
            client_identity=authority.issue(issue_request(client_name), now=NOW),
            server_identity=server_token,
            deployment_epoch="test-epoch",
            client_nonce=nonce_prefix.ljust(32, b"c"),
            issued_at=NOW,
        )
        store.add(material)
        return hello, material

    hello_a, material_a = build_hello(
        "vpn-client-a",
        b"pool-client-a",
    )
    hello_b, material_b = build_hello(
        "vpn-client-b",
        b"pool-client-b",
    )
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"deployment-pool-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    closed_sessions: list[int] = []

    class CloseableMemoryTunDevice:
        def __init__(self, session_id: int) -> None:
            self.session_id = session_id
            self.memory = MemoryTunDevice(mtu=900)
            self.closed = False

        @property
        def mtu(self) -> int:
            return self.memory.mtu

        async def read_packet(self, timeout: float | None = None) -> bytes:
            return await self.memory.read_packet(timeout=timeout)

        async def write_packet(self, packet: bytes) -> None:
            await self.memory.write_packet(packet)

        def write_packet_nowait(self, packet: bytes) -> None:
            self.memory.write_packet_nowait(packet)

        def close(self) -> None:
            if self.closed:
                return
            self.closed = True
            closed_sessions.append(self.session_id)

    server_tuns: dict[int, CloseableMemoryTunDevice] = {}

    def tun_factory(session) -> CloseableMemoryTunDevice:
        device = CloseableMemoryTunDevice(session.session_id)
        server_tuns[session.session_id] = device
        return device

    activator = build_firstparty_admission_tun_server_pool_activator(
        config=config,
        registry=registry,
        tun_factory=tun_factory,
        host="127.0.0.1",
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    result = activator(await build_test_deployment_packet(tmp_path))
    pool_resource = result.resources[0]
    server_resource = result.resources[1]
    client_a_tun = MemoryTunDevice(mtu=900)
    client_b_tun = MemoryTunDevice(mtu=900)
    managed_a = None
    managed_b = None
    try:
        assert result.count == 2
        assert isinstance(server_resource, FirstPartyThreadedAdmissionTunServerResource)
        assert server_resource.running is True

        assert server_resource.service.tcp_addr is not None
        candidate = DataplaneEndpointCandidate(
            candidate_id="deployment-pool-tcp",
            path_label="deployment-pool-path",
            transport="tcp",
            remote_ref="deployment-pool-ref",
            remote_addr=server_resource.service.tcp_addr,
            priority=1,
            timeout_seconds=0.5,
        )
        managed_a = await open_firstparty_admission_tun_client_bridge(
            hello=hello_a,
            pqc_material=material_a,
            tun=client_a_tun,
            candidates=(candidate,),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )
        managed_b = await open_firstparty_admission_tun_client_bridge(
            hello=hello_b,
            pqc_material=material_b,
            tun=client_b_tun,
            candidates=(candidate,),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )
        session_a = managed_a.client.session.session_id
        session_b = managed_b.client.session.session_id
        assert session_a != session_b
        assert server_resource.admitted_session_ids == tuple(
            sorted((session_a, session_b))
        )

        async def wait_for_session_tun(session_id: int) -> None:
            deadline = asyncio.get_running_loop().time() + 1.0
            while (
                session_id not in server_tuns
                and asyncio.get_running_loop().time() < deadline
            ):
                await asyncio.sleep(0.01)
            assert session_id in server_tuns

        packet_a = ipv4_packet(b"deployment-pool-user-a")
        packet_b = ipv4_packet(b"deployment-pool-user-b")
        client_a_tun.inject_packet(packet_a)
        await managed_a.send_one_from_tun(timeout=1.0)
        await wait_for_session_tun(session_a)
        client_b_tun.inject_packet(packet_b)
        await managed_b.send_one_from_tun(timeout=1.0)
        await wait_for_session_tun(session_b)
        assert pool_resource.session_ids == tuple(sorted((session_a, session_b)))
        assert await server_tuns[session_a].memory.read_written(timeout=1.0) == packet_a
        assert await server_tuns[session_b].memory.read_written(timeout=1.0) == packet_b

        reply_b = ip_like_response(b"deployment-pool-return-b:", packet_b)
        server_tuns[session_b].memory.inject_packet(reply_b)
        await managed_b.receive_one_to_tun(timeout=1.0)
        assert await client_b_tun.read_written(timeout=1.0) == reply_b

        reply_a = ip_like_response(b"deployment-pool-return-a:", packet_a)
        server_tuns[session_a].memory.inject_packet(reply_a)
        await managed_a.receive_one_to_tun(timeout=1.0)
        assert await client_a_tun.read_written(timeout=1.0) == reply_a
    finally:
        if managed_b is not None:
            await managed_b.close()
        if managed_a is not None:
            await managed_a.close()
        server_resource.close()
        pool_resource.close()
    assert server_resource.running is False
    assert closed_sessions == [session_b, session_a]


@pytest.mark.asyncio
async def test_build_firstparty_admission_tun_client_activators_open_tun_then_start_pump(
    tmp_path: Path,
) -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"deployment-client-activator".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"deployment-client-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server_tuns: dict[int, MemoryTunDevice] = {}
    server_resource = open_threaded_firstparty_admission_tun_server(
        registry=registry,
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    devices: list[FakeDeploymentTunDevice] = []

    class FakeDeploymentTunDevice:
        def __init__(self, tun_config: LinuxTunConfig) -> None:
            self.config = tun_config
            self.mtu = tun_config.mtu
            self.tun = MemoryTunDevice(mtu=tun_config.mtu)
            self.opened = False
            self.closed = False
            devices.append(self)

        def open_interface(self) -> None:
            assert self.config.allow_os_mutation is True
            self.opened = True

        async def read_packet(self, timeout: float | None = None) -> bytes:
            return await self.tun.read_packet(timeout=timeout)

        async def write_packet(self, packet: bytes) -> None:
            await self.tun.write_packet(packet)

        def write_packet_nowait(self, packet: bytes) -> None:
            self.tun.write_packet_nowait(packet)

        def close(self) -> None:
            self.closed = True

    try:
        assert server_resource.service.tcp_addr is not None
        tun_activator, dataplane_activator = (
            build_firstparty_admission_tun_client_activators(
                config=FirstPartyVpnDeploymentConfig(),
                hello=hello,
                pqc_material=material,
                candidates=(
                    DataplaneEndpointCandidate(
                        candidate_id="deployment-client-activator-tcp",
                        path_label="deployment-client-activator",
                        transport="tcp",
                        remote_ref="deployment-client-activator-ref",
                        remote_addr=server_resource.service.tcp_addr,
                        priority=1,
                        timeout_seconds=0.5,
                    ),
                ),
                identity_authority=authority,
                policy=zero_trust_policy,
                captured_at=NOW,
                device_factory=FakeDeploymentTunDevice,
                tun_read_timeout=0.02,
                transport_read_timeout=0.02,
            )
        )
        packet = await build_test_deployment_packet(tmp_path)
        with pytest.raises(
            FirstPartyVpnDeploymentError,
            match="admission TUN client requires activated TUN",
        ):
            dataplane_activator(packet)

        tun_result = tun_activator(packet)
        assert tun_result.count == 1
        assert len(devices) == 1
        assert devices[0].opened is True
        client_result = dataplane_activator(packet)
        client_resource = client_result.resources[0]
        try:
            assert isinstance(client_resource, FirstPartyThreadedTunClientResource)
            assert client_resource.running is True
            assert client_resource.managed.client.transport == "tcp"

            request = ipv4_packet(b"deployment-client-activator-request")
            devices[0].tun.inject_packet(request)
            session_id = client_resource.managed.client.session.session_id
            deadline = asyncio.get_running_loop().time() + 1.0
            while (
                session_id not in server_tuns
                and asyncio.get_running_loop().time() < deadline
            ):
                await asyncio.sleep(0.01)
            assert session_id in server_tuns

            server_tun = server_tuns[session_id]
            assert await server_tun.read_written(timeout=1.0) == request
            reply = ip_like_response(
                b"deployment-client-activator-return:",
                request,
            )
            server_tun.inject_packet(reply)
            assert await devices[0].tun.read_written(timeout=1.0) == reply
        finally:
            client_resource.close()
            tun_result.resources[0].close()
        assert devices[0].closed is True
    finally:
        server_resource.close()


@pytest.mark.asyncio
async def test_build_firstparty_admission_vpn_activators_run_full_runtime_with_executor(
    tmp_path: Path,
    unused_tcp_port: int,
) -> None:
    config = FirstPartyVpnDeploymentConfig(
        client_tun=LinuxTunConfig(name="x0vpn-client", address="10.77.0.2/32"),
        server_tun=LinuxTunConfig(name="x0vpn-server", address="10.77.0.1/24"),
        server_nat=LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="tcp", port=unused_tcp_port),
            ),
        ),
        required_dataplane_transports=(("restricted-work-wifi", "tcp"),),
    )
    opened: list[str] = []
    closed: list[str] = []

    class FakeDeploymentTunDevice:
        def __init__(self, tun_config: LinuxTunConfig) -> None:
            self.config = tun_config
            self.tun = MemoryTunDevice(mtu=tun_config.mtu)

        @property
        def mtu(self) -> int:
            return self.tun.mtu

        async def read_packet(self, timeout: float | None = None) -> bytes:
            return await self.tun.read_packet(timeout=timeout)

        async def write_packet(self, packet: bytes) -> None:
            await self.tun.write_packet(packet)

        def write_packet_nowait(self, packet: bytes) -> None:
            self.tun.write_packet_nowait(packet)

        def open_interface(self) -> None:
            assert self.config.allow_os_mutation is True
            opened.append(self.config.name)

        def close(self) -> None:
            closed.append(self.config.name)

    server_devices: list[FakeDeploymentTunDevice] = []
    client_devices: list[FakeDeploymentTunDevice] = []

    def server_device_factory(tun_config: LinuxTunConfig) -> FakeDeploymentTunDevice:
        device = FakeDeploymentTunDevice(tun_config)
        server_devices.append(device)
        return device

    def client_device_factory(tun_config: LinuxTunConfig) -> FakeDeploymentTunDevice:
        device = FakeDeploymentTunDevice(tun_config)
        client_devices.append(device)
        return device

    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"deployment-full-vpn-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"deployment-full-vpn-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    tun_activator, dataplane_activator = build_firstparty_admission_vpn_activators(
        config=config,
        registry=registry,
        hello=hello,
        pqc_material=material,
        candidates=(
            DataplaneEndpointCandidate(
                candidate_id="deployment-full-vpn-tcp",
                path_label="deployment-full-vpn-path",
                transport="tcp",
                remote_ref="deployment-full-vpn-ref",
                remote_addr=("127.0.0.1", unused_tcp_port),
                priority=1,
                timeout_seconds=0.5,
            ),
        ),
        identity_authority=authority,
        policy=zero_trust_policy,
        captured_at=NOW,
        server_device_factory=server_device_factory,
        client_device_factory=client_device_factory,
        host="127.0.0.1",
        return_transports=("tcp",),
        tun_read_timeout=0.02,
        transport_read_timeout=0.02,
    )
    packet = await build_test_deployment_packet(tmp_path)
    executed: list[tuple[str, ...]] = []
    executor = FirstPartyVpnDeploymentExecutor(
        packet=packet,
        command_runner=executed.append,
        allow_os_mutation=True,
        tun_activator=tun_activator,
        dataplane_activator=dataplane_activator,
        post_apply_validator=lambda _packet: successful_post_apply_evidence(),
        now_provider=lambda: NOW,
    )

    apply_evidence = executor.apply()
    try:
        assert apply_evidence.succeeded is True
        assert apply_evidence.tun_activation_count == 2
        assert apply_evidence.dataplane_activation_count == 2
        assert opened == ["x0vpn-server", "x0vpn-client"]
        assert len(server_devices) == 1
        assert len(client_devices) == 1

        server_resource = executor._dataplane_activation_resources[0]
        client_resource = executor._dataplane_activation_resources[1]
        assert isinstance(server_resource, FirstPartyThreadedAdmissionTunServerResource)
        assert isinstance(client_resource, FirstPartyThreadedTunClientResource)
        assert server_resource.running is True
        assert client_resource.running is True
        assert client_resource.managed.client.transport == "tcp"

        request = ipv4_packet(b"deployment-full-vpn-request")
        client_devices[0].tun.inject_packet(request)
        assert await server_devices[0].tun.read_written(timeout=1.0) == request

        reply = ip_like_response(b"deployment-full-vpn-return:", request)
        server_devices[0].tun.inject_packet(reply)
        assert await client_devices[0].tun.read_written(timeout=1.0) == reply

        session_id = client_resource.managed.client.session.session_id
        assert server_resource.service.active_transport_by_session[session_id] == "tcp"
        assert_privacy_safe(apply_evidence.to_json_dict())
    finally:
        rollback = executor.rollback()
    assert rollback.succeeded is True
    assert closed == ["x0vpn-client", "x0vpn-server"]
    assert executed == list(packet.apply_commands + packet.rollback_commands)
    assert_privacy_safe(rollback.to_json_dict())


@pytest.mark.asyncio
async def test_threaded_tun_client_resource_bridges_to_threaded_server_resource(
    unused_tcp_port: int,
) -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"threaded-client-pqc-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"threaded-client-side".ljust(32, b"c"),
        server_nonce=b"threaded-server-side".ljust(32, b"s"),
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tun = MemoryTunDevice(mtu=900)
    server_resource = open_threaded_firstparty_tun_server(
        session=session,
        tun=server_tun,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            tcp_port=unused_tcp_port,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transport="tcp",
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassembler=PacketReassembler(),
        tun_read_timeout=0.05,
    )
    client_resource = None
    try:
        client_resource = open_threaded_firstparty_tun_client_pump(
            session=session,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-client-to-server",
                    path_label="nl-tcp-threaded-client",
                    transport="tcp",
                    remote_ref="threaded-client-to-server-ref",
                    remote_addr=server_resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )

        assert isinstance(client_resource, FirstPartyThreadedTunClientResource)
        assert client_resource.running is True
        assert client_resource.managed.selection_evidence.passed is True
        assert client_resource.managed.client.open_evidence is not None
        assert client_resource.managed.client.open_evidence.passed is True

        packet = ipv4_packet(b"threaded-client-packet" * 8)
        client_tun.inject_packet(packet)
        assert await server_tun.read_written(timeout=1.0) == packet

        reply = ip_like_response(b"threaded-server-reply:", packet)
        server_tun.inject_packet(reply)
        assert await client_tun.read_written(timeout=1.0) == reply

        assert server_resource.handler.stats.packets_to_tun == 1
        assert server_resource.pump.stats.packets_from_tun == 1
        assert client_resource.managed.stats.packets_from_tun == 1
        assert client_resource.managed.stats.packets_to_tun == 1
    finally:
        if client_resource is not None:
            client_resource.close()
        server_resource.close()
    assert server_resource.running is False
    if client_resource is not None:
        assert client_resource.running is False


@pytest.mark.asyncio
async def test_threaded_multi_session_tun_server_routes_two_users_on_one_listener(
    unused_tcp_port: int,
) -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"threaded-multi-pqc-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"threaded-multi-client-a".ljust(32, b"c"),
        server_nonce=b"threaded-multi-server-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"threaded-multi-pqc-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"threaded-multi-client-b".ljust(32, b"c"),
        server_nonce=b"threaded-multi-server-b".ljust(32, b"s"),
    )
    client_tun_a = MemoryTunDevice(mtu=900)
    client_tun_b = MemoryTunDevice(mtu=900)
    server_tun_a = MemoryTunDevice(mtu=900)
    server_tun_b = MemoryTunDevice(mtu=900)
    resource = open_threaded_firstparty_multi_session_tun_server(
        sessions=(session_a, session_b),
        tuns={
            session_a.session_id: server_tun_a,
            session_b.session_id: server_tun_b,
        },
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            tcp_port=unused_tcp_port,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transport="tcp",
        fragmenter=PacketFragmenter(max_payload_size=64),
        reassemblers={
            session_a.session_id: PacketReassembler(),
            session_b.session_id: PacketReassembler(),
        },
        tun_read_timeout=0.05,
    )
    client_pump_a = None
    client_pump_b = None
    try:
        assert isinstance(resource, FirstPartyThreadedMultiSessionTunServerResource)
        assert resource.running is True
        assert resource.service.tcp_addr == ("127.0.0.1", unused_tcp_port)
        assert resource.handler.admitted_session_ids == tuple(
            sorted((session_a.session_id, session_b.session_id))
        )
        assert len(resource.pumps) == 2
        assert resource.pump_for(session_a).running is True
        assert resource.pump_for(session_b).running is True

        client_pump_a = await open_firstparty_tun_client_pump(
            session=session_a,
            tun=client_tun_a,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-multi-a",
                    path_label="nl-tcp-a",
                    transport="tcp",
                    remote_ref="threaded-multi-a-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )
        client_pump_b = await open_firstparty_tun_client_pump(
            session=session_b,
            tun=client_tun_b,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-multi-b",
                    path_label="nl-tcp-b",
                    transport="tcp",
                    remote_ref="threaded-multi-b-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
            fragmenter=PacketFragmenter(max_payload_size=64),
            reassembler=PacketReassembler(),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
        )

        packet_a = ipv4_packet(b"threaded-user-a" * 12)
        packet_b = ipv4_packet(b"threaded-user-b" * 12)
        client_tun_a.inject_packet(packet_a)
        client_tun_b.inject_packet(packet_b)
        assert await server_tun_a.read_written(timeout=1.0) == packet_a
        assert await server_tun_b.read_written(timeout=1.0) == packet_b

        response_a = ip_like_response(b"return-a:", packet_a)
        response_b = ip_like_response(b"return-b:", packet_b)
        server_tun_a.inject_packet(response_a)
        server_tun_b.inject_packet(response_b)
        assert await client_tun_a.read_written(timeout=1.0) == response_a
        assert await client_tun_b.read_written(timeout=1.0) == response_b

        assert resource.handler.handler_for(session_a).stats.packets_to_tun == 1
        assert resource.handler.handler_for(session_b).stats.packets_to_tun == 1
        assert resource.pump_for(session_a).stats.packets_from_tun == 1
        assert resource.pump_for(session_b).stats.packets_from_tun == 1
        assert client_pump_a.managed.stats.packets_to_tun == 1
        assert client_pump_b.managed.stats.packets_to_tun == 1
    finally:
        if client_pump_a is not None:
            await client_pump_a.stop()
        if client_pump_b is not None:
            await client_pump_b.stop()
        resource.close()
    assert resource.running is False


@pytest.mark.asyncio
async def test_firstparty_admission_dataplane_service_admits_all_transports() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hellos_and_materials = tuple(
        create_firstparty_handshake_hello(
            pqc_provider=provider,
            client_identity=client_token,
            server_identity=server_token,
            deployment_epoch="test-epoch",
            client_nonce=f"admission-service-client-{index}".encode().ljust(
                32,
                b"c",
            ),
            issued_at=NOW + index,
        )
        for index in range(3)
    )
    store = FirstPartyHandshakeSecretStore()
    for _hello, material in hellos_and_materials:
        store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda hello: hashlib.sha256(
            b"admission-service-server-nonce" + bytes.fromhex(hello.hello_hash())
        ).digest(),
        accepted_at_provider=lambda hello: max(NOW, hello.issued_at),
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    service = await open_firstparty_admission_dataplane_service(
        registry=registry,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        on_data=lambda payload, _peer: b"admission-service:" + payload,
    )
    udp_transport = None
    tcp_result = None
    camouflage_result = None
    try:
        assert service.running is True
        assert service.udp_addr is not None
        assert service.tcp_addr is not None
        assert service.camouflage_addr is not None
        assert service.bind_evidence.passed is True
        assert len(service.bind_evidence.attempts) == 3
        assert {attempt.transport for attempt in service.bind_evidence.attempts} == {
            "camouflage",
            "tcp",
            "udp",
        }
        encoded = json.dumps(service.bind_evidence.to_json_dict(), sort_keys=True)
        assert "127.0.0.1" not in encoded
        assert_privacy_safe(service.bind_evidence.to_json_dict())

        udp_hello, udp_material = hellos_and_materials[0]
        tcp_hello, tcp_material = hellos_and_materials[1]
        camouflage_hello, camouflage_material = hellos_and_materials[2]

        udp_transport, udp_client = await open_udp_admission_client(
            hello=udp_hello,
            pqc_material=udp_material,
            remote_addr=service.udp_addr,
            identity_authority=authority,
            policy=zero_trust_policy,
        )
        tcp_result = await open_tcp_admission_client(
            hello=tcp_hello,
            pqc_material=tcp_material,
            remote_addr=service.tcp_addr,
            identity_authority=authority,
            policy=zero_trust_policy,
        )
        camouflage_result = await open_camouflage_admission_client(
            hello=camouflage_hello,
            pqc_material=camouflage_material,
            remote_addr=service.camouflage_addr,
            identity_authority=authority,
            policy=zero_trust_policy,
            profile=profile,
            camouflage_policy=camouflage_policy,
            timeout=0.5,
        )

        assert udp_client.session is not None
        assert service.admitted_session_ids == tuple(
            sorted(
                (
                    udp_client.session.session_id,
                    tcp_result.session.session_id,
                    camouflage_result.session.session_id,
                )
            )
        )

        udp_client.send_data(b"udp")
        assert (await udp_client.recv(timeout=1.0)).payload == b"admission-service:udp"
        assert service.udp_protocol is not None
        service.udp_protocol.send_data(
            b"udp-server-push",
            session=udp_client.session,
        )
        assert (await udp_client.recv(timeout=1.0)).payload == b"udp-server-push"

        tcp_result.client.send_data(b"tcp")
        await tcp_result.client.drain()
        assert (
            await tcp_result.client.recv(timeout=1.0)
        ).payload == b"admission-service:tcp"
        assert service.tcp_protocol is not None
        await service.tcp_protocol.send_data(
            b"tcp-server-push",
            session=tcp_result.session,
        )
        assert (
            await tcp_result.client.recv(timeout=1.0)
        ).payload == b"tcp-server-push"

        camouflage_result.client.send_data(b"camouflage")
        await camouflage_result.client.drain()
        assert (
            await camouflage_result.client.recv(timeout=1.0)
        ).payload == b"admission-service:camouflage"
        assert service.camouflage_protocol is not None
        await service.camouflage_protocol.send_data(
            b"camouflage-server-push",
            session=camouflage_result.session,
        )
        assert (
            await camouflage_result.client.recv(timeout=1.0)
        ).payload == b"camouflage-server-push"
    finally:
        if udp_transport is not None:
            udp_transport.close()
        if tcp_result is not None:
            tcp_result.client.close()
            await tcp_result.client.wait_closed()
        if camouflage_result is not None:
            camouflage_result.client.close()
            await camouflage_result.client.wait_closed()
        await service.close()

    assert service.running is False
    assert service.udp_addr is None
    assert service.tcp_addr is None
    assert service.camouflage_addr is None


@pytest.mark.asyncio
async def test_firstparty_admission_dataplane_client_fails_over_to_camouflage() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-client-failover".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-client-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    service = await open_firstparty_admission_dataplane_service(
        registry=registry,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        on_data=lambda payload, _peer: b"admission-client:" + payload,
    )
    client = None
    try:
        assert service.camouflage_addr is not None
        client = await open_firstparty_admission_dataplane_client(
            hello=hello,
            pqc_material=material,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="admission-client-udp-blocked",
                    path_label="work-udp",
                    transport="udp",
                    remote_ref="admission-client-udp-private-ref",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="admission-client-tcp-blocked",
                    path_label="work-tcp",
                    transport="tcp",
                    remote_ref="admission-client-tcp-private-ref",
                    remote_addr=("127.0.0.1", 1),
                    priority=2,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="admission-client-camouflage-working",
                    path_label="work-camouflage",
                    transport="camouflage",
                    remote_ref="admission-client-camouflage-private-ref",
                    remote_addr=service.camouflage_addr,
                    priority=3,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            camouflage_profile=profile,
            camouflage_policy=camouflage_policy,
        )
        encoded_selection = json.dumps(
            client.selection_evidence.to_json_dict(),
            sort_keys=True,
        )
        assert client.open_evidence is not None
        encoded_open = json.dumps(client.open_evidence.to_json_dict(), sort_keys=True)

        assert client.transport == "camouflage"
        assert client.session.session_id == client.accept.session_id
        assert registry.admitted_session_ids == (client.session.session_id,)
        assert client.selection_evidence.passed is True
        assert len(client.selection_evidence.results) == 3
        assert client.selection_evidence.results[0].success is False
        assert client.selection_evidence.results[1].success is False
        assert client.selection_evidence.results[2].success is True
        assert client.open_evidence.passed is True
        assert client.open_evidence.attempts[0].opened is False
        assert client.open_evidence.attempts[1].opened is False
        assert client.open_evidence.attempts[2].opened is True
        assert client.open_evidence.selected_candidate_hash == client.selected.candidate_hash
        assert "127.0.0.1" not in encoded_selection
        assert "127.0.0.1" not in encoded_open
        assert "admission-client-udp-private-ref" not in encoded_selection
        assert "admission-client-udp-private-ref" not in encoded_open
        assert "admission-client-tcp-private-ref" not in encoded_selection
        assert "admission-client-tcp-private-ref" not in encoded_open
        assert "admission-client-camouflage-private-ref" not in encoded_selection
        assert "admission-client-camouflage-private-ref" not in encoded_open
        assert "admission-client-udp-blocked" not in encoded_selection
        assert "admission-client-tcp-blocked" not in encoded_selection
        assert "admission-client-camouflage-working" not in encoded_selection
        assert_privacy_safe(client.selection_evidence.to_json_dict())
        assert_privacy_safe(client.open_evidence.to_json_dict())

        client.send_data(b"packet")
        await client.drain()
        data_response = await client.recv(timeout=1.0)
        assert data_response.frame_type == FrameType.DATA
        assert data_response.payload == b"admission-client:packet"

        client.send_ping(b"health")
        await client.drain()
        ping_response = await client.recv(timeout=1.0)
        assert ping_response.frame_type == FrameType.PONG
        assert ping_response.payload == b"health"
    finally:
        if client is not None:
            await client.close()
        await service.close()

    assert client is not None
    with pytest.raises(FirstPartyDataplaneClientError):
        client.send_ping(b"closed")


@pytest.mark.asyncio
async def test_firstparty_admission_dataplane_client_rejects_stale_accept() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-client-stale-accept".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-stale-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server, protocol, addr = await open_tcp_admission_server(registry=registry)
    try:
        with pytest.raises(FirstPartyDataplaneClientError) as exc:
            await open_firstparty_admission_dataplane_client(
                hello=hello,
                pqc_material=material,
                candidates=(
                    DataplaneEndpointCandidate(
                        candidate_id="admission-client-stale-accept-tcp",
                        path_label="work-tcp",
                        transport="tcp",
                        remote_ref="admission-client-stale-accept-ref",
                        remote_addr=addr,
                        priority=1,
                        timeout_seconds=0.5,
                    ),
                ),
                identity_authority=authority,
                policy=zero_trust_policy,
                captured_at=NOW + 301,
            )
    finally:
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()

    assert exc.value.open_evidence is not None
    assert exc.value.open_evidence.passed is False
    assert exc.value.open_evidence.attempts[0].opened is False
    assert_privacy_safe(exc.value.open_evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_admission_tun_bridge_rejects_stale_accept() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-tun-stale-accept".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-tun-stale-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    server, protocol, addr = await open_tcp_admission_server(registry=registry)
    try:
        with pytest.raises(FirstPartyDataplaneClientError) as exc:
            await open_firstparty_admission_tun_client_bridge(
                hello=hello,
                pqc_material=material,
                tun=MemoryTunDevice(mtu=900),
                candidates=(
                    DataplaneEndpointCandidate(
                        candidate_id="admission-tun-stale-accept-tcp",
                        path_label="tun-tcp",
                        transport="tcp",
                        remote_ref="admission-tun-stale-accept-ref",
                        remote_addr=addr,
                        priority=1,
                        timeout_seconds=0.5,
                    ),
                ),
                identity_authority=authority,
                policy=zero_trust_policy,
                captured_at=NOW + 301,
            )
    finally:
        server.close()
        await server.wait_closed()
        await protocol.wait_client_tasks()

    assert exc.value.open_evidence is not None
    assert exc.value.open_evidence.passed is False
    assert exc.value.open_evidence.attempts[0].opened is False
    assert_privacy_safe(exc.value.open_evidence.to_json_dict())


@pytest.mark.asyncio
async def test_firstparty_admission_tun_bridge_sends_packet_after_camouflage_failover() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-tun-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-tun-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    service = await open_firstparty_admission_dataplane_service(
        registry=registry,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        on_data=lambda packet, _peer: ip_like_response(b"admission-tun:", packet),
    )
    tun = MemoryTunDevice(mtu=900)
    managed = None
    try:
        assert service.camouflage_addr is not None
        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="admission-tun-udp-blocked",
                    path_label="tun-udp",
                    transport="udp",
                    remote_ref="admission-tun-udp-private-ref",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="admission-tun-camouflage-working",
                    path_label="tun-camouflage",
                    transport="camouflage",
                    remote_ref="admission-tun-camouflage-private-ref",
                    remote_addr=service.camouflage_addr,
                    priority=2,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            camouflage_profile=profile,
            camouflage_policy=camouflage_policy,
            completed_at_provider=lambda accept: accept.accepted_at,
        )
        packet = ipv4_packet(b"packet-from-tun")
        expected = ip_like_response(b"admission-tun:", packet)

        assert managed.client.transport == "camouflage"
        assert managed.client.accept is not None
        assert managed.client.session.session_id == managed.client.accept.session_id
        assert managed.selection_evidence.passed is True
        assert len(managed.selection_evidence.results) == 2
        assert managed.selection_evidence.results[0].success is False
        assert managed.selection_evidence.results[1].success is True

        tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)
        await managed.receive_one_to_tun(timeout=1.0)

        assert await tun.read_written(timeout=1.0) == expected
        assert managed.stats.packets_from_tun == 1
        assert managed.stats.packets_to_tun == 1
        assert managed.stats.bytes_from_tun == len(packet)
        assert managed.stats.bytes_to_tun == len(expected)
    finally:
        if managed is not None:
            await managed.close()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_admission_tun_server_handler_creates_route_for_new_session() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-server-tun-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-server-tun-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    server_tuns: dict[int, MemoryTunDevice] = {}
    tun_handler = FirstPartyAdmissionTunServerHandler(
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
        response_factory=lambda _session: (
            lambda packet: ip_like_response(b"server-admission-tun:", packet)
        ),
    )
    service = await open_firstparty_admission_dataplane_service(
        registry=registry,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        on_session_data=tun_handler,
    )
    managed = None
    try:
        assert service.camouflage_addr is not None
        assert tun_handler.admitted_session_ids == ()
        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="admission-server-tun-camouflage",
                    path_label="server-tun-camouflage",
                    transport="camouflage",
                    remote_ref="admission-server-tun-private-ref",
                    remote_addr=service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            camouflage_profile=profile,
            camouflage_policy=camouflage_policy,
        )
        packet = ipv4_packet(b"server-tun-packet")
        expected = ip_like_response(b"server-admission-tun:", packet)

        managed.bridge.tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)
        await managed.receive_one_to_tun(timeout=1.0)

        assert managed.client.session.session_id in server_tuns
        server_tun = server_tuns[managed.client.session.session_id]
        assert await server_tun.read_written(timeout=1.0) == packet
        assert await managed.bridge.tun.read_written(timeout=1.0) == expected
        assert tun_handler.admitted_session_ids == (managed.client.session.session_id,)
        assert tun_handler.handler_for(managed.client.session).stats.packets_to_tun == 1
        assert tun_handler.handler_for(managed.client.session).stats.packets_from_tun == 1

        return_packet = ip_like_response(b"server-return:", packet)
        server_tun.inject_packet(return_packet)
        assert service.camouflage_protocol is not None
        return_pump = FirstPartyAdmissionTunServerReturnPump(
            session=managed.client.session,
            handler=tun_handler,
            server=service.camouflage_protocol,
        )
        await return_pump.send_one_from_tun(timeout=1.0)

        await managed.receive_one_to_tun(timeout=1.0)
        assert await managed.bridge.tun.read_written(timeout=1.0) == return_packet
        assert return_pump.stats.packets_from_tun == 1
        assert return_pump.stats.bytes_from_tun == len(return_packet)
    finally:
        if managed is not None:
            await managed.close()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_admission_tun_return_pump_manager_starts_for_new_session() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"admission-auto-return-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"admission-auto-return-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    server_tuns: dict[int, MemoryTunDevice] = {}
    tun_handler = FirstPartyAdmissionTunServerHandler(
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
    )
    service = await open_firstparty_admission_dataplane_service(
        registry=registry,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        on_session_data=tun_handler,
    )
    managed = None
    manager = None
    try:
        assert service.camouflage_addr is not None
        assert service.camouflage_protocol is not None
        manager = FirstPartyAdmissionTunServerReturnPumpManager(
            handler=tun_handler,
            server=service.camouflage_protocol,
            tun_read_timeout=0.02,
        )
        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="admission-auto-return-camouflage",
                    path_label="auto-return-camouflage",
                    transport="camouflage",
                    remote_ref="admission-auto-return-private-ref",
                    remote_addr=service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            camouflage_profile=profile,
            camouflage_policy=camouflage_policy,
        )

        packet = ipv4_packet(b"auto-return-request")
        managed.bridge.tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)

        session_id = managed.client.session.session_id
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            session_id not in server_tuns
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert session_id in server_tuns
        server_tun = server_tuns[session_id]
        assert await server_tun.read_written(timeout=1.0) == packet
        assert manager.running is True

        return_packet = ip_like_response(b"auto-return:", packet)
        server_tun.inject_packet(return_packet)

        await managed.receive_one_to_tun(timeout=1.0)
        assert await managed.bridge.tun.read_written(timeout=1.0) == return_packet
        pump = manager.pump_for(managed.client.session)
        assert pump.stats.packets_from_tun == 1
        assert pump.stats.bytes_from_tun == len(return_packet)
        assert pump.pump_stats.tun_to_transport_cycles >= 1
    finally:
        if manager is not None:
            await manager.stop()
        if managed is not None:
            await managed.close()
        await service.close()


@pytest.mark.asyncio
async def test_threaded_firstparty_admission_tun_server_routes_new_session_return_path() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"threaded-admission-tun-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"threaded-admission-tun-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    camouflage_policy = CamouflagePolicy(
        allowed_profile_ids=frozenset({"restricted-work-wifi"})
    )
    server_tuns: dict[int, MemoryTunDevice] = {}
    resource = open_threaded_firstparty_admission_tun_server(
        registry=registry,
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=True,
            enable_tcp=True,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=camouflage_policy,
        tun_read_timeout=0.02,
    )
    managed = None
    try:
        assert isinstance(resource, FirstPartyThreadedAdmissionTunServerResource)
        assert resource.running is True
        assert resource.service.camouflage_addr is not None
        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-admission-tun-camouflage",
                    path_label="threaded-admission-camouflage",
                    transport="camouflage",
                    remote_ref="threaded-admission-tun-private-ref",
                    remote_addr=resource.service.camouflage_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            camouflage_profile=profile,
            camouflage_policy=camouflage_policy,
        )

        packet = ipv4_packet(b"threaded-admission-request")
        managed.bridge.tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)

        session_id = managed.client.session.session_id
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            session_id not in server_tuns
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert session_id in server_tuns
        assert resource.service.active_transport_by_session[session_id] == "camouflage"

        server_tun = server_tuns[session_id]
        assert await server_tun.read_written(timeout=1.0) == packet
        return_packet = ip_like_response(b"threaded-admission-return:", packet)
        server_tun.inject_packet(return_packet)

        await managed.receive_one_to_tun(timeout=1.0)
        assert await managed.bridge.tun.read_written(timeout=1.0) == return_packet
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            resource.return_router.last_transport_by_session.get(session_id)
            != "camouflage"
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert (
            resource.return_router.last_transport_by_session[session_id]
            == "camouflage"
        )
        assert resource.pump_for(managed.client.session).stats.packets_from_tun == 1
    finally:
        if managed is not None:
            await managed.close()
        resource.close()


@pytest.mark.asyncio
async def test_threaded_firstparty_admission_tun_client_pump_bridges_to_server() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"threaded-admission-client-pump".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"threaded-admission-pump-server".ljust(
            32,
            b"s",
        ),
        accepted_at_provider=lambda _hello: NOW,
    )
    client_tun = MemoryTunDevice(mtu=900)
    server_tuns: dict[int, MemoryTunDevice] = {}
    server_resource = open_threaded_firstparty_admission_tun_server(
        registry=registry,
        tun_factory=lambda session: server_tuns.setdefault(
            session.session_id,
            MemoryTunDevice(mtu=900),
        ),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    client_resource = None
    try:
        assert server_resource.service.tcp_addr is not None
        client_resource = open_threaded_firstparty_admission_tun_client_pump(
            hello=hello,
            pqc_material=material,
            tun=client_tun,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="threaded-admission-client-pump-tcp",
                    path_label="threaded-admission-client-pump",
                    transport="tcp",
                    remote_ref="threaded-admission-client-pump-ref",
                    remote_addr=server_resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
            tun_read_timeout=0.02,
            transport_read_timeout=0.02,
        )

        assert isinstance(client_resource, FirstPartyThreadedTunClientResource)
        assert client_resource.running is True
        assert client_resource.managed.client.transport == "tcp"
        assert client_resource.managed.client.accept is not None

        packet = ipv4_packet(b"threaded-admission-client-packet")
        client_tun.inject_packet(packet)
        session_id = client_resource.managed.client.session.session_id
        deadline = asyncio.get_running_loop().time() + 1.0
        while (
            session_id not in server_tuns
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert session_id in server_tuns

        server_tun = server_tuns[session_id]
        assert await server_tun.read_written(timeout=1.0) == packet
        reply = ip_like_response(b"threaded-admission-client-return:", packet)
        server_tun.inject_packet(reply)
        assert await client_tun.read_written(timeout=1.0) == reply

        pump = server_resource.pump_for(client_resource.managed.client.session)
        assert pump.stats.packets_from_tun == 1
        assert client_resource.managed.stats.packets_from_tun == 1
        assert client_resource.managed.stats.packets_to_tun == 1
    finally:
        if client_resource is not None:
            client_resource.close()
        server_resource.close()
    assert server_resource.running is False
    if client_resource is not None:
        assert client_resource.running is False


@pytest.mark.asyncio
async def test_firstparty_dataplane_service_serves_udp_and_tcp_remote_probes() -> None:
    with pytest.raises(ValueError):
        FirstPartyDataplaneBind(enable_udp=False, enable_tcp=False)
    with pytest.raises(ValueError):
        FirstPartyDataplaneBind(udp_port=-1)

    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_camouflage=True,
        ),
    )
    try:
        assert service.running is True
        assert service.udp_addr is not None
        assert service.tcp_addr is not None
        assert service.camouflage_addr is not None
        with pytest.raises(FirstPartyDataplaneServiceError):
            await service.start()

        probes = (
            DataplaneProbeSpec(
                probe_id="service-udp",
                path_label="service-udp",
                transport="udp",
                remote_ref="service-udp-private-ref",
            ),
            DataplaneProbeSpec(
                probe_id="service-tcp",
                path_label="service-tcp",
                transport="tcp",
                remote_ref="service-tcp-private-ref",
            ),
            DataplaneProbeSpec(
                probe_id="service-camouflage",
                path_label="service-camouflage",
                transport="camouflage",
                remote_ref="service-camouflage-private-ref",
            ),
        )
        endpoint_map = {
            "service-udp": service.udp_addr,
            "service-tcp": service.tcp_addr,
            "service-camouflage": service.camouflage_addr,
        }
        evidence = await evaluate_dataplane_validation(
            plan=DataplaneValidationPlan(
                probes=probes,
                required_path_labels=frozenset(probe.path_label for probe in probes),
                min_successful_probes=len(probes),
            ),
            runner=FirstPartyRemoteProbeRunner(
                session=session,
                endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
            ),
            captured_at=NOW,
        )

        assert evidence.passed is True
        assert set(evidence.covered_path_labels) == {
            "service-camouflage",
            "service-tcp",
            "service-udp",
        }
    finally:
        await service.close()

    assert service.running is False
    assert service.udp_addr is None
    assert service.tcp_addr is None
    assert service.camouflage_addr is None


@pytest.mark.asyncio
async def test_firstparty_multi_session_dataplane_service_serves_all_transports() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"service-pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"service-client-nonce-a".ljust(32, b"c"),
        server_nonce=b"service-server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"service-pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"service-client-nonce-b".ljust(32, b"c"),
        server_nonce=b"service-server-nonce-b".ljust(32, b"s"),
    )
    profile = CamouflageProfile(
        profile_id="restricted-work-wifi",
        host="updates.invalid",
        path="/assets/check",
    )
    policy = CamouflagePolicy(allowed_profile_ids=frozenset({"restricted-work-wifi"}))
    service = await open_firstparty_multi_session_dataplane_service(
        sessions=(session_a, session_b),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=policy,
        on_data=lambda payload, _addr: b"multi-service:" + payload,
    )
    udp_a_transport = None
    udp_b_transport = None
    tcp_a = None
    tcp_b = None
    camouflage_a = None
    camouflage_b = None
    try:
        assert service.running is True
        assert service.udp_addr is not None
        assert service.tcp_addr is not None
        assert service.camouflage_addr is not None
        assert service.bind_evidence.passed is True
        assert len(service.bind_evidence.attempts) == 3
        assert {attempt.transport for attempt in service.bind_evidence.attempts} == {
            "camouflage",
            "tcp",
            "udp",
        }
        assert all(attempt.opened for attempt in service.bind_evidence.attempts)
        encoded = json.dumps(service.bind_evidence.to_json_dict(), sort_keys=True)
        assert "127.0.0.1" not in encoded
        assert_privacy_safe(service.bind_evidence.to_json_dict())

        udp_a_transport, udp_a = await open_udp_client(
            session=session_a,
            remote_addr=service.udp_addr,
        )
        udp_b_transport, udp_b = await open_udp_client(
            session=session_b,
            remote_addr=service.udp_addr,
        )
        udp_a.send_data(b"udp-a")
        udp_b.send_data(b"udp-b")
        assert (await udp_a.recv(timeout=1.0)).payload == b"multi-service:udp-a"
        assert (await udp_b.recv(timeout=1.0)).payload == b"multi-service:udp-b"

        tcp_a = await open_tcp_client(session=session_a, remote_addr=service.tcp_addr)
        tcp_b = await open_tcp_client(session=session_b, remote_addr=service.tcp_addr)
        tcp_a.send_data(b"tcp-a")
        tcp_b.send_data(b"tcp-b")
        await tcp_a.drain()
        await tcp_b.drain()
        assert (await tcp_a.recv(timeout=1.0)).payload == b"multi-service:tcp-a"
        assert (await tcp_b.recv(timeout=1.0)).payload == b"multi-service:tcp-b"

        camouflage_a = await open_camouflage_client(
            session=session_a,
            remote_addr=service.camouflage_addr,
            profile=profile,
            policy=policy,
            timeout=0.5,
        )
        camouflage_b = await open_camouflage_client(
            session=session_b,
            remote_addr=service.camouflage_addr,
            profile=profile,
            policy=policy,
            timeout=0.5,
        )
        camouflage_a.send_data(b"camouflage-a")
        camouflage_b.send_data(b"camouflage-b")
        await camouflage_a.drain()
        await camouflage_b.drain()
        assert (
            await camouflage_a.recv(timeout=1.0)
        ).payload == b"multi-service:camouflage-a"
        assert (
            await camouflage_b.recv(timeout=1.0)
        ).payload == b"multi-service:camouflage-b"
    finally:
        if udp_a_transport is not None:
            udp_a_transport.close()
        if udp_b_transport is not None:
            udp_b_transport.close()
        if tcp_a is not None:
            tcp_a.close()
            await tcp_a.wait_closed()
        if tcp_b is not None:
            tcp_b.close()
            await tcp_b.wait_closed()
        if camouflage_a is not None:
            camouflage_a.close()
            await camouflage_a.wait_closed()
        if camouflage_b is not None:
            camouflage_b.close()
            await camouflage_b.wait_closed()
        await service.close()

    assert service.running is False
    assert service.udp_addr is None
    assert service.tcp_addr is None
    assert service.camouflage_addr is None


@pytest.mark.asyncio
async def test_firstparty_multi_session_tun_handler_routes_all_transports_by_session() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"tun-pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"tun-client-nonce-a".ljust(32, b"c"),
        server_nonce=b"tun-server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"tun-pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"tun-client-nonce-b".ljust(32, b"c"),
        server_nonce=b"tun-server-nonce-b".ljust(32, b"s"),
    )
    server_tun_a = MemoryTunDevice(mtu=900)
    server_tun_b = MemoryTunDevice(mtu=900)
    tun_handler = FirstPartyMultiSessionTunServerHandler(
        handlers={
            session_a.session_id: FirstPartyTunServerHandler(
                tun=server_tun_a,
                response=lambda packet: ip_like_response(b"tun-a:", packet),
            ),
            session_b.session_id: FirstPartyTunServerHandler(
                tun=server_tun_b,
                response=lambda packet: ip_like_response(b"tun-b:", packet),
            ),
        },
    )
    profile = CamouflageProfile(
        profile_id="multi-tun-work-wifi",
        host="assets.invalid",
        path="/ws/tun",
    )
    policy = CamouflagePolicy(allowed_profile_ids=frozenset({"multi-tun-work-wifi"}))
    service = await open_firstparty_multi_session_dataplane_service(
        sessions=(session_a, session_b),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_camouflage=True,
        ),
        camouflage_profile=profile,
        camouflage_policy=policy,
        on_session_data=tun_handler,
    )
    udp_a_transport = None
    udp_b_transport = None
    tcp_a = None
    tcp_b = None
    camouflage_a = None
    camouflage_b = None
    try:
        assert service.udp_protocol is not None
        assert service.tcp_protocol is not None
        assert service.camouflage_protocol is not None
        assert tun_handler.admitted_session_ids == tuple(
            sorted((session_a.session_id, session_b.session_id))
        )

        udp_a_transport, udp_a = await open_udp_client(
            session=session_a,
            remote_addr=service.udp_addr,
        )
        udp_b_transport, udp_b = await open_udp_client(
            session=session_b,
            remote_addr=service.udp_addr,
        )
        udp_packet_a = ipv4_packet(b"udp-user-a")
        udp_packet_b = ipv4_packet(b"udp-user-b")
        udp_a.send_data(udp_packet_a)
        udp_b.send_data(udp_packet_b)
        assert await server_tun_a.read_written(timeout=1.0) == udp_packet_a
        assert await server_tun_b.read_written(timeout=1.0) == udp_packet_b
        assert (await udp_a.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-a:",
            udp_packet_a,
        )
        assert (await udp_b.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-b:",
            udp_packet_b,
        )
        udp_return_a = ip_like_response(b"return-a:", udp_packet_a)
        udp_return_b = ip_like_response(b"return-b:", udp_packet_b)
        service.udp_protocol.send_data_fragments(
            (udp_return_a,),
            session=session_a,
        )
        service.udp_protocol.send_data_fragments(
            (udp_return_b,),
            session=session_b,
        )
        assert (await udp_a.recv(timeout=1.0)).payload == udp_return_a
        assert (await udp_b.recv(timeout=1.0)).payload == udp_return_b

        tcp_a = await open_tcp_client(session=session_a, remote_addr=service.tcp_addr)
        tcp_b = await open_tcp_client(session=session_b, remote_addr=service.tcp_addr)
        tcp_packet_a = ipv4_packet(b"tcp-user-a")
        tcp_packet_b = ipv4_packet(b"tcp-user-b")
        tcp_a.send_data(tcp_packet_a)
        tcp_b.send_data(tcp_packet_b)
        await tcp_a.drain()
        await tcp_b.drain()
        assert await server_tun_a.read_written(timeout=1.0) == tcp_packet_a
        assert await server_tun_b.read_written(timeout=1.0) == tcp_packet_b
        assert (await tcp_a.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-a:",
            tcp_packet_a,
        )
        assert (await tcp_b.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-b:",
            tcp_packet_b,
        )
        tcp_return_a = ip_like_response(b"tcp-return-a:", tcp_packet_a)
        tcp_return_b = ip_like_response(b"tcp-return-b:", tcp_packet_b)
        await service.tcp_protocol.send_data_fragments(
            (tcp_return_a,),
            session=session_a,
        )
        await service.tcp_protocol.send_data_fragments(
            (tcp_return_b,),
            session=session_b,
        )
        assert (await tcp_a.recv(timeout=1.0)).payload == tcp_return_a
        assert (await tcp_b.recv(timeout=1.0)).payload == tcp_return_b

        camouflage_a = await open_camouflage_client(
            session=session_a,
            remote_addr=service.camouflage_addr,
            profile=profile,
            policy=policy,
            timeout=0.5,
        )
        camouflage_b = await open_camouflage_client(
            session=session_b,
            remote_addr=service.camouflage_addr,
            profile=profile,
            policy=policy,
            timeout=0.5,
        )
        camouflage_packet_a = ipv4_packet(b"camouflage-user-a")
        camouflage_packet_b = ipv4_packet(b"camouflage-user-b")
        camouflage_a.send_data(camouflage_packet_a)
        camouflage_b.send_data(camouflage_packet_b)
        await camouflage_a.drain()
        await camouflage_b.drain()
        assert await server_tun_a.read_written(timeout=1.0) == camouflage_packet_a
        assert await server_tun_b.read_written(timeout=1.0) == camouflage_packet_b
        assert (await camouflage_a.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-a:",
            camouflage_packet_a,
        )
        assert (await camouflage_b.recv(timeout=1.0)).payload == ip_like_response(
            b"tun-b:",
            camouflage_packet_b,
        )
        camouflage_return_a = ip_like_response(
            b"camouflage-return-a:",
            camouflage_packet_a,
        )
        camouflage_return_b = ip_like_response(
            b"camouflage-return-b:",
            camouflage_packet_b,
        )
        await service.camouflage_protocol.send_data_fragments(
            (camouflage_return_a,),
            session=session_a,
        )
        await service.camouflage_protocol.send_data_fragments(
            (camouflage_return_b,),
            session=session_b,
        )
        assert (await camouflage_a.recv(timeout=1.0)).payload == camouflage_return_a
        assert (await camouflage_b.recv(timeout=1.0)).payload == camouflage_return_b
    finally:
        if udp_a_transport is not None:
            udp_a_transport.close()
        if udp_b_transport is not None:
            udp_b_transport.close()
        if tcp_a is not None:
            tcp_a.close()
            await tcp_a.wait_closed()
        if tcp_b is not None:
            tcp_b.close()
            await tcp_b.wait_closed()
        if camouflage_a is not None:
            camouflage_a.close()
            await camouflage_a.wait_closed()
        if camouflage_b is not None:
            camouflage_b.close()
            await camouflage_b.wait_closed()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_multi_session_tun_server_pump_returns_by_session() -> None:
    session_a = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pump-pqc-shared-secret-a".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"pump-client-nonce-a".ljust(32, b"c"),
        server_nonce=b"pump-server-nonce-a".ljust(32, b"s"),
    )
    session_b = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pump-pqc-shared-secret-b".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"pump-client-nonce-b".ljust(32, b"c"),
        server_nonce=b"pump-server-nonce-b".ljust(32, b"s"),
    )
    server_tun_a = MemoryTunDevice(mtu=900)
    server_tun_b = MemoryTunDevice(mtu=900)
    tun_handler = FirstPartyMultiSessionTunServerHandler(
        handlers={
            session_a.session_id: FirstPartyTunServerHandler(tun=server_tun_a),
            session_b.session_id: FirstPartyTunServerHandler(tun=server_tun_b),
        },
    )
    service = await open_firstparty_multi_session_dataplane_service(
        sessions=(session_a, session_b),
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_session_data=tun_handler,
    )
    tcp_a = None
    tcp_b = None
    try:
        assert service.tcp_protocol is not None
        tcp_a = await open_tcp_client(session=session_a, remote_addr=service.tcp_addr)
        tcp_b = await open_tcp_client(session=session_b, remote_addr=service.tcp_addr)
        packet_a = ipv4_packet(b"pump-user-a")
        packet_b = ipv4_packet(b"pump-user-b")
        tcp_a.send_data(packet_a)
        tcp_b.send_data(packet_b)
        await tcp_a.drain()
        await tcp_b.drain()
        assert await server_tun_a.read_written(timeout=1.0) == packet_a
        assert await server_tun_b.read_written(timeout=1.0) == packet_b

        pump_a = FirstPartyMultiSessionTunServerPump(
            session=session_a,
            tun=server_tun_a,
            server=service.tcp_protocol,
        )
        pump_b = FirstPartyMultiSessionTunServerPump(
            session=session_b,
            tun=server_tun_b,
            server=service.tcp_protocol,
        )
        response_a = ip_like_response(b"pump-return-a:", packet_a)
        response_b = ip_like_response(b"pump-return-b:", packet_b)
        server_tun_a.inject_packet(response_a)
        server_tun_b.inject_packet(response_b)
        await pump_a.send_one_from_tun(timeout=1.0)
        await pump_b.send_one_from_tun(timeout=1.0)

        assert (await tcp_a.recv(timeout=1.0)).payload == response_a
        assert (await tcp_b.recv(timeout=1.0)).payload == response_b
        assert pump_a.stats.packets_from_tun == 1
        assert pump_b.stats.packets_from_tun == 1
    finally:
        if tcp_a is not None:
            tcp_a.close()
            await tcp_a.wait_closed()
        if tcp_b is not None:
            tcp_b.close()
            await tcp_b.wait_closed()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_shared_tun_admission_return_pump_routes_by_destination_ip() -> None:
    class CapturingMultiSessionServer:
        def __init__(self) -> None:
            self.sent: list[tuple[int, tuple[bytes, ...]]] = []

        def send_data_fragments(
            self,
            payloads: tuple[bytes, ...],
            *,
            session: int,
        ) -> None:
            self.sent.append((session, tuple(payloads)))

    def packet_to(dst: bytes, payload: bytes) -> bytes:
        total_length = 20 + len(payload)
        return b"".join(
            (
                b"\x45\x00",
                total_length.to_bytes(2, "big"),
                b"\x00\x00",
                b"\x00\x00",
                b"\x40",
                b"\x11",
                b"\x00\x00",
                b"\x0a\x00\x00\x01",
                dst,
                payload,
            )
        )

    tun = MemoryTunDevice(mtu=900)
    server = CapturingMultiSessionServer()
    pump = FirstPartySharedTunAdmissionReturnPump(
        tun=tun,
        server=server,
        session_by_destination={
            "10.0.0.2": 1002,
            "10.0.0.3": 1003,
        },
    )
    packet_a = packet_to(b"\x0a\x00\x00\x02", b"client-a")
    packet_b = packet_to(b"\x0a\x00\x00\x03", b"client-b")
    packet_unknown = packet_to(b"\x0a\x00\x00\x63", b"client-unknown")

    tun.inject_packet(packet_a)
    await pump.send_one_from_tun(timeout=1.0)
    tun.inject_packet(packet_b)
    await pump.send_one_from_tun(timeout=1.0)
    tun.inject_packet(packet_unknown)
    with pytest.raises(FirstPartyTunPumpError, match="no destination session"):
        await pump.send_one_from_tun(timeout=1.0)

    assert server.sent == [
        (1002, (packet_a,)),
        (1003, (packet_b,)),
    ]
    assert pump.stats.packets_from_tun == 2
    assert pump.route_drops == 1
    assert pump.last_destination == "10.0.0.99"


async def wait_for_shared_return_pump_packets(
    resource: FirstPartyThreadedSharedTunAdmissionServerResource,
    expected: int,
    *,
    timeout: float = 1.0,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while resource.return_pump.stats.packets_from_tun < expected:
        if loop.time() >= deadline:
            break
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_threaded_shared_tun_admission_server_returns_by_client_lease() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_token = authority.issue(issue_request("vpn-client"), now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"shared-admission-client".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda _hello: b"shared-admission-server".ljust(32, b"s"),
        accepted_at_provider=lambda _hello: NOW,
    )
    server_tun = MemoryTunDevice(mtu=900)
    resource = open_threaded_firstparty_shared_tun_admission_server(
        registry=registry,
        tun=server_tun,
        destination_by_identity_hash={
            identity_binding_hash(client_token.claims).hex(): "10.0.0.2",
        },
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    managed = None
    try:
        assert isinstance(resource, FirstPartyThreadedSharedTunAdmissionServerResource)
        assert resource.service.tcp_addr is not None
        managed = await open_firstparty_admission_tun_client_bridge(
            hello=hello,
            pqc_material=material,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="shared-admission-tcp",
                    path_label="shared-admission",
                    transport="tcp",
                    remote_ref="shared-admission-private-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )
        packet = ipv4_packet(b"shared-admission-request")
        managed.bridge.tun.inject_packet(packet)
        await managed.send_one_from_tun(timeout=1.0)
        assert await server_tun.read_written(timeout=1.0) == packet

        session_id = managed.client.session.session_id
        assert resource.session_by_destination["10.0.0.2"].session_id == session_id
        return_packet = ip_like_response(b"shared-return:", packet)
        server_tun.inject_packet(return_packet)
        await managed.receive_one_to_tun(timeout=1.0)

        assert await managed.bridge.tun.read_written(timeout=1.0) == return_packet
        await wait_for_shared_return_pump_packets(resource, 1)
        assert resource.return_pump.stats.packets_from_tun == 1
        assert resource.lease_drops == 0
    finally:
        if managed is not None:
            await managed.close()
        resource.close()


@pytest.mark.asyncio
async def test_threaded_shared_tun_admission_server_handles_two_active_clients() -> None:
    authority = identity_authority()
    zero_trust_policy = ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"}))
    client_a_request = replace(
        issue_request("vpn-client"),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/vpn-client/client-a",
        did="did:mesh:pqc:vpn-client:client-a",
        device_id="vpn-client-a",
    )
    client_b_request = replace(
        issue_request("vpn-client"),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/vpn-client/client-b",
        did="did:mesh:pqc:vpn-client:client-b",
        device_id="vpn-client-b",
    )
    client_a_token = authority.issue(client_a_request, now=NOW)
    client_b_token = authority.issue(client_b_request, now=NOW)
    server_token = authority.issue(issue_request("vpn-server"), now=NOW)
    provider = LocalTestPqcProvider(issued_at=NOW - 60)
    hello_a, material_a = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_a_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"shared-client-a".ljust(32, b"c"),
        issued_at=NOW,
    )
    hello_b, material_b = create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=client_b_token,
        server_identity=server_token,
        deployment_epoch="test-epoch",
        client_nonce=b"shared-client-b".ljust(32, b"c"),
        issued_at=NOW,
    )
    store = FirstPartyHandshakeSecretStore()
    store.add(material_a)
    store.add(material_b)
    registry = FirstPartySessionAdmissionRegistry(
        server_identity=server_token,
        identity_authority=authority,
        policy=zero_trust_policy,
        shared_secret_resolver=store.resolve,
        server_nonce_provider=lambda hello: hashlib.sha256(
            b"shared-two-client-server-nonce" + hello.client_nonce
        ).digest(),
        accepted_at_provider=lambda _hello: NOW,
    )
    server_tun = MemoryTunDevice(mtu=900)

    def packet_to_client(dst: bytes, payload: bytes) -> bytes:
        total_length = 20 + len(payload)
        return b"".join(
            (
                b"\x45\x00",
                total_length.to_bytes(2, "big"),
                b"\x00\x00",
                b"\x00\x00",
                b"\x40",
                b"\x11",
                b"\x00\x00",
                b"\x0a\x00\x00\x01",
                dst,
                payload,
            )
        )

    resource = open_threaded_firstparty_shared_tun_admission_server(
        registry=registry,
        tun=server_tun,
        destination_by_identity_hash={
            identity_binding_hash(client_a_token.claims).hex(): "10.0.0.2",
            identity_binding_hash(client_b_token.claims).hex(): "10.0.0.3",
        },
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=False,
        ),
        return_transports=("tcp",),
        tun_read_timeout=0.02,
    )
    managed_a = None
    managed_b = None
    try:
        assert resource.service.tcp_addr is not None
        managed_a = await open_firstparty_admission_tun_client_bridge(
            hello=hello_a,
            pqc_material=material_a,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="shared-client-a",
                    path_label="shared-client-a",
                    transport="tcp",
                    remote_ref="shared-client-a-private-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )
        managed_b = await open_firstparty_admission_tun_client_bridge(
            hello=hello_b,
            pqc_material=material_b,
            tun=MemoryTunDevice(mtu=900),
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="shared-client-b",
                    path_label="shared-client-b",
                    transport="tcp",
                    remote_ref="shared-client-b-private-ref",
                    remote_addr=resource.service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
            ),
            identity_authority=authority,
            policy=zero_trust_policy,
            captured_at=NOW,
        )
        packet_a = ipv4_packet(b"request-from-a")
        packet_b = ipv4_packet(b"request-from-b")
        managed_a.bridge.tun.inject_packet(packet_a)
        managed_b.bridge.tun.inject_packet(packet_b)
        await managed_a.send_one_from_tun(timeout=1.0)
        await managed_b.send_one_from_tun(timeout=1.0)
        assert await server_tun.read_written(timeout=1.0) == packet_a
        assert await server_tun.read_written(timeout=1.0) == packet_b

        assert (
            resource.session_by_destination["10.0.0.2"].session_id
            == managed_a.client.session.session_id
        )
        assert (
            resource.session_by_destination["10.0.0.3"].session_id
            == managed_b.client.session.session_id
        )
        return_a = packet_to_client(b"\x0a\x00\x00\x02", b"return-to-a")
        return_b = packet_to_client(b"\x0a\x00\x00\x03", b"return-to-b")
        server_tun.inject_packet(return_a)
        server_tun.inject_packet(return_b)
        await managed_a.receive_one_to_tun(timeout=1.0)
        await managed_b.receive_one_to_tun(timeout=1.0)

        assert await managed_a.bridge.tun.read_written(timeout=1.0) == return_a
        assert await managed_b.bridge.tun.read_written(timeout=1.0) == return_b
        await wait_for_shared_return_pump_packets(resource, 2)
        assert resource.return_pump.stats.packets_from_tun == 2
        assert resource.return_pump.route_drops == 0
        assert resource.lease_drops == 0
    finally:
        if managed_a is not None:
            await managed_a.close()
        if managed_b is not None:
            await managed_b.close()
        resource.close()


@pytest.mark.asyncio
async def test_firstparty_dataplane_service_falls_back_when_tcp_port_is_busy() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    occupying_server = await asyncio.start_server(
        lambda _reader, _writer: None,
        host="127.0.0.1",
        port=0,
    )
    occupied_sock = occupying_server.sockets[0]
    occupied_port = int(occupied_sock.getsockname()[1])
    service = None
    try:
        service = await open_firstparty_dataplane_service(
            session=session,
            bind=FirstPartyDataplaneBind(
                host="127.0.0.1",
                udp_port=0,
                tcp_port=occupied_port,
                tcp_port_candidates=(0,),
                enable_udp=False,
                enable_tcp=True,
            ),
            on_data=lambda payload, _addr: b"bind-fallback:" + payload,
        )

        assert service.tcp_addr is not None
        assert service.tcp_addr[1] != occupied_port
        assert service.bind_evidence.passed is True
        assert len(service.bind_evidence.attempts) == 2
        assert service.bind_evidence.attempts[0].transport == "tcp"
        assert service.bind_evidence.attempts[0].opened is False
        assert service.bind_evidence.attempts[0].failure_reason is not None
        assert service.bind_evidence.attempts[1].transport == "tcp"
        assert service.bind_evidence.attempts[1].requested_ephemeral_port is True
        assert service.bind_evidence.attempts[1].opened is True
        encoded = json.dumps(service.bind_evidence.to_json_dict(), sort_keys=True)
        assert "127.0.0.1" not in encoded
        assert_privacy_safe(service.bind_evidence.to_json_dict())

        client = await open_tcp_client(session=session, remote_addr=service.tcp_addr)
        try:
            client.send_data(b"packet")
            await client.drain()
            response = await client.recv(timeout=1.0)
            assert response.frame_type == FrameType.DATA
            assert response.payload == b"bind-fallback:packet"
        finally:
            client.close()
            await client.wait_closed()
    finally:
        if service is not None:
            await service.close()
        occupying_server.close()
        await occupying_server.wait_closed()


@pytest.mark.asyncio
async def test_firstparty_dataplane_selector_falls_back_to_working_tcp_privately() -> None:
    with pytest.raises(DataplaneSelectionError):
        FirstPartyDataplaneSelector(
            session=establish_firstparty_session(
                kem_algorithm="ML-KEM-768",
                signature_algorithm="ML-DSA-65",
                pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
                client_identity=claims("vpn-client"),
                server_identity=claims("vpn-server"),
                policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
                now=NOW,
                client_nonce=b"client-nonce".ljust(32, b"c"),
                server_nonce=b"server-nonce".ljust(32, b"s"),
            ),
            candidates=(),
        )

    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
    )
    try:
        assert service.tcp_addr is not None
        blocked_udp = DataplaneEndpointCandidate(
            candidate_id="primary-udp-blocked",
            path_label="nl-udp",
            transport="udp",
            remote_ref="nl-primary-udp",
            remote_addr=("127.0.0.1", 1),
            priority=1,
            timeout_seconds=0.05,
        )
        working_tcp = DataplaneEndpointCandidate(
            candidate_id="fallback-tcp-open",
            path_label="nl-tcp",
            transport="tcp",
            remote_ref="nl-fallback-tcp",
            remote_addr=service.tcp_addr,
            priority=2,
            timeout_seconds=0.5,
        )

        outcome = await FirstPartyDataplaneSelector(
            session=session,
            candidates=(blocked_udp, working_tcp),
        ).select(captured_at=NOW)
        encoded = json.dumps(outcome.evidence.to_json_dict(), sort_keys=True)

        assert outcome.passed is True
        assert outcome.selected == working_tcp
        assert outcome.evidence.selected_candidate_hash == working_tcp.candidate_hash
        assert len(outcome.evidence.results) == 2
        assert outcome.evidence.results[0].success is False
        assert outcome.evidence.results[1].success is True
        assert "127.0.0.1" not in encoded
        assert "nl-primary-udp" not in encoded
        assert "nl-fallback-tcp" not in encoded
        assert "primary-udp-blocked" not in encoded
        assert "fallback-tcp-open" not in encoded
        assert_privacy_safe(outcome.evidence.to_json_dict())
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_dataplane_client_uses_selected_tcp_for_data_and_ping() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            enable_udp=False,
            enable_tcp=True,
        ),
        on_data=lambda payload, _addr: b"client-echo:" + payload,
    )
    client = None
    try:
        assert service.tcp_addr is not None
        client = await open_firstparty_dataplane_client(
            session=session,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="client-udp-blocked",
                    path_label="nl-udp",
                    transport="udp",
                    remote_ref="client-primary-udp",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="client-tcp-working",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="client-fallback-tcp",
                    remote_addr=service.tcp_addr,
                    priority=2,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
        )
        encoded = json.dumps(client.selection_evidence.to_json_dict(), sort_keys=True)

        assert client.transport == "tcp"
        assert client.selection_evidence.passed is True
        assert len(client.selection_evidence.results) == 2
        assert client.selection_evidence.results[0].success is False
        assert client.selection_evidence.results[1].success is True
        assert "127.0.0.1" not in encoded
        assert "client-primary-udp" not in encoded
        assert "client-fallback-tcp" not in encoded
        assert_privacy_safe(client.selection_evidence.to_json_dict())

        client.send_data(b"packet")
        await client.drain()
        data_response = await client.recv(timeout=1.0)
        assert data_response.frame_type == FrameType.DATA
        assert data_response.payload == b"client-echo:packet"

        client.send_ping(b"health")
        await client.drain()
        ping_response = await client.recv(timeout=1.0)
        assert ping_response.frame_type == FrameType.PONG
        assert ping_response.payload == b"health"
        assert client.stats.tx_frames >= 2
        assert client.stats.rx_frames >= 2
    finally:
        if client is not None:
            await client.close()
        await service.close()

    assert client is not None
    with pytest.raises(FirstPartyDataplaneClientError):
        client.send_ping(b"closed")


@pytest.mark.asyncio
async def test_firstparty_dataplane_client_uses_camouflage_fallback_for_data_and_ping() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=False,
            enable_camouflage=True,
        ),
        on_data=lambda payload, _addr: b"camouflage-client-echo:" + payload,
    )
    client = None
    try:
        assert service.camouflage_addr is not None
        client = await open_firstparty_dataplane_client(
            session=session,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="client-udp-blocked-before-camouflage",
                    path_label="restricted-udp",
                    transport="udp",
                    remote_ref="client-camouflage-primary-udp",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="client-tcp-blocked-before-camouflage",
                    path_label="restricted-tcp",
                    transport="tcp",
                    remote_ref="client-camouflage-primary-tcp",
                    remote_addr=("127.0.0.1", 1),
                    priority=2,
                    timeout_seconds=0.05,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="client-camouflage-working",
                    path_label="restricted-camouflage",
                    transport="camouflage",
                    remote_ref="client-camouflage-443",
                    remote_addr=service.camouflage_addr,
                    priority=3,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
        )
        encoded = json.dumps(client.selection_evidence.to_json_dict(), sort_keys=True)

        assert client.transport == "camouflage"
        assert client.selection_evidence.passed is True
        assert len(client.selection_evidence.results) == 3
        assert client.selection_evidence.results[0].success is False
        assert client.selection_evidence.results[1].success is False
        assert client.selection_evidence.results[2].success is True
        assert "127.0.0.1" not in encoded
        assert "client-camouflage-primary-udp" not in encoded
        assert "client-camouflage-primary-tcp" not in encoded
        assert "client-camouflage-443" not in encoded
        assert_privacy_safe(client.selection_evidence.to_json_dict())

        client.send_data(b"packet")
        await client.drain()
        data_response = await client.recv(timeout=1.0)
        assert data_response.frame_type == FrameType.DATA
        assert data_response.payload == b"camouflage-client-echo:packet"

        client.send_ping(b"health")
        await client.drain()
        ping_response = await client.recv(timeout=1.0)
        assert ping_response.frame_type == FrameType.PONG
        assert ping_response.payload == b"health"
    finally:
        if client is not None:
            await client.close()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_dataplane_client_continues_failover_after_open_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )
    service = await open_firstparty_dataplane_service(
        session=session,
        bind=FirstPartyDataplaneBind(
            host="127.0.0.1",
            udp_port=0,
            tcp_port=0,
            camouflage_port=0,
            enable_udp=False,
            enable_tcp=True,
            enable_camouflage=True,
        ),
        on_data=lambda payload, _addr: b"open-failover:" + payload,
    )
    client = None

    async def fail_tcp_open(**_kwargs: object) -> object:
        raise ConnectionError("simulated selected transport open failure")

    monkeypatch.setattr("src.network.firstparty_vpn.client.open_tcp_client", fail_tcp_open)
    try:
        assert service.tcp_addr is not None
        assert service.camouflage_addr is not None
        client = await open_firstparty_dataplane_client(
            session=session,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="client-tcp-probes-then-open-fails",
                    path_label="work-tcp",
                    transport="tcp",
                    remote_ref="client-open-failover-tcp-private-ref",
                    remote_addr=service.tcp_addr,
                    priority=1,
                    timeout_seconds=0.5,
                ),
                DataplaneEndpointCandidate(
                    candidate_id="client-camouflage-opens-after-tcp-failure",
                    path_label="work-camouflage",
                    transport="camouflage",
                    remote_ref="client-open-failover-camouflage-private-ref",
                    remote_addr=service.camouflage_addr,
                    priority=2,
                    timeout_seconds=0.5,
                ),
            ),
            captured_at=NOW,
        )
        encoded_selection = json.dumps(
            client.selection_evidence.to_json_dict(),
            sort_keys=True,
        )
        assert client.open_evidence is not None
        encoded_open = json.dumps(client.open_evidence.to_json_dict(), sort_keys=True)

        assert client.transport == "camouflage"
        assert client.selection_evidence.passed is True
        assert len(client.selection_evidence.results) == 2
        assert client.selection_evidence.results[0].success is True
        assert client.selection_evidence.results[1].success is True
        assert client.open_evidence.passed is True
        assert client.open_evidence.attempts[0].opened is False
        assert client.open_evidence.attempts[0].failure_reason == "ConnectionError"
        assert client.open_evidence.attempts[1].opened is True
        assert client.open_evidence.selected_candidate_hash == client.selected.candidate_hash
        assert "127.0.0.1" not in encoded_selection
        assert "127.0.0.1" not in encoded_open
        assert "client-open-failover-tcp-private-ref" not in encoded_selection
        assert "client-open-failover-tcp-private-ref" not in encoded_open
        assert "client-open-failover-camouflage-private-ref" not in encoded_selection
        assert "client-open-failover-camouflage-private-ref" not in encoded_open
        assert "client-tcp-probes-then-open-fails" not in encoded_selection
        assert "client-tcp-probes-then-open-fails" not in encoded_open
        assert "client-camouflage-opens-after-tcp-failure" not in encoded_selection
        assert "client-camouflage-opens-after-tcp-failure" not in encoded_open
        assert_privacy_safe(client.selection_evidence.to_json_dict())
        assert_privacy_safe(client.open_evidence.to_json_dict())

        client.send_data(b"packet")
        await client.drain()
        data_response = await client.recv(timeout=1.0)
        assert data_response.frame_type == FrameType.DATA
        assert data_response.payload == b"open-failover:packet"
    finally:
        if client is not None:
            await client.close()
        await service.close()


@pytest.mark.asyncio
async def test_firstparty_dataplane_client_fails_closed_with_selection_evidence() -> None:
    session = establish_firstparty_session(
        kem_algorithm="ML-KEM-768",
        signature_algorithm="ML-DSA-65",
        pqc_shared_secret=b"pqc-shared-secret".ljust(48, b"-"),
        client_identity=claims("vpn-client"),
        server_identity=claims("vpn-server"),
        policy=ZeroTrustPolicy(allowed_tenants=frozenset({"team-a"})),
        now=NOW,
        client_nonce=b"client-nonce".ljust(32, b"c"),
        server_nonce=b"server-nonce".ljust(32, b"s"),
    )

    with pytest.raises(FirstPartyDataplaneClientError) as exc:
        await open_firstparty_dataplane_client(
            session=session,
            candidates=(
                DataplaneEndpointCandidate(
                    candidate_id="client-tcp-closed",
                    path_label="nl-tcp",
                    transport="tcp",
                    remote_ref="client-closed-tcp",
                    remote_addr=("127.0.0.1", 1),
                    priority=1,
                    timeout_seconds=0.05,
                ),
            ),
            captured_at=NOW,
        )

    evidence = exc.value.selection_evidence
    assert evidence is not None
    assert evidence.passed is False
    assert len(evidence.results) == 1
    assert evidence.results[0].success is False
    encoded = json.dumps(evidence.to_json_dict(), sort_keys=True)
    assert "127.0.0.1" not in encoded
    assert "client-closed-tcp" not in encoded
    assert "client-tcp-closed" not in encoded
    assert_privacy_safe(evidence.to_json_dict())


def test_rollout_gate_requires_tests_approval_rollback_and_policy_hash() -> None:
    test_evidence = TestEvidence(
        command=("pytest", "tests/unit/network/test_firstparty_vpn_protocol_unit.py"),
        passed=41,
        failed=0,
        collected=41,
        generated_at=NOW,
    )
    approval = OperatorApproval(
        approval_id="approval-1",
        approved_by_hash=hash_identifier("operator-1", namespace="operator"),
        scope="nl-rollout",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
    )
    plan = RolloutPlan(
        target="nl-rollout",
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        test_evidence=test_evidence,
        approval=approval,
        policy_snapshot_hash="a" * 64,
        preflight_evidence=successful_preflight(),
    )

    decision = evaluate_rollout_gate(plan, expected_test_count=41, now=NOW)

    assert decision.allowed is True
    assert decision.reasons == ()
    assert len(decision.evidence_hash) == 64
    assert plan.apply_evidence().command_count == 1

    blocked = evaluate_rollout_gate(
        RolloutPlan(
            target="nl-rollout",
            apply_commands=(("echo", "private_key=abc"),),
            rollback_commands=(),
            test_evidence=TestEvidence(
                command=("pytest",),
                passed=40,
                failed=1,
                collected=41,
                generated_at=NOW,
            ),
            approval=None,
            policy_snapshot_hash=None,
        ),
        expected_test_count=41,
        now=NOW,
    )
    assert blocked.allowed is False
    assert "rollback_plan_missing" in blocked.reasons
    assert "tests_not_successful" in blocked.reasons
    assert "operator_approval_missing" in blocked.reasons
    assert "policy_snapshot_hash_missing" in blocked.reasons
    assert "linux_preflight_missing" in blocked.reasons
    assert "command_plan_contains_sensitive_material" in blocked.reasons


def test_rollout_gate_hash_binds_operator_approval_evidence() -> None:
    test_evidence = TestEvidence(
        command=("pytest", "tests/unit/network/test_firstparty_vpn_protocol_unit.py"),
        passed=41,
        failed=0,
        collected=41,
        generated_at=NOW,
    )
    approval = OperatorApproval(
        approval_id="approval-1",
        approved_by_hash=hash_identifier("operator-1", namespace="operator"),
        scope="nl-rollout",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
    )
    plan = RolloutPlan(
        target="nl-rollout",
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        test_evidence=test_evidence,
        approval=approval,
        policy_snapshot_hash="a" * 64,
        preflight_evidence=successful_preflight(),
    )

    baseline = evaluate_rollout_gate(plan, expected_test_count=41, now=NOW)
    changed_approval_id = evaluate_rollout_gate(
        replace(
            plan,
            approval=replace(approval, approval_id="approval-2"),
        ),
        expected_test_count=41,
        now=NOW,
    )
    changed_approver = evaluate_rollout_gate(
        replace(
            plan,
            approval=replace(
                approval,
                approved_by_hash=hash_identifier("operator-2", namespace="operator"),
            ),
        ),
        expected_test_count=41,
        now=NOW,
    )

    assert baseline.allowed is True
    assert changed_approval_id.allowed is True
    assert changed_approver.allowed is True
    assert baseline.evidence_hash != changed_approval_id.evidence_hash
    assert baseline.evidence_hash != changed_approver.evidence_hash
    assert "operator-1" not in json.dumps(approval.to_json_dict(), sort_keys=True)


def test_rollout_gate_hash_binds_gate_requirements_and_evaluation_time() -> None:
    test_evidence = TestEvidence(
        command=("pytest", "tests/unit/network/test_firstparty_vpn_protocol_unit.py"),
        passed=41,
        failed=0,
        collected=41,
        generated_at=NOW,
    )
    approval = OperatorApproval(
        approval_id="approval-1",
        approved_by_hash=hash_identifier("operator-1", namespace="operator"),
        scope="nl-rollout",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
    )
    plan = RolloutPlan(
        target="nl-rollout",
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        test_evidence=test_evidence,
        approval=approval,
        policy_snapshot_hash="a" * 64,
        preflight_evidence=successful_preflight(),
    )

    baseline = evaluate_rollout_gate(plan, expected_test_count=41, now=NOW)
    lower_test_requirement = evaluate_rollout_gate(
        plan,
        expected_test_count=40,
        now=NOW,
    )
    required_path_requirement = evaluate_rollout_gate(
        plan,
        expected_test_count=41,
        required_dataplane_paths=frozenset({"lan"}),
        now=NOW,
    )
    later_evaluation = evaluate_rollout_gate(
        plan,
        expected_test_count=41,
        now=NOW + 1,
    )

    assert baseline.allowed is True
    assert lower_test_requirement.allowed is True
    assert required_path_requirement.allowed is False
    assert later_evaluation.allowed is True
    assert baseline.evidence_hash != lower_test_requirement.evidence_hash
    assert baseline.evidence_hash != required_path_requirement.evidence_hash
    assert baseline.evidence_hash != later_evaluation.evidence_hash
    assert "dataplane_evidence_missing" in required_path_requirement.reasons


def test_rollout_gate_rejects_stale_or_future_test_evidence() -> None:
    approval = OperatorApproval(
        approval_id="approval-1",
        approved_by_hash=hash_identifier("operator-1", namespace="operator"),
        scope="nl-rollout",
        issued_at=NOW - 60,
        expires_at=NOW + 600,
    )
    plan = RolloutPlan(
        target="nl-rollout",
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        test_evidence=TestEvidence(
            command=("pytest",),
            passed=41,
            failed=0,
            collected=41,
            generated_at=NOW,
        ),
        approval=approval,
        policy_snapshot_hash="a" * 64,
        preflight_evidence=successful_preflight(),
    )

    fresh = evaluate_rollout_gate(
        plan,
        expected_test_count=41,
        max_test_evidence_age_seconds=300,
        now=NOW,
    )
    stale = evaluate_rollout_gate(
        replace(
            plan,
            test_evidence=replace(plan.test_evidence, generated_at=NOW - 301),
        ),
        expected_test_count=41,
        max_test_evidence_age_seconds=300,
        now=NOW,
    )
    future = evaluate_rollout_gate(
        replace(
            plan,
            test_evidence=replace(plan.test_evidence, generated_at=NOW + 1),
        ),
        expected_test_count=41,
        max_test_evidence_age_seconds=300,
        now=NOW,
    )

    assert fresh.allowed is True
    assert stale.allowed is False
    assert "test_evidence_stale" in stale.reasons
    assert future.allowed is False
    assert "test_evidence_from_future" in future.reasons
    with pytest.raises(OperationalEvidenceError, match="test evidence age"):
        evaluate_rollout_gate(
            plan,
            expected_test_count=41,
            max_test_evidence_age_seconds=0,
            now=NOW,
        )
    with pytest.raises(ValueError, match="generation time"):
        TestEvidence(
            command=("pytest",),
            passed=1,
            failed=0,
            collected=1,
            generated_at=-1,
        )


@pytest.mark.asyncio
async def test_rollout_gate_requires_external_path_evidence() -> None:
    plan = dataplane_validation_plan()

    async def runner(probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        return DataplaneProbeResult.success_result(probe, latency_millis=7)

    dataplane_evidence = await evaluate_dataplane_validation(
        plan=plan,
        runner=runner,
        captured_at=NOW,
    )
    tun_dataplane_evidence = TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_tun_probe_result(probe) for probe in plan.probes),
        captured_at=NOW,
    )
    mtu_validation_evidence = MtuValidationEvidence.from_results(
        plan=plan,
        results=tuple(_successful_mtu_probe_result(probe) for probe in plan.probes),
        captured_at=NOW,
    )
    rollout_plan = RolloutPlan(
        target="nl-rollout",
        apply_commands=(("ip", "link", "set", "dev", "x0vpn0", "up"),),
        rollback_commands=(("nft", "delete", "table", "inet", "x0vpn"),),
        test_evidence=TestEvidence(
            command=("pytest",),
            passed=66,
            failed=0,
            collected=66,
            generated_at=NOW,
        ),
        approval=OperatorApproval(
            approval_id="approval-1",
            approved_by_hash=hash_identifier("operator-1", namespace="operator"),
            scope="nl-rollout",
            issued_at=NOW - 60,
            expires_at=NOW + 600,
        ),
        policy_snapshot_hash="a" * 64,
        preflight_evidence=successful_preflight(),
        dataplane_evidence=dataplane_evidence,
        tun_dataplane_evidence=tun_dataplane_evidence,
        mtu_validation_evidence=mtu_validation_evidence,
    )

    allowed = evaluate_rollout_gate(
        rollout_plan,
        expected_test_count=66,
        required_dataplane_paths=plan.required_path_labels,
        now=NOW,
    )
    blocked = evaluate_rollout_gate(
        replace(
            rollout_plan,
            dataplane_evidence=None,
            tun_dataplane_evidence=None,
            mtu_validation_evidence=None,
        ),
        expected_test_count=66,
        required_dataplane_paths=plan.required_path_labels,
        now=NOW,
    )

    assert allowed.allowed is True
    assert allowed.reasons == ()
    assert blocked.allowed is False
    assert "dataplane_evidence_missing" in blocked.reasons
    assert "tun_dataplane_evidence_missing" in blocked.reasons
    assert "mtu_evidence_missing" in blocked.reasons


def test_privacy_safe_audit_log_redacts_networks_and_rejects_secrets(
    tmp_path: Path,
) -> None:
    command = ("ip", "route", "replace", "203.0.113.10/32", "dev", "x0vpn0")
    redacted_command = redact_command(command)
    event = PrivacySafeAuditEvent(
        event_type="rollout_gate",
        outcome="allowed",
        occurred_at=NOW,
        actor_hash=hash_identifier("operator-1", namespace="operator"),
        subject_hash=hash_identifier("nl-rollout", namespace="target"),
        metadata={"redacted_command": list(redacted_command)},
    )
    log = PrivacySafeAuditLog(tmp_path / "audit.jsonl")

    event_hash = log.append(event)
    events = log.read_events()

    assert len(event_hash) == 64
    assert events[0]["metadata"] == {"redacted_command": list(redacted_command)}
    assert "203.0.113.10" not in log.path.read_text(encoding="utf-8")
    assert "<network-redacted>" in redacted_command
    with pytest.raises(OperationalEvidenceError):
        PrivacySafeAuditEvent(
            event_type="rollout_gate",
            outcome="blocked",
            occurred_at=NOW,
            actor_hash=hash_identifier("operator-1", namespace="operator"),
            subject_hash=hash_identifier("nl-rollout", namespace="target"),
            metadata={"private_key": "do-not-log"},
        )


def test_metrics_snapshot_contains_counters_without_payloads() -> None:
    runtime = RuntimeStats(
        rx_frames=3,
        tx_frames=4,
        rx_data_frames=2,
        tx_data_frames=2,
        rx_bytes=300,
        tx_bytes=400,
        auth_drops=1,
    )
    tun_stats = TunBridgeStats(
        packets_from_tun=2,
        packets_to_tun=1,
        bytes_from_tun=200,
        bytes_to_tun=100,
        tx_fragments=3,
        rx_fragments=2,
    )
    snapshot = MetricsSnapshot(runtime=runtime, tun=tun_stats, captured_at=NOW)
    payload = snapshot.to_json_dict()

    assert payload["runtime"]["rx_frames"] == 3
    assert payload["runtime"]["auth_drops"] == 1
    assert payload["tun"]["tx_fragments"] == 3
    assert_privacy_safe(payload)


def test_firstparty_package_does_not_embed_third_party_vpn_markers() -> None:
    package_dir = Path("src/network/firstparty_vpn")
    forbidden = ("vless://", "vmess://", "trojan://", "ss://")

    text = "\n".join(path.read_text(encoding="utf-8") for path in package_dir.glob("*.py"))

    for marker in forbidden:
        assert marker not in text.lower()
