#!/usr/bin/env python3
"""Read-only dirty-worktree review packet builder.

The real-readiness gate intentionally fails when the worktree is dirty. This
helper makes that blocker actionable without staging or committing anything.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


OWNERSHIP_PATH = Path("docs/team/swarm_ownership.json")

PACKAGE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "repo_memory_workflow",
        (
            ".gitmark-memory/",
            ".hermes/",
            ".workflow/",
            "scripts/gitmark_memory_bank.py",
            "skills/gitmark-memory-bank/",
            "tests/unit/scripts/test_gitmark_memory_bank_unit.py",
        ),
    ),
    (
        "repo_hygiene_config",
        (
            ".dockerignore",
            ".gitlab-ci.yml",
            "docs/templates/",
            "fix_all_strings.py",
            "fix_strings.py",
            "fix_test_files.sh",
            "pyproject.toml",
            "result.json",
            "scripts/golden_smoke_premerge.sh",
            "x0tta6bl4-project-audit-2026-06-06.md",
        ),
    ),
    (
        "dao_governance_policy",
        (
            "config/dao_policy.json",
            "src/dao/",
            "tests/unit/dao/",
            "tests/unit/services/test_pqc_formal_rotation.py",
            "tests/unit/security/test_tee_attestation.py",
        ),
    ),
    (
        "commercial_income_automation",
        (
            "docs/commercial/",
            "docs/marketing/",
            "src/sales/",
            "tests/unit/sales/",
            "scripts/ops/*agent*.py",
            "scripts/ops/*402*.py",
            "scripts/ops/*paid*.py",
            "scripts/ops/*income*.py",
            "scripts/ops/*bounty*.py",
            "scripts/ops/*commercial*.py",
            "scripts/ops/*product*.py",
            "scripts/ops/*wallet*.py",
            "scripts/ops/*directory*.py",
            "scripts/ops/*market*.py",
            "scripts/ops/*opentask*.py",
            "scripts/ops/*workprotocol*.py",
            "tests/unit/scripts/test_*agent*.py",
            "tests/unit/scripts/test_*402*.py",
            "tests/unit/scripts/test_*paid*.py",
            "tests/unit/scripts/test_*income*.py",
            "tests/unit/scripts/test_*bounty*.py",
            "tests/unit/scripts/test_*commercial*.py",
            "tests/unit/scripts/test_*product*.py",
            "tests/unit/scripts/test_*wallet*.py",
            "tests/unit/scripts/test_*directory*.py",
            "tests/unit/scripts/test_*market*.py",
            "tests/unit/scripts/test_*opentask*.py",
            "tests/unit/scripts/test_*workprotocol*.py",
        ),
    ),
    (
        "ghost_pulse_delivery",
        (
            ".dockerignore.ghost-pulse",
            "Dockerfile.ghost-pulse",
            "docker-compose.ghost-pulse.yml",
            "deploy_ghost/",
            "docs/verification/GHOST_PULSE_*",
            "ghost_pulse_vpn.py",
            "requirements-ghost.txt",
            "scripts/ops/*ghost_pulse*.py",
            "src/network/transport/ghost_pulse_transport.py",
            "tests/verify_ghost_pulse.py",
        ),
    ),
    (
        "vpn_client_distribution",
        (
            "docs/runbooks/NL_VPN_HEALTH.md",
            "nl-vpn-diagnostics-*.md",
            "scripts/apply_vpn_mobile_fix.sh",
            "scripts/refresh_nl_vpn_readonly_evidence.sh",
            "scripts/review_nl_no_progress_nudge.sh",
            "scripts/send_nl_no_progress_nudge_guarded.sh",
            "scripts/update_routing_safely.sh",
            "scripts/vpn_*.sh",
            "src/api/vpn.py",
            "src/services/xray_manager.py",
            "tests/api/test_vpn_api.py",
            "tests/unit/api/test_vpn_security_unit.py",
            "tests/unit/services/test_xray_manager_unit.py",
            "x0tta6bl4-xray-vps/",
            "ghost_pulse_vpn.py",
            "launch_vpn_ui.sh",
            "start_ghost_client.sh",
            "x0tta6bl4_vpn_app.py",
            "xui-inbounds-*.png",
            "tests/unit/scripts/test_*vpn*.py",
            "tests/unit/scripts/test_*xray*.py",
        ),
    ),
    (
        "formal_runtime_contracts",
        (
            "docs/architecture/FIRSTPARTY_PQC_ZERO_TRUST_VPN_CONTRACT.md",
            "docs/architecture/FORMAL_SPEC_*.md",
            "src/integration/formal_proof_registry.py",
            "src/network/ebpf/dataplane_logic_contract.py",
            "src/self_healing/mape_k/logic_contract.py",
            "src/services/pqc_logic_contract.py",
            "tests/integration/test_global_formal_registry.py",
            "tests/integration/test_pqc_swarm.py",
            "tests/unit/network/test_firstparty_vpn_protocol_unit.py",
            "tests/unit/self_healing/test_mapek_formal_logic.py",
            "tests/unit/services/test_pqc_formal_rotation.py",
        ),
    ),
    (
        "mapek_runtime_contracts",
        (
            "src/core/agent_mape_integration.py",
            "src/core/enhanced_thinking_techniques.py",
            "src/core/mape_k/",
            "src/core/mape_k_*.py",
            "src/core/mape_orchestrator.py",
            "src/core/parl_mapek_integration.py",
            "src/core/production_lifespan.py",
            "src/libx0t/core/enhanced_thinking_techniques.py",
            "src/libx0t/core/mape_k/",
            "src/libx0t/core/mape_k_*.py",
            "src/libx0t/core/mape_orchestrator.py",
            "src/libx0t/core/parl_mapek_integration.py",
            "src/libx0t/core/production_lifespan.py",
            "tests/test_mape_k_refactored.py",
            "tests/unit/core/test_mape_orchestrator_unit.py",
            "tests/unit/core/test_parl_mapek_integration_unit.py",
            "tests/unit/self_healing/test_mape_k_unit.py",
        ),
    ),
    (
        "agent_role_runtime",
        (
            "agent/",
            "ai/roles/",
            "docs/ai_agents/",
            "GEMINI.md",
            "skills/x0tta6bl4-*",
            "src/agent/",
            "src/agents/",
            "src/core/agent_thinking.py",
            "tests/unit/agents/",
            "tests/unit/core/test_agent_thinking_unit.py",
            "tests/unit/core/test_agent_mape_integration_thinking_unit.py",
            "tests/unit/coordination/test_agent_coordinator_thinking_unit.py",
        ),
    ),
    (
        "network_runtime",
        (
            "scripts/ebpf_prometheus_exporter.py",
            "src/libx0t/network/",
            "src/network/",
            "tests/test_ebpf_loader_refactored.py",
            "tests/unit/libx0t/network/",
            "tests/unit/network/",
        ),
    ),
    (
        "security_identity_runtime",
        (
            "src/libx0t/security/",
            "src/security/",
            "src/services/pqc_rotator_service.py",
            "tests/security/",
            "tests/unit/security/",
        ),
    ),
    (
        "mesh_platform_runtime",
        (
            "src/ai/",
            "src/chaos/",
            "src/client/",
            "src/coordination/",
            "src/edge/",
            "src/event_sourcing/",
            "src/federated_learning/",
            "src/integration/alertmanager_client.py",
            "src/licensing/",
            "src/mesh/",
            "src/ml/",
            "src/monitoring/",
            "src/optimization/",
            "src/parl/",
            "src/quality/",
            "src/sdk/",
            "src/services/maas_orchestrator.py",
            "src/services/node_manager_service.py",
            "src/services/share_to_earn_service.py",
            "src/swarm/",
            "src/vision/",
            "tests/integration/test_fl_twin_integration.py",
            "tests/integration/test_graphsage_fl_integration.py",
            "tests/test_lora_fl_integration.py",
            "tests/unit/chaos/",
            "tests/unit/coordination/",
            "tests/unit/edge/",
            "tests/unit/event_sourcing/",
            "tests/unit/federated_learning/",
            "tests/unit/licensing/",
            "tests/unit/mesh/",
            "tests/unit/ml/",
            "tests/unit/monitoring/",
            "tests/unit/quality/",
            "tests/unit/services/test_maas_orchestrator_unit.py",
            "tests/unit/swarm/",
        ),
    ),
    (
        "api_route_inventory",
        (
            "list_routes.py",
            "scripts/ops/list_api_routes.py",
            "tests/unit/scripts/test_list_api_routes.py",
        ),
    ),
    (
        "evidence_readiness",
        (
            "docs/05-operations/",
            "docs/architecture/CURRENT_*.json",
            "docs/verification/ANTI_HALLUCINATION_REPORT.md",
            "scripts/ops/check_real_readiness.py",
            "scripts/ops/summarize_dirty_worktree_review.py",
            "scripts/ops/check_telegram_control_boundary.py",
            "scripts/ops/run_measured_attestation_verifier_handoff.py",
            "scripts/ops/verify_maas_autonomous_mesh_runtime_smoke.py",
            "scripts/ops/verify_maas_real_agent_control_loop.py",
            "scripts/ops/verify_measured_attestation_verifier_smoke.py",
            "scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py",
            "scripts/ops/verify_safe_actuator_runtime_metadata_retention.py",
            "scripts/ops/verify_*evidence*.py",
            "scripts/ops/verify_*operator*.py",
            "scripts/ops/run_*proof_gate*.py",
            "tests/unit/scripts/test_summarize_dirty_worktree_review.py",
            "tests/unit/scripts/test_run_measured_attestation_verifier_handoff.py",
            "tests/unit/scripts/test_verify_measured_attestation_verifier_smoke.py",
            "tests/unit/scripts/test_verify_measured_attestation_verifier_smoke_artifact.py",
            "tests/unit/scripts/test_*readiness*.py",
            "tests/unit/scripts/test_*operator*.py",
            "tests/unit/test_*evidence*_unit.py",
            "tests/unit/test_*reality_map_unit.py",
            "tests/unit/test_*readiness_gate_doc_unit.py",
        ),
    ),
    (
        "maas_api_compat",
        (
            "src/api/maas/",
            "src/api/maas_*.py",
            "tests/unit/api/test_maas_*.py",
            "tests/api/test_maas_*.py",
        ),
    ),
    (
        "core_api_runtime",
        (
            "src/core/app.py",
            "src/core/app_desktop.py",
            "tests/unit/core/test_app*_unit.py",
            "tests/unit/core/test_*app*.py",
        ),
    ),
    (
        "self_healing_evidence",
        (
            "src/self_healing/mape_k/",
            "src/self_healing/ebpf_anomaly_detector.py",
            "src/self_healing/pqc_zero_trust_healer.py",
            "tests/unit/self_healing/test_self_healing_manager.py",
            "tests/unit/self_healing/test_self_healing_mapek_*.py",
        ),
    ),
    (
        "maas_auth_service",
        (
            "src/services/maas_auth_service.py",
            "tests/unit/services/test_maas_auth_service_unit.py",
            "tests/api/test_maas_auth.py",
        ),
    ),
    (
        "nl_runtime_diagnostics",
        (
            "nl-diagnostics/",
            "services/nl-server/",
        ),
    ),
    (
        "frontend_native_app",
        (
            "x0tta6bl4-app/",
            "src-tauri/",
        ),
    ),
    (
        "coordination",
        (
            "scripts/agents/",
            "docs/TEAM_RESPONSIBILITIES.md",
            "docs/team/",
            "COORDINATION.md",
        ),
    ),
)

PACKAGE_CHECKS: dict[str, tuple[str, ...]] = {
    "agent_role_runtime": (
        "go test ./agent/...",
        "python3 -m py_compile src/core/agent_thinking.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/agents tests/unit/core/test_agent_thinking_unit.py tests/unit/coordination/test_agent_coordinator_thinking_unit.py -q --no-cov",
    ),
    "api_route_inventory": (
        "python3 -m py_compile list_routes.py scripts/ops/list_api_routes.py tests/unit/scripts/test_list_api_routes.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_list_api_routes.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/python scripts/ops/list_api_routes.py --json",
    ),
    "commercial_income_automation": (
        "python3 -m py_compile src/sales/*.py scripts/ops/*agent*.py scripts/ops/*paid*.py scripts/ops/*income*.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/sales tests/unit/scripts/test_run_income_watch_cycle.py tests/unit/scripts/test_run_paid_task_hunter.py tests/unit/scripts/test_check_commercial_mesh_platform_readiness.py -q --no-cov",
    ),
    "coordination": (
        "python3 -m json.tool docs/team/swarm_ownership.json >/dev/null",
        "bash scripts/agents/check_coordination_contract.sh",
    ),
    "core_api_runtime": (
        "python3 -m py_compile src/core/app.py src/core/app_desktop.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/core/test_app_desktop_live_snapshot_unit.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/python - <<'PY'\nimport src.core.app\nprint('app_import_ok')\nPY",
    ),
    "evidence_readiness": (
        "python3 -m py_compile scripts/ops/check_real_readiness.py scripts/ops/summarize_dirty_worktree_review.py scripts/ops/verify_traffic_delivery_operator_flow.py scripts/ops/run_measured_attestation_verifier_handoff.py scripts/ops/verify_measured_attestation_verifier_smoke.py scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_check_real_readiness_unit.py tests/unit/scripts/test_summarize_dirty_worktree_review.py tests/unit/scripts/test_verify_traffic_delivery_operator_flow.py tests/unit/scripts/test_run_measured_attestation_verifier_handoff.py tests/unit/scripts/test_verify_measured_attestation_verifier_smoke.py tests/unit/scripts/test_verify_measured_attestation_verifier_smoke_artifact.py tests/unit/test_real_readiness_gate_doc_unit.py tests/unit/test_cross_plane_evidence_map_unit.py tests/unit/test_autonomous_mesh_reality_map_unit.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/python scripts/ops/check_real_readiness.py --json --skip-git-check",
    ),
    "dao_governance_policy": (
        "python3 -m json.tool config/dao_policy.json >/dev/null",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/dao tests/unit/services/test_pqc_formal_rotation.py tests/unit/security/test_tee_attestation.py -q --no-cov",
    ),
    "formal_runtime_contracts": (
        "python3 -m py_compile src/integration/formal_proof_registry.py src/network/ebpf/dataplane_logic_contract.py src/self_healing/mape_k/logic_contract.py src/services/pqc_logic_contract.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/integration/test_global_formal_registry.py tests/unit/network/test_firstparty_vpn_protocol_unit.py tests/unit/self_healing/test_mapek_formal_logic.py tests/unit/services/test_pqc_formal_rotation.py -q --no-cov",
    ),
    "frontend_native_app": (
        "npm --prefix x0tta6bl4-app run build",
    ),
    "ghost_pulse_delivery": (
        "python3 -m py_compile ghost_pulse_vpn.py tests/verify_ghost_pulse.py scripts/ops/run_ghost_pulse_verification_suite.py scripts/ops/verify_ghost_pulse_artifact_chain.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/verify_ghost_pulse.py -q --no-cov",
    ),
    "maas_api_compat": (
        "python3 -m py_compile src/api/maas_auth.py src/api/maas_legacy.py src/api/maas_compat.py src/api/maas_billing.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_compat_* tests/unit/api/test_maas_legacy_* -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/pytest tests/api/test_maas_billing.py tests/unit/api/test_maas_unit.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py tests/unit/api/test_maas_compat_* tests/unit/api/test_maas_legacy_* tests/api/test_maas_auth.py tests/api/test_maas_integration.py tests/api/test_maas_enterprise.py tests/api/test_maas_analytics.py tests/api/test_maas_billing.py -q --no-cov",
        "PYTHONPATH=. ./.venv/bin/python - <<'PY'\nimport src.core.app\nprint('app_import_ok')\nPY",
    ),
    "maas_auth_service": (
        "python3 -m py_compile src/services/maas_auth_service.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/services/test_maas_auth_service_unit.py tests/api/test_maas_auth.py -q --no-cov",
    ),
    "mapek_runtime_contracts": (
        "python3 -m py_compile src/core/mape_k_loop.py src/core/mape_orchestrator.py src/core/parl_mapek_integration.py src/libx0t/core/mape_orchestrator.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/core/test_mape_orchestrator_unit.py tests/unit/core/test_parl_mapek_integration_unit.py tests/unit/self_healing/test_mape_k_unit.py -q --no-cov",
    ),
    "mesh_platform_runtime": (
        "python3 -m py_compile src/ai/*.py src/chaos/*.py src/client/*.py src/mesh/*.py src/ml/*.py src/monitoring/*.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/chaos tests/unit/coordination tests/unit/edge tests/unit/federated_learning tests/unit/mesh tests/unit/ml tests/unit/monitoring tests/unit/quality -q --no-cov",
    ),
    "network_runtime": (
        "python3 -m py_compile src/network/transport/ghost_pulse_transport.py src/network/firstparty_vpn/*.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/network tests/unit/libx0t/network -q --no-cov",
    ),
    "nl_runtime_diagnostics": (
        "find services/nl-server -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile",
        "PYTHONPATH=. ./.venv/bin/pytest services/nl-server/tests -q --no-cov",
    ),
    "repo_memory_workflow": (
        "python3 -m py_compile scripts/gitmark_memory_bank.py tests/unit/scripts/test_gitmark_memory_bank_unit.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_gitmark_memory_bank_unit.py -q --no-cov",
        "python3 scripts/gitmark_memory_bank.py search \"technical debt\"",
    ),
    "repo_hygiene_config": (
        "python3 -m py_compile fix_all_strings.py fix_strings.py",
        "python3 -m json.tool result.json >/dev/null",
        "bash -n fix_test_files.sh scripts/golden_smoke_premerge.sh",
    ),
    "security_identity_runtime": (
        "find src/security src/libx0t/security -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/security tests/security -q --no-cov",
    ),
    "self_healing_evidence": (
        "python3 -m py_compile src/self_healing/mape_k/manager.py",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/self_healing/test_self_healing_mapek_verification_unit.py -q --no-cov",
    ),
    "vpn_client_distribution": (
        "bash x0tta6bl4-xray-vps/scripts/check-client-distribution-gate.sh",
        "PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_xray_client_distribution_gate_unit.py tests/unit/scripts/test_vpn_systemd_templates_unit.py -q --no-cov",
    ),
}


@dataclass(frozen=True)
class DirtyPath:
    status: str
    status_label: str
    path: str
    original_path: str | None = None


def _status_label(status: str) -> str:
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


def parse_porcelain_lines(lines: Iterable[str]) -> list[DirtyPath]:
    paths: list[DirtyPath] = []
    for line in lines:
        if not line.strip():
            continue
        status = line[:2] if len(line) >= 2 else line
        raw_path = line[3:].strip() if len(line) > 3 else ""
        original_path: str | None = None
        path = raw_path
        if " -> " in raw_path:
            original_path, path = raw_path.rsplit(" -> ", 1)
        paths.append(
            DirtyPath(
                status=status,
                status_label=_status_label(status),
                path=path or "(unknown)",
                original_path=original_path,
            )
        )
    return paths


def match_rule(path: str, rule: str) -> bool:
    if "*" in rule or "?" in rule or "[" in rule:
        return fnmatch.fnmatch(path, rule)
    if rule.endswith("/"):
        return path.startswith(rule)
    return path == rule


def classify_package(path: str) -> str:
    for package, rules in PACKAGE_RULES:
        if any(match_rule(path, rule) for rule in rules):
            return package
    return "other_manual_review"


def load_ownership(root: Path) -> dict[str, object]:
    path = root / OWNERSHIP_PATH
    if not path.exists():
        return {"shared_allow": [], "agents": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def owner_candidates(path: str, ownership: dict[str, object]) -> list[str]:
    agents = ownership.get("agents", {})
    if not isinstance(agents, dict):
        return []
    shared = ownership.get("shared_allow", [])
    shared_rules = list(shared) if isinstance(shared, list) else []
    matches: list[str] = []
    for agent, config in sorted(agents.items()):
        if not isinstance(config, dict):
            continue
        allow = config.get("allow", [])
        rules = shared_rules + (list(allow) if isinstance(allow, list) else [])
        if any(match_rule(path, str(rule)) for rule in rules):
            matches.append(str(agent))
    return matches


def git_status_porcelain(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git status failed")
    return result.stdout.splitlines()


def explicit_git_add_command(paths: Sequence[str], *, max_paths: int) -> dict[str, object]:
    selected = list(paths[:max_paths])
    quoted = " ".join(shlex.quote(path) for path in selected)
    return {
        "command": f"git add -- {quoted}" if selected else "",
        "path_count": len(paths),
        "shown_path_count": len(selected),
        "truncated": len(selected) < len(paths),
        "note": "Review the diff before running. Never replace this with git add -A.",
    }


def owner_review_metadata(
    owner_counts: Counter[str],
    *,
    path_count: int,
    paths: Sequence[str],
    max_paths: int,
) -> dict[str, object]:
    non_manual = [
        (owner, count)
        for owner, count in owner_counts.most_common()
        if owner != "unowned_or_manual"
    ]
    recommended_owner = non_manual[0][0] if non_manual else None
    full_owners = [owner for owner, count in non_manual if count == path_count]

    if owner_counts.get("unowned_or_manual", 0):
        status = "contains_unowned_paths"
    elif len(full_owners) == 1 and len(non_manual) == 1:
        status = "single_owner"
    elif len(full_owners) == 1:
        status = "primary_owner_with_secondary_reviewers"
    elif len(full_owners) > 1:
        status = "multiple_full_owner_candidates"
    elif non_manual:
        status = "split_owner_review_required"
    else:
        status = "no_owner_metadata"

    selected = list(paths[:max_paths])
    quoted = " ".join(shlex.quote(path) for path in selected)
    claim_command = (
        "PYTHONPATH=. ./.venv/bin/python scripts/agents/swarm_coord.py "
        f"claim --agent {shlex.quote(recommended_owner)} --ttl 3600 --paths {quoted}"
        if recommended_owner and selected
        else ""
    )

    return {
        "recommended_owner": recommended_owner,
        "owner_review_status": status,
        "full_owner_candidates": full_owners,
        "owner_claim_example": {
            "command": claim_command,
            "path_count": len(paths),
            "shown_path_count": len(selected),
            "truncated": len(selected) < len(paths),
            "note": (
                "Run this only as the recommended owner or another listed full owner. "
                "Never bypass coordination scope checks."
            ),
        },
    }


def current_agent_review_metadata(
    agent: str | None,
    owner_counts: Counter[str],
    *,
    path_count: int,
) -> dict[str, object]:
    if not agent:
        return {
            "current_agent": None,
            "current_agent_owner_path_count": 0,
            "current_agent_review_status": "agent_not_specified",
            "current_agent_can_claim_package": None,
        }

    owned_count = owner_counts.get(agent, 0)
    can_claim = owned_count == path_count and not owner_counts.get("unowned_or_manual", 0)
    if can_claim:
        status = "claimable_by_current_agent"
    elif owned_count:
        status = "partial_owner_handoff_required"
    else:
        status = "handoff_required"
    return {
        "current_agent": agent,
        "current_agent_owner_path_count": owned_count,
        "current_agent_review_status": status,
        "current_agent_can_claim_package": can_claim,
    }


def build_review(
    root: Path,
    *,
    max_command_paths: int = 20,
    current_agent: str | None = None,
) -> dict[str, object]:
    dirty_paths = parse_porcelain_lines(git_status_porcelain(root))
    ownership = load_ownership(root)
    package_items: dict[str, list[DirtyPath]] = defaultdict(list)
    owner_counts: Counter[str] = Counter()
    top_paths: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    path_owner_map: dict[str, list[str]] = {}
    unowned_paths: list[str] = []
    for item in dirty_paths:
        package_items[classify_package(item.path)].append(item)
        owners = owner_candidates(item.path, ownership)
        path_owner_map[item.path] = owners
        if not owners:
            unowned_paths.append(item.path)
        for owner in owners or ["unowned_or_manual"]:
            owner_counts[owner] += 1
        top_paths[item.path.split("/", 1)[0]] += 1
        status_counts[item.status_label] += 1

    packages: list[dict[str, object]] = []
    for package, items in sorted(package_items.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        paths = [item.path for item in items]
        package_status_counts = Counter(item.status_label for item in items)
        package_owner_counts: Counter[str] = Counter()
        for path in paths:
            for owner in path_owner_map.get(path) or ["unowned_or_manual"]:
                package_owner_counts[owner] += 1
        owner_metadata = owner_review_metadata(
            package_owner_counts,
            path_count=len(paths),
            paths=paths,
            max_paths=max_command_paths,
        )
        agent_metadata = current_agent_review_metadata(
            current_agent,
            package_owner_counts,
            path_count=len(paths),
        )
        packages.append(
            {
                "package": package,
                "review_stage": "requires_package_checks_before_staging",
                "path_count": len(paths),
                "status_counts": dict(sorted(package_status_counts.items())),
                "owner_candidates": dict(package_owner_counts.most_common()),
                **owner_metadata,
                **agent_metadata,
                "paths": paths,
                "suggested_checks": list(PACKAGE_CHECKS.get(package, ())),
                "explicit_stage_example": explicit_git_add_command(
                    paths,
                    max_paths=max_command_paths,
                ),
            }
        )

    owner_review_ready = len(unowned_paths) == 0
    claimable_packages = [
        package["package"]
        for package in packages
        if package.get("current_agent_can_claim_package") is True
    ]
    handoff_required_packages = [
        package["package"]
        for package in packages
        if package.get("current_agent_review_status")
        in {"handoff_required", "partial_owner_handoff_required"}
    ]
    all_dirty_packages_claimable_by_agent = bool(current_agent) and not handoff_required_packages
    return {
        "schema": "x0tta6bl4.dirty_worktree_review.v1",
        "decision": (
            "DIRTY_WORKTREE_OWNER_REVIEW_READY"
            if owner_review_ready
            else "DIRTY_WORKTREE_UNOWNED_PATHS_BLOCKED"
        ),
        "claim_boundary": (
            "Read-only dirty-worktree review inventory. This is not a commit, "
            "not a readiness pass, and not production evidence."
        ),
        "agent_review": {
            "agent": current_agent,
            "agent_required_for_claimable_gate": current_agent is None,
            "all_dirty_packages_claimable_by_agent": all_dirty_packages_claimable_by_agent,
            "claimable_packages": claimable_packages,
            "handoff_required_packages": handoff_required_packages,
        },
        "ready_to_release": len(dirty_paths) == 0,
        "owner_review_ready": owner_review_ready,
        "dirty_path_count": len(dirty_paths),
        "unowned_path_count": len(unowned_paths),
        "unowned_paths": unowned_paths,
        "status_counts": dict(status_counts.most_common()),
        "top_paths": dict(top_paths.most_common(12)),
        "owner_candidates": dict(owner_counts.most_common()),
        "packages": packages,
        "unsafe_shortcuts_blocked": [
            "git add -A",
            "git add .",
            "committing the entire dirty worktree",
            "reverting files owned by other agents",
        ],
    }


def print_text(report: dict[str, object]) -> None:
    print(f"decision: {report['decision']}")
    print(f"dirty_path_count: {report['dirty_path_count']}")
    print(f"ready_to_release: {str(report['ready_to_release']).lower()}")
    print(f"owner_review_ready: {str(report['owner_review_ready']).lower()}")
    print(f"unowned_path_count: {report['unowned_path_count']}")
    unowned_paths = report.get("unowned_paths", [])
    if isinstance(unowned_paths, list) and unowned_paths:
        print("unowned_paths:")
        for path in unowned_paths[:12]:
            print(f"  - {path}")
        if len(unowned_paths) > 12:
            print(f"  ... {len(unowned_paths) - 12} more")
    print(f"status_counts: {json.dumps(report['status_counts'], ensure_ascii=False)}")
    print(f"top_paths: {json.dumps(report['top_paths'], ensure_ascii=False)}")
    print("")
    for package in report.get("packages", []):
        if not isinstance(package, dict):
            continue
        print(f"[{package['package']}] {package['path_count']} path(s)")
        print(f"  review_stage: {package.get('review_stage')}")
        print(f"  owners: {json.dumps(package['owner_candidates'], ensure_ascii=False)}")
        print(f"  recommended_owner: {package.get('recommended_owner')}")
        print(f"  owner_review_status: {package.get('owner_review_status')}")
        if package.get("current_agent"):
            print(f"  current_agent: {package.get('current_agent')}")
            print(
                "  current_agent_review_status: "
                f"{package.get('current_agent_review_status')}"
            )
        print(f"  statuses: {json.dumps(package['status_counts'], ensure_ascii=False)}")
        checks = package.get("suggested_checks", [])
        if isinstance(checks, list) and checks:
            print("  suggested_checks:")
            for check in checks:
                print(f"    - {check}")
        paths = package.get("paths", [])
        if isinstance(paths, list):
            for path in paths[:8]:
                print(f"  - {path}")
            if len(paths) > 8:
                print(f"  ... {len(paths) - 8} more")
        command = package.get("explicit_stage_example", {})
        if isinstance(command, dict) and command.get("command"):
            print(f"  stage_example: {command['command']}")
        claim = package.get("owner_claim_example", {})
        if isinstance(claim, dict) and claim.get("command"):
            print(f"  owner_claim_example: {claim['command']}")
        print("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument(
        "--max-command-paths",
        type=int,
        default=20,
        help="Maximum paths shown in per-package explicit git add examples",
    )
    parser.add_argument(
        "--require-owned",
        action="store_true",
        help="Exit non-zero when any dirty path has no owner candidate",
    )
    parser.add_argument(
        "--agent",
        help=(
            "Optional agent name. Adds per-package claimability guidance for that agent "
            "without claiming any paths."
        ),
    )
    parser.add_argument(
        "--require-agent-claimable",
        action="store_true",
        help=(
            "Exit non-zero unless --agent can claim every dirty package. "
            "Use this before claiming paths to fail closed on handoff-required packages."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report = build_review(
        root,
        max_command_paths=max(0, args.max_command_paths),
        current_agent=args.agent,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_text(report)
    if args.require_owned and not report.get("owner_review_ready"):
        return 1
    if args.require_agent_claimable:
        if not args.agent:
            return 1
        agent_review = report.get("agent_review", {})
        if not isinstance(agent_review, dict):
            return 1
        if not agent_review.get("all_dirty_packages_claimable_by_agent"):
            return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"dirty-worktree-review: {exc}", file=sys.stderr)
        raise SystemExit(2)
