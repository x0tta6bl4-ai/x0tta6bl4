from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.ops.summarize_dirty_worktree_review as review


ROOT = Path(__file__).resolve().parents[3]


def test_parse_porcelain_lines_handles_rename_and_untracked() -> None:
    items = review.parse_porcelain_lines(
        [
            " M src/core/app.py",
            "?? tests/unit/new_test.py",
            "R  old/path.py -> docs/new/path.py",
        ]
    )

    assert [item.status_label for item in items] == ["modified", "untracked", "renamed"]
    assert items[1].path == "tests/unit/new_test.py"
    assert items[2].original_path == "old/path.py"
    assert items[2].path == "docs/new/path.py"


def test_build_review_groups_dirty_paths_by_package_and_owner(
    tmp_path: Path, monkeypatch
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps(
            {
                "shared_allow": [],
                "agents": {
                    "codex-implementer": {
                        "allow": [
                            "docs/",
                            "config/dao_policy.json",
                            "list_routes.py",
                            "scripts/ops/",
                            "src/",
                            "tests/",
                            ".gitmark-memory/",
                            ".workflow/",
                            "agent/",
                        ]
                    },
                    "vpn-runtime-ops": {
                        "allow": [
                            "nl-diagnostics/",
                            "services/nl-server/",
                            "x0tta6bl4-xray-vps/",
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        review,
        "git_status_porcelain",
        lambda _root: [
            "?? list_routes.py",
            "?? scripts/ops/list_api_routes.py",
            " M docs/05-operations/REAL_READINESS_GATE.md",
            " M docs/TEAM_RESPONSIBILITIES.md",
            " M scripts/ops/check_real_readiness.py",
            " M src/api/maas_legacy.py",
            " M src/core/app.py",
            "?? src/core/app_desktop.py",
            "?? tests/unit/core/test_app_desktop_live_snapshot_unit.py",
            " M src/self_healing/mape_k/manager.py",
            " M src/services/maas_auth_service.py",
            "?? tests/unit/api/test_maas_package_compat_unit.py",
            " M nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md",
            " M services/nl-server/manifest.json",
            "?? services/nl-server/ghost-access/build_anti_block_production_audit.py",
            " M x0tta6bl4-app/src/App.tsx",
            "?? .gitmark-memory/graph.html",
            " M config/dao_policy.json",
            "?? docs/commercial/MVP_PACKAGING_V1.md",
            "?? docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md",
            "?? x0tta6bl4-xray-vps/scripts/check-client-distribution-gate.sh",
            "?? docs/architecture/FORMAL_SPEC_DATAPLANE.md",
            " M agent/main.go",
            " M src/network/firstparty_vpn/protocol.py",
            " M src/security/pqc_mtls.py",
            " M src/ml/rag.py",
        ],
    )

    report = review.build_review(
        tmp_path,
        max_command_paths=3,
        current_agent="codex-implementer",
    )

    assert report["schema"] == "x0tta6bl4.dirty_worktree_review.v1"
    assert report["decision"] == "DIRTY_WORKTREE_UNOWNED_PATHS_BLOCKED"
    assert report["ready_to_release"] is False
    assert report["owner_review_ready"] is False
    assert report["dirty_path_count"] == 26
    assert report["unowned_path_count"] == 1
    assert report["unowned_paths"] == ["x0tta6bl4-app/src/App.tsx"]
    assert report["status_counts"] == {"modified": 15, "untracked": 11}
    assert report["top_paths"]["nl-diagnostics"] == 1
    assert report["top_paths"]["services"] == 2
    assert report["agent_review"]["agent"] == "codex-implementer"
    assert "nl_runtime_diagnostics" in report["agent_review"][
        "handoff_required_packages"
    ]
    assert "core_api_runtime" in report["agent_review"]["claimable_packages"]

    packages = {item["package"]: item for item in report["packages"]}
    assert packages["evidence_readiness"]["path_count"] == 2
    assert packages["api_route_inventory"]["path_count"] == 2
    assert packages["coordination"]["path_count"] == 1
    assert packages["core_api_runtime"]["path_count"] == 3
    assert packages["self_healing_evidence"]["path_count"] == 1
    assert packages["maas_auth_service"]["path_count"] == 1
    assert packages["maas_api_compat"]["path_count"] == 2
    assert packages["nl_runtime_diagnostics"]["path_count"] == 3
    assert packages["frontend_native_app"]["path_count"] == 1
    assert packages["repo_memory_workflow"]["path_count"] == 1
    assert packages["dao_governance_policy"]["path_count"] == 1
    assert packages["commercial_income_automation"]["path_count"] == 1
    assert packages["ghost_pulse_delivery"]["path_count"] == 1
    assert packages["vpn_client_distribution"]["path_count"] == 1
    assert packages["formal_runtime_contracts"]["path_count"] == 1
    assert packages["agent_role_runtime"]["path_count"] == 1
    assert packages["network_runtime"]["path_count"] == 1
    assert packages["security_identity_runtime"]["path_count"] == 1
    assert packages["mesh_platform_runtime"]["path_count"] == 1
    assert "other_manual_review" not in packages

    for package in packages.values():
        assert package["review_stage"] == "requires_package_checks_before_staging"
        assert package["suggested_checks"]

    maas_command = packages["maas_api_compat"]["explicit_stage_example"]["command"]
    assert maas_command.startswith("git add -- ")
    assert "git add -A" not in maas_command
    assert "src/api/maas_legacy.py" in maas_command
    maas_checks = " ".join(packages["maas_api_compat"]["suggested_checks"])
    assert "test_maas_compat_*" in maas_checks
    assert "test_maas_legacy_*" in maas_checks
    assert "tests/api/test_maas_billing.py" in maas_checks
    assert "tests/unit/api/test_maas_unit.py" in maas_checks

    assert "git add -A" in report["unsafe_shortcuts_blocked"]
    assert packages["nl_runtime_diagnostics"]["owner_candidates"] == {
        "vpn-runtime-ops": 3
    }
    assert packages["nl_runtime_diagnostics"]["recommended_owner"] == "vpn-runtime-ops"
    assert packages["nl_runtime_diagnostics"]["owner_review_status"] == "single_owner"
    assert packages["nl_runtime_diagnostics"]["full_owner_candidates"] == [
        "vpn-runtime-ops"
    ]
    assert (
        packages["nl_runtime_diagnostics"]["current_agent_review_status"]
        == "handoff_required"
    )
    assert packages["nl_runtime_diagnostics"]["current_agent_can_claim_package"] is False
    assert packages["core_api_runtime"]["current_agent_review_status"] == (
        "claimable_by_current_agent"
    )
    assert packages["core_api_runtime"]["current_agent_can_claim_package"] is True
    nl_claim = packages["nl_runtime_diagnostics"]["owner_claim_example"]
    assert nl_claim["command"].startswith(
        "PYTHONPATH=. ./.venv/bin/python scripts/agents/swarm_coord.py claim "
        "--agent vpn-runtime-ops"
    )
    assert "codex-implementer" not in nl_claim["command"]
    assert "Never bypass coordination scope checks" in nl_claim["note"]
    assert packages["frontend_native_app"]["recommended_owner"] is None
    assert packages["frontend_native_app"]["owner_review_status"] == "contains_unowned_paths"
    assert packages["frontend_native_app"]["current_agent_review_status"] == (
        "handoff_required"
    )
    assert "pytest tests/unit/scripts/test_list_api_routes.py" in " ".join(
        packages["api_route_inventory"]["suggested_checks"]
    )
    assert "check_real_readiness.py" in " ".join(
        packages["evidence_readiness"]["suggested_checks"]
    )
    assert "npm --prefix x0tta6bl4-app run build" in packages[
        "frontend_native_app"
    ]["suggested_checks"]
    assert "gitmark_memory_bank.py" in " ".join(
        packages["repo_memory_workflow"]["suggested_checks"]
    )
    assert "json.tool config/dao_policy.json" in " ".join(
        packages["dao_governance_policy"]["suggested_checks"]
    )
    assert "run_paid_task_hunter.py" in " ".join(
        packages["commercial_income_automation"]["suggested_checks"]
    )
    assert "verify_ghost_pulse_artifact_chain.py" in " ".join(
        packages["ghost_pulse_delivery"]["suggested_checks"]
    )
    assert "check-client-distribution-gate.sh" in " ".join(
        packages["vpn_client_distribution"]["suggested_checks"]
    )
    assert "formal_proof_registry.py" in " ".join(
        packages["formal_runtime_contracts"]["suggested_checks"]
    )
    assert "go test ./agent/..." in " ".join(
        packages["agent_role_runtime"]["suggested_checks"]
    )
    assert "tests/unit/network" in " ".join(
        packages["network_runtime"]["suggested_checks"]
    )
    assert "tests/unit/security" in " ".join(
        packages["security_identity_runtime"]["suggested_checks"]
    )
    assert "tests/unit/ml" in " ".join(
        packages["mesh_platform_runtime"]["suggested_checks"]
    )
    assert "test_app_desktop_live_snapshot_unit.py" in " ".join(
        packages["core_api_runtime"]["suggested_checks"]
    )
    nl_checks = " ".join(packages["nl_runtime_diagnostics"]["suggested_checks"])
    assert "find services/nl-server -name '*.py'" in nl_checks
    assert "xargs -0 python3 -m py_compile" in nl_checks


def test_build_review_marks_owner_ready_when_all_dirty_paths_have_owner(
    tmp_path: Path, monkeypatch
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps(
            {
                "shared_allow": [],
                "agents": {
                    "codex-implementer": {
                        "allow": ["scripts/ops/", "x0tta6bl4-app/"]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        review,
        "git_status_porcelain",
        lambda _root: [
            " M scripts/ops/check_real_readiness.py",
            " M x0tta6bl4-app/src/App.tsx",
        ],
    )

    report = review.build_review(tmp_path)

    assert report["decision"] == "DIRTY_WORKTREE_OWNER_REVIEW_READY"
    assert report["owner_review_ready"] is True
    assert report["unowned_path_count"] == 0
    assert report["unowned_paths"] == []


def test_require_owned_returns_failure_for_unowned_paths(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps({"shared_allow": [], "agents": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(review, "git_status_porcelain", lambda _root: ["?? scratch.py"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_dirty_worktree_review.py",
            "--root",
            str(tmp_path),
            "--require-owned",
            "--json",
        ],
    )

    assert review.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "DIRTY_WORKTREE_UNOWNED_PATHS_BLOCKED"
    assert payload["unowned_paths"] == ["scratch.py"]


def test_require_agent_claimable_fails_without_agent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps(
            {
                "shared_allow": [],
                "agents": {"codex-implementer": {"allow": ["src/"]}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        review,
        "git_status_porcelain",
        lambda _root: [" M src/core/app.py"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_dirty_worktree_review.py",
            "--root",
            str(tmp_path),
            "--require-agent-claimable",
            "--json",
        ],
    )

    assert review.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_review"]["agent"] is None
    assert payload["agent_review"]["agent_required_for_claimable_gate"] is True
    assert payload["agent_review"]["all_dirty_packages_claimable_by_agent"] is False


def test_require_agent_claimable_fails_for_handoff_packages(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps(
            {
                "shared_allow": [],
                "agents": {
                    "codex-implementer": {"allow": ["src/"]},
                    "vpn-runtime-ops": {"allow": ["services/nl-server/"]},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        review,
        "git_status_porcelain",
        lambda _root: [
            " M src/core/app.py",
            "?? services/nl-server/ghost-access/new_probe.py",
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_dirty_worktree_review.py",
            "--root",
            str(tmp_path),
            "--agent",
            "codex-implementer",
            "--require-agent-claimable",
            "--json",
        ],
    )

    assert review.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_review"]["agent"] == "codex-implementer"
    assert payload["agent_review"]["agent_required_for_claimable_gate"] is False
    assert payload["agent_review"]["all_dirty_packages_claimable_by_agent"] is False
    assert "nl_runtime_diagnostics" in payload["agent_review"][
        "handoff_required_packages"
    ]
    assert "core_api_runtime" in payload["agent_review"]["claimable_packages"]


def test_require_agent_claimable_passes_when_agent_owns_all_dirty_packages(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ownership_path = tmp_path / "docs/team/swarm_ownership.json"
    ownership_path.parent.mkdir(parents=True)
    ownership_path.write_text(
        json.dumps(
            {
                "shared_allow": [],
                "agents": {
                    "codex-implementer": {"allow": ["src/", "tests/"]},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        review,
        "git_status_porcelain",
        lambda _root: [
            " M src/core/app.py",
            "?? tests/unit/core/test_app_desktop_live_snapshot_unit.py",
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_dirty_worktree_review.py",
            "--root",
            str(tmp_path),
            "--agent",
            "codex-implementer",
            "--require-agent-claimable",
            "--json",
        ],
    )

    assert review.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_review"]["agent_required_for_claimable_gate"] is False
    assert payload["agent_review"]["all_dirty_packages_claimable_by_agent"] is True
    assert payload["agent_review"]["handoff_required_packages"] == []
    assert payload["agent_review"]["claimable_packages"] == ["core_api_runtime"]


def test_real_ownership_map_covers_nl_runtime_diagnostics() -> None:
    ownership = review.load_ownership(ROOT)

    assert "vpn-runtime-ops" in review.owner_candidates(
        "nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md",
        ownership,
    )
    assert "vpn-runtime-ops" in review.owner_candidates(
        "services/nl-server/manifest.json",
        ownership,
    )


def test_real_ownership_map_covers_frontend_native_app() -> None:
    ownership = review.load_ownership(ROOT)

    assert "codex-implementer" in review.owner_candidates(
        "x0tta6bl4-app/src/App.tsx",
        ownership,
    )
    assert "codex-implementer" in review.owner_candidates(
        "src-tauri/src/main.rs",
        ownership,
    )


def test_real_ownership_map_covers_api_route_inventory_tool() -> None:
    ownership = review.load_ownership(ROOT)

    assert "codex-implementer" in review.owner_candidates("list_routes.py", ownership)
    assert "codex-implementer" in review.owner_candidates(
        "scripts/ops/list_api_routes.py",
        ownership,
    )
    assert "codex-implementer" in review.owner_candidates(
        "tests/unit/scripts/test_list_api_routes.py",
        ownership,
    )


def test_real_ownership_map_covers_dao_governance_policy() -> None:
    ownership = review.load_ownership(ROOT)

    assert "codex-implementer" in review.owner_candidates(
        "config/dao_policy.json",
        ownership,
    )


def test_explicit_git_add_command_is_shell_quoted() -> None:
    command = review.explicit_git_add_command(
        ["path one.py", "path-$two.py", "path-three.py"],
        max_paths=3,
    )

    assert command["path_count"] == 3
    assert command["shown_path_count"] == 3
    assert command["truncated"] is False
    assert command["command"] == "git add -- 'path one.py' 'path-$two.py' path-three.py"
    assert "git add -A" in command["note"]
