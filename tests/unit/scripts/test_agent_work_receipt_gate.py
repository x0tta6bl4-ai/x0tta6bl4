from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "agents" / "agent_work_receipt_gate.py"
POLICY = ROOT / "products" / "agent-work-receipt-gate" / "policy.example.json"
RECEIPTS = ROOT / "products" / "agent-work-receipt-gate" / "receipts"


def run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def parse_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def test_valid_receipt_passes() -> None:
    result = run_gate(
        "validate",
        "--policy",
        str(POLICY.relative_to(ROOT)),
        "--receipt",
        str((RECEIPTS / "valid.json").relative_to(ROOT)),
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = parse_stdout(result)
    assert payload["ok"] is True
    assert payload["failure_signature"] == ""


def test_missing_verification_has_stable_signature() -> None:
    result = run_gate(
        "validate",
        "--policy",
        str(POLICY.relative_to(ROOT)),
        "--receipt",
        str((RECEIPTS / "invalid-missing-verification.json").relative_to(ROOT)),
        "--json",
    )

    assert result.returncode == 2
    payload = parse_stdout(result)
    assert payload["ok"] is False
    assert payload["failure_signature"] == "handoff.invalid.missing_verification"


def test_forbidden_claim_has_stable_signature() -> None:
    result = run_gate(
        "validate",
        "--policy",
        str(POLICY.relative_to(ROOT)),
        "--receipt",
        str((RECEIPTS / "invalid-forbidden-claim.json").relative_to(ROOT)),
        "--json",
    )

    assert result.returncode == 2
    payload = parse_stdout(result)
    assert payload["ok"] is False
    assert payload["failure_signature"] == "receipt.invalid.forbidden_claim"


def test_missing_source_truth_has_stable_signature() -> None:
    result = run_gate(
        "validate",
        "--policy",
        str(POLICY.relative_to(ROOT)),
        "--receipt",
        str((RECEIPTS / "invalid-missing-source-truth.json").relative_to(ROOT)),
        "--json",
    )

    assert result.returncode == 2
    payload = parse_stdout(result)
    assert payload["ok"] is False
    assert payload["failure_signature"] == "receipt.invalid.missing_source_of_truth"


def test_markdown_report_for_valid_receipt() -> None:
    result = run_gate(
        "report",
        "--policy",
        str(POLICY.relative_to(ROOT)),
        "--receipt",
        str((RECEIPTS / "valid.json").relative_to(ROOT)),
    )

    assert result.returncode == 0
    assert "Status: PASS" in result.stdout
    assert "Remaining Gaps" in result.stdout
