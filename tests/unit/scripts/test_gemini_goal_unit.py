import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "gemini_goal.py"
    spec = importlib.util.spec_from_file_location("gemini_goal", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_status_marks_superseded_gemini_claims(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / ".agent-coord/state.json",
        {
            "agents": {
                "gemini": {
                    "status": "in_progress",
                    "last_verified_here": [
                        "open5gs_remote_bridge: reachable",
                        "xdp_live_attach: prog_id 1110 on enp8s0",
                        "GHOST-CORE: MVP stabilization completed",
                        "Share-to-Earn: payout engine configured",
                        "SPIRE: Zero Trust identity verified",
                    ],
                }
            },
            "global_not_verified_yet": ["manual client matrix"],
        },
    )
    _write_json(
        tmp_path / ".tmp/validation-shards/gemini-ghost-core-vv-audit-current.json",
        {
            "decision": "PARTIAL_CONTEXT_ONLY_NOT_PRODUCTION_READY",
            "generated_at": "2026-05-20T21:06:37Z",
            "summary": {"production_promotion_allowed": False},
            "not_verified_yet": ["current live SPIRE SVID"],
            "claims": [
                {
                    "id": "ebpf_current_xdp_attach",
                    "claim": "eBPF/XDP protection is currently attached and verified.",
                    "decision": "NOT_VERIFIED_CURRENT_RUNTIME",
                },
                {
                    "id": "ghost_core_mvp_stabilization_completed",
                    "claim": "GHOST-CORE MVP stabilization is completed.",
                    "decision": "PARTIAL_LOCAL_RUNTIME_ONLY",
                },
                {
                    "id": "share_to_earn_blockchain_payout_engine",
                    "claim": "Share-to-Earn payout engine is configured for real X0T payouts.",
                    "decision": "NOT_VERIFIED",
                },
                {
                    "id": "spire_live_svid_current_runtime",
                    "claim": "SPIRE Zero Trust identity is verified in the current runtime.",
                    "decision": "NOT_VERIFIED_CURRENT_RUNTIME",
                },
            ],
        },
    )

    mod.show_goal()

    output = capsys.readouterr().out
    assert "Current V&V Audit Boundary" in output
    assert "Superseded Gemini Claims" in output
    assert "xdp_live_attach: prog_id 1110 on enp8s0 -> NOT_VERIFIED_CURRENT_RUNTIME" in output
    assert "GHOST-CORE: MVP stabilization completed -> PARTIAL_LOCAL_RUNTIME_ONLY" in output
    assert "Share-to-Earn: payout engine configured -> NOT_VERIFIED" in output
    assert "SPIRE: Zero Trust identity verified -> NOT_VERIFIED_CURRENT_RUNTIME" in output
    assert "Recently Verified by Gemini" not in output


def test_audit_override_ignores_unrelated_verified_items():
    mod = _load_module()
    audit = {
        "claims": [
            {
                "id": "ebpf_current_xdp_attach",
                "decision": "NOT_VERIFIED_CURRENT_RUNTIME",
            }
        ]
    }

    assert mod.audit_override_for_verified_item("open5gs_remote_bridge: reachable", audit) == {}
