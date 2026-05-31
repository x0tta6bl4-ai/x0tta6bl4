#!/usr/bin/env python3
"""Fail-closed real-readiness gate for the current x0tta6bl4 runtime contracts.

The check is intentionally stricter than old "production readiness score" scripts:
absence of evidence is a blocker, not a pass. It does not start services or mutate
state; command checks are limited to config/syntax/migration-head validation.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/real-readiness-current.json"
DEFAULT_OUTPUT_MD = ".tmp/validation-shards/real-readiness-current.md"
CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
EXTERNAL_DPI_PROOF_MISSING_GAP_ID = "external-dpi-proof-missing"
EXTERNAL_DPI_INTAKE_ACTION_ID = "external-dpi-real-artifact-intake"
EXTERNAL_DPI_CANDIDATE = "docs/verification/incoming/dpi_lab.json"
EXTERNAL_DPI_CONTRACT = "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
EXTERNAL_DPI_VALIDATOR = "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_COLLECTOR = "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_IMPORTER = "scripts/ops/import_ghost_pulse_external_evidence.py"
EXTERNAL_DPI_LOCAL_RUNNER = "scripts/ops/run_external_dpi_intake_local.py"
EXTERNAL_DPI_RUNBOOK = "docs/verification/ghost-pulse-external-dpi-intake-runbook.md"
EXTERNAL_DPI_LATEST = "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
EXTERNAL_DPI_SCHEMA_VERSION = "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1"
DATAPLANE_DELIVERY_EVENTBUS_COLLECTOR = (
    "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py"
)
REQUIRED_CROSS_PLANE_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_WARN = "WARN"

APP_REQUIRED_ENV_EMPTY = ("DATABASE_URL", "ADMIN_USER", "ADMIN_PASS")
APP_REQUIRED_ENV_PRESENT = (
    "VITE_API_BASE",
    "PORT",
    "CORE_API_HOST",
    "CORE_API_PORT",
)
FORBIDDEN_APP_TOKENS = (
    "x0tta6bl4_password",
    "mesh-ready-2026",
)
FORBIDDEN_GHOST_TOKENS = ("GHOST_AUTH_KEY",)
API_KEY_LOOKUP_PATTERNS = (
    re.compile(r"User\.api_key\s*=="),
    re.compile(r"filter_by\(\s*api_key\s*="),
    re.compile(r"\.filter\([^)\n]*api_key\s*=="),
)
EXTERNAL_DPI_FORBIDDEN_RAW_FIELDS = (
    "raw_ip_address",
    "raw_domain",
    "raw_url",
    "raw_sni",
    "raw_host_header",
    "raw_http_headers",
    "raw_payload",
    "subscriber_id",
    "customer_id",
    "wallet_address",
    "spiffe_id",
    "did",
    "api_token",
    "private_key",
)
EXTERNAL_DPI_REQUIRED_TRUE_FLAGS = (
    "authorization_scope.authorization_present",
    "authorization_scope.consent_or_legal_basis_present",
    "methodology.external_dpi_or_blocking_middlebox_observed",
    "result_summary.external_dpi_tested",
    "result_summary.baseline_blocked_or_detected",
    "result_summary.treatment_reachability_observed",
    "result_summary.reachability_observed",
    "result_summary.dpi_bypass_confirmed",
    "result_summary.bypass_confirmed",
    "result_summary.dataplane_confirmed",
    "raw_capture_redaction.redaction_performed",
    "raw_capture_redaction.forbidden_raw_fields_absent",
    "packet_flow_summary.packet_payloads_redacted",
    "repeatability_limits.not_generalizable_beyond_environment",
)
EXTERNAL_DPI_MUST_REMAIN_FALSE_FLAGS = (
    "result_summary.production_ready",
    "claim_boundary.proof_claims.production_ready",
    "claim_boundary.proof_claims.customer_traffic_confirmed",
    "claim_boundary.proof_claims.durable_policy_confirmed",
    "claim_boundary.proof_claims.anonymity_confirmed",
    "claim_boundary.proof_claims.provider_health_confirmed",
    "claim_boundary.proof_claims.payment_or_token_settlement_finality_confirmed",
)
HIGH_RISK_TRUE_CLAIM_LITERAL_RE = re.compile(
    r"""(?x)
    (?:
        ["'](?P<dict_key>
            production_ready|
            production_readiness_claim_allowed|
            dataplane_confirmed|
            mesh_dataplane_confirmed|
            restored_dataplane_claim_allowed|
            dpi_bypass_confirmed|
            bypass_confirmed|
            settlement_finality_confirmed|
            payment_settlement_confirmed|
            external_settlement_finality_confirmed|
            live_token_settlement_confirmed|
            traffic_delivery_claim_allowed|
            customer_traffic_claim_allowed|
            live_customer_traffic_confirmed
        )["']\s*:\s*True
    )
    |
    (?:
        (?P<assignment>
            production_ready|
            production_readiness_claim_allowed|
            dataplane_confirmed|
            mesh_dataplane_confirmed|
            restored_dataplane_claim_allowed|
            dpi_bypass_confirmed|
            bypass_confirmed|
            settlement_finality_confirmed|
            payment_settlement_confirmed|
            external_settlement_finality_confirmed|
            live_token_settlement_confirmed|
            traffic_delivery_claim_allowed|
            customer_traffic_claim_allowed|
            live_customer_traffic_confirmed
        )\s*=\s*True
    )
    """
)
HIGH_RISK_TRUE_CLAIM_BOUNDARY_MARKERS = (
    "claim_gate",
    "cross_plane_claim_gate",
    "claim_boundary",
    "required_evidence",
    "observed_evidence",
    "blockers",
    "proof_gate",
    "not proof",
    "not prove",
    "does not prove",
    "fail-closed",
    "local-only",
)
HIGH_RISK_TRUE_CLAIM_SCAN_DIRS = ("src", "scripts")
HIGH_RISK_TRUE_CLAIM_SCAN_EXCLUDED_PARTS = {
    "__pycache__",
    ".venv",
    "node_modules",
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: str
    evidence: str

    @property
    def ok(self) -> bool:
        return self.status != STATUS_FAIL


Runner = Callable[[Sequence[str], Mapping[str, str] | None, int], CommandResult]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def pass_check(check_id: str, details: str, evidence: str) -> CheckResult:
    return CheckResult(check_id, STATUS_PASS, details, evidence)


def fail_check(check_id: str, details: str, evidence: str) -> CheckResult:
    return CheckResult(check_id, STATUS_FAIL, details, evidence)


def warn_check(check_id: str, details: str, evidence: str) -> CheckResult:
    return CheckResult(check_id, STATUS_WARN, details, evidence)


def default_runner(root: Path) -> Runner:
    def _run(args: Sequence[str], env: Mapping[str, str] | None = None, timeout: int = 60) -> CommandResult:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            completed = subprocess.run(
                list(args),
                cwd=root,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return CommandResult(127, "", str(exc))
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return CommandResult(124, stdout, stderr or f"command timed out after {timeout}s")
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    return _run


def _format_command_failure(result: CommandResult) -> str:
    output = (result.stderr or result.stdout).strip()
    if len(output) > 500:
        output = output[:497] + "..."
    return f"exit={result.returncode}; {output or 'no output'}"


def check_required_files(root: Path) -> list[CheckResult]:
    files = (
        "Caddyfile.app",
        "Dockerfile.vpn",
        "docker-compose.app.yml",
        "docker-compose.ghost-vpn.yml",
        "x0tta6bl4-app/Dockerfile",
        "x0tta6bl4-app/server.cjs",
        "x0tta6bl4-app/src/App.tsx",
        "x0tta6bl4-app/vite.config.ts",
        "x0tta6bl4-app/.env.example",
        "alembic/env.py",
        "alembic/versions/d7c8f1a2b3c4_add_hashed_api_keys.py",
        "scripts/ops/run_cross_plane_proof_gate.py",
        DATAPLANE_DELIVERY_EVENTBUS_COLLECTOR,
        "src/mesh/metric_evidence_policy.py",
    )
    missing = [item for item in files if not _exists(root, item)]
    if missing:
        return [fail_check("required_files", "Missing real-readiness files: " + ", ".join(missing), "file existence")]
    return [pass_check("required_files", f"Required files present: {len(files)}", "file existence")]


def check_app_contract(root: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    compose = _read(root, "docker-compose.app.yml")
    caddy = _read(root, "Caddyfile.app")
    dockerfile = _read(root, "x0tta6bl4-app/Dockerfile")
    server = _read(root, "x0tta6bl4-app/server.cjs")
    vite = _read(root, "x0tta6bl4-app/vite.config.ts")
    app = _read(root, "x0tta6bl4-app/src/App.tsx")
    env_example = _read(root, "x0tta6bl4-app/.env.example")

    required_fragments = {
        "compose_port_8081": ('PORT: "8081"', compose),
        "compose_core_api_port_8083": ('CORE_API_PORT: "8083"', compose),
        "compose_database_required": ("DATABASE_URL: ${DATABASE_URL:?set DATABASE_URL}", compose),
        "compose_admin_user_required": ("ADMIN_USER: ${ADMIN_USER:?set ADMIN_USER}", compose),
        "compose_admin_pass_required": ("ADMIN_PASS: ${ADMIN_PASS:?set ADMIN_PASS}", compose),
        "caddy_to_app_8081": ("reverse_proxy localhost:8081", caddy),
        "dockerfile_exposes_8081": ("EXPOSE 8081", dockerfile),
        "dockerfile_health_8081": ("http://localhost:8081/api/status", dockerfile),
        "server_port_default_8081": ("parsePort('PORT', '8081')", server),
        "server_core_api_port_8083": ("parsePort('CORE_API_PORT', '8083')", server),
        "server_admin_user_required": ("requiredEnv('ADMIN_USER')", server),
        "server_admin_pass_required": ("requiredEnv('ADMIN_PASS')", server),
        "server_database_url_or_pg_required": ("poolConfigFromEnv", server),
        "vite_proxy_8081": ("http://localhost:8081", vite),
        "ui_api_base_env": ("import.meta.env.VITE_API_BASE || '/api'", app),
    }
    missing = [check_id for check_id, (fragment, text) in required_fragments.items() if fragment not in text]
    if missing:
        checks.append(fail_check("app_port_env_contract", "Missing app contract fragments: " + ", ".join(missing), "static file scan"))
    else:
        checks.append(pass_check("app_port_env_contract", "App/UI/Caddy contract is pinned to app port 8081 and core API 8083", "static file scan"))

    forbidden_hits = [token for token in FORBIDDEN_APP_TOKENS if any(token in text for text in (compose, dockerfile, server, env_example))]
    if forbidden_hits:
        checks.append(fail_check("app_no_default_secrets", "Forbidden app secret/default tokens found: " + ", ".join(forbidden_hits), "static file scan"))
    else:
        checks.append(pass_check("app_no_default_secrets", "No known app default secret tokens in app runtime files", "static file scan"))

    env_map = parse_env_example(env_example)
    missing_env = [key for key in (*APP_REQUIRED_ENV_EMPTY, *APP_REQUIRED_ENV_PRESENT) if key not in env_map]
    non_empty_secrets = [key for key in APP_REQUIRED_ENV_EMPTY if env_map.get(key, "") != ""]
    if missing_env or non_empty_secrets:
        details: list[str] = []
        if missing_env:
            details.append("missing keys: " + ", ".join(missing_env))
        if non_empty_secrets:
            details.append("secret placeholders must be empty: " + ", ".join(non_empty_secrets))
        checks.append(fail_check("app_env_example_contract", "; ".join(details), "x0tta6bl4-app/.env.example"))
    else:
        checks.append(pass_check("app_env_example_contract", "Secret-bearing app env placeholders are present and empty", "x0tta6bl4-app/.env.example"))

    return checks


def parse_env_example(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def check_auth_contract(root: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    database = _read(root, "src/database/__init__.py")
    auth_service = _read(root, "src/services/maas_auth_service.py")
    security = _read(root, "src/api/maas_security.py")
    migration = _read(root, "alembic/versions/d7c8f1a2b3c4_add_hashed_api_keys.py")

    required = {
        "user_api_key_hash_column": "api_key_hash = Column" in database,
        "hash_lookup_helper": "User.api_key_hash == ApiKeyManager.hash_key(api_key)" in auth_service,
        "legacy_api_key_cleared": "user.api_key = None" in auth_service,
        "migration_adds_hash": "api_key_hash" in migration and "create_index" in migration,
        "hash_uses_utf8": "key.encode(\"utf-8\")" in security or "key.encode('utf-8')" in security,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        checks.append(fail_check("auth_hash_only_contract", "Missing auth hash-only fragments: " + ", ".join(missing), "static file scan"))
    else:
        checks.append(pass_check("auth_hash_only_contract", "API keys are issued/queried through api_key_hash with legacy api_key cleared", "static file scan"))

    lookup_hits: list[str] = []
    for path in iter_source_files(root / "src"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("src/libx0t/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in API_KEY_LOOKUP_PATTERNS):
            lookup_hits.append(rel)
    if lookup_hits:
        checks.append(fail_check("auth_no_plaintext_user_lookup", "Plaintext User.api_key lookup remains in: " + ", ".join(sorted(lookup_hits)), "src scan"))
    else:
        checks.append(pass_check("auth_no_plaintext_user_lookup", "No direct User.api_key lookup patterns in src outside src/libx0t", "src scan"))
    return checks


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in {".git", "__pycache__", ".venv", "node_modules"} for part in path.parts):
            continue
        yield path


def check_db_contract(root: Path) -> list[CheckResult]:
    database = _read(root, "src/database/__init__.py")
    parity_script = _read(root, "scripts/check_orm_schema_parity.py")
    required = {
        "schema_parity_report": "def get_schema_parity_report" in database,
        "alembic_head_gaps": "def get_alembic_head_gaps" in database,
        "compatibility_gaps": "def get_schema_compatibility_gaps" in database,
        "ensure_compatible": "def ensure_schema_compatible" in database,
        "parity_script_uses_report": "get_schema_parity_report" in parity_script,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [fail_check("db_schema_guard_contract", "Missing DB schema guard fragments: " + ", ".join(missing), "static file scan")]
    return [pass_check("db_schema_guard_contract", "DB guard checks Alembic heads and ORM/DB parity", "static file scan")]


def check_ghost_contract(root: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    compose = _read(root, "docker-compose.ghost-vpn.yml")
    dockerfile = _read(root, "Dockerfile.vpn")
    protocol = _read(root, "services/nl-server/ghost-vpn/ghost_vpn_protocol.py")

    required = {
        "compose_requires_ghost_vpn_auth_key": "GHOST_VPN_AUTH_KEY: ${GHOST_VPN_AUTH_KEY:?set GHOST_VPN_AUTH_KEY}" in compose,
        "compose_requires_grafana_password": "GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?set GRAFANA_PASSWORD}" in compose,
        "dockerfile_uses_local_source": "services/nl-server/ghost-vpn" in dockerfile,
        "protocol_auth_key_contract": 'AUTH_KEY_ENV = "GHOST_VPN_AUTH_KEY"' in protocol,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        checks.append(fail_check("ghost_vpn_contract", "Missing Ghost VPN fragments: " + ", ".join(missing), "static file scan"))
    else:
        checks.append(pass_check("ghost_vpn_contract", "Ghost VPN compose/source/auth env contract is explicit", "static file scan"))

    forbidden = [token for token in FORBIDDEN_GHOST_TOKENS if token in compose or token in dockerfile]
    if forbidden:
        checks.append(fail_check("ghost_no_legacy_auth_key", "Legacy Ghost auth env found: " + ", ".join(forbidden), "static file scan"))
    else:
        checks.append(pass_check("ghost_no_legacy_auth_key", "No legacy GHOST_AUTH_KEY in Ghost VPN deployment files", "static file scan"))
    return checks


def check_pulse_contract(root: Path) -> list[CheckResult]:
    proof_gate = _read(root, "scripts/ops/run_ghost_pulse_proof_gate.py")
    required = {
        "current_runtime_claim": 'CURRENT_RUNTIME_CLAIM_ID = "current_runtime_attached"' in proof_gate,
        "runtime_env": 'RUNTIME_INTERFACE_ENV = "GHOST_PULSE_RUNTIME_INTERFACE"' in proof_gate,
        "current_runtime_provider": "current_runtime_provider" in proof_gate,
        "production_ready_requires_runtime": "and current_runtime_verified" in proof_gate,
        "claim_boundary_runtime": '"current_runtime_attached": current_runtime_verified' in proof_gate,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [fail_check("pulse_current_runtime_gate", "Missing Pulse/eBPF runtime gate fragments: " + ", ".join(missing), "static file scan")]
    return [pass_check("pulse_current_runtime_gate", "Pulse proof gate separates historical evidence from current runtime attach", "static file scan")]


def check_ghost_pulse_local_timing_evidence_contract(root: Path) -> list[CheckResult]:
    required_paths = {
        "pulse_transport": "src/network/transport/pulse_transport.py",
        "whitelist_mimicry": "src/network/obfuscation/whitelist_mimicry.py",
        "pulse_ebpf_source": "src/network/ebpf/x0tta6bl4_pulse.bpf.c",
        "ghost_core_entrypoint": "ghost-core.sh",
        "pulse_protocol_boundary_doc": "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md",
        "seed_replay_verifier": "scripts/ops/verify_ghost_pulse_rng_replay.py",
        "artifact_chain_verifier": "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    }
    missing_paths = [
        name
        for name, relative in required_paths.items()
        if not _exists(root, relative)
    ]
    if missing_paths:
        return [
            fail_check(
                "ghost_pulse_local_timing_evidence_contract",
                "Missing Ghost Pulse local timing evidence files: " + ", ".join(missing_paths),
                "static file scan",
            )
        ]

    pulse_transport = _read(root, required_paths["pulse_transport"])
    whitelist_mimicry = _read(root, required_paths["whitelist_mimicry"])
    pulse_ebpf_source = _read(root, required_paths["pulse_ebpf_source"])
    ghost_core = _read(root, required_paths["ghost_core_entrypoint"])
    protocol_doc = _read(root, required_paths["pulse_protocol_boundary_doc"])
    seed_replay = _read(root, required_paths["seed_replay_verifier"])
    artifact_chain = _read(root, required_paths["artifact_chain_verifier"])

    required = {
        "pulse_transport_seeded_class": (
            "class PulseUDPTransport" in pulse_transport
            and "pulse_seed" in pulse_transport
            and "PULSE_LOCAL_CLAIM_BOUNDARY" in pulse_transport
        ),
        "pulse_transport_bounded_timing_metadata": (
            "timing_plan_samples" in pulse_transport
            and "timing_plan_samples_tail" in pulse_transport
            and "timing_plan_summary" in pulse_transport
            and "timing_plan_replay" in pulse_transport
        ),
        "pulse_transport_replay_digest_projection": (
            "def timing_plan_replay_digest" in pulse_transport
            and "def timing_plan_replay_projection" in pulse_transport
        ),
        "pulse_transport_local_only_claim_boundary": (
            "EXPERIMENTAL_LOCAL_TIMING_PROFILE" in pulse_transport
            and '"stealth_mode": "NOT_VERIFIED"' in pulse_transport
            and "production" in pulse_transport.lower()
        ),
        "whitelist_mimicry_local_only_boundary": (
            "WHITELIST_MIMICRY_CLAIM_BOUNDARY" in whitelist_mimicry
            and '"provider_whitelist_confirmed": False' in whitelist_mimicry
            and '"external_dpi_tested": False' in whitelist_mimicry
        ),
        "pulse_ebpf_static_source_marker": (
            "xdp_x0tta6bl4_pulse" in pulse_ebpf_source
            and "attached" in pulse_ebpf_source.lower()
            and "production readiness" in pulse_ebpf_source.lower()
        ),
        "ghost_core_fail_closed_status": (
            "LOCAL_EXPERIMENT_NOT_PRODUCTION_PROOF" in ghost_core
            and "dpi_bypass_confirmed=false" in ghost_core
            and "production_ready=false" in ghost_core
        ),
        "protocol_doc_claim_boundary": (
            "LOCAL_EXPERIMENT_NOT_PRODUCTION_PROOF" in protocol_doc
            and "external DPI bypass" in protocol_doc
            and "provider whitelist behavior" in protocol_doc
            and "production readiness" in protocol_doc
        ),
        "seed_replay_verifier_uses_transport_digest": (
            "PulseUDPTransport.timing_plan_replay_digest" in seed_replay
            and "PulseUDPTransport.timing_plan_replay_projection" in seed_replay
        ),
        "artifact_chain_runs_seed_replay": (
            "seed_replay_verifier" in artifact_chain
            and "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED" in artifact_chain
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "ghost_pulse_local_timing_evidence_contract",
                "Missing Ghost Pulse local timing evidence fragments: " + ", ".join(missing),
                "static file scan",
            )
        ]
    return [
        pass_check(
            "ghost_pulse_local_timing_evidence_contract",
            "Ghost Pulse local timing evidence keeps deterministic seed replay, bounded metadata, static artifact-chain markers, and local-only claim boundaries",
            "src/network/transport/pulse_transport.py; scripts/ops/verify_ghost_pulse_rng_replay.py; scripts/ops/verify_ghost_pulse_artifact_chain.py",
        )
    ]


def check_post_action_dataplane_gate_contract(root: Path) -> list[CheckResult]:
    action_enforcer = _read(root, "src/mesh/action_enforcer.py")
    mape_k_loop = _read(root, "src/core/mape_k_loop.py")
    maas_nodes = _read(root, "src/api/maas_nodes.py")
    service_trace = _read(root, "src/services/service_event_trace.py")
    recovery_executor = _read(root, "src/self_healing/recovery/executor.py")
    ebpf_self_healing = _read(root, "src/self_healing/ebpf_anomaly_detector.py")

    required = {
        "post_action_probe_env": "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE" in action_enforcer,
        "post_action_summary": "def _post_action_dataplane_revalidation_summary" in action_enforcer,
        "restored_dataplane_gate": "restored_dataplane_claim_allowed" in action_enforcer,
        "post_action_claim_gate": '"claim_gate"' in action_enforcer,
        "action_enforcer_downstream_claim_boundaries": "def _claim_boundary_summary"
        in action_enforcer
        and '"claim_boundaries"' in action_enforcer
        and 'downstream_evidence.get("claim_boundaries"' in action_enforcer,
        "core_mapek_execute_claim_boundaries": "def _terminal_event_payloads_by_source"
        in mape_k_loop
        and "event_payloads_by_source" in mape_k_loop
        and "def _downstream_evidence_delta" in mape_k_loop
        and '"claim_boundaries"' in mape_k_loop,
        "env_rechecked_per_call": "return _env_bool(_POST_ACTION_PROBE_ENV_VAR, False)" in action_enforcer,
        "maas_heal_revalidation": "def _mesh_healing_post_action_revalidation" in maas_nodes,
        "maas_heal_response_field": '"post_action_dataplane_revalidation"' in maas_nodes,
        "maas_heal_blocks_restored_claim": '"restored_dataplane_claim_allowed": False' in maas_nodes,
        "maas_heal_no_probe_reason": "no_bounded_post_action_dataplane_probe_attached" in maas_nodes,
        "service_trace_post_action_summary": (
            "def _post_action_dataplane_revalidation_summary" in service_trace
            and '"post_action_dataplane_revalidation": post_action_dataplane' in service_trace
        ),
        "service_trace_profile_requires_post_action_gate": (
            "post_action_gate_allows_dataplane" in service_trace
            and '"raw_dataplane_confirmed": raw_dataplane_confirmed' in service_trace
            and '"dataplane_claim_gate_required"' in service_trace
            and '"post_action_dataplane_claim_gate_not_allowed"' in service_trace
        ),
        "recovery_executor_post_action_gate": (
            "X0TTA6BL4_RECOVERY_POST_ACTION_PROBE" in recovery_executor
            and "_DATAPLANE_REVALIDATED_ACTION_TYPES" in recovery_executor
            and "def _post_action_dataplane_claim_gate" in recovery_executor
            and "def _post_action_dataplane_revalidation_summary"
            in recovery_executor
            and "def _recovery_claim_gate" in recovery_executor
            and '"post_action_dataplane_revalidation": post_action_revalidation'
            in recovery_executor
            and '"claim_gate": _recovery_claim_gate(result, post_action_revalidation)'
            in recovery_executor
            and '"restored_dataplane_claim_allowed": restored_dataplane_claim_allowed'
            in recovery_executor
            and '"production_readiness_claim_allowed": False' in recovery_executor
            and '"live_customer_traffic_confirmed": False' in recovery_executor
            and '"operator_approval_confirmed": False' in recovery_executor
            and '"external_dpi_bypass_confirmed": False' in recovery_executor
            and '"settlement_finality_confirmed": False' in recovery_executor
        ),
        "ebpf_self_healing_claim_gate": (
            "def _ebpf_recovery_claim_gate" in ebpf_self_healing
            and "x0tta6bl4.self_healing.ebpf_recovery_claim_gate.v1"
            in ebpf_self_healing
            and '"claim_gate": _ebpf_recovery_claim_gate(result)'
            in ebpf_self_healing
            and '"restored_dataplane_claim_allowed": False'
            in ebpf_self_healing
            and '"route_convergence_claim_allowed": False'
            in ebpf_self_healing
            and '"kernel_forwarding_correctness_claim_allowed": False'
            in ebpf_self_healing
            and '"dataplane_delivery_claim_allowed": False'
            in ebpf_self_healing
            and '"traffic_delivery_claim_allowed": False'
            in ebpf_self_healing
            and '"production_readiness_claim_allowed": False'
            in ebpf_self_healing
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "post_action_dataplane_gate_contract",
                "Missing post-action dataplane gate fragments: " + ", ".join(missing),
                "src/mesh/action_enforcer.py; src/core/mape_k_loop.py; src/api/maas_nodes.py; src/services/service_event_trace.py; src/self_healing/recovery/executor.py; src/self_healing/ebpf_anomaly_detector.py",
            )
        ]
    return [
        pass_check(
            "post_action_dataplane_gate_contract",
            "Mesh heal/restart, self-healing recovery, and eBPF self-healing paths keep restored-dataplane/route/traffic/production claims behind bounded proof or fail-closed claim gates, and service traces keep post-action dataplane profile claims behind the nested claim gate",
            "src/mesh/action_enforcer.py; src/core/mape_k_loop.py; src/api/maas_nodes.py; src/services/service_event_trace.py; src/self_healing/recovery/executor.py; src/self_healing/ebpf_anomaly_detector.py",
        )
    ]


def check_dataplane_delivery_eventbus_collector_contract(root: Path) -> list[CheckResult]:
    collector = _read(root, DATAPLANE_DELIVERY_EVENTBUS_COLLECTOR)
    required = {
        "collector_schema": (
            'SCHEMA = "x0tta6bl4.dataplane_delivery_eventbus_evidence_collector.v1"'
            in collector
        ),
        "explicit_local_probe_authorization": (
            '"--allow-local-probe"' in collector
            and "BLOCKED_LOCAL_PROBE_NOT_AUTHORIZED" in collector
            and "allow_local_probe_required" in collector
        ),
        "event_write_is_opt_in": (
            '"--write-event"' in collector
            and "if args.write_event:" in collector
            and "EventBus(project_root=str(root)).publish" in collector
            and "EventType.PIPELINE_STAGE_END" in collector
        ),
        "non_local_targets_blocked": (
            "def is_localish_target" in collector
            and "BLOCKED_NON_LOCAL_TARGET" in collector
            and "target_must_be_loopback_private_or_link_local" in collector
        ),
        "target_metadata_redacted": (
            '"host_hash": sha256_text' in collector
            and '"raw_target_redacted": True' in collector
        ),
        "post_action_revalidation_shape": (
            '"post_action_dataplane_revalidation"' in collector
            and '"post_action_dataplane_revalidated": confirmed' in collector
            and '"restored_dataplane_claim_allowed": confirmed' in collector
            and '"evidence": {' in collector
            and '"event_ids_count": 1' in collector
            and '"source_agents_count": 1' in collector
        ),
        "nested_claim_gate_shape": (
            '"schema": "x0tta6bl4.post_action_dataplane_claim_gate.v1"' in collector
            and '"observed_evidence": {' in collector
            and '"probe_attempted": True' in collector
            and '"dataplane_confirmed": confirmed' in collector
            and '"redacted": True' in collector
            and '"claim_boundary": CLAIM_BOUNDARY' in collector
        ),
        "proof_gate_compatible_event_shape": (
            '"operation": "post_action_dataplane_revalidation"' in collector
            and '"component": "post_action_dataplane_local_collector"' in collector
            and '"proof_gate_command": [' in collector
            and '"scripts/ops/run_cross_plane_proof_gate.py"' in collector
            and '"dataplane_delivery"' in collector
        ),
        "ready_requires_successful_written_event": (
            'ready = probe.get("dataplane_confirmed") is True and event_written'
            in collector
            and "DATAPLANE_EVENTBUS_EVIDENCE_READY" in collector
        ),
        "no_strong_claim_overpromotion": (
            '"traffic_delivery_claim_allowed": False' in collector
            and '"customer_traffic_claim_allowed": False' in collector
            and '"production_readiness_claim_allowed": False' in collector
            and '"external_reachability_claim_allowed": False' in collector
            and '"dpi_bypass_claim_allowed": False' in collector
            and '"settlement_finality_claim_allowed": False' in collector
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "dataplane_delivery_eventbus_collector_contract",
                "Missing dataplane delivery EventBus collector fragments: "
                + ", ".join(missing),
                DATAPLANE_DELIVERY_EVENTBUS_COLLECTOR,
            )
        ]
    return [
        pass_check(
            "dataplane_delivery_eventbus_collector_contract",
            "Dataplane delivery collector is local-only, opt-in for probing and EventBus writes, redacts targets, emits proof-gate-compatible post-action revalidation evidence, and keeps traffic/customer/DPI/settlement/production claims false",
            DATAPLANE_DELIVERY_EVENTBUS_COLLECTOR,
        )
    ]


def check_mesh_metric_policy_contract(root: Path) -> list[CheckResult]:
    policy = _read(root, "src/mesh/metric_evidence_policy.py")
    mape_k_loop = _read(root, "src/core/mape_k_loop.py")
    action_enforcer = _read(root, "src/mesh/action_enforcer.py")

    required = {
        "estimate_decision_present": 'DECISION_ESTIMATE_OR_FALLBACK = "estimate_or_fallback_based"' in policy,
        "estimate_high_risk_blocked": (
            "elif estimated_samples > 0.0 or fallback_samples > 0.0" in policy
            and 'decision_basis = DECISION_ESTIMATE_OR_FALLBACK' in policy
            and 'control_risk = "blocked"' in policy
            and "allows_high_risk = False" in policy
        ),
        "high_risk_allowlist_excludes_estimates": (
            "HIGH_RISK_ALLOWED_DECISION_BASES" in policy
            and "DECISION_DATAPLANE_CONFIRMED" in policy
            and "DECISION_ESTIMATE_OR_FALLBACK,\n}" not in policy
        ),
        "mapek_applies_policy": (
            "def _apply_mesh_metric_evidence_policy" in mape_k_loop
            and "blocked_high_risk_mesh_actions" in mape_k_loop
            and "mesh_high_risk_actions_blocked" in mape_k_loop
        ),
        "action_enforcer_applies_policy": (
            "mesh_metric_policy_allows_high_risk" in action_enforcer
            and "blocked_by_metric_evidence_policy" in action_enforcer
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "mesh_metric_policy_contract",
                "Missing mesh metric policy fragments: " + ", ".join(missing),
                "src/mesh/metric_evidence_policy.py; src/core/mape_k_loop.py; src/mesh/action_enforcer.py",
            )
        ]
    return [
        pass_check(
            "mesh_metric_policy_contract",
            "High-risk mesh actions require dataplane-confirmed metric evidence; estimates/fallbacks are visible but blocking",
            "src/mesh/metric_evidence_policy.py; src/core/mape_k_loop.py; src/mesh/action_enforcer.py",
        )
    ]


def check_yggdrasil_observed_state_contract(root: Path) -> list[CheckResult]:
    yggdrasil = _read(root, "src/network/yggdrasil_client.py")
    libx0t_yggdrasil = _read(root, "src/libx0t/network/yggdrasil_client.py")
    telemetry_collector = _read(root, "src/mesh/telemetry_collector.py")
    network_manager = _read(root, "src/mesh/network_manager.py")
    mape_k_loop = _read(root, "src/core/mape_k_loop.py")

    required = {
        "claim_boundary": "YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY" in yggdrasil
        and "remote peer authenticity" in yggdrasil,
        "eventbus_publish_helper": "def _publish_yggdrasil_observation" in yggdrasil
        and "EventType.PIPELINE_STAGE_END" in yggdrasil
        and '"network_yggdrasil_observed_state"' in yggdrasil,
        "service_identity_metadata": "service_event_identity" in yggdrasil
        and '"spiffe_id_configured"' in yggdrasil
        and '"did_configured"' in yggdrasil
        and '"wallet_address_configured"' in yggdrasil,
        "bounded_output_metadata": "def _bounded_output_metadata" in yggdrasil
        and '"stdout_sha256"' in yggdrasil
        and '"stderr_sha256"' in yggdrasil
        and '"output_bounded": True' in yggdrasil
        and '"output_redacted": True' in yggdrasil,
        "common_evidence_metadata": "def _evidence_metadata" in yggdrasil
        and '"payloads_redacted": True' in yggdrasil
        and '"redacted": True' in yggdrasil,
        "get_self_signature": "def get_yggdrasil_status(" in yggdrasil
        and "event_bus: Optional[EventBus]" in yggdrasil
        and "include_evidence: bool = False" in yggdrasil,
        "get_self_observation": 'operation="get_self"' in yggdrasil
        and 'command=["yggdrasilctl", "getSelf"]' in yggdrasil
        and '"node_field_count"' in yggdrasil,
        "get_peers_signature": "def get_yggdrasil_peers(" in yggdrasil
        and "event_bus: Optional[EventBus]" in yggdrasil
        and "include_evidence: bool = False" in yggdrasil,
        "get_peers_observation": 'operation="get_peers"' in yggdrasil
        and 'command=["yggdrasilctl", "getPeers"]' in yggdrasil
        and '"peer_count"' in yggdrasil,
        "return_code_and_duration": "returncode=result.returncode" in yggdrasil
        and "returncode=returncode" in yggdrasil
        and "duration_ms = (time.monotonic() - started) * 1000.0" in yggdrasil,
        "fatal_output_failure_boundary": "def _has_yggdrasil_output_failure"
        in yggdrasil
        and "YggdrasilCommandOutputError" in yggdrasil,
        "libx0t_facade_uses_canonical_publish": "_impl._publish_yggdrasil_observation"
        in libx0t_yggdrasil
        and "_impl.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY" in libx0t_yggdrasil,
        "telemetry_collector_requests_evidence": "include_evidence=True"
        in telemetry_collector
        and "downstream_claim_boundaries" in telemetry_collector
        and '"claim_boundaries"' in telemetry_collector
        and "def _safe_evidence_claim_boundaries" in telemetry_collector,
        "network_manager_requests_evidence": "include_evidence=True" in network_manager
        and "yggdrasil_evidence_summary" in network_manager
        and "downstream_claim_boundaries" in network_manager
        and '"claim_boundaries"' in network_manager,
        "core_mapek_preserves_transitive_claim_boundaries": "def _transitive_downstream_evidence"
        in mape_k_loop
        and "downstream_claim_boundaries" in mape_k_loop
        and '"claim_boundaries"' in mape_k_loop
        and '"claim_boundaries_total"' in mape_k_loop,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "yggdrasil_observed_state_contract",
                "Missing Yggdrasil observed-state fragments: " + ", ".join(missing),
                "src/network/yggdrasil_client.py; src/libx0t/network/yggdrasil_client.py; src/mesh/telemetry_collector.py; src/mesh/network_manager.py; src/core/mape_k_loop.py",
            )
        ]
    return [
        pass_check(
            "yggdrasil_observed_state_contract",
            "Yggdrasil getSelf/getPeers publish bounded read-only EventBus observed-state evidence and telemetry/network-manager/core-MAPE-K consumers preserve event IDs plus claim boundaries downstream",
            "src/network/yggdrasil_client.py; src/libx0t/network/yggdrasil_client.py; src/mesh/telemetry_collector.py; src/mesh/network_manager.py; src/core/mape_k_loop.py",
        )
    ]


def check_service_identity_trust_claim_gate_contract(root: Path) -> list[CheckResult]:
    service_identity_status = _read(root, "src/api/service_identity_status.py")
    pqc_healer = _read(root, "src/self_healing/pqc_zero_trust_healer.py")
    spiffe_mapek = _read(root, "src/self_healing/mape_k_spiffe_integration.py")
    required = {
        "claim_gate_boundary": (
            "SERVICE_IDENTITY_CLAIM_GATE_BOUNDARY" in service_identity_status
            and "does not prove live SPIFFE SVID issuance" in service_identity_status
        ),
        "claim_gate_helper": (
            "def _service_identity_claim_gate" in service_identity_status
            and "x0tta6bl4.service_identity.claim_gate.v1" in service_identity_status
        ),
        "local_registry_claim_allowed": (
            '"local_redacted_identity_registry_claim_allowed"' in service_identity_status
        ),
        "local_trace_surface_claim_allowed": (
            '"local_trace_filter_surface_claim_allowed"' in service_identity_status
        ),
        "live_spiffe_svid_false": (
            '"live_spiffe_svid_claim_allowed": False' in service_identity_status
        ),
        "did_ownership_false": (
            '"did_ownership_claim_allowed": False' in service_identity_status
        ),
        "wallet_control_false": (
            '"wallet_control_claim_allowed": False' in service_identity_status
        ),
        "event_producer_authenticity_false": (
            '"event_producer_identity_authenticity_claim_allowed": False'
            in service_identity_status
        ),
        "chain_identity_finality_false": (
            '"chain_identity_finality_claim_allowed": False' in service_identity_status
        ),
        "production_readiness_false": (
            '"production_readiness_claim_allowed": False' in service_identity_status
        ),
        "raw_identity_values_redacted": (
            '"raw_identity_values_redacted": True' in service_identity_status
        ),
        "claim_gate_attached_to_status": (
            '"service_identity_claim_gate": _service_identity_claim_gate('
            in service_identity_status
        ),
        "trace_claim_gate_attacher": (
            "def _attach_service_identity_trace_claim_gates" in service_identity_status
            and "def _redacted_trace_payload_ready" in service_identity_status
        ),
        "event_trace_filter_claim_gate": (
            'surface="service_identity.event_trace_filter"' in service_identity_status
            and "_attach_service_identity_trace_claim_gates(" in service_identity_status
        ),
        "event_traces_claim_gate": (
            'surface="service_identity.event_traces"' in service_identity_status
            and "_attach_service_identity_trace_claim_gates(" in service_identity_status
        ),
        "cross_plane_gate_still_attached": (
            '"cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata'
            in service_identity_status
        ),
        "pqc_recovery_claim_gate": (
            "def _pqc_recovery_claim_gate" in pqc_healer
            and "x0tta6bl4.self_healing.pqc_recovery_claim_gate.v1" in pqc_healer
            and '"claim_gate": _pqc_recovery_claim_gate(result)' in pqc_healer
            and '"live_pqc_trust_finality_claim_allowed": False' in pqc_healer
            and '"live_spiffe_svid_claim_allowed": False' in pqc_healer
            and '"dataplane_delivery_claim_allowed": False' in pqc_healer
            and '"traffic_delivery_claim_allowed": False' in pqc_healer
            and '"production_readiness_claim_allowed": False' in pqc_healer
        ),
        "spiffe_recovery_claim_gate": (
            "def _spiffe_recovery_claim_gate" in spiffe_mapek
            and "x0tta6bl4.self_healing.spiffe_recovery_claim_gate.v1"
            in spiffe_mapek
            and '"claim_gate": _spiffe_recovery_claim_gate(result)' in spiffe_mapek
            and '"live_spiffe_svid_claim_allowed": False' in spiffe_mapek
            and '"did_ownership_claim_allowed": False' in spiffe_mapek
            and '"wallet_control_claim_allowed": False' in spiffe_mapek
            and '"chain_identity_finality_claim_allowed": False' in spiffe_mapek
            and '"dataplane_delivery_claim_allowed": False' in spiffe_mapek
            and '"traffic_delivery_claim_allowed": False' in spiffe_mapek
            and '"production_readiness_claim_allowed": False' in spiffe_mapek
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "service_identity_trust_claim_gate_contract",
                "Missing service identity trust claim-gate fragments: "
                + ", ".join(missing),
                "src/api/service_identity_status.py; src/self_healing/pqc_zero_trust_healer.py; src/self_healing/mape_k_spiffe_integration.py",
            )
        ]
    return [
        pass_check(
            "service_identity_trust_claim_gate_contract",
            "Service identity status plus PQC/SPIFFE recovery events separate local redacted configuration or recovery lifecycle from live SPIFFE/DID/wallet/chain trust-finality, dataplane, traffic, and production claims",
            "src/api/service_identity_status.py; src/self_healing/pqc_zero_trust_healer.py; src/self_healing/mape_k_spiffe_integration.py",
        )
    ]


def check_maas_telemetry_claim_gate_contract(root: Path) -> list[CheckResult]:
    maas_telemetry = _read(root, "src/api/maas_telemetry.py")
    required = {
        "claim_gate_boundary": (
            "_MAAS_TELEMETRY_CLAIM_GATE_BOUNDARY" in maas_telemetry
            and "does not prove fresh live agent connectivity" in maas_telemetry
            and "settlement finality" in maas_telemetry
        ),
        "claim_gate_helper": (
            "def _maas_telemetry_claim_gate" in maas_telemetry
            and "x0tta6bl4.maas_telemetry.claim_gate.v1" in maas_telemetry
        ),
        "eventbus_payload_gate": (
            '"maas_telemetry_claim_gate": _maas_telemetry_event_claim_gate('
            in maas_telemetry
            and 'surface=f"maas_telemetry.{operation}"' in maas_telemetry
        ),
        "readiness_gate": (
            '"maas_telemetry_claim_gate": _maas_telemetry_claim_gate('
            in maas_telemetry
            and 'surface="maas_telemetry.readiness"' in maas_telemetry
            and "settlement_uptime_ready=settlement_uptime_ready" in maas_telemetry
        ),
        "topology_node_evidence_gate": (
            'surface="maas_telemetry.topology_node_telemetry_evidence"'
            in maas_telemetry
        ),
        "topology_control_evidence_gate": (
            'surface="maas_telemetry.topology_control_policy_evidence"'
            in maas_telemetry
        ),
        "heartbeat_response_gate": (
            'surface="maas_telemetry.heartbeat_response"' in maas_telemetry
            and "local_heartbeat_processing=True" in maas_telemetry
        ),
        "local_observation_allowed": (
            '"local_telemetry_snapshot_observation_claim_allowed"'
            in maas_telemetry
            and '"local_uptime_sample_observation_claim_allowed"'
            in maas_telemetry
        ),
        "raw_values_redacted": (
            '"raw_identifiers_redacted": True' in maas_telemetry
            and '"raw_telemetry_values_redacted": True' in maas_telemetry
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in maas_telemetry
        ),
        "dataplane_delivery_false": (
            '"dataplane_delivery_claim_allowed": False' in maas_telemetry
        ),
        "traffic_delivery_false": (
            '"traffic_delivery_claim_allowed": False' in maas_telemetry
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in maas_telemetry
        ),
        "settlement_finality_false": (
            '"settlement_finality_claim_allowed": False' in maas_telemetry
            and '"external_settlement_finality_claim_allowed": False'
            in maas_telemetry
        ),
        "production_readiness_false": (
            '"production_readiness_claim_allowed": False' in maas_telemetry
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_telemetry_claim_gate_contract",
                "Missing MaaS telemetry claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas_telemetry.py",
            )
        ]
    return [
        pass_check(
            "maas_telemetry_claim_gate_contract",
            "MaaS telemetry readiness, EventBus, heartbeat, and topology evidence remain local-only and cannot imply dataplane, settlement, or production claims",
            "src/api/maas_telemetry.py",
        )
    ]


def check_mesh_api_claim_gate_contract(root: Path) -> list[CheckResult]:
    core_app = _read(root, "src/core/app.py")
    legacy_app = _read(root, "src/libx0t/core/app.py")

    required = {
        "core_mesh_claim_gate_helper": "def _mesh_api_claim_gate" in core_app,
        "core_mesh_cross_plane_gate": '"cross_plane_claim_gate"' in core_app
        and "cross_plane_claim_gate_metadata" in core_app,
        "core_mesh_dataplane_false": '"dataplane_delivery_claim_allowed": False' in core_app,
        "core_mesh_customer_traffic_false": '"customer_traffic_claim_allowed": False' in core_app,
        "core_mesh_dpi_false": '"external_dpi_bypass_claim_allowed": False' in core_app,
        "core_mesh_production_false": '"production_readiness_claim_allowed": False' in core_app,
        "legacy_mesh_claim_gate_helper": "def _mesh_api_claim_gate" in legacy_app,
        "legacy_mesh_cross_plane_gate": '"cross_plane_claim_gate"' in legacy_app
        and "cross_plane_claim_gate_metadata" in legacy_app,
        "legacy_mesh_dataplane_false": '"dataplane_delivery_claim_allowed": False' in legacy_app,
        "legacy_mesh_customer_traffic_false": '"customer_traffic_claim_allowed": False' in legacy_app,
        "legacy_mesh_dpi_false": '"external_dpi_bypass_claim_allowed": False' in legacy_app,
        "legacy_mesh_production_false": '"production_readiness_claim_allowed": False' in legacy_app,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "mesh_api_claim_gate_contract",
                "Missing mesh API claim-gate fragments: " + ", ".join(missing),
                "src/core/app.py; src/libx0t/core/app.py",
            )
        ]
    return [
        pass_check(
            "mesh_api_claim_gate_contract",
            "Mesh API Yggdrasil responses expose local observed-state only and attach fail-closed cross-plane claim gates",
            "src/core/app.py; src/libx0t/core/app.py",
        )
    ]


def check_status_api_claim_gate_contract(root: Path) -> list[CheckResult]:
    core_app = _read(root, "src/core/app.py")
    legacy_app = _read(root, "src/libx0t/core/app.py")

    required = {
        "core_status_claim_gate_helper": "def _status_api_claim_gate" in core_app,
        "core_status_response_helper": "def _status_api_response" in core_app,
        "core_status_cross_plane_gate": '"cross_plane_claim_gate"' in core_app
        and "cross_plane_claim_gate_metadata" in core_app,
        "core_status_production_false": '"production_readiness_claim_allowed": False' in core_app,
        "core_status_dataplane_false": '"dataplane_delivery_claim_allowed": False' in core_app,
        "core_status_dpi_false": '"external_dpi_bypass_claim_allowed": False' in core_app,
        "core_status_settlement_false": '"settlement_finality_claim_allowed": False' in core_app,
        "legacy_status_claim_gate_helper": "def _status_api_claim_gate" in legacy_app,
        "legacy_status_response_helper": "def _status_api_response" in legacy_app,
        "legacy_status_cross_plane_gate": '"cross_plane_claim_gate"' in legacy_app
        and "cross_plane_claim_gate_metadata" in legacy_app,
        "legacy_status_production_false": '"production_readiness_claim_allowed": False' in legacy_app,
        "legacy_status_dataplane_false": '"dataplane_delivery_claim_allowed": False' in legacy_app,
        "legacy_status_dpi_false": '"external_dpi_bypass_claim_allowed": False' in legacy_app,
        "legacy_status_settlement_false": '"settlement_finality_claim_allowed": False' in legacy_app,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "status_api_claim_gate_contract",
                "Missing status API claim-gate fragments: " + ", ".join(missing),
                "src/core/app.py; src/libx0t/core/app.py",
            )
        ]
    return [
        pass_check(
            "status_api_claim_gate_contract",
            "Status API local health responses attach fail-closed production/dataplane/DPI/settlement claim gates",
            "src/core/app.py; src/libx0t/core/app.py",
        )
    ]


def check_health_api_claim_gate_contract(root: Path) -> list[CheckResult]:
    core_app = _read(root, "src/core/app.py")
    legacy_app = _read(root, "src/libx0t/core/app.py")

    required = {
        "core_health_claim_gate_helper": "def _health_api_claim_gate" in core_app,
        "core_health_response_helper": "def _health_api_response" in core_app,
        "core_health_cross_plane_gate": '"cross_plane_claim_gate"' in core_app
        and "cross_plane_claim_gate_metadata" in core_app,
        "core_health_production_false": '"production_readiness_claim_allowed": False' in core_app,
        "core_health_dataplane_false": '"dataplane_delivery_claim_allowed": False' in core_app,
        "core_health_dpi_false": '"external_dpi_bypass_claim_allowed": False' in core_app,
        "core_health_settlement_false": '"settlement_finality_claim_allowed": False' in core_app,
        "legacy_health_claim_gate_helper": "def _health_api_claim_gate" in legacy_app,
        "legacy_health_response_helper": "def _health_api_response" in legacy_app,
        "legacy_health_cross_plane_gate": '"cross_plane_claim_gate"' in legacy_app
        and "cross_plane_claim_gate_metadata" in legacy_app,
        "legacy_health_production_false": '"production_readiness_claim_allowed": False' in legacy_app,
        "legacy_health_dataplane_false": '"dataplane_delivery_claim_allowed": False' in legacy_app,
        "legacy_health_dpi_false": '"external_dpi_bypass_claim_allowed": False' in legacy_app,
        "legacy_health_settlement_false": '"settlement_finality_claim_allowed": False' in legacy_app,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "health_api_claim_gate_contract",
                "Missing health API claim-gate fragments: " + ", ".join(missing),
                "src/core/app.py; src/libx0t/core/app.py",
            )
        ]
    return [
        pass_check(
            "health_api_claim_gate_contract",
            "Health/liveness/readiness API responses attach fail-closed production/dataplane/DPI/settlement claim gates",
            "src/core/app.py; src/libx0t/core/app.py",
        )
    ]


def check_metrics_api_claim_boundary_contract(root: Path) -> list[CheckResult]:
    core_app = _read(root, "src/core/app.py")
    legacy_app = _read(root, "src/libx0t/core/app.py")

    required = {
        "core_metrics_header_helper": (
            "def _metrics_api_claim_boundary_headers" in core_app
        ),
        "core_metrics_endpoint_uses_headers": (
            "headers=_metrics_api_claim_boundary_headers()" in core_app
        ),
        "core_metrics_schema_header": "X-X0TTA6BL4-Claim-Gate-Schema" in core_app,
        "core_metrics_local_observation_true": (
            '"X-X0TTA6BL4-Local-Metrics-Observation-Claim-Allowed": "true"'
            in core_app
        ),
        "core_metrics_production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"' in core_app
        ),
        "core_metrics_settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"' in core_app
        ),
        "legacy_metrics_header_helper": (
            "def _metrics_api_claim_boundary_headers" in legacy_app
        ),
        "legacy_metrics_endpoint_uses_headers": (
            "headers=_metrics_api_claim_boundary_headers()" in legacy_app
        ),
        "legacy_metrics_schema_header": "X-X0TTA6BL4-Claim-Gate-Schema" in legacy_app,
        "legacy_metrics_local_observation_true": (
            '"X-X0TTA6BL4-Local-Metrics-Observation-Claim-Allowed": "true"'
            in legacy_app
        ),
        "legacy_metrics_production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"'
            in legacy_app
        ),
        "legacy_metrics_slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"' in legacy_app
        ),
        "legacy_metrics_dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"' in legacy_app
        ),
        "legacy_metrics_traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"' in legacy_app
        ),
        "legacy_metrics_customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"' in legacy_app
        ),
        "legacy_metrics_dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"'
            in legacy_app
        ),
        "legacy_metrics_settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"'
            in legacy_app
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "metrics_api_claim_boundary_contract",
                "Missing metrics API claim-boundary fragments: " + ", ".join(missing),
                "src/core/app.py; src/libx0t/core/app.py",
            )
        ]
    return [
        pass_check(
            "metrics_api_claim_boundary_contract",
            "Metrics API keeps Prometheus output intact while exposing fail-closed production/dataplane/DPI/settlement claim-boundary headers",
            "src/core/app.py; src/libx0t/core/app.py",
        )
    ]


def check_maas_mesh_metrics_claim_gate_contract(root: Path) -> list[CheckResult]:
    mesh_endpoint = _read(root, "src/api/maas/endpoints/mesh.py")
    mesh_models = _read(root, "src/api/maas/models.py")
    legacy_maas = _read(root, "src/api/maas_legacy.py")

    required = {
        "mesh_metrics_model_claim_gate": "mesh_metrics_claim_gate" in mesh_models,
        "mesh_metrics_model_cross_plane_gate": "cross_plane_claim_gate" in mesh_models,
        "mesh_metrics_claim_gate_helper": "def _mesh_metrics_claim_gate" in mesh_endpoint,
        "mesh_metrics_cross_plane_helper": "cross_plane_claim_gate_metadata" in mesh_endpoint,
        "mesh_metrics_response_claim_gate": (
            "mesh_metrics_claim_gate=_mesh_metrics_claim_gate()" in mesh_endpoint
        ),
        "mesh_metrics_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata" in mesh_endpoint
        ),
        "mesh_metrics_local_observation_true": (
            '"local_mesh_metrics_observation_claim_allowed": True' in mesh_endpoint
        ),
        "mesh_metrics_control_policy_true": (
            '"local_control_policy_observation_claim_allowed": True' in mesh_endpoint
        ),
        "mesh_metrics_production_false": (
            '"production_readiness_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_slo_false": (
            '"production_slo_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_settlement_false": (
            '"settlement_finality_claim_allowed": False' in mesh_endpoint
        ),
        "mesh_metrics_summary_claim_gate": (
            '"mesh_metrics_claim_gate_present"' in mesh_endpoint
        ),
        "legacy_mesh_metrics_model_claim_gate": (
            "mesh_metrics_claim_gate" in legacy_maas
        ),
        "legacy_mesh_metrics_model_cross_plane_gate": (
            "cross_plane_claim_gate" in legacy_maas
        ),
        "legacy_mesh_metrics_claim_gate_helper": (
            "def _legacy_mesh_metrics_claim_gate" in legacy_maas
        ),
        "legacy_mesh_metrics_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in legacy_maas
        ),
        "legacy_mesh_metrics_response_claim_gate": (
            "mesh_metrics_claim_gate=_legacy_mesh_metrics_claim_gate()" in legacy_maas
        ),
        "legacy_mesh_metrics_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata" in legacy_maas
        ),
        "legacy_mesh_metrics_local_observation_true": (
            '"local_mesh_metrics_observation_claim_allowed": True' in legacy_maas
        ),
        "legacy_mesh_metrics_production_false": (
            '"production_readiness_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_slo_false": (
            '"production_slo_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_settlement_false": (
            '"settlement_finality_claim_allowed": False' in legacy_maas
        ),
        "legacy_mesh_metrics_summary_claim_gate": (
            '"mesh_metrics_claim_gate_present"' in legacy_maas
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_mesh_metrics_claim_gate_contract",
                "Missing MaaS mesh metrics claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/mesh.py; src/api/maas/models.py; src/api/maas_legacy.py",
            )
        ]
    return [
        pass_check(
            "maas_mesh_metrics_claim_gate_contract",
            "MaaS mesh metrics responses expose local metrics only and block production/dataplane/DPI/settlement promotion",
            "src/api/maas/endpoints/mesh.py; src/api/maas/models.py; src/api/maas_legacy.py",
        )
    ]


def check_maas_mesh_deploy_claim_gate_contract(root: Path) -> list[CheckResult]:
    mesh_endpoint = _read(root, "src/api/maas/endpoints/mesh.py")
    mesh_models = _read(root, "src/api/maas/models.py")

    required = {
        "mesh_deploy_model_claim_gate": "mesh_deploy_claim_gate" in mesh_models,
        "mesh_deploy_model_provisioner_claim_gate": (
            "mesh_provisioner_claim_gate" in mesh_models
        ),
        "mesh_deploy_model_provisioner_cross_plane_gate": (
            "provisioner_cross_plane_claim_gate" in mesh_models
        ),
        "mesh_deploy_model_cross_plane_gate": (
            "cross_plane_claim_gate" in mesh_models
        ),
        "mesh_deploy_claim_boundary": (
            "_MESH_DEPLOY_RESPONSE_CLAIM_BOUNDARY" in mesh_endpoint
        ),
        "mesh_deploy_cross_plane_claims": (
            "_MESH_DEPLOY_CROSS_PLANE_CLAIMS" in mesh_endpoint
        ),
        "mesh_deploy_claim_gate_helper": (
            "def _mesh_deploy_claim_gate" in mesh_endpoint
        ),
        "mesh_deploy_cross_plane_helper": (
            "def _mesh_deploy_cross_plane_gate" in mesh_endpoint
        ),
        "mesh_deploy_cross_plane_gate_metadata": (
            "cross_plane_claim_gate_metadata" in mesh_endpoint
        ),
        "provisioner_claim_gate_read": (
            'getattr(instance, "mesh_provisioner_claim_gate", None)'
            in mesh_endpoint
        ),
        "provisioner_cross_plane_gate_read": (
            'getattr(instance, "cross_plane_claim_gate", None)' in mesh_endpoint
        ),
        "response_mesh_deploy_claim_gate": (
            "mesh_deploy_claim_gate=_mesh_deploy_claim_gate(" in mesh_endpoint
        ),
        "response_provisioner_claim_gate": (
            "mesh_provisioner_claim_gate=provisioner_claim_gate" in mesh_endpoint
        ),
        "response_provisioner_cross_plane_gate": (
            "provisioner_cross_plane_claim_gate=provisioner_cross_plane_claim_gate"
            in mesh_endpoint
        ),
        "response_cross_plane_gate": (
            "cross_plane_claim_gate=_mesh_deploy_cross_plane_gate()"
            in mesh_endpoint
        ),
        "summary_mesh_deploy_claim_gate": (
            '"mesh_deploy_claim_gate_present"' in mesh_endpoint
        ),
        "summary_mesh_provisioner_claim_gate": (
            '"mesh_provisioner_claim_gate_present"' in mesh_endpoint
        ),
        "summary_cross_plane_claim_gate": (
            '"cross_plane_claim_gate_present"' in mesh_endpoint
        ),
        "local_api_deploy_true": (
            '"local_api_deploy_request_claim_allowed": bool(response_created)'
            in mesh_endpoint
        ),
        "local_provisioner_invocation_true": (
            '"local_mesh_provisioner_invocation_claim_allowed": bool('
            in mesh_endpoint
        ),
        "local_db_persistence_true": (
            '"local_db_persistence_claim_allowed": bool(db_write_committed)'
            in mesh_endpoint
        ),
        "external_infra_false": (
            '"external_infrastructure_provisioning_claim_allowed": False'
            in mesh_endpoint
        ),
        "external_node_deploy_false": (
            '"external_node_deployment_claim_allowed": False' in mesh_endpoint
        ),
        "node_join_false": (
            '"node_dataplane_join_claim_allowed": False' in mesh_endpoint
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in mesh_endpoint
        ),
        "routing_false": (
            '"routing_convergence_claim_allowed": False' in mesh_endpoint
        ),
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in mesh_endpoint
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in mesh_endpoint
        ),
        "settlement_false": (
            '"settlement_finality_claim_allowed": False' in mesh_endpoint
        ),
        "slo_false": '"production_slo_claim_allowed": False' in mesh_endpoint,
        "production_false": (
            '"production_readiness_claim_allowed": False' in mesh_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_mesh_deploy_claim_gate_contract",
                "Missing MaaS mesh deploy claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/mesh.py; src/api/maas/models.py",
            )
        ]
    return [
        pass_check(
            "maas_mesh_deploy_claim_gate_contract",
            "MaaS modular mesh deploy responses propagate provisioner gates and expose local API/DB lifecycle evidence only while blocking infrastructure/dataplane/traffic/DPI/settlement/production promotion",
            "src/api/maas/endpoints/mesh.py; src/api/maas/models.py",
        )
    ]


def check_maas_mesh_lifecycle_claim_gate_contract(root: Path) -> list[CheckResult]:
    mesh_endpoint = _read(root, "src/api/maas/endpoints/mesh.py")
    mesh_models = _read(root, "src/api/maas/models.py")

    required = {
        "mesh_status_model_lifecycle_claim_gate": (
            "mesh_lifecycle_claim_gate" in mesh_models
        ),
        "mesh_status_model_cross_plane_gate": (
            "cross_plane_claim_gate" in mesh_models
        ),
        "lifecycle_claim_boundary": (
            "_MESH_LIFECYCLE_RESPONSE_CLAIM_BOUNDARY" in mesh_endpoint
        ),
        "lifecycle_cross_plane_claims": (
            "_MESH_LIFECYCLE_CROSS_PLANE_CLAIMS" in mesh_endpoint
        ),
        "lifecycle_claim_gate_helper": (
            "def _mesh_lifecycle_claim_gate" in mesh_endpoint
        ),
        "lifecycle_cross_plane_helper": (
            "def _mesh_lifecycle_cross_plane_gate" in mesh_endpoint
        ),
        "attach_lifecycle_gate_helper": (
            "def _attach_mesh_lifecycle_gates" in mesh_endpoint
        ),
        "status_response_claim_gate": (
            "mesh_lifecycle_claim_gate=_mesh_lifecycle_claim_gate("
            in mesh_endpoint
        ),
        "status_response_cross_plane_gate": (
            "cross_plane_claim_gate=_mesh_lifecycle_cross_plane_gate"
            in mesh_endpoint
        ),
        "list_claim_surface": (
            'claim_surface="maas_mesh.list"' in mesh_endpoint
        ),
        "scale_attach_gate": (
            'surface="maas_mesh.scale"' in mesh_endpoint
            and "response = _attach_mesh_lifecycle_gates(" in mesh_endpoint
        ),
        "terminate_attach_gate": (
            'surface="maas_mesh.terminate"' in mesh_endpoint
            and "response = _attach_mesh_lifecycle_gates(" in mesh_endpoint
        ),
        "result_summary_claim_gate": (
            '"mesh_lifecycle_claim_gate_present"' in mesh_endpoint
        ),
        "list_summary_claim_gate_count": (
            '"mesh_lifecycle_claim_gate_count"' in mesh_endpoint
        ),
        "local_registry_read_true": (
            '"local_mesh_registry_read_claim_allowed": bool(read_only)'
            in mesh_endpoint
        ),
        "local_status_observation_true": (
            '"local_mesh_status_observation_claim_allowed": bool(read_only)'
            in mesh_endpoint
        ),
        "local_control_action_true": (
            '"local_mesh_control_action_claim_allowed": bool(control_action)'
            in mesh_endpoint
        ),
        "local_registry_mutation_true": (
            '"local_mesh_registry_mutation_claim_allowed": bool(' in mesh_endpoint
        ),
        "local_provisioner_invocation_true": (
            '"local_mesh_provisioner_invocation_claim_allowed": bool('
            in mesh_endpoint
        ),
        "external_infra_convergence_false": (
            '"external_infrastructure_convergence_claim_allowed": False'
            in mesh_endpoint
        ),
        "external_node_deploy_false": (
            '"external_node_deployment_claim_allowed": False' in mesh_endpoint
        ),
        "node_join_false": (
            '"node_dataplane_join_claim_allowed": False' in mesh_endpoint
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in mesh_endpoint
        ),
        "routing_false": (
            '"routing_convergence_claim_allowed": False' in mesh_endpoint
        ),
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in mesh_endpoint
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in mesh_endpoint
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in mesh_endpoint
        ),
        "settlement_false": (
            '"settlement_finality_claim_allowed": False' in mesh_endpoint
        ),
        "slo_false": '"production_slo_claim_allowed": False' in mesh_endpoint,
        "production_false": (
            '"production_readiness_claim_allowed": False' in mesh_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_mesh_lifecycle_claim_gate_contract",
                "Missing MaaS mesh lifecycle claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/mesh.py; src/api/maas/models.py",
            )
        ]
    return [
        pass_check(
            "maas_mesh_lifecycle_claim_gate_contract",
            "MaaS modular mesh list/status/scale/terminate responses expose local registry/status/control evidence only while blocking infrastructure/dataplane/traffic/DPI/settlement/production promotion",
            "src/api/maas/endpoints/mesh.py; src/api/maas/models.py",
        )
    ]


def check_maas_mesh_read_list_claim_boundary_contract(
    root: Path,
) -> list[CheckResult]:
    mesh_endpoint = _read(root, "src/api/maas/endpoints/mesh.py")

    required = {
        "read_list_claim_boundary": (
            "_MESH_READ_LIST_CLAIM_BOUNDARY" in mesh_endpoint
        ),
        "read_list_claim_headers": (
            "_MESH_READ_LIST_CLAIM_HEADERS" in mesh_endpoint
        ),
        "read_list_header_helper": (
            "def _mesh_read_list_claim_boundary_headers" in mesh_endpoint
        ),
        "read_list_set_headers_helper": (
            "def _set_mesh_read_list_claim_headers" in mesh_endpoint
        ),
        "read_list_summary_helper": (
            "def _mesh_read_list_claim_boundary_summary" in mesh_endpoint
        ),
        "audit_response_param": (
            "async def get_mesh_audit(" in mesh_endpoint
            and "http_response: Response = None" in mesh_endpoint
        ),
        "mapek_response_param": (
            "async def get_mesh_mapek(" in mesh_endpoint
            and "http_response: Response = None" in mesh_endpoint
        ),
        "audit_sets_headers": (
            '_set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.audit")'
            in mesh_endpoint
        ),
        "mapek_sets_headers": (
            '_set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.mapek")'
            in mesh_endpoint
        ),
        "audit_summary_surface": (
            'claim_surface="maas_mesh.audit"' in mesh_endpoint
        ),
        "mapek_summary_surface": (
            'claim_surface="maas_mesh.mapek"' in mesh_endpoint
        ),
        "summary_headers_present": (
            '"mesh_read_list_claim_boundary_headers_present": True'
            in mesh_endpoint
        ),
        "local_audit_true": (
            '"X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed": "true"'
            in mesh_endpoint
        ),
        "local_mapek_true": (
            '"X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed": "true"'
            in mesh_endpoint
        ),
        "autonomous_remediation_false": (
            '"X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "external_infra_false": (
            '"X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "restored_dataplane_false": (
            '"X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "node_reachability_false": (
            '"X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "routing_false": (
            '"X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
        "production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"'
            in mesh_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_mesh_read_list_claim_boundary_contract",
                "Missing MaaS mesh audit/MAPE-K read-list claim-boundary fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/mesh.py",
            )
        ]
    return [
        pass_check(
            "maas_mesh_read_list_claim_boundary_contract",
            "MaaS modular mesh audit and MAPE-K list responses keep list body shape while exposing HTTP claim-boundary headers and redacted EventBus summary flags",
            "src/api/maas/endpoints/mesh.py",
        )
    ]


def check_maas_compat_read_list_claim_boundary_contract(
    root: Path,
) -> list[CheckResult]:
    maas_compat = _read(root, "src/api/maas_compat.py")

    required = {
        "compat_read_list_headers": (
            "_COMPAT_READ_LIST_CLAIM_HEADERS" in maas_compat
        ),
        "compat_audit_claim_boundary": (
            "_COMPAT_AUDIT_READ_CLAIM_BOUNDARY" in maas_compat
        ),
        "compat_mapek_claim_boundary": (
            "_COMPAT_MAPEK_READ_CLAIM_BOUNDARY" in maas_compat
        ),
        "compat_header_helper": (
            "def _compat_read_list_claim_boundary_headers" in maas_compat
        ),
        "compat_set_headers_helper": (
            "def _set_compat_read_list_claim_headers" in maas_compat
        ),
        "compat_summary_helper": (
            "def _compat_read_list_claim_summary" in maas_compat
        ),
        "audit_alias_response_param": (
            "async def get_audit_logs_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "mapek_alias_response_param": (
            "async def get_mapek_events_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "audit_alias_sets_headers": (
            'surface="maas_compat.audit_logs"' in maas_compat
            and "claim_boundary=_COMPAT_AUDIT_READ_CLAIM_BOUNDARY" in maas_compat
            and "local_audit_log_claim_allowed=True" in maas_compat
        ),
        "mapek_alias_sets_headers": (
            'surface="maas_compat.mapek_events"' in maas_compat
            and "claim_boundary=_COMPAT_MAPEK_READ_CLAIM_BOUNDARY" in maas_compat
            and "local_mapek_event_claim_allowed=True" in maas_compat
        ),
        "summary_headers_present": (
            '"compat_read_list_claim_boundary_headers_present": True'
            in maas_compat
        ),
        "local_audit_true": (
            '"X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed"'
            in maas_compat
        ),
        "local_mapek_true": (
            '"X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed"'
            in maas_compat
        ),
        "autonomous_remediation_false": (
            '"X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false"'
            in maas_compat
        ),
        "durable_audit_false": (
            '"X-X0TTA6BL4-Durable-Audit-Persistence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "durable_event_false": (
            '"X-X0TTA6BL4-Durable-Event-Persistence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "historical_coverage_false": (
            '"X-X0TTA6BL4-Complete-Historical-Coverage-Claim-Allowed": "false"'
            in maas_compat
        ),
        "external_infra_false": (
            '"X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "restored_dataplane_false": (
            '"X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false"'
            in maas_compat
        ),
        "node_reachability_false": (
            '"X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false"'
            in maas_compat
        ),
        "routing_false": (
            '"X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"'
            in maas_compat
        ),
        "settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"'
            in maas_compat
        ),
        "slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"'
            in maas_compat
        ),
        "production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"'
            in maas_compat
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_compat_read_list_claim_boundary_contract",
                "Missing MaaS compat audit/MAPE-K read-list claim-boundary fragments: "
                + ", ".join(missing),
                "src/api/maas_compat.py",
            )
        ]
    return [
        pass_check(
            "maas_compat_read_list_claim_boundary_contract",
            "MaaS compatibility audit and MAPE-K aliases expose HTTP claim-boundary headers plus fail-closed EventBus summary flags",
            "src/api/maas_compat.py",
        )
    ]


def check_maas_compat_lifecycle_read_claim_boundary_contract(
    root: Path,
) -> list[CheckResult]:
    maas_compat = _read(root, "src/api/maas_compat.py")

    required = {
        "compat_lifecycle_read_headers": (
            "_COMPAT_LIFECYCLE_READ_CLAIM_HEADERS" in maas_compat
        ),
        "compat_lifecycle_claim_boundary": (
            "_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY" in maas_compat
        ),
        "compat_header_helper": (
            "def _compat_lifecycle_read_claim_boundary_headers" in maas_compat
        ),
        "compat_set_headers_helper": (
            "def _set_compat_lifecycle_read_claim_headers" in maas_compat
        ),
        "compat_summary_helper": (
            "def _compat_lifecycle_read_claim_summary" in maas_compat
        ),
        "list_alias_response_param": (
            "async def list_meshes_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "status_alias_response_param": (
            "async def get_mesh_status_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "metrics_alias_response_param": (
            "async def get_mesh_metrics_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "list_alias_sets_headers": (
            'surface="maas_compat.lifecycle.list"' in maas_compat
            and "claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY"
            in maas_compat
            and "local_lifecycle_state_claim_allowed=True" in maas_compat
        ),
        "status_alias_sets_headers": (
            'surface="maas_compat.lifecycle.status"' in maas_compat
            and "claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY"
            in maas_compat
        ),
        "metrics_alias_sets_headers": (
            'surface="maas_compat.lifecycle.metrics"' in maas_compat
            and "claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY"
            in maas_compat
        ),
        "list_body_shape_preserved": (
            'return {"meshes": meshes, "count": len(meshes)}' in maas_compat
        ),
        "summary_headers_present": (
            '"compat_lifecycle_read_claim_boundary_headers_present": True'
            in maas_compat
        ),
        "summary_local_lifecycle_true": (
            '"local_lifecycle_state_observation_claim_allowed"' in maas_compat
            and "local_lifecycle_state_claim_allowed=True" in maas_compat
        ),
        "summary_lifecycle_gate_present": (
            '"mesh_lifecycle_claim_gate_present"' in maas_compat
        ),
        "summary_metrics_gate_present": (
            '"mesh_metrics_claim_gate_present"' in maas_compat
        ),
        "summary_cross_plane_gate_present": (
            '"cross_plane_claim_gate_present"' in maas_compat
        ),
        "local_lifecycle_header": (
            '"X-X0TTA6BL4-Local-Lifecycle-State-Observation-Claim-Allowed"'
            in maas_compat
        ),
        "autonomous_remediation_false": (
            '"X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false"'
            in maas_compat
        ),
        "durable_lifecycle_false": (
            '"X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "external_infra_false": (
            '"X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "fresh_dataplane_false": (
            '"X-X0TTA6BL4-Fresh-Dataplane-Health-Claim-Allowed": "false"'
            in maas_compat
        ),
        "restored_dataplane_false": (
            '"X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false"'
            in maas_compat
        ),
        "node_reachability_false": (
            '"X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false"'
            in maas_compat
        ),
        "routing_false": (
            '"X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"'
            in maas_compat
        ),
        "settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"'
            in maas_compat
        ),
        "slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"'
            in maas_compat
        ),
        "production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"'
            in maas_compat
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_compat_lifecycle_read_claim_boundary_contract",
                "Missing MaaS compat lifecycle read claim-boundary fragments: "
                + ", ".join(missing),
                "src/api/maas_compat.py",
            )
        ]
    return [
        pass_check(
            "maas_compat_lifecycle_read_claim_boundary_contract",
            "MaaS compatibility list/status/metrics aliases preserve response bodies while exposing HTTP claim-boundary headers and redacted EventBus gate summary flags",
            "src/api/maas_compat.py",
        )
    ]


def check_maas_compat_lifecycle_control_claim_gate_contract(
    root: Path,
) -> list[CheckResult]:
    maas_compat = _read(root, "src/api/maas_compat.py")

    required = {
        "compat_lifecycle_control_headers": (
            "_COMPAT_LIFECYCLE_CONTROL_CLAIM_HEADERS" in maas_compat
        ),
        "scale_claim_boundary": "_COMPAT_SCALE_CLAIM_BOUNDARY" in maas_compat,
        "terminate_claim_boundary": (
            "_COMPAT_TERMINATE_CLAIM_BOUNDARY" in maas_compat
        ),
        "deploy_claim_boundary": "_COMPAT_DEPLOY_CLAIM_BOUNDARY" in maas_compat,
        "control_header_helper": (
            "def _compat_lifecycle_control_claim_boundary_headers"
            in maas_compat
        ),
        "control_set_headers_helper": (
            "def _set_compat_lifecycle_control_claim_headers" in maas_compat
        ),
        "control_claim_gate_helper": (
            "def _compat_lifecycle_control_claim_gate" in maas_compat
        ),
        "control_cross_plane_helper": (
            "def _compat_lifecycle_control_cross_plane_gate" in maas_compat
            and "cross_plane_claim_gate_metadata(" in maas_compat
        ),
        "scale_alias_response_param": (
            "async def scale_mesh_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "terminate_alias_response_param": (
            "async def terminate_mesh_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "deploy_alias_response_param": (
            "async def deploy_mesh_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
        ),
        "scale_surface": (
            'claim_surface = "maas_compat.lifecycle_control.scale"'
            in maas_compat
        ),
        "terminate_surface": (
            'claim_surface = "maas_compat.lifecycle_control.terminate"'
            in maas_compat
        ),
        "deploy_surface": (
            'claim_surface = "maas_compat.lifecycle_control.deploy"'
            in maas_compat
        ),
        "scale_headers_set": (
            "_set_compat_lifecycle_control_claim_headers(" in maas_compat
            and "claim_boundary=_COMPAT_SCALE_CLAIM_BOUNDARY" in maas_compat
            and "local_registry_mutation_claim_allowed=True" in maas_compat
        ),
        "terminate_headers_set": (
            "_set_compat_lifecycle_control_claim_headers(" in maas_compat
            and "claim_boundary=_COMPAT_TERMINATE_CLAIM_BOUNDARY" in maas_compat
            and "delegated_modular_lifecycle_claim_allowed=True" in maas_compat
        ),
        "deploy_headers_set": (
            "_set_compat_lifecycle_control_claim_headers(" in maas_compat
            and "claim_boundary=_COMPAT_DEPLOY_CLAIM_BOUNDARY" in maas_compat
            and "delegated_modular_lifecycle_claim_allowed=True" in maas_compat
        ),
        "scale_response_claim_gate": (
            '"compat_lifecycle_control_claim_gate": compat_lifecycle_control_claim_gate'
            in maas_compat
        ),
        "scale_response_cross_plane": (
            '"cross_plane_claim_gate": cross_plane_claim_gate' in maas_compat
        ),
        "terminate_response_claim_gate": (
            "result_payload.update(" in maas_compat
            and '"compat_lifecycle_control_claim_gate": (' in maas_compat
        ),
        "deploy_summary_modular_gate_presence": (
            '"mesh_deploy_claim_gate_present"' in maas_compat
            and '"mesh_provisioner_claim_gate_present"' in maas_compat
            and '"provisioner_cross_plane_claim_gate_present"' in maas_compat
        ),
        "deploy_summary_alias_gate_presence": (
            '"compat_lifecycle_control_claim_boundary_headers_present"'
            in maas_compat
            and '"claim_surface": "maas_compat.lifecycle_control.deploy"'
            in maas_compat
        ),
        "event_claim_gate_presence": (
            '"compat_lifecycle_control_claim_gate_present"' in maas_compat
        ),
        "event_cross_plane_presence": (
            '"cross_plane_claim_gate_present"' in maas_compat
        ),
        "local_registry_header": (
            '"X-X0TTA6BL4-Local-Registry-Mutation-Claim-Allowed"'
            in maas_compat
        ),
        "delegated_lifecycle_header": (
            '"X-X0TTA6BL4-Delegated-Modular-Lifecycle-Claim-Allowed"'
            in maas_compat
        ),
        "local_audit_append_header": (
            '"X-X0TTA6BL4-Local-Audit-Log-Append-Claim-Allowed"'
            in maas_compat
        ),
        "local_mapek_append_header": (
            '"X-X0TTA6BL4-Local-MAPE-K-Event-Append-Claim-Allowed"'
            in maas_compat
        ),
        "autonomous_remediation_false": (
            '"X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false"'
            in maas_compat
        ),
        "durable_lifecycle_false": (
            '"X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "external_infra_false": (
            '"X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "external_deploy_false": (
            '"X-X0TTA6BL4-External-Node-Deployment-Claim-Allowed": "false"'
            in maas_compat
        ),
        "external_shutdown_false": (
            '"X-X0TTA6BL4-External-Node-Shutdown-Claim-Allowed": "false"'
            in maas_compat
        ),
        "restored_dataplane_false": (
            '"X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false"'
            in maas_compat
        ),
        "node_reachability_false": (
            '"X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false"'
            in maas_compat
        ),
        "routing_false": (
            '"X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dataplane_false": (
            '"X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "traffic_false": (
            '"X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false"'
            in maas_compat
        ),
        "customer_traffic_false": (
            '"X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false"'
            in maas_compat
        ),
        "dpi_false": (
            '"X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false"'
            in maas_compat
        ),
        "settlement_false": (
            '"X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false"'
            in maas_compat
        ),
        "slo_false": (
            '"X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false"'
            in maas_compat
        ),
        "production_false": (
            '"X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false"'
            in maas_compat
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_compat_lifecycle_control_claim_gate_contract",
                "Missing MaaS compat lifecycle control claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas_compat.py",
            )
        ]
    return [
        pass_check(
            "maas_compat_lifecycle_control_claim_gate_contract",
            "MaaS compatibility deploy/scale/terminate aliases expose response or summary claim gates, HTTP claim-boundary headers, and EventBus gate presence while blocking infrastructure/dataplane/traffic/DPI/settlement/production promotion",
            "src/api/maas_compat.py",
        )
    ]


def check_maas_core_lifecycle_claim_gate_contract(root: Path) -> list[CheckResult]:
    maas_core = _read(root, "src/api/maas_core.py")

    required = {
        "lifecycle_claim_gate_helper": (
            "def _maas_core_lifecycle_claim_gate" in maas_core
        ),
        "lifecycle_header_helper": (
            "def _maas_core_lifecycle_claim_boundary_headers" in maas_core
        ),
        "lifecycle_headers_set": (
            "_set_maas_core_lifecycle_claim_headers(http_response)" in maas_core
        ),
        "lifecycle_model_claim_gate": (
            "maas_core_lifecycle_claim_gate: Dict[str, Any] = Field(default_factory=dict)"
            in maas_core
        ),
        "lifecycle_model_cross_plane_gate": (
            "cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)"
            in maas_core
        ),
        "lifecycle_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in maas_core
        ),
        "lifecycle_deploy_surface": '"maas_core.lifecycle.deploy"' in maas_core,
        "lifecycle_list_surface": '"maas_core.lifecycle.list"' in maas_core,
        "lifecycle_terminate_surface": (
            '"maas_core.lifecycle.terminate"' in maas_core
        ),
        "local_mesh_lifecycle_true": (
            '"local_mesh_lifecycle_claim_allowed": True' in maas_core
        ),
        "local_db_lifecycle_true": (
            '"local_db_lifecycle_claim_allowed": True' in maas_core
        ),
        "infrastructure_provisioning_false": (
            '"infrastructure_provisioning_claim_allowed": False' in maas_core
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in maas_core
        ),
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in maas_core
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in maas_core
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in maas_core
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in maas_core
        ),
        "settlement_false": (
            '"settlement_finality_claim_allowed": False' in maas_core
        ),
        "production_false": (
            '"production_readiness_claim_allowed": False' in maas_core
        ),
        "slo_false": '"production_slo_claim_allowed": False' in maas_core,
        "routing_false": (
            '"routing_convergence_claim_allowed": False' in maas_core
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_core_lifecycle_claim_gate_contract",
                "Missing MaaS core lifecycle claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas_core.py",
            )
        ]
    return [
        pass_check(
            "maas_core_lifecycle_claim_gate_contract",
            "MaaS core deploy/list/terminate responses expose local DB lifecycle only and block infrastructure/dataplane/DPI/settlement/production promotion",
            "src/api/maas_core.py",
        )
    ]


def check_maas_provisioning_setup_claim_gate_contract(root: Path) -> list[CheckResult]:
    provisioning = _read(root, "src/api/maas_provisioning.py")

    required = {
        "setup_claim_boundary": "PROVISIONING_CLAIM_BOUNDARY" in provisioning,
        "setup_claim_gate_helper": (
            "def _provisioning_setup_claim_gate" in provisioning
        ),
        "setup_header_helper": (
            "def _provisioning_setup_claim_boundary_headers" in provisioning
        ),
        "setup_headers_set": (
            "_set_provisioning_setup_claim_headers(http_response)" in provisioning
        ),
        "setup_model_claim_gate": (
            "provisioning_setup_claim_gate: Dict[str, Any] = Field(default_factory=dict)"
            in provisioning
        ),
        "setup_model_cross_plane_gate": (
            "cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)"
            in provisioning
        ),
        "setup_response_claim_gate": (
            "provisioning_setup_claim_gate=_provisioning_setup_claim_gate("
            in provisioning
        ),
        "setup_response_cross_plane_gate": (
            "cross_plane_claim_gate=_provisioning_setup_cross_plane_gate("
            in provisioning
        ),
        "setup_event_claim_gate": (
            '"provisioning_setup_claim_gate": _provisioning_setup_claim_gate('
            in provisioning
        ),
        "setup_cross_plane_helper": (
            "readiness_cross_plane_claim_gate_metadata" in provisioning
        ),
        "local_setup_true": (
            '"local_setup_package_generation_claim_allowed": True' in provisioning
        ),
        "local_join_token_true": (
            '"local_join_token_generation_claim_allowed": True' in provisioning
        ),
        "local_pending_db_bool": (
            '"local_pending_node_db_write_claim_allowed": bool(db_write_succeeded)'
            in provisioning
        ),
        "install_executed_false": (
            '"install_command_executed_claim_allowed": False' in provisioning
        ),
        "node_join_false": (
            '"node_dataplane_join_claim_allowed": False' in provisioning
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in provisioning
        ),
        "pqc_false": '"pqc_negotiation_claim_allowed": False' in provisioning,
        "zkp_false": '"zkp_authentication_claim_allowed": False' in provisioning,
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in provisioning
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in provisioning
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in provisioning
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in provisioning
        ),
        "production_false": (
            '"production_readiness_claim_allowed": False' in provisioning
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "maas_provisioning_setup_claim_gate_contract",
                "Missing MaaS provisioning setup claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas_provisioning.py",
            )
        ]
    return [
        pass_check(
            "maas_provisioning_setup_claim_gate_contract",
            "MaaS provisioning setup responses and events expose local pending-node/setup-package evidence only and block node-join/dataplane/PQC/ZKP/production promotion",
            "src/api/maas_provisioning.py",
        )
    ]


def check_mesh_provisioning_service_claim_gate_contract(root: Path) -> list[CheckResult]:
    provisioning_service = _read(root, "src/services/provisioning_service.py")

    required = {
        "service_claim_boundary": (
            "MESH_PROVISIONING_CLAIM_BOUNDARY" in provisioning_service
        ),
        "service_claim_gate_helper": (
            "def _mesh_provisioning_claim_gate" in provisioning_service
        ),
        "service_cross_plane_helper": (
            "def _mesh_provisioning_cross_plane_gate" in provisioning_service
        ),
        "service_cross_plane_gate_metadata": (
            "cross_plane_claim_gate_metadata" in provisioning_service
        ),
        "service_success_claim_gate": (
            '"mesh_provisioning_claim_gate": _mesh_provisioning_claim_gate('
            in provisioning_service
        ),
        "service_success_cross_plane_gate": (
            '"cross_plane_claim_gate": _mesh_provisioning_cross_plane_gate('
            in provisioning_service
        ),
        "local_delegate_bool": (
            '"local_mesh_provisioner_delegate_claim_allowed": bool('
            in provisioning_service
        ),
        "local_lifecycle_bool": (
            '"local_mesh_lifecycle_claim_allowed": bool(' in provisioning_service
        ),
        "provisioner_available_field": (
            '"mesh_provisioner_available": provisioner_available is True'
            in provisioning_service
        ),
        "provisioner_create_field": (
            '"mesh_provisioner_create_succeeded": provisioner_create_succeeded is True'
            in provisioning_service
        ),
        "external_infra_false": (
            '"external_infrastructure_provisioning_claim_allowed": False'
            in provisioning_service
        ),
        "node_join_false": (
            '"node_dataplane_join_claim_allowed": False' in provisioning_service
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in provisioning_service
        ),
        "routing_false": (
            '"routing_convergence_claim_allowed": False' in provisioning_service
        ),
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in provisioning_service
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in provisioning_service
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in provisioning_service
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in provisioning_service
        ),
        "settlement_false": (
            '"settlement_finality_claim_allowed": False' in provisioning_service
        ),
        "slo_false": (
            '"production_slo_claim_allowed": False' in provisioning_service
        ),
        "production_false": (
            '"production_readiness_claim_allowed": False' in provisioning_service
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "mesh_provisioning_service_claim_gate_contract",
                "Missing mesh provisioning service claim-gate fragments: "
                + ", ".join(missing),
                "src/services/provisioning_service.py",
            )
        ]
    return [
        pass_check(
            "mesh_provisioning_service_claim_gate_contract",
            "MaaS provisioning service provision_mesh results expose local delegate/lifecycle evidence only and block infrastructure/dataplane/traffic/DPI/settlement/production promotion",
            "src/services/provisioning_service.py",
        )
    ]


def check_mesh_provisioner_claim_gate_contract(root: Path) -> list[CheckResult]:
    maas_services = _read(root, "src/api/maas/services.py")

    required = {
        "provisioner_claim_boundary": (
            "MESH_PROVISIONER_CLAIM_BOUNDARY" in maas_services
        ),
        "provisioner_claim_gate_helper": (
            "def _mesh_provisioner_claim_gate" in maas_services
        ),
        "provisioner_cross_plane_helper": (
            "def _mesh_provisioner_cross_plane_gate" in maas_services
        ),
        "provisioner_cross_plane_gate_metadata": (
            "cross_plane_claim_gate_metadata" in maas_services
        ),
        "instance_claim_gate_attached": (
            "instance.mesh_provisioner_claim_gate = _mesh_provisioner_claim_gate("
            in maas_services
        ),
        "instance_cross_plane_attached": (
            "instance.cross_plane_claim_gate = _mesh_provisioner_cross_plane_gate("
            in maas_services
        ),
        "plan_limit_checked_field": '"plan_limit_checked": bool(' in maas_services,
        "mesh_instance_created_field": (
            '"mesh_instance_created": bool(mesh_instance_created)' in maas_services
        ),
        "local_node_records_field": (
            '"local_node_records_seeded": bool(local_node_records_seeded)'
            in maas_services
        ),
        "registry_mutation_field": (
            '"registry_mutation_committed": bool(registry_mutation_committed)'
            in maas_services
        ),
        "local_lifecycle_allowed": (
            '"local_mesh_instance_lifecycle_claim_allowed": bool(mesh_instance_created)'
            in maas_services
        ),
        "local_node_seed_allowed": (
            '"local_node_seed_claim_allowed": bool(local_node_records_seeded)'
            in maas_services
        ),
        "external_infra_false": (
            '"external_infrastructure_provisioning_claim_allowed": False'
            in maas_services
        ),
        "node_join_false": (
            '"node_dataplane_join_claim_allowed": False' in maas_services
        ),
        "node_reachability_false": (
            '"node_reachability_claim_allowed": False' in maas_services
        ),
        "routing_false": (
            '"routing_convergence_claim_allowed": False' in maas_services
        ),
        "dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in maas_services
        ),
        "traffic_false": (
            '"traffic_delivery_claim_allowed": False' in maas_services
        ),
        "customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in maas_services
        ),
        "dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in maas_services
        ),
        "settlement_false": (
            '"settlement_finality_claim_allowed": False' in maas_services
        ),
        "slo_false": '"production_slo_claim_allowed": False' in maas_services,
        "production_false": (
            '"production_readiness_claim_allowed": False' in maas_services
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "mesh_provisioner_claim_gate_contract",
                "Missing MeshProvisioner claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/services.py",
            )
        ]
    return [
        pass_check(
            "mesh_provisioner_claim_gate_contract",
            "MeshProvisioner.provision_mesh attaches local MeshInstance/node-seed/registry lifecycle evidence only and blocks infrastructure/dataplane/traffic/DPI/settlement/production promotion",
            "src/api/maas/services.py",
        )
    ]


def check_batman_metrics_claim_gate_contract(root: Path) -> list[CheckResult]:
    batman_endpoint = _read(root, "src/api/maas/endpoints/batman.py")

    required = {
        "batman_metrics_claim_gate_model": (
            "batman_metrics_claim_gate" in batman_endpoint
        ),
        "batman_metrics_cross_plane_model": (
            "cross_plane_claim_gate" in batman_endpoint
        ),
        "batman_metrics_claim_gate_helper": (
            "def _batman_metrics_claim_gate" in batman_endpoint
        ),
        "batman_metrics_header_helper": (
            "def _batman_metrics_claim_boundary_headers" in batman_endpoint
        ),
        "batman_metrics_prometheus_boundary_helper": (
            "def _batman_metrics_prometheus_claim_boundary" in batman_endpoint
        ),
        "batman_metrics_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_metrics_response_claim_gate": (
            "batman_metrics_claim_gate=_batman_metrics_claim_gate()" in batman_endpoint
        ),
        "batman_metrics_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_metrics_history_sets_headers": (
            "_set_batman_metrics_claim_headers(http_response)" in batman_endpoint
        ),
        "batman_metrics_prometheus_comments": (
            "x0tta6bl4_dataplane_delivery_claim_allowed false" in batman_endpoint
        ),
        "batman_metrics_local_observation_true": (
            '"local_batman_metrics_observation_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_metrics_production_false": (
            '"production_readiness_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_slo_false": (
            '"production_slo_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_settlement_false": (
            '"settlement_finality_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_kernel_forwarding_false": (
            '"kernel_forwarding_correctness_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_metrics_routing_convergence_false": (
            '"routing_convergence_claim_allowed": False' in batman_endpoint
        ),
        "batman_metrics_summary_claim_gate": (
            '"batman_metrics_claim_gate_present"' in batman_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "batman_metrics_claim_gate_contract",
                "Missing BATMAN metrics claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/batman.py",
            )
        ]
    return [
        pass_check(
            "batman_metrics_claim_gate_contract",
            "BATMAN metrics surfaces expose local observed-state only and block production/dataplane/DPI/settlement promotion",
            "src/api/maas/endpoints/batman.py",
        )
    ]


def check_batman_health_claim_gate_contract(root: Path) -> list[CheckResult]:
    batman_endpoint = _read(root, "src/api/maas/endpoints/batman.py")

    required = {
        "batman_health_claim_gate_model": (
            "batman_health_claim_gate" in batman_endpoint
        ),
        "batman_health_cross_plane_model": (
            "cross_plane_claim_gate" in batman_endpoint
        ),
        "batman_health_claim_gate_helper": (
            "def _batman_health_claim_gate" in batman_endpoint
        ),
        "batman_health_header_helper": (
            "def _batman_health_claim_boundary_headers" in batman_endpoint
        ),
        "batman_health_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_health_response_claim_gate": (
            "batman_health_claim_gate=_batman_health_claim_gate()" in batman_endpoint
        ),
        "batman_health_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_health_history_sets_headers": (
            "_set_batman_health_claim_headers(http_response)" in batman_endpoint
        ),
        "batman_health_local_observation_true": (
            '"local_batman_health_observation_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_health_production_false": (
            '"production_readiness_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_slo_false": (
            '"production_slo_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_settlement_false": (
            '"settlement_finality_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_physical_link_false": (
            '"physical_link_health_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_kernel_forwarding_false": (
            '"kernel_forwarding_correctness_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_health_routing_convergence_false": (
            '"routing_convergence_claim_allowed": False' in batman_endpoint
        ),
        "batman_health_summary_claim_gate": (
            '"batman_health_claim_gate_present"' in batman_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "batman_health_claim_gate_contract",
                "Missing BATMAN health claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/batman.py",
            )
        ]
    return [
        pass_check(
            "batman_health_claim_gate_contract",
            "BATMAN health surfaces expose local observed-state only and block production/dataplane/link-health promotion",
            "src/api/maas/endpoints/batman.py",
        )
    ]


def check_batman_topology_claim_gate_contract(root: Path) -> list[CheckResult]:
    batman_endpoint = _read(root, "src/api/maas/endpoints/batman.py")

    required = {
        "batman_topology_claim_gate_model": (
            "batman_topology_claim_gate" in batman_endpoint
        ),
        "batman_topology_cross_plane_model": (
            "cross_plane_claim_gate" in batman_endpoint
        ),
        "batman_topology_claim_gate_helper": (
            "def _batman_topology_claim_gate" in batman_endpoint
        ),
        "batman_topology_header_helper": (
            "def _batman_topology_claim_boundary_headers" in batman_endpoint
        ),
        "batman_topology_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_topology_response_claim_gate": (
            "batman_topology_claim_gate=_batman_topology_claim_gate("
            in batman_endpoint
        ),
        "batman_topology_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata"
            in batman_endpoint
        ),
        "batman_topology_sets_headers": (
            "_set_batman_topology_claim_headers(http_response)" in batman_endpoint
        ),
        "batman_topology_originators_surface": (
            'surface="maas_batman.originators"' in batman_endpoint
        ),
        "batman_topology_gateways_surface": (
            'surface="maas_batman.gateways"' in batman_endpoint
        ),
        "batman_topology_local_observation_true": (
            '"local_batman_topology_observation_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_topology_batctl_observation_true": (
            '"local_batctl_observation_claim_allowed": True' in batman_endpoint
        ),
        "batman_topology_production_false": (
            '"production_readiness_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_slo_false": (
            '"production_slo_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_settlement_false": (
            '"settlement_finality_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_physical_link_false": (
            '"physical_link_health_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_kernel_forwarding_false": (
            '"kernel_forwarding_correctness_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_topology_routing_convergence_false": (
            '"routing_convergence_claim_allowed": False' in batman_endpoint
        ),
        "batman_topology_summary_claim_gate": (
            '"batman_topology_claim_gate_present"' in batman_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "batman_topology_claim_gate_contract",
                "Missing BATMAN topology claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/batman.py",
            )
        ]
    return [
        pass_check(
            "batman_topology_claim_gate_contract",
            "BATMAN topology surfaces expose local observed-state only and block route/dataplane/production promotion",
            "src/api/maas/endpoints/batman.py",
        )
    ]


def check_batman_control_claim_gate_contract(root: Path) -> list[CheckResult]:
    batman_endpoint = _read(root, "src/api/maas/endpoints/batman.py")

    required = {
        "batman_control_claim_gate_model": (
            "batman_control_claim_gate" in batman_endpoint
        ),
        "batman_control_cross_plane_model": (
            "cross_plane_claim_gate" in batman_endpoint
        ),
        "batman_control_claim_gate_helper": (
            "def _batman_control_claim_gate" in batman_endpoint
        ),
        "batman_control_header_helper": (
            "def _batman_control_claim_boundary_headers" in batman_endpoint
        ),
        "batman_control_sets_headers": (
            "_set_batman_control_claim_headers(http_response)" in batman_endpoint
        ),
        "batman_control_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_control_response_claim_gate": (
            "batman_control_claim_gate=_batman_control_claim_gate("
            in batman_endpoint
        ),
        "batman_control_response_cross_plane_gate": (
            "cross_plane_claim_gate=cross_plane_claim_gate_metadata"
            in batman_endpoint
        ),
        "batman_control_mapek_status_surface": (
            'surface="maas_batman.mapek.status"' in batman_endpoint
        ),
        "batman_control_mapek_cycle_surface": (
            'surface="maas_batman.mapek.cycle"' in batman_endpoint
        ),
        "batman_control_mapek_start_surface": (
            'surface="maas_batman.mapek.start"' in batman_endpoint
        ),
        "batman_control_mapek_stop_surface": (
            'surface="maas_batman.mapek.stop"' in batman_endpoint
        ),
        "batman_control_healing_surface": (
            'surface="maas_batman.healing"' in batman_endpoint
        ),
        "batman_control_healing_actions_surface": (
            "maas_batman.healing.actions" in batman_endpoint
        ),
        "batman_control_local_mapek_true": (
            '"local_batman_mapek_control_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_control_local_healing_true": (
            '"local_batman_healing_control_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_control_autonomous_remediation_false": (
            '"autonomous_remediation_completion_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_control_route_mutation_false": (
            '"production_route_mutation_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_post_action_false": (
            '"post_action_dataplane_revalidated": False' in batman_endpoint
        ),
        "batman_control_restored_dataplane_false": (
            '"restored_dataplane_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_production_false": (
            '"production_readiness_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_slo_false": (
            '"production_slo_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_settlement_false": (
            '"settlement_finality_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_kernel_forwarding_false": (
            '"kernel_forwarding_correctness_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_control_routing_convergence_false": (
            '"routing_convergence_claim_allowed": False' in batman_endpoint
        ),
        "batman_control_summary_claim_gate": (
            '"batman_control_claim_gate_present"' in batman_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "batman_control_claim_gate_contract",
                "Missing BATMAN control claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/batman.py",
            )
        ]
    return [
        pass_check(
            "batman_control_claim_gate_contract",
            "BATMAN MAPE-K/healing surfaces expose local control outcomes only and block restored-dataplane/route/production promotion",
            "src/api/maas/endpoints/batman.py",
        )
    ]


def check_batman_mesh_status_claim_gate_contract(root: Path) -> list[CheckResult]:
    batman_endpoint = _read(root, "src/api/maas/endpoints/batman.py")

    required = {
        "batman_mesh_status_claim_gate_model": (
            "batman_mesh_status_claim_gate" in batman_endpoint
        ),
        "batman_mesh_status_cross_plane_model": (
            "cross_plane_claim_gate" in batman_endpoint
        ),
        "batman_mesh_status_claim_gate_helper": (
            "def _batman_mesh_status_claim_gate" in batman_endpoint
        ),
        "batman_mesh_status_header_helper": (
            "def _batman_mesh_status_claim_boundary_headers" in batman_endpoint
        ),
        "batman_mesh_status_sets_headers": (
            "_set_batman_mesh_status_claim_headers(http_response)"
            in batman_endpoint
        ),
        "batman_mesh_status_cross_plane_helper": (
            "cross_plane_claim_gate_metadata" in batman_endpoint
        ),
        "batman_mesh_status_response_claim_gate": (
            '"batman_mesh_status_claim_gate": _batman_mesh_status_claim_gate()'
            in batman_endpoint
        ),
        "batman_mesh_status_response_cross_plane_gate": (
            '"cross_plane_claim_gate": cross_plane_claim_gate_metadata'
            in batman_endpoint
        ),
        "batman_mesh_status_surface": (
            'surface="maas_batman.mesh.status"' in batman_endpoint
        ),
        "batman_mesh_status_local_observation_true": (
            '"local_batman_mesh_status_observation_claim_allowed": True'
            in batman_endpoint
        ),
        "batman_mesh_status_production_false": (
            '"production_readiness_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_slo_false": (
            '"production_slo_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_dataplane_false": (
            '"dataplane_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_traffic_false": (
            '"traffic_delivery_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_customer_traffic_false": (
            '"customer_traffic_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_dpi_false": (
            '"external_dpi_bypass_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_settlement_false": (
            '"settlement_finality_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_physical_link_false": (
            '"physical_link_health_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_kernel_forwarding_false": (
            '"kernel_forwarding_correctness_claim_allowed": False'
            in batman_endpoint
        ),
        "batman_mesh_status_routing_convergence_false": (
            '"routing_convergence_claim_allowed": False' in batman_endpoint
        ),
        "batman_mesh_status_summary_claim_gate": (
            '"batman_mesh_status_claim_gate_present"' in batman_endpoint
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "batman_mesh_status_claim_gate_contract",
                "Missing BATMAN mesh-status claim-gate fragments: "
                + ", ".join(missing),
                "src/api/maas/endpoints/batman.py",
            )
        ]
    return [
        pass_check(
            "batman_mesh_status_claim_gate_contract",
            "BATMAN mesh status surfaces expose local health aggregation only and block mesh/dataplane/production promotion",
            "src/api/maas/endpoints/batman.py",
        )
    ]


def check_economy_dataplane_claim_gate_contract(root: Path) -> list[CheckResult]:
    service_trace = _read(root, "src/services/service_event_trace.py")
    rag_search = _read(root, "src/ledger/rag_search.py")
    ledger_endpoints = _read(root, "src/api/ledger_endpoints.py")
    ledger_citation_smoke = _read(
        root,
        "scripts/ops/smoke_ledger_event_trace_citation.py",
    )
    billing_api = _read(root, "src/api/billing.py")
    maas_billing = _read(root, "src/api/maas_billing.py")
    maas_compat = _read(root, "src/api/maas_compat.py")
    reward_events = _read(root, "src/services/reward_events.py")
    marketplace_settlement = _read(root, "src/services/marketplace_settlement.py")
    marketplace_events = _read(root, "src/services/marketplace_events.py")
    marketplace_api = _read(root, "src/api/maas_marketplace.py")
    mesh_vpn_bridge = _read(root, "src/network/mesh_vpn_bridge.py")
    share_to_earn_service = _read(root, "src/services/share_to_earn_service.py")

    required = {
        "economy_finality_summary": "def economy_finality_summary" in service_trace,
        "economy_high_risk_gate": "def _economy_high_risk_claim_gate" in service_trace
        and '"high_risk_claim_gate"' in service_trace,
        "service_trace_claim_boundary_summary": "CLAIM_BOUNDARY_SUMMARY_LIMIT"
        in service_trace
        and "def _claim_boundary_summary" in service_trace
        and '"claim_boundary_summary"' in service_trace
        and '"claim_boundaries_truncated"' in service_trace
        and '"claim_boundaries_present"' in service_trace,
        "service_trace_upstream_claim_gate_summary": (
            "def _upstream_claim_gate_summary" in service_trace
            and "def _upstream_cross_plane_claim_gate_summary" in service_trace
            and '"claim_gate_summary": claim_gate_summary' in service_trace
            and '"cross_plane_claim_gate_summary": cross_plane_claim_gate_summary'
            in service_trace
            and '"upstream_claim_boundary_present"' in service_trace
            and '"upstream_claim_gate": {' in service_trace
            and '"upstream_cross_plane_claim_gate": {' in service_trace
        ),
        "rag_event_trace_claim_boundary_metadata": (
            "def _event_trace_claim_boundary_summary" in rag_search
            and "def _event_trace_upstream_claim_gate_summary" in rag_search
            and "def _event_trace_upstream_cross_plane_claim_gate_summary"
            in rag_search
            and '"claim_boundary_summary": claim_boundary_summary' in rag_search
            and '"upstream_claim_gate_summary": upstream_claim_gate_summary'
            in rag_search
            and '"upstream_cross_plane_claim_gate_summary": (' in rag_search
            and '"claim_boundary_summary": metadata["claim_boundary_summary"]'
            in rag_search
        ),
        "rag_external_dpi_intake_gap_citation_metadata": (
            "CLAIM_STATUS_EXTERNAL_DPI_GAP_RECORD" in rag_search
            and "def _external_dpi_intake_claim_gate_summary" in rag_search
            and "def _external_dpi_intake_metadata" in rag_search
            and '"external_dpi_intake_claim_gate_summary": summary' in rag_search
            and '"external_evidence_gap_record": gap_record' in rag_search
            and '"proof_gate_dpi_bypass_claim_allowed": False' in rag_search
            and '"production_readiness_claim_allowed": False' in rag_search
        ),
        "ledger_api_event_trace_claim_boundary_citations": (
            '"claim_boundary_summary": metadata.get("claim_boundary_summary")'
            in ledger_endpoints
            and '"upstream_claim_gate_summary": metadata.get(' in ledger_endpoints
            and '"upstream_cross_plane_claim_gate_summary": metadata.get('
            in ledger_endpoints
            and '"cross_plane_evidence_profile": metadata.get(' in ledger_endpoints
            and '"economy_finality_summary": metadata.get("economy_finality_summary")'
            in ledger_endpoints
        ),
        "ledger_api_external_dpi_intake_gap_citations": (
            '"external_dpi_intake_claim_gate_summary": metadata.get('
            in ledger_endpoints
            and '"external_evidence_gap_record": (' in ledger_endpoints
            and '"external_evidence_gap_record_not_proof"' in ledger_endpoints
            and '"external_dpi_intake_citation_not_proof"' in ledger_endpoints
            and '"external_dpi_proof_gate_not_allowed"' in ledger_endpoints
            and '"external_dpi_intake_citations"' in ledger_endpoints
            and '"external_evidence_gap_record_citations"' in ledger_endpoints
        ),
        "ledger_api_claim_sensitive_citation_usage_gate": (
            "def _citation_claim_usage_gate" in ledger_endpoints
            and "CLAIM_USAGE_GATE_BOUNDARY" in ledger_endpoints
            and '"claim_sensitive_citation_gate"' in ledger_endpoints
            and '"standalone_claim_proof_allowed": False' in ledger_endpoints
            and '"historical_claim_inventory_not_proof"' in ledger_endpoints
            and '"cross_plane_claim_gate_blocked"' in ledger_endpoints
            and '"upstream_claim_gate_local_only_not_proof"' in ledger_endpoints
            and '"upstream_cross_plane_claim_gate_blocked"' in ledger_endpoints
            and '"upstream_claim_gate_present"' in ledger_endpoints
            and '"upstream_cross_plane_claim_gate_present"' in ledger_endpoints
        ),
        "ledger_event_trace_citation_smoke_summary_assertions": (
            "citation_summary_metadata_present" in ledger_citation_smoke
            and "claim_boundary_summaries_bounded" in ledger_citation_smoke
            and "claim_boundaries_present_for_bounded_services"
            in ledger_citation_smoke
            and "cross_plane_summaries_fail_closed" in ledger_citation_smoke
            and "economy_summaries_fail_closed" in ledger_citation_smoke
            and "economy_services_have_local_only_gates" in ledger_citation_smoke
        ),
        "billing_api_claim_gate": "def _billing_api_claim_gate" in billing_api
        and '"customer_dataplane_delivery_claim_allowed": False' in billing_api
        and '"external_settlement_finality_claim_allowed": False' in billing_api,
        "billing_api_checkout_response_claim_gate": (
            "def _billing_api_checkout_response_claim_metadata" in billing_api
            and '"claim_gate": _billing_api_claim_gate' in billing_api
            and '"cross_plane_claim_gate": cross_plane_claim_gate_metadata' in billing_api
            and 'surface="billing_api.checkout_session"' in billing_api
        ),
        "billing_api_order_status_response_claim_gate": (
            "def _billing_api_order_status_response_claim_metadata" in billing_api
            and 'surface="billing_api.order_status"' in billing_api
            and '"vless_link": link' in billing_api
            and "_billing_api_order_status_response_claim_metadata(" in billing_api
        ),
        "billing_api_local_observation_response_claim_gate": (
            "def _billing_api_local_observation_response_claim_metadata" in billing_api
            and 'surface="billing_api.config"' in billing_api
            and 'surface="billing_api.revenue_metrics"' in billing_api
            and "_billing_api_local_observation_response_claim_metadata(" in billing_api
        ),
        "billing_api_webhook_response_claim_gate": (
            "def _billing_api_webhook_response_claim_metadata" in billing_api
            and 'surface="billing_api.webhook"' in billing_api
            and '"received": True' in billing_api
            and "_billing_api_webhook_response_claim_metadata(" in billing_api
        ),
        "maas_billing_claim_gate": "def _billing_local_claim_gate" in maas_billing
        and "claim_gate: dict[str, Any] = Field(default_factory=dict)" in maas_billing,
        "maas_billing_intent_response_claim_gate": (
            "def _billing_intent_response_claim_metadata" in maas_billing
            and '"claim_gate": _billing_local_claim_gate' in maas_billing
            and '"cross_plane_claim_gate": cross_plane_claim_gate_metadata' in maas_billing
            and 'surface="maas_billing.subscription_checkout"' in maas_billing
            and 'surface="maas_billing.customer_portal"' in maas_billing
            and 'surface="maas_billing.invoice_checkout"' in maas_billing
        ),
        "compat_billing_pay_claim_headers": "_COMPAT_BILLING_PAY_CLAIM_HEADERS"
        in maas_compat
        and "def _set_compat_billing_pay_claim_headers" in maas_compat,
        "compat_billing_pay_claim_gate": "def _compat_billing_pay_claim_gate"
        in maas_compat
        and '"provider_settlement_claim_allowed": False' in maas_compat
        and '"bank_settlement_claim_allowed": False' in maas_compat
        and '"external_settlement_finality_claim_allowed": False' in maas_compat
        and '"subscription_activation_claim_allowed": False' in maas_compat
        and '"customer_access_claim_allowed": False' in maas_compat
        and '"dataplane_delivery_claim_allowed": False' in maas_compat
        and '"traffic_delivery_claim_allowed": False' in maas_compat
        and '"customer_traffic_claim_allowed": False' in maas_compat
        and '"production_readiness_claim_allowed": False' in maas_compat,
        "compat_billing_pay_cross_plane_gate": (
            "def _compat_billing_pay_cross_plane_gate" in maas_compat
            and "cross_plane_claim_gate_metadata(" in maas_compat
        ),
        "compat_billing_pay_alias_response_gate": (
            "async def billing_pay_alias(" in maas_compat
            and "http_response: Response = None" in maas_compat
            and 'claim_surface = "maas_compat.billing_pay"' in maas_compat
            and '"compat_billing_pay_claim_gate": compat_billing_pay_claim_gate'
            in maas_compat
            and '"cross_plane_claim_gate": cross_plane_claim_gate' in maas_compat
        ),
        "compat_billing_pay_summary_gate": (
            '"compat_billing_pay_claim_gate_present"' in maas_compat
            and '"cross_plane_claim_gate_present"' in maas_compat
            and '"claim_surface"' in maas_compat
        ),
        "reward_claim_gate": "def _reward_claim_gate" in reward_events
        and '"reward_claim_gate"' in reward_events
        and '"token_settlement_finality_claim_allowed": False' in reward_events,
        "reward_upstream_claim_gate_summary": (
            "def _safe_claim_gate_summary" in reward_events
            and "def _safe_cross_plane_claim_gate_summary" in reward_events
            and '"claim_gate_summary": _safe_claim_gate_summary' in reward_events
            and '"cross_plane_claim_gate_summary": _safe_cross_plane_claim_gate_summary' in reward_events
            and "upstream_claim_gate" in reward_events
            and "upstream_cross_plane_claim_gate" in reward_events
        ),
        "share_to_earn_upstream_claim_gate_passthrough": (
            "_UPSTREAM_CLAIM_GATE_KEYS" in share_to_earn_service
            and "_UPSTREAM_CROSS_PLANE_CLAIM_GATE_KEYS" in share_to_earn_service
            and '"claim_gate_present": mesh_upstream_evidence["claim_gate_present"]'
            in share_to_earn_service
            and '"cross_plane_claim_gate_present": (' in share_to_earn_service
            and "upstream_claim_gate=mesh_upstream_evidence" in share_to_earn_service
            and "upstream_cross_plane_claim_gate=mesh_upstream_evidence"
            in share_to_earn_service
        ),
        "marketplace_settlement_claim_gate": '"claim_gate"' in marketplace_settlement
        and '"requires_external_finality_evidence_for_settlement_claim": True'
        in marketplace_settlement
        and '"traffic_delivery_claim_allowed": False' in marketplace_settlement
        and '"dataplane_delivery_claim_allowed": False' in marketplace_settlement
        and '"external_settlement_finality_claim_allowed": False'
        in marketplace_settlement
        and '"production_readiness_claim_allowed": False'
        in marketplace_settlement
        and '"requires_cross_plane_proof_gate_for_high_risk_claims": True'
        in marketplace_settlement
        and '"upstream_high_risk_claims_present"' in marketplace_settlement
        and '"blocker_reason_ids": list(' in marketplace_settlement
        and "This worker never promotes high-risk " in marketplace_settlement
        and "claims; those must be evaluated by separate cross-plane proof gates."
        in marketplace_settlement,
        "marketplace_event_sanitizes_claim_gate": "def _claim_gate_evidence" in marketplace_events
        and '"production_readiness_claim_allowed"' in marketplace_events,
        "marketplace_listing_claim_gate": "def _marketplace_listing_claim_gate" in marketplace_api
        and "listing_claim_gate" in marketplace_api,
        "mesh_vpn_relay_reward_claim_gate": "def _relay_reward_claim_gate" in mesh_vpn_bridge
        and '"relay_reward_claim_gate"' in mesh_vpn_bridge,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "economy_dataplane_claim_gate_contract",
                "Missing economy/dataplane claim-gate fragments: " + ", ".join(missing),
                "billing/reward/marketplace/relay static file scan",
            )
        ]
    return [
        pass_check(
            "economy_dataplane_claim_gate_contract",
            "Economy, reward, marketplace, billing config/checkout/order-status/revenue/webhook responses, compat billing, relay, service trace, RAG, Ledger API, and Ledger citation smoke evidence keep settlement/dataplane claims behind explicit gates and redacted upstream gate summaries",
            "billing/reward/share-to-earn/marketplace/compat/relay/service-trace/rag/ledger-api/smoke static file scan",
        )
    ]


def check_cross_plane_proof_gate_contract(root: Path) -> list[CheckResult]:
    gate = _read(root, "scripts/ops/run_cross_plane_proof_gate.py")
    external_settlement = _read(root, "src/integration/external_settlement.py")
    required = {
        "cross_plane_schema": 'SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"' in gate,
        "claim_requirements": "CLAIM_REQUIREMENTS" in gate,
        "production_readiness_claim": '"production_readiness"' in gate,
        "dataplane_delivery_claim": '"dataplane_delivery"' in gate,
        "dpi_bypass_claim": '"dpi_bypass"' in gate,
        "settlement_finality_claim": '"settlement_finality"' in gate,
        "dynamic_imports_keep_repo_root_importable": (
            "def load_script_module" in gate
            and "module_roots" in gate
            and "sys.path.insert" in gate
            and "ROOT" in gate
        ),
        "current_gap_blocker": "current_evidence_open_gaps" in gate,
        "blocking_false_flags": "blocking_false_flags" in gate,
        "writes_validation_shard": (
            "DEFAULT_OUTPUT_JSON" in gate
            and ".tmp/validation-shards/cross-plane-proof-gate-current.json" in gate
            and "def atomic_write_json" in gate
            and "--output-json" in gate
            and "atomic_write_json(resolve_path(args.root, args.output_json), report)" in gate
        ),
        "source_artifact_identity_metadata": (
            "def source_artifact_identity" in gate
            and "current_cross_plane_evidence_map" in gate
            and "current_active_goal_gap_audit" in gate
            and '"source_artifacts": [map_identity, audit_identity]' in gate
            and '"source_artifact_hashes_present"' in gate
            and '"map_sha256": map_identity["sha256"]' in gate
            and '"audit_sha256": audit_identity["sha256"]' in gate
            and "it does not prove that the underlying external-world claim is true" in gate
        ),
        "dataplane_delivery_eventbus_artifact_evidence": (
            "def dataplane_delivery_artifact_evidence" in gate
            and "DATAPLANE_DELIVERY_CLAIM_ID" in gate
            and "EVENTBUS_LOG" in gate
        ),
        "dataplane_delivery_eventbus_artifact_blocker": (
            "dataplane_delivery_eventbus_artifact_not_verified" in gate
        ),
        "dataplane_delivery_eventbus_artifact_uses_probe_gate": (
            "post_action_dataplane_revalidated" in gate
            and "restored_dataplane_claim_allowed" in gate
            and "bounded_dataplane_probe_not_attempted" in gate
            and "dataplane_evidence_not_redacted" in gate
            and "restored_dataplane_claim_gate_missing" in gate
            and "restored_dataplane_claim_gate_not_redacted" in gate
            and "restored_dataplane_claim_gate_probe_not_observed" in gate
            and "restored_dataplane_claim_gate_dataplane_not_observed" in gate
            and '"candidate_blockers": []' in gate
        ),
        "dpi_imported_artifact_evidence": "def dpi_lab_artifact_evidence" in gate,
        "dpi_artifact_required_for_claim": '"required_for_claim": "dpi_bypass"' in gate,
        "dpi_artifact_blocker": "dpi_lab_imported_artifact_not_verified" in gate,
        "dpi_uses_ghost_pulse_validation": "validate_external_evidence(root, requirement)" in gate,
        "dpi_uses_external_validator": (
            "external_dpi_proxy_validation" in gate
            and "validator.validate_payload(contract, payload)" in gate
            and "validator.source_artifact_errors(root, payload)" in gate
        ),
        "dpi_requires_fresh_import_bundle": (
            "def dpi_lab_import_freshness_evidence" in gate
            and "ghost-pulse-external-evidence-import-*" in gate
            and "import-report.json" in gate
            and "write_freshness_claim_allowed" in gate
            and "local_latest_evidence_copy_claim_allowed" in gate
            and "dpi_lab_import_freshness_not_verified" in gate
            and "verified_dpi_lab_fresh_import_report_not_found" in gate
        ),
        "dpi_intake_context_surfaces_replacement_state": (
            "def dpi_lab_intake_context" in gate
            and "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST" in gate
            and "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST" in gate
            and "ready_to_import" in gate
            and "ready_for_write_import" in gate
            and "candidate_is_symlink" in gate
            and "failures_capped" in gate
            and "command_shapes" in gate
            and "collector_local_input_placeholders_present" in gate
            and "DPI intake context is diagnostic" in gate
        ),
        "production_readiness_imported_artifact_evidence": (
            "def production_readiness_artifact_evidence" in gate
            and "PRODUCTION_READINESS_CLAIM_ID" in gate
        ),
        "production_readiness_artifact_blocker": (
            "production_readiness_imported_artifact_not_verified" in gate
        ),
        "production_readiness_uses_ghost_pulse_validation": (
            "production_readiness_proof_gate_validation_not_verified" in gate
            and "validate_external_evidence(root, requirement)" in gate
        ),
        "external_settlement_imported_artifact_evidence": (
            "def external_settlement_artifact_evidence" in gate
            and "EXTERNAL_SETTLEMENT_CLAIM_ID" in gate
        ),
        "external_settlement_artifact_blocker": (
            "external_settlement_artifact_not_verified" in gate
        ),
        "external_settlement_uses_external_settlement_validator": (
            "settlement.validate_evidence_file(evidence_path" in gate
            and "DEFAULT_RPC_REPORT" in gate
            and "DEFAULT_BLOCKER_REPORT" in gate
            and "source_artifacts" in gate
            and "DEFAULT_EVIDENCE_REPORT" in gate
            and "READY_TO_PROMOTE" in gate
        ),
        "external_settlement_redacts_rpc_endpoint": (
            "def _redact_external_settlement_live_rpc_report" in gate
            and "rpc_endpoint_redacted" in gate
            and "rpc_endpoint_hash" in gate
            and "def _redacted_rpc_endpoint_metadata" in external_settlement
            and "rpc_endpoint_redacted" in external_settlement
            and "rpc_endpoint_hash" in external_settlement
            and '"rpc_endpoint": None' in external_settlement
        ),
        "external_settlement_operator_handoff_context": (
            "EXTERNAL_SETTLEMENT_HANDOFF_MODULE" in gate
            and "def external_settlement_operator_handoff_context" in gate
            and "ready_for_completion_rerun" in gate
            and "missing_inputs" in gate
            and "source_reports" in gate
            and "operator_sequence_ready" in gate
            and "operator_handoff" in gate
        ),
        "economy_boundary_event_artifact_evidence": (
            "def economy_boundary_artifact_evidence" in gate
            and "ECONOMY_BOUNDARY_CLAIM_ID" in gate
            and "SERVICE_EVENT_TRACE_MODULE" in gate
            and "EVENTBUS_LOG" in gate
        ),
        "economy_boundary_uses_source_prefiltered_retention_scan": (
            "ECONOMY_BOUNDARY_SOURCE_AGENTS" in gate
            and "ECONOMY_BOUNDARY_CANDIDATE_SCAN_LIMIT" in gate
            and "def _source_filtered_event_log_entries" in gate
            and "source_agent_prefiltered_reverse_scan" in gate
            and "candidate_events_scanned_limit" in gate
            and "event_log_lines_seen" in gate
        ),
        "economy_boundary_event_artifact_blocker": (
            "economy_boundary_artifact_not_verified" in gate
        ),
        "economy_boundary_uses_high_risk_claim_gate": (
            "economy_finality_summary" in gate
            and "high_risk_claim_gate" in gate
            and "required_for_high_risk_claims" in gate
            and "external_settlement_finality_missing" in gate
            and "economy_event_redaction_metadata_missing" in gate
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "cross_plane_proof_gate_contract",
                "Missing cross-plane proof gate fragments: " + ", ".join(missing),
                "scripts/ops/run_cross_plane_proof_gate.py",
            )
        ]
    return [
        pass_check(
            "cross_plane_proof_gate_contract",
            "Cross-plane proof gate can fail-close strong production/dataplane/DPI/settlement claims, write its canonical validation shard, identify current map/audit source artifacts by hash, keep dynamic repo imports working in CLI mode, require nested dataplane claim-gate evidence, require fresh dpi_lab import provenance, surface bounded DPI replacement/intake context, redact external settlement RPC endpoint metadata, surface bounded external-settlement operator handoff context, and require retained economy-boundary evidence with source-prefiltered EventBus retention scan for settlement/production promotion",
            "scripts/ops/run_cross_plane_proof_gate.py",
        )
    ]


def check_production_system_cross_plane_gate_contract(root: Path) -> list[CheckResult]:
    paths = (
        "src/core/production_system.py",
        "src/libx0t/core/production_system.py",
    )
    missing_by_path: dict[str, list[str]] = {}
    for path in paths:
        source = _read(root, path)
        required = {
            "imports_readiness_cross_plane_gate": (
                "readiness_cross_plane_claim_gate_metadata" in source
            ),
            "declares_requested_claims": (
                "PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS" in source
                and '"production_readiness"' in source
                and '"dataplane_delivery"' in source
                and '"settlement_finality"' in source
                and '"dpi_bypass"' in source
            ),
            "builds_cross_plane_proof_gate_context": (
                "def _cross_plane_proof_gate_context" in source
                and "cross_plane_proof_gate_unavailable" in source
                and "cross_plane_proof_gate_error:" in source
                and "cross_plane_proof_gate_invalid_response" in source
            ),
            "requires_gate_for_claim": (
                "cross_plane_proof_gate.get(\"allowed\") is True" in source
                and (
                    "production_claim_allowed = (" in source
                    or "production_readiness_claim_allowed = (" in source
                )
                and (
                    '"production_readiness_claim_allowed": production_claim_allowed'
                    in source
                    or '"production_readiness_claim_allowed": (' in source
                )
            ),
            "reports_gate_metadata": (
                '"cross_plane_proof_gate": cross_plane_proof_gate' in source
            ),
            "blocks_ready_level_when_gate_blocks": (
                "PRODUCTION_READY_BLOCKED_BY_CROSS_PLANE_PROOF_GATE" in source
            ),
            "claim_boundary_mentions_proof_gate": (
                "cross-plane proof gate allows the requested strong claims" in source
            ),
        }
        missing = [name for name, ok in required.items() if not ok]
        if missing:
            missing_by_path[path] = missing

    if missing_by_path:
        details = "; ".join(
            f"{path}: {', '.join(missing)}"
            for path, missing in sorted(missing_by_path.items())
        )
        return [
            fail_check(
                "production_system_cross_plane_gate_contract",
                "Missing ProductionSystem cross-plane proof-gate fragments: "
                + details,
                ", ".join(paths),
            )
        ]
    return [
        pass_check(
            "production_system_cross_plane_gate_contract",
            "ProductionSystem readiness requires current evidence plus the reusable cross-plane proof gate before allowing production-readiness promotion",
            ", ".join(paths),
        )
    ]


def check_phase6_production_readiness_context_gate_contract(root: Path) -> list[CheckResult]:
    readiness = _read(root, "tests/integration/production_readiness.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in readiness,
        "current_evidence_gate_helper": "def _current_evidence_gate_clear" in readiness,
        "declares_cross_plane_proof_gate_artifact": (
            "CROSS_PLANE_PROOF_GATE" in readiness
            and ".tmp/validation-shards/cross-plane-proof-gate-current.json" in readiness
            and "PRODUCTION_READINESS_CHECKLIST_CROSS_PLANE_CLAIMS" in readiness
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in readiness
            and "def _cross_plane_proof_gate_allowed" in readiness
            and "def _cross_plane_proof_gate_blocker_ids" in readiness
            and "source_artifact_hashes_present" in readiness
        ),
        "production_ready_requires_proof_gate": (
            "is_ready = raw_checklist_ready and current_evidence_clear and cross_plane_proof_gate_clear"
            in readiness
        ),
        "current_evidence_report_fields": (
            '"current_evidence_gate_clear": current_evidence_clear' in readiness
            and '"current_evidence_context": current_evidence' in readiness
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate_clear": cross_plane_proof_gate_clear' in readiness
            and '"cross_plane_proof_gate": cross_plane_proof_gate' in readiness
            and '"cross_plane_proof_gate_required": True' in readiness
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_clear'
            in readiness
        ),
        "raw_checklist_separated": '"raw_checklist_ready": raw_checklist_ready' in readiness,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in readiness
            and '"production_readiness_claim_allowed": is_ready' in readiness
            and '"proof_claims": {' in readiness
            and '"production_ready": False' in readiness
            and '"live_apply_authorized": False' in readiness
            and '"goal_completion_authorized": False' in readiness
        ),
        "claim_boundary_mentions_proof_gate": (
            "reusable cross-plane proof gate allows the requested strong claims" in readiness
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "phase6_production_readiness_context_gate_contract",
                "Missing Phase 6 production-readiness checklist gate fragments: "
                + ", ".join(missing),
                "tests/integration/production_readiness.py",
            )
        ]
    return [
        pass_check(
            "phase6_production_readiness_context_gate_contract",
            "Phase 6 production-readiness checklist separates raw local checklist state from production readiness and requires current evidence context plus the reusable cross-plane proof gate",
            "tests/integration/production_readiness.py",
        )
    ]


def check_production_grade_audit_cross_plane_gate_contract(root: Path) -> list[CheckResult]:
    source = _read(root, "scripts/ops/audit_production_grade_goal.py")
    required = {
        "imports_cross_plane_proof_gate": (
            "build_cross_plane_proof_gate_report" in source
        ),
        "declares_requested_claims": (
            "PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS" in source
            and '"production_readiness"' in source
            and '"dataplane_delivery"' in source
            and '"settlement_finality"' in source
            and '"dpi_bypass"' in source
        ),
        "builds_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in source
            and "cross_plane_proof_gate_unavailable" in source
            and "cross_plane_proof_gate_error:" in source
            and "cross_plane_proof_gate_invalid_response" in source
        ),
        "extracts_proof_gate_blockers": (
            "def _cross_plane_proof_gate_blocker_ids" in source
            and "claim_blocked:" in source
        ),
        "complete_requires_proof_gate": (
            "cross_plane_proof_gate_clear = cross_plane_proof_gate.get(\"allowed\") is True"
            in source
            and "complete = requirements_complete and current_evidence_clear and cross_plane_proof_gate_clear"
            in source
        ),
        "reports_proof_gate_metadata": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in source
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_clear'
            in source
        ),
        "adds_proof_gate_next_action": (
            "clear_cross_plane_proof_gate" in source
            and "cross_plane_proof_gate_action_required" in source
        ),
        "claim_boundary_mentions_proof_gate": (
            "reusable cross-plane proof gate" in source
        ),
        "guards_current_evidence_outputs": (
            "PROTECTED_CURRENT_EVIDENCE_OUTPUTS" in source
            and "_guard_output_path(root, args.output_json" in source
            and "_guard_output_path(root, args.output_md" in source
            and "must not overwrite current evidence source artifact" in source
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "production_grade_audit_cross_plane_gate_contract",
                "Missing production-grade audit proof-gate fragments: "
                + ", ".join(missing),
                "scripts/ops/audit_production_grade_goal.py",
            )
        ]
    return [
        pass_check(
            "production_grade_audit_cross_plane_gate_contract",
            "Production-grade audit requires current evidence plus the reusable cross-plane proof gate before returning COMPLETE",
            "scripts/ops/audit_production_grade_goal.py",
        )
    ]


def check_objective_coverage_cross_plane_gate_contract(root: Path) -> list[CheckResult]:
    source = _read(root, "src/integration/objective_coverage_audit.py")
    required = {
        "declares_proof_gate_artifact": (
            "DEFAULT_CROSS_PLANE_PROOF_GATE" in source
            and ".tmp/validation-shards/cross-plane-proof-gate-current.json" in source
        ),
        "declares_requested_claims": (
            "OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS" in source
            and '"production_readiness"' in source
            and '"dataplane_delivery"' in source
            and '"traffic_delivery"' in source
            and '"customer_traffic"' in source
            and '"settlement_finality"' in source
            and '"dpi_bypass"' in source
        ),
        "requires_goal_audit_row": (
            "REQUIRED_GOAL_AUDIT_ROWS" in source
            and '"goal_audit:cross_plane_proof_gate"' in source
        ),
        "loads_proof_gate_source_artifact": (
            'ArtifactSpec("cross_plane_proof_gate", DEFAULT_CROSS_PLANE_PROOF_GATE)'
            in source
        ),
        "extracts_proof_gate_blockers": (
            "def _cross_plane_proof_gate_blocker_ids" in source
            and "claim_blocked:" in source
        ),
        "allows_only_when_gate_allows": (
            "def _cross_plane_proof_gate_allowed" in source
            and "CROSS_PLANE_CLAIMS_ALLOWED" in source
            and 'data.get("allowed") is True' in source
            and "all(claim_results[claim_id].get(\"allowed\") is True" in source
        ),
        "adds_blocking_row": (
            "cross_plane_gate_allowed" in source
            and "cross-plane proof gate has not allowed objective strong claims"
            in source
        ),
        "reports_proof_gate_metadata": (
            '"cross_plane_proof_gate_allowed": cross_plane_gate_allowed' in source
            and '"cross_plane_proof_gate_blocker_ids": cross_plane_gate_blocker_ids'
            in source
        ),
        "adds_proof_gate_next_action": (
            '"clear_cross_plane_proof_gate"' in source
            and "_cross_plane_proof_gate_command()" in source
            and "--output-json" in source
            and f"--output-json {{DEFAULT_CROSS_PLANE_PROOF_GATE}}" in source
            and "> {DEFAULT_CROSS_PLANE_PROOF_GATE}" not in source
        ),
        "claim_boundary_mentions_proof_gate": (
            "reusable cross-plane proof gate" in source
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "objective_coverage_cross_plane_gate_contract",
                "Missing objective coverage proof-gate fragments: "
                + ", ".join(missing),
                "src/integration/objective_coverage_audit.py",
            )
        ]
    return [
        pass_check(
            "objective_coverage_cross_plane_gate_contract",
            "Objective coverage audit requires the reusable cross-plane proof gate source artifact and regenerates it through the gate's --output-json command before returning COMPLETE",
            "src/integration/objective_coverage_audit.py",
        )
    ]


def _high_risk_true_claim_literal_files(root: Path) -> Iterable[Path]:
    for scan_dir in HIGH_RISK_TRUE_CLAIM_SCAN_DIRS:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            parts = set(path.relative_to(root).parts)
            if parts.intersection(HIGH_RISK_TRUE_CLAIM_SCAN_EXCLUDED_PARTS):
                continue
            yield path


def _has_claim_boundary_context(lines: list[str], index: int) -> bool:
    start = max(0, index - 18)
    end = min(len(lines), index + 19)
    context = "\n".join(lines[start:end]).lower()
    return any(marker in context for marker in HIGH_RISK_TRUE_CLAIM_BOUNDARY_MARKERS)


def check_high_risk_true_claim_literal_contract(root: Path) -> list[CheckResult]:
    unguarded: list[str] = []
    scanned_files = 0
    guarded_literals = 0
    for path in _high_risk_true_claim_literal_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        scanned_files += 1
        relative = path.relative_to(root).as_posix()
        for index, line in enumerate(lines):
            if not HIGH_RISK_TRUE_CLAIM_LITERAL_RE.search(line):
                continue
            if _has_claim_boundary_context(lines, index):
                guarded_literals += 1
                continue
            unguarded.append(f"{relative}:{index + 1}:{line.strip()[:120]}")

    if unguarded:
        return [
            fail_check(
                "high_risk_true_claim_literal_contract",
                (
                    "High-risk true claim literals need nearby claim_gate, "
                    "cross_plane_claim_gate, claim_boundary, or proof metadata: "
                    + "; ".join(unguarded[:8])
                ),
                "src/**/*.py; scripts/**/*.py static scan",
            )
        ]
    return [
        pass_check(
            "high_risk_true_claim_literal_contract",
            (
                "High-risk true claim literals are guarded by nearby claim-boundary "
                f"metadata: scanned_files={scanned_files}; guarded_literals={guarded_literals}"
            ),
            "src/**/*.py; scripts/**/*.py static scan",
        )
    ]


def check_external_dpi_collector_import_bridge_contract(root: Path) -> list[CheckResult]:
    collector = _read(root, EXTERNAL_DPI_COLLECTOR)
    validator = _read(root, EXTERNAL_DPI_VALIDATOR)
    importer = _read(root, EXTERNAL_DPI_IMPORTER)
    intake = _read(root, "scripts/ops/verify_ghost_pulse_external_evidence_intake.py")
    local_runner = _read(root, EXTERNAL_DPI_LOCAL_RUNNER)
    runbook = _read(root, EXTERNAL_DPI_RUNBOOK)
    required = {
        "ghost_pulse_claim_schema": (
            "GHOST_PULSE_CLAIM_SCHEMA" in collector
            and "x0tta6bl4.ghost_pulse.claim_evidence.v1" in collector
        ),
        "import_contract_helper": "def attach_ghost_pulse_import_contract" in collector,
        "dpi_claim_id": '"claim_id": "dpi_lab"' in collector,
        "proof_gate_measurements": (
            '"authorized_lab"' in collector
            and '"baseline_detected_or_blocked"' in collector
            and '"pulse_result_recorded"' in collector
            and '"dpi_bypass_verified"' in collector
        ),
        "required_artifact_roles": (
            "GHOST_PULSE_DPI_ARTIFACT_ROLES" in collector
            and '"lab_scope"' in collector
            and '"baseline_result"' in collector
            and '"pulse_result"' in collector
            and '"lab_conclusion"' in collector
        ),
        "artifact_hash_recomputed_after_claim_envelope": (
            'payload["artifact_identity"]["artifact_sha256"] = artifact_content_sha256(payload)'
            in collector
        ),
        "redacted_command_shape": (
            '"--target-url-sha256"' in collector
            and '"--treatment-url-sha256"' in collector
            and '"--treatment-proxy-present"' in collector
        ),
        "collector_operator_handoff_command_shapes": (
            "COLLECTOR_OPERATOR_HANDOFF_SCHEMA" in collector
            and "x0tta6bl4.external_dpi_proxy.collector_operator_handoff.v1" in collector
            and "def build_operator_handoff" in collector
            and '"read_only_post_collection_commands"' in collector
            and '"write_sequence_after_ready"' in collector
            and "def regenerate_cross_plane_proof_gate_command" in collector
            and "scripts/ops/run_cross_plane_proof_gate.py" in collector
            and "Do not paste private URLs, proxy endpoints, operator IDs, authorization "
            in collector
            and '"raw_inputs_retained": False' in collector
            and '"collector_handoff_is_not_evidence": True' in collector
        ),
        "validator_intake_claim_gate": (
            "def external_dpi_intake_claim_gate" in validator
            and "x0tta6bl4.external_dpi_intake.claim_gate.v1" in validator
            and '"surface": "external_dpi_proxy.validator"' in validator
            and '"proof_gate_dpi_bypass_claim_allowed": False' in validator
            and '"production_readiness_claim_allowed": False' in validator
        ),
        "validator_source_artifact_intake_root_guard": (
            "INCOMING_ARTIFACT_ROOT" in validator
            and "docs/verification/incoming/artifacts" in validator
            and "path must stay under {INCOMING_ARTIFACT_ROOT}" in validator
            and "path must not include symlink components" in validator
        ),
        "importer_intake_claim_gate": (
            "def external_dpi_intake_claim_gate" in importer
            and "x0tta6bl4.external_dpi_intake.claim_gate.v1" in importer
            and "ghost_pulse_external_import" in importer
            and '"local_latest_evidence_copy_claim_allowed": bool(written)'
            in importer
            and '"proof_gate_dpi_bypass_claim_allowed": False' in importer
            and '"production_readiness_claim_allowed": False' in importer
        ),
        "importer_write_freshness_gate": (
            "REPLACEMENT_CANDIDATES_REPORT" in importer
            and "EXTERNAL_EVIDENCE_INTAKE_REPORT" in importer
            and "def write_freshness_context" in importer
            and "verify_saved_report" in importer
            and "claim_ready_in_replacement_report" in importer
            and "claim_ready_in_intake_report" in importer
            and '"write_freshness_claim_allowed"' in importer
            and "def write_freshness_errors" in importer
            and "write freshness gate is not clear" in importer
        ),
        "intake_markdown_operator_command_shapes": (
            "def command_line" in intake
            and "shlex.join" in intake
            and "def append_command_block" in intake
            and "## Operator Command Shapes" in intake
            and "Placeholder values in angle brackets must be filled locally by the operator." in intake
            and "Do not paste target URLs, proxy URLs, operator IDs, authorization scope, or policy context into chat."
            in intake
            and "collector_command_shape" in intake
            and "Read-only import check:" in intake
            and "Write import command, only after readiness is true:" in intake
            and "Acceptance commands:" in intake
        ),
        "intake_markdown_links_external_dpi_runbook": EXTERNAL_DPI_RUNBOOK in intake,
        "local_runner_private_input_guard": (
            "x0tta6bl4.external_dpi_intake.local_runner.v1" in local_runner
            and "x0tta6bl4.external_dpi_intake.local_runner_plan.v1" in local_runner
            and 'CONFIRM_PHRASE = "RUN EXTERNAL DPI PROBES"' in local_runner
            and "getpass.getpass" in local_runner
            and "stream=sys.stderr" in local_runner
            and "Do not paste private values into chat" in local_runner
            and "<authorized target URL; local input only>" in local_runner
            and "<authorized proxy URL; local input only>" in local_runner
            and '"raw_private_values_in_report": False' in local_runner
            and '"raw_private_values_retained": False' in local_runner
            and "READY_TO_IMPORT" in local_runner
            and EXTERNAL_DPI_COLLECTOR in local_runner
            and EXTERNAL_DPI_VALIDATOR in local_runner
            and EXTERNAL_DPI_IMPORTER in local_runner
        ),
        "local_runner_output_redaction": (
            "REDACTED_LOCAL_INPUT" in local_runner
            and "def _redact_private_values" in local_runner
            and "_redact_private_values(collector_report" in local_runner
            and "_redact_private_values(validator_report" in local_runner
            and "_redact_private_values(import_report" in local_runner
            and '"raw_private_values_retained": False' in local_runner
        ),
        "local_runner_post_import_refresh_plan": (
            "def _post_import_refresh_commands" in local_runner
            and '"scripts/ops/verify_ghost_pulse_external_evidence.py"' in local_runner
            and '"scripts/ops/verify_ghost_pulse_external_evidence_intake.py"' in local_runner
            and '"scripts/ops/verify_ghost_pulse_external_evidence_inventory.py"' in local_runner
            and '"scripts/ops/verify_ghost_pulse_artifact_chain.py"' in local_runner
            and '"scripts/ops/verify_ghost_pulse_goal_state.py"' in local_runner
            and '"post_import_refresh_commands": _post_import_refresh_commands()' in local_runner
        ),
        "operator_runbook": (
            "# Ghost Pulse External DPI Intake Runbook" in runbook
            and "AUTHORIZED_EXTERNAL_EVIDENCE_REQUIRED" in runbook
            and "run_external_dpi_intake_local.py --json --write-ready" in runbook
            and "Do not paste target URLs" in runbook
            and "validator and import preflight both report readiness" in runbook
            and "verify_ghost_pulse_external_evidence_inventory.py --write-report --json" in runbook
            and "verify_ghost_pulse_goal_state.py --write-report --json" in runbook
            and "Do not edit `GHOST_PULSE_DPI_LAB_LATEST.json` by hand" in runbook
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "external_dpi_collector_import_bridge_contract",
                "Missing external DPI collector-to-import bridge fragments: " + ", ".join(missing),
                (
                    f"{EXTERNAL_DPI_COLLECTOR}; {EXTERNAL_DPI_VALIDATOR}; "
                    f"{EXTERNAL_DPI_IMPORTER}; scripts/ops/verify_ghost_pulse_external_evidence_intake.py; "
                    f"{EXTERNAL_DPI_LOCAL_RUNNER}; {EXTERNAL_DPI_RUNBOOK}"
                ),
            )
        ]
    return [
        pass_check(
            "external_dpi_collector_import_bridge_contract",
            "External DPI collector emits validator/import-ready artifacts plus a safe local operator handoff, local runner keeps private target/proxy inputs out of chat/shell history, redacts local inputs from its output, and returns the post-import refresh plan; validator source artifacts stay under the incoming artifact root, importer write requires fresh replacement/intake reports, intake Markdown links the DPI runbook, and validator/importer reports carry fail-closed intake claim gates",
            (
                f"{EXTERNAL_DPI_COLLECTOR}; {EXTERNAL_DPI_VALIDATOR}; "
                f"{EXTERNAL_DPI_IMPORTER}; scripts/ops/verify_ghost_pulse_external_evidence_intake.py; "
                f"{EXTERNAL_DPI_LOCAL_RUNNER}; {EXTERNAL_DPI_RUNBOOK}"
            ),
        )
    ]


def check_integration_spine_claim_gate_contract(root: Path) -> list[CheckResult]:
    spine = _read(root, "src/integration/spine.py")
    code_wiring = _read(root, "src/integration/code_wiring.py")
    required = {
        "spine_claim_gate_helper": "def _spine_claim_gate(" in spine,
        "spine_cross_plane_gate_helper": "def _spine_cross_plane_claim_gate(" in spine,
        "outcome_claim_gate_fields": (
            "claim_gate: Dict[str, Any] = field(default_factory=dict)" in spine
            and "cross_plane_claim_gate: Dict[str, Any] = field(default_factory=dict)" in spine
        ),
        "outcome_serializes_gates": (
            '"claim_gate": dict(self.claim_gate)' in spine
            and '"cross_plane_claim_gate": dict(self.cross_plane_claim_gate)' in spine
        ),
        "events_carry_gates": (
            '"claim_gate": _spine_claim_gate(' in spine
            and '"cross_plane_claim_gate": _spine_cross_plane_claim_gate(' in spine
        ),
        "actuator_context_carries_gates": (
            '"claim_gate": actuator_claim_gate' in spine
            and '"cross_plane_claim_gate": actuator_cross_plane_claim_gate' in spine
            and '"upstream_event_ids": list(event_ids)' in spine
            and '"upstream_source_agents": [self.source_agent]' in spine
        ),
        "reward_context_carries_gates": (
            "reward_claim_gate = _spine_claim_gate(" in spine
            and "reward_cross_plane_claim_gate = _spine_cross_plane_claim_gate(" in spine
            and "upstream_claim_gate=reward_claim_gate" in spine
            and "upstream_cross_plane_claim_gate=reward_cross_plane_claim_gate" in spine
        ),
        "strong_claims_fail_closed": (
            '"production_readiness_claim_allowed": False' in spine
            and '"dataplane_delivery_claim_allowed": False' in spine
            and '"traffic_delivery_claim_allowed": False' in spine
            and '"customer_traffic_claim_allowed": False' in spine
            and '"external_dpi_bypass_claim_allowed": False' in spine
            and '"external_settlement_finality_claim_allowed": False' in spine
            and '"allowed": False' in spine
        ),
        "code_wiring_verifies_gates": (
            '"outcome_claim_gate_present"' in code_wiring
            and '"event_claim_gates_present"' in code_wiring
            and '"actuator_context_claim_gate_present"' in code_wiring
            and '"actuator_context_upstream_events_present"' in code_wiring
            and '"reward_context_claim_gate_present"' in code_wiring
            and '"reward_context_upstream_events_present"' in code_wiring
            and '"strong_claims_blocked"' in code_wiring
            and '"spine_claim_gates_preserved"' in code_wiring
            and '"actuator_context_claim_gates_preserved"' in code_wiring
            and '"reward_context_claim_gates_preserved"' in code_wiring
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "integration_spine_claim_gate_contract",
                "Missing integration-spine claim-gate fragments: " + ", ".join(missing),
                "src/integration/spine.py; src/integration/code_wiring.py",
            )
        ]
    return [
        pass_check(
            "integration_spine_claim_gate_contract",
            "Integration spine outcomes, EventBus trace events, actuator context, and reward context keep local lifecycle and reward-adapter records separate from production/dataplane/DPI/traffic/settlement proof",
            "src/integration/spine.py; src/integration/code_wiring.py",
        )
    ]


def check_rollup_approval_context_gate_contract(root: Path) -> list[CheckResult]:
    rollup = _read(root, "src/integration/rollup_approval_contract.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in rollup,
        "current_evidence_clear_helper": "def _current_evidence_clear" in rollup,
        "declares_cross_plane_proof_gate_artifact": (
            'DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"'
            in rollup
            and "ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS" in rollup
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in rollup
            and "def _cross_plane_proof_gate_allowed" in rollup
            and "def _cross_plane_proof_gate_blocker_ids" in rollup
        ),
        "ready_requires_current_evidence": (
            "ready = local_ready and current_evidence_clear and cross_plane_proof_gate_allowed" in rollup
        ),
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in rollup
            and '"current_evidence_context_hash": current_evidence_context_hash' in rollup
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in rollup
            and '"cross_plane_proof_gate_required": True' in rollup
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in rollup
        ),
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in rollup
            and '"proof_claims": {' in rollup
            and '"production_ready": False' in rollup
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in rollup
        ),
        "local_only_no_live_apply": (
            '"live_apply_authorized": False' in rollup
            and '"goal_completion_authorized": False' in rollup
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "rollup_approval_context_gate_contract",
                "Missing rollup approval current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/rollup_approval_contract.py",
            )
        ]
    return [
        pass_check(
            "rollup_approval_context_gate_contract",
            "Rollup approval contract requires current evidence context plus the reusable cross-plane proof gate and keeps production/live-apply claims fail-closed",
            "src/integration/rollup_approval_contract.py",
        )
    ]


def check_required_evidence_consistency_context_gate_contract(root: Path) -> list[CheckResult]:
    consistency = _read(root, "src/integration/required_evidence_consistency.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in consistency,
        "current_evidence_clear_helper": "def _current_evidence_clear" in consistency,
        "declares_cross_plane_proof_gate_artifact": (
            'DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"'
            in consistency
            and "REQUIRED_EVIDENCE_CROSS_PLANE_CLAIMS" in consistency
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in consistency
            and "def _cross_plane_proof_gate_allowed" in consistency
            and "def _cross_plane_proof_gate_blocker_ids" in consistency
        ),
        "production_ready_requires_current_evidence": (
            "production_ready = raw_consistency_ready and current_evidence_clear and cross_plane_proof_gate_allowed"
            in consistency
        ),
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in consistency
            and '"current_evidence_context_hash": current_evidence_context_hash' in consistency
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in consistency
            and '"cross_plane_proof_gate_required": True' in consistency
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in consistency
        ),
        "raw_consistency_separated": '"raw_consistency_ready": raw_consistency_ready' in consistency,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in consistency
            and '"production_ready_claim_allowed": production_ready' in consistency
            and '"proof_claims": {' in consistency
            and '"production_ready": False' in consistency
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in consistency
        ),
        "local_only_no_live_apply": (
            '"live_apply_authorized": False' in consistency
            and '"goal_completion_authorized": False' in consistency
        ),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "required_evidence_consistency_context_gate_contract",
                "Missing required-evidence current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/required_evidence_consistency.py",
            )
        ]
    return [
        pass_check(
            "required_evidence_consistency_context_gate_contract",
            "Required-evidence consistency separates raw consistency from production readiness and requires current evidence context plus the reusable cross-plane proof gate",
            "src/integration/required_evidence_consistency.py",
        )
    ]


def check_semantic_blocker_queue_context_gate_contract(root: Path) -> list[CheckResult]:
    queue = _read(root, "src/integration/semantic_production_blocker_queue.py")
    required = {
        "cross_plane_proof_gate_default": "DEFAULT_CROSS_PLANE_PROOF_GATE" in queue,
        "cross_plane_proof_gate_claims": "SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS" in queue,
        "current_evidence_context_helper": "def _current_evidence_context" in queue,
        "current_evidence_clear_helper": "def _current_evidence_clear" in queue,
        "cross_plane_proof_gate_context_helper": "def _cross_plane_proof_gate_context" in queue,
        "cross_plane_proof_gate_allowed_helper": "def _cross_plane_proof_gate_allowed" in queue,
        "cross_plane_proof_gate_blocker_helper": "def _cross_plane_proof_gate_blocker_ids" in queue,
        "complete_requires_current_evidence": (
            "complete = local_queue_clear and current_evidence_clear and cross_plane_proof_gate_allowed"
            in queue
        ),
        "goal_completion_uses_complete": '"goal_can_be_marked_complete": complete' in queue,
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in queue
            and '"current_evidence_context_hash": current_evidence_context_hash' in queue
            and '"cross_plane_proof_gate": cross_plane_proof_gate' in queue
        ),
        "local_queue_separated": '"local_queue_clear": local_queue_clear' in queue,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in queue
            and '"goal_completion_claim_allowed": complete' in queue
            and '"cross_plane_proof_gate_required": True' in queue
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in queue
            and '"proof_claims": {' in queue
            and '"production_ready": False' in queue
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in queue,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "semantic_blocker_queue_context_gate_contract",
                "Missing semantic blocker queue current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/semantic_production_blocker_queue.py",
            )
        ]
    return [
        pass_check(
            "semantic_blocker_queue_context_gate_contract",
            "Semantic blocker queue separates local queue state from goal completion and requires current evidence context plus the reusable proof gate",
            "src/integration/semantic_production_blocker_queue.py",
        )
    ]


def check_raw_evidence_inventory_context_gate_contract(root: Path) -> list[CheckResult]:
    inventory = _read(root, "src/integration/raw_evidence_inventory.py")
    required = {
        "cross_plane_proof_gate_default": "DEFAULT_CROSS_PLANE_PROOF_GATE" in inventory,
        "cross_plane_proof_gate_claims": "RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS" in inventory,
        "current_evidence_context_helper": "def _current_evidence_context" in inventory,
        "current_evidence_clear_helper": "def _current_evidence_clear" in inventory,
        "cross_plane_proof_gate_context_helper": "def _cross_plane_proof_gate_context" in inventory,
        "cross_plane_proof_gate_allowed_helper": "def _cross_plane_proof_gate_allowed" in inventory,
        "cross_plane_proof_gate_blocker_helper": "def _cross_plane_proof_gate_blocker_ids" in inventory,
        "complete_requires_current_evidence": (
            "complete = local_inventory_clear and current_evidence_clear and cross_plane_proof_gate_allowed"
            in inventory
        ),
        "goal_completion_uses_complete": '"goal_can_be_marked_complete": complete' in inventory,
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in inventory
            and '"current_evidence_context_hash": current_evidence_context_hash' in inventory
            and '"cross_plane_proof_gate": cross_plane_proof_gate' in inventory
        ),
        "local_inventory_separated": '"local_inventory_clear": local_inventory_clear' in inventory,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in inventory
            and '"goal_completion_claim_allowed": complete' in inventory
            and '"cross_plane_proof_gate_required": True' in inventory
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in inventory
            and '"proof_claims": {' in inventory
            and '"production_ready": False' in inventory
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in inventory,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "raw_evidence_inventory_context_gate_contract",
                "Missing raw evidence inventory current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/raw_evidence_inventory.py",
            )
        ]
    return [
        pass_check(
            "raw_evidence_inventory_context_gate_contract",
            "Raw evidence inventory separates local inventory state from goal completion and requires current evidence context plus the reusable proof gate",
            "src/integration/raw_evidence_inventory.py",
        )
    ]


def check_raw_evidence_operator_packet_context_gate_contract(root: Path) -> list[CheckResult]:
    packet = _read(root, "src/integration/production_raw_evidence_operator_packet.py")
    required = {
        "cross_plane_proof_gate_default": "DEFAULT_CROSS_PLANE_PROOF_GATE" in packet,
        "cross_plane_proof_gate_claims": "RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS" in packet,
        "current_evidence_context_helper": "def _current_evidence_context" in packet,
        "current_evidence_clear_helper": "def _current_evidence_clear" in packet,
        "cross_plane_proof_gate_context_helper": "def _cross_plane_proof_gate_context" in packet,
        "cross_plane_proof_gate_allowed_helper": "def _cross_plane_proof_gate_allowed" in packet,
        "cross_plane_proof_gate_blocker_helper": "def _cross_plane_proof_gate_blocker_ids" in packet,
        "production_ready_requires_current_evidence": (
            "production_ready = local_production_ready and current_evidence_clear and cross_plane_proof_gate_allowed"
            in packet
        ),
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in packet
            and '"current_evidence_context_hash": current_evidence_context_hash' in packet
            and '"cross_plane_proof_gate": cross_plane_proof_gate' in packet
        ),
        "local_production_ready_separated": '"local_production_ready": local_production_ready' in packet,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in packet
            and '"production_ready_claim_allowed": production_ready' in packet
            and '"cross_plane_proof_gate_required": True' in packet
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in packet
            and '"proof_claims": {' in packet
            and '"goal_completion_authorized": False' in packet
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in packet,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "raw_evidence_operator_packet_context_gate_contract",
                "Missing raw evidence operator packet current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/production_raw_evidence_operator_packet.py",
            )
        ]
    return [
        pass_check(
            "raw_evidence_operator_packet_context_gate_contract",
            "Raw evidence operator packet separates local production-ready files from production_ready and requires current evidence context plus the reusable proof gate",
            "src/integration/production_raw_evidence_operator_packet.py",
        )
    ]


def check_production_evidence_replacement_passport_context_gate_contract(root: Path) -> list[CheckResult]:
    passport = _read(root, "src/integration/production_evidence_replacement_passport.py")
    required = {
        "cross_plane_proof_gate_default": "DEFAULT_CROSS_PLANE_PROOF_GATE" in passport,
        "cross_plane_proof_gate_claims": "REPLACEMENT_PASSPORT_CROSS_PLANE_CLAIMS" in passport,
        "current_evidence_context_helper": "def _current_evidence_context" in passport,
        "current_evidence_clear_helper": "def _current_evidence_clear" in passport,
        "cross_plane_proof_gate_context_helper": "def _cross_plane_proof_gate_context" in passport,
        "cross_plane_proof_gate_allowed_helper": "def _cross_plane_proof_gate_allowed" in passport,
        "cross_plane_proof_gate_blocker_helper": "def _cross_plane_proof_gate_blocker_ids" in passport,
        "production_ready_requires_current_evidence": (
            "production_ready = local_production_ready and current_evidence_clear and cross_plane_proof_gate_allowed"
            in passport
        ),
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in passport
            and '"current_evidence_context_hash": current_evidence_context_hash' in passport
            and '"cross_plane_proof_gate": cross_plane_proof_gate' in passport
        ),
        "local_production_ready_separated": '"local_production_ready": local_production_ready' in passport,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in passport
            and '"production_ready_claim_allowed": production_ready' in passport
            and '"cross_plane_proof_gate_required": True' in passport
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in passport
            and '"proof_claims": {' in passport
            and '"goal_completion_authorized": False' in passport
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in passport,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "production_evidence_replacement_passport_context_gate_contract",
                "Missing replacement passport current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/production_evidence_replacement_passport.py",
            )
        ]
    return [
        pass_check(
            "production_evidence_replacement_passport_context_gate_contract",
            "Production evidence replacement passport separates local replacement readiness from production_ready and requires current evidence context plus the reusable proof gate",
            "src/integration/production_evidence_replacement_passport.py",
        )
    ]


def check_completion_gate_runner_context_gate_contract(root: Path) -> list[CheckResult]:
    runner = _read(root, "src/integration/completion_gate_runner.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in runner,
        "current_evidence_clear_helper": "def _current_evidence_clear" in runner,
        "declares_cross_plane_proof_gate_artifact": (
            "DEFAULT_CROSS_PLANE_PROOF_GATE" in runner
            and ".tmp/validation-shards/cross-plane-proof-gate-current.json" in runner
            and "COMPLETION_GATE_CROSS_PLANE_CLAIMS" in runner
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in runner
            and "def _cross_plane_proof_gate_allowed" in runner
            and "def _cross_plane_proof_gate_blocker_ids" in runner
            and "source_artifact_hashes_present" in runner
        ),
        "complete_requires_current_evidence": (
            "complete = local_completion_ready and current_evidence_clear and cross_plane_proof_gate_allowed"
            in runner
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in runner
            and '"cross_plane_proof_gate_required": True' in runner
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed'
            in runner
        ),
        "goal_completion_uses_complete": '"goal_can_be_marked_complete": complete' in runner,
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in runner
            and '"current_evidence_context_hash": current_evidence_context_hash' in runner
        ),
        "local_completion_ready_separated": '"local_completion_ready": local_completion_ready' in runner,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in runner
            and '"goal_completion_claim_allowed": complete' in runner
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed'
            in runner
            and '"proof_claims": {' in runner
            and '"goal_completion_authorized": False' in runner
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in runner,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "completion_gate_runner_context_gate_contract",
                "Missing completion gate runner current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/completion_gate_runner.py",
            )
        ]
    return [
        pass_check(
            "completion_gate_runner_context_gate_contract",
            "Completion gate runner separates local source readiness from goal completion and requires current evidence context plus the reusable cross-plane proof gate",
            "src/integration/completion_gate_runner.py",
        )
    ]


def check_production_gap_index_context_gate_contract(root: Path) -> list[CheckResult]:
    gap_index = _read(root, "src/integration/production_gap_index.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in gap_index,
        "current_evidence_clear_helper": "def _current_evidence_clear" in gap_index,
        "declares_cross_plane_proof_gate_artifact": (
            'DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"'
            in gap_index
            and "PRODUCTION_GAP_INDEX_CROSS_PLANE_CLAIMS" in gap_index
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in gap_index
            and "def _cross_plane_proof_gate_allowed" in gap_index
            and "def _cross_plane_proof_gate_blocker_ids" in gap_index
        ),
        "complete_requires_current_evidence": (
            "complete = local_gap_index_clear and current_evidence_clear and cross_plane_proof_gate_allowed"
            in gap_index
        ),
        "goal_completion_uses_complete": '"goal_can_be_marked_complete": complete' in gap_index,
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in gap_index
            and '"current_evidence_context_hash": current_evidence_context_hash' in gap_index
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in gap_index
            and '"cross_plane_proof_gate_required": True' in gap_index
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in gap_index
        ),
        "local_gap_index_clear_separated": '"local_gap_index_clear": local_gap_index_clear' in gap_index,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in gap_index
            and '"goal_completion_claim_allowed": complete' in gap_index
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in gap_index
            and '"proof_claims": {' in gap_index
            and '"goal_completion_authorized": False' in gap_index
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in gap_index,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "production_gap_index_context_gate_contract",
                "Missing production gap index current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/production_gap_index.py",
            )
        ]
    return [
        pass_check(
            "production_gap_index_context_gate_contract",
            "Production gap index separates local gap clearance from goal completion and requires current evidence context plus the reusable cross-plane proof gate",
            "src/integration/production_gap_index.py",
        )
    ]


def check_production_closeout_review_context_gate_contract(root: Path) -> list[CheckResult]:
    closeout = _read(root, "src/integration/production_closeout_review.py")
    required = {
        "current_evidence_context_helper": "def _current_evidence_context" in closeout,
        "current_evidence_clear_helper": "def _current_evidence_clear" in closeout,
        "declares_cross_plane_proof_gate_artifact": (
            'DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"'
            in closeout
            and "CLOSEOUT_REVIEW_CROSS_PLANE_CLAIMS" in closeout
        ),
        "loads_cross_plane_proof_gate_context": (
            "def _cross_plane_proof_gate_context" in closeout
            and "def _cross_plane_proof_gate_allowed" in closeout
            and "def _cross_plane_proof_gate_blocker_ids" in closeout
        ),
        "ready_requires_current_evidence": (
            "ready = local_closeout_ready and current_evidence_clear and cross_plane_proof_gate_allowed"
            in closeout
        ),
        "current_evidence_report_fields": (
            '"current_evidence_context": current_evidence_context' in closeout
            and '"current_evidence_context_hash": current_evidence_context_hash' in closeout
        ),
        "reports_cross_plane_proof_gate": (
            '"cross_plane_proof_gate": cross_plane_proof_gate' in closeout
            and '"cross_plane_proof_gate_required": True' in closeout
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in closeout
        ),
        "local_closeout_ready_separated": '"local_closeout_ready": local_closeout_ready' in closeout,
        "cross_plane_claim_gate": (
            '"cross_plane_claim_gate": {' in closeout
            and '"closeout_ready_claim_allowed": ready' in closeout
            and '"cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed' in closeout
            and '"proof_claims": {' in closeout
            and '"goal_completion_authorized": False' in closeout
        ),
        "local_only_no_live_apply": '"live_apply_authorized": False' in closeout,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return [
            fail_check(
                "production_closeout_review_context_gate_contract",
                "Missing production closeout review current-evidence gate fragments: " + ", ".join(missing),
                "src/integration/production_closeout_review.py",
            )
        ]
    return [
        pass_check(
            "production_closeout_review_context_gate_contract",
            "Production closeout review separates local closeout readiness from closeout-ready claim and requires current evidence context plus the reusable cross-plane proof gate",
            "src/integration/production_closeout_review.py",
        )
    ]


def check_api_readiness_claim_gate_inventory(root: Path) -> list[CheckResult]:
    api_root = root / "src/api"
    if not api_root.exists():
        return [
            fail_check(
                "api_readiness_claim_gate_inventory",
                "Missing API source root for readiness claim-gate inventory",
                "src/api",
            )
        ]

    missing: list[str] = []
    parse_errors: list[str] = []
    checked = 0
    for path in sorted(api_root.glob("*.py")):
        rel = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            parse_errors.append(f"{rel}:{exc.lineno or 1}:{exc.msg}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.endswith("readiness_status"):
                continue
            checked += 1
            segment = ast.get_source_segment(source, node) or ""
            if "cross_plane_claim_gate" not in segment:
                missing.append(f"{rel}:{node.lineno}:{node.name}")

    if parse_errors:
        return [
            fail_check(
                "api_readiness_claim_gate_inventory",
                "API readiness inventory parse errors: " + ", ".join(parse_errors),
                "src/api/*.py",
            )
        ]
    if missing:
        return [
            fail_check(
                "api_readiness_claim_gate_inventory",
                "API readiness helpers missing cross_plane_claim_gate: " + ", ".join(missing),
                "src/api/*.py",
            )
        ]
    return [
        pass_check(
            "api_readiness_claim_gate_inventory",
            f"API readiness helpers carry cross_plane_claim_gate metadata: {checked}",
            "src/api/*.py",
        )
    ]


def external_dpi_intake_requirement(root: Path) -> dict[str, object]:
    candidate_path = root / EXTERNAL_DPI_CANDIDATE
    contract_path = root / EXTERNAL_DPI_CONTRACT
    validator_path = root / EXTERNAL_DPI_VALIDATOR
    collector_path = root / EXTERNAL_DPI_COLLECTOR
    importer_path = root / EXTERNAL_DPI_IMPORTER
    candidate_exists = candidate_path.exists()
    candidate_is_file = candidate_path.is_file()
    candidate_is_symlink = candidate_path.is_symlink()
    return {
        "id": EXTERNAL_DPI_INTAKE_ACTION_ID,
        "blocking_gap_id": EXTERNAL_DPI_PROOF_MISSING_GAP_ID,
        "status": "WAITING_FOR_AUTHORIZED_EXTERNAL_ARTIFACT",
        "required_artifact_schema": EXTERNAL_DPI_SCHEMA_VERSION,
        "ghost_pulse_import_bridge_required": True,
        "ghost_pulse_claim_schema": "x0tta6bl4.ghost_pulse.claim_evidence.v1",
        "ghost_pulse_claim_id": "dpi_lab",
        "ghost_pulse_required_artifact_roles": [
            "lab_scope",
            "baseline_result",
            "pulse_result",
            "lab_conclusion",
        ],
        "expected_candidate_path": EXTERNAL_DPI_CANDIDATE,
        "candidate_exists": candidate_exists,
        "candidate_is_file": candidate_is_file,
        "candidate_is_symlink": candidate_is_symlink,
        "contract_path": EXTERNAL_DPI_CONTRACT,
        "contract_exists": contract_path.is_file(),
        "validator_path": EXTERNAL_DPI_VALIDATOR,
        "validator_exists": validator_path.is_file(),
        "collector_path": EXTERNAL_DPI_COLLECTOR,
        "collector_exists": collector_path.is_file(),
        "importer_path": EXTERNAL_DPI_IMPORTER,
        "importer_exists": importer_path.is_file(),
        "validator_command": [
            "python3",
            EXTERNAL_DPI_VALIDATOR,
            "--candidate",
            EXTERNAL_DPI_CANDIDATE,
            "--require-ready",
            "--json",
        ],
        "import_preflight_command": [
            "python3",
            EXTERNAL_DPI_IMPORTER,
            "--claim",
            "dpi_lab",
            "--candidate",
            EXTERNAL_DPI_CANDIDATE,
            "--require-ready",
            "--json",
        ],
        "safe_local_runner_command": [
            "python3",
            EXTERNAL_DPI_LOCAL_RUNNER,
            "--json",
            "--write-ready",
        ],
        "collector_command_shape": [
            "python3",
            EXTERNAL_DPI_COLLECTOR,
            "--output",
            EXTERNAL_DPI_CANDIDATE,
            "--artifact-dir",
            "docs/verification/incoming/artifacts/dpi_lab",
            "--allow-external-probes",
            "--target-url",
            "<authorized target URL; local input only>",
            "--treatment-proxy",
            "<authorized proxy URL; local input only>",
            "--operator-or-lab-id",
            "<local operator/lab id; hashed before writing>",
            "--authorization-scope-id",
            "<local authorization scope; hashed before writing>",
            "--scope-summary",
            "<bounded authorized scope>",
            "--network-region-bucket",
            "<coarse region>",
            "--network-type",
            "<authorized lab/field network>",
            "--isp-or-lab-profile",
            "<local ISP/lab profile; hashed before writing>",
            "--egress-location-bucket",
            "<coarse egress>",
            "--policy-context",
            "<authorized policy context>",
            "--json",
        ],
        "requires_authorized_external_lab_or_field_run": True,
        "collector_output_ready_when": [
            "bounded_external_dpi_proxy_validator_reports_READY_TO_IMPORT",
            "ghost_pulse_import_preflight_reports_READY_TO_IMPORT",
        ],
        "safe_local_input_rule": (
            "Do not paste private URLs, proxy endpoints, operator IDs, scope IDs, "
            "subscriber data, tokens, or captures into chat. Provide them only to "
            "the local runner or collector process in the authorized environment."
        ),
        "required_true_flags": list(EXTERNAL_DPI_REQUIRED_TRUE_FLAGS),
        "must_remain_false_flags": list(EXTERNAL_DPI_MUST_REMAIN_FALSE_FLAGS),
        "forbidden_raw_fields": list(EXTERNAL_DPI_FORBIDDEN_RAW_FIELDS),
        "bounded_output_metadata_required": [
            "artifact_sha256",
            "operator_or_lab_hash",
            "scope_id_hash",
            "isp_or_lab_profile_hash",
            "probe_target_hash",
            "redacted_capture_sha256",
            "attempt_count",
            "success_count",
            "failure_buckets",
            "capture_artifact_hashes",
            "redacted_fields",
        ],
        "claim_boundary": {
            "this_detail_is_not_evidence": True,
            "production_ready": False,
            "customer_traffic_confirmed": False,
            "durable_censorship_bypass_confirmed": False,
            "anonymity_confirmed": False,
            "provider_health_confirmed": False,
            "payment_or_token_settlement_finality_confirmed": False,
        },
        "claim_gate": {
            "schema": "x0tta6bl4.external_dpi_intake.next_action_claim_gate.v1",
            "surface": "real_readiness.external_dpi_real_artifact_intake",
            "local_intake_task_observation_claim_allowed": True,
            "candidate_file_observed_claim_allowed": bool(
                candidate_exists and candidate_is_file and not candidate_is_symlink
            ),
            "authorized_external_artifact_required": True,
            "validator_ready_to_import_required": True,
            "import_preflight_ready_required": True,
            "this_detail_is_evidence": False,
            "external_dpi_tested_claim_allowed": False,
            "dpi_bypass_claim_allowed": False,
            "dataplane_confirmed_claim_allowed": False,
            "durable_censorship_bypass_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "anonymity_claim_allowed": False,
            "provider_health_claim_allowed": False,
            "payment_or_token_settlement_finality_claim_allowed": False,
            "production_readiness_claim_allowed": False,
        },
    }


def current_next_action_details(
    root: Path,
    *,
    open_gap_ids: Sequence[object],
    next_action_ids: Sequence[object],
) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    if (
        EXTERNAL_DPI_PROOF_MISSING_GAP_ID in open_gap_ids
        or EXTERNAL_DPI_INTAKE_ACTION_ID in next_action_ids
    ):
        details.append(external_dpi_intake_requirement(root))
    return details


def _non_negative_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int) and value >= 0:
        return value
    return fallback


def _string_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _current_map_claims_external_dpi_subclaim(source_data: Mapping[str, object]) -> bool:
    links = source_data.get("cross_plane_links")
    if not isinstance(links, list):
        return False
    for item in links:
        if not isinstance(item, Mapping):
            continue
        if item.get("id") != "anti-censorship-local-evidence-to-dpi-claim-boundary":
            continue
        proof_flags = item.get("proof_flags")
        if not isinstance(proof_flags, Mapping):
            return False
        return all(
            proof_flags.get(flag) is True
            for flag in (
                "external_dpi_tested",
                "dpi_bypass_confirmed",
                "bypass_confirmed",
            )
        )
    return False


def _external_dpi_latest_artifact_state(root: Path) -> dict[str, object]:
    path = root / EXTERNAL_DPI_LATEST
    state: dict[str, object] = {
        "path": EXTERNAL_DPI_LATEST,
        "exists": path.is_file() and not path.is_symlink(),
        "valid": False,
        "blockers": [],
    }
    blockers: list[str] = []
    if not path.exists():
        blockers.append("external_dpi_latest_missing")
    elif path.is_symlink():
        blockers.append("external_dpi_latest_is_symlink")
    elif not path.is_file():
        blockers.append("external_dpi_latest_not_regular_file")
    if blockers:
        state["blockers"] = blockers
        return state

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        state["blockers"] = [f"external_dpi_latest_json_invalid:{exc}"]
        return state
    if not isinstance(payload, Mapping):
        state["blockers"] = ["external_dpi_latest_not_object"]
        return state

    state["status"] = payload.get("status")
    state["claim_id"] = payload.get("claim_id")
    measurements = payload.get("measurements")
    if not isinstance(measurements, Mapping):
        measurements = {}
    result_summary = payload.get("result_summary")
    if not isinstance(result_summary, Mapping):
        result_summary = {}

    required_measurements = {
        "authorized_lab": True,
        "baseline_detected_or_blocked": True,
        "dpi_bypass_verified": True,
        "pulse_result_recorded": True,
    }
    blockers = []
    if payload.get("status") != "VERIFIED":
        blockers.append("external_dpi_latest_status_not_verified")
    if payload.get("claim_id") != "dpi_lab":
        blockers.append("external_dpi_latest_claim_id_not_dpi_lab")
    for key, expected in required_measurements.items():
        if measurements.get(key) is not expected:
            blockers.append(f"external_dpi_latest_measurement_not_true:{key}")
    if result_summary.get("production_ready") is True:
        blockers.append("external_dpi_latest_production_ready_must_not_be_true")

    state["blockers"] = blockers
    state["valid"] = not blockers
    return state


def current_evidence_context(root: Path) -> dict[str, object]:
    map_path = root / CURRENT_CROSS_PLANE_MAP
    audit_path = root / CURRENT_ACTIVE_AUDIT
    context: dict[str, object] = {
        "included": map_path.exists() and audit_path.exists(),
        "source": "docs/architecture",
        "cross_plane_map": CURRENT_CROSS_PLANE_MAP,
        "active_goal_audit": CURRENT_ACTIVE_AUDIT,
        "claim_boundary": (
            "Real-readiness requires current cross-plane evidence context. "
            "These maps/audits are gating context, not production proof by themselves."
        ),
    }
    if not map_path.exists() or not audit_path.exists():
        context.update(
            {
                "status": "missing_current_evidence_context",
                "current_gap_count": None,
                "tracked_gap_count": None,
                "non_blocking_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
                "non_blocking_gap_ids": [],
                "next_action_ids": [],
                "next_action_details": [],
            }
        )
        return context
    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as exc:
        context.update(
            {
                "status": "invalid_current_evidence_map",
                "error": str(exc),
                "current_gap_count": None,
                "tracked_gap_count": None,
                "non_blocking_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
                "non_blocking_gap_ids": [],
                "next_action_ids": [],
                "next_action_details": [],
            }
        )
        return context
    source_data: Mapping[str, object] = data
    source_format = "top_level_working_map"
    embedded_context = data.get("current_evidence_context")
    if (
        isinstance(embedded_context, Mapping)
        and embedded_context.get("status") == "working_map_not_production_completion_proof"
    ):
        source_data = embedded_context
        source_format = "embedded_current_evidence_context"
    source_shape_valid = (
        source_format == "embedded_current_evidence_context"
        or (
            isinstance(data.get("planes"), Mapping)
            and isinstance(data.get("current_gaps"), list)
            and isinstance(data.get("next_actions"), list)
        )
    )

    gaps = source_data.get("current_gaps")
    gap_items = gaps if isinstance(gaps, list) else []
    blocking_gaps = [
        item
        for item in gap_items
        if isinstance(item, Mapping) and item.get("blocks_real_readiness") is not False
    ]
    non_blocking_gaps = [
        item
        for item in gap_items
        if isinstance(item, Mapping) and item.get("blocks_real_readiness") is False
    ]
    open_gap_ids = [
        str(item.get("id"))
        for item in blocking_gaps
        if isinstance(item, Mapping) and item.get("id")
    ]
    if not open_gap_ids:
        open_gap_ids = _string_ids(source_data.get("open_gap_ids"))
    non_blocking_gap_ids = [
        str(item.get("id"))
        for item in non_blocking_gaps
        if isinstance(item, Mapping) and item.get("id")
    ]
    if not non_blocking_gap_ids:
        non_blocking_gap_ids = _string_ids(source_data.get("non_blocking_gap_ids"))

    next_actions = source_data.get("next_actions")
    next_action_items = next_actions if isinstance(next_actions, list) else []
    next_action_ids = [
        str(item.get("id"))
        for item in next_action_items
        if isinstance(item, Mapping) and item.get("id")
    ]
    if not next_action_ids:
        next_action_ids = _string_ids(source_data.get("next_action_ids"))

    planes = source_data.get("planes")
    if isinstance(planes, Mapping):
        plane_ids = set(planes)
    else:
        plane_ids = set(_string_ids(source_data.get("plane_ids")))

    current_gap_count = _non_negative_int(
        source_data.get("current_gap_count"),
        len(blocking_gaps) if gap_items else len(open_gap_ids),
    )
    non_blocking_gap_count = _non_negative_int(
        source_data.get("non_blocking_gap_count"),
        len(non_blocking_gaps) if gap_items else len(non_blocking_gap_ids),
    )
    tracked_gap_count = _non_negative_int(
        source_data.get("tracked_gap_count"),
        len([item for item in gap_items if isinstance(item, Mapping)])
        if gap_items
        else current_gap_count + non_blocking_gap_count,
    )
    next_action_count = _non_negative_int(
        source_data.get("next_action_count"),
        len(next_action_items) if next_action_items else len(next_action_ids),
    )
    context.update(
        {
            "status": source_data.get("status"),
            "source_format": source_format,
            "source_shape_valid": source_shape_valid,
            "current_gap_count": current_gap_count,
            "tracked_gap_count": tracked_gap_count,
            "non_blocking_gap_count": non_blocking_gap_count,
            "next_action_count": next_action_count,
            "open_gap_ids": open_gap_ids,
            "non_blocking_gap_ids": non_blocking_gap_ids,
            "next_action_ids": next_action_ids,
            "required_planes_present": REQUIRED_CROSS_PLANE_PLANES.issubset(plane_ids),
            "plane_ids": sorted(plane_ids),
        }
    )
    external_dpi_subclaim_claimed = _current_map_claims_external_dpi_subclaim(source_data)
    context["external_dpi_subclaim_claimed"] = external_dpi_subclaim_claimed
    context["external_dpi_latest_artifact"] = (
        _external_dpi_latest_artifact_state(root)
        if external_dpi_subclaim_claimed
        else {
            "path": EXTERNAL_DPI_LATEST,
            "required": False,
            "valid": None,
            "blockers": [],
        }
    )
    context["next_action_details"] = current_next_action_details(
        root,
        open_gap_ids=context["open_gap_ids"],
        next_action_ids=context["next_action_ids"],
    )
    return context


def check_current_evidence_context(root: Path) -> list[CheckResult]:
    context = current_evidence_context(root)
    if context.get("included") is not True:
        return [
            fail_check(
                "current_evidence_context_present",
                "Missing current evidence map or active audit",
                f"{CURRENT_CROSS_PLANE_MAP}; {CURRENT_ACTIVE_AUDIT}",
            )
        ]
    if context.get("source_shape_valid") is not True:
        return [
            fail_check(
                "current_evidence_context_shape",
                (
                    "Current evidence map must be either the full working map "
                    "with planes/current_gaps/next_actions or a generated audit "
                    "wrapper with embedded current_evidence_context"
                ),
                CURRENT_CROSS_PLANE_MAP,
            )
        ]
    if context.get("status") != "working_map_not_production_completion_proof":
        return [
            fail_check(
                "current_evidence_context_status",
                f"Unexpected current evidence map status: {context.get('status')}",
                CURRENT_CROSS_PLANE_MAP,
            )
        ]
    if context.get("required_planes_present") is not True:
        return [
            fail_check(
                "current_evidence_context_planes",
                "Current evidence map does not cover data/control/trust/evidence/economy planes",
                CURRENT_CROSS_PLANE_MAP,
            )
        ]
    gap_count = context.get("current_gap_count")
    next_action_count = context.get("next_action_count")
    if gap_count or next_action_count:
        return [
            fail_check(
                "current_evidence_open_gaps",
                (
                    f"Current evidence map still has {gap_count} gaps and "
                    f"{next_action_count} next actions: "
                    f"gaps={context.get('open_gap_ids')}; "
                    f"next_actions={context.get('next_action_ids')}"
                ),
                CURRENT_CROSS_PLANE_MAP,
            )
        ]
    if (
        context.get("external_dpi_subclaim_claimed") is True
        and not isinstance(context.get("external_dpi_latest_artifact"), Mapping)
    ):
        return [
            fail_check(
                "current_evidence_dpi_artifact_missing",
                "Current evidence map claims external DPI subclaim but artifact state is unavailable",
                CURRENT_CROSS_PLANE_MAP,
            )
        ]
    artifact_state = context.get("external_dpi_latest_artifact")
    if (
        context.get("external_dpi_subclaim_claimed") is True
        and isinstance(artifact_state, Mapping)
        and artifact_state.get("valid") is not True
    ):
        return [
            fail_check(
                "current_evidence_dpi_artifact_missing",
                (
                    "Current evidence map claims external DPI subclaim but "
                    f"{EXTERNAL_DPI_LATEST} is not a valid VERIFIED dpi_lab artifact: "
                    f"{artifact_state.get('blockers')}"
                ),
                EXTERNAL_DPI_LATEST,
            )
        ]
    return [
        pass_check(
            "current_evidence_context_clear",
            "Current cross-plane evidence context is present and has no open gaps/next actions",
            CURRENT_CROSS_PLANE_MAP,
        )
    ]


def check_command_contracts(root: Path, runner: Runner) -> list[CheckResult]:
    checks: list[CheckResult] = []

    for zone in ("authoritative", "active_claim_surface"):
        claim_hygiene = runner(
            (
                sys.executable,
                "scripts/claim_hygiene_scan.py",
                "--zone",
                zone,
                "--fail-on-active",
                "--json",
            ),
            None,
            60,
        )
        check_id = f"claim_hygiene_{zone}"
        if claim_hygiene.returncode != 0:
            checks.append(
                fail_check(
                    check_id,
                    _format_command_failure(claim_hygiene),
                    f"python scripts/claim_hygiene_scan.py --zone {zone} --fail-on-active --json",
                )
            )
            continue
        try:
            payload = json.loads(claim_hygiene.stdout)
        except json.JSONDecodeError:
            payload = {}
        active_count = payload.get("active_count")
        files_scanned = payload.get("files_scanned")
        detail = f"Claim hygiene scan passes for {zone}"
        if isinstance(active_count, int):
            detail += f"; active={active_count}"
        if isinstance(files_scanned, int):
            detail += f"; files_scanned={files_scanned}"
        checks.append(
            pass_check(
                check_id,
                detail,
                f"python scripts/claim_hygiene_scan.py --zone {zone} --fail-on-active --json",
            )
        )

    app_env = {
        "DATABASE_URL": "postgresql://readiness:readiness@localhost:5432/readiness",
        "ADMIN_USER": "readiness-admin",
        "ADMIN_PASS": "readiness-placeholder-not-secret",
    }
    app_config = runner(("docker", "compose", "-f", "docker-compose.app.yml", "config"), app_env, 60)
    if app_config.returncode == 0:
        checks.append(pass_check("compose_app_config", "docker compose app config renders with required env", "docker compose -f docker-compose.app.yml config"))
    else:
        checks.append(fail_check("compose_app_config", _format_command_failure(app_config), "docker compose -f docker-compose.app.yml config"))

    ghost_env = {
        "GHOST_VPN_AUTH_KEY": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
        "GRAFANA_PASSWORD": "readiness-placeholder-not-secret",
    }
    ghost_config = runner(("docker", "compose", "-f", "docker-compose.ghost-vpn.yml", "config"), ghost_env, 60)
    if ghost_config.returncode == 0:
        checks.append(pass_check("compose_ghost_vpn_config", "docker compose Ghost VPN config renders with required env", "docker compose -f docker-compose.ghost-vpn.yml config"))
    else:
        checks.append(fail_check("compose_ghost_vpn_config", _format_command_failure(ghost_config), "docker compose -f docker-compose.ghost-vpn.yml config"))

    node_check = runner(("node", "--check", "x0tta6bl4-app/server.cjs"), None, 30)
    if node_check.returncode == 0:
        checks.append(pass_check("app_server_node_check", "Node syntax check passes for app server", "node --check x0tta6bl4-app/server.cjs"))
    else:
        checks.append(fail_check("app_server_node_check", _format_command_failure(node_check), "node --check x0tta6bl4-app/server.cjs"))

    alembic_heads = runner((sys.executable, "-m", "alembic", "heads"), None, 60)
    if alembic_heads.returncode != 0:
        checks.append(fail_check("alembic_single_head", _format_command_failure(alembic_heads), "python -m alembic heads"))
    else:
        heads = [line.strip() for line in alembic_heads.stdout.splitlines() if line.strip()]
        if len(heads) == 1:
            checks.append(pass_check("alembic_single_head", f"Single Alembic head: {heads[0]}", "python -m alembic heads"))
        else:
            checks.append(fail_check("alembic_single_head", f"Expected one Alembic head, got {len(heads)}: {heads}", "python -m alembic heads"))

    return checks


def _git_dirty_status_label(status: str) -> str:
    if status == "??":
        return "untracked"
    if "D" in status:
        return "deleted"
    if "M" in status:
        return "modified"
    if "A" in status:
        return "added"
    if "R" in status:
        return "renamed"
    if "C" in status:
        return "copied"
    return status.strip() or "unknown"


def _git_dirty_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else ""
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1]
    return path or "(unknown)"


def _summarize_git_dirty_lines(dirty_lines: Sequence[str]) -> str:
    status_counts: dict[str, int] = {}
    top_path_counts: dict[str, int] = {}
    for line in dirty_lines:
        status = line[:2] if len(line) >= 2 else line
        status_label = _git_dirty_status_label(status)
        status_counts[status_label] = status_counts.get(status_label, 0) + 1
        path = _git_dirty_path(line)
        top_path = path.split("/", 1)[0]
        top_path_counts[top_path] = top_path_counts.get(top_path, 0) + 1

    preferred_order = ("modified", "deleted", "untracked", "added", "renamed", "copied", "unknown")
    status_parts = [
        f"{label}={status_counts[label]}"
        for label in preferred_order
        if label in status_counts
    ]
    status_parts.extend(
        f"{label}={count}"
        for label, count in sorted(status_counts.items())
        if label not in preferred_order
    )
    top_parts = [
        f"{path}={count}"
        for path, count in sorted(
            top_path_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:8]
    ]
    return f"status_counts: {', '.join(status_parts)}; top_paths: {', '.join(top_parts)}"


def check_git_state(root: Path, runner: Runner) -> list[CheckResult]:
    result = runner(("git", "status", "--porcelain"), None, 30)
    if result.returncode != 0:
        return [fail_check("git_worktree_clean", _format_command_failure(result), "git status --porcelain")]
    dirty_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty_lines:
        details = (
            f"Worktree has {len(dirty_lines)} uncommitted paths; "
            f"{_summarize_git_dirty_lines(dirty_lines)}; "
            "release readiness requires reviewed commits or a clean worktree"
        )
        return [fail_check("git_worktree_clean", details, "git status --porcelain")]
    return [pass_check("git_worktree_clean", "Worktree is clean", "git status --porcelain")]


def build_report(
    root: Path,
    *,
    runner: Runner | None = None,
    include_command_checks: bool = True,
    include_git_check: bool = True,
) -> dict[str, object]:
    runner = runner or default_runner(root)
    checks: list[CheckResult] = []
    checks.extend(check_required_files(root))
    if all(check.ok for check in checks):
        checks.extend(check_app_contract(root))
        checks.extend(check_auth_contract(root))
        checks.extend(check_db_contract(root))
        checks.extend(check_ghost_contract(root))
        checks.extend(check_pulse_contract(root))
        checks.extend(check_ghost_pulse_local_timing_evidence_contract(root))
        checks.extend(check_post_action_dataplane_gate_contract(root))
        checks.extend(check_dataplane_delivery_eventbus_collector_contract(root))
        checks.extend(check_mesh_metric_policy_contract(root))
        checks.extend(check_yggdrasil_observed_state_contract(root))
        checks.extend(check_service_identity_trust_claim_gate_contract(root))
        checks.extend(check_maas_telemetry_claim_gate_contract(root))
        checks.extend(check_mesh_api_claim_gate_contract(root))
        checks.extend(check_status_api_claim_gate_contract(root))
        checks.extend(check_health_api_claim_gate_contract(root))
        checks.extend(check_metrics_api_claim_boundary_contract(root))
        checks.extend(check_maas_mesh_metrics_claim_gate_contract(root))
        checks.extend(check_maas_mesh_deploy_claim_gate_contract(root))
        checks.extend(check_maas_mesh_lifecycle_claim_gate_contract(root))
        checks.extend(check_maas_mesh_read_list_claim_boundary_contract(root))
        checks.extend(check_maas_compat_read_list_claim_boundary_contract(root))
        checks.extend(check_maas_compat_lifecycle_read_claim_boundary_contract(root))
        checks.extend(check_maas_compat_lifecycle_control_claim_gate_contract(root))
        checks.extend(check_maas_core_lifecycle_claim_gate_contract(root))
        checks.extend(check_maas_provisioning_setup_claim_gate_contract(root))
        checks.extend(check_mesh_provisioning_service_claim_gate_contract(root))
        checks.extend(check_mesh_provisioner_claim_gate_contract(root))
        checks.extend(check_batman_metrics_claim_gate_contract(root))
        checks.extend(check_batman_health_claim_gate_contract(root))
        checks.extend(check_batman_topology_claim_gate_contract(root))
        checks.extend(check_batman_control_claim_gate_contract(root))
        checks.extend(check_batman_mesh_status_claim_gate_contract(root))
        checks.extend(check_economy_dataplane_claim_gate_contract(root))
        checks.extend(check_cross_plane_proof_gate_contract(root))
        checks.extend(check_production_system_cross_plane_gate_contract(root))
        checks.extend(check_phase6_production_readiness_context_gate_contract(root))
        checks.extend(check_production_grade_audit_cross_plane_gate_contract(root))
        checks.extend(check_objective_coverage_cross_plane_gate_contract(root))
        checks.extend(check_high_risk_true_claim_literal_contract(root))
        checks.extend(check_external_dpi_collector_import_bridge_contract(root))
        checks.extend(check_integration_spine_claim_gate_contract(root))
        checks.extend(check_rollup_approval_context_gate_contract(root))
        checks.extend(check_required_evidence_consistency_context_gate_contract(root))
        checks.extend(check_semantic_blocker_queue_context_gate_contract(root))
        checks.extend(check_raw_evidence_inventory_context_gate_contract(root))
        checks.extend(check_raw_evidence_operator_packet_context_gate_contract(root))
        checks.extend(check_production_evidence_replacement_passport_context_gate_contract(root))
        checks.extend(check_completion_gate_runner_context_gate_contract(root))
        checks.extend(check_production_gap_index_context_gate_contract(root))
        checks.extend(check_production_closeout_review_context_gate_contract(root))
        checks.extend(check_api_readiness_claim_gate_inventory(root))
        checks.extend(check_current_evidence_context(root))
        if include_command_checks:
            checks.extend(check_command_contracts(root, runner))
        if include_git_check:
            checks.extend(check_git_state(root, runner))

    failures = [check for check in checks if check.status == STATUS_FAIL]
    warnings = [check for check in checks if check.status == STATUS_WARN]
    ready = not failures
    return {
        "schema": "x0tta6bl4.real_readiness.v1",
        "timestamp_utc": utc_now(),
        "root": root.as_posix(),
        "ready": ready,
        "decision": "REAL_READINESS_READY" if ready else "REAL_READINESS_BLOCKED",
        "current_evidence_context": current_evidence_context(root),
        "claim_boundary": (
            "REAL_READINESS_READY means local static contracts, command checks, clean "
            "release state, and current cross-plane evidence context passed this gate. "
            "It does not prove live customer traffic, external DPI bypass, payment "
            "settlement finality, or production SLOs without their own evidence."
        ),
        "summary": {
            "checks_total": len(checks),
            "passed": sum(1 for check in checks if check.status == STATUS_PASS),
            "warnings": len(warnings),
            "failures": len(failures),
        },
        "checks": [asdict(check) for check in checks],
        "blockers": [asdict(check) for check in failures],
    }


def render_markdown(report: Mapping[str, object]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    lines = [
        "# x0tta6bl4 Real-Readiness Gate",
        "",
        f"- decision: `{report.get('decision')}`",
        f"- ready: `{report.get('ready')}`",
        f"- timestamp_utc: `{report.get('timestamp_utc')}`",
        f"- checks_total: `{summary.get('checks_total')}`",
        f"- passed: `{summary.get('passed')}`",
        f"- warnings: `{summary.get('warnings')}`",
        f"- failures: `{summary.get('failures')}`",
        "",
        "## Checks",
        "",
        "| status | check | details | evidence |",
        "|---|---|---|---|",
    ]
    checks = report.get("checks", [])
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, Mapping):
                continue
            details = str(item.get("details", "")).replace("|", "\\|")
            evidence = str(item.get("evidence", "")).replace("|", "\\|")
            lines.append(
                f"| `{item.get('status')}` | `{item.get('check_id')}` | {details} | `{evidence}` |"
            )
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check current x0tta6bl4 real-readiness contracts")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--write-json", nargs="?", const=DEFAULT_OUTPUT_JSON, help="Write JSON report")
    parser.add_argument("--write-md", nargs="?", const=DEFAULT_OUTPUT_MD, help="Write Markdown report")
    parser.add_argument("--skip-command-checks", action="store_true", help="Skip docker/node/alembic command checks")
    parser.add_argument("--skip-git-check", action="store_true", help="Skip clean worktree check")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root,
        include_command_checks=not args.skip_command_checks,
        include_git_check=not args.skip_git_check,
    )

    if args.write_json:
        _write(root / args.write_json, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.write_md:
        _write(root / args.write_md, render_markdown(report))
    if args.json or not (args.write_json or args.write_md):
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report["ready"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
