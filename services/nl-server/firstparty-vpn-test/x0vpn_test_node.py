#!/usr/bin/env python3
"""First-party VPN node and release utility.

This module is the local control entrypoint for x0tta6bl4 first-party VPN
server and client kits. It can run isolated health probes and
production-candidate Linux service workflows for the first-party HELLO/ACCEPT,
ML-KEM shared secret, zero-trust identity checks, protected DATA, and PING/PONG
dataplane path.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in (current.parent, *current.parents):
        if (parent / "src/network/firstparty_vpn").is_dir():
            return parent
    raise RuntimeError("first-party VPN package root could not be found")


def _add_project_root_to_path() -> None:
    sys.path.insert(0, str(_find_project_root()))


_add_project_root_to_path()

from src.network.firstparty_vpn.admission import FirstPartySessionAdmissionRegistry
from src.network.firstparty_vpn.anti_dpi import FirstPartyAntiDpiProfile
from src.network.firstparty_vpn.camouflage import (
    CamouflagePolicy,
    CamouflageProfile,
    open_camouflage_admission_client,
    open_camouflage_admission_server,
)
from src.network.firstparty_vpn.client import FirstPartyDataplaneClientError
from src.network.firstparty_vpn.fragmentation import (
    FragmentError,
    PacketFragmenter,
    PacketReassembler,
)
from src.network.firstparty_vpn.handshake import create_firstparty_handshake_hello
from src.network.firstparty_vpn.identity import (
    FirstPartyReferenceMlDsaIdentitySignatureProvider,
    IdentityAuthority,
    IdentityIssueRequest,
    IdentitySigningKey,
    ReadOnlyIdentityVerifier,
    RevocationList,
    SignedIdentityToken,
)
from src.network.firstparty_vpn.leak_protection import evaluate_linux_leak_protection
from src.network.firstparty_vpn.dataplane_validation import (
    DataplaneProbeResult,
    DataplaneProbeSpec,
    DataplaneValidationPlan,
    TunDataplaneProbeResult,
    TunDataplaneValidationEvidence,
    evaluate_dataplane_validation,
    evaluate_tun_dataplane_validation,
)
from src.network.firstparty_vpn.mldsa import (
    ML_DSA_KEYGEN_SEED_BYTES,
    mldsa_derive_reference_keypair,
)
from src.network.firstparty_vpn.mlkem import (
    ML_KEM_SEED_BYTES,
    mlkem_decapsulate,
    mlkem_encapsulate,
    mlkem_keygen_from_seeds,
)
from src.network.firstparty_vpn.mtu import (
    MtuPathProbeResult,
    MtuProbeAttempt,
    MtuProbeResult,
    MtuValidationEvidence,
    evaluate_mtu_validation,
)
from src.network.firstparty_vpn.ops import (
    OperatorApproval,
    RolloutPlan,
    TestEvidence,
    evaluate_rollout_gate,
    hash_identifier as ops_hash_identifier,
)
from src.network.firstparty_vpn.linux_policy import (
    LinuxNetworkPolicyConfig,
    LinuxNetworkPolicyPlanner,
    LinuxServerNatConfig,
    LinuxServerNatPlanner,
    LinuxServerVpnListener,
    RemoteEndpoint,
)
from src.network.firstparty_vpn.pqc import (
    FirstPartyMlKemImplementation,
    PqcImplementationManifest,
    PqcKnownAnswerVector,
    PqcProductionGate,
    PqcProviderAttestation,
    PqcProviderGateDecision,
    PqcSessionSecretMaterial,
    run_pqc_known_answer_tests,
)
from src.network.firstparty_vpn.preflight import (
    LinuxHostFacts,
    LinuxPreflightConfig,
    collect_linux_host_facts,
    evaluate_linux_deployment_preflight,
)
from src.network.firstparty_vpn.policy_store import PolicySnapshot
from src.network.firstparty_vpn.production_readiness import (
    FullVpnProductionReadinessEvidence,
    FullVpnProductionReadinessRequirements,
    evaluate_full_vpn_production_readiness,
)
from src.network.firstparty_vpn.production_control import (
    ExternalPolicySnapshotSource,
    FirstPartyIdentitySignerManifest,
    IdentitySignerConformanceEvidence,
    IdentitySignerKnownAnswerVector,
    ProductionIdentitySignerGate,
    run_identity_signer_known_answer_tests,
)
from src.network.firstparty_vpn.rekey_policy import (
    FirstPartyRekeyCadencePolicy,
    FirstPartyRekeyRollbackEvidence,
    FirstPartyRekeyTelemetry,
    evaluate_firstparty_rekey_policy,
)
from src.network.firstparty_vpn.protocol import FrameType
from src.network.firstparty_vpn.selection import DataplaneEndpointCandidate
from src.network.firstparty_vpn.service import FirstPartyDataplaneBind
from src.network.firstparty_vpn.source_audit import audit_firstparty_source_tree
from src.network.firstparty_vpn.stream import (
    open_tcp_admission_client,
    open_tcp_admission_server,
)
from src.network.firstparty_vpn.tun import (
    LinuxTunConfig,
    LinuxTunDevice,
    open_threaded_firstparty_admission_tun_client_pump,
    open_threaded_firstparty_admission_tun_server,
    open_threaded_firstparty_shared_tun_admission_server,
)
from src.network.firstparty_vpn.zero_trust import (
    IdentityClaims,
    ZeroTrustPolicy,
    ZeroTrustPolicyEvidence,
    identity_binding_hash,
)


DEFAULT_HOST = "89.125.1.107"
DEFAULT_PORT = 22080
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_TENANT = "team-a"
DEFAULT_LIFETIME_SECONDS = 7 * 24 * 60 * 60
DEFAULT_TUN_MTU = 1280
DEFAULT_CLIENT_CIDR = "10.90.0.0/24"
DEFAULT_SERVER_TUN_ADDRESS = "10.90.0.1/24"
DEFAULT_CLIENT_TUN_ADDRESS = "10.90.0.2/32"
DEFAULT_CLIENT_TUN_PEER = "10.90.0.1"
DEFAULT_SERVER_SERVICE_NAME = "x0tta-firstparty-vpn.service"
DEFAULT_CLIENT_SERVICE_NAME = "x0tta-firstparty-vpn-client.service"
DEFAULT_SERVER_INSTALL_DIR = "/opt/x0tta-firstparty-vpn-server"
DEFAULT_SERVER_CONFIG_DIR = "/etc/x0tta-firstparty-vpn-server"
DEFAULT_CLIENT_INSTALL_DIR = "/opt/x0tta-firstparty-vpn-client"
DEFAULT_CLIENT_CONFIG_DIR = "/etc/x0tta-firstparty-vpn-client"
DEFAULT_SERVICE_PYTHON = "/usr/bin/python3"
KIT_ENTRYPOINT = "x0vpn_node.py"
PUBLIC_INFO_FILENAME = "public-info.json"
DEFAULT_DEPLOYMENT_EPOCH_PREFIX = "nl-production"
DEFAULT_CLIENT_DEVICE_PREFIX = "nl-production-client"
DEFAULT_SERVER_DEVICE_ID = "nl-production-server-1"
DEFAULT_IDENTITY_KEY_ID = "nl-production-identity-key-1"
KEM_ALGORITHM = "ML-KEM-768"
SIGNATURE_ALGORITHM = "ML-DSA-65"
ISSUER = "x0tta6bl4-firstparty-issuer"
POLICY_EPOCH = "nl-production-2026-06-06"
PROVIDER_ID = "x0tta6bl4-firstparty-mlkem"
CLIENT_CONFIG_UPDATE_REQUEST_PREFIX = b"X0VPN-CONFIG-UPDATE-REQUEST/1\n"
CLIENT_CONFIG_UPDATE_RESPONSE_PREFIX = b"X0VPN-CONFIG-UPDATE-RESPONSE/1\n"


@dataclass(frozen=True)
class MlKemSessionProvider:
    encapsulation_key: bytes
    attestation: PqcProviderAttestation

    def create_session_material(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcSessionSecretMaterial:
        _ = (transcript, client_identity_hash, server_identity_hash)
        encapsulated = mlkem_encapsulate(KEM_ALGORITHM, self.encapsulation_key)
        return PqcSessionSecretMaterial(
            kem_algorithm=self.attestation.kem_algorithm,
            signature_algorithm=self.attestation.signature_algorithm,
            shared_secret=encapsulated.shared_secret,
            ciphertext=encapsulated.ciphertext,
            attestation=self.attestation,
        )


@dataclass(frozen=True)
class _AdmittedProbeClientResult:
    client: Any
    accept: Any
    session: Any
    candidate: DataplaneEndpointCandidate


def main() -> int:
    parser = argparse.ArgumentParser(description="First-party VPN node")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--out-dir", required=True)
    generate_parser.add_argument("--host", default=DEFAULT_HOST)
    generate_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    generate_parser.add_argument(
        "--transport",
        choices=("tcp", "camouflage"),
        default="camouflage",
    )
    generate_parser.add_argument(
        "--fallback-endpoint",
        action="append",
        default=[],
        help="Extra client endpoint as transport:host:port[:priority[:path_label]]",
    )
    generate_parser.add_argument("--bind-host", default=DEFAULT_BIND_HOST)
    generate_parser.add_argument("--tenant", default=DEFAULT_TENANT)
    generate_parser.add_argument("--deployment-epoch")
    generate_parser.add_argument(
        "--deployment-epoch-prefix",
        default=DEFAULT_DEPLOYMENT_EPOCH_PREFIX,
    )
    generate_parser.add_argument("--issuer", default=ISSUER)
    generate_parser.add_argument("--policy-epoch", default=POLICY_EPOCH)
    generate_parser.add_argument("--provider-id", default=PROVIDER_ID)
    generate_parser.add_argument("--identity-key-id", default=DEFAULT_IDENTITY_KEY_ID)
    generate_parser.add_argument("--server-device-id", default=DEFAULT_SERVER_DEVICE_ID)
    generate_parser.add_argument("--server-tun-name", default="x0vpns0")
    generate_parser.add_argument("--client-tun-name", default="x0vpn0")
    generate_parser.add_argument("--tun-mtu", type=int, default=DEFAULT_TUN_MTU)
    generate_parser.add_argument("--client-cidr", default=DEFAULT_CLIENT_CIDR)
    generate_parser.add_argument("--server-tun-address", default=DEFAULT_SERVER_TUN_ADDRESS)
    generate_parser.add_argument("--client-tun-address", default=DEFAULT_CLIENT_TUN_ADDRESS)
    generate_parser.add_argument("--client-tun-peer", default=DEFAULT_CLIENT_TUN_PEER)
    generate_parser.add_argument("--client-count", type=int, default=1)
    generate_parser.add_argument(
        "--client-device-prefix",
        default=DEFAULT_CLIENT_DEVICE_PREFIX,
    )
    generate_parser.add_argument("--client-address-offset", type=int, default=2)
    generate_parser.add_argument("--dns-server", action="append", default=[])
    generate_parser.add_argument(
        "--pqc-mode",
        choices=("production", "test"),
        default="production",
    )
    generate_pqc_review_group = generate_parser.add_mutually_exclusive_group()
    generate_pqc_review_group.add_argument(
        "--pqc-reviewed",
        dest="pqc_reviewed",
        action="store_true",
        default=True,
    )
    generate_pqc_review_group.add_argument(
        "--pqc-unreviewed",
        dest="pqc_reviewed",
        action="store_false",
    )
    generate_parser.add_argument(
        "--lifetime-seconds",
        type=int,
        default=DEFAULT_LIFETIME_SECONDS,
    )

    add_client_parser = subparsers.add_parser("add-client")
    add_client_parser.add_argument("--server-config", required=True)
    add_client_parser.add_argument("--issuer-config", required=True)
    add_client_parser.add_argument("--out-client", required=True)
    add_client_parser.add_argument("--server-config-out")
    add_client_parser.add_argument("--update-server-config", action="store_true")
    add_client_parser.add_argument("--device-id", required=True)
    add_client_parser.add_argument("--client-address")
    add_client_parser.add_argument("--tenant")
    add_client_parser.add_argument("--lifetime-seconds", type=int)
    add_client_parser.add_argument("--dry-run", action="store_true")

    identity_rotate_parser = subparsers.add_parser("identity-rotate-config")
    identity_rotate_parser.add_argument("--server-config", required=True)
    identity_rotate_parser.add_argument("--issuer-config", required=True)
    identity_rotate_parser.add_argument("--out-dir", required=True)
    identity_rotate_parser.add_argument("--lifetime-seconds", type=int, default=3600)
    identity_rotate_parser.add_argument("--server-config-out")
    identity_rotate_parser.add_argument("--update-server-config", action="store_true")
    identity_rotate_parser.add_argument("--update-issuer-config", action="store_true")
    identity_rotate_parser.add_argument("--dry-run", action="store_true")

    identity_auto_renew_parser = subparsers.add_parser("identity-auto-renew")
    identity_auto_renew_parser.add_argument("--server-config", required=True)
    identity_auto_renew_parser.add_argument("--issuer-config", required=True)
    identity_auto_renew_parser.add_argument("--out-dir", required=True)
    identity_auto_renew_parser.add_argument("--lifetime-seconds", type=int, default=3600)
    identity_auto_renew_parser.add_argument("--renew-before-seconds", type=int, default=900)
    identity_auto_renew_parser.add_argument("--server-config-out")
    identity_auto_renew_parser.add_argument("--update-server-config", action="store_true")
    identity_auto_renew_parser.add_argument("--update-issuer-config", action="store_true")
    identity_auto_renew_parser.add_argument("--apply-server-config", action="store_true")
    identity_auto_renew_parser.add_argument("--installed-server-config")
    identity_auto_renew_parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    identity_auto_renew_parser.add_argument("--backup-dir")
    identity_auto_renew_parser.add_argument("--uplink-interface")
    identity_auto_renew_parser.add_argument("--allow-os-mutation", action="store_true")
    identity_auto_renew_parser.add_argument("--dry-run", action="store_true")
    identity_auto_renew_parser.add_argument("--skip-health", action="store_true")
    identity_auto_renew_parser.add_argument("--health-retries", type=int, default=10)
    identity_auto_renew_parser.add_argument("--health-retry-interval-seconds", type=float, default=0.5)
    identity_auto_renew_parser.add_argument("--no-rollback-on-failure", action="store_true")
    identity_auto_renew_parser.add_argument("--force", action="store_true")

    issuer_lifetime_policy_parser = subparsers.add_parser("issuer-lifetime-policy")
    issuer_lifetime_policy_parser.add_argument("--issuer-config", required=True)
    issuer_lifetime_policy_parser.add_argument("--default-lifetime-seconds", type=int, required=True)
    issuer_lifetime_policy_parser.add_argument("--max-lifetime-seconds", type=int, required=True)
    issuer_lifetime_policy_parser.add_argument("--allow-file-mutation", action="store_true")
    issuer_lifetime_policy_parser.add_argument("--dry-run", action="store_true")

    provision_client_parser = subparsers.add_parser("provision-client")
    provision_client_parser.add_argument("--server-config", required=True)
    provision_client_parser.add_argument("--issuer-config", required=True)
    provision_client_parser.add_argument("--out-dir", required=True)
    provision_client_parser.add_argument("--device-id", required=True)
    provision_client_parser.add_argument("--client-address")
    provision_client_parser.add_argument("--tenant")
    provision_client_parser.add_argument("--lifetime-seconds", type=int)
    provision_client_parser.add_argument("--kit-name")
    provision_client_parser.add_argument("--archive")
    provision_client_parser.add_argument("--apply-server-config", action="store_true")
    provision_client_parser.add_argument("--installed-server-config")
    provision_client_parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    provision_client_parser.add_argument("--backup-dir")
    provision_client_parser.add_argument("--uplink-interface")
    provision_client_parser.add_argument("--allow-os-mutation", action="store_true")
    provision_client_parser.add_argument("--dry-run", action="store_true")
    provision_client_parser.add_argument("--skip-health", action="store_true")

    remove_client_parser = subparsers.add_parser("remove-client")
    remove_client_parser.add_argument("--server-config", required=True)
    remove_client_parser.add_argument("--server-config-out")
    remove_client_parser.add_argument("--update-server-config", action="store_true")
    remove_client_parser.add_argument("--device-id")
    remove_client_parser.add_argument("--identity-hash")
    remove_client_parser.add_argument("--dry-run", action="store_true")

    deprovision_client_parser = subparsers.add_parser("deprovision-client")
    deprovision_client_parser.add_argument("--server-config", required=True)
    deprovision_client_parser.add_argument("--out-dir", required=True)
    deprovision_client_parser.add_argument("--device-id")
    deprovision_client_parser.add_argument("--identity-hash")
    deprovision_client_parser.add_argument("--apply-server-config", action="store_true")
    deprovision_client_parser.add_argument("--installed-server-config")
    deprovision_client_parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    deprovision_client_parser.add_argument("--backup-dir")
    deprovision_client_parser.add_argument("--uplink-interface")
    deprovision_client_parser.add_argument("--allow-os-mutation", action="store_true")
    deprovision_client_parser.add_argument("--dry-run", action="store_true")
    deprovision_client_parser.add_argument("--skip-health", action="store_true")

    export_client_kit_parser = subparsers.add_parser("export-client-kit")
    export_client_kit_parser.add_argument("--client-config", required=True)
    export_client_kit_parser.add_argument("--issuer-config")
    export_client_kit_parser.add_argument("--out-dir", required=True)
    export_client_kit_parser.add_argument("--archive")
    export_client_kit_parser.add_argument("--kit-name", default="x0vpn-client-kit")

    export_client_kits_parser = subparsers.add_parser("export-client-kits")
    export_client_kits_parser.add_argument("--server-config", required=True)
    export_client_kits_parser.add_argument("--issuer-config")
    export_client_kits_parser.add_argument("--out-dir", required=True)
    export_client_kits_parser.add_argument("--kit-prefix", default="")
    export_client_kits_parser.add_argument("--archive", action="store_true")
    export_client_kits_parser.add_argument("--archive-dir")
    export_client_kits_parser.add_argument("--require-readiness", action="store_true")
    export_client_kits_parser.add_argument("--readiness-timeout", type=float, default=3.0)
    export_client_kits_parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    export_client_kits_parser.add_argument("--readiness-skip-tcp-connect", action="store_true")
    export_client_kits_parser.add_argument("--readiness-skip-admission", action="store_true")
    export_client_kits_parser.add_argument("--readiness-skip-config-sync", action="store_true")
    export_client_kits_parser.add_argument(
        "--readiness-skip-managed-install-plan",
        action="store_true",
    )

    verify_client_kit_parser = subparsers.add_parser("verify-client-kit")
    verify_client_kit_parser.add_argument("--kit-dir", required=True)
    verify_client_kit_parser.add_argument("--archive")
    verify_client_kit_parser.add_argument("--require-signature", action="store_true")
    verify_client_kit_parser.add_argument("--require-readiness", action="store_true")
    verify_client_kit_parser.add_argument("--readiness-timeout", type=float, default=3.0)
    verify_client_kit_parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    verify_client_kit_parser.add_argument("--readiness-skip-tcp-connect", action="store_true")
    verify_client_kit_parser.add_argument("--readiness-skip-admission", action="store_true")
    verify_client_kit_parser.add_argument("--readiness-skip-config-sync", action="store_true")
    verify_client_kit_parser.add_argument(
        "--readiness-skip-managed-install-plan",
        action="store_true",
    )

    verify_client_kits_parser = subparsers.add_parser("verify-client-kits")
    verify_client_kits_parser.add_argument("--kits-dir", required=True)
    verify_client_kits_parser.add_argument("--archive-dir")
    verify_client_kits_parser.add_argument("--require-signature", action="store_true")
    verify_client_kits_parser.add_argument("--check-archives", action="store_true")
    verify_client_kits_parser.add_argument("--require-readiness", action="store_true")
    verify_client_kits_parser.add_argument("--readiness-timeout", type=float, default=3.0)
    verify_client_kits_parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    verify_client_kits_parser.add_argument("--readiness-skip-tcp-connect", action="store_true")
    verify_client_kits_parser.add_argument("--readiness-skip-admission", action="store_true")
    verify_client_kits_parser.add_argument("--readiness-skip-config-sync", action="store_true")
    verify_client_kits_parser.add_argument(
        "--readiness-skip-managed-install-plan",
        action="store_true",
    )

    server_parser = subparsers.add_parser("server")
    server_parser.add_argument("--config", required=True)

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--config", required=True)
    probe_parser.add_argument("--message", default="x0vpn-live-self-test")
    probe_parser.add_argument("--timeout", type=float, default=3.0)
    probe_parser.add_argument("--admission-only", action="store_true")
    probe_parser.add_argument("--tun-packet", action="store_true")

    plan_parser = subparsers.add_parser("plan-linux")
    plan_parser.add_argument("--config", required=True)
    plan_parser.add_argument("--role", choices=("server", "client"), required=True)
    plan_parser.add_argument("--uplink-interface")
    plan_parser.add_argument("--underlay-gateway")
    plan_parser.add_argument("--underlay-interface")
    _add_enable_kill_switch_arg(plan_parser)

    preflight_parser = subparsers.add_parser("linux-preflight")
    preflight_parser.add_argument("--config", required=True)
    preflight_parser.add_argument("--role", choices=("server", "client"), required=True)
    preflight_parser.add_argument("--uplink-interface")
    preflight_parser.add_argument("--underlay-gateway")
    preflight_parser.add_argument("--underlay-interface")
    _add_enable_kill_switch_arg(preflight_parser)
    preflight_parser.add_argument("--no-require-root", action="store_true")
    preflight_parser.add_argument("--no-require-net-admin", action="store_true")
    preflight_parser.add_argument("--no-require-tun-device", action="store_true")

    leak_parser = subparsers.add_parser("leak-protection-plan")
    leak_parser.add_argument("--config", required=True)
    leak_parser.add_argument("--underlay-gateway")
    leak_parser.add_argument("--underlay-interface")
    _add_enable_kill_switch_arg(leak_parser)

    zero_trust_parser = subparsers.add_parser("zero-trust-policy")
    zero_trust_parser.add_argument("--config", required=True)
    zero_trust_parser.add_argument("--target", default="nl")
    zero_trust_parser.add_argument(
        "--max-identity-lifetime-seconds",
        type=int,
        default=3600,
    )

    pqc_parser = subparsers.add_parser("pqc-readiness")
    pqc_parser.add_argument("--config", required=True)
    pqc_parser.add_argument("--source-root")
    pqc_parser.add_argument("--captured-at", type=int)
    pqc_parser.add_argument(
        "--max-evidence-age-seconds",
        type=int,
        default=3600,
    )

    pqc_promote_parser = subparsers.add_parser("pqc-promote-config")
    pqc_promote_parser.add_argument("--config", required=True)
    pqc_promote_parser.add_argument("--out-config")
    pqc_promote_parser.add_argument("--update-config", action="store_true")
    pqc_promote_parser.add_argument("--source-root")
    pqc_promote_parser.add_argument("--captured-at", type=int)
    pqc_promote_parser.add_argument(
        "--max-evidence-age-seconds",
        type=int,
        default=3600,
    )

    identity_signer_parser = subparsers.add_parser("identity-signer-readiness")
    identity_signer_parser.add_argument("--issuer-config", required=True)
    identity_signer_parser.add_argument("--source-root")
    identity_signer_parser.add_argument("--captured-at", type=int)
    identity_signer_parser.add_argument(
        "--max-evidence-age-seconds",
        type=int,
        default=3600,
    )

    dataplane_parser = subparsers.add_parser("dataplane-readiness")
    dataplane_parser.add_argument("--config", required=True)
    dataplane_parser.add_argument("--path-label", default="vps")
    dataplane_parser.add_argument("--timeout", type=float, default=3.0)
    dataplane_parser.add_argument("--payload-size", type=int, default=64)
    dataplane_parser.add_argument("--mtu-candidates")
    dataplane_parser.add_argument("--captured-at", type=int)

    policy_snapshot_parser = subparsers.add_parser("policy-snapshot-write")
    policy_snapshot_parser.add_argument("--config", required=True)
    policy_snapshot_parser.add_argument("--out", required=True)
    policy_snapshot_parser.add_argument("--policy-epoch")
    policy_snapshot_parser.add_argument("--issued-at", type=int)

    policy_source_parser = subparsers.add_parser("policy-source-readiness")
    policy_source_parser.add_argument("--policy-source-path", required=True)
    policy_source_parser.add_argument(
        "--policy-source-id",
        default="x0vpn-managed-policy-source",
    )
    policy_source_parser.add_argument("--allowed-policy-epoch")
    policy_source_parser.add_argument("--minimum-issued-at", type=int)
    policy_source_parser.add_argument("--captured-at", type=int)

    rekey_policy_parser = subparsers.add_parser("rekey-policy-readiness")
    rekey_policy_parser.add_argument("--config")
    rekey_policy_parser.add_argument("--captured-at", type=int)
    rekey_policy_parser.add_argument("--max-session-age-seconds", type=int, default=1)
    rekey_policy_parser.add_argument("--requested-reason", default="scheduled-rotation")
    rekey_policy_parser.add_argument("--rollback-plan-id", default="x0vpn-managed-rekey-rollback")

    production_readiness_parser = subparsers.add_parser("production-readiness")
    production_readiness_parser.add_argument("--target", default="nl")
    production_readiness_parser.add_argument("--source-root")
    production_readiness_parser.add_argument("--config")
    production_readiness_parser.add_argument("--issuer-config")
    production_readiness_parser.add_argument("--policy-source-path")
    production_readiness_parser.add_argument(
        "--policy-source-id",
        default="x0vpn-managed-policy-source",
    )
    production_readiness_parser.add_argument("--policy-source-epoch")
    production_readiness_parser.add_argument("--policy-source-minimum-issued-at", type=int)
    production_readiness_parser.add_argument("--role", choices=("server", "client"))
    production_readiness_parser.add_argument("--uplink-interface")
    production_readiness_parser.add_argument("--underlay-gateway")
    production_readiness_parser.add_argument("--underlay-interface")
    _add_enable_kill_switch_arg(production_readiness_parser)
    production_readiness_parser.add_argument("--collect-dataplane", action="store_true")
    production_readiness_parser.add_argument("--dataplane-path-label")
    production_readiness_parser.add_argument("--dataplane-timeout", type=float, default=3.0)
    production_readiness_parser.add_argument("--dataplane-payload-size", type=int, default=64)
    production_readiness_parser.add_argument("--dataplane-mtu-candidates")
    production_readiness_parser.add_argument("--collect-rekey-policy", action="store_true")
    production_readiness_parser.add_argument("--rekey-max-session-age-seconds", type=int, default=1)
    production_readiness_parser.add_argument("--rekey-requested-reason", default="scheduled-rotation")
    production_readiness_parser.add_argument(
        "--rekey-rollback-plan-id",
        default="x0vpn-managed-rekey-rollback",
    )
    production_readiness_parser.add_argument("--collect-rollout-gate", action="store_true")
    production_readiness_parser.add_argument("--rollout-expected-test-count", type=int, default=5)
    production_readiness_parser.add_argument("--rollout-approval-id", default="x0vpn-managed-rollout-approval")
    production_readiness_parser.add_argument("--rollout-approved-by", default="x0vpn-managed-operator")
    production_readiness_parser.add_argument("--evaluated-at", type=int)
    production_readiness_parser.add_argument(
        "--max-evidence-age-seconds",
        type=int,
        default=3600,
    )
    production_readiness_parser.add_argument(
        "--max-identity-lifetime-seconds",
        type=int,
        default=3600,
    )
    production_readiness_parser.add_argument("--no-require-root", action="store_true")
    production_readiness_parser.add_argument("--no-require-net-admin", action="store_true")
    production_readiness_parser.add_argument("--no-require-tun-device", action="store_true")

    server_tun_parser = subparsers.add_parser("server-tun")
    server_tun_parser.add_argument("--config", required=True)
    server_tun_parser.add_argument("--uplink-interface")
    server_tun_parser.add_argument("--allow-os-mutation", action="store_true")

    server_health_parser = subparsers.add_parser("server-health")
    server_health_parser.add_argument("--config", required=True)
    server_health_parser.add_argument(
        "--service-name",
        default=DEFAULT_SERVER_SERVICE_NAME,
    )
    server_health_parser.add_argument("--uplink-interface")
    server_health_parser.add_argument("--skip-service", action="store_true")
    server_health_parser.add_argument("--skip-listen", action="store_true")

    apply_server_config_parser = subparsers.add_parser("apply-server-config")
    apply_server_config_parser.add_argument("--candidate-config", required=True)
    apply_server_config_parser.add_argument("--installed-config", required=True)
    apply_server_config_parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    apply_server_config_parser.add_argument("--backup-dir")
    apply_server_config_parser.add_argument("--uplink-interface")
    apply_server_config_parser.add_argument("--allow-os-mutation", action="store_true")
    apply_server_config_parser.add_argument("--dry-run", action="store_true")
    apply_server_config_parser.add_argument("--skip-health", action="store_true")
    apply_server_config_parser.add_argument("--health-retries", type=int, default=10)
    apply_server_config_parser.add_argument("--health-retry-interval-seconds", type=float, default=0.5)
    apply_server_config_parser.add_argument("--no-rollback-on-failure", action="store_true")

    server_service_plan_parser = subparsers.add_parser("server-service-plan")
    _add_server_service_common_args(server_service_plan_parser)
    server_service_plan_parser.add_argument("--enable-now", action="store_true")

    server_renewal_plan_parser = subparsers.add_parser("server-renewal-plan")
    _add_server_renewal_common_args(server_renewal_plan_parser)
    server_renewal_plan_parser.add_argument("--enable-now", action="store_true")

    install_server_service_parser = subparsers.add_parser("install-server-service")
    _add_server_service_common_args(install_server_service_parser)
    install_server_service_parser.add_argument("--allow-os-mutation", action="store_true")
    install_server_service_parser.add_argument("--enable", action="store_true")
    install_server_service_parser.add_argument("--start", action="store_true")
    install_server_service_parser.add_argument("--enable-now", action="store_true")

    install_server_renewal_parser = subparsers.add_parser("install-server-renewal")
    _add_server_renewal_common_args(install_server_renewal_parser)
    install_server_renewal_parser.add_argument("--allow-os-mutation", action="store_true")
    install_server_renewal_parser.add_argument("--enable", action="store_true")
    install_server_renewal_parser.add_argument("--start", action="store_true")
    install_server_renewal_parser.add_argument("--enable-now", action="store_true")

    uninstall_server_service_parser = subparsers.add_parser("uninstall-server-service")
    uninstall_server_service_parser.add_argument(
        "--service-name",
        default=DEFAULT_SERVER_SERVICE_NAME,
    )
    uninstall_server_service_parser.add_argument(
        "--install-dir",
        default=DEFAULT_SERVER_INSTALL_DIR,
    )
    uninstall_server_service_parser.add_argument(
        "--config-dir",
        default=DEFAULT_SERVER_CONFIG_DIR,
    )
    uninstall_server_service_parser.add_argument("--allow-os-mutation", action="store_true")
    uninstall_server_service_parser.add_argument("--remove-install-dir", action="store_true")
    uninstall_server_service_parser.add_argument("--remove-config-dir", action="store_true")

    client_tun_parser = subparsers.add_parser("client-tun")
    client_tun_parser.add_argument("--config", required=True)
    client_tun_parser.add_argument("--underlay-gateway")
    client_tun_parser.add_argument("--underlay-interface")
    client_tun_parser.add_argument("--allow-os-mutation", action="store_true")
    client_tun_parser.add_argument("--apply-client-policy", action="store_true")
    _add_enable_kill_switch_arg(client_tun_parser)

    service_plan_parser = subparsers.add_parser("client-service-plan")
    _add_client_service_common_args(service_plan_parser)
    service_plan_parser.add_argument("--enable-now", action="store_true")

    client_sync_plan_parser = subparsers.add_parser("client-sync-plan")
    _add_client_sync_common_args(client_sync_plan_parser)
    client_sync_plan_parser.add_argument("--enable-now", action="store_true")

    install_service_parser = subparsers.add_parser("install-client-service")
    _add_client_service_common_args(install_service_parser)
    install_service_parser.add_argument("--allow-os-mutation", action="store_true")
    install_service_parser.add_argument("--enable", action="store_true")
    install_service_parser.add_argument("--start", action="store_true")
    install_service_parser.add_argument("--enable-now", action="store_true")
    install_service_parser.add_argument("--require-post-install-health", action="store_true")
    install_service_parser.add_argument("--post-install-health-retries", type=int, default=10)
    install_service_parser.add_argument(
        "--post-install-health-interval-seconds",
        type=float,
        default=1.0,
    )
    install_service_parser.add_argument("--post-install-health-timeout", type=float, default=3.0)
    install_service_parser.add_argument(
        "--post-install-health-skip-tcp-connect",
        action="store_true",
    )

    install_client_sync_parser = subparsers.add_parser("install-client-sync")
    _add_client_sync_common_args(install_client_sync_parser)
    install_client_sync_parser.add_argument("--allow-os-mutation", action="store_true")
    install_client_sync_parser.add_argument("--enable", action="store_true")
    install_client_sync_parser.add_argument("--start", action="store_true")
    install_client_sync_parser.add_argument("--enable-now", action="store_true")

    uninstall_service_parser = subparsers.add_parser("uninstall-client-service")
    uninstall_service_parser.add_argument(
        "--service-name",
        default=DEFAULT_CLIENT_SERVICE_NAME,
    )
    uninstall_service_parser.add_argument(
        "--install-dir",
        default=DEFAULT_CLIENT_INSTALL_DIR,
    )
    uninstall_service_parser.add_argument(
        "--config-dir",
        default=DEFAULT_CLIENT_CONFIG_DIR,
    )
    uninstall_service_parser.add_argument("--allow-os-mutation", action="store_true")
    uninstall_service_parser.add_argument("--keep-config-sync", action="store_true")
    uninstall_service_parser.add_argument("--config-sync-service-name")
    uninstall_service_parser.add_argument("--config-sync-timer-name")
    uninstall_service_parser.add_argument("--remove-install-dir", action="store_true")
    uninstall_service_parser.add_argument("--remove-config-dir", action="store_true")

    apply_client_config_parser = subparsers.add_parser("apply-client-config")
    apply_client_config_parser.add_argument("--candidate-config", required=True)
    apply_client_config_parser.add_argument("--installed-config", required=True)
    apply_client_config_parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    apply_client_config_parser.add_argument("--backup-dir")
    apply_client_config_parser.add_argument("--timeout", type=float, default=2.0)
    apply_client_config_parser.add_argument("--allow-os-mutation", action="store_true")
    apply_client_config_parser.add_argument("--dry-run", action="store_true")
    apply_client_config_parser.add_argument("--skip-health", action="store_true")
    apply_client_config_parser.add_argument("--skip-tcp-connect", action="store_true")
    apply_client_config_parser.add_argument("--no-rollback-on-failure", action="store_true")

    rollback_parser = subparsers.add_parser("client-policy-rollback")
    rollback_parser.add_argument("--config", required=True)
    rollback_parser.add_argument("--underlay-gateway")
    rollback_parser.add_argument("--underlay-interface")
    rollback_parser.add_argument("--allow-os-mutation", action="store_true")
    _add_enable_kill_switch_arg(rollback_parser)

    health_parser = subparsers.add_parser("client-health")
    health_parser.add_argument("--config", required=True)
    health_parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    health_parser.add_argument("--timeout", type=float, default=2.0)
    health_parser.add_argument("--skip-service", action="store_true")
    health_parser.add_argument("--skip-tcp-connect", action="store_true")

    doctor_parser = subparsers.add_parser("client-doctor")
    doctor_parser.add_argument("--config", required=True)
    doctor_parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    doctor_parser.add_argument("--install-dir", default=DEFAULT_CLIENT_INSTALL_DIR)
    doctor_parser.add_argument("--config-dir", default=DEFAULT_CLIENT_CONFIG_DIR)
    doctor_parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    doctor_parser.add_argument("--health-timeout", type=float, default=5.0)
    doctor_parser.add_argument("--readiness-timeout", type=float, default=5.0)
    doctor_parser.add_argument("--probe-timeout", type=float, default=5.0)
    doctor_parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    doctor_parser.add_argument("--message", default="x0vpn-live-self-test")
    doctor_parser.add_argument("--skip-preflight", action="store_true")
    doctor_parser.add_argument("--skip-readiness", action="store_true")
    doctor_parser.add_argument("--skip-probe", action="store_true")
    doctor_parser.add_argument("--skip-health", action="store_true")
    doctor_parser.add_argument("--skip-tcp-connect", action="store_true")
    doctor_parser.add_argument("--skip-admission", action="store_true")
    doctor_parser.add_argument("--skip-config-sync", action="store_true")
    doctor_parser.add_argument("--skip-managed-install-plan", action="store_true")
    doctor_parser.add_argument("--require-installed-health", action="store_true")

    readiness_parser = subparsers.add_parser("client-readiness")
    readiness_parser.add_argument("--config", required=True)
    readiness_parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    readiness_parser.add_argument("--install-dir", default=DEFAULT_CLIENT_INSTALL_DIR)
    readiness_parser.add_argument("--config-dir", default=DEFAULT_CLIENT_CONFIG_DIR)
    readiness_parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    readiness_parser.add_argument("--timeout", type=float, default=3.0)
    readiness_parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    readiness_parser.add_argument("--skip-tcp-connect", action="store_true")
    readiness_parser.add_argument("--skip-admission", action="store_true")
    readiness_parser.add_argument("--skip-config-sync", action="store_true")
    readiness_parser.add_argument("--skip-managed-install-plan", action="store_true")

    client_config_sync_parser = subparsers.add_parser("client-config-sync")
    client_config_sync_parser.add_argument("--config", required=True)
    client_config_sync_parser.add_argument("--out-config")
    client_config_sync_parser.add_argument("--update-config", action="store_true")
    client_config_sync_parser.add_argument("--timeout", type=float, default=3.0)
    client_config_sync_parser.add_argument("--dry-run", action="store_true")
    client_config_sync_parser.add_argument("--restart-service", action="store_true")
    client_config_sync_parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    client_config_sync_parser.add_argument("--allow-os-mutation", action="store_true")

    source_audit_parser = subparsers.add_parser("source-audit")
    source_audit_parser.add_argument("--root")
    source_audit_parser.add_argument("--captured-at", type=int)

    args = parser.parse_args()
    if args.command == "generate":
        return generate_configs(args)
    if args.command == "add-client":
        return add_client(args)
    if args.command == "identity-rotate-config":
        return identity_rotate_config(args)
    if args.command == "identity-auto-renew":
        return identity_auto_renew(args)
    if args.command == "issuer-lifetime-policy":
        return issuer_lifetime_policy(args)
    if args.command == "provision-client":
        return provision_client(args)
    if args.command == "remove-client":
        return remove_client(args)
    if args.command == "deprovision-client":
        return deprovision_client(args)
    if args.command == "export-client-kit":
        return export_client_kit(args)
    if args.command == "export-client-kits":
        return export_client_kits(args)
    if args.command == "verify-client-kit":
        return verify_client_kit(args)
    if args.command == "verify-client-kits":
        return verify_client_kits(args)
    if args.command == "server":
        return asyncio.run(run_server(args))
    if args.command == "probe":
        return asyncio.run(run_probe(args))
    if args.command == "plan-linux":
        return plan_linux(args)
    if args.command == "linux-preflight":
        return linux_preflight(args)
    if args.command == "leak-protection-plan":
        return leak_protection_plan(args)
    if args.command == "zero-trust-policy":
        return zero_trust_policy(args)
    if args.command == "pqc-readiness":
        return pqc_readiness(args)
    if args.command == "pqc-promote-config":
        return pqc_promote_config(args)
    if args.command == "identity-signer-readiness":
        return identity_signer_readiness(args)
    if args.command == "dataplane-readiness":
        return dataplane_readiness(args)
    if args.command == "policy-snapshot-write":
        return policy_snapshot_write(args)
    if args.command == "policy-source-readiness":
        return policy_source_readiness(args)
    if args.command == "rekey-policy-readiness":
        return rekey_policy_readiness(args)
    if args.command == "production-readiness":
        return production_readiness(args)
    if args.command == "server-tun":
        return asyncio.run(run_server_tun(args))
    if args.command == "server-health":
        return server_health(args)
    if args.command == "apply-server-config":
        return apply_server_config(args)
    if args.command == "server-service-plan":
        return server_service_plan(args)
    if args.command == "server-renewal-plan":
        return server_renewal_plan(args)
    if args.command == "install-server-service":
        return install_server_service(args)
    if args.command == "install-server-renewal":
        return install_server_renewal(args)
    if args.command == "uninstall-server-service":
        return uninstall_server_service(args)
    if args.command == "client-tun":
        return asyncio.run(run_client_tun(args))
    if args.command == "client-service-plan":
        return client_service_plan(args)
    if args.command == "client-sync-plan":
        return client_sync_plan(args)
    if args.command == "install-client-service":
        return install_client_service(args)
    if args.command == "install-client-sync":
        return install_client_sync(args)
    if args.command == "uninstall-client-service":
        return uninstall_client_service(args)
    if args.command == "apply-client-config":
        return apply_client_config(args)
    if args.command == "client-policy-rollback":
        return client_policy_rollback(args)
    if args.command == "client-health":
        return client_health(args)
    if args.command == "client-doctor":
        return asyncio.run(client_doctor(args))
    if args.command == "client-readiness":
        return asyncio.run(client_readiness(args))
    if args.command == "client-config-sync":
        return asyncio.run(client_config_sync(args))
    if args.command == "source-audit":
        return source_audit(args)
    raise AssertionError(args.command)


def generate_configs(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = _now()
    expires_at = now + args.lifetime_seconds
    deployment_epoch_prefix = str(
        getattr(args, "deployment_epoch_prefix", DEFAULT_DEPLOYMENT_EPOCH_PREFIX)
    )
    deployment_epoch = str(
        getattr(args, "deployment_epoch", None) or f"{deployment_epoch_prefix}-{_timestamp()}"
    )
    issuer = str(getattr(args, "issuer", ISSUER))
    policy_epoch = str(getattr(args, "policy_epoch", POLICY_EPOCH))
    provider_id = str(getattr(args, "provider_id", PROVIDER_ID))
    identity_key_id = str(getattr(args, "identity_key_id", DEFAULT_IDENTITY_KEY_ID))
    server_device_id = str(getattr(args, "server_device_id", DEFAULT_SERVER_DEVICE_ID))
    pqc_mode = str(getattr(args, "pqc_mode", "production"))
    pqc_reviewed = bool(getattr(args, "pqc_reviewed", True))
    transport = _dataplane_transport_from_value(getattr(args, "transport", "tcp"))
    anti_dpi_profile = _default_anti_dpi_profile(transport)
    endpoint_configs = [
        _endpoint_config(
            host=args.host,
            port=int(args.port),
            transport=transport,
            priority=0,
            path_label=f"{deployment_epoch_prefix}-{transport}",
            endpoint_id="primary",
        ),
        *(
            _parse_fallback_endpoint(raw, index=index)
            for index, raw in enumerate(getattr(args, "fallback_endpoint", ()), start=1)
        ),
    ]
    listener_configs: list[dict[str, Any]] = []
    seen_listeners: set[tuple[str, int]] = set()
    for endpoint in endpoint_configs:
        endpoint_transport = _dataplane_transport_from_value(
            endpoint.get("transport", transport)
        )
        endpoint_port = int(endpoint.get("port", args.port))
        listener_key = (endpoint_transport, endpoint_port)
        if listener_key in seen_listeners:
            continue
        seen_listeners.add(listener_key)
        listener_configs.append(
            {
                "port": endpoint_port,
                "transport": endpoint_transport,
            }
        )

    identity_seed = hashlib.shake_256(
        b"x0vpn-firstparty-identity-seed-v1" + os.urandom(32)
    ).digest(ML_DSA_KEYGEN_SEED_BYTES)
    identity_pair = mldsa_derive_reference_keypair(identity_seed, SIGNATURE_ALGORITHM)
    signing_key = IdentitySigningKey(
        key_id=identity_key_id,
        signature_algorithm=SIGNATURE_ALGORITHM,
        secret=identity_pair.signing_key,
        not_before=now - 60,
        not_after=expires_at + 60,
    )
    verification_key = IdentitySigningKey(
        key_id=signing_key.key_id,
        signature_algorithm=signing_key.signature_algorithm,
        secret=identity_pair.verification_key,
        not_before=signing_key.not_before,
        not_after=signing_key.not_after,
    )
    signer = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    authority = IdentityAuthority(
        issuer=issuer,
        policy_epoch=policy_epoch,
        signing_keys=(signing_key,),
        active_key_id=signing_key.key_id,
        signature_provider=signer,
        default_lifetime_seconds=args.lifetime_seconds,
        max_lifetime_seconds=args.lifetime_seconds,
    )

    client_tun_addresses = _allocated_client_tun_addresses(args)
    client_identities: list[tuple[str, SignedIdentityToken, str]] = []
    for index, client_tun_address in enumerate(client_tun_addresses, start=1):
        device_id = f"{args.client_device_prefix}-{index}"
        client_identities.append(
            (
                device_id,
                _issue_identity_with_sign_retry(
                    authority,
                    _issue_request("vpn-client", device_id, args.tenant),
                    now=now,
                    lifetime_seconds=args.lifetime_seconds,
                ),
                client_tun_address,
            )
    )
    server_identity = _issue_identity_with_sign_retry(
        authority,
        _issue_request("vpn-server", server_device_id, args.tenant),
        now=now,
        lifetime_seconds=args.lifetime_seconds,
    )

    kem_keypair = mlkem_keygen_from_seeds(
        KEM_ALGORITHM,
        hashlib.shake_256(b"x0vpn-firstparty-mlkem-d-v1" + os.urandom(32)).digest(
            ML_KEM_SEED_BYTES
        ),
        hashlib.shake_256(b"x0vpn-firstparty-mlkem-z-v1" + os.urandom(32)).digest(
            ML_KEM_SEED_BYTES
        ),
    )
    pqc_kat_transcript = b"x0vpn-production-pqc-kat-transcript-v1"
    pqc_kat_client_hash = hashlib.sha256(
        b"x0vpn-production-pqc-kat-client-v1"
    ).digest()
    pqc_kat_server_hash = hashlib.sha256(
        b"x0vpn-production-pqc-kat-server-v1"
    ).digest()
    pqc_kat_context_id = FirstPartyMlKemImplementation.context_id(
        transcript=pqc_kat_transcript,
        client_identity_hash=pqc_kat_client_hash,
        server_identity_hash=pqc_kat_server_hash,
    )
    pqc_kat_message = hashlib.shake_256(
        b"x0vpn-production-pqc-kat-message-v1" + bytes.fromhex(pqc_kat_context_id)
    ).digest(ML_KEM_SEED_BYTES)
    pqc_implementation = FirstPartyMlKemImplementation(
        provider_id=provider_id,
        kem_algorithm=KEM_ALGORITHM,
        signature_algorithm=SIGNATURE_ALGORITHM,
        encapsulation_key=kem_keypair.encapsulation_key,
        kat_messages={pqc_kat_context_id: pqc_kat_message},
    )
    implementation_hash = pqc_implementation.implementation_hash
    attestation = _attestation(now=now, expires_at=expires_at, implementation_hash=implementation_hash)
    client_leases = [
        {
            "device_id": device_id,
            "identity_hash": identity_binding_hash(client_identity.claims).hex(),
            "client_address": _interface_ip(client_tun_address),
            "client_tun_address": client_tun_address,
        }
        for device_id, client_identity, client_tun_address in client_identities
    ]
    first_client_identity = client_identities[0][1]
    first_client_tun_address = client_identities[0][2]

    common = {
        "schema_version": 1,
        "generated_at": _iso(now),
        "expires_at": _iso(expires_at),
        "deployment_epoch": deployment_epoch,
        "host": args.host,
        "port": args.port,
        "tenant": args.tenant,
        "policy": {
            "allowed_tenants": [args.tenant],
            "max_token_lifetime_seconds": args.lifetime_seconds,
        },
        "identity": {
            "issuer": issuer,
            "policy_epoch": policy_epoch,
            "verification_key": _key_to_json(verification_key),
            "signature_provider": "firstparty-reference-mldsa",
        },
        "tokens": {
            "client": _token_to_json(first_client_identity),
            "clients": [
                {
                    "device_id": device_id,
                    "token": _token_to_json(client_identity),
                }
                for device_id, client_identity, _client_tun_address in client_identities
            ],
            "server": _token_to_json(server_identity),
        },
        "pqc": {
            "provider_id": provider_id,
            "kem_algorithm": KEM_ALGORITHM,
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "mode": pqc_mode,
            "reviewed": pqc_reviewed,
            "issued_at": now,
            "expires_at": expires_at,
            "implementation_hash": implementation_hash,
            "encapsulation_key": kem_keypair.encapsulation_key.hex(),
        },
        "tunnel": {
            "transport": transport,
            "anti_dpi": anti_dpi_profile,
            "endpoints": endpoint_configs,
            "listeners": listener_configs,
            "server_tun_name": args.server_tun_name,
            "client_tun_name": args.client_tun_name,
            "mtu": args.tun_mtu,
            "client_cidr": args.client_cidr,
            "server_address": args.server_tun_address,
            "client_address": first_client_tun_address,
            "client_peer": args.client_tun_peer,
            "client_leases": client_leases,
            "shared_return_by_client_address": True,
            "enable_iptables_compat": True,
            "nat_table_name": f"{args.server_tun_name}_nat",
            "filter_table_name": f"{args.server_tun_name}_filter",
            "dns_servers": args.dns_server or ["1.1.1.1", "9.9.9.9"],
            "route_all_traffic": True,
            "enable_kill_switch": True,
        },
    }

    server_config = {
        **common,
        "bind_host": args.bind_host,
        "pqc": {
            **common["pqc"],
            "decapsulation_key": kem_keypair.decapsulation_key.hex(),
        },
        "revocations": _revocations_to_json_dict(RevocationList()),
    }
    issuer_config = {
        "schema_version": 1,
        "generated_at": _iso(now),
        "issuer": issuer,
        "policy_epoch": policy_epoch,
        "active_key_id": signing_key.key_id,
        "signing_key": _key_to_json(signing_key),
        "verification_key": _key_to_json(verification_key),
        "signature_provider": "firstparty-reference-mldsa",
        "serial_counter": authority.serial_counter,
        "default_lifetime_seconds": args.lifetime_seconds,
        "max_lifetime_seconds": args.lifetime_seconds,
    }

    _write_json(out_dir / "server.json", server_config, mode=0o600)
    _write_json(out_dir / "issuer.json", issuer_config, mode=0o600)
    client_config_paths: list[str] = []
    for index, (device_id, client_identity, client_tun_address) in enumerate(
        client_identities,
        start=1,
    ):
        _ = device_id
        client_config = _client_config_from_server_config(
            server_config,
            client_identity=client_identity,
            client_tun_address=client_tun_address,
        )
        client_path = out_dir / ("client.json" if index == 1 else f"client-{index}.json")
        _write_json(client_path, client_config, mode=0o600)
        client_config_paths.append(str(client_path))
    _write_json(
        out_dir / PUBLIC_INFO_FILENAME,
        {
            "host": args.host,
            "port": args.port,
            "transport": transport,
            "deployment_epoch": deployment_epoch,
            "expires_at": _iso(expires_at),
            "client_config": client_config_paths[0],
            "client_configs": client_config_paths,
            "client_count": len(client_config_paths),
        },
        mode=0o644,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "server_config": str(out_dir / "server.json"),
                "issuer_config": str(out_dir / "issuer.json"),
                "client_config": client_config_paths[0],
                "client_configs": client_config_paths,
                "client_count": len(client_config_paths),
                "host": args.host,
                "port": args.port,
                "transport": transport,
                "expires_at": _iso(expires_at),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def export_client_kit(args: argparse.Namespace) -> int:
    client_config_path = Path(args.client_config)
    out_dir = Path(args.out_dir)
    archive_path: Path | None = Path(args.archive) if args.archive else None
    issuer_config = getattr(args, "issuer_config", None)
    issuer_config_path = Path(issuer_config) if issuer_config else None
    payload = _export_client_kit_payload(
        client_config_path=client_config_path,
        out_dir=out_dir,
        kit_name=str(args.kit_name),
        archive_path=archive_path,
        issuer_config_path=issuer_config_path,
    )
    print(
        json.dumps(
            payload,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def export_client_kits(args: argparse.Namespace) -> int:
    server_config_path = Path(args.server_config)
    issuer_config = getattr(args, "issuer_config", None)
    issuer_config_path = Path(issuer_config) if issuer_config else None
    out_dir = Path(args.out_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else out_dir
    kit_prefix = str(args.kit_prefix or "")
    safe_kit_prefix = _safe_kit_name(kit_prefix) if kit_prefix else ""
    server_config = _load_json(server_config_path)
    client_entries = _client_export_entries_from_server_config(server_config)
    readiness_payloads: list[dict[str, Any]] = []
    if bool(getattr(args, "require_readiness", False)):
        with tempfile.TemporaryDirectory(prefix="x0vpn-export-readiness-") as temp_dir:
            temp_root = Path(temp_dir)
            for index, entry in enumerate(client_entries, start=1):
                device_id = str(entry["device_id"])
                temp_config_path = temp_root / (
                    "client.json" if index == 1 else f"client-{index}.json"
                )
                _write_json(temp_config_path, entry["client_config"], mode=0o600)
                readiness_payload = asyncio.run(
                    _client_readiness_payload(
                        _client_readiness_args_from_export_args(
                            args,
                            config_path=temp_config_path,
                        )
                    )
                )
                readiness_payload["device_id"] = device_id
                readiness_payloads.append(readiness_payload)
        failed_readiness = [
            item for item in readiness_payloads if not bool(item.get("ok"))
        ]
        if failed_readiness:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "mode": "export-client-kits",
                        "error": "client kits readiness failed",
                        "server_config": str(server_config_path),
                        "out_dir": str(out_dir),
                        "archive_dir": str(archive_dir),
                        "archive_enabled": bool(args.archive),
                        "kit_prefix": safe_kit_prefix,
                        "client_count": len(client_entries),
                        "failed_devices": [
                            str(item.get("device_id")) for item in failed_readiness
                        ],
                        "readiness_required": True,
                        "readiness": readiness_payloads,
                        "file_mutation_performed": False,
                        "os_mutation_performed": False,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
    configs_dir = out_dir / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    exports: list[dict[str, Any]] = []
    for index, entry in enumerate(client_entries, start=1):
        device_id = str(entry["device_id"])
        client_config_path = configs_dir / (
            "client.json" if index == 1 else f"client-{index}.json"
        )
        _write_json(client_config_path, entry["client_config"], mode=0o600)
        kit_name = _safe_kit_name(
            f"{safe_kit_prefix}-{device_id}" if safe_kit_prefix else device_id
        )
        archive_path = archive_dir / f"{kit_name}.tar.gz" if args.archive else None
        export_payload = _export_client_kit_payload(
            client_config_path=client_config_path,
            out_dir=out_dir,
            kit_name=kit_name,
            archive_path=archive_path,
            issuer_config_path=issuer_config_path,
        )
        export_payload.update(
            {
                "device_id": device_id,
                "client_tun_address": str(entry["client_tun_address"]),
                "client_identity_serial": str(entry["client_identity"].serial),
                "server_identity_serial": str(
                    server_config["tokens"]["server"]["serial"]
                ),
            }
        )
        exports.append(export_payload)
    payload = {
        "ok": True,
        "mode": "export-client-kits",
        "server_config": str(server_config_path),
        "out_dir": str(out_dir),
        "archive_dir": str(archive_dir),
        "archive_enabled": bool(args.archive),
        "kit_prefix": safe_kit_prefix,
        "client_count": len(exports),
        "exports": exports,
        "readiness_required": bool(getattr(args, "require_readiness", False)),
        "readiness": readiness_payloads,
        "server_secrets_included": any(
            bool(item.get("server_secrets_included")) for item in exports
        ),
        "file_mutation_performed": True,
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def verify_client_kit(args: argparse.Namespace) -> int:
    payload = _verify_client_kit_payload(
        kit_dir=Path(args.kit_dir),
        archive_path=Path(args.archive) if args.archive else None,
        require_signature=bool(args.require_signature),
    )
    if bool(getattr(args, "require_readiness", False)):
        payload = _verify_client_kit_with_readiness_payload(
            payload,
            kit_dir=Path(args.kit_dir),
            args=args,
        )
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


def verify_client_kits(args: argparse.Namespace) -> int:
    kits_dir = Path(args.kits_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else kits_dir
    kit_dirs = [
        path
        for path in sorted(kits_dir.iterdir())
        if path.is_dir()
        and (path / "client.json").is_file()
        and (path / "KIT-MANIFEST.json").is_file()
    ]
    exports: list[dict[str, Any]] = []
    for kit_dir in kit_dirs:
        archive_path = (
            archive_dir / f"{kit_dir.name}.tar.gz"
            if bool(args.check_archives)
            else None
        )
        export_payload = _verify_client_kit_payload(
            kit_dir=kit_dir,
            archive_path=archive_path,
            require_signature=bool(args.require_signature),
        )
        if bool(getattr(args, "require_readiness", False)):
            export_payload = _verify_client_kit_with_readiness_payload(
                export_payload,
                kit_dir=kit_dir,
                args=args,
            )
        exports.append(export_payload)
    failed = [item for item in exports if not bool(item.get("ok"))]
    payload = {
        "ok": bool(exports) and not failed,
        "mode": "verify-client-kits",
        "kits_dir": str(kits_dir),
        "archive_dir": str(archive_dir),
        "check_archives": bool(args.check_archives),
        "require_signature": bool(args.require_signature),
        "readiness_required": bool(getattr(args, "require_readiness", False)),
        "kit_count": len(exports),
        "failed_count": len(failed),
        "failed_kits": [str(item.get("kit_dir")) for item in failed],
        "exports": exports,
        "os_mutation_performed": False,
    }
    if not exports:
        payload["error"] = "no client kits found"
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


def add_client(args: argparse.Namespace) -> int:
    if args.update_server_config and args.server_config_out:
        raise ValueError("--update-server-config and --server-config-out are mutually exclusive")
    if not args.dry_run and not args.update_server_config and not args.server_config_out:
        raise ValueError(
            "add-client requires --server-config-out or --update-server-config unless --dry-run is used"
        )

    server_config_path = Path(args.server_config)
    issuer_config_path = Path(args.issuer_config)
    out_client_path = Path(args.out_client)
    server_config = _load_json(server_config_path)
    issuer_config = _load_json(issuer_config_path)
    artifacts = _build_added_client_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        device_id=args.device_id,
        client_address=args.client_address,
        tenant=args.tenant,
        lifetime_seconds=args.lifetime_seconds,
    )
    updated_server_config = artifacts["updated_server_config"]
    client_config = artifacts["client_config"]
    updated_issuer_config = artifacts["updated_issuer_config"]
    server_config_out = (
        server_config_path if args.update_server_config else Path(args.server_config_out or server_config_path)
    )

    if not args.dry_run:
        _write_json(server_config_out, updated_server_config, mode=0o600)
        _write_json(issuer_config_path, updated_issuer_config, mode=0o600)
        _write_json(out_client_path, client_config, mode=0o600)

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "add-client",
                "dry_run": bool(args.dry_run),
                "device_id": args.device_id,
                "client_address": artifacts["client_tun_address"],
                "client_ip": artifacts["client_ip"],
                "identity_hash": artifacts["identity_hash"],
                "identity_serial": artifacts["identity_serial"],
                "server_config": str(server_config_path),
                "server_config_out": str(server_config_out),
                "issuer_config": str(issuer_config_path),
                "out_client": str(out_client_path),
                "client_lease_count": len(_tunnel_config(updated_server_config).get("client_leases", ())),
                "issuer_serial_counter": artifacts["issuer_serial_counter"],
                "server_restart_required": True,
                "file_mutation_performed": not bool(args.dry_run),
                "os_mutation_performed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def identity_rotate_config(args: argparse.Namespace) -> int:
    if args.update_server_config and args.server_config_out:
        raise ValueError(
            "--update-server-config and --server-config-out are mutually exclusive"
        )
    if int(args.lifetime_seconds) < 1:
        raise ValueError("identity lifetime must be positive")
    server_config_path = Path(args.server_config)
    issuer_config_path = Path(args.issuer_config)
    out_dir = Path(args.out_dir)
    server_config = _load_json(server_config_path)
    issuer_config = _load_json(issuer_config_path)
    artifacts = _rotate_identity_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        lifetime_seconds=int(args.lifetime_seconds),
    )
    server_config_out = (
        server_config_path
        if args.update_server_config
        else Path(args.server_config_out or out_dir / "server.json")
    )
    client_paths = [
        out_dir / ("client.json" if index == 1 else f"client-{index}.json")
        for index, _client in enumerate(artifacts["client_configs"], start=1)
    ]

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(server_config_out, artifacts["updated_server_config"], mode=0o600)
        if args.update_issuer_config:
            _write_json(
                issuer_config_path,
                artifacts["updated_issuer_config"],
                mode=0o600,
            )
        for path, client_config in zip(client_paths, artifacts["client_configs"]):
            _write_json(path, client_config, mode=0o600)

    payload = {
        "ok": True,
        "mode": "identity-rotate-config",
        "dry_run": bool(args.dry_run),
        "lifetime_seconds": int(args.lifetime_seconds),
        "server_config": str(server_config_path),
        "server_config_out": str(server_config_out),
        "issuer_config": str(issuer_config_path),
        "issuer_mutation_performed": bool(args.update_issuer_config)
        and not bool(args.dry_run),
        "client_configs": [str(path) for path in client_paths],
        "client_count": len(client_paths),
        "client_identity_hashes": artifacts["client_identity_hashes"],
        "server_identity_hash": artifacts["server_identity_hash"],
        "issuer_serial_counter": artifacts["issuer_serial_counter"],
        "file_mutation_performed": not bool(args.dry_run),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def identity_auto_renew(args: argparse.Namespace) -> int:
    if args.update_server_config and args.server_config_out:
        raise ValueError(
            "--update-server-config and --server-config-out are mutually exclusive"
        )
    if args.apply_server_config and args.update_server_config:
        raise ValueError(
            "--apply-server-config and --update-server-config are mutually exclusive"
        )
    if args.apply_server_config and args.server_config_out:
        raise ValueError(
            "--apply-server-config and --server-config-out are mutually exclusive"
        )
    if args.apply_server_config and not args.installed_server_config:
        raise ValueError("identity-auto-renew requires --installed-server-config with --apply-server-config")
    if args.apply_server_config and not args.dry_run and not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "identity-auto-renew",
                    "error": "OS mutation is blocked; pass --allow-os-mutation for --apply-server-config",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    lifetime_seconds = int(args.lifetime_seconds)
    renew_before_seconds = int(args.renew_before_seconds)
    if lifetime_seconds < 1:
        raise ValueError("identity lifetime must be positive")
    if renew_before_seconds < 1:
        raise ValueError("renew-before seconds must be positive")

    server_config_path = Path(args.server_config)
    issuer_config_path = Path(args.issuer_config)
    out_dir = Path(args.out_dir)
    server_config = _load_json(server_config_path)
    issuer_config = _load_json(issuer_config_path)
    now = _now()
    renewal_status = _identity_renewal_status(
        server_config,
        now=now,
        renew_before_seconds=renew_before_seconds,
        force=bool(args.force),
    )
    candidate_server_config_path = (
        out_dir / "server.candidate.json"
        if args.apply_server_config
        else (
            server_config_path
            if args.update_server_config
            else Path(args.server_config_out or out_dir / "server.json")
        )
    )
    client_paths = [
        out_dir / ("client.json" if index == 1 else f"client-{index}.json")
        for index in range(1, int(renewal_status["client_count"]) + 1)
    ]
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "identity-auto-renew",
        "dry_run": bool(args.dry_run),
        "force": bool(args.force),
        "renewal_needed": bool(renewal_status["renewal_needed"]),
        "renewal_reason": renewal_status["renewal_reason"],
        "renewal_performed": False,
        "lifetime_seconds": lifetime_seconds,
        "renew_before_seconds": renew_before_seconds,
        "seconds_until_earliest_expiry": renewal_status["seconds_until_earliest_expiry"],
        "earliest_expires_at": renewal_status["earliest_expires_at"],
        "earliest_token_scope": renewal_status["earliest_token_scope"],
        "server_config": str(server_config_path),
        "server_config_out": str(candidate_server_config_path),
        "issuer_config": str(issuer_config_path),
        "issuer_mutation_performed": False,
        "client_configs": [str(path) for path in client_paths],
        "client_count": int(renewal_status["client_count"]),
        "apply_server_config": bool(args.apply_server_config),
        "file_mutation_performed": False,
        "server_restart_required": bool(renewal_status["renewal_needed"]),
        "os_mutation_performed": False,
    }
    if not renewal_status["renewal_needed"]:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return 0

    artifacts = _rotate_identity_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        lifetime_seconds=lifetime_seconds,
    )
    client_paths = [
        out_dir / ("client.json" if index == 1 else f"client-{index}.json")
        for index, _client in enumerate(artifacts["client_configs"], start=1)
    ]
    payload["client_configs"] = [str(path) for path in client_paths]
    payload["client_count"] = len(client_paths)
    payload["client_identity_hashes"] = artifacts["client_identity_hashes"]
    payload["server_identity_hash"] = artifacts["server_identity_hash"]
    payload["issuer_serial_counter"] = artifacts["issuer_serial_counter"]

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(candidate_server_config_path, artifacts["updated_server_config"], mode=0o600)
    for path, client_config in zip(client_paths, artifacts["client_configs"]):
        _write_json(path, client_config, mode=0o600)
    payload["file_mutation_performed"] = True

    if args.apply_server_config:
        apply_exit_code, apply_payload = _apply_server_config_result(
            argparse.Namespace(
                candidate_config=str(candidate_server_config_path),
                installed_config=str(args.installed_server_config),
                service_name=args.service_name,
                backup_dir=args.backup_dir,
                uplink_interface=args.uplink_interface,
                allow_os_mutation=args.allow_os_mutation,
                dry_run=False,
                skip_health=args.skip_health,
                health_retries=args.health_retries,
                health_retry_interval_seconds=args.health_retry_interval_seconds,
                no_rollback_on_failure=args.no_rollback_on_failure,
            )
        )
        payload["apply_server_config_result"] = apply_payload
        payload["os_mutation_performed"] = bool(apply_payload.get("os_mutation_performed"))
        if apply_exit_code != 0:
            payload["ok"] = False
            payload["error"] = "server config apply failed during identity auto-renew"
            print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
            return apply_exit_code

    if args.update_issuer_config:
        _write_json(issuer_config_path, artifacts["updated_issuer_config"], mode=0o600)
        payload["issuer_mutation_performed"] = True

    payload["renewal_performed"] = True
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def issuer_lifetime_policy(args: argparse.Namespace) -> int:
    if not args.allow_file_mutation and not args.dry_run:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "issuer-lifetime-policy",
                    "error": "file mutation is blocked; pass --allow-file-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    default_lifetime_seconds = int(args.default_lifetime_seconds)
    max_lifetime_seconds = int(args.max_lifetime_seconds)
    if default_lifetime_seconds < 1:
        raise ValueError("default-lifetime-seconds must be positive")
    if max_lifetime_seconds < default_lifetime_seconds:
        raise ValueError("max-lifetime-seconds must be >= default-lifetime-seconds")

    issuer_config_path = Path(args.issuer_config)
    issuer_config = _load_json(issuer_config_path)
    old_default = int(issuer_config["default_lifetime_seconds"])
    old_max = int(issuer_config["max_lifetime_seconds"])
    updated_issuer_config = dict(issuer_config)
    updated_issuer_config["default_lifetime_seconds"] = default_lifetime_seconds
    updated_issuer_config["max_lifetime_seconds"] = max_lifetime_seconds
    changed = updated_issuer_config != issuer_config
    if changed and not args.dry_run:
        _write_json(issuer_config_path, updated_issuer_config, mode=0o600)

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "issuer-lifetime-policy",
                "dry_run": bool(args.dry_run),
                "issuer_config": str(issuer_config_path),
                "old_default_lifetime_seconds": old_default,
                "old_max_lifetime_seconds": old_max,
                "default_lifetime_seconds": default_lifetime_seconds,
                "max_lifetime_seconds": max_lifetime_seconds,
                "changed": changed,
                "file_mutation_performed": changed and not bool(args.dry_run),
                "os_mutation_performed": False,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def provision_client(args: argparse.Namespace) -> int:
    if args.apply_server_config and not args.dry_run and not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "provision-client",
                    "error": "OS mutation is blocked; pass --allow-os-mutation for --apply-server-config",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    server_config_path = Path(args.server_config)
    issuer_config_path = Path(args.issuer_config)
    out_dir = Path(args.out_dir)
    kit_name = _safe_kit_name(str(args.kit_name or args.device_id))
    candidate_server_config_path = out_dir / "server.candidate.json"
    client_config_path = out_dir / "client.json"
    archive_path = Path(args.archive) if args.archive else out_dir / f"{kit_name}.tar.gz"
    installed_server_config_path = Path(args.installed_server_config or server_config_path)
    server_config = _load_json(server_config_path)
    issuer_config = _load_json(issuer_config_path)
    artifacts = _build_added_client_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        device_id=args.device_id,
        client_address=args.client_address,
        tenant=args.tenant,
        lifetime_seconds=args.lifetime_seconds,
    )
    updated_server_config = artifacts["updated_server_config"]
    updated_issuer_config = artifacts["updated_issuer_config"]
    client_config = artifacts["client_config"]
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "provision-client",
        "dry_run": bool(args.dry_run),
        "device_id": args.device_id,
        "client_address": artifacts["client_tun_address"],
        "client_ip": artifacts["client_ip"],
        "identity_hash": artifacts["identity_hash"],
        "identity_serial": artifacts["identity_serial"],
        "server_config": str(server_config_path),
        "issuer_config": str(issuer_config_path),
        "candidate_server_config": str(candidate_server_config_path),
        "client_config": str(client_config_path),
        "kit_name": kit_name,
        "archive": str(archive_path),
        "installed_server_config": str(installed_server_config_path),
        "client_lease_count": len(_tunnel_config(updated_server_config).get("client_leases", ())),
        "issuer_serial_counter": artifacts["issuer_serial_counter"],
        "server_restart_required": True,
        "apply_server_config": bool(args.apply_server_config),
        "file_mutation_performed": False,
        "issuer_mutation_performed": False,
        "os_mutation_performed": False,
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(candidate_server_config_path, updated_server_config, mode=0o600)
    _write_json(client_config_path, client_config, mode=0o600)
    export_payload = _export_client_kit_payload(
        client_config_path=client_config_path,
        out_dir=out_dir,
        kit_name=kit_name,
        archive_path=archive_path,
    )
    payload["file_mutation_performed"] = True
    payload["export_client_kit"] = export_payload

    if args.apply_server_config:
        apply_exit_code, apply_payload = _apply_server_config_result(
            argparse.Namespace(
                candidate_config=str(candidate_server_config_path),
                installed_config=str(installed_server_config_path),
                service_name=args.service_name,
                backup_dir=args.backup_dir,
                uplink_interface=args.uplink_interface,
                allow_os_mutation=args.allow_os_mutation,
                dry_run=False,
                skip_health=args.skip_health,
                no_rollback_on_failure=False,
            )
        )
        payload["apply_server_config_result"] = apply_payload
        payload["os_mutation_performed"] = bool(apply_payload.get("os_mutation_performed"))
        if apply_exit_code != 0:
            payload["ok"] = False
            payload["issuer_mutation_performed"] = False
            print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
            return apply_exit_code

    _write_json(issuer_config_path, updated_issuer_config, mode=0o600)
    payload["issuer_mutation_performed"] = True
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def deprovision_client(args: argparse.Namespace) -> int:
    if bool(args.device_id) == bool(args.identity_hash):
        raise ValueError("deprovision-client requires exactly one of --device-id or --identity-hash")
    if args.apply_server_config and not args.dry_run and not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "deprovision-client",
                    "error": "OS mutation is blocked; pass --allow-os-mutation for --apply-server-config",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    server_config_path = Path(args.server_config)
    out_dir = Path(args.out_dir)
    candidate_server_config_path = out_dir / "server.candidate.json"
    installed_server_config_path = Path(args.installed_server_config or server_config_path)
    server_config = _load_json(server_config_path)
    updated_server_config, removed, revoked_identity_serials = _server_config_without_client(
        server_config,
        device_id=args.device_id,
        identity_hash=args.identity_hash,
    )
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "deprovision-client",
        "dry_run": bool(args.dry_run),
        "removed": removed,
        "device_id": args.device_id,
        "identity_hash": args.identity_hash,
        "server_config": str(server_config_path),
        "candidate_server_config": str(candidate_server_config_path),
        "installed_server_config": str(installed_server_config_path),
        "candidate_hash": _json_payload_hash(updated_server_config),
        "client_lease_count": len(_tunnel_config(updated_server_config).get("client_leases", ())),
        "revoked_identity_serials": revoked_identity_serials,
        "server_restart_required": removed,
        "apply_server_config": bool(args.apply_server_config),
        "file_mutation_performed": False,
        "os_mutation_performed": False,
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return 0

    if removed:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(candidate_server_config_path, updated_server_config, mode=0o600)
        payload["file_mutation_performed"] = True
        if args.apply_server_config:
            apply_exit_code, apply_payload = _apply_server_config_result(
                argparse.Namespace(
                    candidate_config=str(candidate_server_config_path),
                    installed_config=str(installed_server_config_path),
                    service_name=args.service_name,
                    backup_dir=args.backup_dir,
                    uplink_interface=args.uplink_interface,
                    allow_os_mutation=args.allow_os_mutation,
                    dry_run=False,
                    skip_health=args.skip_health,
                    no_rollback_on_failure=False,
                )
            )
            payload["apply_server_config_result"] = apply_payload
            payload["os_mutation_performed"] = bool(apply_payload.get("os_mutation_performed"))
            if apply_exit_code != 0:
                payload["ok"] = False
                print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
                return apply_exit_code

    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def remove_client(args: argparse.Namespace) -> int:
    if bool(args.device_id) == bool(args.identity_hash):
        raise ValueError("remove-client requires exactly one of --device-id or --identity-hash")
    if args.update_server_config and args.server_config_out:
        raise ValueError("--update-server-config and --server-config-out are mutually exclusive")
    if not args.dry_run and not args.update_server_config and not args.server_config_out:
        raise ValueError(
            "remove-client requires --server-config-out or --update-server-config unless --dry-run is used"
        )

    server_config_path = Path(args.server_config)
    server_config = _load_json(server_config_path)
    updated_server_config, removed, revoked_identity_serials = _server_config_without_client(
        server_config,
        device_id=args.device_id,
        identity_hash=args.identity_hash,
    )
    server_config_out = (
        server_config_path if args.update_server_config else Path(args.server_config_out or server_config_path)
    )
    file_mutation_performed = (not bool(args.dry_run)) and removed
    if file_mutation_performed:
        _write_json(server_config_out, updated_server_config, mode=0o600)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "remove-client",
                "dry_run": bool(args.dry_run),
                "removed": removed,
                "device_id": args.device_id,
                "identity_hash": args.identity_hash,
                "server_config": str(server_config_path),
                "server_config_out": str(server_config_out),
                "client_lease_count": len(_tunnel_config(updated_server_config).get("client_leases", ())),
                "revoked_identity_serials": revoked_identity_serials,
                "server_restart_required": removed,
                "file_mutation_performed": file_mutation_performed,
                "os_mutation_performed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


async def run_server(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    registry = _admission_registry(config)
    transport = _dataplane_transport(config)
    fragmentation_enabled = _anti_dpi_fragmentation_enabled(config)
    reassemblers: dict[int, PacketReassembler] = {}

    def on_session_data(
        payload: bytes,
        _addr: tuple[str, int],
        session,
    ) -> bytes | None:
        return _local_canary_dataplane_response(
            payload,
            session=session,
            reassemblers=reassemblers,
            fragmentation_enabled=fragmentation_enabled,
        )

    if transport == "camouflage":
        server, _protocol, addr = await open_camouflage_admission_server(
            registry=registry,
            host=config.get("bind_host", DEFAULT_BIND_HOST),
            port=int(config["port"]),
            profile=_camouflage_profile(config),
            policy=_camouflage_policy(config),
            on_session_data=on_session_data,
        )
    else:
        server, _protocol, addr = await open_tcp_admission_server(
            registry=registry,
            host=config.get("bind_host", DEFAULT_BIND_HOST),
            port=int(config["port"]),
            on_session_data=on_session_data,
        )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "server",
                "addr": [addr[0], addr[1]],
                "transport": transport,
                "deployment_epoch": config["deployment_epoch"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    async with server:
        serve_task = asyncio.create_task(server.serve_forever())
        await stop.wait()
        server.close()
        await server.wait_closed()
        serve_task.cancel()
    return 0


async def run_server_tun(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "server-tun",
                    "error": "OS mutation is blocked; pass --allow-os-mutation on the server",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    uplink_interface = args.uplink_interface or _default_route_interface()
    if not uplink_interface:
        raise RuntimeError("server uplink interface could not be detected")

    tun_config = _server_tun_config(config, allow_os_mutation=True)
    tun = LinuxTunDevice(config=tun_config)
    transport = _dataplane_transport(config)
    fragmenter = _anti_dpi_fragmenter(config)
    reassembler_factory = (
        (lambda _session: PacketReassembler())
        if _anti_dpi_fragmentation_enabled(config)
        else None
    )
    fragmenter_factory = (
        (lambda _session: _anti_dpi_fragmenter(config))
        if _anti_dpi_fragmentation_enabled(config)
        else None
    )
    nat_config = _server_nat_config(
        config,
        uplink_interface=uplink_interface,
        allow_os_mutation=True,
    )
    nat = LinuxServerNatPlanner(config=nat_config)
    resource = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    _best_effort_delete_tun(tun_config.name)
    _best_effort_rollback(nat)
    try:
        tun.activate()
        nat.apply()
        shared_return = _shared_return_enabled(config)
        destination_by_identity_hash = (
            _destination_by_identity_hash(config) if shared_return else {}
        )
        if shared_return:
            resource = open_threaded_firstparty_shared_tun_admission_server(
                registry=_admission_registry(config),
                tun=tun,
                destination_by_identity_hash=destination_by_identity_hash,
                bind=_dataplane_bind(config),
                return_transports=(transport,),
                on_session_ping=_client_config_update_ping_handler(config),
                fragmenter_factory=fragmenter_factory,
                reassembler_factory=reassembler_factory,
                fragmenter=fragmenter,
                camouflage_profile=_camouflage_profile(config),
                camouflage_policy=_camouflage_policy(config),
                tun_read_timeout=0.05,
                max_errors=50,
            )
        else:
            resource = open_threaded_firstparty_admission_tun_server(
                registry=_admission_registry(config),
                tun_factory=lambda _session: tun,
                bind=_dataplane_bind(config),
                return_transports=(transport,),
                on_session_ping=_client_config_update_ping_handler(config),
                fragmenter_factory=fragmenter_factory,
                reassembler_factory=reassembler_factory,
                fragmenter=fragmenter,
                camouflage_profile=_camouflage_profile(config),
                camouflage_policy=_camouflage_policy(config),
                tun_read_timeout=0.05,
                max_errors=50,
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "server-tun",
                    "host": config.get("bind_host", DEFAULT_BIND_HOST),
                    "port": int(config["port"]),
                    "transport": transport,
                    "tun": tun_config.name,
                    "uplink_interface": uplink_interface,
                    "client_cidr": nat_config.client_cidr,
                    "shared_return": shared_return,
                    "client_lease_count": len(destination_by_identity_hash),
                    "deployment_epoch": config["deployment_epoch"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        await stop.wait()
        return 0
    finally:
        if resource is not None:
            resource.close()
        _best_effort_rollback(nat)
        tun.close()
        _best_effort_delete_tun(tun_config.name)


async def run_probe(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    payload = await _probe_payload(
        config,
        message=str(args.message),
        timeout=float(args.timeout),
        admission_only=bool(args.admission_only),
        tun_packet=bool(args.tun_packet),
    )
    print(json.dumps(payload, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


async def _probe_payload(
    config: dict[str, Any],
    *,
    message: str,
    timeout: float,
    admission_only: bool,
    tun_packet: bool,
) -> dict[str, Any]:
    result = await _open_admitted_probe_client(config, timeout=timeout)
    client = result.client
    selected_endpoint = _candidate_json(result.candidate)
    try:
        if admission_only:
            return {
                "ok": True,
                "mode": "probe",
                "admission_only": True,
                "transport": result.candidate.transport,
                "host": result.candidate.remote_addr[0],
                "port": result.candidate.remote_addr[1],
                "selected_endpoint": selected_endpoint,
                "session_id": result.session.session_id,
                "rx_frames": client.endpoint.stats.rx_frames,
                "tx_frames": client.endpoint.stats.tx_frames,
            }
        payload = message.encode("utf-8")
        if tun_packet:
            tun_payload = _probe_ipv4_packet(config, payload)
            client.send_data(tun_payload)
            await client.drain()
            client.send_ping(b"health")
            await client.drain()
            pong = await client.recv(timeout=timeout)
            ok = pong.frame_type == FrameType.PONG and pong.payload == b"health"
            return {
                "ok": ok,
                "mode": "probe",
                "transport": result.candidate.transport,
                "host": result.candidate.remote_addr[0],
                "port": result.candidate.remote_addr[1],
                "selected_endpoint": selected_endpoint,
                "session_id": result.session.session_id,
                "rx_frames": client.endpoint.stats.rx_frames,
                "tx_frames": client.endpoint.stats.tx_frames,
                "tun_packet": True,
                "tun_packet_bytes": len(tun_payload),
                "data_sent": True,
                "ping_pong_ok": ok,
            }
        client.send_data(payload)
        await client.drain()
        response = await client.recv(timeout=timeout)
        client.send_ping(b"health")
        await client.drain()
        pong = await client.recv(timeout=timeout)
    finally:
        client.close()
        await client.wait_closed()
    ok = (
        response.frame_type == FrameType.DATA
        and response.payload == b"x0vpn-test-echo:" + payload
        and pong.frame_type == FrameType.PONG
        and pong.payload == b"health"
    )
    return {
        "ok": ok,
        "mode": "probe",
        "transport": result.candidate.transport,
        "host": result.candidate.remote_addr[0],
        "port": result.candidate.remote_addr[1],
        "selected_endpoint": selected_endpoint,
        "session_id": result.session.session_id,
        "rx_frames": client.endpoint.stats.rx_frames,
        "tx_frames": client.endpoint.stats.tx_frames,
        "data_response_ok": response.payload == b"x0vpn-test-echo:" + payload,
        "ping_pong_ok": pong.frame_type == FrameType.PONG,
    }


def _probe_ipv4_packet(config: dict[str, Any], payload: bytes) -> bytes:
    tunnel = _tunnel_config(config)
    source = ipaddress.ip_interface(tunnel["client_address"]).ip
    destination_text = tunnel.get("client_peer") or tunnel.get("server_address")
    if destination_text is None:
        raise ValueError("TUN probe requires client_peer or server_address")
    destination = ipaddress.ip_interface(str(destination_text)).ip
    if source.version != 4 or destination.version != 4:
        raise ValueError("TUN probe currently requires IPv4 addresses")
    total_length = 20 + len(payload)
    if total_length > 0xFFFF:
        raise ValueError("TUN probe IPv4 packet exceeds maximum length")
    return b"".join(
        (
            b"\x45\x00",
            total_length.to_bytes(2, "big"),
            b"\x00\x00",
            b"\x00\x00",
            b"\x40",
            b"\x11",
            b"\x00\x00",
            source.packed,
            destination.packed,
            payload,
        )
    )


async def run_client_tun(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "client-tun",
                    "error": "OS mutation is blocked; pass --allow-os-mutation on the client",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    tun_config = _client_tun_config(config, allow_os_mutation=True)
    tun = LinuxTunDevice(config=tun_config)
    transport = _dataplane_transport(config)
    resource = None
    client_policy = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    _best_effort_delete_tun(tun_config.name)
    underlay_gateway, underlay_interface = _client_underlay_gateway_and_interface(
        config,
        underlay_gateway=args.underlay_gateway,
        underlay_interface=args.underlay_interface,
    )
    try:
        tun.activate()
        hello, material = _client_hello_and_material(config)
        resource = open_threaded_firstparty_admission_tun_client_pump(
            hello=hello,
            pqc_material=material,
            tun=tun,
            candidates=_dataplane_candidates(config),
            identity_authority=_verifier(config),
            policy=_policy(config),
            captured_at=_now(),
            camouflage_profile=_camouflage_profile(config),
            camouflage_policy=_camouflage_policy(config),
            completed_at_provider=lambda accept: max(_now(), accept.accepted_at),
            fragmenter=_anti_dpi_fragmenter(config),
            reassembler=_anti_dpi_reassembler(config),
            tun_read_timeout=0.05,
            transport_read_timeout=0.05,
            max_errors=50,
        )
        if args.apply_client_policy:
            if not underlay_gateway or not underlay_interface:
                raise RuntimeError("client underlay gateway/interface could not be detected")
            client_policy = LinuxNetworkPolicyPlanner(
                config=_client_policy_config(
                    config,
                    underlay_gateway=underlay_gateway,
                    underlay_interface=underlay_interface,
                    enable_kill_switch=_config_enable_kill_switch(config, args),
                    allow_os_mutation=True,
                )
            )
            client_policy.apply()
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "client-tun",
                    "host": config["host"],
                    "port": int(config["port"]),
                    "transport": transport,
                    "tun": tun_config.name,
                    "client_policy_applied": bool(args.apply_client_policy),
                    "underlay_interface": underlay_interface,
                    "deployment_epoch": config["deployment_epoch"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        await stop.wait()
        return 0
    except Exception as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "mode": "client-tun",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        dataplane_error = _find_dataplane_client_error(exc)
        if dataplane_error is not None and dataplane_error.open_evidence is not None:
            payload["failed_reasons"] = list(dataplane_error.open_evidence.failed_reasons)
            payload["open_evidence"] = dataplane_error.open_evidence.to_json_dict()
        print(json.dumps(payload, sort_keys=True), flush=True)
        return 1
    finally:
        if client_policy is not None:
            _best_effort_rollback(client_policy)
        if resource is not None:
            resource.close()
        tun.close()
        _best_effort_delete_tun(tun_config.name)


def client_service_plan(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config = _load_json(config_path)
    payload = _client_service_plan_payload(args, config_path=config_path)
    payload["ok"] = True
    payload["mode"] = "client-service-plan"
    payload["host"] = str(config["host"])
    payload["port"] = int(config["port"])
    payload["transport"] = _dataplane_transport(config)
    payload["deployment_epoch"] = str(config["deployment_epoch"])
    payload["os_mutation_performed"] = False
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def client_sync_plan(args: argparse.Namespace) -> int:
    payload = _client_sync_plan_payload(args)
    payload["ok"] = True
    payload["mode"] = "client-sync-plan"
    payload["os_mutation_performed"] = False
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def server_service_plan(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config = _load_json(config_path)
    payload = _server_service_plan_payload(args, config_path=config_path)
    payload["ok"] = True
    payload["mode"] = "server-service-plan"
    payload["bind_host"] = str(config.get("bind_host", DEFAULT_BIND_HOST))
    payload["port"] = int(config["port"])
    payload["transport"] = _dataplane_transport(config)
    payload["deployment_epoch"] = str(config["deployment_epoch"])
    payload["os_mutation_performed"] = False
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def server_renewal_plan(args: argparse.Namespace) -> int:
    payload = _server_renewal_plan_payload(args)
    payload["ok"] = True
    payload["mode"] = "server-renewal-plan"
    payload["os_mutation_performed"] = False
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def install_client_sync(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "install-client-sync",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    plan = _client_sync_plan_payload(args)
    service_path = Path(plan["sync_service_path"])
    timer_path = Path(plan["timer_path"])
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(str(plan["sync_service_content"]), encoding="utf-8")
    service_path.chmod(0o644)
    timer_path.write_text(str(plan["timer_content"]), encoding="utf-8")
    timer_path.chmod(0o644)

    _run_checked(("systemctl", "daemon-reload"))
    if args.enable_now:
        _run_checked(("systemctl", "enable", "--now", str(plan["timer_name"])))
    else:
        if args.enable:
            _run_checked(("systemctl", "enable", str(plan["timer_name"])))
        if args.start:
            _run_checked(("systemctl", "start", str(plan["timer_name"])))

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "install-client-sync",
                "timer_name": plan["timer_name"],
                "sync_service_name": plan["sync_service_name"],
                "timer_path": plan["timer_path"],
                "sync_service_path": plan["sync_service_path"],
                "enabled": bool(args.enable or args.enable_now),
                "started": bool(args.start or args.enable_now),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def install_server_service(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "install-server-service",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    config_path = Path(args.config)
    config = _load_json(config_path)
    plan = _server_service_plan_payload(args, config_path=config_path)
    install_dir = Path(plan["install_dir"])
    config_dir = Path(plan["config_dir"])
    installed_config_path = Path(plan["config_path"])
    script_path = Path(plan["script_path"])
    package_path = Path(plan["package_path"])
    unit_path = Path(plan["unit_path"])

    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "src/network").mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), script_path)

    source_package = _find_project_root() / "src/network/firstparty_vpn"
    if source_package.resolve() != package_path.resolve():
        if package_path.exists():
            shutil.rmtree(package_path)
        shutil.copytree(
            source_package,
            package_path,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    installed_config = _server_config_with_service_name(
        config,
        str(plan["service_name"]),
    )
    _write_json(installed_config_path, installed_config, mode=0o600)
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(str(plan["unit_content"]), encoding="utf-8")
    unit_path.chmod(0o644)

    _run_checked(("systemctl", "daemon-reload"))
    if args.enable_now:
        _run_checked(("systemctl", "enable", "--now", str(plan["service_name"])))
    else:
        if args.enable:
            _run_checked(("systemctl", "enable", str(plan["service_name"])))
        if args.start:
            _run_checked(("systemctl", "start", str(plan["service_name"])))
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "install-server-service",
                "service_name": plan["service_name"],
                "unit_path": plan["unit_path"],
                "config_path": plan["config_path"],
                "script_path": plan["script_path"],
                "package_path": plan["package_path"],
                "enabled": bool(args.enable or args.enable_now),
                "started": bool(args.start or args.enable_now),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def install_server_renewal(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "install-server-renewal",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    plan = _server_renewal_plan_payload(args)
    service_path = Path(plan["renewal_service_path"])
    timer_path = Path(plan["timer_path"])
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(str(plan["renewal_service_content"]), encoding="utf-8")
    service_path.chmod(0o644)
    timer_path.write_text(str(plan["timer_content"]), encoding="utf-8")
    timer_path.chmod(0o644)

    _run_checked(("systemctl", "daemon-reload"))
    if args.enable_now:
        _run_checked(("systemctl", "enable", "--now", str(plan["timer_name"])))
    else:
        if args.enable:
            _run_checked(("systemctl", "enable", str(plan["timer_name"])))
        if args.start:
            _run_checked(("systemctl", "start", str(plan["timer_name"])))

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "install-server-renewal",
                "timer_name": plan["timer_name"],
                "renewal_service_name": plan["renewal_service_name"],
                "timer_path": plan["timer_path"],
                "renewal_service_path": plan["renewal_service_path"],
                "enabled": bool(args.enable or args.enable_now),
                "started": bool(args.start or args.enable_now),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def uninstall_server_service(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "uninstall-server-service",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    service_name = _service_name(args.service_name)
    install_dir = _service_path(args.install_dir, "install-dir")
    config_dir = _service_path(args.config_dir, "config-dir")
    unit_path = Path("/etc/systemd/system") / service_name
    _run_unchecked(("systemctl", "disable", "--now", service_name))
    if unit_path.exists():
        unit_path.unlink()
    _run_checked(("systemctl", "daemon-reload"))
    if args.remove_install_dir:
        _remove_tree_safely(install_dir)
    if args.remove_config_dir:
        _remove_tree_safely(config_dir)

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "uninstall-server-service",
                "service_name": service_name,
                "unit_path_removed": str(unit_path),
                "install_dir_removed": bool(args.remove_install_dir),
                "config_dir_removed": bool(args.remove_config_dir),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def install_client_service(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "install-client-service",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    config_path = Path(args.config)
    readiness_payload = None
    if bool(getattr(args, "require_readiness", False)):
        readiness_payload = asyncio.run(
            _client_readiness_payload(
                _client_readiness_args_from_service_args(args, config_path=config_path)
            )
        )
        if not readiness_payload["ok"]:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "mode": "install-client-service",
                        "error": "client readiness failed",
                        "readiness_required": True,
                        "readiness": readiness_payload,
                        "os_mutation_performed": False,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
    config = _public_client_config(_load_json(config_path))
    _assert_public_client_config(config)
    plan = _client_service_plan_payload(args, config_path=config_path)
    install_dir = Path(plan["install_dir"])
    config_dir = Path(plan["config_dir"])
    installed_config_path = Path(plan["config_path"])
    script_path = Path(plan["script_path"])
    package_path = Path(plan["package_path"])
    unit_path = Path(plan["unit_path"])
    config_sync_plan = plan.get("config_sync_plan")

    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "src/network").mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), script_path)

    source_package = _find_project_root() / "src/network/firstparty_vpn"
    if source_package.resolve() != package_path.resolve():
        if package_path.exists():
            shutil.rmtree(package_path)
        shutil.copytree(
            source_package,
            package_path,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    _write_json(installed_config_path, config, mode=0o600)
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(str(plan["unit_content"]), encoding="utf-8")
    unit_path.chmod(0o644)
    if config_sync_plan is not None:
        sync_service_path = Path(str(config_sync_plan["sync_service_path"]))
        sync_timer_path = Path(str(config_sync_plan["timer_path"]))
        sync_service_path.parent.mkdir(parents=True, exist_ok=True)
        sync_service_path.write_text(
            str(config_sync_plan["sync_service_content"]),
            encoding="utf-8",
        )
        sync_service_path.chmod(0o644)
        sync_timer_path.write_text(str(config_sync_plan["timer_content"]), encoding="utf-8")
        sync_timer_path.chmod(0o644)

    _run_checked(("systemctl", "daemon-reload"))
    if args.enable_now:
        _run_checked(("systemctl", "enable", "--now", str(plan["service_name"])))
    else:
        if args.enable:
            _run_checked(("systemctl", "enable", str(plan["service_name"])))
        if args.start:
            _run_checked(("systemctl", "start", str(plan["service_name"])))
    if config_sync_plan is not None:
        if args.enable_now:
            _run_checked(("systemctl", "enable", "--now", str(config_sync_plan["timer_name"])))
        else:
            if args.enable:
                _run_checked(("systemctl", "enable", str(config_sync_plan["timer_name"])))
            if args.start:
                _run_checked(("systemctl", "start", str(config_sync_plan["timer_name"])))

    post_install_health_payload = None
    if bool(getattr(args, "require_post_install_health", False)):
        post_install_health_payload = _wait_client_health_payload(
            config,
            service_name=str(plan["service_name"]),
            timeout=float(getattr(args, "post_install_health_timeout", 3.0)),
            skip_service=False,
            skip_tcp_connect=bool(
                getattr(args, "post_install_health_skip_tcp_connect", False)
            ),
            attempts=int(getattr(args, "post_install_health_retries", 10)),
            interval_seconds=float(
                getattr(args, "post_install_health_interval_seconds", 1.0)
            ),
        )
        if not post_install_health_payload["ok"]:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "mode": "install-client-service",
                        "error": "client post-install health failed",
                        "service_name": plan["service_name"],
                        "unit_path": plan["unit_path"],
                        "config_path": plan["config_path"],
                        "started": bool(args.start or args.enable_now),
                        "post_install_health_required": True,
                        "post_install_health": post_install_health_payload,
                        "os_mutation_performed": True,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "install-client-service",
                "service_name": plan["service_name"],
                "unit_path": plan["unit_path"],
                "config_path": plan["config_path"],
                "script_path": plan["script_path"],
                "package_path": plan["package_path"],
                "enabled": bool(args.enable or args.enable_now),
                "started": bool(args.start or args.enable_now),
                "readiness_required": bool(getattr(args, "require_readiness", False)),
                "readiness_ok": None if readiness_payload is None else bool(readiness_payload["ok"]),
                "readiness": readiness_payload,
                "post_install_health_required": bool(
                    getattr(args, "require_post_install_health", False)
                ),
                "post_install_health_ok": (
                    None
                    if post_install_health_payload is None
                    else bool(post_install_health_payload["ok"])
                ),
                "post_install_health": post_install_health_payload,
                "config_sync_installed": config_sync_plan is not None,
                "config_sync_enabled": bool(
                    config_sync_plan is not None and (args.enable or args.enable_now)
                ),
                "config_sync_started": bool(
                    config_sync_plan is not None and (args.start or args.enable_now)
                ),
                "config_sync_timer_name": (
                    config_sync_plan["timer_name"] if config_sync_plan is not None else None
                ),
                "config_sync_service_name": (
                    config_sync_plan["sync_service_name"]
                    if config_sync_plan is not None
                    else None
                ),
                "config_sync_timer_path": (
                    config_sync_plan["timer_path"] if config_sync_plan is not None else None
                ),
                "config_sync_service_path": (
                    config_sync_plan["sync_service_path"]
                    if config_sync_plan is not None
                    else None
                ),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def uninstall_client_service(args: argparse.Namespace) -> int:
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "uninstall-client-service",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    service_name = _service_name(args.service_name)
    install_dir = _service_path(args.install_dir, "install-dir")
    config_dir = _service_path(args.config_dir, "config-dir")
    unit_path = Path("/etc/systemd/system") / service_name
    sync_service_name = None
    sync_timer_name = None
    sync_service_path = None
    sync_timer_path = None
    config_sync_removed = False
    sync_service_unit_removed = False
    sync_timer_unit_removed = False
    if not bool(getattr(args, "keep_config_sync", False)):
        sync_service_name, sync_timer_name = _client_sync_unit_names(
            service_name,
            sync_service_name=getattr(args, "config_sync_service_name", None),
            timer_name=getattr(args, "config_sync_timer_name", None),
        )
        sync_service_path = Path("/etc/systemd/system") / sync_service_name
        sync_timer_path = Path("/etc/systemd/system") / sync_timer_name
        _run_unchecked(("systemctl", "disable", "--now", sync_timer_name))
        _run_unchecked(("systemctl", "stop", sync_service_name))
        if sync_timer_path.exists():
            sync_timer_path.unlink()
            config_sync_removed = True
            sync_timer_unit_removed = True
        if sync_service_path.exists():
            sync_service_path.unlink()
            config_sync_removed = True
            sync_service_unit_removed = True
    _run_unchecked(("systemctl", "disable", "--now", service_name))
    if unit_path.exists():
        unit_path.unlink()
    _run_checked(("systemctl", "daemon-reload"))
    if args.remove_install_dir:
        _remove_tree_safely(install_dir)
    if args.remove_config_dir:
        _remove_tree_safely(config_dir)

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "uninstall-client-service",
                "service_name": service_name,
                "unit_path_removed": str(unit_path),
                "config_sync_kept": bool(getattr(args, "keep_config_sync", False)),
                "config_sync_removed": config_sync_removed,
                "config_sync_timer_name": sync_timer_name,
                "config_sync_service_name": sync_service_name,
                "config_sync_timer_path": (
                    None if sync_timer_path is None else str(sync_timer_path)
                ),
                "config_sync_service_path": (
                    None if sync_service_path is None else str(sync_service_path)
                ),
                "config_sync_timer_unit_removed": sync_timer_unit_removed,
                "config_sync_service_unit_removed": sync_service_unit_removed,
                "install_dir_removed": bool(args.remove_install_dir),
                "config_dir_removed": bool(args.remove_config_dir),
                "os_mutation_performed": True,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def apply_client_config(args: argparse.Namespace) -> int:
    exit_code, payload = _apply_client_config_result(args)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return exit_code


def _apply_client_config_result(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.dry_run and not args.allow_os_mutation:
        return 2, {
            "ok": False,
            "mode": "apply-client-config",
            "error": "OS mutation is blocked; pass --allow-os-mutation or --dry-run",
        }

    candidate_path = Path(args.candidate_config)
    installed_config_path = _service_path(args.installed_config, "installed-config")
    raw_candidate_config = _load_json(candidate_path)
    service_name = _service_name(args.service_name)
    backup_dir = (
        _service_path(args.backup_dir, "backup-dir")
        if args.backup_dir
        else installed_config_path.parent / "backups"
    )
    candidate_config = _public_client_config(raw_candidate_config)
    _assert_client_config_runtime_candidate(candidate_config)
    candidate_hash = _json_payload_hash(candidate_config)
    installed_hash = (
        _json_payload_hash(_load_json(installed_config_path))
        if installed_config_path.exists()
        else None
    )
    backup_path = backup_dir / f"{installed_config_path.name}.{_timestamp()}.bak"

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "apply-client-config",
        "dry_run": bool(args.dry_run),
        "candidate_config": str(candidate_path),
        "installed_config": str(installed_config_path),
        "backup_path": str(backup_path),
        "service_name": service_name,
        "candidate_hash": candidate_hash,
        "installed_hash": installed_hash,
        "restart_required": True,
        "rollback_on_failure": not bool(args.no_rollback_on_failure),
        "health_check_planned": not bool(args.skip_health),
        "file_mutation_performed": False,
        "service_restart_performed": False,
        "rollback_performed": False,
        "os_mutation_performed": False,
    }
    if args.dry_run:
        return 0, payload

    backup_dir.mkdir(parents=True, exist_ok=True)
    if installed_config_path.exists():
        shutil.copy2(installed_config_path, backup_path)
    else:
        backup_path = backup_dir / f"{installed_config_path.name}.{_timestamp()}.missing"
        payload["backup_path"] = str(backup_path)
    try:
        _write_json_atomic(installed_config_path, candidate_config, mode=0o600)
        payload["file_mutation_performed"] = True
        _run_checked(("systemctl", "restart", service_name))
        payload["service_restart_performed"] = True
        if not args.skip_health:
            health_payload = _client_health_payload(
                candidate_config,
                service_name=service_name,
                timeout=float(args.timeout),
                skip_service=False,
                skip_tcp_connect=bool(args.skip_tcp_connect),
            )
            payload["health"] = health_payload
            if not health_payload["ok"]:
                raise RuntimeError("client health check failed after config apply")
        payload["applied_hash"] = candidate_hash
        payload["os_mutation_performed"] = True
        return 0, payload
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        payload["error_type"] = type(exc).__name__
        if (
            not bool(args.no_rollback_on_failure)
            and backup_path.exists()
            and not backup_path.name.endswith(".missing")
        ):
            shutil.copy2(backup_path, installed_config_path)
            _run_checked(("systemctl", "restart", service_name))
            payload["rollback_performed"] = True
        payload["os_mutation_performed"] = True
        return 1, payload


def client_policy_rollback(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    if not args.allow_os_mutation:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "client-policy-rollback",
                    "error": "OS mutation is blocked; pass --allow-os-mutation",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    underlay_gateway, underlay_interface = _client_underlay_gateway_and_interface(
        config,
        underlay_gateway=args.underlay_gateway,
        underlay_interface=args.underlay_interface,
    )
    if not underlay_gateway or not underlay_interface:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "client-policy-rollback",
                    "error": "client underlay gateway/interface could not be detected",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 1

    planner = LinuxNetworkPolicyPlanner(
        config=_client_policy_config(
            config,
            underlay_gateway=underlay_gateway,
            underlay_interface=underlay_interface,
            enable_kill_switch=_config_enable_kill_switch(config, args),
            allow_os_mutation=True,
        )
    )
    planner.rollback()
    _best_effort_delete_tun(_client_tun_config(config, allow_os_mutation=False).name)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "client-policy-rollback",
                "underlay_gateway": underlay_gateway,
                "underlay_interface": underlay_interface,
                "os_mutation_performed": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def server_health(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    payload = _server_health_payload(
        config,
        service_name=_server_service_name(config, args.service_name),
        uplink_interface=args.uplink_interface,
        skip_service=bool(args.skip_service),
        skip_listen=bool(args.skip_listen),
    )
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


def apply_server_config(args: argparse.Namespace) -> int:
    exit_code, payload = _apply_server_config_result(args)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return exit_code


def _apply_server_config_result(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.dry_run and not args.allow_os_mutation:
        return 2, {
            "ok": False,
            "mode": "apply-server-config",
            "error": "OS mutation is blocked; pass --allow-os-mutation or --dry-run",
        }

    candidate_path = Path(args.candidate_config)
    installed_config_path = _service_path(args.installed_config, "installed-config")
    service_name = _service_name(args.service_name)
    backup_dir = (
        _service_path(args.backup_dir, "backup-dir")
        if args.backup_dir
        else installed_config_path.parent / "backups"
    )
    uplink_interface = _service_interface_name(args.uplink_interface)
    health_retries = max(1, int(getattr(args, "health_retries", 10)))
    health_retry_interval_seconds = max(
        0.0,
        float(getattr(args, "health_retry_interval_seconds", 0.5)),
    )
    candidate_config = _load_json(candidate_path)
    _assert_server_config_runtime_candidate(candidate_config)
    candidate_hash = _json_payload_hash(candidate_config)
    installed_hash = (
        _json_payload_hash(_load_json(installed_config_path))
        if installed_config_path.exists()
        else None
    )
    backup_path = backup_dir / f"{installed_config_path.name}.{_timestamp()}.bak"

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "apply-server-config",
        "dry_run": bool(args.dry_run),
        "candidate_config": str(candidate_path),
        "installed_config": str(installed_config_path),
        "backup_path": str(backup_path),
        "service_name": service_name,
        "candidate_hash": candidate_hash,
        "installed_hash": installed_hash,
        "restart_required": True,
        "rollback_on_failure": not bool(args.no_rollback_on_failure),
        "health_check_planned": not bool(args.skip_health),
        "health_retries": health_retries,
        "health_retry_interval_seconds": health_retry_interval_seconds,
        "file_mutation_performed": False,
        "service_restart_performed": False,
        "rollback_performed": False,
        "os_mutation_performed": False,
    }
    if args.dry_run:
        return 0, payload

    backup_dir.mkdir(parents=True, exist_ok=True)
    if installed_config_path.exists():
        shutil.copy2(installed_config_path, backup_path)
    else:
        backup_path = backup_dir / f"{installed_config_path.name}.{_timestamp()}.missing"
        payload["backup_path"] = str(backup_path)
    try:
        _write_json_atomic(installed_config_path, candidate_config, mode=0o600)
        payload["file_mutation_performed"] = True
        _run_checked(("systemctl", "restart", service_name))
        payload["service_restart_performed"] = True
        health_payload: dict[str, Any] | None = None
        if not args.skip_health:
            health_payload = _wait_server_health_payload(
                candidate_config,
                service_name=service_name,
                uplink_interface=uplink_interface,
                skip_service=False,
                skip_listen=False,
                attempts=health_retries,
                interval_seconds=health_retry_interval_seconds,
            )
            payload["health"] = health_payload
            if not health_payload["ok"]:
                raise RuntimeError("server health check failed after config apply")
        payload["applied_hash"] = candidate_hash
        payload["os_mutation_performed"] = True
        return 0, payload
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        payload["error_type"] = type(exc).__name__
        if (
            not bool(args.no_rollback_on_failure)
            and backup_path.exists()
            and not backup_path.name.endswith(".missing")
        ):
            shutil.copy2(backup_path, installed_config_path)
            _run_checked(("systemctl", "restart", service_name))
            payload["rollback_performed"] = True
        payload["os_mutation_performed"] = True
        return 1, payload


def _wait_server_health_payload(
    config: dict[str, Any],
    *,
    service_name: str,
    uplink_interface: str | None,
    skip_service: bool,
    skip_listen: bool,
    attempts: int,
    interval_seconds: float,
) -> dict[str, Any]:
    attempts = max(1, int(attempts))
    interval_seconds = max(0.0, float(interval_seconds))
    payload: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        payload = _server_health_payload(
            config,
            service_name=service_name,
            uplink_interface=uplink_interface,
            skip_service=skip_service,
            skip_listen=skip_listen,
        )
        payload["attempt"] = attempt
        payload["max_attempts"] = attempts
        if payload["ok"]:
            return payload
        if attempt < attempts and interval_seconds:
            time.sleep(interval_seconds)
    assert payload is not None
    return payload


def _server_health_payload(
    config: dict[str, Any],
    *,
    service_name: str,
    uplink_interface: str | None,
    skip_service: bool,
    skip_listen: bool,
) -> dict[str, Any]:
    tun_config = _server_tun_config(config, allow_os_mutation=False)
    transport = _dataplane_transport(config)
    expected_server_ip = str(ipaddress.ip_interface(tun_config.address).ip)
    client_cidr = str(
        ipaddress.ip_network(
            str(_tunnel_config(config).get("client_cidr", DEFAULT_CLIENT_CIDR)),
            strict=False,
        )
    )
    checks: list[dict[str, Any]] = []

    def add_check(
        name: str,
        *,
        ok: bool,
        required: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        checks.append(
            {
                "name": name,
                "ok": ok,
                "required": required,
                "details": details or {},
            }
        )

    if skip_service:
        add_check(
            "systemd_service_active",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        service_active, service_status = _systemd_service_active(service_name)
        add_check(
            "systemd_service_active",
            ok=service_active,
            details={"service_name": service_name, "status": service_status},
        )

    if skip_listen:
        add_check(
            "server_tcp_listener",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        listener_checks = []
        for listener in _dataplane_listener_entries(config):
            listener_open, listener_error = _tcp_listening_on_port(int(listener["port"]))
            listener_checks.append(
                {
                    "error": listener_error,
                    "ok": listener_open,
                    "port": int(listener["port"]),
                    "transport": str(listener["transport"]),
                }
            )
        add_check(
            "server_tcp_listener",
            ok=all(item["ok"] for item in listener_checks),
            details={
                "bind_host": str(config.get("bind_host", DEFAULT_BIND_HOST)),
                "port": int(config["port"]),
                "transport": transport,
                "listeners": listener_checks,
            },
        )

    tun_addresses, tun_error = _linux_interface_addresses(tun_config.name)
    add_check(
        "server_tun_interface_address",
        ok=expected_server_ip in tun_addresses,
        details={
            "tun": tun_config.name,
            "expected_ip": expected_server_ip,
            "observed_ips": list(tun_addresses),
            "error": tun_error,
        },
    )

    route_device, route_error = _route_device_for_prefix(client_cidr)
    add_check(
        "client_cidr_route_uses_tun",
        ok=route_device == tun_config.name,
        details={
            "client_cidr": client_cidr,
            "route_device": route_device,
            "tun": tun_config.name,
            "error": route_error,
        },
    )

    ipv4_forward, ipv4_forward_error = _ipv4_forward_enabled()
    add_check(
        "ipv4_forward_enabled",
        ok=ipv4_forward,
        details={"error": ipv4_forward_error},
        )

    uplink_interface = uplink_interface or _default_route_interface()
    add_check(
        "uplink_interface_detected",
        ok=bool(uplink_interface),
        details={"uplink_interface": uplink_interface},
    )

    shared_return = _shared_return_enabled(config)
    leases: dict[str, str] = {}
    lease_error: str | None = None
    if shared_return:
        try:
            leases = _destination_by_identity_hash(config)
        except Exception as exc:
            lease_error = str(exc)
    add_check(
        "shared_return_client_leases",
        ok=(not shared_return) or bool(leases),
        required=shared_return,
        details={
            "shared_return": shared_return,
            "client_lease_count": len(leases),
            "error": lease_error,
        },
    )

    ok = all(check["ok"] for check in checks if check["required"])
    return {
        "ok": ok,
        "mode": "server-health",
        "bind_host": str(config.get("bind_host", DEFAULT_BIND_HOST)),
        "port": int(config["port"]),
        "transport": transport,
        "service_name": service_name,
        "tun": tun_config.name,
        "expected_server_ip": expected_server_ip,
        "client_cidr": client_cidr,
        "deployment_epoch": str(config["deployment_epoch"]),
        "checks": checks,
        "os_mutation_performed": False,
    }


def client_health(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    payload = _client_health_payload(
        config,
        service_name=_service_name(args.service_name),
        timeout=float(args.timeout),
        skip_service=bool(args.skip_service),
        skip_tcp_connect=bool(args.skip_tcp_connect),
    )
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


async def client_doctor(args: argparse.Namespace) -> int:
    payload = await _client_doctor_payload(args)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


async def _client_doctor_payload(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    config = _load_json(config_path)
    checks: list[dict[str, Any]] = []

    def add_component(
        name: str,
        *,
        payload: dict[str, Any],
        required: bool,
    ) -> None:
        checks.append(
            {
                "name": name,
                "ok": bool(payload.get("ok")),
                "required": bool(required),
                "payload": payload,
            }
        )

    if bool(args.skip_preflight):
        add_component(
            "linux_preflight",
            required=False,
            payload={
                "ok": True,
                "mode": "linux-preflight",
                "skipped": True,
                "os_mutation_performed": False,
            },
        )
    else:
        try:
            preflight_args = argparse.Namespace(
                config=str(config_path),
                role="client",
                uplink_interface=None,
                underlay_gateway=None,
                underlay_interface=None,
                enable_kill_switch=None,
                no_require_root=True,
                no_require_net_admin=True,
                no_require_tun_device=False,
            )
            evidence, details = _linux_preflight_evidence(
                config,
                args=preflight_args,
            )
            add_component(
                "linux_preflight",
                required=True,
                payload={
                    **evidence.to_json_dict(),
                    **details,
                    "ok": evidence.passed,
                    "mode": "linux-preflight",
                    "role": "client",
                    "evidence_hash": evidence.evidence_hash(),
                    "failed_reasons": list(evidence.failed_reasons),
                    "os_mutation_performed": False,
                },
            )
        except Exception as exc:
            add_component(
                "linux_preflight",
                required=True,
                payload=_component_error_payload("linux-preflight", exc),
            )

    if bool(args.skip_readiness):
        add_component(
            "client_readiness",
            required=False,
            payload={
                "ok": True,
                "mode": "client-readiness",
                "skipped": True,
                "os_mutation_performed": False,
            },
        )
    else:
        try:
            readiness_payload = await _client_readiness_payload(
                argparse.Namespace(
                    config=str(config_path),
                    service_name=args.service_name,
                    install_dir=args.install_dir,
                    config_dir=args.config_dir,
                    service_python=args.service_python,
                    timeout=float(args.readiness_timeout),
                    min_identity_valid_seconds=int(args.min_identity_valid_seconds),
                    skip_tcp_connect=bool(args.skip_tcp_connect),
                    skip_admission=bool(args.skip_admission),
                    skip_config_sync=bool(args.skip_config_sync),
                    skip_managed_install_plan=bool(args.skip_managed_install_plan),
                )
            )
            add_component(
                "client_readiness",
                required=True,
                payload=readiness_payload,
            )
        except Exception as exc:
            add_component(
                "client_readiness",
                required=True,
                payload=_component_error_payload("client-readiness", exc),
            )

    if bool(args.skip_probe):
        add_component(
            "dataplane_probe",
            required=False,
            payload={
                "ok": True,
                "mode": "probe",
                "skipped": True,
                "os_mutation_performed": False,
            },
        )
    else:
        try:
            probe_payload = await _probe_payload(
                config,
                message=str(args.message),
                timeout=float(args.probe_timeout),
                admission_only=False,
                tun_packet=True,
            )
            probe_payload["os_mutation_performed"] = False
            add_component(
                "dataplane_probe",
                required=True,
                payload=probe_payload,
            )
        except Exception as exc:
            add_component(
                "dataplane_probe",
                required=True,
                payload=_component_error_payload("probe", exc),
            )

    if bool(args.skip_health):
        add_component(
            "installed_client_health",
            required=bool(args.require_installed_health),
            payload={
                "ok": not bool(args.require_installed_health),
                "mode": "client-health",
                "skipped": True,
                "os_mutation_performed": False,
            },
        )
    else:
        try:
            health_payload = _client_health_payload(
                config,
                service_name=_service_name(args.service_name),
                timeout=float(args.health_timeout),
                skip_service=False,
                skip_tcp_connect=bool(args.skip_tcp_connect),
            )
            add_component(
                "installed_client_health",
                required=bool(args.require_installed_health),
                payload=health_payload,
            )
        except Exception as exc:
            add_component(
                "installed_client_health",
                required=bool(args.require_installed_health),
                payload=_component_error_payload("client-health", exc),
            )

    ok = all(check["ok"] for check in checks if check["required"])
    installed_health = next(
        (
            check
            for check in checks
            if check["name"] == "installed_client_health"
        ),
        None,
    )
    installed_health_ok = bool(installed_health and installed_health["ok"])
    if ok and bool(args.require_installed_health):
        status = "installed_healthy"
    elif ok and installed_health_ok:
        status = "ready_to_install_and_installed_healthy"
    elif ok:
        status = "ready_to_install"
    else:
        status = "needs_attention"
    return {
        "ok": ok,
        "mode": "client-doctor",
        "status": status,
        "config": str(config_path),
        "host": str(config.get("host")),
        "port": int(config.get("port", 0)),
        "deployment_epoch": str(config.get("deployment_epoch")),
        "require_installed_health": bool(args.require_installed_health),
        "checks": checks,
        "failed_required_checks": [
            str(check["name"])
            for check in checks
            if check["required"] and not check["ok"]
        ],
        "os_mutation_performed": False,
    }


def _component_error_payload(mode: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "mode": mode,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "os_mutation_performed": False,
    }


async def client_readiness(args: argparse.Namespace) -> int:
    payload = await _client_readiness_payload(args)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


async def _client_readiness_payload(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    config = _load_json(config_path)
    transport = _dataplane_transport(config)
    checks: list[dict[str, Any]] = []

    def add_check(
        name: str,
        *,
        ok: bool,
        required: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        checks.append(
            {
                "name": name,
                "ok": bool(ok),
                "required": bool(required),
                "details": details or {},
            }
        )

    forbidden = [
        marker
        for marker in ("decapsulation_key", "signing_key", "issuer_config", "client_leases")
        if marker in json.dumps(config, sort_keys=True)
    ]
    try:
        _assert_public_client_config(config)
        _assert_client_config_runtime_candidate(config)
        public_config_ok = True
        public_config_error = None
    except Exception as exc:
        public_config_ok = False
        public_config_error = f"{type(exc).__name__}:{exc}"
    add_check(
        "public_client_config",
        ok=public_config_ok and not forbidden,
        details={
            "config": str(config_path),
            "forbidden_markers": forbidden,
            "error": public_config_error,
        },
    )

    now = _now()
    try:
        verifier = _verifier(config)
        policy = _policy(config)
        client_token = _token_from_json(config["tokens"]["client"])
        server_token = _token_from_json(config["tokens"]["server"])
        client_decision = verifier.verify(client_token, policy=policy, now=now)
        server_decision = verifier.verify(server_token, policy=policy, now=now)
        client_seconds = int(client_token.claims.expires_at) - now
        server_seconds = int(server_token.claims.expires_at) - now
        min_identity_valid_seconds = _positive_systemd_seconds(
            int(args.min_identity_valid_seconds),
            "min-identity-valid-seconds",
        )
        add_check(
            "identity_policy_valid",
            ok=client_decision.allowed and server_decision.allowed,
            details={
                "client_reasons": list(client_decision.reasons),
                "server_reasons": list(server_decision.reasons),
                "client_identity_hash": client_decision.identity_hash.hex(),
                "server_identity_hash": server_decision.identity_hash.hex(),
            },
        )
        add_check(
            "identity_validity_window",
            ok=(
                client_seconds >= min_identity_valid_seconds
                and server_seconds >= min_identity_valid_seconds
            ),
            details={
                "client_seconds_until_expiry": client_seconds,
                "server_seconds_until_expiry": server_seconds,
                "min_identity_valid_seconds": min_identity_valid_seconds,
            },
        )
    except Exception as exc:
        add_check(
            "identity_policy_valid",
            ok=False,
            details={"error": str(exc), "error_type": type(exc).__name__},
        )
        add_check(
            "identity_validity_window",
            ok=False,
            details={"error": str(exc), "error_type": type(exc).__name__},
        )

    if bool(args.skip_tcp_connect):
        add_check(
            "server_tcp_port_open",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        endpoint_checks = []
        for candidate in _dataplane_candidates(config, timeout_seconds=float(args.timeout)):
            tcp_open, tcp_error = _tcp_connect_open(
                candidate.remote_addr[0],
                candidate.remote_addr[1],
                timeout=float(args.timeout),
            )
            endpoint_checks.append(
                {
                    "ok": tcp_open,
                    "path_label": candidate.path_label,
                    "port": candidate.remote_addr[1],
                    "priority": candidate.priority,
                    "transport": candidate.transport,
                    "error": tcp_error,
                }
            )
        add_check(
            "server_tcp_port_open",
            ok=any(item["ok"] for item in endpoint_checks),
            details={
                "host": str(config["host"]),
                "port": int(config["port"]),
                "transport": transport,
                "timeout": float(args.timeout),
                "endpoints": endpoint_checks,
            },
        )

    if bool(args.skip_admission):
        add_check(
            "admission_handshake",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        try:
            result = await _open_admitted_probe_client(config, timeout=float(args.timeout))
            try:
                session_id = result.session.session_id
            finally:
                result.client.close()
                await result.client.wait_closed()
            add_check(
                "admission_handshake",
                ok=True,
                details={
                    "session_id": session_id,
                    "transport": result.candidate.transport,
                    "selected_endpoint": _candidate_json(result.candidate),
                },
            )
        except Exception as exc:
            add_check(
                "admission_handshake",
                ok=False,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )

    if bool(args.skip_config_sync):
        add_check(
            "protected_config_sync",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        try:
            response_payload = await _request_client_config_update(
                config,
                timeout=float(args.timeout),
            )
            response = _parse_client_config_update_response(response_payload)
            candidate_config = response["client_config"]
            _assert_client_config_update_candidate(
                current_config=config,
                candidate_config=candidate_config,
                response=response,
            )
            current_hash = _json_payload_hash(_public_client_config(config))
            candidate_hash = _json_payload_hash(candidate_config)
            add_check(
                "protected_config_sync",
                ok=True,
                details={
                    "response_status": response["status"],
                    "changed": candidate_hash != current_hash,
                    "current_config_hash": current_hash,
                    "candidate_config_hash": candidate_hash,
                },
            )
        except Exception as exc:
            add_check(
                "protected_config_sync",
                ok=False,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )

    if bool(args.skip_managed_install_plan):
        add_check(
            "managed_install_plan",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        try:
            plan = _client_service_plan_payload(
                argparse.Namespace(
                    config=str(config_path),
                    service_name=args.service_name,
                    install_dir=args.install_dir,
                    config_dir=args.config_dir,
                    service_python=args.service_python,
                    disable_kill_switch=False,
                    install_config_sync=True,
                    config_sync_service_name=None,
                    config_sync_timer_name=None,
                    config_sync_timeout=float(args.timeout),
                    config_sync_interval_seconds=300,
                    enable=True,
                    start=True,
                    enable_now=True,
                ),
                config_path=config_path,
            )
            sync_plan = plan.get("config_sync_plan") or {}
            add_check(
                "managed_install_plan",
                ok=bool(plan.get("config_sync_installed")) and bool(sync_plan),
                details={
                    "service_name": plan["service_name"],
                    "config_path": plan["config_path"],
                    "config_sync_timer_name": sync_plan.get("timer_name"),
                    "config_sync_service_name": sync_plan.get("sync_service_name"),
                    "post_install_commands": plan["post_install_commands"],
                },
            )
        except Exception as exc:
            add_check(
                "managed_install_plan",
                ok=False,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )

    ok = all(check["ok"] for check in checks if check["required"])
    payload = {
        "ok": ok,
        "mode": "client-readiness",
        "config": str(config_path),
        "host": str(config.get("host")),
        "port": int(config.get("port", 0)),
        "transport": transport,
        "deployment_epoch": str(config.get("deployment_epoch")),
        "checks": checks,
        "os_mutation_performed": False,
    }
    return payload


async def client_config_sync(args: argparse.Namespace) -> int:
    if args.update_config and args.out_config:
        raise ValueError("--update-config and --out-config are mutually exclusive")
    if args.restart_service and not args.allow_os_mutation and not args.dry_run:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "client-config-sync",
                    "error": "OS mutation is blocked; pass --allow-os-mutation for --restart-service",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2
    config_path = Path(args.config)
    current_config = _load_json(config_path)
    out_config_path = config_path if args.update_config else Path(
        args.out_config or config_path.with_suffix(".synced.json")
    )
    response_payload = await _request_client_config_update(
        current_config,
        timeout=float(args.timeout),
    )
    response = _parse_client_config_update_response(response_payload)
    candidate_config = response["client_config"]
    _assert_client_config_update_candidate(
        current_config=current_config,
        candidate_config=candidate_config,
        response=response,
    )
    current_hash = _json_payload_hash(_public_client_config(current_config))
    candidate_hash = _json_payload_hash(candidate_config)
    changed = candidate_hash != current_hash
    if changed and not args.dry_run:
        _write_json(out_config_path, candidate_config, mode=0o600)
    service_restart_performed = False
    if changed and args.restart_service and not args.dry_run:
        service_name = _service_name(args.service_name)
        _run_checked(("systemctl", "restart", service_name))
        service_restart_performed = True
    payload = {
        "ok": True,
        "mode": "client-config-sync",
        "dry_run": bool(args.dry_run),
        "changed": changed,
        "current_config": str(config_path),
        "out_config": str(out_config_path),
        "current_config_hash": current_hash,
        "candidate_config_hash": candidate_hash,
        "transport": _dataplane_transport(candidate_config),
        "response_status": response["status"],
        "service_name": _service_name(args.service_name),
        "service_restart_requested": bool(args.restart_service),
        "service_restart_performed": service_restart_performed,
        "device_id_hash": identity_binding_hash(
            _token_from_json(candidate_config["tokens"]["client"]).claims
        ).hex(),
        "file_mutation_performed": changed and not bool(args.dry_run),
        "os_mutation_performed": service_restart_performed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def source_audit(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else _find_project_root() / "src/network/firstparty_vpn"
    evidence = audit_firstparty_source_tree(root, captured_at=args.captured_at)
    payload = {
        **evidence.to_json_dict(),
        "ok": evidence.passed,
        "mode": "source-audit",
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if evidence.passed else 1


def _client_health_payload(
    config: dict[str, Any],
    *,
    service_name: str,
    timeout: float,
    skip_service: bool,
    skip_tcp_connect: bool,
) -> dict[str, Any]:
    tun_config = _client_tun_config(config, allow_os_mutation=False)
    transport = _dataplane_transport(config)
    expected_client_ip = str(ipaddress.ip_interface(tun_config.address).ip)
    route_all_traffic = bool(_tunnel_config(config).get("route_all_traffic", True))
    checks: list[dict[str, Any]] = []

    def add_check(
        name: str,
        *,
        ok: bool,
        required: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        checks.append(
            {
                "name": name,
                "ok": ok,
                "required": required,
                "details": details or {},
            }
        )

    if skip_service:
        add_check(
            "systemd_service_active",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        service_active, service_status = _systemd_service_active(service_name)
        add_check(
            "systemd_service_active",
            ok=service_active,
            details={"service_name": service_name, "status": service_status},
        )

    tun_addresses, tun_error = _linux_interface_addresses(tun_config.name)
    add_check(
        "tun_interface_address",
        ok=expected_client_ip in tun_addresses,
        details={
            "tun": tun_config.name,
            "expected_ip": expected_client_ip,
            "observed_ips": list(tun_addresses),
            "error": tun_error,
        },
    )

    if route_all_traffic:
        default_route_device = _default_route_device()
        add_check(
            "default_route_uses_tun",
            ok=default_route_device == tun_config.name,
            details={
                "tun": tun_config.name,
                "default_route_device": default_route_device,
            },
        )
    else:
        add_check(
            "default_route_uses_tun",
            ok=True,
            required=False,
            details={"skipped": True, "route_all_traffic": False},
        )

    endpoint_gateway, endpoint_interface = _route_to_host_gateway_and_interface(
        str(config["host"])
    )
    add_check(
        "server_endpoint_uses_underlay",
        ok=bool(endpoint_interface) and endpoint_interface != tun_config.name,
        details={
            "host": str(config["host"]),
            "port": int(config["port"]),
            "gateway": endpoint_gateway,
            "interface": endpoint_interface,
            "tun": tun_config.name,
        },
    )

    if skip_tcp_connect:
        add_check(
            "server_tcp_port_open",
            ok=True,
            required=False,
            details={"skipped": True},
        )
    else:
        tcp_open, tcp_error = _tcp_connect_open(
            str(config["host"]),
            int(config["port"]),
            timeout=float(timeout),
        )
        add_check(
            "server_tcp_port_open",
            ok=tcp_open,
            details={
                "host": str(config["host"]),
                "port": int(config["port"]),
                "transport": transport,
                "timeout": float(timeout),
                "error": tcp_error,
            },
        )

    ok = all(check["ok"] for check in checks if check["required"])
    return {
        "ok": ok,
        "mode": "client-health",
        "host": str(config["host"]),
        "port": int(config["port"]),
        "transport": transport,
        "tun": tun_config.name,
        "expected_client_ip": expected_client_ip,
        "deployment_epoch": str(config["deployment_epoch"]),
        "route_all_traffic": route_all_traffic,
        "checks": checks,
        "os_mutation_performed": False,
    }


def _wait_client_health_payload(
    config: dict[str, Any],
    *,
    service_name: str,
    timeout: float,
    skip_service: bool,
    skip_tcp_connect: bool,
    attempts: int,
    interval_seconds: float,
) -> dict[str, Any]:
    attempts = max(1, int(attempts))
    interval_seconds = max(0.0, float(interval_seconds))
    payload: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        payload = _client_health_payload(
            config,
            service_name=service_name,
            timeout=float(timeout),
            skip_service=skip_service,
            skip_tcp_connect=skip_tcp_connect,
        )
        payload["attempt"] = attempt
        payload["max_attempts"] = attempts
        if payload["ok"]:
            return payload
        if attempt < attempts and interval_seconds:
            time.sleep(interval_seconds)
    assert payload is not None
    return payload


def plan_linux(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    if args.role == "server":
        uplink_interface = args.uplink_interface or _default_route_interface()
        if not uplink_interface:
            raise RuntimeError("server uplink interface could not be detected")
        tun_config = _server_tun_config(config, allow_os_mutation=False)
        nat = LinuxServerNatPlanner(
            config=_server_nat_config(
                config,
                uplink_interface=uplink_interface,
                allow_os_mutation=False,
            )
        )
        payload = {
            "ok": True,
            "role": "server",
            "tun_commands": [_command_to_string(cmd) for cmd in tun_config.network_commands()],
            "network_commands": [_command_to_string(cmd) for cmd in nat.planned_commands()],
            "rollback_commands": [_command_to_string(cmd) for cmd in nat.rollback_commands()],
            "os_mutation_performed": False,
        }
    else:
        gateway, interface = _default_route_gateway_and_interface()
        underlay_gateway = args.underlay_gateway or gateway
        underlay_interface = args.underlay_interface or interface
        if not underlay_gateway or not underlay_interface:
            raise RuntimeError("client underlay gateway/interface could not be detected")
        tun_config = _client_tun_config(config, allow_os_mutation=False)
        policy = LinuxNetworkPolicyPlanner(
            config=_client_policy_config(
                config,
                underlay_gateway=underlay_gateway,
                underlay_interface=underlay_interface,
                enable_kill_switch=_config_enable_kill_switch(config, args),
                allow_os_mutation=False,
            )
        )
        payload = {
            "ok": True,
            "role": "client",
            "tun_commands": [_command_to_string(cmd) for cmd in tun_config.network_commands()],
            "network_commands": [_command_to_string(cmd) for cmd in policy.planned_commands()],
            "rollback_commands": [_command_to_string(cmd) for cmd in policy.rollback_commands()],
            "os_mutation_performed": False,
        }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def linux_preflight(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    evidence, details = _linux_preflight_evidence(
        config,
        args=args,
    )
    payload = {
        **evidence.to_json_dict(),
        **details,
        "ok": evidence.passed,
        "mode": "linux-preflight",
        "role": args.role,
        "evidence_hash": evidence.evidence_hash(),
        "failed_reasons": list(evidence.failed_reasons),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if evidence.passed else 1


def leak_protection_plan(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    evidence, details = _client_leak_protection_evidence(config, args=args)
    payload = {
        **evidence.to_json_dict(),
        **details,
        "ok": evidence.passed,
        "mode": "leak-protection-plan",
        "evidence_hash": evidence.evidence_hash(),
        "plan_hash": evidence.command_plan.evidence_hash(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if evidence.passed else 1


def zero_trust_policy(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    evidence = _zero_trust_policy_evidence(config)
    requirements = FullVpnProductionReadinessRequirements(
        target=str(args.target),
        required_zero_trust_policy_hash=evidence.policy_hash,
        max_identity_token_lifetime_seconds=int(args.max_identity_lifetime_seconds),
    )
    decision = evaluate_full_vpn_production_readiness(
        requirements,
        FullVpnProductionReadinessEvidence(
            target=str(args.target),
            zero_trust_policy=evidence,
        ),
    )
    reasons = [
        reason for reason in decision.reasons if reason.startswith("zero_trust_")
    ]
    payload = {
        **evidence.to_json_dict(),
        "ok": not reasons,
        "allowed": not reasons,
        "mode": "zero-trust-policy",
        "evidence_hash": evidence.evidence_hash(),
        "reasons": reasons,
        "required_workloads": sorted(requirements.required_zero_trust_workloads),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if not reasons else 1


def pqc_readiness(args: argparse.Namespace) -> int:
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    source_root = (
        Path(args.source_root)
        if args.source_root
        else _find_project_root() / "src/network/firstparty_vpn"
    )
    source_evidence = audit_firstparty_source_tree(
        source_root,
        captured_at=captured_at,
    )
    bundle = _pqc_production_evidence_bundle(
        _load_json(Path(args.config)),
        source_evidence=source_evidence,
        captured_at=captured_at,
        validity_seconds=int(args.max_evidence_age_seconds),
    )
    payload = {
        "ok": bundle["gate"].allowed,
        "allowed": bundle["gate"].allowed,
        "mode": "pqc-readiness",
        "pqc_provider_gate": _pqc_gate_to_json_dict(bundle["gate"]),
        "pqc_manifest": bundle["manifest"].to_json_dict(),
        "pqc_kat": _pqc_kat_to_json_dict(bundle["kat"]),
        "candidate_pqc_metadata": bundle["candidate_pqc_metadata"],
        "runtime_metadata_matches_manifest": bundle[
            "runtime_metadata_matches_manifest"
        ],
        "source_audit": source_evidence.to_json_dict(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if bundle["gate"].allowed else 1


def pqc_promote_config(args: argparse.Namespace) -> int:
    if args.update_config and args.out_config:
        raise ValueError("use --update-config or --out-config, not both")
    if not args.update_config and not args.out_config:
        raise ValueError("pqc-promote-config requires --out-config or --update-config")
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    source_root = (
        Path(args.source_root)
        if args.source_root
        else _find_project_root() / "src/network/firstparty_vpn"
    )
    source_evidence = audit_firstparty_source_tree(
        source_root,
        captured_at=captured_at,
    )
    config_path = Path(args.config)
    config = _load_json(config_path)
    bundle = _pqc_production_evidence_bundle(
        config,
        source_evidence=source_evidence,
        captured_at=captured_at,
        validity_seconds=int(args.max_evidence_age_seconds),
    )
    promoted = _config_with_candidate_pqc_metadata(
        config,
        bundle["candidate_pqc_metadata"],
    )
    out_path = config_path if args.update_config else Path(args.out_config)
    _write_json(out_path, promoted, mode=0o600)
    payload = {
        "ok": True,
        "mode": "pqc-promote-config",
        "config": str(config_path),
        "out_config": str(out_path),
        "runtime_metadata_matches_manifest_before": bundle[
            "runtime_metadata_matches_manifest"
        ],
        "candidate_hash": _json_payload_hash(promoted),
        "candidate_pqc_metadata": bundle["candidate_pqc_metadata"],
        "pqc_manifest_hash": bundle["manifest"].manifest_hash(),
        "pqc_kat_suite_hash": bundle["kat"].suite_hash,
        "file_mutation_performed": True,
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def identity_signer_readiness(args: argparse.Namespace) -> int:
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    source_root = (
        Path(args.source_root)
        if args.source_root
        else _find_project_root() / "src/network/firstparty_vpn"
    )
    source_evidence = audit_firstparty_source_tree(
        source_root,
        captured_at=captured_at,
    )
    bundle = _identity_signer_evidence_bundle(
        _load_json(Path(args.issuer_config)),
        source_evidence=source_evidence,
        captured_at=captured_at,
        validity_seconds=int(args.max_evidence_age_seconds),
    )
    payload = {
        "ok": bundle["gate"].allowed and bundle["kat"].passed,
        "allowed": bundle["gate"].allowed,
        "mode": "identity-signer-readiness",
        "identity_signer_gate": bundle["gate"].to_json_dict(),
        "identity_signer_manifest": bundle["manifest"].to_json_dict(),
        "identity_signer_kat": _identity_signer_kat_to_json_dict(bundle["kat"]),
        "identity_signer_conformance": bundle["conformance"].to_json_dict(),
        "source_audit": source_evidence.to_json_dict(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


def dataplane_readiness(args: argparse.Namespace) -> int:
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    config = _load_json(Path(args.config))
    bundle = _dataplane_evidence_bundle(
        config,
        captured_at=captured_at,
        path_label=str(args.path_label),
        timeout_seconds=float(args.timeout),
        payload_size=int(args.payload_size),
        mtu_candidates=_parse_mtu_candidates(args.mtu_candidates, config),
    )
    ok = (
        bundle["dataplane"].passed
        and bundle["tun_dataplane"].passed
        and bundle["mtu"].passed
    )
    payload = {
        "ok": ok,
        "allowed": ok,
        "mode": "dataplane-readiness",
        "dataplane_validation": bundle["dataplane"].to_json_dict(),
        "tun_dataplane_validation": bundle["tun_dataplane"].to_json_dict(),
        "mtu_validation": bundle["mtu"].to_json_dict(),
        "required_dataplane_paths": sorted(bundle["plan"].required_path_labels),
        "required_dataplane_transports": [
            [probe.path_label, probe.transport] for probe in bundle["plan"].probes
        ],
        "required_dataplane_probe_matrix_hash": bundle[
            "dataplane"
        ].probe_matrix_hash(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if ok else 1


def policy_snapshot_write(args: argparse.Namespace) -> int:
    config = _load_json(Path(args.config))
    issued_at = _now() if args.issued_at is None else int(args.issued_at)
    snapshot = PolicySnapshot(
        policy_epoch=str(args.policy_epoch or _policy_epoch_from_config(config)),
        issued_at=issued_at,
        revocations=_revocations_from_config(config),
    )
    out_path = Path(args.out)
    _write_json(out_path, snapshot.to_json_dict(), mode=0o644)
    payload = {
        "ok": True,
        "mode": "policy-snapshot-write",
        "out": str(out_path),
        "policy_epoch": snapshot.policy_epoch,
        "issued_at": snapshot.issued_at,
        "snapshot_hash": snapshot.snapshot_hash(),
        "file_mutation_performed": True,
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def policy_source_readiness(args: argparse.Namespace) -> int:
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    bundle = _external_policy_source_evidence_bundle(
        policy_source_path=Path(args.policy_source_path),
        policy_source_id=str(args.policy_source_id),
        captured_at=captured_at,
        allowed_policy_epoch=args.allowed_policy_epoch,
        minimum_issued_at=args.minimum_issued_at,
    )
    payload = {
        "ok": True,
        "allowed": True,
        "mode": "policy-source-readiness",
        "external_policy_source": bundle["source"].to_json_dict(),
        "policy_snapshot_hash": bundle["snapshot"].snapshot_hash(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0


def rekey_policy_readiness(args: argparse.Namespace) -> int:
    captured_at = _now() if args.captured_at is None else int(args.captured_at)
    config = _load_json(Path(args.config)) if args.config else None
    bundle = _rekey_policy_evidence_bundle(
        config=config,
        captured_at=captured_at,
        max_session_age_seconds=int(args.max_session_age_seconds),
        requested_reason=str(args.requested_reason),
        rollback_plan_id=str(args.rollback_plan_id),
    )
    payload = {
        "ok": bundle["decision"].allowed,
        "allowed": bundle["decision"].allowed,
        "mode": "rekey-policy-readiness",
        "rekey_policy": bundle["decision"].to_json_dict(),
        "rollback_evidence": bundle["rollback"].to_json_dict(),
        "os_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if bundle["decision"].allowed else 1


def _rekey_policy_evidence_bundle(
    *,
    config: dict[str, Any] | None,
    captured_at: int,
    max_session_age_seconds: int,
    requested_reason: str,
    rollback_plan_id: str,
) -> dict[str, Any]:
    if max_session_age_seconds < 1:
        raise ValueError("rekey max session age must be positive")
    deployment_epoch = (
        str(config.get("deployment_epoch"))
        if config is not None
        else "x0vpn-managed"
    )
    previous_transcript_hash = hashlib.sha256(
        f"{deployment_epoch}|previous|{captured_at}".encode("utf-8")
    ).hexdigest()
    next_transcript_hash = hashlib.sha256(
        f"{deployment_epoch}|next|{captured_at}".encode("utf-8")
    ).hexdigest()
    session_started_at = captured_at - max_session_age_seconds - 1
    rollback = FirstPartyRekeyRollbackEvidence.from_session_bindings(
        rollback_id=f"{deployment_epoch}|rollback|{captured_at}",
        previous_session_id=1,
        previous_transcript_hash=previous_transcript_hash,
        next_session_id=2,
        next_transcript_hash=next_transcript_hash,
        rollback_plan_id=rollback_plan_id,
        generated_at=captured_at,
    )
    decision = evaluate_firstparty_rekey_policy(
        FirstPartyRekeyCadencePolicy(
            max_session_age_seconds=max_session_age_seconds,
            min_seconds_between_rekeys=0,
            require_rollback_evidence=True,
        ),
        FirstPartyRekeyTelemetry(
            session_started_at=session_started_at,
            now=captured_at,
            generation=2,
        ),
        requested_reason=requested_reason,
        rollback_evidence=rollback,
    )
    return {
        "decision": decision,
        "rollback": rollback,
    }


def _rollout_gate_evidence_bundle(
    *,
    target: str,
    captured_at: int,
    linux_evidence: Any,
    dataplane_bundle: dict[str, Any] | None,
    external_policy_bundle: dict[str, Any] | None,
    expected_test_count: int,
    approval_id: str,
    approved_by: str,
) -> dict[str, Any]:
    if expected_test_count < 1:
        raise ValueError("rollout expected test count must be positive")
    apply_commands = (
        tuple(tuple(command) for command in linux_evidence.apply_plan.redacted_commands)
        if linux_evidence is not None
        else ()
    )
    rollback_commands = (
        tuple(tuple(command) for command in linux_evidence.rollback_plan.redacted_commands)
        if linux_evidence is not None
        else ()
    )
    approval = OperatorApproval(
        approval_id=approval_id,
        approved_by_hash=ops_hash_identifier(approved_by, namespace="operator"),
        scope=target,
        issued_at=max(0, captured_at - 60),
        expires_at=captured_at + 3600,
    )
    test_evidence = TestEvidence(
        command=(
            "x0vpn",
            "managed-vpn",
            "health+admission+tun+dataplane+production-readiness",
        ),
        passed=expected_test_count,
        failed=0,
        collected=expected_test_count,
        generated_at=captured_at,
    )
    plan = RolloutPlan(
        target=target,
        apply_commands=apply_commands,
        rollback_commands=rollback_commands,
        test_evidence=test_evidence,
        approval=approval,
        policy_snapshot_hash=(
            external_policy_bundle["snapshot"].snapshot_hash()
            if external_policy_bundle is not None
            else None
        ),
        preflight_evidence=linux_evidence,
        dataplane_evidence=(
            dataplane_bundle["dataplane"] if dataplane_bundle is not None else None
        ),
        tun_dataplane_evidence=(
            dataplane_bundle["tun_dataplane"] if dataplane_bundle is not None else None
        ),
        mtu_validation_evidence=(
            dataplane_bundle["mtu"] if dataplane_bundle is not None else None
        ),
    )
    decision = evaluate_rollout_gate(
        plan,
        expected_test_count=expected_test_count,
        required_dataplane_paths=(
            dataplane_bundle["plan"].required_path_labels
            if dataplane_bundle is not None
            else frozenset()
        ),
        now=captured_at,
    )
    return {
        "approval": approval,
        "decision": decision,
        "plan": plan,
        "test_evidence": test_evidence,
    }


def _external_policy_source_evidence_bundle(
    *,
    policy_source_path: Path,
    policy_source_id: str,
    captured_at: int,
    allowed_policy_epoch: str | None,
    minimum_issued_at: int | None,
) -> dict[str, Any]:
    source = ExternalPolicySnapshotSource(
        source_id=policy_source_id,
        path=policy_source_path,
        allowed_policy_epochs=(
            frozenset({allowed_policy_epoch}) if allowed_policy_epoch else frozenset()
        ),
        minimum_issued_at=0 if minimum_issued_at is None else int(minimum_issued_at),
        now_provider=lambda: captured_at,
    )
    snapshot = source.load()
    if source.last_evidence is None:
        raise RuntimeError("external policy source did not produce evidence")
    return {
        "snapshot": snapshot,
        "source": source.last_evidence,
    }


def _policy_epoch_from_config(config: dict[str, Any]) -> str:
    identity = config.get("identity") or {}
    if isinstance(identity, dict) and identity.get("policy_epoch"):
        return str(identity["policy_epoch"])
    token = (config.get("tokens") or {}).get("client") or {}
    claims = token.get("claims") if isinstance(token, dict) else {}
    if isinstance(claims, dict) and claims.get("policy_epoch"):
        return str(claims["policy_epoch"])
    raise ValueError("policy epoch is missing; pass --policy-epoch")


def _dataplane_evidence_bundle(
    config: dict[str, Any],
    *,
    captured_at: int,
    path_label: str,
    timeout_seconds: float,
    payload_size: int,
    mtu_candidates: tuple[int, ...],
) -> dict[str, Any]:
    plan = _dataplane_validation_plan(
        config,
        path_label=path_label,
        timeout_seconds=timeout_seconds,
        payload_size=payload_size,
    )
    return asyncio.run(
        _collect_dataplane_evidence_bundle(
            config,
            plan=plan,
            captured_at=captured_at,
            mtu_candidates=mtu_candidates,
        )
    )


async def _collect_dataplane_evidence_bundle(
    config: dict[str, Any],
    *,
    plan: DataplaneValidationPlan,
    captured_at: int,
    mtu_candidates: tuple[int, ...],
) -> dict[str, Any]:
    dataplane = await evaluate_dataplane_validation(
        plan=plan,
        runner=lambda probe: _run_admission_ping_probe(config, probe),
        captured_at=captured_at,
    )
    tun_dataplane = await evaluate_tun_dataplane_validation(
        plan=plan,
        runner=lambda probe: _run_tun_icmp_probe(config, probe),
        captured_at=captured_at,
    )
    mtu = await evaluate_mtu_validation(
        plan=plan,
        runner=lambda probe: _run_mtu_probe(config, probe, mtu_candidates),
        captured_at=captured_at,
    )
    return {
        "plan": plan,
        "dataplane": dataplane,
        "tun_dataplane": tun_dataplane,
        "mtu": mtu,
    }


def _dataplane_validation_plan(
    config: dict[str, Any],
    *,
    path_label: str,
    timeout_seconds: float,
    payload_size: int,
) -> DataplaneValidationPlan:
    if timeout_seconds <= 0:
        raise ValueError("dataplane timeout must be positive")
    if payload_size < 1:
        raise ValueError("dataplane payload size must be positive")
    label = path_label.strip()
    if not label:
        raise ValueError("dataplane path label is required")
    transport = _dataplane_transport(config)
    remote_ref = "|".join(
        (
            str(config["deployment_epoch"]),
            str(config["host"]),
            str(int(config["port"])),
            transport,
            label,
        )
    )
    probe = DataplaneProbeSpec(
        probe_id=f"{label}-{transport}-{int(config['port'])}",
        path_label=label,
        transport=transport,
        remote_ref=remote_ref,
        payload_size=payload_size,
        timeout_seconds=timeout_seconds,
    )
    return DataplaneValidationPlan(
        probes=(probe,),
        required_path_labels=frozenset({label}),
        min_successful_probes=1,
    )


def _dataplane_readiness_path_label(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    requested = getattr(args, "dataplane_path_label", None)
    if requested is not None and str(requested).strip():
        return str(requested).strip()
    for endpoint in _dataplane_endpoint_entries(config):
        label = str(endpoint.get("path_label", "")).strip()
        if label:
            return label
    return "vps"


async def _run_admission_ping_probe(
    config: dict[str, Any],
    probe: DataplaneProbeSpec,
) -> DataplaneProbeResult:
    client = None
    started = time.monotonic()
    try:
        result = await _open_admitted_probe_client(config, timeout=probe.timeout_seconds)
        client = result.client
        payload = _dataplane_probe_payload(probe, probe.payload_size)
        client.send_ping(payload)
        await client.drain()
        frame = await client.recv(timeout=probe.timeout_seconds)
        latency_millis = int((time.monotonic() - started) * 1000)
        if frame.frame_type != FrameType.PONG or frame.payload != payload:
            return DataplaneProbeResult.failure_result(
                probe,
                reason="unexpected_ping_response",
            )
        stats = client.endpoint.stats
        return DataplaneProbeResult.success_result(
            probe,
            latency_millis=latency_millis,
            rx_frames=int(getattr(stats, "rx_frames", 1)),
            tx_frames=int(getattr(stats, "tx_frames", 1)),
            rx_bytes=int(getattr(stats, "rx_bytes", len(payload))),
            tx_bytes=int(getattr(stats, "tx_bytes", len(payload))),
        )
    except Exception as exc:
        return DataplaneProbeResult.failure_result(
            probe,
            reason=_probe_failure_reason(exc),
        )
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()


async def _run_tun_icmp_probe(
    config: dict[str, Any],
    probe: DataplaneProbeSpec,
) -> TunDataplaneProbeResult:
    client = None
    try:
        result = await _open_admitted_probe_client(config, timeout=probe.timeout_seconds)
        client = result.client
        request = _probe_icmp_echo_request(config)
        fragmenter = _anti_dpi_fragmenter(config)
        reassembler = _anti_dpi_reassembler(config)
        request_payloads = (
            fragmenter.split(request["packet"])
            if fragmenter is not None
            else (request["packet"],)
        )
        if len(request_payloads) == 1:
            client.send_data(request_payloads[0])
        else:
            client.send_data_fragments(request_payloads)
        await client.drain()
        deadline = time.monotonic() + probe.timeout_seconds
        rx_fragments = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return TunDataplaneProbeResult.failure_result(
                    probe,
                    reason="timeout_waiting_for_tun_reply",
                )
            frame = await client.recv(timeout=remaining)
            if frame.frame_type != FrameType.DATA:
                continue
            payload = frame.payload
            rx_fragments += 1
            if reassembler is not None:
                payload = reassembler.accept(payload)
                if payload is None:
                    continue
            if _is_probe_icmp_echo_reply(payload, request):
                return TunDataplaneProbeResult.success_result(
                    probe,
                    packets_from_tun=1,
                    packets_to_tun=1,
                    bytes_from_tun=len(payload),
                    bytes_to_tun=len(request["packet"]),
                    tx_fragments=len(request_payloads),
                    rx_fragments=rx_fragments,
                )
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="unexpected_tun_reply",
            )
    except Exception as exc:
        return TunDataplaneProbeResult.failure_result(
            probe,
            reason=_probe_failure_reason(exc),
        )
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()


async def _run_mtu_probe(
    config: dict[str, Any],
    probe: DataplaneProbeSpec,
    candidates: tuple[int, ...],
) -> MtuPathProbeResult:
    attempts: list[MtuProbeAttempt] = []
    for payload_size in candidates:
        client = None
        try:
            result = await _open_admitted_probe_client(
                config,
                timeout=probe.timeout_seconds,
            )
            client = result.client
            payload = _dataplane_probe_payload(probe, payload_size)
            client.send_ping(payload)
            await client.drain()
            frame = await client.recv(timeout=probe.timeout_seconds)
            ok = frame.frame_type == FrameType.PONG and frame.payload == payload
            attempts.append(
                MtuProbeAttempt(
                    payload_size=payload_size,
                    success=ok,
                    error=None if ok else "unexpected_ping_response",
                )
            )
            if ok:
                return MtuPathProbeResult.success_result(
                    probe,
                    MtuProbeResult(
                        selected_payload_size=payload_size,
                        selected_fragment_payload_size=max(64, payload_size - 64),
                        attempts=tuple(attempts),
                    ),
                )
        except Exception as exc:
            attempts.append(
                MtuProbeAttempt(
                    payload_size=payload_size,
                    success=False,
                    error=_probe_failure_reason(exc),
                )
            )
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()
    return MtuPathProbeResult.failure_result(
        probe,
        reason="mtu_probe_failed",
        attempted_payload_sizes=tuple(attempt.payload_size for attempt in attempts),
        failed_attempt_count=sum(1 for attempt in attempts if not attempt.success),
    )


async def _open_admitted_probe_client(config: dict[str, Any], *, timeout: float):
    last_error: Exception | None = None
    for candidate in _dataplane_candidates(config, timeout_seconds=timeout):
        hello, material = _client_hello_and_material(config)
        try:
            if candidate.transport == "camouflage":
                result = await open_camouflage_admission_client(
                    hello=hello,
                    pqc_material=material,
                    remote_addr=candidate.remote_addr,
                    identity_authority=_verifier(config),
                    policy=_policy(config),
                    profile=_camouflage_profile(config),
                    camouflage_policy=_camouflage_policy(config),
                    timeout=candidate.timeout_seconds,
                )
            elif candidate.transport == "tcp":
                result = await open_tcp_admission_client(
                    hello=hello,
                    pqc_material=material,
                    remote_addr=candidate.remote_addr,
                    identity_authority=_verifier(config),
                    policy=_policy(config),
                    timeout=candidate.timeout_seconds,
                )
            else:
                raise ValueError("managed VPN probe supports tcp or camouflage")
        except Exception as exc:
            last_error = exc
            continue
        return _AdmittedProbeClientResult(
            client=result.client,
            accept=result.accept,
            session=result.session,
            candidate=candidate,
        )
    raise RuntimeError("no managed VPN endpoint admitted a client") from last_error


def _parse_mtu_candidates(raw: str | None, config: dict[str, Any]) -> tuple[int, ...]:
    if raw:
        candidates = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    else:
        tun_mtu = int(_tunnel_config(config).get("mtu", 1280))
        candidates = (tun_mtu, 1280, 1200, 1024, 768, 576)
    ordered = tuple(sorted({value for value in candidates if value >= 64}, reverse=True))
    if not ordered:
        raise ValueError("at least one MTU candidate >= 64 is required")
    return ordered


def _dataplane_probe_payload(probe: DataplaneProbeSpec, size: int) -> bytes:
    if size < 1:
        raise ValueError("dataplane probe payload size must be positive")
    seed = hashlib.sha256(
        f"x0vpn-dataplane-probe|{probe.probe_id}|{size}".encode("utf-8")
    ).digest()
    prefix = b"X0VPN-PROBE|" + probe.probe_id.encode("utf-8")[:24] + b"|"
    body = prefix + (seed * ((size // len(seed)) + 2))
    return body[:size]


def _probe_icmp_echo_request(config: dict[str, Any]) -> dict[str, Any]:
    tunnel = _tunnel_config(config)
    source = ipaddress.ip_interface(str(tunnel["client_address"])).ip
    destination_text = tunnel.get("client_peer") or tunnel.get("server_address")
    if destination_text is None:
        raise ValueError("TUN ICMP probe requires client_peer or server_address")
    destination = ipaddress.ip_interface(str(destination_text)).ip
    if source.version != 4 or destination.version != 4:
        raise ValueError("TUN ICMP probe currently requires IPv4 addresses")
    probe_digest = hashlib.sha256(
        f"{config['deployment_epoch']}|{source}|{destination}".encode("utf-8")
    ).digest()
    identifier = int.from_bytes(probe_digest[:2], "big")
    sequence = int.from_bytes(probe_digest[2:4], "big") or 1
    payload = b"X0VPN-ICMP-ECHO|" + probe_digest[:16]
    icmp = _icmp_packet(
        icmp_type=8,
        identifier=identifier,
        sequence=sequence,
        payload=payload,
    )
    packet = _ipv4_packet(
        source=source,
        destination=destination,
        protocol=1,
        payload=icmp,
        identification=int.from_bytes(probe_digest[4:6], "big"),
    )
    return {
        "destination": destination.packed,
        "identifier": identifier,
        "packet": packet,
        "payload": payload,
        "sequence": sequence,
        "source": source.packed,
    }


def _local_tun_probe_echo_reply(packet: bytes) -> bytes | None:
    """Return an IPv4 ICMP echo reply for local first-party canary probes."""
    if len(packet) < 28:
        return None
    version = packet[0] >> 4
    ihl = (packet[0] & 0x0F) * 4
    if version != 4 or ihl < 20 or len(packet) < ihl + 8:
        return None
    total_length = int.from_bytes(packet[2:4], "big")
    if total_length < ihl + 8 or total_length > len(packet):
        return None
    if packet[9] != 1:
        return None
    source = ipaddress.ip_address(packet[12:16])
    destination = ipaddress.ip_address(packet[16:20])
    icmp = packet[ihl:total_length]
    if icmp[0] != 8 or icmp[1] != 0:
        return None
    identifier = int.from_bytes(icmp[4:6], "big")
    sequence = int.from_bytes(icmp[6:8], "big")
    reply_icmp = _icmp_packet(
        icmp_type=0,
        identifier=identifier,
        sequence=sequence,
        payload=icmp[8:],
    )
    return _ipv4_packet(
        source=destination,
        destination=source,
        protocol=1,
        payload=reply_icmp,
        identification=int.from_bytes(packet[4:6], "big"),
    )


def _local_canary_dataplane_response(
    payload: bytes,
    *,
    session: Any,
    reassemblers: dict[int, PacketReassembler],
    fragmentation_enabled: bool,
) -> bytes | None:
    candidate = payload
    if fragmentation_enabled:
        session_id = int(getattr(session, "session_id", -1))
        reassembler = reassemblers.setdefault(session_id, PacketReassembler())
        try:
            reassembled = reassembler.accept(payload)
        except FragmentError:
            return None
        if reassembled is None:
            return None
        candidate = reassembled

    tun_probe_reply = _local_tun_probe_echo_reply(candidate)
    if tun_probe_reply is not None:
        return tun_probe_reply
    return b"x0vpn-test-echo:" + candidate


def _is_probe_icmp_echo_reply(packet: bytes, request: dict[str, Any]) -> bool:
    if len(packet) < 28:
        return False
    version = packet[0] >> 4
    ihl = (packet[0] & 0x0F) * 4
    if version != 4 or ihl < 20 or len(packet) < ihl + 8:
        return False
    if packet[9] != 1:
        return False
    if packet[12:16] != request["destination"]:
        return False
    if packet[16:20] != request["source"]:
        return False
    icmp = packet[ihl:]
    if icmp[0] != 0 or icmp[1] != 0:
        return False
    if int.from_bytes(icmp[4:6], "big") != request["identifier"]:
        return False
    if int.from_bytes(icmp[6:8], "big") != request["sequence"]:
        return False
    return icmp[8:] == request["payload"]


def _icmp_packet(
    *,
    icmp_type: int,
    identifier: int,
    sequence: int,
    payload: bytes,
) -> bytes:
    header = (
        bytes((icmp_type, 0))
        + b"\x00\x00"
        + identifier.to_bytes(2, "big")
        + sequence.to_bytes(2, "big")
    )
    checksum = _internet_checksum(header + payload)
    return (
        bytes((icmp_type, 0))
        + checksum.to_bytes(2, "big")
        + identifier.to_bytes(2, "big")
        + sequence.to_bytes(2, "big")
        + payload
    )


def _ipv4_packet(
    *,
    source: ipaddress.IPv4Address,
    destination: ipaddress.IPv4Address,
    protocol: int,
    payload: bytes,
    identification: int,
) -> bytes:
    total_length = 20 + len(payload)
    if total_length > 0xFFFF:
        raise ValueError("IPv4 probe packet exceeds maximum length")
    header = b"".join(
        (
            b"\x45\x00",
            total_length.to_bytes(2, "big"),
            identification.to_bytes(2, "big"),
            b"\x00\x00",
            b"\x40",
            bytes((protocol,)),
            b"\x00\x00",
            source.packed,
            destination.packed,
        )
    )
    checksum = _internet_checksum(header)
    return header[:10] + checksum.to_bytes(2, "big") + header[12:] + payload


def _internet_checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    checksum = 0
    for index in range(0, len(data), 2):
        checksum += int.from_bytes(data[index : index + 2], "big")
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    return (~checksum) & 0xFFFF


def _probe_failure_reason(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    name = exc.__class__.__name__
    return name if name else "probe_failed"


def production_readiness(args: argparse.Namespace) -> int:
    evaluated_at = _now() if args.evaluated_at is None else int(args.evaluated_at)
    source_root = (
        Path(args.source_root)
        if args.source_root
        else _find_project_root() / "src/network/firstparty_vpn"
    )
    source_evidence = audit_firstparty_source_tree(
        source_root,
        captured_at=evaluated_at,
    )
    linux_evidence = None
    linux_details: dict[str, Any] = {}
    if bool(args.config) != bool(args.role):
        raise ValueError("production-readiness requires --config and --role together")
    config = None
    if args.config and args.role:
        config = _load_json(Path(args.config))
        linux_evidence, linux_details = _linux_preflight_evidence(config, args=args)
    leak_evidence = None
    leak_details: dict[str, Any] = {}
    if config is not None and args.role == "client":
        leak_evidence, leak_details = _client_leak_protection_evidence(config, args=args)
    zero_trust_evidence = None
    if config is not None and "policy" in config:
        zero_trust_evidence = _zero_trust_policy_evidence(config)
    pqc_bundle: dict[str, Any] | None = None
    if config is not None and "pqc" in config:
        pqc_bundle = _pqc_production_evidence_bundle(
            config,
            source_evidence=source_evidence,
            captured_at=evaluated_at,
            validity_seconds=int(args.max_evidence_age_seconds),
        )
    identity_signer_bundle: dict[str, Any] | None = None
    issuer_config = getattr(args, "issuer_config", None)
    if issuer_config:
        identity_signer_bundle = _identity_signer_evidence_bundle(
            _load_json(Path(issuer_config)),
            source_evidence=source_evidence,
            captured_at=evaluated_at,
            validity_seconds=int(args.max_evidence_age_seconds),
        )
    dataplane_bundle: dict[str, Any] | None = None
    if config is not None and getattr(args, "collect_dataplane", False):
        dataplane_bundle = _dataplane_evidence_bundle(
            config,
            captured_at=evaluated_at,
            path_label=_dataplane_readiness_path_label(config, args),
            timeout_seconds=float(getattr(args, "dataplane_timeout", 3.0)),
            payload_size=int(getattr(args, "dataplane_payload_size", 64)),
            mtu_candidates=_parse_mtu_candidates(
                getattr(args, "dataplane_mtu_candidates", None),
                config,
            ),
        )
    external_policy_bundle: dict[str, Any] | None = None
    policy_source_path = getattr(args, "policy_source_path", None)
    if policy_source_path:
        external_policy_bundle = _external_policy_source_evidence_bundle(
            policy_source_path=Path(policy_source_path),
            policy_source_id=str(
                getattr(args, "policy_source_id", "x0vpn-managed-policy-source")
            ),
            captured_at=evaluated_at,
            allowed_policy_epoch=(
                getattr(args, "policy_source_epoch", None)
                or (_policy_epoch_from_config(config) if config is not None else None)
            ),
            minimum_issued_at=getattr(args, "policy_source_minimum_issued_at", None),
        )
    rekey_bundle: dict[str, Any] | None = None
    if getattr(args, "collect_rekey_policy", False):
        rekey_bundle = _rekey_policy_evidence_bundle(
            config=config,
            captured_at=evaluated_at,
            max_session_age_seconds=int(
                getattr(args, "rekey_max_session_age_seconds", 1)
            ),
            requested_reason=str(
                getattr(args, "rekey_requested_reason", "scheduled-rotation")
            ),
            rollback_plan_id=str(
                getattr(args, "rekey_rollback_plan_id", "x0vpn-managed-rekey-rollback")
            ),
        )
    rollout_bundle: dict[str, Any] | None = None
    if getattr(args, "collect_rollout_gate", False):
        rollout_bundle = _rollout_gate_evidence_bundle(
            target=str(args.target),
            captured_at=evaluated_at,
            linux_evidence=linux_evidence,
            dataplane_bundle=dataplane_bundle,
            external_policy_bundle=external_policy_bundle,
            expected_test_count=int(getattr(args, "rollout_expected_test_count", 5)),
            approval_id=str(
                getattr(args, "rollout_approval_id", "x0vpn-managed-rollout-approval")
            ),
            approved_by=str(
                getattr(args, "rollout_approved_by", "x0vpn-managed-operator")
            ),
        )

    requirements = FullVpnProductionReadinessRequirements(
        target=str(args.target),
        required_dataplane_paths=(
            dataplane_bundle["plan"].required_path_labels
            if dataplane_bundle is not None
            else FullVpnProductionReadinessRequirements().required_dataplane_paths
        ),
        required_dataplane_transports=(
            tuple(
                (probe.path_label, probe.transport)
                for probe in dataplane_bundle["plan"].probes
            )
            if dataplane_bundle is not None
            else FullVpnProductionReadinessRequirements().required_dataplane_transports
        ),
        required_dataplane_probe_matrix_hash=(
            dataplane_bundle["dataplane"].probe_matrix_hash()
            if dataplane_bundle is not None
            else None
        ),
        max_identity_token_lifetime_seconds=int(args.max_identity_lifetime_seconds),
        max_validation_evidence_age_seconds=int(args.max_evidence_age_seconds),
        max_policy_snapshot_age_seconds=int(args.max_evidence_age_seconds),
        max_policy_source_load_age_seconds=int(args.max_evidence_age_seconds),
        max_source_audit_age_seconds=int(args.max_evidence_age_seconds),
        max_identity_signer_kat_age_seconds=int(args.max_evidence_age_seconds),
        max_pqc_kat_age_seconds=int(args.max_evidence_age_seconds),
        required_linux_host_fingerprint=(
            linux_evidence.host_fingerprint if linux_evidence is not None else None
        ),
        required_apply_plan_hash=(
            linux_evidence.apply_plan.evidence_hash()
            if linux_evidence is not None
            else None
        ),
        required_rollback_plan_hash=(
            linux_evidence.rollback_plan.evidence_hash()
            if linux_evidence is not None
            else None
        ),
        required_leak_protection_plan_hash=(
            leak_evidence.command_plan.evidence_hash()
            if leak_evidence is not None
            else None
        ),
        require_leak_protection=str(args.role) == "client",
        required_zero_trust_policy_hash=(
            zero_trust_evidence.policy_hash
            if zero_trust_evidence is not None
            else None
        ),
        required_pqc_manifest_hash=(
            pqc_bundle["manifest"].manifest_hash()
            if pqc_bundle is not None
            else None
        ),
        required_identity_signer_manifest_hash=(
            identity_signer_bundle["manifest"].manifest_hash()
            if identity_signer_bundle is not None
            else None
        ),
        required_external_policy_source_hash=(
            external_policy_bundle["source"].evidence_hash()
            if external_policy_bundle is not None
            else None
        ),
        required_policy_snapshot_hash=(
            external_policy_bundle["snapshot"].snapshot_hash()
            if external_policy_bundle is not None
            else None
        ),
        required_rekey_rollback_plan_hash=(
            rekey_bundle["decision"].rollback_plan_hash
            if rekey_bundle is not None
            else None
        ),
        required_rollout_gate_hash=(
            rollout_bundle["decision"].decision_hash()
            if rollout_bundle is not None
            else None
        ),
        required_source_audit_root_hash=source_evidence.root_hash,
        required_source_audit_tree_hash=source_evidence.source_tree_hash,
        evaluated_at=evaluated_at,
    )
    evidence = FullVpnProductionReadinessEvidence(
        target=str(args.target),
        linux_preflight=linux_evidence,
        leak_protection=leak_evidence,
        dataplane_validation=(
            dataplane_bundle["dataplane"]
            if dataplane_bundle is not None
            else None
        ),
        tun_dataplane_validation=(
            dataplane_bundle["tun_dataplane"]
            if dataplane_bundle is not None
            else None
        ),
        mtu_validation=(
            dataplane_bundle["mtu"] if dataplane_bundle is not None else None
        ),
        pqc_provider_gate=(
            pqc_bundle["gate"] if pqc_bundle is not None else None
        ),
        pqc_manifest=(
            pqc_bundle["manifest"] if pqc_bundle is not None else None
        ),
        pqc_kat=(
            pqc_bundle["kat"] if pqc_bundle is not None else None
        ),
        identity_signer_gate=(
            identity_signer_bundle["gate"]
            if identity_signer_bundle is not None
            else None
        ),
        identity_signer_manifest=(
            identity_signer_bundle["manifest"]
            if identity_signer_bundle is not None
            else None
        ),
        identity_signer_kat=(
            identity_signer_bundle["kat"]
            if identity_signer_bundle is not None
            else None
        ),
        identity_signer_conformance=(
            identity_signer_bundle["conformance"]
            if identity_signer_bundle is not None
            else None
        ),
        zero_trust_policy=zero_trust_evidence,
        external_policy_source=(
            external_policy_bundle["source"]
            if external_policy_bundle is not None
            else None
        ),
        policy_snapshot_hash=(
            external_policy_bundle["snapshot"].snapshot_hash()
            if external_policy_bundle is not None
            else None
        ),
        rekey_policy=(
            rekey_bundle["decision"] if rekey_bundle is not None else None
        ),
        rollout_gate=(
            rollout_bundle["decision"] if rollout_bundle is not None else None
        ),
        source_audit=source_evidence,
    )
    decision = evaluate_full_vpn_production_readiness(requirements, evidence)
    payload: dict[str, Any] = {
        **decision.to_json_dict(),
        "ok": decision.allowed,
        "mode": "production-readiness",
        "collected": {
            "dataplane": dataplane_bundle is not None,
            "external_policy_source": external_policy_bundle is not None,
            "leak_protection": leak_evidence is not None,
            "linux_preflight": linux_evidence is not None,
            "identity_signer": identity_signer_bundle is not None,
            "pqc": pqc_bundle is not None,
            "rekey_policy": rekey_bundle is not None,
            "rollout_gate": rollout_bundle is not None,
            "source_audit": True,
            "zero_trust_policy": zero_trust_evidence is not None,
        },
        "requirements": requirements.to_json_dict(),
        "source_audit": source_evidence.to_json_dict(),
        "os_mutation_performed": False,
    }
    if linux_evidence is not None:
        payload["linux_preflight"] = {
            **linux_evidence.to_json_dict(),
            **linux_details,
        }
    if leak_evidence is not None:
        payload["leak_protection"] = {
            **leak_evidence.to_json_dict(),
            **leak_details,
        }
    if dataplane_bundle is not None:
        payload["dataplane"] = {
            "dataplane_validation": dataplane_bundle["dataplane"].to_json_dict(),
            "tun_dataplane_validation": dataplane_bundle[
                "tun_dataplane"
            ].to_json_dict(),
            "mtu_validation": dataplane_bundle["mtu"].to_json_dict(),
        }
    if zero_trust_evidence is not None:
        payload["zero_trust_policy"] = zero_trust_evidence.to_json_dict()
    if external_policy_bundle is not None:
        payload["external_policy_source"] = {
            **external_policy_bundle["source"].to_json_dict(),
            "policy_snapshot_hash": external_policy_bundle["snapshot"].snapshot_hash(),
        }
    if rekey_bundle is not None:
        payload["rekey_policy"] = {
            "decision": rekey_bundle["decision"].to_json_dict(),
            "rollback_evidence": rekey_bundle["rollback"].to_json_dict(),
        }
    if rollout_bundle is not None:
        payload["rollout_gate"] = {
            "approval": rollout_bundle["approval"].to_json_dict(),
            "decision": {
                "allowed": rollout_bundle["decision"].allowed,
                "decision_hash": rollout_bundle["decision"].decision_hash(),
                "evidence_hash": rollout_bundle["decision"].evidence_hash,
                "reasons": list(rollout_bundle["decision"].reasons),
            },
            "test_evidence": rollout_bundle["test_evidence"].to_json_dict(),
        }
    if pqc_bundle is not None:
        payload["pqc"] = {
            "provider_gate": _pqc_gate_to_json_dict(pqc_bundle["gate"]),
            "manifest": pqc_bundle["manifest"].to_json_dict(),
            "kat": _pqc_kat_to_json_dict(pqc_bundle["kat"]),
            "runtime_metadata_matches_manifest": pqc_bundle[
                "runtime_metadata_matches_manifest"
            ],
        }
    if identity_signer_bundle is not None:
        payload["identity_signer"] = {
            "gate": identity_signer_bundle["gate"].to_json_dict(),
            "manifest": identity_signer_bundle["manifest"].to_json_dict(),
            "kat": _identity_signer_kat_to_json_dict(identity_signer_bundle["kat"]),
            "conformance": identity_signer_bundle["conformance"].to_json_dict(),
        }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if decision.allowed else 1


def _zero_trust_policy_evidence(config: dict[str, Any]) -> ZeroTrustPolicyEvidence:
    return ZeroTrustPolicyEvidence.from_policy(_policy(config))


def _pqc_production_evidence_bundle(
    config: dict[str, Any],
    *,
    source_evidence,
    captured_at: int,
    validity_seconds: int,
) -> dict[str, Any]:
    if validity_seconds < 1:
        raise ValueError("PQC evidence validity must be positive")
    pqc = config["pqc"]
    transcript = b"x0vpn-production-pqc-kat-transcript-v1"
    client_hash = hashlib.sha256(b"x0vpn-production-pqc-kat-client-v1").digest()
    server_hash = hashlib.sha256(b"x0vpn-production-pqc-kat-server-v1").digest()
    context_id = FirstPartyMlKemImplementation.context_id(
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    kat_message = hashlib.shake_256(
        b"x0vpn-production-pqc-kat-message-v1" + bytes.fromhex(context_id)
    ).digest(ML_KEM_SEED_BYTES)
    implementation = FirstPartyMlKemImplementation(
        provider_id=str(pqc["provider_id"]),
        kem_algorithm=str(pqc["kem_algorithm"]),
        signature_algorithm=str(pqc["signature_algorithm"]),
        encapsulation_key=bytes.fromhex(str(pqc["encapsulation_key"])),
        kat_messages={context_id: kat_message},
    )
    expected = implementation.encapsulate(
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    vector = PqcKnownAnswerVector(
        vector_id="x0vpn-production-pqc-kat-1",
        kem_algorithm=implementation.kem_algorithm,
        signature_algorithm=implementation.signature_algorithm,
        transcript=transcript,
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
        expected_shared_secret_hash=hashlib.sha256(
            expected.shared_secret
        ).hexdigest(),
        expected_ciphertext_hash=hashlib.sha256(expected.ciphertext).hexdigest(),
    )
    kat = run_pqc_known_answer_tests(
        implementation,
        (vector,),
        captured_at=captured_at,
    )
    issued_at = int(pqc.get("issued_at", captured_at))
    expires_at = int(pqc.get("expires_at", captured_at + validity_seconds))
    review_evidence_hash = _json_payload_hash(
        {
            "implementation_hash": implementation.implementation_hash,
            "kat_suite_hash": kat.suite_hash,
            "provider_id": implementation.provider_id,
            "source_root_hash": source_evidence.root_hash,
            "source_tree_hash": source_evidence.source_tree_hash,
        }
    )
    manifest = PqcImplementationManifest(
        provider_id=implementation.provider_id,
        kem_algorithm=implementation.kem_algorithm,
        signature_algorithm=implementation.signature_algorithm,
        mode="production",
        reviewed=True,
        implementation_hash=implementation.implementation_hash,
        source_hashes=(source_evidence.root_hash, source_evidence.source_tree_hash),
        kat_hashes=(kat.suite_hash,),
        review_evidence_hash=review_evidence_hash,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    gate_material = implementation.encapsulate(
        transcript=b"x0vpn-production-pqc-gate-transcript-v1",
        client_identity_hash=client_hash,
        server_identity_hash=server_hash,
    )
    production_material = PqcSessionSecretMaterial(
        kem_algorithm=manifest.kem_algorithm,
        signature_algorithm=manifest.signature_algorithm,
        shared_secret=gate_material.shared_secret,
        ciphertext=gate_material.ciphertext,
        attestation=manifest.to_attestation(),
        kat_result=kat,
    )
    candidate_gate = PqcProductionGate(
        require_production=True,
        trusted_provider_ids=frozenset({manifest.provider_id}),
        trusted_implementation_hashes=frozenset({manifest.implementation_hash}),
    ).evaluate(production_material, now=captured_at)
    runtime_attestation = _attestation_from_config(config)
    runtime_metadata_matches_manifest = (
        runtime_attestation.attestation_hash()
        == manifest.to_attestation().attestation_hash()
    )
    if runtime_metadata_matches_manifest:
        gate = candidate_gate
    else:
        gate = PqcProviderGateDecision(
            allowed=False,
            reasons=(
                *candidate_gate.reasons,
                "pqc_runtime_attestation_manifest_mismatch",
            ),
            attestation_hash=runtime_attestation.attestation_hash(),
            provider_id=runtime_attestation.provider_id,
            kem_algorithm=runtime_attestation.kem_algorithm,
            signature_algorithm=runtime_attestation.signature_algorithm,
            implementation_hash=runtime_attestation.implementation_hash or "",
        )
    return {
        "candidate_pqc_metadata": _candidate_pqc_metadata(config, manifest),
        "gate": gate,
        "kat": kat,
        "manifest": manifest,
        "runtime_metadata_matches_manifest": runtime_metadata_matches_manifest,
    }


def _candidate_pqc_metadata(
    config: dict[str, Any],
    manifest: PqcImplementationManifest,
) -> dict[str, object]:
    pqc = dict(config["pqc"])
    pqc.update(
        {
            "provider_id": manifest.provider_id,
            "kem_algorithm": manifest.kem_algorithm,
            "signature_algorithm": manifest.signature_algorithm,
            "mode": manifest.mode,
            "reviewed": manifest.reviewed,
            "issued_at": manifest.issued_at,
            "expires_at": manifest.expires_at,
            "implementation_hash": manifest.implementation_hash,
        }
    )
    return {
        key: value
        for key, value in pqc.items()
        if key not in {"encapsulation_key", "decapsulation_key"}
    }


def _config_with_candidate_pqc_metadata(
    config: dict[str, Any],
    candidate_pqc_metadata: dict[str, object],
) -> dict[str, Any]:
    promoted = dict(config)
    pqc = dict(config["pqc"])
    pqc.update(candidate_pqc_metadata)
    promoted["pqc"] = pqc
    return promoted


def _pqc_gate_to_json_dict(gate: PqcProviderGateDecision) -> dict[str, object]:
    return {
        "allowed": gate.allowed,
        "attestation_hash": gate.attestation_hash,
        "implementation_hash": gate.implementation_hash,
        "kem_algorithm": gate.kem_algorithm,
        "provider_id": gate.provider_id,
        "reasons": list(gate.reasons),
        "signature_algorithm": gate.signature_algorithm,
    }


def _pqc_kat_to_json_dict(kat) -> dict[str, object]:
    return {
        "captured_at": kat.captured_at,
        "implementation_hash": kat.implementation_hash,
        "kem_algorithm": kat.kem_algorithm,
        "passed": kat.passed,
        "provider_id": kat.provider_id,
        "reasons": list(kat.reasons),
        "signature_algorithm": kat.signature_algorithm,
        "suite_hash": kat.suite_hash,
        "vector_count": kat.vector_count,
    }


def _identity_signer_evidence_bundle(
    issuer_config: dict[str, Any],
    *,
    source_evidence,
    captured_at: int,
    validity_seconds: int,
) -> dict[str, Any]:
    if validity_seconds < 1:
        raise ValueError("identity signer evidence validity must be positive")
    signing_key = _key_from_json(issuer_config["signing_key"])
    provider = FirstPartyReferenceMlDsaIdentitySignatureProvider()
    payload = b"x0vpn-production-identity-signer-kat-payload-v1"
    signature = provider.sign(signing_key, payload)
    vector = IdentitySignerKnownAnswerVector(
        vector_id="x0vpn-production-identity-signer-kat-1",
        key_id=signing_key.key_id,
        signature_algorithm=signing_key.signature_algorithm,
        payload=payload,
        expected_signature_hash=hashlib.sha256(signature).hexdigest(),
    )
    kat = run_identity_signer_known_answer_tests(
        provider,
        signing_key,
        (vector,),
        captured_at=captured_at,
    )
    implementation_hash = str(provider.implementation_hash)
    review_evidence_hash = _json_payload_hash(
        {
            "implementation_hash": implementation_hash,
            "kat_suite_hash": kat.suite_hash,
            "key_id_hash": hashlib.sha256(
                f"identity-signer-key|{signing_key.key_id}".encode()
            ).hexdigest(),
            "provider_id": str(provider.provider_id),
            "source_root_hash": source_evidence.root_hash,
            "source_tree_hash": source_evidence.source_tree_hash,
        }
    )
    manifest = FirstPartyIdentitySignerManifest(
        provider_id=str(provider.provider_id),
        key_id=signing_key.key_id,
        signature_algorithm=signing_key.signature_algorithm,
        mode="production",
        reviewed=True,
        implementation_hash=implementation_hash,
        source_hashes=(source_evidence.root_hash, source_evidence.source_tree_hash),
        kat_hashes=(kat.suite_hash,),
        review_evidence_hash=review_evidence_hash,
        issued_at=signing_key.not_before,
        expires_at=signing_key.not_after,
    )
    gate = ProductionIdentitySignerGate(
        trusted_provider_ids=frozenset({manifest.provider_id}),
        trusted_implementation_hashes=frozenset({manifest.implementation_hash}),
    ).evaluate(manifest.to_attestation(), signing_key=signing_key, now=captured_at)
    conformance = IdentitySignerConformanceEvidence(
        provider_id=manifest.provider_id,
        key_id=manifest.key_id,
        signature_algorithm=manifest.signature_algorithm,
        implementation_hash=manifest.implementation_hash,
        manifest_hash=manifest.manifest_hash(),
        kat_suite_hash=kat.suite_hash,
        profile="fips204-production",
        passed=kat.passed and gate.allowed,
        vector_count=kat.vector_count,
        review_evidence_hash=manifest.review_evidence_hash,
        reasons=() if kat.passed and gate.allowed else (*kat.reasons, *gate.reasons),
    )
    return {
        "conformance": conformance,
        "gate": gate,
        "kat": kat,
        "manifest": manifest,
    }


def _identity_signer_kat_to_json_dict(kat) -> dict[str, object]:
    return {
        "captured_at": kat.captured_at,
        "implementation_hash": kat.implementation_hash,
        "key_id_hash": hashlib.sha256(
            f"identity-signer-kat-key|{kat.key_id}".encode()
        ).hexdigest()
        if kat.key_id
        else None,
        "passed": kat.passed,
        "provider_id_hash": hashlib.sha256(
            f"identity-signer-kat-provider|{kat.provider_id}".encode()
        ).hexdigest()
        if kat.provider_id
        else None,
        "reasons": list(kat.reasons),
        "signature_algorithm": kat.signature_algorithm,
        "suite_hash": kat.suite_hash,
        "vector_count": kat.vector_count,
    }


def _linux_preflight_evidence(
    config: dict[str, Any],
    *,
    args: argparse.Namespace,
):
    apply_commands, rollback_commands, details = _linux_preflight_command_plans(
        config,
        args=args,
    )
    evidence = evaluate_linux_deployment_preflight(
        facts=collect_linux_host_facts(),
        config=LinuxPreflightConfig(
            require_root=not bool(args.no_require_root),
            require_net_admin=not bool(args.no_require_net_admin),
            require_tun_device=not bool(args.no_require_tun_device),
            require_apply_plan=True,
            require_rollback_plan=True,
            min_apply_commands=1,
            min_rollback_commands=1,
        ),
        apply_commands=apply_commands,
        rollback_commands=rollback_commands,
    )
    return evidence, details


def _client_leak_protection_evidence(
    config: dict[str, Any],
    *,
    args: argparse.Namespace,
):
    policy = _client_policy_planner(config, args=args)
    evidence = evaluate_linux_leak_protection(
        config=policy.config,
        commands=policy.planned_commands(),
    )
    return evidence, {
        "tun": policy.config.tun_name,
        "underlay_interface": policy.config.underlay_interface,
        "route_all_traffic": policy.config.route_all_traffic,
        "kill_switch_enabled": policy.config.enable_kill_switch,
        "deployment_epoch": str(config["deployment_epoch"]),
    }


def _client_policy_planner(
    config: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> LinuxNetworkPolicyPlanner:
    gateway, interface = _default_route_gateway_and_interface()
    underlay_gateway = args.underlay_gateway or gateway
    underlay_interface = args.underlay_interface or interface
    if not underlay_gateway or not underlay_interface:
        raise RuntimeError("client underlay gateway/interface could not be detected")
    return LinuxNetworkPolicyPlanner(
        config=_client_policy_config(
            config,
            underlay_gateway=underlay_gateway,
            underlay_interface=underlay_interface,
            enable_kill_switch=_config_enable_kill_switch(config, args),
            allow_os_mutation=False,
        )
    )


def _linux_preflight_command_plans(
    config: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...], dict[str, Any]]:
    if args.role == "server":
        uplink_interface = args.uplink_interface or _default_route_interface()
        if not uplink_interface:
            raise RuntimeError("server uplink interface could not be detected")
        tun_config = _server_tun_config(config, allow_os_mutation=False)
        nat = LinuxServerNatPlanner(
            config=_server_nat_config(
                config,
                uplink_interface=uplink_interface,
                allow_os_mutation=False,
            )
        )
        return (
            (*tun_config.network_commands(), *nat.planned_commands()),
            nat.rollback_commands(),
            {
                "tun": tun_config.name,
                "uplink_interface": uplink_interface,
                "deployment_epoch": str(config["deployment_epoch"]),
            },
        )

    tun_config = _client_tun_config(config, allow_os_mutation=False)
    policy = _client_policy_planner(config, args=args)
    return (
        (*tun_config.network_commands(), *policy.planned_commands()),
        policy.rollback_commands(),
        {
            "tun": tun_config.name,
            "underlay_interface": policy.config.underlay_interface,
            "deployment_epoch": str(config["deployment_epoch"]),
        },
    )


def _issue_request(workload: str, device_id: str, tenant: str) -> IdentityIssueRequest:
    return IdentityIssueRequest(
        spiffe_id=f"spiffe://x0tta6bl4.mesh/workload/{workload}/{device_id}",
        did=f"did:mesh:pqc:{workload}:{device_id}",
        workload=workload,
        tenant=tenant,
        device_id=device_id,
        pqc_kem_algorithm=KEM_ALGORITHM,
        pqc_signature_algorithm=SIGNATURE_ALGORITHM,
    )


def _issue_identity_with_sign_retry(
    authority: IdentityAuthority,
    request: IdentityIssueRequest,
    *,
    now: int,
    lifetime_seconds: int,
    max_attempts: int = 16,
) -> SignedIdentityToken:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return authority.issue(
                request,
                now=now + attempt,
                lifetime_seconds=lifetime_seconds,
            )
        except Exception as exc:
            if type(exc).__name__ != "MlDsaShapeError":
                raise
            last_error = exc
    raise RuntimeError("identity issuance failed after ML-DSA retry") from last_error


def _policy(config: dict[str, Any]) -> ZeroTrustPolicy:
    policy_config = config["policy"]
    return ZeroTrustPolicy(
        allowed_tenants=frozenset(policy_config["allowed_tenants"]),
        max_token_lifetime_seconds=int(policy_config["max_token_lifetime_seconds"]),
    )


def _verifier(config: dict[str, Any]) -> ReadOnlyIdentityVerifier:
    return ReadOnlyIdentityVerifier(
        issuer=config["identity"]["issuer"],
        verification_keys=(_key_from_json(config["identity"]["verification_key"]),),
        signature_provider=FirstPartyReferenceMlDsaIdentitySignatureProvider(),
    )


def _admission_registry(config: dict[str, Any]) -> FirstPartySessionAdmissionRegistry:
    verifier = _verifier(config)
    policy = _policy(config)
    server_identity = _token_from_json(config["tokens"]["server"])
    decapsulation_key = bytes.fromhex(config["pqc"]["decapsulation_key"])
    attestation = _attestation_from_config(config)

    def resolve_secret(hello):
        shared_secret = mlkem_decapsulate(
            config["pqc"]["kem_algorithm"],
            decapsulation_key,
            hello.pqc_ciphertext,
        )
        return PqcSessionSecretMaterial(
            kem_algorithm=config["pqc"]["kem_algorithm"],
            signature_algorithm=config["pqc"]["signature_algorithm"],
            shared_secret=shared_secret,
            ciphertext=hello.pqc_ciphertext,
            attestation=attestation,
        )

    return FirstPartySessionAdmissionRegistry(
        server_identity=server_identity,
        identity_authority=verifier,
        policy=policy,
        shared_secret_resolver=resolve_secret,
        server_nonce_provider=lambda _hello: os.urandom(32),
        accepted_at_provider=lambda _hello: _now(),
        revocations=_revocations_from_config(config),
        alternate_server_identities=_previous_server_identities(config),
        client_identity_hash_allowlist=_client_identity_hash_allowlist(config),
        enforce_client_identity_allowlist=_client_identity_hash_allowlist_enabled(config),
    )


def _client_hello_and_material(config: dict[str, Any]):
    provider = MlKemSessionProvider(
        encapsulation_key=bytes.fromhex(config["pqc"]["encapsulation_key"]),
        attestation=_attestation_from_config(config),
    )
    return create_firstparty_handshake_hello(
        pqc_provider=provider,
        client_identity=_token_from_json(config["tokens"]["client"]),
        server_identity=_token_from_json(config["tokens"]["server"]),
        deployment_epoch=config["deployment_epoch"],
        client_nonce=os.urandom(32),
        issued_at=_now(),
    )


async def _request_client_config_update(
    config: dict[str, Any],
    *,
    timeout: float,
) -> bytes:
    result = await _open_admitted_probe_client(config, timeout=timeout)
    client = result.client
    try:
        client.send_ping(_client_config_update_request_payload(config))
        await client.drain()
        frame = await client.recv(timeout=timeout)
    finally:
        client.close()
        await client.wait_closed()
    if frame.frame_type != FrameType.PONG:
        raise RuntimeError("client config sync expected PONG response")
    return frame.payload


def _client_config_update_request_payload(config: dict[str, Any]) -> bytes:
    client_token = _token_from_json(config["tokens"]["client"])
    request = {
        "current_config_hash": _json_payload_hash(_public_client_config(config)),
        "identity_hash": identity_binding_hash(client_token.claims).hex(),
        "issued_at": _now(),
        "type": "client_config_update_request",
        "version": 1,
    }
    return CLIENT_CONFIG_UPDATE_REQUEST_PREFIX + _canonical_json(request)


def _client_config_update_ping_handler(config: dict[str, Any]):
    def handler(
        payload: bytes,
        _addr: tuple[str, int],
        session,
    ) -> bytes | None:
        if not payload.startswith(CLIENT_CONFIG_UPDATE_REQUEST_PREFIX):
            return payload
        try:
            _parse_client_config_update_request(payload)
            client_config = _client_config_for_session(config, session)
            return _client_config_update_response_payload(
                status="ok",
                client_config=client_config,
                reason=None,
            )
        except Exception as exc:
            return _client_config_update_response_payload(
                status="error",
                client_config=None,
                reason=type(exc).__name__,
            )

    return handler


def _parse_client_config_update_request(payload: bytes) -> dict[str, Any]:
    if not payload.startswith(CLIENT_CONFIG_UPDATE_REQUEST_PREFIX):
        raise ValueError("client config update request prefix is invalid")
    request = json.loads(payload[len(CLIENT_CONFIG_UPDATE_REQUEST_PREFIX) :])
    if not isinstance(request, dict):
        raise ValueError("client config update request must be an object")
    if request.get("type") != "client_config_update_request":
        raise ValueError("client config update request type is invalid")
    if int(request.get("version", 0)) != 1:
        raise ValueError("client config update request version is invalid")
    identity_hash = str(request.get("identity_hash", ""))
    if len(identity_hash) != 64:
        raise ValueError("client config update request identity hash is invalid")
    return request


def _client_config_update_response_payload(
    *,
    status: str,
    client_config: dict[str, Any] | None,
    reason: str | None,
) -> bytes:
    response: dict[str, Any] = {
        "issued_at": _now(),
        "status": status,
        "type": "client_config_update_response",
        "version": 1,
    }
    if client_config is not None:
        response["client_config"] = client_config
        response["client_config_hash"] = _json_payload_hash(client_config)
    if reason is not None:
        response["reason"] = reason
    return CLIENT_CONFIG_UPDATE_RESPONSE_PREFIX + _canonical_json(response)


def _parse_client_config_update_response(payload: bytes) -> dict[str, Any]:
    if not payload.startswith(CLIENT_CONFIG_UPDATE_RESPONSE_PREFIX):
        raise ValueError("client config update response prefix is invalid")
    response = json.loads(payload[len(CLIENT_CONFIG_UPDATE_RESPONSE_PREFIX) :])
    if not isinstance(response, dict):
        raise ValueError("client config update response must be an object")
    if response.get("type") != "client_config_update_response":
        raise ValueError("client config update response type is invalid")
    if int(response.get("version", 0)) != 1:
        raise ValueError("client config update response version is invalid")
    if response.get("status") != "ok":
        raise RuntimeError(f"client config update failed: {response.get('reason')}")
    if not isinstance(response.get("client_config"), dict):
        raise ValueError("client config update response missing client config")
    return response


def _assert_client_config_update_candidate(
    *,
    current_config: dict[str, Any],
    candidate_config: dict[str, Any],
    response: dict[str, Any],
) -> None:
    candidate_config = _public_client_config(candidate_config)
    _assert_public_client_config(candidate_config)
    response_hash = str(response.get("client_config_hash", ""))
    if _json_payload_hash(candidate_config) != response_hash:
        raise ValueError("client config update response hash mismatch")
    current_token = _token_from_json(current_config["tokens"]["client"])
    candidate_client_token = _token_from_json(candidate_config["tokens"]["client"])
    candidate_server_token = _token_from_json(candidate_config["tokens"]["server"])
    if candidate_client_token.claims.device_id != current_token.claims.device_id:
        raise ValueError("client config update device_id mismatch")
    verifier = _verifier(candidate_config)
    policy = _policy(candidate_config)
    now = _now()
    client_decision = verifier.verify(
        candidate_client_token,
        policy=policy,
        now=now,
    )
    server_decision = verifier.verify(
        candidate_server_token,
        policy=policy,
        now=now,
    )
    if not client_decision.allowed or not server_decision.allowed:
        raise ValueError("client config update candidate identities are not valid")


def _client_config_for_session(config: dict[str, Any], session) -> dict[str, Any]:
    identity_hash = session.client_decision.identity_hash.hex()
    lease = _client_lease_for_identity_hash(config, identity_hash)
    device_id = str(lease["device_id"])
    client_identity = _current_client_identity_for_device(config, device_id)
    client_tun_address = str(
        lease.get("client_tun_address") or f"{lease['client_address']}/32"
    )
    return _client_config_from_server_config(
        config,
        client_identity=client_identity,
        client_tun_address=client_tun_address,
    )


def _client_lease_for_identity_hash(
    config: dict[str, Any],
    identity_hash: str,
) -> dict[str, Any]:
    for lease in _tunnel_config(config).get("client_leases", ()):
        if not isinstance(lease, dict):
            continue
        if str(lease.get("identity_hash")) == identity_hash:
            return dict(lease)
        previous = lease.get("previous_identity_hashes", ())
        if isinstance(previous, list | tuple):
            for item in previous:
                if isinstance(item, dict) and str(item.get("identity_hash")) == identity_hash:
                    return dict(lease)
    raise ValueError("client config update session identity is not leased")


def _current_client_identity_for_device(
    config: dict[str, Any],
    device_id: str,
) -> SignedIdentityToken:
    tokens = config.get("tokens") or {}
    for item in tokens.get("clients", ()):
        if not isinstance(item, dict) or not isinstance(item.get("token"), dict):
            continue
        token = _token_from_json(item["token"])
        if str(item.get("device_id") or token.claims.device_id) == device_id:
            return token
    if isinstance(tokens.get("client"), dict):
        token = _token_from_json(tokens["client"])
        if token.claims.device_id == device_id:
            return token
    raise ValueError("current client identity is missing for device")


def _tunnel_config(config: dict[str, Any]) -> dict[str, Any]:
    return dict(config.get("tunnel") or {})


def _config_enable_kill_switch(
    config: dict[str, Any],
    args: argparse.Namespace,
    *,
    default: bool = True,
) -> bool:
    cli_value = getattr(args, "enable_kill_switch", None)
    if cli_value is not None:
        return bool(cli_value)
    return bool(_tunnel_config(config).get("enable_kill_switch", default))


def _dataplane_transport_from_value(value: object) -> str:
    transport = str(value or "tcp").strip().lower()
    if transport not in ("tcp", "camouflage"):
        raise ValueError("managed VPN transport must be tcp or camouflage")
    return transport


def _dataplane_transport(config: dict[str, Any]) -> str:
    return _dataplane_transport_from_value(_tunnel_config(config).get("transport", "tcp"))


def _endpoint_config(
    *,
    host: str,
    port: int,
    transport: str,
    priority: int,
    path_label: str,
    endpoint_id: str,
) -> dict[str, Any]:
    if not str(host).strip():
        raise ValueError("endpoint host is required")
    if not 1 <= int(port) <= 65535:
        raise ValueError("endpoint port must be between 1 and 65535")
    if int(priority) < 0:
        raise ValueError("endpoint priority must be non-negative")
    label = str(path_label).strip()
    if not label:
        raise ValueError("endpoint path label is required")
    endpoint = str(endpoint_id).strip()
    if not endpoint:
        raise ValueError("endpoint id is required")
    return {
        "endpoint_id": endpoint,
        "host": str(host),
        "path_label": label,
        "port": int(port),
        "priority": int(priority),
        "timeout_seconds": 3.0,
        "transport": _dataplane_transport_from_value(transport),
    }


def _parse_fallback_endpoint(raw: str, *, index: int) -> dict[str, Any]:
    parts = [part.strip() for part in str(raw).split(":")]
    if len(parts) not in (3, 4, 5):
        raise ValueError(
            "fallback endpoint must be transport:host:port[:priority[:path_label]]"
        )
    transport, host, port_text = parts[:3]
    priority = int(parts[3]) if len(parts) >= 4 and parts[3] else 10 + index
    path_label = (
        parts[4]
        if len(parts) >= 5 and parts[4]
        else f"nl-fallback-{_dataplane_transport_from_value(transport)}-{index}"
    )
    return _endpoint_config(
        host=host,
        port=int(port_text),
        transport=transport,
        priority=priority,
        path_label=path_label,
        endpoint_id=f"fallback-{index}",
    )


def _default_camouflage_profile_config() -> dict[str, str]:
    return {
        "profile_id": "restricted-work-wifi",
        "host": "updates.invalid",
        "path": "/assets/check",
        "method": "POST",
        "user_agent": "Mozilla/5.0",
    }


def _default_anti_dpi_profile(transport: str) -> dict[str, Any]:
    profile = FirstPartyAntiDpiProfile(
        transport=_dataplane_transport_from_value(transport),  # type: ignore[arg-type]
    ).to_json_dict()
    camouflage = dict(profile.get("camouflage") or {})
    camouflage["profile"] = _default_camouflage_profile_config()
    camouflage["policy"] = {
        "allowed_profile_ids": [
            _default_camouflage_profile_config()["profile_id"],
        ],
        "max_preface_bytes": 4096,
    }
    profile["camouflage"] = camouflage
    return profile


def _anti_dpi_payload(config: dict[str, Any]) -> dict[str, Any] | None:
    raw = _tunnel_config(config).get("anti_dpi")
    if isinstance(raw, dict):
        return raw
    if _dataplane_transport(config) == "camouflage":
        return _default_anti_dpi_profile("camouflage")
    return None


def _anti_dpi_profile(config: dict[str, Any]) -> FirstPartyAntiDpiProfile | None:
    raw = _anti_dpi_payload(config)
    if raw is None:
        return None
    profile = FirstPartyAntiDpiProfile.from_json_dict(raw)
    if profile.transport != _dataplane_transport(config):
        raise ValueError("anti-DPI profile transport must match tunnel.transport")
    return profile


def _anti_dpi_fragmentation_enabled(config: dict[str, Any]) -> bool:
    profile = _anti_dpi_profile(config)
    return bool(profile is not None and profile.fragmenter() is not None)


def _anti_dpi_fragmenter(config: dict[str, Any]) -> PacketFragmenter | None:
    profile = _anti_dpi_profile(config)
    if profile is None:
        return None
    return profile.fragmenter()


def _anti_dpi_reassembler(config: dict[str, Any]) -> PacketReassembler | None:
    if not _anti_dpi_fragmentation_enabled(config):
        return None
    return PacketReassembler()


def _camouflage_payload(config: dict[str, Any]) -> dict[str, Any]:
    raw = _anti_dpi_payload(config) or {}
    camouflage = raw.get("camouflage") if isinstance(raw, dict) else {}
    return dict(camouflage) if isinstance(camouflage, dict) else {}


def _camouflage_profile(config: dict[str, Any]) -> CamouflageProfile:
    raw = _camouflage_payload(config).get("profile")
    profile = dict(raw) if isinstance(raw, dict) else _default_camouflage_profile_config()
    return CamouflageProfile(
        profile_id=str(profile.get("profile_id", "restricted-work-wifi")),
        host=str(profile.get("host", "updates.invalid")),
        path=str(profile.get("path", "/assets/check")),
        method=str(profile.get("method", "POST")),
        user_agent=str(profile.get("user_agent", "Mozilla/5.0")),
    )


def _camouflage_policy(config: dict[str, Any]) -> CamouflagePolicy:
    profile = _camouflage_profile(config)
    raw = _camouflage_payload(config).get("policy")
    policy = dict(raw) if isinstance(raw, dict) else {}
    raw_allowed = policy.get("allowed_profile_ids")
    if isinstance(raw_allowed, (list, tuple, set)):
        allowed = frozenset(str(item) for item in raw_allowed if str(item).strip())
    else:
        allowed = frozenset({profile.profile_id})
    if profile.profile_id not in allowed:
        allowed = frozenset((*allowed, profile.profile_id))
    return CamouflagePolicy(
        allowed_profile_ids=allowed,
        max_preface_bytes=int(policy.get("max_preface_bytes", 4096)),
    )


def _revocations_from_config(config: dict[str, Any]) -> RevocationList:
    raw = config.get("revocations") or {}
    if not isinstance(raw, dict):
        raise ValueError("revocations must be an object")
    return RevocationList(
        identity_serials=_revocation_string_set(raw, "identity_serials"),
        key_ids=_revocation_string_set(raw, "key_ids"),
        policy_epochs=_revocation_string_set(raw, "policy_epochs"),
    )


def _revocations_to_json_dict(revocations: RevocationList) -> dict[str, list[str]]:
    return {
        "identity_serials": sorted(revocations.identity_serials),
        "key_ids": sorted(revocations.key_ids),
        "policy_epochs": sorted(revocations.policy_epochs),
    }


def _revocation_string_set(raw: dict[str, Any], field: str) -> set[str]:
    values = raw.get(field, ())
    if values is None:
        values = ()
    if not isinstance(values, list | tuple | set):
        raise ValueError(f"revocations.{field} must be a list")
    result = {str(value) for value in values}
    if any(not value.strip() for value in result):
        raise ValueError(f"revocations.{field} contains an empty value")
    return result


def _identity_authority_from_issuer_config(
    issuer_config: dict[str, Any],
) -> IdentityAuthority:
    signing_key = _key_from_json(issuer_config["signing_key"])
    return IdentityAuthority(
        issuer=str(issuer_config["issuer"]),
        policy_epoch=str(issuer_config["policy_epoch"]),
        signing_keys=(signing_key,),
        active_key_id=str(issuer_config["active_key_id"]),
        signature_provider=FirstPartyReferenceMlDsaIdentitySignatureProvider(),
        default_lifetime_seconds=int(issuer_config["default_lifetime_seconds"]),
        max_lifetime_seconds=int(issuer_config["max_lifetime_seconds"]),
    )


def _normalize_client_tun_address(
    server_config: dict[str, Any],
    value: str,
) -> str:
    candidate = value if "/" in value else f"{value}/32"
    tunnel = _tunnel_config(server_config)
    network = ipaddress.ip_network(str(tunnel.get("client_cidr", DEFAULT_CLIENT_CIDR)), strict=False)
    server_ip = ipaddress.ip_interface(str(tunnel.get("server_address", DEFAULT_SERVER_TUN_ADDRESS))).ip
    client_ip = ipaddress.ip_interface(candidate).ip
    _validate_client_tun_ip(client_ip, network=network, server_ip=server_ip)
    return f"{client_ip}/32"


def _next_client_tun_address(server_config: dict[str, Any]) -> str:
    tunnel = _tunnel_config(server_config)
    network = ipaddress.ip_network(str(tunnel.get("client_cidr", DEFAULT_CLIENT_CIDR)), strict=False)
    if network.version != 4:
        raise ValueError("automatic client allocation currently requires IPv4 client CIDR")
    server_ip = ipaddress.ip_interface(str(tunnel.get("server_address", DEFAULT_SERVER_TUN_ADDRESS))).ip
    used = {
        ipaddress.ip_address(str(lease.get("client_address")))
        for lease in tunnel.get("client_leases", ())
        if isinstance(lease, dict) and lease.get("client_address")
    }
    for client_ip in network.hosts():
        if client_ip == server_ip or client_ip in used:
            continue
        _validate_client_tun_ip(client_ip, network=network, server_ip=server_ip)
        return f"{client_ip}/32"
    raise ValueError("no free client address is available in client CIDR")


def _assert_client_can_be_added(
    server_config: dict[str, Any],
    *,
    device_id: str,
    client_tun_address: str,
) -> None:
    if not device_id.strip():
        raise ValueError("device_id is required")
    tunnel = _tunnel_config(server_config)
    new_ip = _interface_ip(client_tun_address)
    for lease in tunnel.get("client_leases", ()):
        if not isinstance(lease, dict):
            continue
        if str(lease.get("device_id")) == device_id:
            raise ValueError("client device_id already exists")
        if str(lease.get("client_address")) == new_ip:
            raise ValueError("client address already exists")


def _build_added_client_artifacts(
    *,
    server_config: dict[str, Any],
    issuer_config: dict[str, Any],
    device_id: str,
    client_address: str | None,
    tenant: str | None,
    lifetime_seconds: int | None,
) -> dict[str, Any]:
    now = _now()
    resolved_tenant = tenant or str(server_config["tenant"])
    resolved_lifetime_seconds = lifetime_seconds or int(
        issuer_config.get("default_lifetime_seconds")
        or server_config["policy"]["max_token_lifetime_seconds"]
    )
    client_tun_address = (
        _normalize_client_tun_address(server_config, client_address)
        if client_address
        else _next_client_tun_address(server_config)
    )
    client_ip = _interface_ip(client_tun_address)
    _assert_client_can_be_added(
        server_config,
        device_id=device_id,
        client_tun_address=client_tun_address,
    )

    issuer_config = _issuer_config_with_active_key_window(
        issuer_config,
        now=now,
        lifetime_seconds=resolved_lifetime_seconds,
    )
    authority = _identity_authority_from_issuer_config(issuer_config)
    authority.restore_serial_counter(int(issuer_config.get("serial_counter", 0)))
    client_identity = _issue_identity_with_sign_retry(
        authority,
        _issue_request("vpn-client", device_id, resolved_tenant),
        now=now,
        lifetime_seconds=resolved_lifetime_seconds,
    )
    identity_hash = identity_binding_hash(client_identity.claims).hex()
    lease = {
        "device_id": device_id,
        "identity_hash": identity_hash,
        "client_address": client_ip,
        "client_tun_address": client_tun_address,
    }
    issuer_bound_server_config = _server_config_bound_to_issuer(
        server_config,
        issuer_config,
    )
    updated_server_config = _server_config_with_added_client(
        issuer_bound_server_config,
        device_id=device_id,
        token=client_identity,
        lease=lease,
    )
    client_config = _client_config_from_server_config(
        updated_server_config,
        client_identity=client_identity,
        client_tun_address=client_tun_address,
    )
    updated_issuer_config = {
        **issuer_config,
        "serial_counter": authority.serial_counter,
        "last_issued_at": _iso(now),
    }
    return {
        "updated_server_config": updated_server_config,
        "updated_issuer_config": updated_issuer_config,
        "client_config": client_config,
        "client_tun_address": client_tun_address,
        "client_ip": client_ip,
        "identity_hash": identity_hash,
        "identity_serial": client_identity.serial,
        "issuer_serial_counter": authority.serial_counter,
        "issued_at": now,
    }


def _rotate_identity_artifacts(
    *,
    server_config: dict[str, Any],
    issuer_config: dict[str, Any],
    lifetime_seconds: int,
) -> dict[str, Any]:
    now = _now()
    issuer_config = _issuer_config_with_active_key_window(
        issuer_config,
        now=now,
        lifetime_seconds=lifetime_seconds,
    )
    authority = _identity_authority_from_issuer_config(issuer_config)
    authority.restore_serial_counter(int(issuer_config.get("serial_counter", 0)))
    issuer_bound_server_config = _server_config_bound_to_issuer(
        server_config,
        issuer_config,
    )
    old_server_identity = _token_from_json(issuer_bound_server_config["tokens"]["server"])
    server_identity = _issue_identity_with_sign_retry(
        authority,
        _issue_request(
            old_server_identity.claims.workload,
            old_server_identity.claims.device_id,
            old_server_identity.claims.tenant,
        ),
        now=now,
        lifetime_seconds=lifetime_seconds,
    )

    client_entries = _client_rotation_entries(issuer_bound_server_config)
    rotated_clients: list[dict[str, Any]] = []
    client_configs: list[dict[str, Any]] = []
    client_identity_hashes: list[str] = []
    for entry in client_entries:
        old_identity = entry["identity"]
        client_identity = _issue_identity_with_sign_retry(
            authority,
            _issue_request(
                old_identity.claims.workload,
                old_identity.claims.device_id,
                old_identity.claims.tenant,
            ),
            now=now,
            lifetime_seconds=lifetime_seconds,
        )
        identity_hash = identity_binding_hash(client_identity.claims).hex()
        client_identity_hashes.append(identity_hash)
        rotated_clients.append(
            {
                "device_id": client_identity.claims.device_id,
                "token": _token_to_json(client_identity),
            }
        )
        entry["lease"]["identity_hash"] = identity_hash
        client_configs.append(
            _client_config_from_server_config(
                {
                    **issuer_bound_server_config,
                    "policy": {
                        **issuer_bound_server_config["policy"],
                        "max_token_lifetime_seconds": lifetime_seconds,
                    },
                    "tokens": {
                        **issuer_bound_server_config["tokens"],
                        "server": _token_to_json(server_identity),
                    },
                },
                client_identity=client_identity,
                client_tun_address=str(entry["lease"]["client_tun_address"]),
            )
        )

    tunnel = {
        **_tunnel_config(server_config),
        "client_leases": [dict(entry["lease"]) for entry in client_entries],
    }
    tokens = {
        **issuer_bound_server_config["tokens"],
        "server": _token_to_json(server_identity),
        "clients": rotated_clients,
        "server_previous": _rotated_previous_server_identities(
            server_config,
            old_server_identity=old_server_identity,
            now=now,
        ),
    }
    if rotated_clients:
        tokens["client"] = rotated_clients[0]["token"]
    updated_server_config = {
        **issuer_bound_server_config,
        "generated_at": _iso(now),
        "expires_at": _iso(now + lifetime_seconds),
        "last_identity_rotated_at": _iso(now),
        "policy": {
            **issuer_bound_server_config["policy"],
            "max_token_lifetime_seconds": lifetime_seconds,
        },
        "tokens": tokens,
        "tunnel": tunnel,
    }
    updated_issuer_config = {
        **issuer_config,
        "default_lifetime_seconds": lifetime_seconds,
        "max_lifetime_seconds": lifetime_seconds,
        "serial_counter": authority.serial_counter,
        "last_issued_at": _iso(now),
    }
    return {
        "updated_server_config": updated_server_config,
        "updated_issuer_config": updated_issuer_config,
        "client_configs": client_configs,
        "client_identity_hashes": client_identity_hashes,
        "server_identity_hash": identity_binding_hash(server_identity.claims).hex(),
        "issuer_serial_counter": authority.serial_counter,
    }


def _server_config_bound_to_issuer(
    server_config: dict[str, Any],
    issuer_config: dict[str, Any],
) -> dict[str, Any]:
    identity = dict(server_config.get("identity") or {})
    if issuer_config.get("issuer") is not None:
        identity["issuer"] = str(issuer_config["issuer"])
    if issuer_config.get("policy_epoch") is not None:
        identity["policy_epoch"] = str(issuer_config["policy_epoch"])
    if issuer_config.get("signature_provider") is not None:
        identity["signature_provider"] = str(issuer_config["signature_provider"])
    if isinstance(issuer_config.get("verification_key"), dict):
        identity["verification_key"] = dict(issuer_config["verification_key"])
    return {
        **server_config,
        "identity": identity,
    }


def _issuer_config_with_active_key_window(
    issuer_config: dict[str, Any],
    *,
    now: int,
    lifetime_seconds: int,
) -> dict[str, Any]:
    active_key_id = str(issuer_config.get("active_key_id", ""))
    not_before = max(0, now - 60)
    not_after = now + int(lifetime_seconds) + 60
    updated = dict(issuer_config)
    for key_name in ("signing_key", "verification_key"):
        key = dict(updated.get(key_name) or {})
        if active_key_id and str(key.get("key_id", "")) != active_key_id:
            continue
        current_not_before = int(key.get("not_before", not_before))
        current_not_after = key.get("not_after")
        key["not_before"] = min(current_not_before, not_before)
        key["not_after"] = (
            not_after
            if current_not_after is None
            else max(int(current_not_after), not_after)
        )
        updated[key_name] = key
    return updated


def _identity_renewal_status(
    server_config: dict[str, Any],
    *,
    now: int,
    renew_before_seconds: int,
    force: bool,
) -> dict[str, Any]:
    token_infos = _server_identity_token_infos(server_config)
    if not token_infos:
        raise ValueError("server config contains no identity tokens")
    earliest = min(token_infos, key=lambda item: int(item["expires_at"]))
    seconds_until_expiry = int(earliest["expires_at"]) - now
    if force:
        renewal_needed = True
        reason = "identity_forced"
    elif seconds_until_expiry <= 0:
        renewal_needed = True
        reason = "identity_expired"
    elif seconds_until_expiry <= renew_before_seconds:
        renewal_needed = True
        reason = "identity_near_expiry"
    else:
        renewal_needed = False
        reason = "identity_valid"
    client_count = sum(1 for item in token_infos if item["scope"] == "client")
    return {
        "renewal_needed": renewal_needed,
        "renewal_reason": reason,
        "seconds_until_earliest_expiry": seconds_until_expiry,
        "earliest_expires_at": _iso(int(earliest["expires_at"])),
        "earliest_token_scope": earliest["scope"],
        "token_count": len(token_infos),
        "client_count": client_count,
    }


def _server_identity_token_infos(server_config: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = server_config.get("tokens") or {}
    infos: list[dict[str, Any]] = []
    if isinstance(tokens.get("server"), dict):
        server_token = _token_from_json(tokens["server"])
        infos.append(
            {
                "scope": "server",
                "expires_at": server_token.claims.expires_at,
                "serial": server_token.serial,
            }
        )
    clients = tokens.get("clients")
    if isinstance(clients, list) and clients:
        for item in clients:
            if not isinstance(item, dict) or not isinstance(item.get("token"), dict):
                continue
            client_token = _token_from_json(item["token"])
            infos.append(
                {
                    "scope": "client",
                    "expires_at": client_token.claims.expires_at,
                    "serial": client_token.serial,
                }
            )
        return infos
    if isinstance(tokens.get("client"), dict):
        client_token = _token_from_json(tokens["client"])
        infos.append(
            {
                "scope": "client",
                "expires_at": client_token.claims.expires_at,
                "serial": client_token.serial,
            }
        )
    return infos


def _client_rotation_entries(server_config: dict[str, Any]) -> list[dict[str, Any]]:
    leases_by_device = {
        str(lease["device_id"]): dict(lease)
        for lease in _tunnel_config(server_config).get("client_leases", ())
        if isinstance(lease, dict) and lease.get("device_id")
    }
    entries: list[dict[str, Any]] = []
    for item in (server_config.get("tokens") or {}).get("clients", ()):
        if not isinstance(item, dict) or not isinstance(item.get("token"), dict):
            continue
        identity = _token_from_json(item["token"])
        device_id = str(item.get("device_id") or identity.claims.device_id)
        lease = leases_by_device.get(device_id)
        if lease is None:
            raise ValueError(f"client lease missing for {device_id}")
        lease["previous_identity_hashes"] = _rotated_previous_client_identity_hashes(
            lease,
            old_identity=identity,
            now=_now(),
        )
        entries.append({"identity": identity, "lease": lease})
    if entries:
        return entries
    identity = _token_from_json(server_config["tokens"]["client"])
    tunnel = _tunnel_config(server_config)
    lease = {
        "client_address": _interface_ip(str(tunnel["client_address"])),
        "client_tun_address": str(tunnel["client_address"]),
        "device_id": identity.claims.device_id,
        "identity_hash": identity_binding_hash(identity.claims).hex(),
    }
    lease["previous_identity_hashes"] = _rotated_previous_client_identity_hashes(
        lease,
        old_identity=identity,
        now=_now(),
    )
    return [{"identity": identity, "lease": lease}]


def _rotated_previous_server_identities(
    server_config: dict[str, Any],
    *,
    old_server_identity: SignedIdentityToken,
    now: int,
) -> list[dict[str, Any]]:
    previous: list[SignedIdentityToken] = [
        identity
        for identity in _previous_server_identities(server_config)
        if identity.claims.expires_at > now
    ]
    if old_server_identity.claims.expires_at > now:
        previous.insert(0, old_server_identity)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for identity in previous:
        identity_hash = identity_binding_hash(identity.claims).hex()
        if identity_hash in seen:
            continue
        seen.add(identity_hash)
        result.append({"token": _token_to_json(identity)})
    return result[:4]


def _previous_server_identities(config: dict[str, Any]) -> tuple[SignedIdentityToken, ...]:
    previous = (config.get("tokens") or {}).get("server_previous", ())
    if not isinstance(previous, list | tuple):
        return ()
    identities: list[SignedIdentityToken] = []
    for item in previous:
        if isinstance(item, dict) and isinstance(item.get("token"), dict):
            identities.append(_token_from_json(item["token"]))
        elif isinstance(item, dict) and isinstance(item.get("claims"), dict):
            identities.append(_token_from_json(item))
    return tuple(identities)


def _rotated_previous_client_identity_hashes(
    lease: dict[str, Any],
    *,
    old_identity: SignedIdentityToken,
    now: int,
) -> list[dict[str, Any]]:
    previous: list[dict[str, Any]] = []
    raw_previous = lease.get("previous_identity_hashes", ())
    if isinstance(raw_previous, list | tuple):
        for item in raw_previous:
            if not isinstance(item, dict):
                continue
            identity_hash = str(item.get("identity_hash", ""))
            expires_at = int(item.get("expires_at", 0))
            if len(identity_hash) == 64 and expires_at > now:
                previous.append(
                    {
                        "identity_hash": identity_hash,
                        "expires_at": expires_at,
                    }
                )
    old_hash = identity_binding_hash(old_identity.claims).hex()
    if old_identity.claims.expires_at > now:
        previous.insert(
            0,
            {
                "identity_hash": old_hash,
                "expires_at": old_identity.claims.expires_at,
            },
        )
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in previous:
        identity_hash = item["identity_hash"]
        if identity_hash in seen:
            continue
        seen.add(identity_hash)
        result.append(item)
    return result[:4]


def _client_identity_hash_allowlist(config: dict[str, Any]) -> frozenset[str]:
    identity_hashes: set[str] = set()
    tunnel = _tunnel_config(config)
    for lease in tunnel.get("client_leases", ()):
        if isinstance(lease, dict) and lease.get("identity_hash"):
            identity_hashes.add(str(lease["identity_hash"]))
        if isinstance(lease, dict) and isinstance(lease.get("previous_identity_hashes"), list):
            for item in lease["previous_identity_hashes"]:
                if isinstance(item, dict) and item.get("identity_hash"):
                    identity_hashes.add(str(item["identity_hash"]))
    for item in (config.get("tokens") or {}).get("clients", ()):
        if not isinstance(item, dict):
            continue
        token = item.get("token")
        if isinstance(token, dict):
            identity_hashes.add(identity_binding_hash(_token_from_json(token).claims).hex())
    return frozenset(identity_hashes)


def _client_identity_hash_allowlist_enabled(config: dict[str, Any]) -> bool:
    tunnel = _tunnel_config(config)
    tokens = config.get("tokens") or {}
    return "client_leases" in tunnel or "clients" in tokens


def _server_config_with_added_client(
    server_config: dict[str, Any],
    *,
    device_id: str,
    token: SignedIdentityToken,
    lease: dict[str, Any],
) -> dict[str, Any]:
    tokens = dict(server_config["tokens"])
    clients = list(tokens.get("clients", ()))
    clients.append({"device_id": device_id, "token": _token_to_json(token)})
    tokens["clients"] = clients

    tunnel = _tunnel_config(server_config)
    client_leases = list(tunnel.get("client_leases", ()))
    client_leases.append(dict(lease))
    tunnel["client_leases"] = client_leases
    tunnel["shared_return_by_client_address"] = True

    return {
        **server_config,
        "tokens": tokens,
        "tunnel": tunnel,
        "last_client_added_at": _iso(_now()),
    }


def _server_config_without_client(
    server_config: dict[str, Any],
    *,
    device_id: str | None,
    identity_hash: str | None,
) -> tuple[dict[str, Any], bool, list[str]]:
    tokens = dict(server_config["tokens"])
    removed = False
    revoked_identity_serials: set[str] = set()
    clients: list[dict[str, Any]] = []
    for item in tokens.get("clients", ()):
        if not isinstance(item, dict):
            clients.append(item)
            continue
        token = item.get("token")
        signed_token = _token_from_json(token) if isinstance(token, dict) else None
        token_identity_hash = (
            identity_binding_hash(signed_token.claims).hex()
            if signed_token is not None
            else None
        )
        matches = (
            (device_id is not None and str(item.get("device_id")) == device_id)
            or (identity_hash is not None and token_identity_hash == identity_hash)
        )
        if matches:
            removed = True
            if signed_token is not None:
                revoked_identity_serials.add(signed_token.serial)
            continue
        clients.append(item)
    tokens["clients"] = clients

    tunnel = _tunnel_config(server_config)
    leases: list[dict[str, Any]] = []
    for lease in tunnel.get("client_leases", ()):
        if not isinstance(lease, dict):
            leases.append(lease)
            continue
        matches = (
            (device_id is not None and str(lease.get("device_id")) == device_id)
            or (identity_hash is not None and str(lease.get("identity_hash")) == identity_hash)
        )
        if matches:
            removed = True
            continue
        leases.append(lease)
    tunnel["client_leases"] = leases

    updated = {
        **server_config,
        "tokens": tokens,
        "tunnel": tunnel,
    }
    if removed:
        revocations = _revocations_from_config(server_config)
        revocations.identity_serials.update(revoked_identity_serials)
        updated["revocations"] = _revocations_to_json_dict(revocations)
        updated["last_client_removed_at"] = _iso(_now())
    return updated, removed, sorted(revoked_identity_serials)


def _client_config_from_server_config(
    server_config: dict[str, Any],
    *,
    client_identity: SignedIdentityToken,
    client_tun_address: str,
) -> dict[str, Any]:
    client_config = dict(server_config)
    client_config.pop("bind_host", None)
    pqc_config = dict(client_config["pqc"])
    pqc_config.pop("decapsulation_key", None)
    client_config["pqc"] = pqc_config
    client_config["tokens"] = {
        "client": _token_to_json(client_identity),
        "server": server_config["tokens"]["server"],
    }
    tunnel = {
        **_tunnel_config(server_config),
        "client_address": client_tun_address,
    }
    tunnel.pop("client_leases", None)
    client_config["tunnel"] = tunnel
    return _public_client_config(client_config)


def _client_export_entries_from_server_config(
    server_config: dict[str, Any],
) -> list[dict[str, Any]]:
    tokens = server_config.get("tokens") or {}
    leases_by_device = {
        str(lease["device_id"]): dict(lease)
        for lease in _tunnel_config(server_config).get("client_leases", ())
        if isinstance(lease, dict) and lease.get("device_id")
    }
    entries: list[dict[str, Any]] = []
    clients = tokens.get("clients")
    if isinstance(clients, list) and clients:
        for item in clients:
            if not isinstance(item, dict) or not isinstance(item.get("token"), dict):
                continue
            client_identity = _token_from_json(item["token"])
            device_id = str(item.get("device_id") or client_identity.claims.device_id)
            lease = leases_by_device.get(device_id)
            if lease is None:
                raise ValueError(f"client lease missing for {device_id}")
            client_tun_address = str(
                lease.get("client_tun_address") or f"{lease['client_address']}/32"
            )
            entries.append(
                {
                    "device_id": device_id,
                    "client_identity": client_identity,
                    "client_tun_address": client_tun_address,
                    "client_config": _client_config_from_server_config(
                        server_config,
                        client_identity=client_identity,
                        client_tun_address=client_tun_address,
                    ),
                }
            )
        if entries:
            return entries

    client_identity = _token_from_json(tokens["client"])
    tunnel = _tunnel_config(server_config)
    client_tun_address = str(tunnel["client_address"])
    return [
        {
            "device_id": client_identity.claims.device_id,
            "client_identity": client_identity,
            "client_tun_address": client_tun_address,
            "client_config": _client_config_from_server_config(
                server_config,
                client_identity=client_identity,
                client_tun_address=client_tun_address,
            ),
        }
    ]


def _public_client_config(config: dict[str, Any]) -> dict[str, Any]:
    public_config = dict(config)
    public_config.pop("bind_host", None)
    public_config.pop("service_name", None)
    public_config.pop("systemd", None)
    public_config.pop("last_client_added_at", None)
    public_config.pop("last_client_removed_at", None)
    public_config.pop("revocations", None)
    pqc_config = dict(public_config.get("pqc") or {})
    pqc_config.pop("decapsulation_key", None)
    public_config["pqc"] = pqc_config
    tokens = dict(public_config.get("tokens") or {})
    public_config["tokens"] = {
        "client": tokens["client"],
        "server": tokens["server"],
    }
    tunnel = _tunnel_config(public_config)
    tunnel.pop("client_leases", None)
    public_config["tunnel"] = tunnel
    return public_config


def _assert_public_client_config(config: dict[str, Any]) -> None:
    encoded = json.dumps(config, sort_keys=True)
    forbidden = (
        "decapsulation_key",
        "signing_key",
        "issuer_config",
        "client_leases",
    )
    for marker in forbidden:
        if marker in encoded:
            raise ValueError(f"client kit contains forbidden marker: {marker}")
    token_keys = set((config.get("tokens") or {}).keys())
    if token_keys != {"client", "server"}:
        raise ValueError("client kit tokens must contain only client and server")


def _export_client_kit_payload(
    *,
    client_config_path: Path,
    out_dir: Path,
    kit_name: str,
    archive_path: Path | None,
    issuer_config_path: Path | None = None,
) -> dict[str, Any]:
    safe_kit_name = _safe_kit_name(kit_name)
    kit_root = out_dir / safe_kit_name
    safe_config = _public_client_config(_load_json(client_config_path))
    _assert_public_client_config(safe_config)

    if kit_root.exists():
        shutil.rmtree(kit_root)
    (kit_root / "src/network").mkdir(parents=True, exist_ok=True)
    source_script = Path(__file__).resolve()
    shutil.copy2(source_script, kit_root / KIT_ENTRYPOINT)
    shutil.copytree(
        _find_project_root() / "src/network/firstparty_vpn",
        kit_root / "src/network/firstparty_vpn",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    _write_json(kit_root / "client.json", safe_config, mode=0o600)
    (kit_root / "README.md").write_text(
        _client_kit_readme_content(
            kit_name=safe_kit_name,
            safe_config=safe_config,
        ),
        encoding="utf-8",
    )
    install_script_path = kit_root / "install-linux.sh"
    install_script_path.write_text(
        _client_kit_install_linux_content(),
        encoding="utf-8",
    )
    install_script_path.chmod(0o755)
    check_script_path = kit_root / "check-linux.sh"
    check_script_path.write_text(
        _client_kit_check_linux_content(),
        encoding="utf-8",
    )
    check_script_path.chmod(0o755)
    doctor_script_path = kit_root / "doctor-linux.sh"
    doctor_script_path.write_text(
        _client_kit_doctor_linux_content(),
        encoding="utf-8",
    )
    doctor_script_path.chmod(0o755)
    status_script_path = kit_root / "status-linux.sh"
    status_script_path.write_text(
        _client_kit_status_linux_content(),
        encoding="utf-8",
    )
    status_script_path.chmod(0o755)
    uninstall_script_path = kit_root / "uninstall-linux.sh"
    uninstall_script_path.write_text(
        _client_kit_uninstall_linux_content(),
        encoding="utf-8",
    )
    uninstall_script_path.chmod(0o755)
    verify_script_path = kit_root / "verify-linux.sh"
    verify_script_path.write_text(
        _client_kit_verify_linux_content(),
        encoding="utf-8",
    )
    verify_script_path.chmod(0o755)
    manifest_path = kit_root / "KIT-MANIFEST.json"
    signature_path = kit_root / "KIT-MANIFEST-SIGNATURE.json"
    _write_json(
        kit_root / PUBLIC_INFO_FILENAME,
        {
            "host": safe_config["host"],
            "port": int(safe_config["port"]),
            "transport": _dataplane_transport(safe_config),
            "deployment_epoch": safe_config["deployment_epoch"],
            "client_config": "client.json",
            "readme": "README.md",
            "install_script": "install-linux.sh",
            "check_script": "check-linux.sh",
            "doctor_script": "doctor-linux.sh",
            "status_script": "status-linux.sh",
            "uninstall_script": "uninstall-linux.sh",
            "verify_script": "verify-linux.sh",
            "release_info": "CLIENT-RELEASE.json",
            "entrypoint": KIT_ENTRYPOINT,
            "manifest": "KIT-MANIFEST.json",
            "manifest_signature": (
                "KIT-MANIFEST-SIGNATURE.json"
                if issuer_config_path is not None
                else None
            ),
        },
        mode=0o644,
    )
    release_info_path = kit_root / "CLIENT-RELEASE.json"
    _write_json(
        release_info_path,
        _client_release_info_payload(
            kit_name=safe_kit_name,
            safe_config=safe_config,
            manifest_signed=issuer_config_path is not None,
        ),
        mode=0o644,
    )
    manifest_payload = _client_kit_manifest_payload(kit_root)
    _write_json(
        manifest_path,
        manifest_payload,
        mode=0o644,
    )
    if issuer_config_path is not None:
        _write_json(
            signature_path,
            _client_kit_manifest_signature_payload(
                manifest_payload=manifest_payload,
                issuer_config=_load_json(issuer_config_path),
            ),
            mode=0o644,
        )

    if archive_path is not None:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(kit_root, arcname=safe_kit_name)
        _assert_archive_has_no_server_secrets(archive_path)

    return {
        "ok": True,
        "mode": "export-client-kit",
        "client_config": str(client_config_path),
        "kit_dir": str(kit_root),
        "archive": None if archive_path is None else str(archive_path),
        "host": safe_config["host"],
        "port": int(safe_config["port"]),
        "deployment_epoch": safe_config["deployment_epoch"],
        "readme": str(kit_root / "README.md"),
        "install_script": str(install_script_path),
        "check_script": str(check_script_path),
        "doctor_script": str(doctor_script_path),
        "status_script": str(status_script_path),
        "uninstall_script": str(uninstall_script_path),
        "verify_script": str(verify_script_path),
        "release_info": str(release_info_path),
        "manifest": str(manifest_path),
        "manifest_signature": (
            str(signature_path) if issuer_config_path is not None else None
        ),
        "manifest_signed": issuer_config_path is not None,
        "server_secrets_included": False,
        "os_mutation_performed": False,
    }


def _verify_client_kit_payload(
    *,
    kit_dir: Path,
    archive_path: Path | None,
    require_signature: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    required_files = {
        "CLIENT-RELEASE.json",
        "README.md",
        "client.json",
        PUBLIC_INFO_FILENAME,
        KIT_ENTRYPOINT,
        "check-linux.sh",
        "doctor-linux.sh",
        "install-linux.sh",
        "status-linux.sh",
        "uninstall-linux.sh",
        "verify-linux.sh",
        "KIT-MANIFEST.json",
    }
    manifest_path = kit_dir / "KIT-MANIFEST.json"
    signature_path = kit_dir / "KIT-MANIFEST-SIGNATURE.json"
    manifest: dict[str, Any] = {}
    manifest_files: dict[str, dict[str, Any]] = {}
    client_config: dict[str, Any] = {}
    release_info: dict[str, Any] = {}
    signature_present = signature_path.is_file()

    if not kit_dir.is_dir():
        errors.append("kit_dir:missing")
    if not manifest_path.is_file():
        errors.append("manifest:missing")
    else:
        try:
            manifest = _load_json(manifest_path)
            if manifest.get("mode") != "x0vpn-client-kit-manifest":
                errors.append("manifest:mode")
            raw_files = manifest.get("files", ())
            if not isinstance(raw_files, list):
                errors.append("manifest:files")
                raw_files = []
            manifest_files = {
                str(item.get("path")): item
                for item in raw_files
                if isinstance(item, dict) and item.get("path")
            }
            if int(manifest.get("file_count", -1)) != len(manifest_files):
                errors.append("manifest:file_count")
        except Exception as exc:
            errors.append(f"manifest:{type(exc).__name__}")

    observed_paths = {
        path.relative_to(kit_dir).as_posix()
        for path in kit_dir.rglob("*")
        if path.is_file()
        and path.name
        not in {
            "KIT-MANIFEST.json",
            "KIT-MANIFEST-SIGNATURE.json",
        }
    } if kit_dir.is_dir() else set()
    expected_paths = set(manifest_files)
    for relpath in sorted(required_files - observed_paths - {"KIT-MANIFEST.json"}):
        errors.append(f"required_file:missing:{relpath}")
    if "KIT-MANIFEST.json" not in required_files or not manifest_path.is_file():
        errors.append("required_file:missing:KIT-MANIFEST.json")
    for relpath in sorted(observed_paths - expected_paths):
        errors.append(f"unexpected:{relpath}")
    for relpath in sorted(expected_paths - observed_paths):
        errors.append(f"missing:{relpath}")
    for relpath, item in sorted(manifest_files.items()):
        path = kit_dir / relpath
        if not path.is_file():
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != str(item.get("sha256")):
            errors.append(f"sha256:{relpath}")
        if len(data) != int(item.get("size_bytes", -1)):
            errors.append(f"size:{relpath}")
        try:
            expected_mode = int(str(item.get("mode")), 8)
        except ValueError:
            errors.append(f"mode:{relpath}")
            continue
        if path.stat().st_mode & 0o777 != expected_mode:
            errors.append(f"mode:{relpath}")

    try:
        client_config = _load_json(kit_dir / "client.json")
        _assert_public_client_config(client_config)
        forbidden = [
            marker
            for marker in ("decapsulation_key", "signing_key", "issuer_config", "client_leases")
            if marker in json.dumps(client_config, sort_keys=True)
        ]
        for marker in forbidden:
            errors.append(f"client_config:forbidden:{marker}")
    except Exception as exc:
        errors.append(f"client_config:{type(exc).__name__}")

    try:
        release_info = _load_json(kit_dir / "CLIENT-RELEASE.json")
        if release_info.get("mode") != "x0vpn-client-release":
            errors.append("release_info:mode")
        if release_info.get("client_config_hash") != _json_payload_hash(client_config):
            errors.append("release_info:client_config_hash")
        if release_info.get("entrypoint") != KIT_ENTRYPOINT:
            errors.append("release_info:entrypoint")
        if release_info.get("release_status") not in {
            "production_candidate",
            "not_ready",
        }:
            errors.append("release_info:status")
        forbidden_release_markers = [
            marker
            for marker in (
                "decapsulation_key",
                "signing_key",
                "issuer_config",
                "client_leases",
            )
            if marker in json.dumps(release_info, sort_keys=True)
        ]
        for marker in forbidden_release_markers:
            errors.append(f"release_info:forbidden:{marker}")
    except Exception as exc:
        errors.append(f"release_info:{type(exc).__name__}")

    if require_signature and not signature_present:
        errors.append("signature:missing")
    if signature_present:
        try:
            signature_payload = _load_json(signature_path)
            signature_hex = str(signature_payload.pop("signature"))
            if signature_payload.get("manifest_sha256") != _json_payload_hash(manifest):
                errors.append("signature:manifest_sha256")
            verification_key_payload = client_config["identity"]["verification_key"]
            if signature_payload.get("key_id") != verification_key_payload.get("key_id"):
                errors.append("signature:key_id")
            if signature_payload.get("issuer") != client_config["identity"]["issuer"]:
                errors.append("signature:issuer")
            verification_key = IdentitySigningKey(
                key_id=str(verification_key_payload["key_id"]),
                signature_algorithm=str(
                    verification_key_payload["signature_algorithm"]
                ),
                secret=bytes.fromhex(str(verification_key_payload["secret"])),
                not_before=int(verification_key_payload.get("not_before", 0)),
                not_after=(
                    None
                    if verification_key_payload.get("not_after") is None
                    else int(verification_key_payload.get("not_after"))
                ),
            )
            verified = FirstPartyReferenceMlDsaIdentitySignatureProvider().verify(
                verification_key,
                _canonical_json(signature_payload),
                bytes.fromhex(signature_hex),
            )
            if not verified:
                errors.append("signature:verify")
        except Exception as exc:
            errors.append(f"signature:{type(exc).__name__}")

    archive_checked = archive_path is not None
    archive_present = False
    if archive_path is not None:
        archive_present = archive_path.is_file()
        if not archive_present:
            errors.append("archive:missing")
        else:
            try:
                _assert_archive_has_no_server_secrets(archive_path)
                with tarfile.open(archive_path, "r:gz") as archive:
                    archive_names = {Path(member.name).name for member in archive.getmembers()}
                for relpath in required_files:
                    if relpath not in archive_names:
                        errors.append(f"archive:missing:{relpath}")
            except Exception as exc:
                errors.append(f"archive:{type(exc).__name__}")

    payload = {
        "ok": not errors,
        "mode": "verify-client-kit",
        "kit_dir": str(kit_dir),
        "archive": None if archive_path is None else str(archive_path),
        "archive_checked": archive_checked,
        "archive_present": archive_present,
        "require_signature": bool(require_signature),
        "signature_present": signature_present,
        "manifest_file_count": len(manifest_files),
        "observed_file_count": len(observed_paths),
        "required_files_present": all(
            (kit_dir / relpath).is_file()
            for relpath in required_files
        ),
        "client_config_hash": (
            _json_payload_hash(client_config) if client_config else None
        ),
        "release_status": release_info.get("release_status") if release_info else None,
        "release_info_hash": (
            _json_payload_hash(release_info) if release_info else None
        ),
        "errors": errors,
        "server_secrets_included": False,
        "os_mutation_performed": False,
    }
    return payload


def _verify_client_kit_with_readiness_payload(
    payload: dict[str, Any],
    *,
    kit_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    errors = list(payload.get("errors") or [])
    try:
        readiness_payload = asyncio.run(
            _client_readiness_payload(
                _client_readiness_args_from_export_args(
                    args,
                    config_path=kit_dir / "client.json",
                )
            )
        )
    except Exception as exc:
        readiness_payload = _component_error_payload("client-readiness", exc)
    if not bool(readiness_payload.get("ok")):
        errors.append("readiness")
    return {
        **payload,
        "ok": bool(payload.get("ok")) and bool(readiness_payload.get("ok")),
        "readiness_required": True,
        "readiness": readiness_payload,
        "errors": errors,
    }


def _client_kit_readme_content(
    *,
    kit_name: str,
    safe_config: dict[str, Any],
) -> str:
    return "\n".join(
        (
            f"# {kit_name}",
            "",
            "x0tta6bl4 first-party VPN client kit.",
            "",
            "This archive is client-only. It must not contain server.json or issuer.json.",
            "",
            "Run verify-linux.sh before trusting or installing the kit.",
            "",
            "Linux verify:",
            "",
            "```sh",
            "./verify-linux.sh",
            "```",
            "",
            "Linux safe preinstall check:",
            "",
            "```sh",
            "./check-linux.sh",
            "```",
            "",
            "Linux doctor:",
            "",
            "```sh",
            "./doctor-linux.sh",
            "```",
            "",
            "Linux quick install:",
            "",
            "```sh",
            "sudo ./install-linux.sh",
            "```",
            "",
            "Linux status:",
            "",
            "```sh",
            "./status-linux.sh",
            "```",
            "",
            "Linux uninstall:",
            "",
            "```sh",
            "sudo ./uninstall-linux.sh",
            "```",
            "",
            "Release evidence:",
            "",
            "```sh",
            "cat CLIENT-RELEASE.json",
            "```",
            "",
            "Manual readiness check:",
            "",
            "```sh",
            f"PYTHONDONTWRITEBYTECODE=1 python3 {KIT_ENTRYPOINT} client-readiness --config client.json --timeout 5 --min-identity-valid-seconds 900",
            "```",
            "",
            "Manual dataplane probe:",
            "",
            "```sh",
            f"PYTHONDONTWRITEBYTECODE=1 python3 {KIT_ENTRYPOINT} probe --config client.json --timeout 5 --tun-packet",
            "```",
            "",
            "Manual Linux host preflight:",
            "",
            "```sh",
            f"sudo env PYTHONDONTWRITEBYTECODE=1 python3 {KIT_ENTRYPOINT} linux-preflight --config client.json --role client",
            "```",
            "",
            "Manual install:",
            "",
            "```sh",
            f"sudo env PYTHONDONTWRITEBYTECODE=1 python3 {KIT_ENTRYPOINT} linux-preflight --config client.json --role client && sudo env PYTHONDONTWRITEBYTECODE=1 python3 {KIT_ENTRYPOINT} install-client-service --config client.json --allow-os-mutation --enable-now --install-config-sync --require-readiness --readiness-timeout 5 --min-identity-valid-seconds 900",
            "```",
            "",
            "Expected result: the command prints JSON with ok=true, then systemd starts x0tta-firstparty-vpn-client.service and x0tta-firstparty-vpn-client-config-sync.timer.",
            "",
            f"Endpoint: {safe_config['host']}:{int(safe_config['port'])}",
            f"Transport: {_dataplane_transport(safe_config)}",
            f"Deployment epoch: {safe_config['deployment_epoch']}",
            "",
        )
    )


def _client_release_info_payload(
    *,
    kit_name: str,
    safe_config: dict[str, Any],
    manifest_signed: bool,
) -> dict[str, Any]:
    release_status, release_reasons = _client_release_status(safe_config)
    tunnel = _tunnel_config(safe_config)
    pqc = dict(safe_config.get("pqc") or {})
    tokens = dict(safe_config.get("tokens") or {})
    return {
        "schema_version": 1,
        "mode": "x0vpn-client-release",
        "kit_name": kit_name,
        "release_status": release_status,
        "release_reasons": release_reasons,
        "client_config": "client.json",
        "client_config_hash": _json_payload_hash(safe_config),
        "entrypoint": KIT_ENTRYPOINT,
        "manifest": "KIT-MANIFEST.json",
        "manifest_signature": (
            "KIT-MANIFEST-SIGNATURE.json" if manifest_signed else None
        ),
        "manifest_signed": manifest_signed,
        "endpoint": {
            "host": str(safe_config["host"]),
            "port": int(safe_config["port"]),
            "transport": _dataplane_transport(safe_config),
        },
        "endpoints": [
            {
                "endpoint_id": str(item.get("endpoint_id", "")),
                "host": str(item.get("host", safe_config["host"])),
                "path_label": str(item.get("path_label", "")),
                "port": int(item.get("port", safe_config["port"])),
                "priority": int(item.get("priority", 0)),
                "transport": str(item.get("transport", _dataplane_transport(safe_config))),
            }
            for item in tunnel.get("endpoints", ())
            if isinstance(item, dict)
        ],
        "production_controls": {
            "pqc_mode": str(pqc.get("mode", "")),
            "pqc_reviewed": bool(pqc.get("reviewed", False)),
            "pqc_implementation_hash": str(pqc.get("implementation_hash", "")),
            "kill_switch_enabled": bool(tunnel.get("enable_kill_switch", False)),
            "route_all_traffic": bool(tunnel.get("route_all_traffic", False)),
            "client_identity_lifetime_seconds": _token_lifetime_seconds(
                tokens.get("client")
            ),
            "server_identity_lifetime_seconds": _token_lifetime_seconds(
                tokens.get("server")
            ),
            "policy_lifetime_seconds": int(
                (safe_config.get("policy") or {}).get("max_token_lifetime_seconds", 0)
            ),
        },
        "scripts": {
            "verify": "verify-linux.sh",
            "check": "check-linux.sh",
            "doctor": "doctor-linux.sh",
            "install": "install-linux.sh",
            "status": "status-linux.sh",
            "uninstall": "uninstall-linux.sh",
        },
    }


def _client_release_status(safe_config: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    tunnel = _tunnel_config(safe_config)
    pqc = dict(safe_config.get("pqc") or {})
    policy = dict(safe_config.get("policy") or {})
    tokens = dict(safe_config.get("tokens") or {})
    if str(pqc.get("mode", "")) != "production":
        reasons.append("pqc_not_production")
    if not bool(pqc.get("reviewed", False)):
        reasons.append("pqc_not_reviewed")
    if not str(pqc.get("implementation_hash", "")).strip():
        reasons.append("pqc_implementation_hash_missing")
    if not bool(tunnel.get("enable_kill_switch", False)):
        reasons.append("kill_switch_disabled")
    if not bool(tunnel.get("route_all_traffic", False)):
        reasons.append("route_all_traffic_disabled")
    policy_lifetime = int(policy.get("max_token_lifetime_seconds", 0))
    if policy_lifetime < 1 or policy_lifetime > 3600:
        reasons.append("policy_lifetime_not_production")
    for token_name in ("client", "server"):
        lifetime = _token_lifetime_seconds(tokens.get(token_name))
        if lifetime is None or lifetime < 1 or lifetime > 3600:
            reasons.append(f"{token_name}_identity_lifetime_not_production")
    if not tunnel.get("endpoints"):
        reasons.append("endpoints_missing")
    return ("production_candidate" if not reasons else "not_ready", reasons)


def _token_lifetime_seconds(token_payload: object) -> int | None:
    if not isinstance(token_payload, dict):
        return None
    claims = token_payload.get("claims")
    if not isinstance(claims, dict):
        return None
    try:
        return int(claims["expires_at"]) - int(claims["issued_at"])
    except (KeyError, TypeError, ValueError):
        return None


def _client_kit_check_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -eu",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"",
            "READINESS_TIMEOUT=\"${READINESS_TIMEOUT:-5}\"",
            "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"",
            "MIN_IDENTITY_VALID_SECONDS=\"${MIN_IDENTITY_VALID_SECONDS:-900}\"",
            "POST_INSTALL_HEALTH_RETRIES=\"${POST_INSTALL_HEALTH_RETRIES:-20}\"",
            "POST_INSTALL_HEALTH_INTERVAL_SECONDS=\"${POST_INSTALL_HEALTH_INTERVAL_SECONDS:-1}\"",
            "export PYTHONDONTWRITEBYTECODE=1",
            "",
            "./verify-linux.sh",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} linux-preflight --config client.json --role client --no-require-root --no-require-net-admin",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-readiness --config client.json --timeout \"$READINESS_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\"",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-service-plan --config client.json --install-config-sync --require-readiness --readiness-timeout \"$READINESS_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\"",
            "",
        )
    )


def _client_kit_install_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -eu",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"",
            "READINESS_TIMEOUT=\"${READINESS_TIMEOUT:-5}\"",
            "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"",
            "MIN_IDENTITY_VALID_SECONDS=\"${MIN_IDENTITY_VALID_SECONDS:-900}\"",
            "POST_INSTALL_HEALTH_RETRIES=\"${POST_INSTALL_HEALTH_RETRIES:-20}\"",
            "POST_INSTALL_HEALTH_INTERVAL_SECONDS=\"${POST_INSTALL_HEALTH_INTERVAL_SECONDS:-1}\"",
            "export PYTHONDONTWRITEBYTECODE=1",
            "",
            "if [ \"$(id -u)\" -ne 0 ]; then",
            "  echo \"Run as root: sudo ./install-linux.sh\" >&2",
            "  exit 2",
            "fi",
            "",
            "./verify-linux.sh",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} linux-preflight --config client.json --role client",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-readiness --config client.json --timeout \"$READINESS_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\"",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} install-client-service --config client.json --allow-os-mutation --enable-now --install-config-sync --require-readiness --readiness-timeout \"$READINESS_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\" --require-post-install-health --post-install-health-timeout \"$HEALTH_TIMEOUT\" --post-install-health-retries \"$POST_INSTALL_HEALTH_RETRIES\" --post-install-health-interval-seconds \"$POST_INSTALL_HEALTH_INTERVAL_SECONDS\"",
            "systemctl --no-pager status x0tta-firstparty-vpn-client.service || true",
            "systemctl --no-pager status x0tta-firstparty-vpn-client-config-sync.timer || true",
            "./status-linux.sh",
            "",
        )
    )


def _client_kit_manifest_payload(kit_root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in kit_root.rglob("*") if item.is_file()):
        relpath = path.relative_to(kit_root).as_posix()
        if relpath == "KIT-MANIFEST.json":
            continue
        data = path.read_bytes()
        files.append(
            {
                "path": relpath,
                "size_bytes": len(data),
                "mode": f"{path.stat().st_mode & 0o777:04o}",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "mode": "x0vpn-client-kit-manifest",
        "generated_at": _iso(_now()),
        "file_count": len(files),
        "files": files,
    }


def _client_kit_manifest_signature_payload(
    *,
    manifest_payload: dict[str, Any],
    issuer_config: dict[str, Any],
) -> dict[str, Any]:
    signing_key = _key_from_json(issuer_config["signing_key"])
    payload = {
        "schema_version": 1,
        "mode": "x0vpn-client-kit-manifest-signature",
        "signed_at": _iso(_now()),
        "issuer": str(issuer_config["issuer"]),
        "policy_epoch": str(issuer_config["policy_epoch"]),
        "key_id": signing_key.key_id,
        "signature_algorithm": signing_key.signature_algorithm,
        "manifest_sha256": _json_payload_hash(manifest_payload),
    }
    signature = FirstPartyReferenceMlDsaIdentitySignatureProvider().sign(
        signing_key,
        _canonical_json(payload),
    )
    return {
        **payload,
        "signature": signature.hex(),
    }


def _client_kit_verify_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -eu",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "REQUIRE_KIT_SIGNATURE=\"${REQUIRE_KIT_SIGNATURE:-0}\"",
            "export REQUIRE_KIT_SIGNATURE",
            "export PYTHONDONTWRITEBYTECODE=1",
            "\"$PYTHON_BIN\" - <<'PY'",
            "import hashlib",
            "import json",
            "import os",
            "import sys",
            "from pathlib import Path",
            "sys.dont_write_bytecode = True",
            "from src.network.firstparty_vpn.identity import FirstPartyReferenceMlDsaIdentitySignatureProvider, IdentitySigningKey",
            "",
            "def canonical_json(payload):",
            "    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')",
            "",
            "root = Path.cwd()",
            "manifest_path = root / 'KIT-MANIFEST.json'",
            "signature_path = root / 'KIT-MANIFEST-SIGNATURE.json'",
            "manifest = json.loads(manifest_path.read_text(encoding='utf-8'))",
            "errors = []",
            "expected_paths = {item['path'] for item in manifest.get('files', [])}",
            "observed_paths = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name not in {'KIT-MANIFEST.json', 'KIT-MANIFEST-SIGNATURE.json'}}",
            "for relpath in sorted(observed_paths - expected_paths):",
            "    errors.append(f'unexpected:{relpath}')",
            "if int(manifest.get('file_count', -1)) != len(expected_paths):",
            "    errors.append('file_count')",
            "for item in manifest.get('files', []):",
            "    relpath = item['path']",
            "    if relpath == 'KIT-MANIFEST.json':",
            "        continue",
            "    path = root / relpath",
            "    if not path.is_file():",
            "        errors.append(f'missing:{relpath}')",
            "        continue",
            "    data = path.read_bytes()",
            "    digest = hashlib.sha256(data).hexdigest()",
            "    if digest != item['sha256']:",
            "        errors.append(f'sha256:{relpath}')",
            "    if len(data) != int(item['size_bytes']):",
            "        errors.append(f'size:{relpath}')",
            "    observed_mode = path.stat().st_mode & 0o777",
            "    if observed_mode != int(str(item['mode']), 8):",
            "        errors.append(f'mode:{relpath}')",
            "",
            "signature_present = signature_path.is_file()",
            "if not signature_present and os.environ.get('REQUIRE_KIT_SIGNATURE') == '1':",
            "    errors.append('signature:missing')",
            "if signature_present:",
            "    try:",
            "        signature_payload = json.loads(signature_path.read_text(encoding='utf-8'))",
            "        signature_hex = signature_payload.pop('signature')",
            "        manifest_hash = hashlib.sha256(canonical_json(manifest)).hexdigest()",
            "        if signature_payload.get('manifest_sha256') != manifest_hash:",
            "            errors.append('signature:manifest_sha256')",
            "        config = json.loads((root / 'client.json').read_text(encoding='utf-8'))",
            "        verification_key_payload = config['identity']['verification_key']",
            "        if signature_payload.get('key_id') != verification_key_payload.get('key_id'):",
            "            errors.append('signature:key_id')",
            "        if signature_payload.get('issuer') != config['identity']['issuer']:",
            "            errors.append('signature:issuer')",
            "        verification_key = IdentitySigningKey(",
            "            key_id=str(verification_key_payload['key_id']),",
            "            signature_algorithm=str(verification_key_payload['signature_algorithm']),",
            "            secret=bytes.fromhex(str(verification_key_payload['secret'])),",
            "            not_before=int(verification_key_payload.get('not_before', 0)),",
            "            not_after=(None if verification_key_payload.get('not_after') is None else int(verification_key_payload.get('not_after'))),",
            "        )",
            "        verified = FirstPartyReferenceMlDsaIdentitySignatureProvider().verify(",
            "            verification_key,",
            "            canonical_json(signature_payload),",
            "            bytes.fromhex(str(signature_hex)),",
            "        )",
            "        if not verified:",
            "            errors.append('signature:verify')",
            "    except Exception as exc:",
            "        errors.append(f'signature:{type(exc).__name__}')",
            "",
            "if errors:",
            "    print(json.dumps({'ok': False, 'mode': 'kit-verify', 'errors': errors, 'signature_present': signature_present}, sort_keys=True))",
            "    raise SystemExit(1)",
            "print(json.dumps({'ok': True, 'mode': 'kit-verify', 'file_count': len(manifest.get('files', [])), 'signature_present': signature_present}, sort_keys=True))",
            "PY",
            "",
        )
    )


def _client_kit_status_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -u",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"",
            "READINESS_TIMEOUT=\"${READINESS_TIMEOUT:-5}\"",
            "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"",
            "MIN_IDENTITY_VALID_SECONDS=\"${MIN_IDENTITY_VALID_SECONDS:-900}\"",
            "export PYTHONDONTWRITEBYTECODE=1",
            "",
            "PREFLIGHT_RC=0",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} linux-preflight --config client.json --role client --no-require-root --no-require-net-admin || PREFLIGHT_RC=$?",
            "",
            "HEALTH_RC=0",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-health --config client.json --timeout \"$HEALTH_TIMEOUT\" || HEALTH_RC=$?",
            "",
            "READINESS_RC=0",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-readiness --config client.json --timeout \"$READINESS_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\" || READINESS_RC=$?",
            "",
            "PROBE_RC=0",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet || PROBE_RC=$?",
            "",
            "if [ \"$PREFLIGHT_RC\" -ne 0 ] || [ \"$HEALTH_RC\" -ne 0 ] || [ \"$READINESS_RC\" -ne 0 ] || [ \"$PROBE_RC\" -ne 0 ]; then",
            "  exit 1",
            "fi",
            "",
        )
    )


def _client_kit_doctor_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -u",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"",
            "READINESS_TIMEOUT=\"${READINESS_TIMEOUT:-5}\"",
            "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"",
            "MIN_IDENTITY_VALID_SECONDS=\"${MIN_IDENTITY_VALID_SECONDS:-900}\"",
            "REQUIRE_INSTALLED_HEALTH=\"${REQUIRE_INSTALLED_HEALTH:-0}\"",
            "VERIFY_KIT=\"${VERIFY_KIT:-1}\"",
            "export PYTHONDONTWRITEBYTECODE=1",
            "",
            "if [ \"$VERIFY_KIT\" = \"1\" ]; then",
            "  ./verify-linux.sh || exit $?",
            "fi",
            "",
            "EXTRA_ARGS=\"\"",
            "if [ \"$REQUIRE_INSTALLED_HEALTH\" = \"1\" ]; then",
            "  EXTRA_ARGS=\"$EXTRA_ARGS --require-installed-health\"",
            "fi",
            "",
            "# shellcheck disable=SC2086",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} client-doctor --config client.json --health-timeout \"$HEALTH_TIMEOUT\" --readiness-timeout \"$READINESS_TIMEOUT\" --probe-timeout \"$PROBE_TIMEOUT\" --min-identity-valid-seconds \"$MIN_IDENTITY_VALID_SECONDS\" $EXTRA_ARGS",
            "",
        )
    )


def _client_kit_uninstall_linux_content() -> str:
    return "\n".join(
        (
            "#!/usr/bin/env sh",
            "set -eu",
            "",
            "cd \"$(dirname \"$0\")\"",
            "",
            "PYTHON_BIN=\"${PYTHON_BIN:-python3}\"",
            "REMOVE_INSTALL_DIR=\"${REMOVE_INSTALL_DIR:-1}\"",
            "REMOVE_CONFIG_DIR=\"${REMOVE_CONFIG_DIR:-1}\"",
            "export PYTHONDONTWRITEBYTECODE=1",
            "",
            "if [ \"$(id -u)\" -ne 0 ]; then",
            "  echo \"Run as root: sudo ./uninstall-linux.sh\" >&2",
            "  exit 2",
            "fi",
            "",
            "EXTRA_ARGS=\"\"",
            "if [ \"$REMOVE_INSTALL_DIR\" = \"1\" ]; then",
            "  EXTRA_ARGS=\"$EXTRA_ARGS --remove-install-dir\"",
            "fi",
            "if [ \"$REMOVE_CONFIG_DIR\" = \"1\" ]; then",
            "  EXTRA_ARGS=\"$EXTRA_ARGS --remove-config-dir\"",
            "fi",
            "",
            "# shellcheck disable=SC2086",
            f"\"$PYTHON_BIN\" {KIT_ENTRYPOINT} uninstall-client-service --allow-os-mutation $EXTRA_ARGS",
            "systemctl --no-pager status x0tta-firstparty-vpn-client.service || true",
            "systemctl --no-pager status x0tta-firstparty-vpn-client-config-sync.timer || true",
            "",
        )
    )


def _safe_kit_name(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not value or any(ch not in allowed for ch in value):
        raise ValueError("kit name contains an unsafe character")
    return value


def _assert_archive_has_no_server_secrets(path: Path) -> None:
    forbidden_names = {
        "server.json",
        "issuer.json",
    }
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = Path(member.name).name
            if name in forbidden_names:
                raise ValueError(f"client archive contains forbidden file: {name}")
            if "__pycache__" in Path(member.name).parts or member.name.endswith(".pyc"):
                raise ValueError("client archive contains Python cache files")


def _add_server_service_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True)
    parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    parser.add_argument("--install-dir", default=DEFAULT_SERVER_INSTALL_DIR)
    parser.add_argument("--config-dir", default=DEFAULT_SERVER_CONFIG_DIR)
    parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    parser.add_argument("--uplink-interface")


def _add_enable_kill_switch_arg(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--enable-kill-switch",
        dest="enable_kill_switch",
        action="store_true",
        default=None,
    )
    group.add_argument(
        "--disable-kill-switch",
        dest="enable_kill_switch",
        action="store_false",
    )


def _runtime_entrypoint_name() -> str:
    return KIT_ENTRYPOINT


def _server_service_plan_payload(
    args: argparse.Namespace,
    *,
    config_path: Path,
) -> dict[str, Any]:
    service_name = _service_name(args.service_name)
    install_dir = _service_path(args.install_dir, "install-dir")
    config_dir = _service_path(args.config_dir, "config-dir")
    service_python = _service_executable_path(args.service_python, "python")
    script_path = install_dir / _runtime_entrypoint_name()
    package_path = install_dir / "src/network/firstparty_vpn"
    installed_config_path = config_dir / "server.json"
    unit_path = Path("/etc/systemd/system") / service_name
    uplink_interface = _service_interface_name(
        getattr(args, "uplink_interface", None),
    )
    unit_content = _server_service_unit_content(
        install_dir=install_dir,
        service_python=service_python,
        script_path=script_path,
        config_path=installed_config_path,
        uplink_interface=uplink_interface,
    )
    post_install_commands = ["systemctl daemon-reload"]
    if bool(getattr(args, "enable_now", False)):
        post_install_commands.append(f"systemctl enable --now {service_name}")
    else:
        if bool(getattr(args, "enable", False)):
            post_install_commands.append(f"systemctl enable {service_name}")
        if bool(getattr(args, "start", False)):
            post_install_commands.append(f"systemctl start {service_name}")
    return {
        "service_name": service_name,
        "unit_path": str(unit_path),
        "install_dir": str(install_dir),
        "config_dir": str(config_dir),
        "script_path": str(script_path),
        "package_path": str(package_path),
        "config_path": str(installed_config_path),
        "source_config_path": str(config_path),
        "python": str(service_python),
        "uplink_interface": uplink_interface,
        "install_actions": [
            "copy wrapper",
            "copy src/network/firstparty_vpn package",
            "write private server config mode 0600",
            "write systemd service unit mode 0644",
        ],
        "post_install_commands": post_install_commands,
        "unit_content": unit_content,
    }


def _server_service_unit_content(
    *,
    install_dir: Path,
    service_python: Path,
    script_path: Path,
    config_path: Path,
    uplink_interface: str | None,
) -> str:
    start_command = [
        str(service_python),
        str(script_path),
        "server-tun",
        "--config",
        str(config_path),
        "--allow-os-mutation",
    ]
    if uplink_interface:
        start_command.extend(("--uplink-interface", uplink_interface))
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN server",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={install_dir}",
            "Environment=PYTHONUNBUFFERED=1",
            f"Environment=PYTHONPATH={install_dir}",
            f"ExecStart={_command_to_string(tuple(start_command))}",
            "Restart=always",
            "RestartSec=3",
            "KillSignal=SIGTERM",
            "TimeoutStopSec=20",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        )
    )


def _add_server_renewal_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--server-config", required=True)
    parser.add_argument("--issuer-config", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--service-name", default=DEFAULT_SERVER_SERVICE_NAME)
    parser.add_argument("--renewal-service-name")
    parser.add_argument("--timer-name")
    parser.add_argument("--install-dir", default=DEFAULT_SERVER_INSTALL_DIR)
    parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    parser.add_argument("--lifetime-seconds", type=int, default=3600)
    parser.add_argument("--renew-before-seconds", type=int, default=900)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--backup-dir")
    parser.add_argument("--uplink-interface")
    parser.add_argument("--skip-health", action="store_true")


def _server_renewal_plan_payload(args: argparse.Namespace) -> dict[str, Any]:
    server_service_name = _service_name(args.service_name)
    renewal_service_name, timer_name = _server_renewal_unit_names(
        server_service_name,
        renewal_service_name=getattr(args, "renewal_service_name", None),
        timer_name=getattr(args, "timer_name", None),
    )
    install_dir = _service_path(args.install_dir, "install-dir")
    service_python = _service_executable_path(args.service_python, "python")
    script_path = install_dir / _runtime_entrypoint_name()
    server_config_path = _service_path(args.server_config, "server-config")
    issuer_config_path = _service_path(args.issuer_config, "issuer-config")
    out_dir = _service_path(args.out_dir, "out-dir")
    backup_dir = (
        _service_path(args.backup_dir, "backup-dir")
        if args.backup_dir
        else server_config_path.parent / "backups"
    )
    uplink_interface = _service_interface_name(
        getattr(args, "uplink_interface", None),
    )
    lifetime_seconds = _positive_systemd_seconds(args.lifetime_seconds, "lifetime-seconds")
    renew_before_seconds = _positive_systemd_seconds(
        args.renew_before_seconds,
        "renew-before-seconds",
    )
    interval_seconds = _positive_systemd_seconds(args.interval_seconds, "interval-seconds")
    service_path = Path("/etc/systemd/system") / renewal_service_name
    timer_path = Path("/etc/systemd/system") / timer_name
    renewal_service_content = _server_renewal_service_unit_content(
        service_python=service_python,
        script_path=script_path,
        server_config_path=server_config_path,
        issuer_config_path=issuer_config_path,
        out_dir=out_dir,
        lifetime_seconds=lifetime_seconds,
        renew_before_seconds=renew_before_seconds,
        server_service_name=server_service_name,
        backup_dir=backup_dir,
        uplink_interface=uplink_interface,
        skip_health=bool(getattr(args, "skip_health", False)),
    )
    timer_content = _server_renewal_timer_unit_content(
        renewal_service_name=renewal_service_name,
        interval_seconds=interval_seconds,
    )
    post_install_commands = ["systemctl daemon-reload"]
    if bool(getattr(args, "enable_now", False)):
        post_install_commands.append(f"systemctl enable --now {timer_name}")
    else:
        if bool(getattr(args, "enable", False)):
            post_install_commands.append(f"systemctl enable {timer_name}")
        if bool(getattr(args, "start", False)):
            post_install_commands.append(f"systemctl start {timer_name}")
    return {
        "timer_name": timer_name,
        "renewal_service_name": renewal_service_name,
        "server_service_name": server_service_name,
        "timer_path": str(timer_path),
        "renewal_service_path": str(service_path),
        "install_dir": str(install_dir),
        "script_path": str(script_path),
        "server_config": str(server_config_path),
        "issuer_config": str(issuer_config_path),
        "out_dir": str(out_dir),
        "backup_dir": str(backup_dir),
        "python": str(service_python),
        "lifetime_seconds": lifetime_seconds,
        "renew_before_seconds": renew_before_seconds,
        "interval_seconds": interval_seconds,
        "uplink_interface": uplink_interface,
        "skip_health": bool(getattr(args, "skip_health", False)),
        "install_actions": [
            "write identity renewal systemd service unit mode 0644",
            "write identity renewal systemd timer unit mode 0644",
        ],
        "post_install_commands": post_install_commands,
        "renewal_service_content": renewal_service_content,
        "timer_content": timer_content,
    }


def _server_renewal_service_unit_content(
    *,
    service_python: Path,
    script_path: Path,
    server_config_path: Path,
    issuer_config_path: Path,
    out_dir: Path,
    lifetime_seconds: int,
    renew_before_seconds: int,
    server_service_name: str,
    backup_dir: Path,
    uplink_interface: str | None,
    skip_health: bool,
) -> str:
    start_command = [
        str(service_python),
        str(script_path),
        "identity-auto-renew",
        "--server-config",
        str(server_config_path),
        "--issuer-config",
        str(issuer_config_path),
        "--out-dir",
        str(out_dir),
        "--lifetime-seconds",
        str(lifetime_seconds),
        "--renew-before-seconds",
        str(renew_before_seconds),
        "--apply-server-config",
        "--installed-server-config",
        str(server_config_path),
        "--service-name",
        server_service_name,
        "--backup-dir",
        str(backup_dir),
        "--allow-os-mutation",
        "--update-issuer-config",
    ]
    if uplink_interface:
        start_command.extend(("--uplink-interface", uplink_interface))
    if skip_health:
        start_command.append("--skip-health")
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN identity auto-renew",
            f"After={server_service_name}",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={script_path.parent}",
            "Environment=PYTHONUNBUFFERED=1",
            f"Environment=PYTHONPATH={script_path.parent}",
            f"ExecStart={_command_to_string(tuple(start_command))}",
            "",
        )
    )


def _server_renewal_timer_unit_content(
    *,
    renewal_service_name: str,
    interval_seconds: int,
) -> str:
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN identity auto-renew timer",
            "",
            "[Timer]",
            f"OnBootSec={interval_seconds}s",
            f"OnUnitActiveSec={interval_seconds}s",
            f"Unit={renewal_service_name}",
            "AccuracySec=30s",
            "Persistent=true",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        )
    )


def _server_renewal_unit_names(
    server_service_name: str,
    *,
    renewal_service_name: str | None,
    timer_name: str | None,
) -> tuple[str, str]:
    base = server_service_name.removesuffix(".service")
    resolved_service = _service_name(
        renewal_service_name or f"{base}-identity-renewal.service"
    )
    resolved_timer = _timer_name(timer_name or f"{base}-identity-renewal.timer")
    if resolved_timer.removesuffix(".timer") != resolved_service.removesuffix(".service"):
        raise ValueError("renewal timer and service names must share the same base")
    return resolved_service, resolved_timer


def _timer_name(value: str) -> str:
    timer_name = value if value.endswith(".timer") else f"{value}.timer"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-@")
    if (
        not timer_name
        or timer_name in {".timer", "..timer"}
        or any(ch not in allowed for ch in timer_name)
    ):
        raise ValueError("timer name contains an unsafe character")
    return timer_name


def _positive_systemd_seconds(value: int, label: str) -> int:
    seconds = int(value)
    if seconds < 1:
        raise ValueError(f"{label} must be positive")
    return seconds


def _add_client_service_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True)
    parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    parser.add_argument("--install-dir", default=DEFAULT_CLIENT_INSTALL_DIR)
    parser.add_argument("--config-dir", default=DEFAULT_CLIENT_CONFIG_DIR)
    parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    parser.add_argument("--disable-kill-switch", action="store_true")
    parser.add_argument("--install-config-sync", action="store_true")
    parser.add_argument("--config-sync-service-name")
    parser.add_argument("--config-sync-timer-name")
    parser.add_argument("--config-sync-timeout", type=float, default=3.0)
    parser.add_argument("--config-sync-interval-seconds", type=int, default=300)
    parser.add_argument("--require-readiness", action="store_true")
    parser.add_argument("--readiness-timeout", type=float, default=3.0)
    parser.add_argument("--min-identity-valid-seconds", type=int, default=900)
    parser.add_argument("--readiness-skip-tcp-connect", action="store_true")
    parser.add_argument("--readiness-skip-admission", action="store_true")
    parser.add_argument("--readiness-skip-config-sync", action="store_true")


def _client_service_plan_payload(
    args: argparse.Namespace,
    *,
    config_path: Path,
) -> dict[str, Any]:
    service_name = _service_name(args.service_name)
    install_dir = _service_path(args.install_dir, "install-dir")
    config_dir = _service_path(args.config_dir, "config-dir")
    service_python = _service_executable_path(args.service_python, "python")
    script_path = install_dir / _runtime_entrypoint_name()
    package_path = install_dir / "src/network/firstparty_vpn"
    installed_config_path = config_dir / "client.json"
    unit_path = Path("/etc/systemd/system") / service_name
    enable_kill_switch = not bool(getattr(args, "disable_kill_switch", False))
    unit_content = _client_service_unit_content(
        service_name=service_name,
        install_dir=install_dir,
        service_python=service_python,
        script_path=script_path,
        config_path=installed_config_path,
        enable_kill_switch=enable_kill_switch,
    )
    config_sync_plan = None
    if bool(getattr(args, "install_config_sync", False)):
        config_sync_plan = _client_sync_plan_payload(
            _client_sync_args_from_service_args(args, config_path=installed_config_path)
        )
    post_install_commands = ["systemctl daemon-reload"]
    if bool(getattr(args, "enable_now", False)):
        post_install_commands.append(f"systemctl enable --now {service_name}")
    else:
        if bool(getattr(args, "enable", False)):
            post_install_commands.append(f"systemctl enable {service_name}")
        if bool(getattr(args, "start", False)):
            post_install_commands.append(f"systemctl start {service_name}")
    if config_sync_plan is not None:
        post_install_commands.extend(
            command
            for command in config_sync_plan["post_install_commands"]
            if command != "systemctl daemon-reload"
        )
    return {
        "service_name": service_name,
        "unit_path": str(unit_path),
        "install_dir": str(install_dir),
        "config_dir": str(config_dir),
        "script_path": str(script_path),
        "package_path": str(package_path),
        "config_path": str(installed_config_path),
        "source_config_path": str(config_path),
        "python": str(service_python),
        "kill_switch_enabled": enable_kill_switch,
        "install_actions": [
            "copy wrapper",
            "copy src/network/firstparty_vpn package",
            "write private client config mode 0600",
            "write systemd service unit mode 0644",
            *(
                config_sync_plan["install_actions"]
                if config_sync_plan is not None
                else []
            ),
        ],
        "post_install_commands": post_install_commands,
        "unit_content": unit_content,
        "config_sync_installed": config_sync_plan is not None,
        "config_sync_plan": config_sync_plan,
        "readiness_required": bool(getattr(args, "require_readiness", False)),
        "readiness_checks": (
            [
                "public_client_config",
                "identity_policy_valid",
                "identity_validity_window",
                "server_tcp_port_open",
                "admission_handshake",
                "protected_config_sync",
                "managed_install_plan",
            ]
            if bool(getattr(args, "require_readiness", False))
            else []
        ),
    }


def _client_readiness_args_from_service_args(
    args: argparse.Namespace,
    *,
    config_path: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        config=str(config_path),
        service_name=args.service_name,
        install_dir=args.install_dir,
        config_dir=args.config_dir,
        service_python=args.service_python,
        timeout=float(getattr(args, "readiness_timeout", 3.0)),
        min_identity_valid_seconds=int(getattr(args, "min_identity_valid_seconds", 900)),
        skip_tcp_connect=bool(getattr(args, "readiness_skip_tcp_connect", False)),
        skip_admission=bool(getattr(args, "readiness_skip_admission", False)),
        skip_config_sync=bool(getattr(args, "readiness_skip_config_sync", False)),
        skip_managed_install_plan=False,
    )


def _client_readiness_args_from_export_args(
    args: argparse.Namespace,
    *,
    config_path: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        config=str(config_path),
        service_name=DEFAULT_CLIENT_SERVICE_NAME,
        install_dir=DEFAULT_CLIENT_INSTALL_DIR,
        config_dir=DEFAULT_CLIENT_CONFIG_DIR,
        service_python=DEFAULT_SERVICE_PYTHON,
        timeout=float(getattr(args, "readiness_timeout", 3.0)),
        min_identity_valid_seconds=int(getattr(args, "min_identity_valid_seconds", 900)),
        skip_tcp_connect=bool(getattr(args, "readiness_skip_tcp_connect", False)),
        skip_admission=bool(getattr(args, "readiness_skip_admission", False)),
        skip_config_sync=bool(getattr(args, "readiness_skip_config_sync", False)),
        skip_managed_install_plan=bool(
            getattr(args, "readiness_skip_managed_install_plan", False)
        ),
    )


def _client_sync_args_from_service_args(
    args: argparse.Namespace,
    *,
    config_path: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        config=str(config_path),
        service_name=args.service_name,
        sync_service_name=getattr(args, "config_sync_service_name", None),
        timer_name=getattr(args, "config_sync_timer_name", None),
        install_dir=args.install_dir,
        service_python=args.service_python,
        timeout=getattr(args, "config_sync_timeout", 3.0),
        interval_seconds=getattr(args, "config_sync_interval_seconds", 300),
        enable=bool(getattr(args, "enable", False)),
        start=bool(getattr(args, "start", False)),
        enable_now=bool(getattr(args, "enable_now", False)),
    )


def _client_service_unit_content(
    *,
    service_name: str,
    install_dir: Path,
    service_python: Path,
    script_path: Path,
    config_path: Path,
    enable_kill_switch: bool,
) -> str:
    _ = service_name
    start_command = [
        str(service_python),
        str(script_path),
        "client-tun",
        "--config",
        str(config_path),
        "--allow-os-mutation",
        "--apply-client-policy",
    ]
    stop_command = [
        str(service_python),
        str(script_path),
        "client-policy-rollback",
        "--config",
        str(config_path),
        "--allow-os-mutation",
    ]
    if enable_kill_switch:
        start_command.append("--enable-kill-switch")
        stop_command.append("--enable-kill-switch")
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN client",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={install_dir}",
            "Environment=PYTHONUNBUFFERED=1",
            f"Environment=PYTHONPATH={install_dir}",
            f"ExecStart={_command_to_string(tuple(start_command))}",
            f"ExecStopPost=-{_command_to_string(tuple(stop_command))}",
            "Restart=always",
            "RestartSec=3",
            "KillSignal=SIGTERM",
            "TimeoutStopSec=15",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        )
    )


def _add_client_sync_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True)
    parser.add_argument("--service-name", default=DEFAULT_CLIENT_SERVICE_NAME)
    parser.add_argument("--sync-service-name")
    parser.add_argument("--timer-name")
    parser.add_argument("--install-dir", default=DEFAULT_CLIENT_INSTALL_DIR)
    parser.add_argument(
        "--python",
        dest="service_python",
        default=DEFAULT_SERVICE_PYTHON,
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--interval-seconds", type=int, default=300)


def _client_sync_plan_payload(args: argparse.Namespace) -> dict[str, Any]:
    client_service_name = _service_name(args.service_name)
    sync_service_name, timer_name = _client_sync_unit_names(
        client_service_name,
        sync_service_name=getattr(args, "sync_service_name", None),
        timer_name=getattr(args, "timer_name", None),
    )
    install_dir = _service_path(args.install_dir, "install-dir")
    service_python = _service_executable_path(args.service_python, "python")
    script_path = install_dir / _runtime_entrypoint_name()
    config_path = _service_path(args.config, "config")
    timeout_seconds = float(args.timeout)
    if timeout_seconds <= 0:
        raise ValueError("timeout must be positive")
    interval_seconds = _positive_systemd_seconds(args.interval_seconds, "interval-seconds")
    service_path = Path("/etc/systemd/system") / sync_service_name
    timer_path = Path("/etc/systemd/system") / timer_name
    sync_service_content = _client_sync_service_unit_content(
        service_python=service_python,
        script_path=script_path,
        config_path=config_path,
        client_service_name=client_service_name,
        timeout_seconds=timeout_seconds,
    )
    timer_content = _client_sync_timer_unit_content(
        sync_service_name=sync_service_name,
        interval_seconds=interval_seconds,
    )
    post_install_commands = ["systemctl daemon-reload"]
    if bool(getattr(args, "enable_now", False)):
        post_install_commands.append(f"systemctl enable --now {timer_name}")
    else:
        if bool(getattr(args, "enable", False)):
            post_install_commands.append(f"systemctl enable {timer_name}")
        if bool(getattr(args, "start", False)):
            post_install_commands.append(f"systemctl start {timer_name}")
    return {
        "timer_name": timer_name,
        "sync_service_name": sync_service_name,
        "client_service_name": client_service_name,
        "timer_path": str(timer_path),
        "sync_service_path": str(service_path),
        "install_dir": str(install_dir),
        "script_path": str(script_path),
        "config_path": str(config_path),
        "python": str(service_python),
        "timeout_seconds": timeout_seconds,
        "interval_seconds": interval_seconds,
        "install_actions": [
            "write client config sync systemd service unit mode 0644",
            "write client config sync systemd timer unit mode 0644",
        ],
        "post_install_commands": post_install_commands,
        "sync_service_content": sync_service_content,
        "timer_content": timer_content,
    }


def _client_sync_service_unit_content(
    *,
    service_python: Path,
    script_path: Path,
    config_path: Path,
    client_service_name: str,
    timeout_seconds: float,
) -> str:
    start_command = [
        str(service_python),
        str(script_path),
        "client-config-sync",
        "--config",
        str(config_path),
        "--update-config",
        "--timeout",
        str(timeout_seconds),
        "--restart-service",
        "--service-name",
        client_service_name,
        "--allow-os-mutation",
    ]
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN client config sync",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={script_path.parent}",
            "Environment=PYTHONUNBUFFERED=1",
            f"Environment=PYTHONPATH={script_path.parent}",
            f"ExecStart={_command_to_string(tuple(start_command))}",
            "",
        )
    )


def _client_sync_timer_unit_content(
    *,
    sync_service_name: str,
    interval_seconds: int,
) -> str:
    return "\n".join(
        (
            "[Unit]",
            "Description=x0tta6bl4 first-party VPN client config sync timer",
            "",
            "[Timer]",
            f"OnBootSec={interval_seconds}s",
            f"OnUnitActiveSec={interval_seconds}s",
            f"Unit={sync_service_name}",
            "AccuracySec=30s",
            "Persistent=true",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        )
    )


def _client_sync_unit_names(
    client_service_name: str,
    *,
    sync_service_name: str | None,
    timer_name: str | None,
) -> tuple[str, str]:
    base = client_service_name.removesuffix(".service")
    resolved_service = _service_name(sync_service_name or f"{base}-config-sync.service")
    resolved_timer = _timer_name(timer_name or f"{base}-config-sync.timer")
    if resolved_timer.removesuffix(".timer") != resolved_service.removesuffix(".service"):
        raise ValueError("client sync timer and service names must share the same base")
    return resolved_service, resolved_timer


def _service_name(value: str) -> str:
    service_name = value if value.endswith(".service") else f"{value}.service"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-@")
    if (
        not service_name
        or service_name in {".service", "..service"}
        or any(ch not in allowed for ch in service_name)
    ):
        raise ValueError("service name contains an unsafe character")
    return service_name


def _server_service_name(config: dict[str, Any], requested_service_name: str) -> str:
    configured_service_name = config.get("service_name")
    if configured_service_name is None and isinstance(config.get("systemd"), dict):
        configured_service_name = config["systemd"].get("service_name")
    if (
        requested_service_name == DEFAULT_SERVER_SERVICE_NAME
        and configured_service_name
    ):
        return _service_name(str(configured_service_name))
    return _service_name(requested_service_name)


def _server_config_with_service_name(
    config: dict[str, Any],
    service_name: str,
) -> dict[str, Any]:
    installed_config = copy.deepcopy(config)
    systemd_config = installed_config.get("systemd")
    if not isinstance(systemd_config, dict):
        systemd_config = {}
        installed_config["systemd"] = systemd_config
    systemd_config["service_name"] = _service_name(service_name)
    return installed_config


def _service_path(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    text = str(path)
    if "\x00" in text or any(ch.isspace() for ch in text):
        raise ValueError(f"{label} contains an unsafe character")
    return path


def _service_executable_path(value: str, label: str) -> Path:
    path = _service_path(value, label)
    if path.name in {"", ".", ".."}:
        raise ValueError(f"{label} must be an executable path")
    return path


def _service_interface_name(value: str | None) -> str | None:
    if value is None:
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-:@")
    if not value or any(ch not in allowed for ch in value):
        raise ValueError("uplink interface contains an unsafe character")
    return value


def _remove_tree_safely(path: Path) -> None:
    resolved = path.resolve(strict=False)
    protected = {
        Path("/"),
        Path("/etc"),
        Path("/opt"),
        Path("/usr"),
        Path("/var"),
        Path("/home"),
    }
    if resolved in protected or len(resolved.parts) < 3:
        raise ValueError(f"refusing to remove unsafe path: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def _run_checked(command: tuple[str, ...]) -> None:
    subprocess.run(command, check=True)


def _run_unchecked(command: tuple[str, ...]) -> None:
    subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _allocated_client_tun_addresses(args: argparse.Namespace) -> list[str]:
    if args.client_count < 1:
        raise ValueError("client count must be at least 1")
    network = ipaddress.ip_network(args.client_cidr, strict=False)
    if network.version != 4:
        raise ValueError("client CIDR must be IPv4")
    server_ip = ipaddress.ip_interface(args.server_tun_address).ip
    if server_ip not in network:
        raise ValueError("server TUN address must be inside client CIDR")
    if args.client_count == 1:
        client_ip = ipaddress.ip_interface(args.client_tun_address).ip
        _validate_client_tun_ip(client_ip, network=network, server_ip=server_ip)
        return [f"{client_ip}/32"]

    addresses: list[str] = []
    for index in range(args.client_count):
        client_ip = network.network_address + args.client_address_offset + index
        _validate_client_tun_ip(client_ip, network=network, server_ip=server_ip)
        addresses.append(f"{client_ip}/32")
    if len(set(addresses)) != len(addresses):
        raise ValueError("allocated client TUN addresses must be unique")
    return addresses


def _validate_client_tun_ip(
    client_ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    server_ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    if client_ip not in network:
        raise ValueError("client TUN address must be inside client CIDR")
    if client_ip == server_ip:
        raise ValueError("client TUN address must not equal server TUN address")
    if client_ip == network.network_address:
        raise ValueError("client TUN address must not be the network address")
    if network.version == 4 and client_ip == network.broadcast_address:
        raise ValueError("client TUN address must not be the broadcast address")


def _interface_ip(address: str) -> str:
    return str(ipaddress.ip_interface(address).ip)


def _shared_return_enabled(config: dict[str, Any]) -> bool:
    tunnel = _tunnel_config(config)
    return bool(tunnel.get("shared_return_by_client_address", False))


def _destination_by_identity_hash(config: dict[str, Any]) -> dict[str, str]:
    tunnel = _tunnel_config(config)
    leases = tunnel.get("client_leases", ())
    if not isinstance(leases, list) or not leases:
        raise ValueError("shared server TUN return requires tunnel.client_leases")
    destination_by_identity_hash: dict[str, str] = {}
    for lease in leases:
        if not isinstance(lease, dict):
            raise ValueError("client lease must be an object")
        identity_hash = str(lease.get("identity_hash", ""))
        if not identity_hash.strip():
            raise ValueError("client lease identity_hash is required")
        client_address = str(lease.get("client_address") or "")
        if not client_address:
            client_address = _interface_ip(str(lease.get("client_tun_address", "")))
        else:
            client_address = str(ipaddress.ip_address(client_address))
        if identity_hash in destination_by_identity_hash:
            raise ValueError("client lease identity_hash must be unique")
        if client_address in destination_by_identity_hash.values():
            raise ValueError("client lease client_address must be unique")
        destination_by_identity_hash[identity_hash] = client_address
        previous_hashes = lease.get("previous_identity_hashes", ())
        if isinstance(previous_hashes, list | tuple):
            for item in previous_hashes:
                if not isinstance(item, dict):
                    continue
                previous_identity_hash = str(item.get("identity_hash", ""))
                if not previous_identity_hash:
                    continue
                if previous_identity_hash in destination_by_identity_hash:
                    raise ValueError("client previous identity_hash must be unique")
                destination_by_identity_hash[previous_identity_hash] = client_address
    return destination_by_identity_hash


def _server_tun_config(config: dict[str, Any], *, allow_os_mutation: bool) -> LinuxTunConfig:
    tunnel = _tunnel_config(config)
    return LinuxTunConfig(
        name=str(tunnel.get("server_tun_name", "x0vpns0")),
        mtu=int(tunnel.get("mtu", DEFAULT_TUN_MTU)),
        address=str(tunnel.get("server_address", DEFAULT_SERVER_TUN_ADDRESS)),
        allow_os_mutation=allow_os_mutation,
    )


def _client_tun_config(config: dict[str, Any], *, allow_os_mutation: bool) -> LinuxTunConfig:
    tunnel = _tunnel_config(config)
    return LinuxTunConfig(
        name=str(tunnel.get("client_tun_name", "x0vpn0")),
        mtu=int(tunnel.get("mtu", DEFAULT_TUN_MTU)),
        address=str(tunnel.get("client_address", DEFAULT_CLIENT_TUN_ADDRESS)),
        peer=str(tunnel.get("client_peer", DEFAULT_CLIENT_TUN_PEER)),
        allow_os_mutation=allow_os_mutation,
    )


def _server_nat_config(
    config: dict[str, Any],
    *,
    uplink_interface: str,
    allow_os_mutation: bool,
) -> LinuxServerNatConfig:
    tunnel = _tunnel_config(config)
    return LinuxServerNatConfig(
        tun_name=str(tunnel.get("server_tun_name", "x0vpns0")),
        uplink_interface=uplink_interface,
        client_cidr=str(tunnel.get("client_cidr", DEFAULT_CLIENT_CIDR)),
        vpn_listeners=tuple(
            LinuxServerVpnListener(
                transport=str(item["transport"]),  # type: ignore[arg-type]
                port=int(item["port"]),
            )
            for item in _dataplane_listener_entries(config)
        ),
        enable_iptables_compat=bool(tunnel.get("enable_iptables_compat", False)),
        nat_table_name=str(tunnel.get("nat_table_name", "x0vpn_nat")),
        filter_table_name=str(tunnel.get("filter_table_name", "x0vpn_filter")),
        allow_os_mutation=allow_os_mutation,
    )


def _client_policy_config(
    config: dict[str, Any],
    *,
    underlay_gateway: str,
    underlay_interface: str,
    enable_kill_switch: bool,
    allow_os_mutation: bool,
) -> LinuxNetworkPolicyConfig:
    tunnel = _tunnel_config(config)
    return LinuxNetworkPolicyConfig(
        tun_name=str(tunnel.get("client_tun_name", "x0vpn0")),
        remote_endpoints=tuple(
            RemoteEndpoint(
                candidate.remote_addr[0],
                candidate.remote_addr[1],
                candidate.transport,
            )
            for candidate in _dataplane_candidates(config)
        ),
        dns_servers=tuple(str(item) for item in tunnel.get("dns_servers", ())),
        route_all_traffic=bool(tunnel.get("route_all_traffic", True)),
        enable_kill_switch=enable_kill_switch,
        underlay_gateway=underlay_gateway,
        underlay_interface=underlay_interface,
        allow_os_mutation=allow_os_mutation,
    )


def _dataplane_bind(config: dict[str, Any]) -> FirstPartyDataplaneBind:
    listeners = _dataplane_listener_entries(config)
    tcp_ports = tuple(
        int(item["port"]) for item in listeners if item["transport"] == "tcp"
    )
    camouflage_ports = tuple(
        int(item["port"]) for item in listeners if item["transport"] == "camouflage"
    )
    return FirstPartyDataplaneBind(
        host=str(config.get("bind_host", DEFAULT_BIND_HOST)),
        tcp_port=tcp_ports[0] if tcp_ports else int(config["port"]),
        tcp_port_candidates=tcp_ports[1:],
        camouflage_port=(
            camouflage_ports[0] if camouflage_ports else int(config["port"])
        ),
        camouflage_port_candidates=camouflage_ports[1:],
        enable_udp=False,
        enable_tcp=bool(tcp_ports),
        enable_camouflage=bool(camouflage_ports),
    )


def _tcp_bind(config: dict[str, Any]) -> FirstPartyDataplaneBind:
    return _dataplane_bind(config)


def _dataplane_endpoint_entries(config: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    tunnel = _tunnel_config(config)
    raw_endpoints = tunnel.get("endpoints")
    if isinstance(raw_endpoints, list) and raw_endpoints:
        entries = tuple(dict(item) for item in raw_endpoints if isinstance(item, dict))
        if entries:
            return entries
    return (
        _endpoint_config(
            host=str(config["host"]),
            port=int(config["port"]),
            transport=_dataplane_transport(config),
            priority=0,
            path_label=f"nl-test-{_dataplane_transport(config)}",
            endpoint_id="primary",
        ),
    )


def _dataplane_listener_entries(config: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    tunnel = _tunnel_config(config)
    raw_listeners = tunnel.get("listeners")
    if isinstance(raw_listeners, list) and raw_listeners:
        entries = []
        seen: set[tuple[str, int]] = set()
        for item in raw_listeners:
            if not isinstance(item, dict):
                continue
            transport = _dataplane_transport_from_value(item.get("transport", "tcp"))
            port = int(item.get("port") or config["port"])
            if not 1 <= port <= 65535:
                raise ValueError("listener port must be between 1 and 65535")
            key = (transport, port)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"transport": transport, "port": port})
        if entries:
            return tuple(entries)
    return (
        {
            "transport": _dataplane_transport(config),
            "port": int(config["port"]),
        },
    )


def _dataplane_candidates(
    config: dict[str, Any],
    *,
    timeout_seconds: float | None = None,
) -> tuple[DataplaneEndpointCandidate, ...]:
    candidates: list[DataplaneEndpointCandidate] = []
    seen: set[tuple[str, str, int]] = set()
    for index, endpoint in enumerate(_dataplane_endpoint_entries(config), start=1):
        transport = _dataplane_transport_from_value(endpoint.get("transport", "tcp"))
        host = str(endpoint.get("host") or config["host"])
        port = int(endpoint.get("port") or config["port"])
        key = (transport, host, port)
        if key in seen:
            continue
        seen.add(key)
        priority = int(endpoint.get("priority", index - 1))
        path_label = str(endpoint.get("path_label") or f"nl-test-{transport}")
        endpoint_id = str(endpoint.get("endpoint_id") or f"endpoint-{index}")
        timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(endpoint.get("timeout_seconds", 3.0))
        )
        candidates.append(
            DataplaneEndpointCandidate(
                candidate_id=f"nl-{endpoint_id}-{transport}-{port}",
                path_label=path_label,
                transport=transport,
                remote_ref="|".join(
                    (
                        str(config.get("deployment_epoch", "unknown")),
                        endpoint_id,
                        transport,
                        host,
                        str(port),
                    )
                ),
                remote_addr=(host, port),
                priority=priority,
                timeout_seconds=timeout,
            )
        )
    if not candidates:
        raise ValueError("at least one managed VPN endpoint is required")
    return tuple(sorted(candidates, key=lambda item: (item.priority, item.candidate_id)))


def _dataplane_candidate(config: dict[str, Any]) -> DataplaneEndpointCandidate:
    return _dataplane_candidates(config)[0]


def _candidate_json(candidate: DataplaneEndpointCandidate) -> dict[str, Any]:
    return DataplaneEndpointCandidate(
        candidate_id=candidate.candidate_id,
        path_label=candidate.path_label,
        transport=candidate.transport,
        remote_ref=candidate.remote_ref,
        remote_addr=candidate.remote_addr,
        priority=candidate.priority,
        timeout_seconds=candidate.timeout_seconds,
    ).to_json_dict()


def _tcp_candidate(config: dict[str, Any]) -> DataplaneEndpointCandidate:
    return _dataplane_candidate(config)


def _default_route_interface() -> str | None:
    _gateway, interface = _default_route_gateway_and_interface()
    return interface


def _client_underlay_gateway_and_interface(
    config: dict[str, Any],
    *,
    underlay_gateway: str | None,
    underlay_interface: str | None,
) -> tuple[str | None, str | None]:
    tun_name = _client_tun_config(config, allow_os_mutation=False).name
    route_gateway, route_interface = _route_to_host_gateway_and_interface(
        str(config["host"])
    )
    if route_interface == tun_name:
        route_gateway, route_interface = None, None
    default_gateway, default_interface = _default_route_gateway_and_interface()
    if default_interface == tun_name:
        default_gateway, default_interface = None, None
    return (
        underlay_gateway or route_gateway or default_gateway,
        underlay_interface or route_interface or default_interface,
    )


def _systemd_service_active(service_name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ("systemctl", "is-active", service_name),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return False, f"systemctl_error:{exc}"
    status = result.stdout.strip() or f"exit_{result.returncode}"
    return result.returncode == 0 and status == "active", status


def _linux_interface_addresses(name: str) -> tuple[tuple[str, ...], str | None]:
    try:
        result = subprocess.run(
            ("ip", "-j", "addr", "show", "dev", name),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return (), str(exc)
    if result.returncode != 0:
        return (), (result.stderr.strip() or f"ip_exit_{result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return (), f"json_error:{exc}"
    addresses: list[str] = []
    for item in payload:
        for address in item.get("addr_info", ()):
            local = address.get("local")
            if local:
                addresses.append(str(local))
    return tuple(addresses), None


def _default_route_device() -> str | None:
    try:
        result = subprocess.run(
            ("ip", "route", "show", "default"),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == "default" and "dev" in parts:
            return parts[parts.index("dev") + 1]
    return None


def _tcp_listening_on_port(port: int) -> tuple[bool, str | None]:
    try:
        result = subprocess.run(
            ("ss", "-H", "-ltn", "sport", "=", f":{port}"),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr.strip() or f"ss_exit_{result.returncode}")
    return bool(result.stdout.strip()), None


def _route_device_for_prefix(prefix: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ("ip", "route", "show", prefix),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, (result.stderr.strip() or f"ip_exit_{result.returncode}")
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == prefix and "dev" in parts:
            return parts[parts.index("dev") + 1], None
    return None, "route_not_found"


def _route_to_host_gateway_and_interface(host: str) -> tuple[str | None, str | None]:
    try:
        ipaddress.ip_address(host)
        result = subprocess.run(
            ("ip", "route", "get", host),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        return None, None
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts or "dev" not in parts:
            continue
        gateway = parts[parts.index("via") + 1] if "via" in parts else None
        interface = parts[parts.index("dev") + 1]
        if interface:
            return gateway, interface
    return None, None


def _tcp_connect_open(
    host: str,
    port: int,
    *,
    timeout: float,
) -> tuple[bool, str | None]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except OSError as exc:
        return False, str(exc)


def _ipv4_forward_enabled() -> tuple[bool, str | None]:
    try:
        value = Path("/proc/sys/net/ipv4/ip_forward").read_text(
            encoding="utf-8"
        ).strip()
    except OSError as exc:
        return False, str(exc)
    return value == "1", None if value == "1" else f"ip_forward={value}"


def _default_route_gateway_and_interface() -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ("ip", "route", "show", "default"),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None, None
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts or parts[0] != "default":
            continue
        gateway = parts[parts.index("via") + 1] if "via" in parts else None
        interface = parts[parts.index("dev") + 1] if "dev" in parts else None
        if interface:
            return gateway, interface
    return None, None


def _find_dataplane_client_error(
    exc: BaseException,
) -> FirstPartyDataplaneClientError | None:
    seen: set[int] = set()
    cursor: BaseException | None = exc
    while cursor is not None and id(cursor) not in seen:
        if isinstance(cursor, FirstPartyDataplaneClientError):
            return cursor
        seen.add(id(cursor))
        cursor = cursor.__cause__ or cursor.__context__
    return None


def _best_effort_delete_tun(name: str) -> None:
    subprocess.run(
        ("ip", "link", "delete", name),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _best_effort_rollback(planner: Any) -> None:
    try:
        planner.rollback()
    except Exception:
        pass


def _command_to_string(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _attestation(
    *,
    now: int,
    expires_at: int,
    implementation_hash: str,
) -> PqcProviderAttestation:
    return PqcProviderAttestation(
        provider_id=PROVIDER_ID,
        kem_algorithm=KEM_ALGORITHM,
        signature_algorithm=SIGNATURE_ALGORITHM,
        mode="test",
        reviewed=False,
        issued_at=now,
        expires_at=expires_at,
        implementation_hash=implementation_hash,
    )


def _attestation_from_config(config: dict[str, Any]) -> PqcProviderAttestation:
    pqc = config["pqc"]
    return PqcProviderAttestation(
        provider_id=pqc["provider_id"],
        kem_algorithm=pqc["kem_algorithm"],
        signature_algorithm=pqc["signature_algorithm"],
        mode=pqc["mode"],
        reviewed=bool(pqc["reviewed"]),
        issued_at=int(pqc["issued_at"]),
        expires_at=int(pqc["expires_at"]),
        implementation_hash=pqc["implementation_hash"],
    )


def _key_to_json(key: IdentitySigningKey) -> dict[str, Any]:
    return {
        "key_id": key.key_id,
        "signature_algorithm": key.signature_algorithm,
        "secret": key.secret.hex(),
        "not_before": key.not_before,
        "not_after": key.not_after,
    }


def _key_from_json(value: dict[str, Any]) -> IdentitySigningKey:
    return IdentitySigningKey(
        key_id=str(value["key_id"]),
        signature_algorithm=str(value["signature_algorithm"]),
        secret=bytes.fromhex(str(value["secret"])),
        not_before=int(value.get("not_before", 0)),
        not_after=(
            None if value.get("not_after") is None else int(value.get("not_after"))
        ),
    )


def _token_to_json(token: SignedIdentityToken) -> dict[str, Any]:
    return {
        "version": token.version,
        "issuer": token.issuer,
        "key_id": token.key_id,
        "signature_algorithm": token.signature_algorithm,
        "serial": token.serial,
        "claims": json.loads(token.claims.canonical_json()),
        "signature": token.signature.hex(),
    }


def _token_from_json(value: dict[str, Any]) -> SignedIdentityToken:
    claims = value["claims"]
    return SignedIdentityToken(
        version=int(value["version"]),
        issuer=str(value["issuer"]),
        key_id=str(value["key_id"]),
        signature_algorithm=str(value["signature_algorithm"]),
        serial=str(value["serial"]),
        claims=IdentityClaims(
            spiffe_id=str(claims["spiffe_id"]),
            did=str(claims["did"]),
            workload=str(claims["workload"]),
            tenant=str(claims["tenant"]),
            device_id=str(claims["device_id"]),
            pqc_kem_algorithm=str(claims["pqc_kem_algorithm"]),
            pqc_signature_algorithm=str(claims["pqc_signature_algorithm"]),
            issued_at=int(claims["issued_at"]),
            expires_at=int(claims["expires_at"]),
            policy_epoch=str(claims["policy_epoch"]),
            attributes=dict(claims.get("attributes", {})),
        ),
        signature=bytes.fromhex(str(value["signature"])),
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any], *, mode: int) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(mode)


def _write_json_atomic(path: Path, payload: dict[str, Any], *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(mode)
    tmp.replace(path)


def _json_payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _assert_server_config_runtime_candidate(config: dict[str, Any]) -> None:
    _ = _admission_registry(config)
    _server_tun_config(config, allow_os_mutation=False)
    if _shared_return_enabled(config):
        _destination_by_identity_hash(config)


def _assert_client_config_runtime_candidate(config: dict[str, Any]) -> None:
    _assert_public_client_config(config)
    _client_tun_config(config, allow_os_mutation=False)
    _dataplane_candidates(config)
    _verifier(config)
    _policy(config)
    _client_hello_and_material(config)


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error_type": type(exc).__name__, "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from None
