from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json"


def _load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                refs.extend(str(item) for item in child)
            else:
                refs.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_source_refs(child))
    return refs


def test_policy_enforcement_map_source_refs_resolve_to_existing_lines():
    policy_map = _load_map()

    for source_ref in _source_refs(policy_map):
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_guarded_components_use_shared_policy_decision_adapter():
    policy_map = _load_map()
    components = policy_map["guarded_components"]

    assert len(components) >= 17
    assert len({component["path"] for component in components}) == len(components)
    assert "src/api/maas_governance.py" not in {
        component["path"] for component in components
    }
    assert "src/dao/token_bridge.py" not in {component["path"] for component in components}
    assert "src/swarm/intelligence.py" not in {
        component["path"] for component in components
    }

    for component in components:
        source = (ROOT / component["path"]).read_text(encoding="utf-8")
        evaluator_source = source
        for evaluator_path in component.get("policy_evaluator_paths", []):
            evaluator_source += "\n" + (ROOT / evaluator_path).read_text(
                encoding="utf-8"
            )
        assert "policy_decision_adapter" in source, component["path"]
        assert "normalize_policy_allowed" in source, component["path"]
        assert "normalize_policy_reason" in source, component["path"]
        assert "normalize_policy_rules" in source, component["path"]
        assert "policy_engine.evaluate" in evaluator_source, component["path"]
        assert 'hasattr(decision, "allowed")' not in source, component["path"]
        assert "return bool(decision)" not in source, component["path"]


def test_policy_decision_dialects_and_audit_semantics_are_recorded():
    policy_map = _load_map()
    adapter_source = (
        ROOT / policy_map["normalization_bridge"]["path"]
    ).read_text(encoding="utf-8")
    zero_trust_source = (
        ROOT / policy_map["decision_dialects"]["zero_trust"]["primary_path"]
    ).read_text(encoding="utf-8")
    abac_source = (
        ROOT / policy_map["decision_dialects"]["abac"]["path"]
    ).read_text(encoding="utf-8")

    assert "effect" in policy_map["decision_dialects"]["abac"]["decision_shape"]
    assert "allowed" in policy_map["decision_dialects"]["zero_trust"]["decision_shape"]
    assert '"audit"' in adapter_source
    assert '"challenge"' in adapter_source
    assert "PolicyAction.ALLOW, PolicyAction.AUDIT" in zero_trust_source
    assert "effect: PolicyEffect" in abac_source


def test_policy_enforcement_map_claims_match_test_coverage():
    policy_map = _load_map()

    for test_path in policy_map["drift_checks"]:
        path = ROOT / test_path
        assert path.exists(), test_path

    assert "tests/unit/security/test_policy_decision_adapter_unit.py" in policy_map["drift_checks"]
    assert "tests/unit/dao/test_governance_spine_unit.py" in policy_map["drift_checks"]
    assert "tests/unit/api/test_maas_governance_spine_unit.py" in policy_map["drift_checks"]


def test_policy_enforcement_map_tracks_access_and_coordination_guards():
    policy_map = _load_map()
    runtime_access = policy_map["runtime_access_enforcement"]
    repo_coordination = policy_map["repo_coordination_enforcement"]
    real_agent_source = (
        ROOT / "scripts/ops/verify_maas_real_agent_control_loop.py"
    ).read_text(encoding="utf-8")
    readiness_source = (ROOT / "scripts/ops/check_real_readiness.py").read_text(
        encoding="utf-8"
    )
    nodes_source = (ROOT / "src/api/maas/endpoints/nodes.py").read_text(
        encoding="utf-8"
    )
    coordination_source = (
        ROOT / "scripts/agents/check_coordination_contract.sh"
    ).read_text(encoding="utf-8")
    pre_commit_source = (ROOT / ".githooks/pre-commit").read_text(encoding="utf-8")
    post_commit_source = (ROOT / ".githooks/post-commit").read_text(encoding="utf-8")

    assert runtime_access["verifier"] == (
        "scripts/ops/verify_maas_real_agent_control_loop.py"
    )
    assert runtime_access["ready_decision"] == (
        "MAAS_REAL_AGENT_CONTROL_LOOP_SMOKE_READY"
    )
    assert runtime_access["readiness_check_id"] == (
        "maas_real_agent_control_loop_smoke"
    )
    assert "temporary MaaS API" in runtime_access["bounded_claim"]
    assert "production readiness" in runtime_access["bounded_claim"]
    assert {
        "enrollment token cannot fetch node-config after registration",
        "missing heartbeat credential is rejected",
        "wrong heartbeat credential is rejected",
        "old rotated runtime credential is rejected",
        "heartbeat path/body node mismatch is rejected",
        "cross-node credential use is rejected",
        "revoked node credential is rejected",
    }.issubset(set(runtime_access["enforced_cases"]))
    assert "MAAS_REAL_AGENT_CONTROL_LOOP_VERIFIER" in readiness_source
    assert "MAAS_REAL_AGENT_CONTROL_LOOP_SMOKE_READY" in readiness_source
    assert "enrollment_token_node_config_rejected" in real_agent_source
    assert "missing_heartbeat_credential_rejected" in real_agent_source
    assert "wrong_heartbeat_credential_rejected" in real_agent_source
    assert "old_rotated_runtime_credential_rejected" in real_agent_source
    assert "heartbeat_path_body_node_mismatch_rejected" in real_agent_source
    assert "cross_node_credential_rejected" in real_agent_source
    assert "revoked_node_credential_rejected" in real_agent_source
    assert "operator_heal_after_real_agent_heartbeat" in real_agent_source
    assert '"/{mesh_id}/nodes/{node_id}/runtime-credential/rotate"' in nodes_source
    assert '"/{mesh_id}/nodes/{node_id}/heartbeat"' in nodes_source
    assert '"/{mesh_id}/node-config/{node_id}"' in nodes_source
    assert '"/{mesh_id}/nodes/{node_id}/heal"' in nodes_source

    assert repo_coordination["verifier"] == "scripts/agents/check_coordination_contract.sh"
    assert repo_coordination["readiness_check_id"] == "swarm_coordination_contract"
    assert "repository coordination" in repo_coordination["bounded_claim"]
    assert {
        "pre-commit requires a swarm agent identity",
        "pre-commit runs ownership checks",
        "pre-commit requires staged files to be covered by active leases",
        "post-commit releases leases for committed paths",
        "coordination landing documentation must match its template",
    }.issubset(set(repo_coordination["enforced_cases"]))
    assert "SWARM_COORDINATION_CONTRACT_CHECK" in readiness_source
    assert "swarm_coordination_contract" in readiness_source
    assert "missing executable hook: .githooks/pre-commit" in coordination_source
    assert "missing executable hook: .githooks/post-commit" in coordination_source
    assert "ensure-staged --agent" in coordination_source
    assert "release --agent" in coordination_source
    assert "check_swarm_ownership.py" in pre_commit_source
    assert "ensure-staged --agent" in pre_commit_source
    assert "git diff-tree --no-commit-id --name-only" in post_commit_source
    assert "release --agent" in post_commit_source
