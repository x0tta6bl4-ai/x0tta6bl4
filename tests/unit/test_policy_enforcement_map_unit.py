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

    for component in components:
        source = (ROOT / component["path"]).read_text(encoding="utf-8")
        assert "policy_decision_adapter" in source, component["path"]
        assert "normalize_policy_allowed" in source, component["path"]
        assert "normalize_policy_reason" in source, component["path"]
        assert "normalize_policy_rules" in source, component["path"]
        assert "policy_engine.evaluate" in source, component["path"]
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
