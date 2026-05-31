from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from scripts.ops.check_real_readiness import CommandResult, build_report, check_git_state


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ready_root(root: Path) -> None:
    _write(root, "Caddyfile.app", "handle /api/* {\n    reverse_proxy localhost:8081\n}\n")
    _write(
        root,
        "docker-compose.app.yml",
        """
services:
  x0tta6bl4-app:
    environment:
      PORT: "8081"
      CORE_API_PORT: "8083"
      DATABASE_URL: ${DATABASE_URL:?set DATABASE_URL}
      ADMIN_USER: ${ADMIN_USER:?set ADMIN_USER}
      ADMIN_PASS: ${ADMIN_PASS:?set ADMIN_PASS}
""",
    )
    _write(
        root,
        "docker-compose.ghost-vpn.yml",
        """
services:
  ghost-vpn-server:
    environment:
      GHOST_VPN_AUTH_KEY: ${GHOST_VPN_AUTH_KEY:?set GHOST_VPN_AUTH_KEY}
  grafana:
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?set GRAFANA_PASSWORD}
""",
    )
    _write(
        root,
        "docker-compose.spire.yml",
        """
services:
  spire-agent:
    volumes:
      - ${SPIRE_AGENT_SOCKET_DIR:-/tmp/x0tta6bl4-spire-agent}:/spire-agent-socket-dir
  x0tta6bl4-test:
    environment:
      SPIFFE_ENDPOINT_SOCKET: unix:///spire-agent-socket-dir/api.sock
    volumes:
      - ${SPIRE_AGENT_SOCKET_DIR:-/tmp/x0tta6bl4-spire-agent}:/spire-agent-socket-dir:ro
""",
    )
    _write(
        root,
        "scripts/spire/start-spire.sh",
        """
SPIRE_AGENT_SOCKET_DIR="${X0TTA6BL4_SPIRE_AGENT_SOCKET_DIR:-${SPIRE_AGENT_SOCKET_DIR:-${XDG_RUNTIME_DIR:-/tmp}/x0tta6bl4-spire-agent}}"
install -d -m 700 "$SPIRE_AGENT_SOCKET_DIR"
if [ -S "$SPIRE_AGENT_SOCKET_DIR/api.sock" ]; then echo ready; fi
""",
    )
    _write(
        root,
        "scripts/spire/SPIRE_SETUP.md",
        """
The socket directory is private.
mode
`0700`
install -d -m 700 "${SPIRE_AGENT_SOCKET_DIR:-${XDG_RUNTIME_DIR:-/tmp}/x0tta6bl4-spire-agent}"
""",
    )
    _write(
        root,
        "src/security/spire_integration.py",
        """
def default_spire_agent_socket_path():
    return "x0tta6bl4-spire-agent/api.sock"
""",
    )
    _write(
        root,
        "src/security/spiffe/production_integration.py",
        """
def default_spire_workload_socket():
    return "x0tta6bl4-spire-agent/api.sock"
""",
    )
    _write(
        root,
        "src/security/spiffe/agent/join_token_guard.py",
        """
import hashlib
import threading

JOIN_TOKEN_GUARD_CLAIM_BOUNDARY = "Local SPIRE join-token replay/race guard evidence only"

class JoinTokenReplayGuard:
    def __init__(self):
        self._lock = threading.Lock()
        self._seen_hashes = set()
        self._inflight_hashes = set()

    def reserve(self, token):
        token_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if token_sha256 in self._inflight_hashes:
            reason = "join_token_attestation_inflight"
        if token_sha256 in self._seen_hashes:
            reason = "join_token_replay_detected"
        return {
            "token_sha256": token_sha256,
            "live_spiffe_svid_claim_allowed": False,
            "production_spire_mtls_claim_allowed": False,
            "production_trust_finality_claim_allowed": False,
            "fail_closed": True,
        }

    def complete(self, token, success):
        token_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self._seen_hashes.add(token_sha256)
        self._inflight_hashes.discard(token_sha256)
""",
    )
    _write(
        root,
        "src/security/spiffe/agent/manager.py",
        """
from src.security.spiffe.agent.join_token_guard import JoinTokenReplayGuard

class SPIREAgentManager:
    def __init__(self):
        self.join_token_guard = JoinTokenReplayGuard()

    def attest_node(self, token):
        guard_decision = self.join_token_guard.reserve(token)
        if not guard_decision.accepted:
            stage = "join_token_guard_blocked"
        context = {
            "attestation_guard": guard_decision.to_safe_context(),
        }
        success = False
        try:
            success = True
            return success
        finally:
            self.join_token_guard.complete(token, success=success)
""",
    )
    _write(
        root,
        "src/network/ebpf/telemetry/models.py",
        """
class TelemetryConfig:
    max_dropped_events_healthy: int = 0
    max_drop_ratio_healthy: float = 0.0
""",
    )
    _write(
        root,
        "src/network/ebpf/telemetry/perf_reader.py",
        """
EBPF_EVENT_LOSS_CLAIM_BOUNDARY = "telemetry blind spot"

class PerfBufferReader:
    def get_loss_health(self):
        loss_detected = True
        blockers = [
            "perf_buffer_events_dropped",
            "perf_buffer_drop_ratio_exceeded",
            "perf_buffer_parse_errors",
        ]
        return {
            "event_loss_detected": loss_detected,
            "observability_integrity_claim_allowed": not loss_detected,
            "blockers": blockers,
        }
""",
    )
    _write(
        root,
        "src/network/ebpf/telemetry/collector.py",
        """
class EBPFTelemetryCollector:
    def get_health_status(self):
        perf_loss = self.perf_reader.get_loss_health()
        return {
            "claim_gate": {
                "decision": "EBPF_TELEMETRY_UNHEALTHY_FAIL_CLOSED",
                "complete_attack_absence_claim_allowed": False,
                "production_security_coverage_claim_allowed": False,
                "fail_closed": True,
            }
        }
""",
    )
    _write(
        root,
        "src/network/ebpf/map_freeze_guard.py",
        """
import subprocess

EBPF_MAP_FREEZE_CLAIM_BOUNDARY = "Local eBPF map-freeze action evidence only"

def _validate_map_name(map_name):
    return bool(map_name)

def build_bpftool_map_freeze_command(map_name):
    if not _validate_map_name(map_name):
        raise ValueError("invalid_map_name")
    return ["bpftool", "map", "freeze", "name", map_name]

def freeze_map_by_name(map_name):
    try:
        subprocess.run(
            build_bpftool_map_freeze_command(map_name),
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        reason = "bpftool_unavailable"
    except TimeoutError:
        reason = "bpftool_timeout"
    except Exception:
        reason = "bpftool_freeze_failed"
    return {
        "map_poisoning_prevention_claim_allowed": False,
        "complete_kernel_tamper_resistance_claim_allowed": False,
        "production_security_coverage_claim_allowed": False,
        "fail_closed": True,
    }
""",
    )
    _write(
        root,
        "Dockerfile.vpn",
        "COPY services/nl-server/ghost-vpn/ghost_vpn_protocol.py src/network/ghost_vpn_protocol.py\n",
    )
    _write(
        root,
        "x0tta6bl4-app/Dockerfile",
        "EXPOSE 8081\nHEALTHCHECK CMD curl -f http://localhost:8081/api/status || exit 1\n",
    )
    _write(
        root,
        "x0tta6bl4-app/server.cjs",
        """
function requiredEnv(name) { return process.env[name]; }
function parsePort(name, defaultValue) { return defaultValue; }
function poolConfigFromEnv() { return {}; }
const PORT = parsePort('PORT', '8081');
const CORE_API_PORT = parsePort('CORE_API_PORT', '8083');
const USER = requiredEnv('ADMIN_USER');
const PASS = requiredEnv('ADMIN_PASS');
""",
    )
    _write(
        root,
        "x0tta6bl4-app/src/App.tsx",
        "const API_URL = (import.meta.env.VITE_API_BASE || '/api').replace(/\\/$/, '');\n",
    )
    _write(
        root,
        "x0tta6bl4-app/vite.config.ts",
        "export default { server: { proxy: { '/api': { target: 'http://localhost:8081' } } } };\n",
    )
    _write(
        root,
        "x0tta6bl4-app/.env.example",
        "VITE_API_BASE=/api\nDATABASE_URL=\nADMIN_USER=\nADMIN_PASS=\nPORT=8081\nCORE_API_HOST=localhost\nCORE_API_PORT=8083\n",
    )
    _write(root, "alembic/env.py", "")
    _write(
        root,
        "alembic/versions/d7c8f1a2b3c4_add_hashed_api_keys.py",
        "op.add_column('users', sa.Column('api_key_hash', sa.String()))\nop.create_index('ix_users_api_key_hash', 'users', ['api_key_hash'])\n",
    )
    _write(
        root,
        "src/database/__init__.py",
        """
class User:
    api_key_hash = Column(String, unique=True, index=True, nullable=True)
def get_schema_parity_report(): pass
def get_alembic_head_gaps(): pass
def get_schema_compatibility_gaps(): pass
def ensure_schema_compatible(): pass
""",
    )
    _write(
        root,
        "src/services/maas_auth_service.py",
        "db.query(User).filter(User.api_key_hash == ApiKeyManager.hash_key(api_key)).first()\nuser.api_key = None\n",
    )
    _write(root, "src/api/maas_security.py", "hashlib.sha256(key.encode(\"utf-8\")).hexdigest()\n")
    _write(root, "scripts/check_orm_schema_parity.py", "from src.database import get_schema_parity_report\n")
    _write(
        root,
        "services/nl-server/ghost-vpn/ghost_vpn_protocol.py",
        'AUTH_KEY_ENV = "GHOST_VPN_AUTH_KEY"\n',
    )
    _write(
        root,
        "scripts/ops/run_ghost_pulse_proof_gate.py",
        """
CURRENT_RUNTIME_CLAIM_ID = "current_runtime_attached"
RUNTIME_INTERFACE_ENV = "GHOST_PULSE_RUNTIME_INTERFACE"
current_runtime_provider = object()
production_ready = all_verified and current_runtime_verified
claim_boundary = {"current_runtime_attached": current_runtime_verified}
""",
    )
    _write(
        root,
        "src/network/transport/pulse_transport.py",
        """
PULSE_LOCAL_CLAIM_BOUNDARY = "local timing evidence only"

class PulseUDPTransport:
    def __init__(self, pulse_seed=None):
        self.pulse_seed = pulse_seed

    @staticmethod
    def timing_plan_replay_digest(samples):
        return "digest"

    @staticmethod
    def timing_plan_replay_projection(samples):
        return {"sample_count": len(samples)}

    def get_stats(self):
        return {
            "evidence_status": "EXPERIMENTAL_LOCAL_TIMING_PROFILE",
            "stealth_mode": "NOT_VERIFIED",
            "production_ready": False,
            "timing_plan_samples": [],
            "timing_plan_samples_tail": [],
            "timing_plan_summary": {},
            "timing_plan_replay": {},
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }
""",
    )
    _write(
        root,
        "src/network/obfuscation/whitelist_mimicry.py",
        """
WHITELIST_MIMICRY_CLAIM_BOUNDARY = "local descriptor only"

def build_whitelist_mimicry_profile():
    return {
        "provider_whitelist_confirmed": False,
        "external_dpi_tested": False,
        "claim_boundary": WHITELIST_MIMICRY_CLAIM_BOUNDARY,
    }
""",
    )
    _write(
        root,
        "src/network/ebpf/x0tta6bl4_pulse.bpf.c",
        """
/* static source marker only; not attached proof and not production readiness proof */
int xdp_x0tta6bl4_pulse(void *ctx) { return 2; }
""",
    )
    _write(
        root,
        "ghost-core.sh",
        """
echo "x0tta6bl4_pulse_status=LOCAL_EXPERIMENT_NOT_PRODUCTION_PROOF"
echo "dpi_bypass_confirmed=false"
echo "production_ready=false"
""",
    )
    _write(
        root,
        "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md",
        """
Status: `LOCAL_EXPERIMENT_NOT_PRODUCTION_PROOF`

This local experiment does not prove external DPI bypass.
It does not prove provider whitelist behavior.
It does not prove production readiness.
""",
    )
    _write(
        root,
        "scripts/ops/verify_ghost_pulse_rng_replay.py",
        """
from src.network.transport.pulse_transport import PulseUDPTransport

def verify():
    PulseUDPTransport.timing_plan_replay_digest([])
    PulseUDPTransport.timing_plan_replay_projection([])
""",
    )
    _write(
        root,
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
        """
def build_report():
    seed_replay_verifier = "scripts/ops/verify_ghost_pulse_rng_replay.py"
    return {"decision": "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED", "seed_replay_verifier": seed_replay_verifier}
""",
    )
    _write(
        root,
        "src/mesh/action_enforcer.py",
        """
_POST_ACTION_PROBE_ENV_VAR = "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE"
mesh_metric_policy_allows_high_risk = object()
def _env_bool(name, default=False): return default
def _claim_boundary_summary(value):
    return {
        "claim_boundaries": ["bounded dataplane probe evidence only"],
        "claim_boundaries_total": 1,
        "claim_boundaries_truncated": False,
    }
def _post_action_dataplane_revalidation_summary():
    return {
        "post_action_dataplane_revalidated": False,
        "restored_dataplane_claim_allowed": False,
        "claim_gate": {"restored_dataplane_claim_allowed": False},
        "downstream_evidence": {
            "claim_boundaries": ["bounded dataplane probe evidence only"],
        },
    }
def _publish_event():
    blocked_by_metric_evidence_policy = True
    downstream_evidence = {
        "claim_boundaries": ["bounded dataplane probe evidence only"],
    }
    return {
        "downstream_evidence": {
            "claim_boundaries": downstream_evidence.get("claim_boundaries", []),
        }
    }
class MeshActionEnforcer:
    def _post_action_probe_enabled(self):
        return _env_bool(_POST_ACTION_PROBE_ENV_VAR, False)
""",
    )
    _write(
        root,
        "src/mesh/metric_evidence_policy.py",
        """
DECISION_DATAPLANE_CONFIRMED = "dataplane_confirmed"
DECISION_ESTIMATE_OR_FALLBACK = "estimate_or_fallback_based"
HIGH_RISK_ALLOWED_DECISION_BASES = {
    DECISION_DATAPLANE_CONFIRMED,
}

def build_mesh_metric_evidence_policy(raw_metrics):
    estimated_samples = 1.0
    fallback_samples = 0.0
    if False:
        pass
    elif estimated_samples > 0.0 or fallback_samples > 0.0:
        decision_basis = DECISION_ESTIMATE_OR_FALLBACK
        control_risk = "blocked"
        allows_high_risk = False
    return {
        "decision_basis": decision_basis,
        "control_risk": control_risk,
        "allows_high_risk_mesh_actions": allows_high_risk,
    }
""",
    )
    _write(
        root,
        "src/api/maas_nodes.py",
        """
def _mesh_healing_post_action_revalidation():
    return {
        "post_action_dataplane_revalidation": {},
        "reason": "no_bounded_post_action_dataplane_probe_attached",
        "restored_dataplane_claim_allowed": False,
    }
async def heal_node():
    return {
        "post_action_dataplane_revalidation": _mesh_healing_post_action_revalidation(),
        "restored_dataplane_claim_allowed": False,
}
""",
    )
    _write(
        root,
        "src/self_healing/recovery/executor.py",
        """
_POST_ACTION_PROBE_ENV_VAR = "X0TTA6BL4_RECOVERY_POST_ACTION_PROBE"
_DATAPLANE_REVALIDATED_ACTION_TYPES = {"restart_service", "switch_route"}
POST_ACTION_DATAPLANE_REVALIDATION_CLAIM_BOUNDARY = "bounded post-action dataplane evidence only"
CLAIM_BOUNDARY = "local recovery action event only"

def _post_action_dataplane_claim_gate(
    *,
    probe_attempted,
    dataplane_confirmed,
    evidence,
    required,
):
    restored_dataplane_claim_allowed = False
    return {
        "required_for_restored_dataplane_claim": required,
        "restored_dataplane_claim_allowed": restored_dataplane_claim_allowed,
        "required_evidence": {
            "probe_attempted": True,
            "dataplane_confirmed": True,
            "redacted_evidence": True,
        },
        "observed_evidence": {
            "probe_attempted": probe_attempted,
            "dataplane_confirmed": dataplane_confirmed,
        },
    }

def _post_action_dataplane_revalidation_summary():
    claim_gate = _post_action_dataplane_claim_gate(
        probe_attempted=False,
        dataplane_confirmed=False,
        evidence={"redacted": True},
        required=True,
    )
    return {
        "post_action_dataplane_revalidated": False,
        "dataplane_confirmed": False,
        "restored_dataplane_claim_allowed": False,
        "claim_gate": claim_gate,
    }

def _recovery_claim_gate(result, post_action_dataplane_revalidation):
    restored_dataplane_claim_allowed = False
    return {
        "restored_dataplane_claim_allowed": restored_dataplane_claim_allowed,
        "production_readiness_claim_allowed": False,
        "live_customer_traffic_confirmed": False,
        "operator_approval_confirmed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
    }

def publish():
    post_action_revalidation = _post_action_dataplane_revalidation_summary()
    result = object()
    return {
        "post_action_dataplane_revalidation": post_action_revalidation,
        "claim_gate": _recovery_claim_gate(result, post_action_revalidation),
        "production_readiness_claim_allowed": False,
        "live_customer_traffic_confirmed": False,
        "operator_approval_confirmed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
    }
""",
    )
    _write(
        root,
        "src/self_healing/ebpf_anomaly_detector.py",
        """
EBPF_CLAIM_BOUNDARY = "local eBPF self-healing action event only"
EBPF_RECOVERY_CLAIM_GATE_SCHEMA = "x0tta6bl4.self_healing.ebpf_recovery_claim_gate.v1"

def _ebpf_recovery_claim_gate(result):
    return {
        "schema": EBPF_RECOVERY_CLAIM_GATE_SCHEMA,
        "restored_dataplane_claim_allowed": False,
        "route_convergence_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

payload = {
    "claim_gate": _ebpf_recovery_claim_gate(result),
    "restored_dataplane_claim_allowed": False,
    "route_convergence_claim_allowed": False,
    "kernel_forwarding_correctness_claim_allowed": False,
    "dataplane_delivery_claim_allowed": False,
    "traffic_delivery_claim_allowed": False,
    "production_readiness_claim_allowed": False,
}
""",
    )
    for app_path in ("src/core/app.py", "src/libx0t/core/app.py"):
        _write(
            root,
            app_path,
            """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

def _mesh_api_claim_gate(operation):
    return {
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _health_api_claim_gate(surface):
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _health_api_response(payload, *, surface):
    return {
        **payload,
        "health_api_claim_gate": _health_api_claim_gate(surface),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface=surface,
        ),
    }

def _metrics_api_claim_boundary_headers():
    return {
        "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.metrics_api_claim_boundary_headers.v1",
        "X-X0TTA6BL4-Local-Metrics-Observation-Claim-Allowed": "true",
        "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
        "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
        "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
        "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
        "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
        "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
        "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    }

def metrics():
    return Response(headers=_metrics_api_claim_boundary_headers())

def _status_api_claim_gate():
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _status_api_response(status_data):
    return {
        **status_data,
        "status_api_claim_gate": _status_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="status_api",
        ),
    }

def _call_yggdrasil_with_api_evidence():
    return {
        "mesh_api_claim_gate": _mesh_api_claim_gate("status"),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["dataplane_delivery"],
            surface="mesh_api.status",
        ),
    }
""",
        )
    for production_system_path in (
        "src/core/production_system.py",
        "src/libx0t/core/production_system.py",
    ):
        _write(
            root,
            production_system_path,
            """
from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata

PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
PRODUCTION_SYSTEM_CLAIM_BOUNDARY = (
    "cross-plane proof gate allows the requested strong claims"
)

class ProductionSystem:
    def _cross_plane_proof_gate_context(self):
        try:
            gate = readiness_cross_plane_claim_gate_metadata(
                surface="production_system.readiness",
                root=".",
                claims=PRODUCTION_SYSTEM_CROSS_PLANE_CLAIMS,
            )
        except Exception:
            return {
                "allowed": False,
                "blockers": ["cross_plane_proof_gate_error:Exception"],
            }
        if readiness_cross_plane_claim_gate_metadata is None:
            return {
                "allowed": False,
                "blockers": ["cross_plane_proof_gate_unavailable"],
            }
        if not isinstance(gate, dict):
            return {
                "allowed": False,
                "blockers": ["cross_plane_proof_gate_invalid_response"],
            }
        return gate

    def get_production_readiness_report(self):
        cross_plane_proof_gate = self._cross_plane_proof_gate_context()
        cross_plane_proof_gate_allows = (
            cross_plane_proof_gate.get("allowed") is True
        )
        production_readiness_claim_allowed = (
            cross_plane_proof_gate_allows
        )
        readiness_level = "PRODUCTION_READY_BLOCKED_BY_CROSS_PLANE_PROOF_GATE"
        return {
            "readiness_level": readiness_level,
            "production_readiness_claim_allowed": (
                production_readiness_claim_allowed
            ),
            "cross_plane_proof_gate": cross_plane_proof_gate,
        }
""",
        )
    _write(
        root,
        "tests/integration/production_readiness.py",
        """
CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
PRODUCTION_READINESS_CHECKLIST_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)

def _current_evidence_context(root):
    return {}

def _current_evidence_gate_clear(context):
    return True

def _cross_plane_proof_gate_allowed(data, missing_claim_ids=None):
    return True

def _cross_plane_proof_gate_blocker_ids(data, missing_claim_ids=None):
    return []

def _cross_plane_proof_gate_context(root):
    return {"allowed": True, "blocker_ids": [], "source_artifact_hashes_present": True}

raw_checklist_ready = True
current_evidence_clear = True
current_evidence = _current_evidence_context(None)
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_clear = cross_plane_proof_gate.get("allowed") is True
is_ready = raw_checklist_ready and current_evidence_clear and cross_plane_proof_gate_clear
report = {
    "raw_checklist_ready": raw_checklist_ready,
    "current_evidence_gate_clear": current_evidence_clear,
    "current_evidence_context": current_evidence,
    "cross_plane_proof_gate_clear": cross_plane_proof_gate_clear,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "cross_plane_claim_gate": {
        "production_readiness_claim_allowed": is_ready,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_clear,
        "proof_claims": {
            "production_ready": False,
            "live_apply_authorized": False,
            "goal_completion_authorized": False,
        },
    },
    "claim_boundary": "reusable cross-plane proof gate allows the requested strong claims",
}
""",
    )
    _write(
        root,
        "scripts/ops/audit_production_grade_goal.py",
        """
from scripts.ops.run_cross_plane_proof_gate import (
    build_report as build_cross_plane_proof_gate_report,
)

PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
PROTECTED_CURRENT_EVIDENCE_OUTPUTS = {
    "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
    "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
}

def _guard_output_path(root, value, *, flag):
    raise SystemExit(f"{flag} must not overwrite current evidence source artifact")

def _cross_plane_proof_gate_context(root):
    try:
        cross_plane_proof_gate = build_cross_plane_proof_gate_report(
            root,
            claims=PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS,
        )
    except Exception:
        return {
            "allowed": False,
            "blockers": ["cross_plane_proof_gate_error:Exception"],
        }
    if build_cross_plane_proof_gate_report is None:
        return {
            "allowed": False,
            "blockers": ["cross_plane_proof_gate_unavailable"],
        }
    if not isinstance(cross_plane_proof_gate, dict):
        return {
            "allowed": False,
            "blockers": ["cross_plane_proof_gate_invalid_response"],
        }
    return cross_plane_proof_gate

def _cross_plane_proof_gate_blocker_ids(cross_plane_proof_gate):
    blockers = []
    for result in cross_plane_proof_gate.get("claim_results") or []:
        blockers.append("claim_blocked:" + str(result.get("claim_id")))
    return blockers

def _next_actions(cross_plane_proof_gate_action_required=False):
    if cross_plane_proof_gate_action_required:
        return [{"id": "clear_cross_plane_proof_gate"}]
    return []

def build_report(root):
    args = type("Args", (), {"output_json": "out.json", "output_md": "out.md"})()
    _guard_output_path(root, args.output_json, flag="--output-json")
    _guard_output_path(root, args.output_md, flag="--output-md")
    cross_plane_proof_gate = _cross_plane_proof_gate_context(root)
    cross_plane_proof_gate_clear = cross_plane_proof_gate.get("allowed") is True
    requirements_complete = True
    current_evidence_clear = True
    complete = requirements_complete and current_evidence_clear and cross_plane_proof_gate_clear
    return {
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "summary": {
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_clear,
        },
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "claim_boundary": "reusable cross-plane proof gate",
        "next_actions": _next_actions(
            cross_plane_proof_gate_action_required=not cross_plane_proof_gate_clear
        ),
    }
""",
    )
    _write(
        root,
        "src/integration/objective_coverage_audit.py",
        """
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
REQUIRED_GOAL_AUDIT_ROWS = {"goal_audit:cross_plane_proof_gate"}

class ArtifactSpec:
    def __init__(self, key, path):
        self.key = key
        self.path = path

class RowSpec:
    def __init__(self, *args):
        self.args = args

def _cross_plane_proof_gate_command():
    return f"python3 scripts/ops/run_cross_plane_proof_gate.py --json --require-allowed --output-json {DEFAULT_CROSS_PLANE_PROOF_GATE}"

def _cross_plane_proof_gate_blocker_ids(data):
    return ["claim_blocked:production_readiness"]

def _cross_plane_proof_gate_allowed(data):
    claim_results = {"production_readiness": {"allowed": True}}
    return (
        data.get("decision") == CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION
        and data.get("allowed") is True
        and all(claim_results[claim_id].get("allowed") is True for claim_id in claim_results)
    )

def build_report(root):
    specs = [ArtifactSpec("cross_plane_proof_gate", DEFAULT_CROSS_PLANE_PROOF_GATE)]
    cross_plane_gate_allowed = _cross_plane_proof_gate_allowed({})
    cross_plane_gate_blocker_ids = _cross_plane_proof_gate_blocker_ids({})
    row = RowSpec(
        "goal_audit:cross_plane_proof_gate",
        "cross-plane proof gate has not allowed objective strong claims",
    )
    return {
        "claim_boundary": "reusable cross-plane proof gate",
        "source_artifacts": [spec.path for spec in specs],
        "prompt_to_artifact_checklist": [row],
        "summary": {
            "cross_plane_proof_gate_allowed": cross_plane_gate_allowed,
            "cross_plane_proof_gate_blocker_ids": cross_plane_gate_blocker_ids,
        },
        "next_actions": [
            {"id": "clear_cross_plane_proof_gate", "command": _cross_plane_proof_gate_command()}
        ],
    }
""",
    )
    _write(
        root,
        "src/network/yggdrasil_client.py",
        """
import time
from typing import Optional
from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY = (
    "Read-only local yggdrasilctl observation; it does not prove remote peer authenticity."
)

def _has_yggdrasil_output_failure(stdout=None, stderr=None):
    return False

class YggdrasilCommandOutputError(RuntimeError):
    pass

def _bounded_output_metadata(stdout, stderr):
    return {
        "stdout_sha256": "hash",
        "stderr_sha256": "hash",
        "output_bounded": True,
        "output_redacted": True,
    }

def _identity_metadata():
    identity = service_event_identity(service_name="yggdrasil-client")
    return {
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
    }

def _evidence_metadata(event_id):
    return {"payloads_redacted": True, "redacted": True}

def _with_evidence(payload, event_id, include_evidence=False):
    return payload

def _publish_yggdrasil_observation(
    event_bus,
    operation,
    command,
    returncode=None,
    duration_ms=0.0,
    stdout=None,
    stderr=None,
    parsed_summary=None,
):
    payload = {
        "layer": "network_yggdrasil_observed_state",
        "operation": operation,
        "returncode": returncode,
        "duration_ms": duration_ms,
        "identity": _identity_metadata(),
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "parsed_summary": parsed_summary or {},
        "output": _bounded_output_metadata(stdout, stderr),
    }
    if event_bus is not None:
        event_bus.publish(EventType.PIPELINE_STAGE_END, "yggdrasil-client", payload)

def get_yggdrasil_status(
    *,
    event_bus: Optional[EventBus] = None,
    include_evidence: bool = False,
):
    command=["yggdrasilctl", "getSelf"]
    started = time.monotonic()
    duration_ms = (time.monotonic() - started) * 1000.0
    result = type("Result", (), {"returncode": 0})()
    _publish_yggdrasil_observation(
        event_bus,
        operation="get_self",
        command=command,
        returncode=result.returncode,
        duration_ms=duration_ms,
        parsed_summary={"node_field_count": 1},
    )
    returncode = 1
    _publish_yggdrasil_observation(
        event_bus,
        operation="get_self",
        command=command,
        returncode=returncode,
        duration_ms=duration_ms,
    )
    return _with_evidence({"status": "online"}, None, include_evidence=include_evidence)

def get_yggdrasil_peers(
    *,
    event_bus: Optional[EventBus] = None,
    include_evidence: bool = False,
):
    command=["yggdrasilctl", "getPeers"]
    started = time.monotonic()
    duration_ms = (time.monotonic() - started) * 1000.0
    result = type("Result", (), {"returncode": 0})()
    _publish_yggdrasil_observation(
        event_bus,
        operation="get_peers",
        command=command,
        returncode=result.returncode,
        duration_ms=duration_ms,
        parsed_summary={"peer_count": 0},
    )
    return _with_evidence({"status": "ok"}, None, include_evidence=include_evidence)
""",
    )
    _write(
        root,
        "src/libx0t/network/yggdrasil_client.py",
        """
from src.network import yggdrasil_client as _impl

def _publish(**kwargs):
    return _impl._publish_yggdrasil_observation(**kwargs)

def _evidence_metadata(event_id):
    return {"claim_boundary": _impl.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY}

def get_yggdrasil_status(**kwargs):
    return _impl.get_yggdrasil_status(**kwargs)

def get_yggdrasil_peers(**kwargs):
    return _impl.get_yggdrasil_peers(**kwargs)
""",
    )
    _write(
        root,
        "src/mesh/telemetry_collector.py",
        """
def _safe_evidence_claim_boundaries(value):
    return [value.get("evidence", {}).get("claim_boundary")]

def get_yggdrasil_downstream_evidence(peers_data):
    peers_data = get_yggdrasil_peers(
        event_bus=None,
        event_project_root=".",
        include_evidence=True,
    )
    downstream_claim_boundaries = _safe_evidence_claim_boundaries(peers_data)
    return {
        "downstream_evidence": {
            "event_ids": peers_data.get("evidence", {}).get("event_ids", []),
            "claim_boundaries": downstream_claim_boundaries,
            "redacted": True,
        }
    }
""",
    )
    _write(
        root,
        "src/mesh/network_manager.py",
        """
def _evidence_summary(evidence):
    return {
        "event_ids": evidence.get("event_ids", []),
        "claim_boundaries": [evidence.get("claim_boundary")],
        "redacted": True,
    }

def get_statistics():
    peer_data = get_yggdrasil_peers(
        event_bus=None,
        event_project_root=".",
        include_evidence=True,
    )
    yggdrasil_evidence_summary = _evidence_summary(peer_data.get("evidence", {}))
    downstream_claim_boundaries = yggdrasil_evidence_summary["claim_boundaries"]
    return {
        "downstream_evidence": {
            "event_ids": yggdrasil_evidence_summary["event_ids"],
            "claim_boundaries": downstream_claim_boundaries,
            "redacted": True,
        }
    }
""",
    )
    _write(
        root,
        "src/core/mape_k_loop.py",
        """
def _transitive_downstream_evidence(mesh_event_payloads):
    downstream_claim_boundaries = []
    return {
        "yggdrasil-client": {
            "event_ids": ["event-1"],
            "claim_boundaries": downstream_claim_boundaries,
            "claim_boundaries_total": len(downstream_claim_boundaries),
            "redacted": True,
        }
    }

def _terminal_event_payloads_by_source(bus, source_agents):
    return {}

def _downstream_evidence_delta(before, after, event_payloads_by_source=None):
    return {
        "claim_boundaries": ["bounded dataplane probe evidence only"],
        "claim_boundaries_total": 1,
        "redacted": True,
    }

def _apply_mesh_metric_evidence_policy(directives, raw_metrics):
    blocked_high_risk_mesh_actions = ["mesh_optimization"]
    directives["blocked_high_risk_mesh_actions"] = blocked_high_risk_mesh_actions
    directives["mesh_high_risk_actions_blocked"] = True
    return directives

MAPEK_SAFE_MODE_CLAIM_BOUNDARY = "Safe-mode blocks route, healing, scaling, DAO dispatch"

def _safe_mode_directives(reason_id, dependency):
    self.safe_mode_active = True
    return {
        "safe_mode": True,
        "safe_mode_final_state": "control_actions_blocked",
        "safe_mode_reason_id": reason_id,
        "production_readiness_claim_allowed": False,
    }

def _publish_safe_mode_event(directives):
    self._publish_control_event(
        operation="enter_safe_mode",
        stage="safe_mode_entered",
    )

def _execute(directives):
    if directives.get("safe_mode"):
        _publish_safe_mode_event(directives)
        reason_id = "planning_failed"
        return [f"safe_mode={reason_id}"]

def _execute_cycle():
    try:
        directives = self._plan(consciousness_metrics)
    except Exception:
        directives = self._safe_mode_directives(
            reason_id="planning_failed",
            dependency="planner",
        )
    try:
        self._knowledge(consciousness_metrics, directives, actions_taken, raw_metrics)
    except Exception:
        self._safe_mode_directives(
            reason_id="knowledge_phase_failed",
            dependency="knowledge",
        )

def _log_to_dao(state):
    try:
        cid = dao_logger.log_consciousness_event(event_data)
    except Exception:
        safe_directives = self._safe_mode_directives(
            reason_id="cid_log_failed",
            dependency="cid_audit_log",
        )
        self._publish_safe_mode_event(directives=safe_directives)
""",
    )
    _write(
        root,
        "src/api/maas/models.py",
        """
class MeshDeployResponse:
    mesh_deploy_claim_gate = {}
    mesh_provisioner_claim_gate = {}
    provisioner_cross_plane_claim_gate = {}
    cross_plane_claim_gate = {}

class MeshStatusResponse:
    mesh_lifecycle_claim_gate = {}
    cross_plane_claim_gate = {}

class MeshMetricsResponse:
    mesh_metrics_claim_gate = {}
    cross_plane_claim_gate = {}
""",
    )
    _write(
        root,
        "src/api/maas/endpoints/mesh.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

_MESH_DEPLOY_CROSS_PLANE_CLAIMS = ("production_readiness",)
_MESH_DEPLOY_RESPONSE_CLAIM_BOUNDARY = "local modular deploy response only"
_MESH_LIFECYCLE_CROSS_PLANE_CLAIMS = ("production_readiness",)
_MESH_LIFECYCLE_RESPONSE_CLAIM_BOUNDARY = "local modular lifecycle response only"
_MESH_READ_LIST_CLAIM_BOUNDARY = "local audit/mapek list observation only"
_MESH_READ_LIST_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_mesh_read_list_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Claim-Boundary": _MESH_READ_LIST_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}

def _claim_gate_dict(value):
    return dict(value) if isinstance(value, dict) else {}

def _mesh_deploy_claim_gate(
    provisioner_call_committed=True,
    db_write_committed=True,
    response_created=True,
    provisioner_claim_gate_present=True,
    provisioner_cross_plane_claim_gate_present=True,
):
    return {
        "local_api_deploy_request_claim_allowed": bool(response_created),
        "local_mesh_provisioner_invocation_claim_allowed": bool(
            provisioner_call_committed
        ),
        "local_db_persistence_claim_allowed": bool(db_write_committed),
        "local_join_material_returned_claim_allowed": bool(response_created),
        "provisioner_claim_gate_present": bool(provisioner_claim_gate_present),
        "provisioner_cross_plane_claim_gate_present": bool(
            provisioner_cross_plane_claim_gate_present
        ),
        "external_infrastructure_provisioning_claim_allowed": False,
        "external_node_deployment_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _mesh_deploy_cross_plane_gate():
    return cross_plane_claim_gate_metadata(
        _MESH_DEPLOY_CROSS_PLANE_CLAIMS,
        surface="maas_mesh.deploy",
    )

def _mesh_lifecycle_claim_gate(
    surface,
    read_only=True,
    control_action=False,
    registry_mutation_committed=False,
    provisioner_call_committed=False,
):
    return {
        "local_mesh_registry_read_claim_allowed": bool(read_only),
        "local_mesh_status_observation_claim_allowed": bool(read_only),
        "local_mesh_control_action_claim_allowed": bool(control_action),
        "local_mesh_registry_mutation_claim_allowed": bool(
            registry_mutation_committed
        ),
        "local_mesh_provisioner_invocation_claim_allowed": bool(
            provisioner_call_committed
        ),
        "external_infrastructure_convergence_claim_allowed": False,
        "external_node_deployment_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _mesh_lifecycle_cross_plane_gate(surface):
    return cross_plane_claim_gate_metadata(
        _MESH_LIFECYCLE_CROSS_PLANE_CLAIMS,
        surface=surface,
    )

def _attach_mesh_lifecycle_gates(result, surface):
    response = {}
    response["mesh_lifecycle_claim_gate"] = _mesh_lifecycle_claim_gate(
        surface,
        read_only=False,
        control_action=True,
        registry_mutation_committed=True,
        provisioner_call_committed=True,
    )
    response["cross_plane_claim_gate"] = _mesh_lifecycle_cross_plane_gate(surface)
    return response

def _mesh_read_list_claim_boundary_headers(surface):
    headers = dict(_MESH_READ_LIST_CLAIM_HEADERS)
    headers["X-X0TTA6BL4-Claim-Surface"] = surface
    return headers

def _set_mesh_read_list_claim_headers(response, surface):
    if response is not None:
        response.headers.update(_mesh_read_list_claim_boundary_headers(surface))

def _mesh_read_list_claim_boundary_summary(surface):
    return {
        "mesh_read_list_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "autonomous_remediation_completion_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _mesh_metrics_claim_gate():
    return {
        "local_mesh_metrics_observation_claim_allowed": True,
        "local_control_policy_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _mesh_metrics_summary(response):
    return {
        "mesh_metrics_claim_gate_present": True,
    }

def _mesh_response_summary(response):
    return {
        "mesh_deploy_claim_gate_present": True,
        "mesh_provisioner_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
    }

def _mesh_status_summary(response):
    return {
        "mesh_lifecycle_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
    }

def _mesh_result_summary(response):
    return {
        "mesh_lifecycle_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
    }

def _mesh_list_summary(response):
    return {
        "mesh_lifecycle_claim_gate_count": 1,
        "cross_plane_claim_gate_count": 1,
    }

def _build_mesh_status_response(instance, claim_surface="maas_mesh.status"):
    return MeshStatusResponse(
        mesh_lifecycle_claim_gate=_mesh_lifecycle_claim_gate(
            claim_surface,
            read_only=True,
            control_action=False,
        ),
        cross_plane_claim_gate=_mesh_lifecycle_cross_plane_gate(claim_surface),
    )

def list_meshes():
    return [_build_mesh_status_response(object(), claim_surface="maas_mesh.list")]

def deploy_mesh():
    instance = object()
    provisioner_claim_gate = _claim_gate_dict(
        getattr(instance, "mesh_provisioner_claim_gate", None)
    )
    provisioner_cross_plane_claim_gate = _claim_gate_dict(
        getattr(instance, "cross_plane_claim_gate", None)
    )
    return MeshDeployResponse(
        mesh_deploy_claim_gate=_mesh_deploy_claim_gate(
            provisioner_call_committed=True,
            db_write_committed=True,
            response_created=True,
            provisioner_claim_gate_present=True,
            provisioner_cross_plane_claim_gate_present=True,
        ),
        mesh_provisioner_claim_gate=provisioner_claim_gate,
        provisioner_cross_plane_claim_gate=provisioner_cross_plane_claim_gate,
        cross_plane_claim_gate=_mesh_deploy_cross_plane_gate(),
    )

def scale_mesh():
    response = _attach_mesh_lifecycle_gates(
        {},
        surface="maas_mesh.scale",
    )
    return response

def terminate_mesh():
    response = _attach_mesh_lifecycle_gates(
        {},
        surface="maas_mesh.terminate",
    )
    return response

async def get_mesh_audit(http_response: Response = None):
    _set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.audit")
    return _audit_log_summary([], returned_count=0, limit=100, claim_surface="maas_mesh.audit")

async def get_mesh_mapek(http_response: Response = None):
    _set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.mapek")
    return _mapek_events_summary([], returned_count=0, limit=100, claim_surface="maas_mesh.mapek")

def get_mesh_metrics():
    return MeshMetricsResponse(
        mesh_metrics_claim_gate=_mesh_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_mesh.metrics",
        ),
    )
""",
    )
    _write(
        root,
        "src/api/maas_compat.py",
        """
from fastapi import Response

_COMPAT_AUDIT_READ_CLAIM_BOUNDARY = "local compat audit read only"
_COMPAT_MAPEK_READ_CLAIM_BOUNDARY = "local compat mapek read only"
_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY = "local compat lifecycle read only"
_COMPAT_READ_LIST_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_read_list_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Audit-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Event-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Complete-Historical-Coverage-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed": "true",
}
_COMPAT_LIFECYCLE_READ_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_lifecycle_read_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Fresh-Dataplane-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}
_COMPAT_SCALE_CLAIM_BOUNDARY = "local compat scale control only"
_COMPAT_TERMINATE_CLAIM_BOUNDARY = "local compat terminate control only"
_COMPAT_DEPLOY_CLAIM_BOUNDARY = "local compat deploy control only"
_COMPAT_LIFECYCLE_CONTROL_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_lifecycle_control_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Node-Deployment-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Node-Shutdown-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}

def _compat_read_list_claim_boundary_headers(
    surface,
    claim_boundary,
    local_audit_log_claim_allowed=False,
    local_mapek_event_claim_allowed=False,
):
    headers = dict(_COMPAT_READ_LIST_CLAIM_HEADERS)
    headers["X-X0TTA6BL4-Claim-Surface"] = surface
    return headers

def _set_compat_read_list_claim_headers(
    response,
    surface,
    claim_boundary,
    local_audit_log_claim_allowed=False,
    local_mapek_event_claim_allowed=False,
):
    if response is not None:
        response.headers.update(
            _compat_read_list_claim_boundary_headers(
                surface=surface,
                claim_boundary=claim_boundary,
                local_audit_log_claim_allowed=local_audit_log_claim_allowed,
                local_mapek_event_claim_allowed=local_mapek_event_claim_allowed,
            )
        )

def _compat_read_list_claim_summary(surface):
    return {
        "compat_read_list_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "autonomous_remediation_completion_claim_allowed": False,
        "durable_audit_persistence_claim_allowed": False,
        "durable_event_persistence_claim_allowed": False,
        "complete_historical_coverage_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _compat_lifecycle_read_claim_boundary_headers(
    surface,
    claim_boundary,
    local_lifecycle_state_claim_allowed=False,
):
    headers = dict(_COMPAT_LIFECYCLE_READ_CLAIM_HEADERS)
    headers["X-X0TTA6BL4-Claim-Surface"] = surface
    headers["X-X0TTA6BL4-Local-Lifecycle-State-Observation-Claim-Allowed"] = "true"
    return headers

def _set_compat_lifecycle_read_claim_headers(
    response,
    surface,
    claim_boundary,
    local_lifecycle_state_claim_allowed=False,
):
    if response is not None:
        response.headers.update(
            _compat_lifecycle_read_claim_boundary_headers(
                surface=surface,
                claim_boundary=claim_boundary,
                local_lifecycle_state_claim_allowed=local_lifecycle_state_claim_allowed,
            )
        )

def _compat_lifecycle_read_claim_summary(surface):
    return {
        "compat_lifecycle_read_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "local_lifecycle_state_observation_claim_allowed": True,
        "mesh_lifecycle_claim_gate_present": True,
        "mesh_metrics_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
        "autonomous_remediation_completion_claim_allowed": False,
        "durable_lifecycle_persistence_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "fresh_dataplane_health_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def cross_plane_claim_gate_metadata(claims, surface):
    return {"surface": surface, "allowed": False, "requested_claim_ids": claims}

def _compat_lifecycle_control_claim_boundary_headers(
    surface,
    claim_boundary,
    local_registry_mutation_claim_allowed=False,
    delegated_modular_lifecycle_claim_allowed=False,
    local_audit_log_claim_allowed=False,
    local_mapek_event_claim_allowed=False,
):
    headers = dict(_COMPAT_LIFECYCLE_CONTROL_CLAIM_HEADERS)
    headers["X-X0TTA6BL4-Claim-Surface"] = surface
    headers["X-X0TTA6BL4-Local-Registry-Mutation-Claim-Allowed"] = "true"
    headers["X-X0TTA6BL4-Delegated-Modular-Lifecycle-Claim-Allowed"] = "true"
    headers["X-X0TTA6BL4-Local-Audit-Log-Append-Claim-Allowed"] = "true"
    headers["X-X0TTA6BL4-Local-MAPE-K-Event-Append-Claim-Allowed"] = "true"
    return headers

def _set_compat_lifecycle_control_claim_headers(
    response,
    surface,
    claim_boundary,
    local_registry_mutation_claim_allowed=False,
    delegated_modular_lifecycle_claim_allowed=False,
    local_audit_log_claim_allowed=False,
    local_mapek_event_claim_allowed=False,
):
    if response is not None:
        response.headers.update(
            _compat_lifecycle_control_claim_boundary_headers(
                surface=surface,
                claim_boundary=claim_boundary,
                local_registry_mutation_claim_allowed=local_registry_mutation_claim_allowed,
                delegated_modular_lifecycle_claim_allowed=delegated_modular_lifecycle_claim_allowed,
                local_audit_log_claim_allowed=local_audit_log_claim_allowed,
                local_mapek_event_claim_allowed=local_mapek_event_claim_allowed,
            )
        )

def _compat_lifecycle_control_claim_gate(surface, claim_boundary):
    return {
        "schema": "x0tta6bl4.maas_compat_lifecycle_control_claim_gate.v1",
        "surface": surface,
        "local_registry_mutation_claim_allowed": True,
        "delegated_modular_lifecycle_claim_allowed": True,
        "local_audit_log_append_claim_allowed": True,
        "local_mapek_event_append_claim_allowed": True,
        "external_node_deployment_claim_allowed": False,
        "external_node_shutdown_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "compat_lifecycle_control_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
    }

def _compat_lifecycle_control_cross_plane_gate(surface):
    return cross_plane_claim_gate_metadata(["production_readiness"], surface=surface)

_COMPAT_BILLING_PAY_CLAIM_BOUNDARY = "local compat billing checkout intent only"
_COMPAT_BILLING_PAY_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_billing_pay_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Provider-Settlement-Claim-Allowed": "false",
    "X-X0TTA6BL4-Bank-Settlement-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Subscription-Activation-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Access-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}

def _set_compat_billing_pay_claim_headers(response, surface, claim_boundary):
    if response is not None:
        response.headers.update(_COMPAT_BILLING_PAY_CLAIM_HEADERS)

def _compat_billing_pay_claim_gate(surface):
    return {
        "schema": "x0tta6bl4.maas_compat_billing_pay_claim_gate.v1",
        "surface": surface,
        "provider_settlement_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "subscription_activation_claim_allowed": False,
        "customer_access_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _compat_billing_pay_cross_plane_gate(surface):
    return cross_plane_claim_gate_metadata(["settlement_finality"], surface=surface)

def _billing_pay_result_summary_for_evidence():
    return {
        "compat_billing_pay_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
        "claim_surface": "maas_compat.billing_pay",
    }

def _deploy_result_summary_for_evidence():
    return {
        "mesh_deploy_claim_gate_present": True,
        "mesh_provisioner_claim_gate_present": True,
        "provisioner_cross_plane_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
        "compat_lifecycle_control_claim_gate_present": True,
        "compat_lifecycle_control_claim_boundary_headers_present": True,
        "claim_surface": "maas_compat.lifecycle_control.deploy",
    }

def _mesh_list_summary_for_evidence():
    return _compat_lifecycle_read_claim_summary("maas_compat.lifecycle.list")

def _mesh_status_summary_for_evidence():
    return _compat_lifecycle_read_claim_summary("maas_compat.lifecycle.status")

def _mesh_metrics_summary_for_evidence():
    return _compat_lifecycle_read_claim_summary("maas_compat.lifecycle.metrics")

def _audit_log_summary_for_evidence():
    return _compat_read_list_claim_summary("maas_compat.audit_logs")

def _mapek_event_summary_for_evidence():
    return _compat_read_list_claim_summary("maas_compat.mapek_events")

async def get_audit_logs_alias(http_response: Response = None):
    _set_compat_read_list_claim_headers(
        http_response,
        surface="maas_compat.audit_logs",
        claim_boundary=_COMPAT_AUDIT_READ_CLAIM_BOUNDARY,
        local_audit_log_claim_allowed=True,
    )
    return {"events": []}

async def get_mapek_events_alias(http_response: Response = None):
    _set_compat_read_list_claim_headers(
        http_response,
        surface="maas_compat.mapek_events",
        claim_boundary=_COMPAT_MAPEK_READ_CLAIM_BOUNDARY,
        local_mapek_event_claim_allowed=True,
    )
    return {"events": []}

async def list_meshes_alias(http_response: Response = None):
    meshes = []
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.list",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    return {"meshes": meshes, "count": len(meshes)}

async def get_mesh_status_alias(http_response: Response = None):
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.status",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    return _mesh_status_summary_for_evidence()

async def get_mesh_metrics_alias(http_response: Response = None):
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.metrics",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    return _mesh_metrics_summary_for_evidence()

async def billing_pay_alias(http_response: Response = None):
    claim_surface = "maas_compat.billing_pay"
    compat_billing_pay_claim_gate = _compat_billing_pay_claim_gate(claim_surface)
    cross_plane_claim_gate = _compat_billing_pay_cross_plane_gate(claim_surface)
    _set_compat_billing_pay_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
    )
    return {
        "payment_url": "https://checkout.example/redacted",
        "compat_billing_pay_claim_gate": compat_billing_pay_claim_gate,
        "cross_plane_claim_gate": cross_plane_claim_gate,
    }

async def deploy_mesh_alias(http_response: Response = None):
    claim_surface = "maas_compat.lifecycle_control.deploy"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        claim_surface,
        _COMPAT_DEPLOY_CLAIM_BOUNDARY,
    )
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_DEPLOY_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    return _deploy_result_summary_for_evidence()

async def scale_mesh_alias(http_response: Response = None):
    claim_surface = "maas_compat.lifecycle_control.scale"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        claim_surface,
        _COMPAT_SCALE_CLAIM_BOUNDARY,
    )
    cross_plane_claim_gate = _compat_lifecycle_control_cross_plane_gate(claim_surface)
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_SCALE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
    )
    return {
        "status": "active",
        "compat_lifecycle_control_claim_gate": compat_lifecycle_control_claim_gate,
        "cross_plane_claim_gate": cross_plane_claim_gate,
    }

