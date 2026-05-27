#!/usr/bin/env python3
"""Render a template-only external X0T settlement evidence intake pack.

This script is intentionally not a collector. It never submits a transaction,
never calls RPC, and never writes the retained settlement evidence file. The
only optional file writes are template/instruction files under the configured
template directory.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.external_settlement import DEFAULT_EVIDENCE_PATH, validate_evidence_file  # noqa: E402


DEFAULT_TEMPLATE_DIR = ".tmp/external-settlement-evidence-template-pack"
DEFAULT_OUTPUT = ".tmp/validation-shards/x0t-external-settlement-evidence-scaffold-current.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _template_payload() -> Dict[str, Any]:
    return {
        "_instructions": (
            "Copy this file to the retained evidence path only after replacing every "
            "placeholder with fields captured from an already-submitted external X0T "
            "settlement transaction."
        ),
        "_not_evidence": True,
        "_template_only": True,
        "schema_version": "x0tta6bl4-x0t-external-settlement-submit-evidence-v1",
        "status": "TEMPLATE_ONLY",
        "evidence_status": "TEMPLATE_ONLY",
        "settlement_submitted": False,
        "destination_chain": "REPLACE_WITH_base-sepolia_OR_base-mainnet",
        "destination_chain_id": "REPLACE_WITH_84532_OR_8453",
        "observed_chain_id": "REPLACE_WITH_RPC_CHAIN_ID",
        "settlement_id": "REPLACE_WITH_SETTLEMENT_ID",
        "token_symbol": "X0T",
        "transaction_receipt_status": "REPLACE_WITH_SUCCESS_STATUS_1_OR_0x1",
        "block_number": "REPLACE_WITH_MINED_BLOCK_NUMBER",
        "block_hash": "REPLACE_WITH_0x_32_BYTE_BLOCK_HASH",
        "from_address": "REPLACE_WITH_0x_FROM_ADDRESS",
        "to_address": "REPLACE_WITH_0x_TO_ADDRESS",
        "transaction_hash": "REPLACE_WITH_0x_32_BYTE_TRANSACTION_HASH",
        "explorer_url": "https://REPLACE_WITH_EXPLORER_HOST/tx/REPLACE_WITH_TRANSACTION_HASH",
        "source_commands": [
            "python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain \"$X0T_DESTINATION_CHAIN\" --settlement-id \"$X0T_SETTLEMENT_ID\" --rpc-url \"$X0T_BASE_RPC_URL\" --evidence .tmp/external-settlement-evidence/settlement-submit.json --require-preflight-ready",
            "python3 -m src.integration.external_settlement --root . --capture-from-rpc --transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain \"$X0T_DESTINATION_CHAIN\" --settlement-id \"$X0T_SETTLEMENT_ID\" --rpc-url \"$X0T_BASE_RPC_URL\" --evidence .tmp/external-settlement-evidence/settlement-submit.json --write-evidence --require-ready",
            "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready",
        ],
        "source_rpc_methods": [
            "eth_chainId",
            "eth_getTransactionReceipt",
            "eth_getTransactionByHash",
        ],
        "template_only": True,
        "dry_run": False,
        "mock": False,
        "simulated": False,
        "settlement_planned_only": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "operator_notes": (
            "The preferred path is capture-from-rpc. Manual edits must still pass "
            "verify_x0t_external_settlement_evidence.py and "
            "verify_x0t_external_settlement_live_rpc.py."
        ),
        "packet_hash": "REPLACE_WITH_CANONICAL_PACKET_HASH_AFTER_ALL_FIELDS_ARE_FINAL",
    }


def _readme(expected_evidence: str) -> str:
    return f"""# X0T External Settlement Evidence Intake Scaffold

This directory is an operator scaffold, not evidence.

Required retained receipt path:

- `{expected_evidence}`

Preferred capture path:

```bash
export X0T_BASE_RPC_URL=https://...
export X0T_SETTLEMENT_TX_HASH=0x...
export X0T_DESTINATION_CHAIN=base-sepolia
export X0T_SETTLEMENT_ID=settlement-...

python3 -m src.integration.external_settlement --root . \\
  --preflight-capture-inputs \\
  --transaction-hash "$X0T_SETTLEMENT_TX_HASH" \\
  --destination-chain "$X0T_DESTINATION_CHAIN" \\
  --settlement-id "$X0T_SETTLEMENT_ID" \\
  --rpc-url "$X0T_BASE_RPC_URL" \\
  --evidence {expected_evidence} \\
  --require-preflight-ready

python3 -m src.integration.external_settlement --root . \\
  --capture-from-rpc \\
  --transaction-hash "$X0T_SETTLEMENT_TX_HASH" \\
  --destination-chain "$X0T_DESTINATION_CHAIN" \\
  --settlement-id "$X0T_SETTLEMENT_ID" \\
  --rpc-url "$X0T_BASE_RPC_URL" \\
  --evidence {expected_evidence} \\
  --write-evidence \\
  --require-ready
```