async def terminate_mesh_alias(http_response: Response = None):
    claim_surface = "maas_compat.lifecycle_control.terminate"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        claim_surface,
        _COMPAT_TERMINATE_CLAIM_BOUNDARY,
    )
    cross_plane_claim_gate = _compat_lifecycle_control_cross_plane_gate(claim_surface)
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_TERMINATE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    result_payload = {"status": "terminated"}
    result_payload.update(
        {
            "compat_lifecycle_control_claim_gate": (
                compat_lifecycle_control_claim_gate
            ),
            "cross_plane_claim_gate": cross_plane_claim_gate,
        }
    )
    return result_payload
""",
    )
    _write(
        root,
        "src/api/maas_legacy.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

class MeshMetricsResponse:
    mesh_metrics_claim_gate = {}
    cross_plane_claim_gate = {}

def _legacy_mesh_metrics_claim_gate():
    return {
        "local_mesh_metrics_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _mesh_metrics_summary_for_evidence(response):
    return {
        "mesh_metrics_claim_gate_present": True,
    }

def legacy_mesh_metrics():
    return MeshMetricsResponse(
        mesh_metrics_claim_gate=_legacy_mesh_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="legacy_maas_mesh.metrics",
        ),
    )
""",
    )
    _write(
        root,
        "src/api/maas_core.py",
        """
from typing import Any, Dict
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

class Field:
    def __init__(self, default_factory=None): pass

class MeshResponse:
    maas_core_lifecycle_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)

def _maas_core_lifecycle_claim_gate(surface="maas_core.lifecycle"):
    return {
        "local_mesh_lifecycle_claim_allowed": True,
        "local_db_lifecycle_claim_allowed": True,
        "infrastructure_provisioning_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _maas_core_lifecycle_claim_boundary_headers():
    return {}

def _set_maas_core_lifecycle_claim_headers(http_response):
    pass

def deploy_mesh(http_response=None):
    _set_maas_core_lifecycle_claim_headers(http_response)
    return {
        "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
            "maas_core.lifecycle.deploy"
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_core.lifecycle.deploy",
        ),
    }

def list_meshes(http_response=None):
    _set_maas_core_lifecycle_claim_headers(http_response)
    return [{
        "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
            "maas_core.lifecycle.list"
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_core.lifecycle.list",
        ),
    }]

def terminate_mesh(http_response=None):
    _set_maas_core_lifecycle_claim_headers(http_response)
    return {
        "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
            "maas_core.lifecycle.terminate"
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_core.lifecycle.terminate",
        ),
    }
""",
    )
    _write(
        root,
        "src/api/maas_provisioning.py",
        """
from typing import Any, Dict
from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata

class Field:
    def __init__(self, default_factory=None): pass

PROVISIONING_CLAIM_BOUNDARY = "local setup only"

class ProvisionResponse:
    provisioning_setup_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)

def _provisioning_setup_claim_gate(db_write_succeeded=True):
    return {
        "local_setup_package_generation_claim_allowed": True,
        "local_join_token_generation_claim_allowed": True,
        "local_pending_node_db_write_claim_allowed": bool(db_write_succeeded),
        "install_command_executed_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "pqc_negotiation_claim_allowed": False,
        "zkp_authentication_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _provisioning_setup_cross_plane_gate(surface):
    return readiness_cross_plane_claim_gate_metadata(surface=surface)

def _provisioning_setup_claim_boundary_headers():
    return {}

def _set_provisioning_setup_claim_headers(http_response):
    pass

def _publish_provisioning_event(db_write_succeeded=True):
    return {
        "provisioning_setup_claim_gate": _provisioning_setup_claim_gate(
            db_write_succeeded=db_write_succeeded,
        ),
    }

def generate_provisioning_setup(http_response=None):
    _set_provisioning_setup_claim_headers(http_response)
    return ProvisionResponse(
        provisioning_setup_claim_gate=_provisioning_setup_claim_gate(
            db_write_succeeded=True,
        ),
        cross_plane_claim_gate=_provisioning_setup_cross_plane_gate(
            "maas_provisioning.generate_setup"
        ),
    )
""",
    )
    _write(
        root,
        "src/services/provisioning_service.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

MESH_PROVISIONING_CLAIM_BOUNDARY = "local delegate only"

def _mesh_provisioning_claim_gate(
    provisioner_available=True,
    provisioner_create_succeeded=True,
):
    return {
        "local_mesh_provisioner_delegate_claim_allowed": bool(
            provisioner_create_succeeded
        ),
        "local_mesh_lifecycle_claim_allowed": bool(provisioner_create_succeeded),
        "mesh_provisioner_available": provisioner_available is True,
        "mesh_provisioner_create_succeeded": provisioner_create_succeeded is True,
        "external_infrastructure_provisioning_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _mesh_provisioning_cross_plane_gate(surface):
    return cross_plane_claim_gate_metadata(
        ["production_readiness"],
        surface=surface,
    )

def provision_mesh():
    return {
        "mesh_provisioning_claim_gate": _mesh_provisioning_claim_gate(
            provisioner_available=True,
            provisioner_create_succeeded=True,
        ),
        "cross_plane_claim_gate": _mesh_provisioning_cross_plane_gate(
            "provisioning_service.provision_mesh"
        ),
    }
""",
    )
    _write(
        root,
        "src/api/maas/services.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

MESH_PROVISIONER_CLAIM_BOUNDARY = "local in-process instance only"

def _mesh_provisioner_claim_gate(
    plan_limit_checked=True,
    mesh_instance_created=True,
    local_node_records_seeded=True,
    registry_mutation_committed=True,
):
    return {
        "plan_limit_checked": bool(plan_limit_checked),
        "mesh_instance_created": bool(mesh_instance_created),
        "local_node_records_seeded": bool(local_node_records_seeded),
        "registry_mutation_committed": bool(registry_mutation_committed),
        "local_mesh_instance_lifecycle_claim_allowed": bool(mesh_instance_created),
        "local_node_seed_claim_allowed": bool(local_node_records_seeded),
        "external_infrastructure_provisioning_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _mesh_provisioner_cross_plane_gate(surface):
    return cross_plane_claim_gate_metadata(
        ["production_readiness"],
        surface=surface,
    )

async def provision_mesh():
    instance = object()
    instance.mesh_provisioner_claim_gate = _mesh_provisioner_claim_gate(
        plan_limit_checked=True,
        mesh_instance_created=True,
        local_node_records_seeded=True,
        registry_mutation_committed=True,
    )
    instance.cross_plane_claim_gate = _mesh_provisioner_cross_plane_gate(
        "maas_services.mesh_provisioner.provision_mesh"
    )
    return instance
""",
    )
    _write(
        root,
        "src/api/maas/endpoints/batman.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

class BatmanMetricsResponse:
    batman_metrics_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanHealthResponse:
    batman_health_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanTopologyResponse:
    batman_topology_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanOriginatorsResponse:
    batman_topology_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanGatewaysResponse:
    batman_topology_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanMAPEKStatusResponse:
    batman_control_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanMAPEKCycleResponse:
    batman_control_claim_gate = {}
    cross_plane_claim_gate = {}

class BatmanHealingResponse:
    batman_control_claim_gate = {}
    cross_plane_claim_gate = {}

def _batman_health_claim_gate():
    return {
        "local_batman_health_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _batman_health_claim_boundary_headers():
    return {}

def _set_batman_health_claim_headers(http_response):
    pass

def _batman_metrics_claim_gate():
    return {
        "local_batman_metrics_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _batman_metrics_claim_boundary_headers():
    return {}

def _batman_metrics_prometheus_claim_boundary(output):
    return "# x0tta6bl4_dataplane_delivery_claim_allowed false\\n" + output

def _set_batman_metrics_claim_headers(http_response):
    pass

def _batman_topology_claim_gate(surface="maas_batman.topology"):
    return {
        "surface": surface,
        "local_batman_topology_observation_claim_allowed": True,
        "local_batctl_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _batman_topology_claim_boundary_headers():
    return {}

def _set_batman_topology_claim_headers(http_response):
    pass

def _batman_control_claim_gate(surface="maas_batman.mapek"):
    return {
        "surface": surface,
        "local_batman_mapek_control_claim_allowed": True,
        "local_batman_healing_control_claim_allowed": True,
        "autonomous_remediation_completion_claim_allowed": False,
        "production_route_mutation_claim_allowed": False,
        "post_action_dataplane_revalidated": False,
        "restored_dataplane_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _batman_control_claim_boundary_headers():
    return {}

def _set_batman_control_claim_headers(http_response):
    pass

def _batman_mesh_status_claim_gate(surface="maas_batman.mesh.status"):
    return {
        "surface": surface,
        "local_batman_mesh_status_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
    }

def _batman_mesh_status_claim_boundary_headers():
    return {}

def _set_batman_mesh_status_claim_headers(http_response):
    pass

def _metrics_response_summary(response):
    return {
        "batman_metrics_claim_gate_present": True,
        "batman_health_claim_gate_present": True,
        "batman_topology_claim_gate_present": True,
        "batman_control_claim_gate_present": True,
        "batman_mesh_status_claim_gate_present": True,
    }

def get_batman_health():
    return BatmanHealthResponse(
        batman_health_claim_gate=_batman_health_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.health",
        ),
    )

def get_batman_health_history(http_response=None):
    _set_batman_health_claim_headers(http_response)
    return []

def get_batman_metrics():
    return BatmanMetricsResponse(
        batman_metrics_claim_gate=_batman_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.metrics",
        ),
    )

def get_batman_metrics_history(http_response=None):
    _set_batman_metrics_claim_headers(http_response)
    return []

def get_batman_topology(http_response=None):
    _set_batman_topology_claim_headers(http_response)
    return BatmanTopologyResponse(
        batman_topology_claim_gate=_batman_topology_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.topology",
        ),
    )

def get_batman_originators(http_response=None):
    _set_batman_topology_claim_headers(http_response)
    return BatmanOriginatorsResponse(
        batman_topology_claim_gate=_batman_topology_claim_gate(
            surface="maas_batman.originators",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.originators",
        ),
    )

def get_batman_gateways(http_response=None):
    _set_batman_topology_claim_headers(http_response)
    return BatmanGatewaysResponse(
        batman_topology_claim_gate=_batman_topology_claim_gate(
            surface="maas_batman.gateways",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.gateways",
        ),
    )

def get_batman_mapek_status(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return BatmanMAPEKStatusResponse(
        batman_control_claim_gate=_batman_control_claim_gate(
            surface="maas_batman.mapek.status",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.mapek.status",
        ),
    )

def run_batman_mapek_cycle(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return BatmanMAPEKCycleResponse(
        batman_control_claim_gate=_batman_control_claim_gate(
            surface="maas_batman.mapek.cycle",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.mapek.cycle",
        ),
    )

def start_batman_mapek_loop(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return {
        "batman_control_claim_gate": _batman_control_claim_gate(
            surface="maas_batman.mapek.start",
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.mapek.start",
        ),
    }

def stop_batman_mapek_loop(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return {
        "batman_control_claim_gate": _batman_control_claim_gate(
            surface="maas_batman.mapek.stop",
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.mapek.stop",
        ),
    }

def trigger_batman_healing(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return BatmanHealingResponse(
        batman_control_claim_gate=_batman_control_claim_gate(
            surface="maas_batman.healing",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.healing",
        ),
    )

def get_batman_healing_actions(http_response=None):
    _set_batman_control_claim_headers(http_response)
    return []

maas_batman_healing_actions_surface = "maas_batman.healing.actions"

def get_mesh_batman_status(http_response=None):
    _set_batman_mesh_status_claim_headers(http_response)
    return {
        "batman_mesh_status_claim_gate": _batman_mesh_status_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_batman.mesh.status",
        ),
    }
""",
    )
    _write(
        root,
        "src/services/service_event_trace.py",
        """
CLAIM_BOUNDARY_SUMMARY_LIMIT = 8

def _claim_boundary_summary(value):
    return {
        "claim_boundary_summary": {},
        "claim_boundaries_truncated": False,
        "claim_boundaries_present": True,
    }

def _upstream_claim_gate_summary(value):
    return {
        "present": True,
        "payloads_redacted": True,
    }

def _upstream_cross_plane_claim_gate_summary(value):
    return {
        "present": True,
        "allowed": False,
        "payloads_redacted": True,
    }

def _economy_high_risk_claim_gate():
    return {"high_risk_claim_gate": {}}

def _post_action_dataplane_revalidation_summary(value):
    post_action_gate_allows_dataplane = False
    raw_dataplane_confirmed = True
    return {
        "post_action_dataplane_claim_gate_not_allowed": True,
    }

def cross_plane_evidence_profile(summary):
    post_action_gate_allows_dataplane = False
    raw_dataplane_confirmed = True
    return {
        "raw_dataplane_confirmed": raw_dataplane_confirmed,
        "dataplane_claim_gate_required": True,
        "dataplane_claim_blockers": [
            "post_action_dataplane_claim_gate_not_allowed",
        ],
    }

def event_trace_evidence_summary(data):
    claim_gate_summary = _upstream_claim_gate_summary(
        data.get("claim_gate_summary"),
    )
    cross_plane_claim_gate_summary = _upstream_cross_plane_claim_gate_summary(
        data.get("cross_plane_claim_gate_summary"),
    )
    post_action_dataplane = _post_action_dataplane_revalidation_summary(
        data.get("post_action_dataplane_revalidation"),
    )
    return {
        "post_action_dataplane_revalidation": post_action_dataplane,
        "upstream_evidence": {
            "claim_gate_summary": claim_gate_summary,
            "cross_plane_claim_gate_summary": cross_plane_claim_gate_summary,
            "upstream_claim_boundary_present": True,
        },
    }

def economy_finality_summary(summary):
    return {
        "high_risk_claim_gate": _economy_high_risk_claim_gate(),
        "claim_boundary_summary": _claim_boundary_summary(summary),
        "upstream_claim_boundary_present": True,
        "upstream_claim_gate": {},
        "upstream_cross_plane_claim_gate": {},
    }
""",
    )
    _write(
        root,
        "src/ledger/rag_search.py",
        """
CLAIM_STATUS_EXTERNAL_DPI_GAP_RECORD = "external_dpi_gap_record"

def _event_trace_claim_boundary_summary(evidence_summary):
    return {"present": True, "claim_boundaries": ["local only"], "redacted": True}

def _event_trace_upstream_claim_gate_summary(evidence_summary):
    return {"present": True, "surface": "integration_spine.reward_context"}

def _event_trace_upstream_cross_plane_claim_gate_summary(evidence_summary):
    return {"present": True, "allowed": False}

def _external_dpi_intake_claim_gate_summary(relative_path, payload):
    gap_record = True
    summary = {
        "proof_gate_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }
    return summary

def _external_dpi_intake_metadata(relative_path, payload):
    gap_record = True
    summary = _external_dpi_intake_claim_gate_summary(relative_path, payload)
    return {
        "external_evidence_gap_record": gap_record,
        "external_dpi_intake_claim_gate_summary": summary,
    }

class LedgerRAGSearch:
    def _event_trace_metadata(self, event, trace_filter):
        claim_boundary_summary = _event_trace_claim_boundary_summary(
            event.get("evidence_summary"),
        )
        upstream_claim_gate_summary = _event_trace_upstream_claim_gate_summary(
            event.get("evidence_summary"),
        )
        upstream_cross_plane_claim_gate_summary = (
            _event_trace_upstream_cross_plane_claim_gate_summary(
                event.get("evidence_summary"),
            )
        )
        return {
            "claim_boundary_summary": claim_boundary_summary,
            "upstream_claim_gate_summary": upstream_claim_gate_summary,
            "upstream_cross_plane_claim_gate_summary": (
                upstream_cross_plane_claim_gate_summary
            ),
        }

    def _event_trace_text(self, event, trace_filter):
        metadata = self._event_trace_metadata(event, trace_filter)
        return {
            "claim_boundary_summary": metadata["claim_boundary_summary"],
            "upstream_claim_gate_summary": metadata["upstream_claim_gate_summary"],
            "upstream_cross_plane_claim_gate_summary": metadata[
                "upstream_cross_plane_claim_gate_summary"
            ],
        }
""",
    )
    _write(
        root,
        "src/api/ledger_endpoints.py",
        """
CLAIM_USAGE_GATE_BOUNDARY = "citations are retrieval context only"

def _citation_claim_usage_gate():
    return {
        "standalone_claim_proof_allowed": False,
        "historical_claim_inventory_not_proof": True,
        "cross_plane_claim_gate_blocked": True,
        "upstream_claim_gate_local_only_not_proof": True,
        "upstream_cross_plane_claim_gate_blocked": True,
        "upstream_claim_gate_present": True,
        "upstream_cross_plane_claim_gate_present": True,
        "external_evidence_gap_record_not_proof": True,
        "external_dpi_intake_citation_not_proof": True,
        "external_dpi_proof_gate_not_allowed": True,
        "external_dpi_intake_citations": 1,
        "external_evidence_gap_record_citations": 1,
    }

def _extract_citations(results):
    metadata = {}
    return [
        {
            "claim_boundary_summary": metadata.get("claim_boundary_summary"),
            "upstream_claim_gate_summary": metadata.get(
                "upstream_claim_gate_summary"
            ),
            "upstream_cross_plane_claim_gate_summary": metadata.get(
                "upstream_cross_plane_claim_gate_summary"
            ),
            "cross_plane_evidence_profile": metadata.get(
                "cross_plane_evidence_profile"
            ),
            "economy_finality_summary": metadata.get("economy_finality_summary"),
            "external_dpi_intake_claim_gate_summary": metadata.get(
                "external_dpi_intake_claim_gate_summary"
            ),
            "external_evidence_gap_record": (
                metadata["external_evidence_gap_record"]
                if "external_evidence_gap_record" in metadata
                else None
            ),
            "claim_sensitive_citation_gate": _citation_claim_usage_gate(),
        }
    ]
""",
    )
    _write(
        root,
        "scripts/ops/smoke_ledger_event_trace_citation.py",
        """
assertions = {
    "citation_summary_metadata_present": True,
    "claim_boundary_summaries_bounded": True,
    "claim_boundaries_present_for_bounded_services": True,
    "cross_plane_summaries_fail_closed": True,
    "economy_summaries_fail_closed": True,
    "economy_services_have_local_only_gates": True,
}
""",
    )
    _write(
        root,
        "src/api/billing.py",
        """
def _billing_api_claim_gate():
    return {
        "customer_dataplane_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
    }
def _billing_api_checkout_response_claim_metadata():
    return {
        "claim_gate": _billing_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(),
    }
def _billing_api_order_status_response_claim_metadata():
    return {
        "claim_gate": _billing_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(),
        "vless_link": link,
    }
def _billing_api_local_observation_response_claim_metadata():
    return {
        "claim_gate": _billing_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(),
    }
def _billing_api_webhook_response_claim_metadata():
    return {
        "received": True,
        "claim_gate": _billing_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(),
    }
surface="billing_api.checkout_session"
surface="billing_api.order_status"
surface="billing_api.config"
surface="billing_api.revenue_metrics"
surface="billing_api.webhook"
""",
    )
    _write(
        root,
        "src/api/maas_billing.py",
        """
class Field:
    def __init__(self, default_factory=None): pass
class Any: pass
def _billing_local_claim_gate():
    return {"claim_gate": True}
def _billing_intent_response_claim_metadata():
    return {
        "claim_gate": _billing_local_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(),
    }
surface="maas_billing.subscription_checkout"
surface="maas_billing.customer_portal"
surface="maas_billing.invoice_checkout"
claim_gate: dict[str, Any] = Field(default_factory=dict)
""",
    )
    _write(
        root,
        "src/services/reward_events.py",
        """
def _safe_claim_gate_summary(value):
    return {"present": True}
def _safe_cross_plane_claim_gate_summary(value):
    return {"present": True}
def _reward_claim_gate():
    return {"token_settlement_finality_claim_allowed": False}
upstream_claim_gate = {}
upstream_cross_plane_claim_gate = {}
payload = {
    "reward_claim_gate": _reward_claim_gate(),
    "claim_gate_summary": _safe_claim_gate_summary(upstream_claim_gate),
    "cross_plane_claim_gate_summary": _safe_cross_plane_claim_gate_summary(
        upstream_cross_plane_claim_gate
    ),
}
""",
    )
    _write(
        root,
        "src/services/share_to_earn_service.py",
        """
_UPSTREAM_CLAIM_GATE_KEYS = ("claim_gate",)
_UPSTREAM_CROSS_PLANE_CLAIM_GATE_KEYS = ("cross_plane_claim_gate",)
mesh_upstream_evidence = {
    "claim_gate_present": True,
    "cross_plane_claim_gate_present": True,
    "claim_gate": {},
    "cross_plane_claim_gate": {},
}
metadata = {
    "claim_gate_present": mesh_upstream_evidence["claim_gate_present"],
    "cross_plane_claim_gate_present": (
        mesh_upstream_evidence["cross_plane_claim_gate_present"]
    ),
}
publish_reward_settlement_event(
    upstream_claim_gate=mesh_upstream_evidence["claim_gate"],
    upstream_cross_plane_claim_gate=mesh_upstream_evidence[
        "cross_plane_claim_gate"
    ],
)
""",
    )
    _write(
        root,
        "src/services/marketplace_settlement.py",
        """
payload = {
    "claim_gate": {
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_external_finality_evidence_for_settlement_claim": True,
        "requires_cross_plane_proof_gate_for_high_risk_claims": True,
        "upstream_high_risk_claims_present": False,
        "blocker_reason_ids": list(("marketplace_settlement_local_lifecycle_only",)),
        "claim_boundary": "This worker never promotes high-risk claims; those must be evaluated by separate cross-plane proof gates.",
    }
}
""",
    )
    _write(
        root,
        "src/services/marketplace_events.py",
        """
def _claim_gate_evidence(value):
    return {"production_readiness_claim_allowed": False}
""",
    )
    _write(
        root,
        "src/api/maas_marketplace.py",
        """
def _marketplace_listing_claim_gate(status):
    return {"listing_claim_gate": True}
listing_claim_gate = _marketplace_listing_claim_gate("available")
""",
    )
    _write(
        root,
        "src/network/mesh_vpn_bridge.py",
        """
def _relay_reward_claim_gate():
    return {"relay_reward_claim_gate": True}
relay_reward_claim_gate = _relay_reward_claim_gate()
""",
    )
    _write(
        root,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
ROOT = "."
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
module_roots = [ROOT]
sys.path.insert(0, ROOT)
def load_script_module(root, rel_path, module_name):
    return None
def atomic_write_json(path, payload):
    atomic_write_json(resolve_path(args.root, args.output_json), report)
    return "--output-json"
def source_artifact_identity(root, path, role):
    map_identity = {"sha256": "0" * 64}
    audit_identity = {"sha256": "1" * 64}
    return {
        "role": role,
        "path": "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        "sha256_present": True,
        "claim_boundary": "it does not prove that the underlying external-world claim is true",
        "source_artifacts": [map_identity, audit_identity],
        "source_artifact_hashes_present": True,
        "map_sha256": map_identity["sha256"],
        "audit_sha256": audit_identity["sha256"],
        "current_cross_plane_evidence_map": True,
        "current_active_goal_gap_audit": True,
    }
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []

EVENTBUS_LOG = ".agent_coordination/events.log"
DATAPLANE_DELIVERY_CLAIM_ID = "dataplane_delivery"
SERVICE_EVENT_TRACE_MODULE = "src/services/service_event_trace.py"
ECONOMY_BOUNDARY_CLAIM_ID = "economy_boundary"
ECONOMY_BOUNDARY_SOURCE_AGENTS = ("maas-marketplace", "maas-settlement")
ECONOMY_BOUNDARY_CANDIDATE_SCAN_LIMIT = 500
GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST = "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST = "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"

def _source_filtered_event_log_entries(path, source_agents, candidate_limit):
    source_agent_prefiltered_reverse_scan = "source_agent_prefiltered_reverse_scan"
    candidate_events_scanned_limit = candidate_limit
    event_log_lines_seen = 0
    return [], {
        "strategy": source_agent_prefiltered_reverse_scan,
        "candidate_events_scanned_limit": candidate_events_scanned_limit,
        "event_log_lines_seen": event_log_lines_seen,
    }

def dataplane_delivery_artifact_evidence(root):
    post_action_dataplane_revalidated = True
    restored_dataplane_claim_allowed = True
    bounded_dataplane_probe_not_attempted = "bounded_dataplane_probe_not_attempted"
    dataplane_evidence_not_redacted = "dataplane_evidence_not_redacted"
    restored_dataplane_claim_gate_missing = "restored_dataplane_claim_gate_missing"
    restored_dataplane_claim_gate_not_redacted = "restored_dataplane_claim_gate_not_redacted"
    restored_dataplane_claim_gate_probe_not_observed = "restored_dataplane_claim_gate_probe_not_observed"
    restored_dataplane_claim_gate_dataplane_not_observed = "restored_dataplane_claim_gate_dataplane_not_observed"
    return {
        "required_for_claim": "dataplane_delivery",
        "candidate_blockers": [],
        "blockers": ["dataplane_delivery_eventbus_artifact_not_verified"],
    }

def economy_boundary_artifact_evidence(root):
    economy_finality_summary = {}
    high_risk_claim_gate = {}
    required_for_high_risk_claims = {"settlement_finality": "provider finality"}
    external_settlement_finality_missing = "external_settlement_finality_missing"
    economy_event_redaction_metadata_missing = "economy_event_redaction_metadata_missing"
    return {
        "required_for_claims": ["settlement_finality", "production_readiness"],
        "blockers": ["economy_boundary_artifact_not_verified"],
    }

def dpi_lab_import_freshness_evidence(root, artifact_path=None):
    ghost_pulse_external_evidence_import_glob = "ghost-pulse-external-evidence-import-*"
    import_report_name = "import-report.json"
    write_freshness_claim_allowed = True
    local_latest_evidence_copy_claim_allowed = True
    verified_dpi_lab_fresh_import_report_not_found = "verified_dpi_lab_fresh_import_report_not_found"
    return {
        "valid": False,
        "blockers": [verified_dpi_lab_fresh_import_report_not_found],
        "write_freshness_claim_allowed": write_freshness_claim_allowed,
        "local_latest_evidence_copy_claim_allowed": local_latest_evidence_copy_claim_allowed,
    }

def dpi_lab_intake_context(root):
    ready_to_import = False
    ready_for_write_import = False
    candidate_is_symlink = False
    failures_capped = True
    command_shapes = {
        "collector_local_input_placeholders_present": True,
    }
    return {
        "claim_id": "dpi_lab",
        "ready_to_import": ready_to_import,
        "ready_for_write_import": ready_for_write_import,
        "candidate_is_symlink": candidate_is_symlink,
        "validation": {"failures_capped": failures_capped},
        "command_shapes": command_shapes,
        "claim_boundary": "DPI intake context is diagnostic operator handoff metadata.",
        "replacement_report_path": GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST,
        "intake_report_path": GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST,
    }

def dpi_lab_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"}
    validate_external_evidence(root, requirement)
    validator.validate_payload(contract, payload)
    validator.source_artifact_errors(root, payload)
    import_freshness = dpi_lab_import_freshness_evidence(root, requirement["path"])
    dpi_lab_import_freshness_not_verified = "dpi_lab_import_freshness_not_verified"
    return {
        "required_for_claim": "dpi_bypass",
        "external_dpi_proxy_validation": {},
        "import_freshness": import_freshness,
        "intake_context": dpi_lab_intake_context(root),
        "dpi_lab_import_freshness_not_verified": dpi_lab_import_freshness_not_verified,
        "blockers": ["dpi_lab_imported_artifact_not_verified"],
    }

PRODUCTION_READINESS_CLAIM_ID = "production_readiness"

def production_readiness_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"}
    validate_external_evidence(root, requirement)
    return {
        "required_for_claim": "production_readiness",
        "blockers": ["production_readiness_proof_gate_validation_not_verified"],
    }

production_readiness_imported_artifact_not_verified = "production_readiness_imported_artifact_not_verified"

EXTERNAL_SETTLEMENT_CLAIM_ID = "external_settlement"
EXTERNAL_SETTLEMENT_HANDOFF_MODULE = "src/integration/external_settlement_operator_handoff.py"

def _redact_external_settlement_live_rpc_report(report):
    rpc_endpoint_redacted = True
    rpc_endpoint_hash = "abc123"
    return {
        **report,
        "rpc_endpoint": None,
        "rpc_endpoint_redacted": rpc_endpoint_redacted,
        "rpc_endpoint_hash": rpc_endpoint_hash,
    }

def external_settlement_operator_handoff_context(root):
    ready_for_completion_rerun = False
    missing_inputs = []
    source_reports = []
    operator_sequence_ready = True
    return {
        "ready_for_completion_rerun": ready_for_completion_rerun,
        "missing_inputs": missing_inputs,
        "source_reports": source_reports,
        "summary": {"operator_sequence_ready": operator_sequence_ready},
    }

def external_settlement_artifact_evidence(root):
    evidence_path = ".tmp/external-settlement-evidence/settlement-submit.json"
    evidence_rel = ".tmp/external-settlement-evidence/settlement-submit.json"
    settlement.validate_evidence_file(evidence_path, evidence_rel.as_posix())
    DEFAULT_EVIDENCE_REPORT = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
    DEFAULT_RPC_REPORT = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
    DEFAULT_BLOCKER_REPORT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
    source_artifacts = [DEFAULT_EVIDENCE_REPORT, DEFAULT_RPC_REPORT]
    READY_TO_PROMOTE = "READY_TO_PROMOTE"
    return {
        "required_for_claim": "settlement_finality",
        "operator_handoff": external_settlement_operator_handoff_context(root),
        "blockers": ["external_settlement_artifact_not_verified"],
    }
""",
    )
    _write(
        root,
        "src/integration/external_settlement.py",
        """
def _redacted_rpc_endpoint_metadata(rpc_url):
    rpc_endpoint_redacted = True
    rpc_endpoint_hash = "abc123"
    return {
        "rpc_endpoint": None,
        "rpc_endpoint_redacted": rpc_endpoint_redacted,
        "rpc_endpoint_hash": rpc_endpoint_hash,
    }
""",
    )
    _write(
        root,
        "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py",
        """
SCHEMA = "x0tta6bl4.dataplane_delivery_eventbus_evidence_collector.v1"
CLAIM_BOUNDARY = "bounded local dataplane evidence only"

def sha256_text(value):
    return "0" * 64

def is_localish_target(host):
    return host == "localhost"

def parse_args(parser):
    parser.add_argument("--allow-local-probe", action="store_true")
    parser.add_argument("--write-event", action="store_true")

def build_event_data(probe, source_agent):
    confirmed = probe.get("dataplane_confirmed") is True
    claim_gate = {
        "schema": "x0tta6bl4.post_action_dataplane_claim_gate.v1",
        "restored_dataplane_claim_allowed": confirmed,
        "redacted": True,
        "observed_evidence": {
            "probe_attempted": True,
            "dataplane_confirmed": confirmed,
            "raw_target_redacted": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "schema": SCHEMA,
        "component": "post_action_dataplane_local_collector",
        "operation": "post_action_dataplane_revalidation",
        "post_action_dataplane_revalidated": confirmed,
        "restored_dataplane_claim_allowed": confirmed,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "post_action_dataplane_revalidation": {
            "post_action_dataplane_revalidated": confirmed,
            "restored_dataplane_claim_allowed": confirmed,
            "claim_boundary": CLAIM_BOUNDARY,
            "claim_gate": claim_gate,
            "evidence": {
                "event_ids_count": 1,
                "source_agents_count": 1,
                "redacted": True,
            },
        },
    }

def collect(args):
    root = args.root
    if not args.allow_local_probe:
        return {
            "decision": "BLOCKED_LOCAL_PROBE_NOT_AUTHORIZED",
            "blockers": ["allow_local_probe_required"],
        }
    if not is_localish_target(args.host):
        return {
            "decision": "BLOCKED_NON_LOCAL_TARGET",
            "blockers": ["target_must_be_loopback_private_or_link_local"],
        }
    probe = {
        "dataplane_confirmed": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "target": {
            "host_hash": sha256_text(args.host),
            "raw_target_redacted": True,
        },
    }
    event_data = build_event_data(probe, args.source_agent)
    event_written = False
    if args.write_event:
        event = EventBus(project_root=str(root)).publish(
            EventType.PIPELINE_STAGE_END,
            args.source_agent,
            event_data,
        )
        event_written = True
    ready = probe.get("dataplane_confirmed") is True and event_written
    return {
        "decision": "DATAPLANE_EVENTBUS_EVIDENCE_READY" if ready else "DATAPLANE_PROBE_FAILED",
        "proof_gate_command": [
            "python3",
            "scripts/ops/run_cross_plane_proof_gate.py",
            "--claim",
            "dataplane_delivery",
        ],
    }
""",
    )
    _write(
        root,
        "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py",
        """
GHOST_PULSE_CLAIM_SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
COLLECTOR_OPERATOR_HANDOFF_SCHEMA = "x0tta6bl4.external_dpi_proxy.collector_operator_handoff.v1"
GHOST_PULSE_DPI_ARTIFACT_ROLES = (
    "lab_scope",
    "baseline_result",
    "pulse_result",
    "lab_conclusion",
)

def regenerate_cross_plane_proof_gate_command():
    return ["python3", "scripts/ops/run_cross_plane_proof_gate.py"]

def build_operator_handoff():
    return {
        "schema": COLLECTOR_OPERATOR_HANDOFF_SCHEMA,
        "safe_local_input_rule": (
            "Do not paste private URLs, proxy endpoints, operator IDs, authorization "
            "scope, policy context, subscriber data, tokens, or raw captures into chat."
        ),
        "read_only_post_collection_commands": [
            ["python3", "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"]
        ],
        "write_sequence_after_ready": [regenerate_cross_plane_proof_gate_command()],
        "raw_inputs_retained": False,
        "claim_boundary": {"collector_handoff_is_not_evidence": True},
    }

def attach_ghost_pulse_import_contract(payload):
    payload.update(
        {
            "claim_id": "dpi_lab",
            "measurements": {
                "authorized_lab": True,
                "baseline_detected_or_blocked": True,
                "pulse_result_recorded": True,
                "dpi_bypass_verified": True,
            },
            "commands": [
                {
                    "args": [
                        "--target-url-sha256",
                        "--treatment-url-sha256",
                        "--treatment-proxy-present",
                    ],
                }
            ],
        }
    )
    payload["artifact_identity"]["artifact_sha256"] = artifact_content_sha256(payload)
""",
    )
    _write(
        root,
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        """
DECISION_READY = "READY_TO_IMPORT"

def external_dpi_intake_claim_gate():
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": "external_dpi_proxy.validator",
        "proof_gate_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

INCOMING_ARTIFACT_ROOT = "docs/verification/incoming/artifacts"

def source_artifact_errors(root, payload):
    return [
        f"path must stay under {INCOMING_ARTIFACT_ROOT}",
        "path must not include symlink components",
    ]

def build_report():
    return {
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(),
    }
""",
    )
    _write(
        root,
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        """
DECISION_READY = "READY_TO_IMPORT"
REPLACEMENT_CANDIDATES_REPORT = "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
EXTERNAL_EVIDENCE_INTAKE_REPORT = "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"

def external_dpi_intake_claim_gate(written=False):
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": f"ghost_pulse_external_import.dpi_lab",
        "local_latest_evidence_copy_claim_allowed": bool(written),
        "write_freshness_claim_allowed": False,
        "proof_gate_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def write_freshness_context():
    verifier.verify_saved_report(REPLACEMENT_CANDIDATES_REPORT)
    intake.verify_saved_report(EXTERNAL_EVIDENCE_INTAKE_REPORT)
    return {
        "claim_ready_in_replacement_report": False,
        "claim_ready_in_intake_report": False,
    }

def write_freshness_errors():
    return ["write freshness gate is not clear"]

def build_report():
    return {
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(),
    }
""",
    )
    _write(
        root,
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        """
import shlex

def command_line(command):
    return shlex.join(command)

def append_command_block(lines, title, command):
    lines.extend(
        [
            "## Operator Command Shapes",
            "Placeholder values in angle brackets must be filled locally by the operator.",
            "Do not paste target URLs, proxy URLs, operator IDs, authorization scope, or policy context into chat.",
            "docs/verification/ghost-pulse-external-dpi-intake-runbook.md",
            "collector_command_shape",
            "Read-only import check:",
            "Write import command, only after readiness is true:",
            "Acceptance commands:",
        ]
    )

def render_markdown(report):
    return '''
## Operator Command Shapes
Placeholder values in angle brackets must be filled locally by the operator.
Do not paste target URLs, proxy URLs, operator IDs, authorization scope, or policy context into chat.
External DPI runbook: `docs/verification/ghost-pulse-external-dpi-intake-runbook.md`.
collector_command_shape
Read-only import check:
Write import command, only after readiness is true:
Acceptance commands:
'''
""",
    )
    _write(
        root,
        "scripts/ops/run_external_dpi_intake_local.py",
        """
import getpass
import sys

CONFIRM_PHRASE = "RUN EXTERNAL DPI PROBES"
EXTERNAL_DPI_COLLECTOR = "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_VALIDATOR = "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_IMPORTER = "scripts/ops/import_ghost_pulse_external_evidence.py"
REDACTED_LOCAL_INPUT = "<redacted local input>"

def _prompt(label, secret=False):
    if secret:
        return getpass.getpass(f"{label}: ", stream=sys.stderr)
    return "local-input"

def _redact_private_values(value, private_values):
    return REDACTED_LOCAL_INPUT

def _post_import_refresh_commands():
    return [
        ["python3", "scripts/ops/verify_ghost_pulse_external_evidence.py"],
        ["python3", "scripts/ops/verify_ghost_pulse_external_evidence_intake.py"],
        ["python3", "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py"],
        ["python3", "scripts/ops/verify_ghost_pulse_artifact_chain.py"],
        ["python3", "scripts/ops/verify_ghost_pulse_goal_state.py"],
    ]

def _plan():
    return {
        "schema": "x0tta6bl4.external_dpi_intake.local_runner_plan.v1",
        "collector_command_shape": [
            EXTERNAL_DPI_COLLECTOR,
            "<authorized target URL; local input only>",
            "<authorized proxy URL; local input only>",
        ],
        "post_import_refresh_commands": _post_import_refresh_commands(),
        "raw_private_values_in_report": False,
    }

def run():
    collector_report = {}
    validator_report = {}
    import_report = {}
    collector_report = _redact_private_values(collector_report, ())
    validator_report = _redact_private_values(validator_report, ())
    import_report = _redact_private_values(import_report, ())
    print("Do not paste private values into chat", file=sys.stderr)
    return {
        "schema": "x0tta6bl4.external_dpi_intake.local_runner.v1",
        "status": "READY_TO_IMPORT",
        "collector": EXTERNAL_DPI_COLLECTOR,
        "validator": EXTERNAL_DPI_VALIDATOR,
        "importer": EXTERNAL_DPI_IMPORTER,
        "post_import_refresh_commands": _post_import_refresh_commands(),
        "claim_boundary": {"raw_private_values_retained": False},
    }
""",
    )
    _write(
        root,
        "docs/verification/ghost-pulse-external-dpi-intake-runbook.md",
        """
# Ghost Pulse External DPI Intake Runbook

Status: `AUTHORIZED_EXTERNAL_EVIDENCE_REQUIRED`

Run:

```bash
python3 scripts/ops/run_external_dpi_intake_local.py --json --write-ready
python3 scripts/ops/verify_ghost_pulse_external_evidence_inventory.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_goal_state.py --write-report --json
```

Do not paste target URLs into chat. This can close `dpi_lab` only when the
validator and import preflight both report readiness.

Do not edit `GHOST_PULSE_DPI_LAB_LATEST.json` by hand.
""",
    )
    _write(
        root,
        "src/integration/spine.py",
        """
from dataclasses import field
from typing import Any, Dict

def _spine_claim_gate():
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
    }

def _spine_cross_plane_claim_gate():
    return {
        "allowed": False,
    }

class SpineOutcome:
    claim_gate: Dict[str, Any] = field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "claim_gate": dict(self.claim_gate),
            "cross_plane_claim_gate": dict(self.cross_plane_claim_gate),
        }

event_payload = {
    "claim_gate": _spine_claim_gate(),
    "cross_plane_claim_gate": _spine_cross_plane_claim_gate(),
}
event_ids = ["evt-1"]
self = type("S", (), {"source_agent": "fixture-spine"})()
actuator_claim_gate = _spine_claim_gate()
actuator_cross_plane_claim_gate = _spine_cross_plane_claim_gate()
actuator_context = {
    "claim_gate": actuator_claim_gate,
    "cross_plane_claim_gate": actuator_cross_plane_claim_gate,
    "upstream_event_ids": list(event_ids),
    "upstream_source_agents": [self.source_agent],
}
reward_claim_gate = _spine_claim_gate()
reward_cross_plane_claim_gate = _spine_cross_plane_claim_gate()
class RewardManager:
    def reward_relay(self, node, packets, **kwargs):
        return kwargs
reward_manager = RewardManager()
reward_call = reward_manager.reward_relay(
    "node",
    1,
    upstream_claim_gate=reward_claim_gate,
    upstream_cross_plane_claim_gate=reward_cross_plane_claim_gate,
)
""",
    )
    _write(
        root,
        "src/integration/code_wiring.py",
        """
trace = {
    "outcome_claim_gate_present": True,
    "event_claim_gates_present": True,
    "actuator_context_claim_gate_present": True,
    "actuator_context_upstream_events_present": True,
    "reward_context_claim_gate_present": True,
    "reward_context_upstream_events_present": True,
    "strong_claims_blocked": True,
}
summary = {
    "spine_claim_gates_preserved": True,
    "actuator_context_claim_gates_preserved": True,
    "reward_context_claim_gates_preserved": True,
}
""",
    )
    _write(
        root,
        "src/integration/rollup_approval_contract.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    source_artifact_hashes_present = True
    return {
        "allowed": True,
        "source_artifact_hashes_present": source_artifact_hashes_present,
    }

local_ready = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
ready = local_ready and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "cross_plane_claim_gate": {
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "production_ready": False,
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/required_evidence_consistency.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
REQUIRED_EVIDENCE_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    return {"allowed": True, "blocker_ids": []}

raw_consistency_ready = True
current_evidence_clear = True
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
production_ready = raw_consistency_ready and current_evidence_clear and cross_plane_proof_gate_allowed
report = {
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "raw_consistency_ready": raw_consistency_ready,
    "cross_plane_claim_gate": {
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "production_ready_claim_allowed": production_ready,
        "proof_claims": {
            "production_ready": False,
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/semantic_production_blocker_queue.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    return {
        "allowed": True,
        "source_artifact_hashes_present": True,
    }

local_queue_clear = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
complete = local_queue_clear and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "goal_can_be_marked_complete": complete,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_queue_clear": local_queue_clear,
    "cross_plane_claim_gate": {
        "goal_completion_claim_allowed": complete,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "production_ready": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/raw_evidence_inventory.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    return {
        "allowed": True,
        "source_artifact_hashes_present": True,
    }

local_inventory_clear = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
complete = local_inventory_clear and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "goal_can_be_marked_complete": complete,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_inventory_clear": local_inventory_clear,
    "cross_plane_claim_gate": {
        "goal_completion_claim_allowed": complete,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "production_ready": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/production_raw_evidence_operator_packet.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    return {
        "allowed": True,
        "source_artifact_hashes_present": True,
    }

local_production_ready = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
production_ready = local_production_ready and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "production_ready": production_ready,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_production_ready": local_production_ready,
    "cross_plane_claim_gate": {
        "production_ready_claim_allowed": production_ready,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/production_evidence_replacement_passport.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
REPLACEMENT_PASSPORT_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    return {
        "allowed": True,
        "source_artifact_hashes_present": True,
    }

local_production_ready = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
production_ready = local_production_ready and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "production_ready": production_ready,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_production_ready": local_production_ready,
    "cross_plane_claim_gate": {
        "production_ready_claim_allowed": production_ready,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/completion_gate_runner.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
COMPLETION_GATE_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    source_artifact_hashes_present = True
    return {
        "allowed": True,
        "source_artifact_hashes_present": source_artifact_hashes_present,
    }

local_completion_ready = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
complete = local_completion_ready and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "goal_can_be_marked_complete": complete,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_completion_ready": local_completion_ready,
    "cross_plane_claim_gate": {
        "goal_completion_claim_allowed": complete,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/production_gap_index.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
PRODUCTION_GAP_INDEX_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    source_artifact_hashes_present = True
    return {
        "allowed": True,
        "source_artifact_hashes_present": source_artifact_hashes_present,
    }

local_gap_index_clear = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
complete = local_gap_index_clear and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "goal_can_be_marked_complete": complete,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_gap_index_clear": local_gap_index_clear,
    "cross_plane_claim_gate": {
        "goal_completion_claim_allowed": complete,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(
        root,
        "src/integration/production_closeout_review.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_clear(context):
    return True

DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
CLOSEOUT_REVIEW_CROSS_PLANE_CLAIMS = ("production_readiness", "dataplane_delivery")

def _cross_plane_proof_gate_allowed(data):
    return True

def _cross_plane_proof_gate_blocker_ids(data):
    return []

def _cross_plane_proof_gate_context(root):
    source_artifact_hashes_present = True
    return {
        "allowed": True,
        "source_artifact_hashes_present": source_artifact_hashes_present,
    }

local_closeout_ready = True
current_evidence_clear = True
cross_plane_proof_gate = _cross_plane_proof_gate_context(None)
cross_plane_proof_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_proof_gate)
ready = local_closeout_ready and current_evidence_clear and cross_plane_proof_gate_allowed
current_evidence_context = _current_evidence_context(None)
current_evidence_context_hash = "0x0"
report = {
    "ready": ready,
    "current_evidence_context": current_evidence_context,
    "current_evidence_context_hash": current_evidence_context_hash,
    "cross_plane_proof_gate": cross_plane_proof_gate,
    "local_closeout_ready": local_closeout_ready,
    "cross_plane_claim_gate": {
        "closeout_ready_claim_allowed": ready,
        "cross_plane_proof_gate_required": True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "proof_claims": {
            "goal_completion_authorized": False,
            "live_apply_authorized": False,
        },
    },
}
""",
    )
    _write(root, "src/api/ok.py", "def ok():\n    return True\n")
    _write(
        root,
        "src/api/ready.py",
        """
def _api_readiness_status():
    return {
        "status": "ready",
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="fixture_readiness"
        ),
    }
""",
    )
    _write(
        root,
        "src/api/maas_telemetry.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

_MAAS_TELEMETRY_CLAIM_GATE_BOUNDARY = (
    "MaaS telemetry claim gate. It does not prove fresh live agent connectivity, "
    "node reachability, dataplane delivery, settlement finality, or production "
    "readiness."
)

def _maas_telemetry_claim_gate(
    *,
    surface,
    read_only=True,
    local_readiness_dependency_observation=False,
    local_snapshot_observation=False,
    local_heartbeat_processing=False,
    local_uptime_sample_observation=False,
    settlement_uptime_ready=False,
    telemetry_runtime_ready=False,
):
    return {
        "schema": "x0tta6bl4.maas_telemetry.claim_gate.v1",
        "surface": surface,
        "local_readiness_dependency_observation_claim_allowed": bool(
            local_readiness_dependency_observation
        ),
        "local_telemetry_snapshot_observation_claim_allowed": bool(
            local_snapshot_observation
        ),
        "local_uptime_sample_observation_claim_allowed": bool(
            local_uptime_sample_observation
        ),
        "local_heartbeat_processing_claim_allowed": bool(
            local_heartbeat_processing
        ),
        "settlement_uptime_dependency_ready_observed": bool(
            settlement_uptime_ready
        ),
        "telemetry_runtime_ready_observed": bool(telemetry_runtime_ready),
        "raw_identifiers_redacted": True,
        "raw_telemetry_values_redacted": True,
        "node_reachability_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _maas_telemetry_event_claim_gate(
    *,
    operation,
    read_only,
    telemetry_summary,
    topology_summary,
    heartbeat_summary,
    settlement_summary,
):
    return _maas_telemetry_claim_gate(
        surface=f"maas_telemetry.{operation}",
        read_only=read_only,
        local_snapshot_observation=True,
    )

def _publish_telemetry_observed_state(operation="telemetry_snapshot_read"):
    payload = {
        "maas_telemetry_claim_gate": _maas_telemetry_event_claim_gate(
            operation=operation,
            read_only=True,
            telemetry_summary={},
            topology_summary={},
            heartbeat_summary={},
            settlement_summary={},
        )
    }
    return payload

def _topology_telemetry_evidence():
    return {
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.topology_node_telemetry_evidence",
            read_only=True,
        )
    }

def _topology_control_policy_evidence():
    return {
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.topology_control_policy_evidence",
            read_only=True,
        )
    }

def _telemetry_readiness_status(db):
    settlement_uptime_ready = True
    telemetry_runtime_ready = True
    return {
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.readiness",
            read_only=True,
            local_readiness_dependency_observation=True,
            settlement_uptime_ready=settlement_uptime_ready,
            telemetry_runtime_ready=telemetry_runtime_ready,
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_telemetry_readiness",
        ),
    }

async def heartbeat():
    return {
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.heartbeat_response",
            read_only=False,
            local_heartbeat_processing=True,
        )
    }
""",
    )
    _write(
        root,
        "src/api/service_identity_status.py",
        """
SERVICE_IDENTITY_CLAIM_GATE_BOUNDARY = (
    "Status does not prove live SPIFFE SVID issuance, DID ownership, wallet "
    "control, event-producer identity authenticity, chain identity finality, "
    "or production readiness."
)

def _service_identity_claim_gate():
    return {
        "schema": "x0tta6bl4.service_identity.claim_gate.v1",
        "local_redacted_identity_registry_claim_allowed": True,
        "local_trace_filter_surface_claim_allowed": True,
        "live_spiffe_svid_claim_allowed": False,
        "did_ownership_claim_allowed": False,
        "wallet_control_claim_allowed": False,
        "event_producer_identity_authenticity_claim_allowed": False,
        "chain_identity_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "raw_identity_values_redacted": True,
    }

def _redacted_trace_payload_ready(payload):
    return True

def _attach_service_identity_trace_claim_gates(payload, *, surface):
    return {
        **payload,
        "service_identity_claim_gate": _service_identity_claim_gate(),
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface=surface
        ),
    }

def _service_identity_readiness_status():
    return {
        "service_identity_claim_gate": _service_identity_claim_gate(),
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="service_identity_readiness"
        ),
    }

def get_service_event_trace_filter():
    return _attach_service_identity_trace_claim_gates(
        {"status": "ok", "redacted": True},
        surface="service_identity.event_trace_filter",
    )

def get_service_event_traces():
    return _attach_service_identity_trace_claim_gates(
        {"status": "ok", "redacted": True},
        surface="service_identity.event_traces",
    )
""",
    )
    _write(
        root,
        "src/self_healing/pqc_zero_trust_healer.py",
        """
PQC_CLAIM_BOUNDARY = (
    "PQC recovery executor event only. It records local policy and healing action "
    "state; it is not live PQC trust finality, dataplane delivery, external "
    "production evidence, or a settlement attestation."
)

def _pqc_recovery_claim_gate(result):
    return {
        "schema": "x0tta6bl4.self_healing.pqc_recovery_claim_gate.v1",
        "live_pqc_trust_finality_claim_allowed": False,
        "live_spiffe_svid_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

payload = {
    "claim_gate": _pqc_recovery_claim_gate(result),
}
""",
    )
    _write(
        root,
        "src/self_healing/mape_k_spiffe_integration.py",
        """
SPIFFE_CLAIM_BOUNDARY = (
    "SPIFFE MAPE-K recovery event only. It records local identity recovery "
    "policy and action state; it is not live SPIFFE SVID issuance, DID "
    "ownership, wallet control, chain identity finality, dataplane delivery, "
    "or external production evidence."
)

def _spiffe_recovery_claim_gate(result):
    return {
        "schema": "x0tta6bl4.self_healing.spiffe_recovery_claim_gate.v1",
        "live_spiffe_svid_claim_allowed": False,
        "did_ownership_claim_allowed": False,
        "wallet_control_claim_allowed": False,
        "chain_identity_finality_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

payload = {
    "claim_gate": _spiffe_recovery_claim_gate(result),
}
""",
    )
    _write_current_evidence(root)


def _write_current_evidence(
    root: Path,
    *,
    current_gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    _write(
        root,
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "# Current Active Goal Gap Audit\n\nStatus: test fixture.\n",
    )
    _write(
        root,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        """{
  "status": "working_map_not_production_completion_proof",
  "planes": {
    "data_plane": {"role": "test", "verified_contours": ["test"], "claim_boundaries": ["not production proof"], "source_refs": []},
    "control_plane": {"role": "test", "verified_contours": ["test"], "claim_boundaries": ["not production proof"], "source_refs": []},
    "trust_plane": {"role": "test", "verified_contours": ["test"], "claim_boundaries": ["not production proof"], "source_refs": []},
    "evidence_plane": {"role": "test", "verified_contours": ["test"], "claim_boundaries": ["not production proof"], "source_refs": []},
    "economy_plane": {"role": "test", "verified_contours": ["test"], "claim_boundaries": ["not production proof"], "source_refs": []}
  },
  "cross_plane_links": [],
  "current_gaps": REPLACE_GAPS,
  "next_actions": REPLACE_ACTIONS
}
""".replace(
            "REPLACE_GAPS",
            json.dumps(current_gaps or []),
        ).replace(
            "REPLACE_ACTIONS",
            json.dumps(next_actions or []),
        ),
    )


def _passing_runner(
    args: Sequence[str],
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> CommandResult:
    if tuple(args) == ("git", "status", "--porcelain"):
        return CommandResult(0, "")
    if tuple(args[-2:]) == ("alembic", "heads"):
        return CommandResult(0, "d7c8f1a2b3c4 (head)\n")
    return CommandResult(0, "ok\n")


def test_dirty_git_worktree_reports_actionable_counts(tmp_path: Path) -> None:
    def runner(
        args: Sequence[str],
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        if tuple(args) == ("git", "status", "--porcelain"):
            return CommandResult(
                0,
                "\n".join(
                    [
                        " M src/core/app.py",
                        " D libx0t/core/app.py",
                        "?? tests/unit/new_test.py",
                        "R  old/path.py -> docs/new/path.py",
                    ]
                )
                + "\n",
            )
        return CommandResult(0, "ok\n")

    [result] = check_git_state(tmp_path, runner)

    assert result.status == "FAIL"
    assert result.check_id == "git_worktree_clean"
    assert "Worktree has 4 uncommitted paths" in result.details
    assert "status_counts: modified=1, deleted=1, untracked=1, renamed=1" in result.details
    assert "top_paths:" in result.details
    assert "docs=1" in result.details
    assert "libx0t=1" in result.details
    assert "src=1" in result.details
    assert "tests=1" in result.details
    assert "reviewed commits or a clean worktree" in result.details


def test_ready_contract_passes_with_clean_static_and_command_evidence(tmp_path: Path) -> None:
    _ready_root(tmp_path)

    report = build_report(tmp_path, runner=_passing_runner)

    assert report["ready"] is True
    assert report["decision"] == "REAL_READINESS_READY"
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0


def test_env_example_secret_placeholders_must_be_empty(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "x0tta6bl4-app/.env.example",
        "VITE_API_BASE=/api\nDATABASE_URL=postgresql://user:password@localhost/db\nADMIN_USER=\nADMIN_PASS=\nPORT=8081\nCORE_API_HOST=localhost\nCORE_API_PORT=8083\n",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "app_env_example_contract" in blocker_ids
    assert report["ready"] is False


def test_plaintext_user_api_key_lookup_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/bad_lookup.py",
        "user = db.query(User).filter(User.api_key == token).first()\n",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "auth_no_plaintext_user_lookup" in blocker_ids


def test_current_evidence_open_gap_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write_current_evidence(
        tmp_path,
        current_gaps=[
            {
                "id": "external-dpi-proof-missing",
                "gap": "external proof missing",
                "risk": "claim overpromotion",
                "practical_next_action": "collect evidence",
            }
        ],
        next_actions=[
            {
                "id": "external-dpi-real-artifact-intake",
                "action": "collect artifact",
                "expected_result": "ready gate can pass",
            }
        ],
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "current_evidence_open_gaps" in blocker_ids
    assert report["current_evidence_context"]["current_gap_count"] == 1
    assert report["current_evidence_context"]["next_action_count"] == 1
    [detail] = report["current_evidence_context"]["next_action_details"]
    assert detail["id"] == "external-dpi-real-artifact-intake"
    assert detail["blocking_gap_id"] == "external-dpi-proof-missing"
    assert detail["status"] == "WAITING_FOR_AUTHORIZED_EXTERNAL_ARTIFACT"
    assert (
        detail["required_artifact_schema"]
        == "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1"
    )
    assert detail["ghost_pulse_import_bridge_required"] is True
    assert detail["ghost_pulse_claim_schema"] == "x0tta6bl4.ghost_pulse.claim_evidence.v1"
    assert detail["ghost_pulse_claim_id"] == "dpi_lab"
    assert detail["ghost_pulse_required_artifact_roles"] == [
        "lab_scope",
        "baseline_result",
        "pulse_result",
        "lab_conclusion",
    ]
    assert detail["expected_candidate_path"] == "docs/verification/incoming/dpi_lab.json"
    assert detail["requires_authorized_external_lab_or_field_run"] is True
    assert detail["collector_output_ready_when"] == [
        "bounded_external_dpi_proxy_validator_reports_READY_TO_IMPORT",
        "ghost_pulse_import_preflight_reports_READY_TO_IMPORT",
    ]
    assert detail["validator_command"] == [
        "python3",
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    assert detail["import_preflight_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    assert detail["safe_local_runner_command"] == [
        "python3",
        "scripts/ops/run_external_dpi_intake_local.py",
        "--json",
        "--write-ready",
    ]
    assert detail["collector_command_shape"][:6] == [
        "python3",
        "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py",
        "--output",
        "docs/verification/incoming/dpi_lab.json",
        "--artifact-dir",
        "docs/verification/incoming/artifacts/dpi_lab",
    ]
    assert "<authorized target URL; local input only>" in detail["collector_command_shape"]
    assert "result_summary.dpi_bypass_confirmed" in detail["required_true_flags"]
    assert "result_summary.production_ready" in detail["must_remain_false_flags"]
    assert "raw_url" in detail["forbidden_raw_fields"]
    assert "Do not paste private URLs" in detail["safe_local_input_rule"]
    assert detail["claim_boundary"]["production_ready"] is False
    assert detail["claim_boundary"]["customer_traffic_confirmed"] is False
    assert detail["claim_gate"]["schema"] == (
        "x0tta6bl4.external_dpi_intake.next_action_claim_gate.v1"
    )
    assert detail["claim_gate"]["local_intake_task_observation_claim_allowed"] is True
    assert detail["claim_gate"]["candidate_file_observed_claim_allowed"] is False
    assert detail["claim_gate"]["authorized_external_artifact_required"] is True
    assert detail["claim_gate"]["validator_ready_to_import_required"] is True
    assert detail["claim_gate"]["import_preflight_ready_required"] is True
    assert detail["claim_gate"]["this_detail_is_evidence"] is False
    assert detail["claim_gate"]["external_dpi_tested_claim_allowed"] is False
    assert detail["claim_gate"]["dpi_bypass_claim_allowed"] is False
    assert detail["claim_gate"]["dataplane_confirmed_claim_allowed"] is False
    assert detail["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert detail["claim_gate"]["production_readiness_claim_allowed"] is False
    assert report["ready"] is False


def test_current_evidence_dpi_subclaim_requires_latest_artifact(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write_current_evidence(tmp_path)
    _write(
        tmp_path,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        json.dumps(
            {
                "status": "working_map_not_production_completion_proof",
                "planes": {
                    "data_plane": {},
                    "control_plane": {},
                    "trust_plane": {},
                    "evidence_plane": {},
                    "economy_plane": {},
                },
                "cross_plane_links": [
                    {
                        "id": "anti-censorship-local-evidence-to-dpi-claim-boundary",
                        "proof_flags": {
                            "external_dpi_tested": True,
                            "dpi_bypass_confirmed": True,
                            "bypass_confirmed": True,
                        },
                    }
                ],
                "current_gaps": [],
                "next_actions": [],
            }
        ),
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "current_evidence_dpi_artifact_missing" in blocker_ids
    assert report["current_evidence_context"]["external_dpi_subclaim_claimed"] is True
    artifact_state = report["current_evidence_context"]["external_dpi_latest_artifact"]
    assert artifact_state["path"] == "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
    assert "external_dpi_latest_missing" in artifact_state["blockers"]
    assert report["ready"] is False


def test_non_blocking_tracked_gap_does_not_block_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write_current_evidence(
        tmp_path,
        current_gaps=[
            {
                "id": "tracked-local-risk",
                "blocks_real_readiness": False,
                "gap": "covered by a static contract check",
                "risk": "future regressions still need review",
                "practical_next_action": "keep contract check green",
            }
        ],
        next_actions=[],
    )

    report = build_report(tmp_path, runner=_passing_runner)

    assert report["ready"] is True
    assert report["current_evidence_context"]["tracked_gap_count"] == 1
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context"]["non_blocking_gap_ids"] == [
        "tracked-local-risk"
    ]


def test_generated_audit_wrapper_uses_nested_current_evidence_context(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        json.dumps(
            {
                "schema_version": "x0tta6bl4-production-grade-goal-audit-v2-repo-generated",
                "status": "VERIFIED HERE",
                "ok": True,
                "completion_decision": "NOT_COMPLETE",
                "goal_can_be_marked_complete": False,
                "current_evidence_context": {
                    "status": "working_map_not_production_completion_proof",
                    "current_gap_count": 1,
                    "tracked_gap_count": 5,
                    "non_blocking_gap_count": 4,
                    "open_gap_ids": ["external-dpi-proof-missing"],
                    "non_blocking_gap_ids": [
                        "cross-plane-proof-gate-wiring-incomplete"
                    ],
                    "next_action_count": 1,
                    "next_action_ids": ["external-dpi-real-artifact-intake"],
                    "required_planes_present": True,
                    "plane_ids": [
                        "control_plane",
                        "data_plane",
                        "economy_plane",
                        "evidence_plane",
                        "trust_plane",
                    ],
                },
                "next_actions": [
                    {
                        "id": "top-level-production-audit-action",
                        "status": "OPERATOR_INPUT_REQUIRED",
                    }
                ],
            }
        ),
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "current_evidence_context_status" not in blocker_ids
    assert "current_evidence_open_gaps" in blocker_ids
    assert report["current_evidence_context"]["source_format"] == (
        "embedded_current_evidence_context"
    )
    assert report["current_evidence_context"]["current_gap_count"] == 1
    assert report["current_evidence_context"]["tracked_gap_count"] == 5
    assert report["current_evidence_context"]["next_action_count"] == 1
    [detail] = report["current_evidence_context"]["next_action_details"]
    assert detail["id"] == "external-dpi-real-artifact-intake"
    assert report["ready"] is False


def test_generated_audit_wrapper_ignores_top_level_operator_actions_when_nested_context_clear(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        json.dumps(
            {
                "schema_version": "x0tta6bl4-production-grade-goal-audit-v2-repo-generated",
                "status": "VERIFIED HERE",
                "ok": True,
                "completion_decision": "NOT_COMPLETE",
                "goal_can_be_marked_complete": False,
                "current_evidence_context": {
                    "status": "working_map_not_production_completion_proof",
                    "current_gap_count": 0,
                    "tracked_gap_count": 0,
                    "non_blocking_gap_count": 0,
                    "open_gap_ids": [],
                    "non_blocking_gap_ids": [],
                    "next_action_count": 0,
                    "next_action_ids": [],
                    "required_planes_present": True,
                    "plane_ids": [
                        "control_plane",
                        "data_plane",
                        "economy_plane",
                        "evidence_plane",
                        "trust_plane",
                    ],
                },
                "next_actions": [
                    {
                        "id": "replace_operator_evidence",
                        "status": "OPERATOR_INPUT_REQUIRED",
                    }
                ],
            }
        ),
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    assert report["ready"] is True
    assert report["current_evidence_context"]["source_format"] == (
        "embedded_current_evidence_context"
    )
    assert report["current_evidence_context"]["next_action_count"] == 0


def test_top_level_current_evidence_summary_shape_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        json.dumps(
            {
                "included": True,
                "status": "working_map_not_production_completion_proof",
                "required_planes_present": True,
                "plane_ids": [
                    "control_plane",
                    "data_plane",
                    "economy_plane",
                    "evidence_plane",
                    "trust_plane",
                ],
                "current_gap_count": 0,
                "next_action_count": 0,
                "open_gap_ids": [],
                "next_action_ids": [],
            }
        ),
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "current_evidence_context_shape" in blocker_ids
    assert report["current_evidence_context"]["source_shape_valid"] is False
    assert report["ready"] is False


def test_api_readiness_status_without_cross_plane_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/unguarded.py",
        """
def _unguarded_readiness_status():
    return {"status": "ready"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "api_readiness_claim_gate_inventory" in blocker_ids
    assert report["ready"] is False


def test_missing_post_action_dataplane_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_nodes.py",
        "async def heal_node():\n    return {'status': 'healed'}\n",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "post_action_dataplane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_post_action_downstream_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/mesh/action_enforcer.py",
        """
_POST_ACTION_PROBE_ENV_VAR = "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE"
def _env_bool(name, default=False): return default
def _post_action_dataplane_revalidation_summary():
    return {
        "post_action_dataplane_revalidated": False,
        "restored_dataplane_claim_allowed": False,
        "claim_gate": {"restored_dataplane_claim_allowed": False},
    }
class MeshActionEnforcer:
    def _post_action_probe_enabled(self):
        return _env_bool(_POST_ACTION_PROBE_ENV_VAR, False)
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "post_action_dataplane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_recovery_executor_post_action_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/self_healing/recovery/executor.py",
        """
class RecoveryActionExecutor:
    def execute(self, action, context=None):
        return True
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "post_action_dataplane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_ebpf_self_healing_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/self_healing/ebpf_anomaly_detector.py",
        """
EBPF_CLAIM_BOUNDARY = "local eBPF self-healing action event only"
payload = {"claim_boundary": EBPF_CLAIM_BOUNDARY}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "post_action_dataplane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_dataplane_delivery_collector_without_local_auth_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py",
        """
SCHEMA = "x0tta6bl4.dataplane_delivery_eventbus_evidence_collector.v1"

def is_localish_target(host):
    return True

def collect(args):
    if args.write_event:
        EventBus(project_root=str(root)).publish(
            EventType.PIPELINE_STAGE_END,
            args.source_agent,
            {},
        )
    return {
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "dataplane_delivery_eventbus_collector_contract" in blocker_ids
    assert report["ready"] is False


def test_estimate_or_fallback_high_risk_metric_policy_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/mesh/metric_evidence_policy.py",
        """
DECISION_DATAPLANE_CONFIRMED = "dataplane_confirmed"
DECISION_ESTIMATE_OR_FALLBACK = "estimate_or_fallback_based"
HIGH_RISK_ALLOWED_DECISION_BASES = {
    DECISION_DATAPLANE_CONFIRMED,
    DECISION_ESTIMATE_OR_FALLBACK,
}

def build_mesh_metric_evidence_policy(raw_metrics):
    estimated_samples = 1.0
    fallback_samples = 0.0
    if False:
        pass
    elif estimated_samples > 0.0 or fallback_samples > 0.0:
        decision_basis = DECISION_ESTIMATE_OR_FALLBACK
        control_risk = "elevated"
        allows_high_risk = True
    return {
        "decision_basis": decision_basis,
        "control_risk": control_risk,
        "allows_high_risk_mesh_actions": allows_high_risk,
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "mesh_metric_policy_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_mesh_api_claim_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/app.py",
        """
def _call_yggdrasil_with_api_evidence():
    return {"status": "online"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "mesh_api_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_status_api_claim_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/libx0t/core/app.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

def _mesh_api_claim_gate(operation):
    return {
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _call_yggdrasil_with_api_evidence():
    return {
        "mesh_api_claim_gate": _mesh_api_claim_gate("status"),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["dataplane_delivery"],
            surface="mesh_api.status",
        ),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "status_api_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_health_api_claim_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/app.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

def _mesh_api_claim_gate(operation):
    return {
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _status_api_claim_gate():
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _status_api_response(status_data):
    return {
        **status_data,
        "status_api_claim_gate": _status_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="status_api",
        ),
    }

def _call_yggdrasil_with_api_evidence():
    return {
        "mesh_api_claim_gate": _mesh_api_claim_gate("status"),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["dataplane_delivery"],
            surface="mesh_api.status",
        ),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "health_api_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_metrics_api_claim_boundary_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/app.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

def _mesh_api_claim_gate(operation):
    return {
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def _health_api_claim_gate(surface):
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _health_api_response(payload, *, surface):
    return {
        **payload,
        "health_api_claim_gate": _health_api_claim_gate(surface),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface=surface,
        ),
    }

def _status_api_claim_gate():
    return {
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }

def _status_api_response(status_data):
    return {
        **status_data,
        "status_api_claim_gate": _status_api_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="status_api",
        ),
    }

def _call_yggdrasil_with_api_evidence():
    return {
        "mesh_api_claim_gate": _mesh_api_claim_gate("status"),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["dataplane_delivery"],
            surface="mesh_api.status",
        ),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "metrics_api_claim_boundary_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_mesh_metrics_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/mesh.py",
        """
def get_mesh_metrics():
    return {"network": {"avg_latency_ms": 1}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_mesh_metrics_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_mesh_deploy_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/mesh.py",
        """
def deploy_mesh():
    return {"status": "active", "join_config": {"token": "local"}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_mesh_deploy_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_mesh_lifecycle_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/mesh.py",
        """
def list_meshes():
    return []

def get_mesh_status():
    return {"status": "active", "nodes_healthy": 1}

def scale_mesh():
    return {"status": "scaling"}

def terminate_mesh():
    return {"status": "terminated"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_mesh_lifecycle_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_mesh_read_list_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/mesh.py",
        """
def get_mesh_audit():
    return [{"event": "deploy"}]

def get_mesh_mapek():
    return [{"phase": "MONITOR"}]
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_mesh_read_list_claim_boundary_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_compat_read_list_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_compat.py",
        """
async def get_audit_logs_alias():
    return {"events": []}

async def get_mapek_events_alias():
    return {"events": []}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_compat_read_list_claim_boundary_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_compat_lifecycle_read_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_compat.py",
        """
async def list_meshes_alias():
    return {"meshes": [], "count": 0}

async def get_mesh_status_alias():
    return {"status": "active"}

async def get_mesh_metrics_alias():
    return {"network": {}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_compat_lifecycle_read_claim_boundary_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_compat_lifecycle_control_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_compat.py",
        """
async def scale_mesh_alias():
    return {"status": "active"}

async def terminate_mesh_alias():
    return {"status": "terminated"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_compat_lifecycle_control_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_legacy_maas_mesh_metrics_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_legacy.py",
        """
def legacy_mesh_metrics():
    return {"network": {"avg_latency_ms": 1}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_mesh_metrics_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_core_lifecycle_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_core.py",
        """
def deploy_mesh():
    return {"status": "active"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_core_lifecycle_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_provisioning_setup_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_provisioning.py",
        """
def generate_provisioning_setup():
    return {"install_command": "curl install.sh"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_provisioning_setup_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_mesh_provisioning_service_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/services/provisioning_service.py",
        """
async def provision_mesh():
    return {"success": True, "status": "active", "nodes": 2}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "mesh_provisioning_service_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_mesh_provisioner_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/services.py",
        """
async def provision_mesh():
    return object()
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "mesh_provisioner_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_batman_metrics_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/batman.py",
        """
def get_batman_metrics():
    return {"throughput_mbps": 100.0}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "batman_metrics_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_batman_health_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/batman.py",
        """
def get_batman_health():
    return {"overall_status": "healthy", "overall_score": 100.0}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "batman_health_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_batman_topology_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/batman.py",
        """
def get_batman_topology():
    return {"total_nodes": 1, "routing_table": {}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "batman_topology_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_batman_control_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/batman.py",
        """
def run_batman_mapek_cycle():
    return {"success": True, "execution": {"status": "success"}}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "batman_control_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_batman_mesh_status_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas/endpoints/batman.py",
        """
def get_mesh_batman_status():
    return {"nodes": [{"health_status": "healthy", "health_score": 100.0}]}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "batman_mesh_status_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_yggdrasil_observed_state_contract_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/network/yggdrasil_client.py",
        """
def get_yggdrasil_status():
    return {"status": "online"}

def get_yggdrasil_peers():
    return {"status": "ok", "peers": []}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "yggdrasil_observed_state_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_yggdrasil_downstream_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/mesh/network_manager.py",
        """
def get_statistics():
    peer_data = get_yggdrasil_peers(event_bus=None, event_project_root=".")
    return {
        "downstream_evidence": {
            "event_ids": peer_data.get("evidence", {}).get("event_ids", []),
            "redacted": True,
        }
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "yggdrasil_observed_state_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_core_mapek_transitive_claim_boundary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/mape_k_loop.py",
        """
def _transitive_downstream_evidence(mesh_event_payloads):
    return {
        "yggdrasil-client": {
            "event_ids": ["event-1"],
            "redacted": True,
        }
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "yggdrasil_observed_state_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_economy_dataplane_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/services/reward_events.py",
        "def publish_reward_settlement_event():\n    return {}\n",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_marketplace_settlement_high_risk_promotion_contract_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/services/marketplace_settlement.py",
        """
payload = {
    "claim_gate": {
        "traffic_delivery_claim_allowed": dataplane_confirmed,
        "dataplane_delivery_claim_allowed": dataplane_confirmed,
        "external_settlement_finality_claim_allowed": chain_finality_confirmed,
        "production_readiness_claim_allowed": production_readiness,
        "requires_external_finality_evidence_for_settlement_claim": True,
    }
}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_service_identity_trust_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/service_identity_status.py",
        """
def _service_identity_readiness_status():
    return {"cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata()}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "service_identity_trust_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_pqc_recovery_trust_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/self_healing/pqc_zero_trust_healer.py",
        """
payload = {
    "claim_boundary": "local PQC recovery only",
}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "service_identity_trust_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_spiffe_recovery_trust_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/self_healing/mape_k_spiffe_integration.py",
        """
payload = {
    "claim_boundary": "local SPIFFE recovery only",
}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "service_identity_trust_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_maas_telemetry_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/maas_telemetry.py",
        """
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata

def _telemetry_readiness_status(db):
    return {
        "settlement_uptime_ready": True,
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            ["production_readiness"],
            surface="maas_telemetry_readiness",
        ),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "maas_telemetry_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_share_to_earn_upstream_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/services/share_to_earn_service.py",
        """
def publish_share_to_earn_reward_event():
    return publish_reward_settlement_event(upstream_event_ids=[])
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_service_trace_claim_boundary_summary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/services/service_event_trace.py",
        """
def _economy_high_risk_claim_gate():
    return {"high_risk_claim_gate": {}}

def economy_finality_summary(summary):
    return {"high_risk_claim_gate": _economy_high_risk_claim_gate()}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_rag_event_trace_claim_boundary_summary_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/ledger/rag_search.py",
        """
class LedgerRAGSearch:
    def _event_trace_metadata(self, event, trace_filter):
        return {"evidence_summary": event.get("evidence_summary")}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_ledger_api_event_trace_claim_boundary_citations_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/api/ledger_endpoints.py",
        """
def _extract_citations(results):
    metadata = {}
    return [{"evidence_summary": metadata.get("evidence_summary")}]
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_ledger_event_trace_citation_smoke_summary_assertions_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/smoke_ledger_event_trace_citation.py",
        """
assertions = {
    "indexed_successfully": True,
    "citations_present": True,
}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_compat_billing_pay_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    compat_path = tmp_path / "src/api/maas_compat.py"
    compat_text = compat_path.read_text(encoding="utf-8").replace(
        '"compat_billing_pay_claim_gate": compat_billing_pay_claim_gate,',
        "",
    )
    _write(tmp_path, "src/api/maas_compat.py", compat_text)

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "economy_dataplane_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_rollup_approval_context_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/rollup_approval_contract.py",
        """
local_ready = True
ready = local_ready
report = {"claim_boundary": "local only"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "rollup_approval_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_integration_spine_claim_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/spine.py",
        """
class SpineOutcome:
    def to_dict(self):
        return {"settlement_recorded": True}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "integration_spine_claim_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_required_evidence_consistency_context_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/required_evidence_consistency.py",
        """
raw_consistency_ready = True
production_ready = raw_consistency_ready
report = {"claim_boundary": "local only"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "required_evidence_consistency_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_semantic_blocker_queue_context_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/semantic_production_blocker_queue.py",
        """
local_queue_clear = True
complete = local_queue_clear
report = {"goal_can_be_marked_complete": complete}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "semantic_blocker_queue_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_raw_evidence_inventory_context_gate_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/raw_evidence_inventory.py",
        """
local_inventory_clear = True
complete = local_inventory_clear
report = {"goal_can_be_marked_complete": complete}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "raw_evidence_inventory_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_raw_evidence_operator_packet_context_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/production_raw_evidence_operator_packet.py",
        """
local_production_ready = True
production_ready = local_production_ready
report = {"production_ready": production_ready}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "raw_evidence_operator_packet_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_production_evidence_replacement_passport_context_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/production_evidence_replacement_passport.py",
        """
local_production_ready = True
production_ready = local_production_ready
report = {"production_ready": production_ready}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "production_evidence_replacement_passport_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_completion_gate_runner_context_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/completion_gate_runner.py",
        """
local_completion_ready = True
complete = local_completion_ready
report = {"goal_can_be_marked_complete": complete}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "completion_gate_runner_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_production_gap_index_context_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/production_gap_index.py",
        """
local_gap_index_clear = True
complete = local_gap_index_clear
report = {"goal_can_be_marked_complete": complete}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "production_gap_index_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_production_closeout_review_context_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/production_closeout_review.py",
        """
local_closeout_ready = True
ready = local_closeout_ready
report = {"ready": ready}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "production_closeout_review_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_collector_import_bridge_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py",
        """
def collect():
    return {"status": "VERIFIED"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_intake_claim_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        """
def build_report():
    return {"decision": "READY_TO_IMPORT"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_source_artifact_root_guard_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        """
DECISION_READY = "READY_TO_IMPORT"

def external_dpi_intake_claim_gate():
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": "external_dpi_proxy.validator",
        "proof_gate_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def build_report():
    return {
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_importer_write_freshness_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        """
DECISION_READY = "READY_TO_IMPORT"

def external_dpi_intake_claim_gate(written=False):
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": f"ghost_pulse_external_import.dpi_lab",
        "local_latest_evidence_copy_claim_allowed": bool(written),
        "proof_gate_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }

def build_report():
    return {
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(),
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_intake_operator_markdown_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        """
def render_markdown(report):
    return "no operator command shapes"
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_local_runner_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_external_dpi_intake_local.py",
        """
def run():
    return {"status": "READY_TO_IMPORT"}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_runbook_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "docs/verification/ghost-pulse-external-dpi-intake-runbook.md",
        "missing safe operator contract",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_local_runner_redaction_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_external_dpi_intake_local.py",
        """
import getpass
import sys

CONFIRM_PHRASE = "RUN EXTERNAL DPI PROBES"
EXTERNAL_DPI_COLLECTOR = "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_VALIDATOR = "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"
EXTERNAL_DPI_IMPORTER = "scripts/ops/import_ghost_pulse_external_evidence.py"

def run():
    print("Do not paste private values into chat", file=sys.stderr)
    return {
        "schema": "x0tta6bl4.external_dpi_intake.local_runner.v1",
        "status": "READY_TO_IMPORT",
        "collector": EXTERNAL_DPI_COLLECTOR,
        "validator": EXTERNAL_DPI_VALIDATOR,
        "importer": EXTERNAL_DPI_IMPORTER,
        "claim_boundary": {"raw_private_values_retained": False},
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_external_dpi_local_runner_refresh_plan_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    runner_path = tmp_path / "scripts/ops/run_external_dpi_intake_local.py"
    runner = runner_path.read_text(encoding="utf-8")
    runner = runner.replace("def _post_import_refresh_commands():", "def _missing_refresh_commands():")
    runner = runner.replace(
        '"post_import_refresh_commands": _post_import_refresh_commands(),',
        '"post_import_refresh_commands": [],',
    )
    runner_path.write_text(runner, encoding="utf-8")

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "external_dpi_collector_import_bridge_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_ghost_pulse_local_timing_evidence_contract_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/network/transport/pulse_transport.py",
        """
class PulseUDPTransport:
    pass
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "ghost_pulse_local_timing_evidence_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_cross_plane_dpi_artifact_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "cross_plane_proof_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_cross_plane_dataplane_eventbus_artifact_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []

def dpi_lab_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"}
    validate_external_evidence(root, requirement)
    validator.validate_payload(contract, payload)
    validator.source_artifact_errors(root, payload)
    return {
        "required_for_claim": "dpi_bypass",
        "external_dpi_proxy_validation": {},
        "blockers": ["dpi_lab_imported_artifact_not_verified"],
    }

PRODUCTION_READINESS_CLAIM_ID = "production_readiness"

def production_readiness_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"}
    validate_external_evidence(root, requirement)
    return {
        "required_for_claim": "production_readiness",
        "blockers": ["production_readiness_proof_gate_validation_not_verified"],
    }

production_readiness_imported_artifact_not_verified = "production_readiness_imported_artifact_not_verified"

EXTERNAL_SETTLEMENT_CLAIM_ID = "external_settlement"

def external_settlement_artifact_evidence(root):
    evidence_path = ".tmp/external-settlement-evidence/settlement-submit.json"
    settlement.validate_evidence_file(evidence_path, evidence_path)
    DEFAULT_EVIDENCE_REPORT = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
    DEFAULT_RPC_REPORT = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
    DEFAULT_BLOCKER_REPORT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
    source_artifacts = [DEFAULT_EVIDENCE_REPORT, DEFAULT_RPC_REPORT]
    READY_TO_PROMOTE = "READY_TO_PROMOTE"
    return {
        "required_for_claim": "settlement_finality",
        "blockers": ["external_settlement_artifact_not_verified"],
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "cross_plane_proof_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_cross_plane_economy_boundary_artifact_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []

EVENTBUS_LOG = ".agent_coordination/events.log"
DATAPLANE_DELIVERY_CLAIM_ID = "dataplane_delivery"

def dataplane_delivery_artifact_evidence(root):
    post_action_dataplane_revalidated = True
    restored_dataplane_claim_allowed = True
    bounded_dataplane_probe_not_attempted = "bounded_dataplane_probe_not_attempted"
    dataplane_evidence_not_redacted = "dataplane_evidence_not_redacted"
    restored_dataplane_claim_gate_missing = "restored_dataplane_claim_gate_missing"
    restored_dataplane_claim_gate_not_redacted = "restored_dataplane_claim_gate_not_redacted"
    restored_dataplane_claim_gate_probe_not_observed = "restored_dataplane_claim_gate_probe_not_observed"
    restored_dataplane_claim_gate_dataplane_not_observed = "restored_dataplane_claim_gate_dataplane_not_observed"
    return {
        "required_for_claim": "dataplane_delivery",
        "candidate_blockers": [],
        "blockers": ["dataplane_delivery_eventbus_artifact_not_verified"],
    }

def dpi_lab_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"}
    validate_external_evidence(root, requirement)
    validator.validate_payload(contract, payload)
    validator.source_artifact_errors(root, payload)
    return {
        "required_for_claim": "dpi_bypass",
        "external_dpi_proxy_validation": {},
        "blockers": ["dpi_lab_imported_artifact_not_verified"],
    }

PRODUCTION_READINESS_CLAIM_ID = "production_readiness"

def production_readiness_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"}
    validate_external_evidence(root, requirement)
    return {
        "required_for_claim": "production_readiness",
        "blockers": ["production_readiness_proof_gate_validation_not_verified"],
    }

production_readiness_imported_artifact_not_verified = "production_readiness_imported_artifact_not_verified"

EXTERNAL_SETTLEMENT_CLAIM_ID = "external_settlement"

def external_settlement_artifact_evidence(root):
    evidence_path = ".tmp/external-settlement-evidence/settlement-submit.json"
    evidence_rel = ".tmp/external-settlement-evidence/settlement-submit.json"
    settlement.validate_evidence_file(evidence_path, evidence_rel.as_posix())
    DEFAULT_EVIDENCE_REPORT = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
    DEFAULT_RPC_REPORT = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
    DEFAULT_BLOCKER_REPORT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
    source_artifacts = [DEFAULT_EVIDENCE_REPORT, DEFAULT_RPC_REPORT]
    READY_TO_PROMOTE = "READY_TO_PROMOTE"
    return {
        "required_for_claim": "settlement_finality",
        "blockers": ["external_settlement_artifact_not_verified"],
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "cross_plane_proof_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_cross_plane_production_readiness_artifact_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []

def dpi_lab_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"}
    validate_external_evidence(root, requirement)
    validator.validate_payload(contract, payload)
    validator.source_artifact_errors(root, payload)
    return {
        "required_for_claim": "dpi_bypass",
        "external_dpi_proxy_validation": {},
        "blockers": ["dpi_lab_imported_artifact_not_verified"],
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "cross_plane_proof_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_cross_plane_settlement_artifact_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/run_cross_plane_proof_gate.py",
        """
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CLAIM_REQUIREMENTS = {
    "production_readiness": {},
    "dataplane_delivery": {},
    "dpi_bypass": {},
    "settlement_finality": {},
}
current_evidence_open_gaps = "current_evidence_open_gaps"
blocking_false_flags = []

def dpi_lab_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"}
    validate_external_evidence(root, requirement)
    validator.validate_payload(contract, payload)
    validator.source_artifact_errors(root, payload)
    return {
        "required_for_claim": "dpi_bypass",
        "external_dpi_proxy_validation": {},
        "blockers": ["dpi_lab_imported_artifact_not_verified"],
    }

PRODUCTION_READINESS_CLAIM_ID = "production_readiness"

def production_readiness_artifact_evidence(root):
    requirement = {"path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"}
    validate_external_evidence(root, requirement)
    return {
        "required_for_claim": "production_readiness",
        "blockers": ["production_readiness_proof_gate_validation_not_verified"],
    }

production_readiness_imported_artifact_not_verified = "production_readiness_imported_artifact_not_verified"
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "cross_plane_proof_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_production_system_cross_plane_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/production_system.py",
        """
class ProductionSystem:
    def get_production_readiness_report(self):
        return {
            "production_readiness_claim_allowed": True,
        }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "production_system_cross_plane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_phase6_production_readiness_proof_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "tests/integration/production_readiness.py",
        """
def _current_evidence_context(root):
    return {}

def _current_evidence_gate_clear(context):
    return True

raw_checklist_ready = True
current_evidence_clear = True
is_ready = raw_checklist_ready and current_evidence_clear
report = {
    "raw_checklist_ready": raw_checklist_ready,
    "current_evidence_gate_clear": current_evidence_clear,
    "production_readiness_claim_allowed": is_ready,
}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "phase6_production_readiness_context_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_production_grade_audit_cross_plane_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/ops/audit_production_grade_goal.py",
        """
def build_report(root):
    requirements_complete = True
    current_evidence_clear = True
    complete = requirements_complete and current_evidence_clear
    return {
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "production_grade_audit_cross_plane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_objective_coverage_cross_plane_gate_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/integration/objective_coverage_audit.py",
        """
def build_report(root):
    return {
        "completion_decision": "COMPLETE",
        "goal_can_be_marked_complete": True,
    }
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "objective_coverage_cross_plane_gate_contract" in blocker_ids
    assert report["ready"] is False


def test_unguarded_high_risk_true_claim_literal_blocks_readiness(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/unsafe_claim_surface.py",
        """
def unsafe_status():
    return {"production_ready": True}
""",
    )

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "high_risk_true_claim_literal_contract" in blocker_ids
    assert report["ready"] is False


def test_missing_current_evidence_context_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    (tmp_path / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").unlink()

    report = build_report(
        tmp_path,
        runner=_passing_runner,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "current_evidence_context_present" in blocker_ids
    assert report["current_evidence_context"]["included"] is False
    assert report["ready"] is False


def test_command_failure_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)

    def failing_runner(
        args: Sequence[str],
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        if tuple(args[:4]) == ("docker", "compose", "-f", "docker-compose.app.yml"):
            return CommandResult(1, "", "compose failed")
        return _passing_runner(args, env, timeout)

    report = build_report(tmp_path, runner=failing_runner, include_git_check=False)

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "compose_app_config" in blocker_ids
    assert report["ready"] is False


def test_spire_local_socket_boundary_blocks_world_writable_setup(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "scripts/spire/start-spire.sh",
        """
mkdir -p /tmp/spire-agent/public
chmod 777 /tmp/spire-agent/public
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "spire_local_socket_boundary_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "spire_local_socket_boundary_contract"
    ]
    assert "chmod 777" in blocker["details"]
    assert "/tmp/spire-agent/public" in blocker["details"]
    assert report["ready"] is False


def test_spire_join_token_replay_guard_blocks_missing_single_use_guard(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/security/spiffe/agent/manager.py",
        """
class SPIREAgentManager:
    def attest_node(self, token):
        self._join_token = token
        return True
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "spire_join_token_replay_guard_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "spire_join_token_replay_guard_contract"
    ]
    assert "hash-only" in blocker["details"]
    assert "reused" in blocker["details"]
    assert report["ready"] is False


def test_mapek_safe_mode_contract_blocks_missing_safe_mode(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/core/mape_k_loop.py",
        """
def _execute_cycle():
    directives = self._plan(consciousness_metrics)
    return directives
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "mapek_safe_mode_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "mapek_safe_mode_contract"
    ]
    assert "planning" in blocker["details"]
    assert "CID-layer" in blocker["details"]
    assert report["ready"] is False


def test_ebpf_telemetry_loss_contract_blocks_missing_fail_closed_health(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/network/ebpf/telemetry/perf_reader.py",
        """
class PerfBufferReader:
    def get_stats(self):
        return {"events_dropped": 0}
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "ebpf_telemetry_loss_fail_closed_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "ebpf_telemetry_loss_fail_closed_contract"
    ]
    assert "dropped/overflowed" in blocker["details"]
    assert "unparseable events" in blocker["details"]
    assert report["ready"] is False


def test_ebpf_map_freeze_guard_contract_blocks_unsafe_wrapper(
    tmp_path: Path,
) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "src/network/ebpf/map_freeze_guard.py",
        """
import subprocess

def freeze_map_by_name(map_name):
    return subprocess.run("bpftool map freeze name " + map_name, shell=True)
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "ebpf_map_freeze_guard_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "ebpf_map_freeze_guard_contract"
    ]
    assert "validate map names" in blocker["details"]
    assert "without a shell" in blocker["details"]
    assert report["ready"] is False


def test_telegram_control_boundary_blocks_direct_mesh_import(tmp_path: Path) -> None:
    _ready_root(tmp_path)
    _write(
        tmp_path,
        "telegram_bot.py",
        """
from src.mesh.network_manager import MeshNetworkManager

def handler():
    return MeshNetworkManager()
""",
    )

    report = build_report(
        tmp_path,
        include_command_checks=False,
        include_git_check=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "telegram_control_boundary_contract" in blocker_ids
    [blocker] = [
        item
        for item in report["blockers"]
        if item["check_id"] == "telegram_control_boundary_contract"
    ]
    assert "forbidden-import" in blocker["details"]
    assert "src.mesh.network_manager" in blocker["details"]
    assert report["ready"] is False


def test_dirty_git_state_blocks_readiness_without_traceback(tmp_path: Path) -> None:
    _ready_root(tmp_path)

    def dirty_runner(
        args: Sequence[str],
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        if tuple(args) == ("git", "status", "--porcelain"):
            return CommandResult(
                0,
                " M scripts/ops/check_real_readiness.py\n"
                "?? docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json\n",
                "",
            )
        return _passing_runner(args, env, timeout)

    report = build_report(
        tmp_path,
        runner=dirty_runner,
        include_command_checks=False,
    )

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "git_worktree_clean" in blocker_ids
    [git_blocker] = [
        item for item in report["blockers"] if item["check_id"] == "git_worktree_clean"
    ]
    assert "status_counts: modified=1, untracked=1" in git_blocker["details"]
    assert "top_paths: docs=1, scripts=1" in git_blocker["details"]
    assert report["ready"] is False


def test_claim_hygiene_failure_blocks_readiness(tmp_path: Path) -> None:
    _ready_root(tmp_path)

    def failing_runner(
        args: Sequence[str],
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        if len(args) > 1 and args[1] == "scripts/claim_hygiene_scan.py":
            return CommandResult(
                1,
                '{"active_count": 1, "files_scanned": 1, "findings": []}\n',
                "",
            )
        return _passing_runner(args, env, timeout)

    report = build_report(tmp_path, runner=failing_runner, include_git_check=False)

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert "claim_hygiene_authoritative" in blocker_ids
    assert "claim_hygiene_active_claim_surface" in blocker_ids
    assert report["ready"] is False