Acceptance:

```bash
python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready
python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready
```

Do not copy the template to the retained evidence path until every placeholder
has been replaced with retained data from an already-submitted transaction.
"""


def _verify_script(expected_evidence: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../.." && pwd)"
cd "${{ROOT_DIR}}"

python3 scripts/ops/verify_x0t_external_settlement_evidence.py \\
  --evidence {expected_evidence} \\
  --require-ready

python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py \\
  --evidence {expected_evidence} \\
  --require-ready
"""


def _template_files(template_dir: str, expected_evidence: str) -> List[Dict[str, Any]]:
    return [
        {
            "kind": "json_template",
            "path": f"{template_dir}/settlement-submit.template.json",
            "mode": "0644",
            "payload": _template_payload(),
        },
        {
            "kind": "markdown_instructions",
            "path": f"{template_dir}/README.md",
            "mode": "0644",
            "content": _readme(expected_evidence),
        },
        {
            "kind": "operator_verify_script",
            "path": f"{template_dir}/verify-filled-evidence.sh",
            "mode": "0755",
            "content": _verify_script(expected_evidence),
        },
    ]


def _write_file(path: Path, item: Dict[str, Any], force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if "payload" in item:
        path.write_text(
            json.dumps(item["payload"], ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(str(item.get("content", "")), encoding="utf-8")
    if item.get("mode") == "0755":
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def build_report(
    root: Path,
    template_dir: str,
    expected_evidence: str,
    write_template_files: bool,
    force: bool,
) -> Dict[str, Any]:
    template_files = _template_files(template_dir, expected_evidence)
    written = 0
    if write_template_files:
        for item in template_files:
            if _write_file(_resolve(root, str(item["path"])), item, force):
                written += 1

    expected_evidence_path = _resolve(root, expected_evidence)
    template_validation = validate_evidence_file(_resolve(root, f"{template_dir}/settlement-submit.template.json"))

    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-evidence-scaffold-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "scaffold_decision": "TEMPLATE_ONLY_NOT_EVIDENCE",
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "External X0T settlement intake scaffold only. It writes optional "
            "template files for operator intake and never submits transactions, "
            "contacts RPC providers, writes the expected evidence JSON, mutates "
            "VPN/runtime state, or marks /goal complete."
        ),
        "write_template_files_requested": write_template_files,
        "force": force,
        "mutates_files": write_template_files,
        "mutates_files_outside_outputs": False,
        "materializes_evidence": False,
        "runs_live_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "template_dir": template_dir,
        "expected_evidence_json": expected_evidence,
        "template_files": template_files,
        "operator_acceptance_commands": [
            f"python3 scripts/ops/verify_x0t_external_settlement_evidence.py --evidence {expected_evidence} --require-ready",
            f"python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --evidence {expected_evidence} --require-ready",
            (
                "python3 -m src.integration.external_settlement --root . "
                "--capture-from-rpc --transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" "
                "--destination-chain \"$X0T_DESTINATION_CHAIN\" "
                "--settlement-id \"$X0T_SETTLEMENT_ID\" "
                "--rpc-url \"$X0T_BASE_RPC_URL\" "
                f"--evidence {expected_evidence} --write-evidence --require-ready"
            ),
        ],
        "summary": {
            "template_files_total": len(template_files),
            "template_files_written": written,
            "template_status_is_not_verified": True,
            "templates_marked_not_evidence": True,
            "expected_evidence_file_exists": expected_evidence_path.exists(),
            "template_validation_rejects_as_evidence": template_validation.found and not template_validation.valid,
        },
        "not_verified_yet": [
            "operator-submitted external X0T settlement transaction",
            "retained settlement-submit.json with VERIFIED HERE status",
            "live Base RPC verification matching the retained receipt",
            "integration-spine production evidence import with all required sources ready",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render template-only X0T external settlement evidence scaffold")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--template-dir", default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--expected-evidence", default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--write-template-files", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-written", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        template_dir=args.template_dir,
        expected_evidence=args.expected_evidence,
        write_template_files=args.write_template_files,
        force=args.force,
    )
    output_path = _resolve(root, args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "scaffold_decision": report["scaffold_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_written and report["summary"]["template_files_written"] != report["summary"]["template_files_total"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
