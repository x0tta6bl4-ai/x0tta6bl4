"""External X0T settlement evidence gate.

This module validates retained evidence for an already-submitted X0T
settlement transaction. It is intentionally read-only: it never submits a
transaction, mutates runtime state, or upgrades the integration objective by
itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_EVIDENCE_PATH = ".tmp/external-settlement-evidence/settlement-submit.json"
DEFAULT_EVIDENCE_REPORT = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
DEFAULT_RPC_REPORT = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
DEFAULT_BLOCKER_REPORT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
DEFAULT_PREFLIGHT_REPORT = ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json"

HEX_32 = re.compile(r"^0x[a-fA-F0-9]{64}$")
ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
PACKET_HASH = re.compile(r"^[a-f0-9]{64}$")
PLACEHOLDER_RE = re.compile(r"(placeholder|example|todo|template|replace|changeme|<|>)", re.IGNORECASE)

CHAIN_IDS = {
    "base-sepolia": 84532,
    "base_sepolia": 84532,
    "base-mainnet": 8453,
    "base": 8453,
}

EXPLORER_URLS = {
    "base-sepolia": "https://sepolia.basescan.org/tx/",
    "base_sepolia": "https://sepolia.basescan.org/tx/",
    "base-mainnet": "https://basescan.org/tx/",
    "base": "https://basescan.org/tx/",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    if not path.exists():
        return None, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"evidence JSON is unreadable: {exc}"]
    if not isinstance(data, dict):
        return None, ["evidence JSON root must be an object"]
    return data, []


def _is_placeholder(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip() or bool(PLACEHOLDER_RE.search(value))


def _positive_block_number(value: Any) -> bool:
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        value = value.strip()
        if value.startswith(("0x", "0X")):
            try:
                return int(value, 16) > 0
            except ValueError:
                return False
        if value.isdigit():
            return int(value) > 0
    return False


def _normalize_chain(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "-")


def _hex_to_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith(("0x", "0X")) else int(value)
        except ValueError:
            return None
    return None


def _required_string(value: Any) -> str:
    return str(value or "").strip()


def _source_command(
    transaction_hash: str,
    destination_chain: str,
    settlement_id: str,
    evidence_path: str,
) -> str:
    return (
        "python3 -m src.integration.external_settlement --root . --capture-from-rpc "
        f"--transaction-hash {transaction_hash} --destination-chain {destination_chain} "
        f"--settlement-id {settlement_id} --rpc-url $X0T_BASE_RPC_URL "
        f"--evidence {evidence_path} --write-evidence"
    )


def _verify_command(evidence_path: str) -> str:
    return (
        "python3 -m src.integration.external_settlement --root . "
        f"--evidence {evidence_path} --rpc-url $X0T_BASE_RPC_URL --require-ready"
    )


def _packet_hash(payload: Dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("packet_hash", None)
    encoded = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _capture_input_values(
    transaction_hash: str,
    destination_chain: str,
    settlement_id: str,
    rpc_url: str,
    collected_by: str,
) -> Tuple[str, str, str, str, str, List[str]]:
    errors: List[str] = []
    tx_hash = _required_string(transaction_hash)
    chain = _normalize_chain(destination_chain)
    sid = _required_string(settlement_id)
    rpc = _required_string(rpc_url)
    collector = _required_string(collected_by)

    if not HEX_32.match(tx_hash):
        errors.append("transaction_hash must be a 0x-prefixed 32-byte hex transaction hash")
    if chain not in CHAIN_IDS:
        errors.append("destination_chain must be base-sepolia/base_sepolia or base-mainnet/base")
    if _is_placeholder(sid):
        errors.append("settlement_id is required and must not be a placeholder")
    if not rpc:
        errors.append("rpc_url is required for live receipt capture")
    elif not rpc.startswith(("https://", "http://")):
        errors.append("rpc_url must be an HTTP(S) read-only Base RPC URL")
    if _is_placeholder(collector):
        errors.append("collected_by must be specific and must not be a placeholder")

    return tx_hash, chain, sid, rpc, collector, errors


def build_capture_preflight_report(
    transaction_hash: str,
    destination_chain: str,
    settlement_id: str,
    rpc_url: str,
    evidence_display_path: str = DEFAULT_EVIDENCE_PATH,
    collected_by: str = "codex-external-settlement-rpc-collector",
) -> Dict[str, Any]:
    """Validate capture inputs without calling RPC or materializing evidence."""

    tx_hash, chain, sid, rpc, collector, errors = _capture_input_values(
        transaction_hash,
        destination_chain,
        settlement_id,
        rpc_url,
        collected_by,
    )
    ready = not errors
    expected_chain_id = CHAIN_IDS.get(chain)
    rpc_scheme = rpc.split(":", 1)[0].lower() if "://" in rpc else ""

    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-capture-preflight-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only preflight for external X0T settlement capture inputs. It validates "
            "operator-provided transaction hash, Base chain, settlement id, and RPC URL shape. "
            "It does not call RPC providers, submit transactions, write settlement evidence, "
            "mutate runtime state, or mark the objective complete."
        ),
        "materializes_evidence": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
        "goal_can_be_marked_complete": False,
        "evidence_path": evidence_display_path,
        "input_status": {
            "transaction_hash_valid": bool(HEX_32.match(tx_hash)),
            "destination_chain": chain,
            "destination_chain_supported": chain in CHAIN_IDS,
            "expected_chain_id": expected_chain_id,
            "settlement_id_present": not _is_placeholder(sid),
            "rpc_url_available": bool(rpc),
            "rpc_url_scheme": rpc_scheme,
            "collected_by_present": not _is_placeholder(collector),
        },
        "summary": {
            "capture_inputs_ready": ready,
            "transaction_hash_valid": bool(HEX_32.match(tx_hash)),
            "destination_chain_supported": chain in CHAIN_IDS,
            "settlement_id_present": not _is_placeholder(sid),
            "rpc_url_available": bool(rpc),
            "collected_by_present": not _is_placeholder(collector),
            "errors_total": len(errors),
        },
        "errors": errors,
        "next_command": (
            "python3 -m src.integration.external_settlement --root . --capture-from-rpc "
            "--transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain "
            f"{chain or 'base-sepolia'} --settlement-id \"$X0T_SETTLEMENT_ID\" "
            "--rpc-url \"$X0T_BASE_RPC_URL\" "
            f"--evidence {evidence_display_path} --write-evidence --require-ready"
        ),
        "not_verified_yet": [] if ready else [
            "operator-provided submitted X0T transaction hash",
            "operator-provided matching Base RPC URL",
            "operator-provided non-placeholder settlement id",
        ],
    }


def capture_evidence_from_rpc(
    transaction_hash: str,
    destination_chain: str,
    settlement_id: str,
    rpc_url: str,
    evidence_display_path: str = DEFAULT_EVIDENCE_PATH,
    collected_by: str = "codex-external-settlement-rpc-collector",
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Build retained settlement evidence from a live read-only RPC endpoint."""

    tx_hash, chain, sid, rpc, collector, errors = _capture_input_values(
        transaction_hash,
        destination_chain,
        settlement_id,
        rpc_url,
        collected_by,
    )
    if errors:
        return None, errors

    observed_chain_id: Optional[int] = None
    receipt: Optional[Dict[str, Any]] = None
    transaction: Optional[Dict[str, Any]] = None
    try:
        observed_chain_id = _hex_to_int(_rpc_call(rpc, "eth_chainId", []))
        receipt = _rpc_call(rpc, "eth_getTransactionReceipt", [tx_hash])
        transaction = _rpc_call(rpc, "eth_getTransactionByHash", [tx_hash])
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        return None, [f"live RPC capture failed: {exc}"]

    expected_chain_id = CHAIN_IDS[chain]
    if observed_chain_id != expected_chain_id:
        errors.append(f"observed chain id {observed_chain_id} does not match expected {expected_chain_id}")
    if not isinstance(receipt, dict):
        errors.append("live eth_getTransactionReceipt did not return a mined receipt")
    if not isinstance(transaction, dict):
        errors.append("live eth_getTransactionByHash did not return a transaction")
    if errors:
        return None, errors

    assert receipt is not None
    assert transaction is not None
    receipt_hash = _required_string(receipt.get("transactionHash"))
    tx_observed_hash = _required_string(transaction.get("hash"))
    if receipt_hash.lower() != tx_hash.lower():
        errors.append(f"receipt transaction hash mismatch: observed {receipt_hash}, expected {tx_hash}")
    if tx_observed_hash.lower() != tx_hash.lower():
        errors.append(f"transaction hash mismatch: observed {tx_observed_hash}, expected {tx_hash}")
    if _hex_to_int(receipt.get("status")) != 1:
        errors.append("receipt status is not successful")

    block_number = _hex_to_int(receipt.get("blockNumber"))
    transaction_block_number = _hex_to_int(transaction.get("blockNumber"))
    if not block_number or block_number <= 0:
        errors.append("receipt blockNumber must be positive")
    if transaction_block_number != block_number:
        errors.append("transaction blockNumber mismatch")

    block_hash = _required_string(receipt.get("blockHash"))
    from_address = _required_string(receipt.get("from") or transaction.get("from"))
    to_address = _required_string(receipt.get("to") or transaction.get("to"))
    if not HEX_32.match(block_hash):
        errors.append("receipt blockHash must be a 0x-prefixed 32-byte hash")
    if not ADDRESS.match(from_address):
        errors.append("receipt/transaction from address must be a 0x-prefixed 20-byte address")
    if not ADDRESS.match(to_address):
        errors.append("receipt/transaction to address must be a 0x-prefixed 20-byte address")
    if errors:
        return None, errors

    explorer_url = EXPLORER_URLS[chain] + tx_hash
    payload: Dict[str, Any] = {
        "status": "VERIFIED HERE",
        "evidence_status": "VERIFIED HERE",
        "schema_version": "x0tta6bl4-x0t-external-settlement-submit-evidence-v1",
        "collected_at": utc_now(),
        "collected_by": collector,
        "settlement_submitted": True,
        "destination_chain": chain,
        "destination_chain_id": expected_chain_id,
        "observed_chain_id": observed_chain_id,
        "settlement_id": sid,
        "token_symbol": "X0T",
        "transaction_receipt_status": "mined_success",
        "block_number": block_number,
        "block_hash": block_hash,
        "from_address": from_address,
        "to_address": to_address,
        "transaction_hash": tx_hash,
        "explorer_url": explorer_url,
        "source_commands": [
            _source_command(tx_hash, chain, sid, evidence_display_path),
            _verify_command(evidence_display_path),
        ],
        "source_rpc_methods": [
            "eth_chainId",
            "eth_getTransactionReceipt",
            "eth_getTransactionByHash",
        ],
        "template_only": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_files": True,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "claim_boundary": (
            "Retained external X0T settlement receipt captured from read-only Base RPC. "
            "The collector reads chain state for an already-submitted transaction and does not submit "
            "transactions or mutate production runtime."
        ),
    }
    payload["packet_hash"] = _packet_hash(payload)
    return payload, []


@dataclass
class EvidenceGateResult:
    evidence_path: Path
    data: Optional[Dict[str, Any]]
    errors: List[str] = field(default_factory=list)
    display_path: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.data is not None or self.evidence_path.exists()

    @property
    def valid(self) -> bool:
        return self.data is not None and not self.errors

    @property
    def transaction_hash(self) -> str:
        if not self.data:
            return ""
        return str(self.data.get("transaction_hash", ""))

    @property
    def destination_chain(self) -> str:
        if not self.data:
            return ""
        return _normalize_chain(self.data.get("destination_chain", ""))

    @property
    def expected_chain_id(self) -> Optional[int]:
        return CHAIN_IDS.get(self.destination_chain)

    def report(self) -> Dict[str, Any]:
        evidence_path = self.display_path or str(self.evidence_path)
        return {
            "schema_version": "x0tta6bl4-x0t-external-settlement-evidence-gate-v2",
            "generated_at": utc_now(),
            "status": "VERIFIED HERE",
            "ok": True,
            "claim_boundary": (
                "Non-live external X0T settlement evidence gate. It validates a retained submitted "
                "settlement receipt and does not contact RPC providers, submit transactions, mutate "
                "runtime state, or mark /goal complete."
            ),
            "materializes_evidence": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "mutates_chain": False,
            "mutates_files": False,
            "mutates_nl": False,
            "mutates_spb": False,
            "mutates_vpn_runtime": False,
            "evidence_file": {
                "path": evidence_path,
                "status": "VALID" if self.valid else ("INVALID" if self.found else "NOT_FOUND"),
                "errors": list(self.errors),
            },
            "summary": {
                "evidence_file_found": self.found,
                "evidence_file_invalid": self.found and not self.valid,
                "evidence_file_valid": self.valid,
                "fake_external_settlement_prevention_enforced": True,
                "x0t_external_settlement_ready": self.valid,
            },
            "x0t_external_settlement_decision": "READY" if self.valid else "BLOCKED",
            "goal_can_be_marked_complete": False,
            "not_verified_yet": [] if self.valid else [
                "retained external X0T settlement receipt with VERIFIED HERE status",
                "full 32-byte transaction hash tied to retained source commands and explorer URL",
                "chain-matched destination chain, explorer URL, RPC/source commands, settlement id, and X0T token symbol",
            ],
        }


def validate_evidence_file(path: Path, display_path: Optional[str] = None) -> EvidenceGateResult:
    data, read_errors = _read_json(path)
    if data is None:
        return EvidenceGateResult(path, data, read_errors, display_path)

    errors = list(read_errors)
    status = data.get("status") or data.get("evidence_status")
    if status != "VERIFIED HERE":
        errors.append("status/evidence_status must be VERIFIED HERE")
    if data.get("settlement_submitted") is not True:
        errors.append("settlement_submitted must be true")

    destination_chain = _normalize_chain(data.get("destination_chain"))
    if destination_chain not in CHAIN_IDS:
        errors.append("destination_chain must be base-sepolia/base_sepolia or base-mainnet/base")
    if _is_placeholder(data.get("settlement_id")):
        errors.append("settlement_id is required and must not be a placeholder")

    token_symbol = str(data.get("token_symbol", "")).strip().upper()
    if token_symbol != "X0T":
        errors.append("token_symbol must be X0T")

    receipt_status = str(data.get("transaction_receipt_status", "")).strip().lower()
    if receipt_status not in {"success", "succeeded", "1", "0x1", "mined_success"}:
        errors.append("transaction_receipt_status must indicate a successful mined receipt")
    if not _positive_block_number(data.get("block_number")):
        errors.append("block_number must be a positive integer or hex quantity")
    if not HEX_32.match(str(data.get("block_hash", ""))):
        errors.append("block_hash must be a 0x-prefixed 32-byte block hash")
    if not ADDRESS.match(str(data.get("from_address", ""))):
        errors.append("from_address must be a 0x-prefixed 20-byte address")
    if not ADDRESS.match(str(data.get("to_address", ""))):
        errors.append("to_address must be a 0x-prefixed 20-byte address")

    transaction_hash = str(data.get("transaction_hash", ""))
    if not HEX_32.match(transaction_hash):
        errors.append("transaction_hash must be a 0x-prefixed 32-byte hex transaction hash")

    source_commands = data.get("source_commands")
    if not isinstance(source_commands, list) or len(source_commands) < 2:
        errors.append("source_commands must contain at least two retained commands")
    else:
        for idx, command in enumerate(source_commands):
            if _is_placeholder(command):
                errors.append(f"source_commands[{idx}] must not contain placeholder text")
        if HEX_32.match(transaction_hash) and not any(
            transaction_hash.lower() in str(command).lower() for command in source_commands
        ):
            errors.append("source_commands must include the exact transaction hash")

    explorer_url = data.get("explorer_url")
    if _is_placeholder(explorer_url) or not str(explorer_url).startswith("https://"):
        errors.append("explorer_url must be a non-placeholder HTTPS URL")
    elif transaction_hash and transaction_hash.lower() not in str(explorer_url).lower():
        errors.append("explorer_url must contain the exact transaction hash")
    elif destination_chain in EXPLORER_URLS and not str(explorer_url).lower().startswith(
        EXPLORER_URLS[destination_chain].lower()
    ):
        errors.append("explorer_url host must match destination_chain")

    packet_hash = str(data.get("packet_hash", ""))
    if not PACKET_HASH.match(packet_hash):
        errors.append("packet_hash must be a 64-character lowercase hex digest")
    elif packet_hash != _packet_hash(data):
        errors.append("packet_hash must match the canonical receipt payload")
    if data.get("template_only") is True:
        errors.append("template_only must not be true")

    return EvidenceGateResult(path, data, errors, display_path)


def _rpc_call(rpc_url: str, method: str, params: List[Any]) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        rpc_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parsed = urllib.parse.urlparse(rpc_url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Banned URL scheme for RPC: {parsed.scheme}")
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(f"{method} RPC error: {payload['error']}")
    return payload.get("result")


def verify_live_rpc(evidence: EvidenceGateResult, rpc_url: Optional[str]) -> Dict[str, Any]:
    errors: List[str] = []
    live_checked = False
    observed_chain_id: Optional[int] = None
    receipt: Optional[Dict[str, Any]] = None
    transaction: Optional[Dict[str, Any]] = None

    if not evidence.valid:
        errors.append("retained external X0T settlement receipt is not valid")
    if not rpc_url:
        errors.append("RPC URL for the matching Base chain is required")

    if evidence.valid and rpc_url:
        live_checked = True
        try:
            observed_chain_id = _hex_to_int(_rpc_call(rpc_url, "eth_chainId", []))
            receipt = _rpc_call(rpc_url, "eth_getTransactionReceipt", [evidence.transaction_hash])
            transaction = _rpc_call(rpc_url, "eth_getTransactionByHash", [evidence.transaction_hash])
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"live RPC check failed: {exc}")

    data = evidence.data or {}
    expected_chain_id = evidence.expected_chain_id
    if live_checked and observed_chain_id != expected_chain_id:
        errors.append(f"observed chain id {observed_chain_id} does not match expected {expected_chain_id}")

    if live_checked and not receipt:
        errors.append("live eth_getTransactionReceipt did not return a mined receipt")
    if live_checked and not transaction:
        errors.append("live eth_getTransactionByHash did not return a transaction")

    if receipt:
        comparisons = {
            "transaction_hash": ("transactionHash", data.get("transaction_hash")),
            "block_hash": ("blockHash", data.get("block_hash")),
            "from_address": ("from", data.get("from_address")),
            "to_address": ("to", data.get("to_address")),
        }
        for label, (rpc_key, expected) in comparisons.items():
            observed = receipt.get(rpc_key)
            if str(observed).lower() != str(expected).lower():
                errors.append(f"receipt {label} mismatch: observed {observed}, expected {expected}")
        if _hex_to_int(receipt.get("blockNumber")) != _hex_to_int(data.get("block_number")):
            errors.append("receipt block_number mismatch")
        if _hex_to_int(receipt.get("status")) != 1:
            errors.append("receipt status is not successful")

    if transaction:
        if str(transaction.get("hash")).lower() != evidence.transaction_hash.lower():
            errors.append("transaction hash mismatch")
        if _hex_to_int(transaction.get("blockNumber")) != _hex_to_int(data.get("block_number")):
            errors.append("transaction block_number mismatch")

    ready = evidence.valid and live_checked and not errors
    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-live-rpc-gate-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only live RPC verification for retained external X0T settlement evidence. "
            "The command checks eth_chainId, eth_getTransactionReceipt, and "
            "eth_getTransactionByHash. It never submits transactions, mutates runtime state, "
            "or marks /goal complete."
        ),
        "materializes_evidence": False,
        "runs_live_rpc": live_checked,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "rpc_endpoint": rpc_url,
        "evidence_file": {
            "path": str(evidence.evidence_path),
            "status": "VALID" if evidence.valid else ("INVALID" if evidence.found else "NOT_FOUND"),
            "errors": list(evidence.errors),
        },
        "retained_evidence_gate": {
            "decision": "READY" if evidence.valid else "BLOCKED",
            "ok": True,
        },
        "live_rpc_result": {
            "ready": ready,
            "destination_chain": evidence.destination_chain,
            "expected_chain_id": expected_chain_id,
            "observed_chain_id": observed_chain_id,
            "transaction_hash": evidence.transaction_hash,
            "receipt_block_number": _hex_to_int(receipt.get("blockNumber")) if receipt else None,
            "transaction_block_number": _hex_to_int(transaction.get("blockNumber")) if transaction else None,
            "receipt_block_hash": receipt.get("blockHash") if receipt else "",
            "errors": errors,
        },
        "summary": {
            "evidence_file_found": evidence.found,
            "retained_evidence_invalid": evidence.found and not evidence.valid,
            "retained_evidence_ready": evidence.valid,
            "rpc_url_available": bool(rpc_url),
            "live_rpc_checked": live_checked,
            "fake_external_settlement_prevention_enforced": True,
            "x0t_external_settlement_live_rpc_ready": ready,
        },
        "x0t_external_settlement_live_rpc_decision": "READY" if ready else (
            "BLOCKED_ON_EVIDENCE" if not evidence.valid else "BLOCKED_ON_RPC"
        ),
        "goal_can_be_marked_complete": False,
        "not_verified_yet": [] if ready else [
            "retained external X0T settlement receipt accepted by the non-live evidence gate",
            "RPC URL for the matching Base chain supplied via --rpc-url or X0T_*_RPC_URL",
            "live eth_getTransactionReceipt and eth_getTransactionByHash match retained receipt fields",
        ],
    }


def build_blocker_report(evidence_report: Dict[str, Any], rpc_report: Dict[str, Any]) -> Dict[str, Any]:
    evidence_ready = evidence_report["summary"]["x0t_external_settlement_ready"]
    live_ready = rpc_report["summary"]["x0t_external_settlement_live_rpc_ready"]
    evidence_path = evidence_report["evidence_file"]["path"]
    errors = list(evidence_report["evidence_file"].get("errors", []))
    errors.extend(rpc_report["live_rpc_result"].get("errors", []))

    ready = evidence_ready and live_ready
    blocking_reasons = []
    if not evidence_report["summary"]["evidence_file_found"]:
        blocking_reasons.append("retained settlement-submit.json is missing")
    elif not evidence_ready:
        blocking_reasons.append("retained settlement-submit.json is invalid")
    if evidence_ready and not live_ready:
        blocking_reasons.append("retained settlement receipt has not passed live RPC verification")
    if errors:
        blocking_reasons.extend(errors)

    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-current-blocker-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only rollup of retained external X0T settlement gate reports. It does not "
            "submit transactions, contact RPC without operator input, mutate chain/runtime state, "
            "or upgrade template/scaffold files into evidence."
        ),
        "decision": "READY_TO_PROMOTE" if ready else "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
        "goal_can_be_marked_complete": False,
        "summary": {
            "expected_evidence_path": evidence_path,
            "expected_evidence_file_exists": evidence_report["summary"]["evidence_file_found"],
            "evidence_file_valid": evidence_ready,
            "collector_evidence_ready": evidence_ready,
            "live_rpc_ready": live_ready,
            "fake_external_settlement_prevention_enforced": True,
            "x0t_external_settlement_ready": ready,
        },
        "blocking_reasons": blocking_reasons,
        "required_next_evidence": [] if ready else [
            "real submitted X0T settlement transaction hash",
            "successful mined receipt fields from Base RPC: status, block_number, block_hash, from_address, to_address",
            "source commands and HTTPS explorer URL containing the exact transaction hash",
            "retained .tmp/external-settlement-evidence/settlement-submit.json with status/evidence_status VERIFIED HERE",
        ],
        "not_verified_yet": [] if ready else [
            "submitted external X0T settlement receipt with matching live RPC report",
            "retained settlement evidence, live RPC report, and production import agree on READY_TO_PROMOTE",
        ],
        "source_artifacts": [
            DEFAULT_EVIDENCE_REPORT,
            DEFAULT_RPC_REPORT,
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_reports(
    evidence_path: Path,
    rpc_url: Optional[str],
    display_path: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    evidence = validate_evidence_file(evidence_path, display_path)
    evidence_report = evidence.report()
    rpc_report = verify_live_rpc(evidence, rpc_url)
    blocker_report = build_blocker_report(evidence_report, rpc_report)
    return evidence_report, rpc_report, blocker_report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate retained external X0T settlement evidence")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_PATH, help="retained settlement evidence JSON")
    parser.add_argument("--rpc-url", help="read-only Base RPC URL for live receipt verification")
    parser.add_argument("--capture-from-rpc", action="store_true", help="build settlement evidence JSON from a live read-only RPC receipt lookup")
    parser.add_argument("--transaction-hash", help="0x-prefixed submitted settlement transaction hash for capture mode")
    parser.add_argument("--destination-chain", default="base-sepolia", help="Base chain for capture mode")
    parser.add_argument("--settlement-id", help="non-placeholder settlement id for capture mode")
    parser.add_argument("--collected-by", default="codex-external-settlement-rpc-collector")
    parser.add_argument("--preflight-capture-inputs", action="store_true", help="validate capture inputs without calling RPC or writing settlement evidence")
    parser.add_argument("--write-evidence", action="store_true", help="write captured evidence to --evidence before running gates")
    parser.add_argument("--output-preflight-json", default=DEFAULT_PREFLIGHT_REPORT)
    parser.add_argument("--output-evidence-json", default=DEFAULT_EVIDENCE_REPORT)
    parser.add_argument("--output-rpc-json", default=DEFAULT_RPC_REPORT)
    parser.add_argument("--output-blocker-json", default=DEFAULT_BLOCKER_REPORT)
    parser.add_argument("--require-preflight-ready", action="store_true", help="return 2 unless capture inputs are structurally ready")
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless evidence and RPC are ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    evidence_input = Path(args.evidence)
    evidence_path = evidence_input if evidence_input.is_absolute() else root / evidence_input

    if args.preflight_capture_inputs:
        preflight_report = build_capture_preflight_report(
            args.transaction_hash or "",
            args.destination_chain,
            args.settlement_id or "",
            args.rpc_url or "",
            str(evidence_input),
            args.collected_by,
        )
        write_json(root / args.output_preflight_json, preflight_report)
        print(json.dumps({
            "decision": preflight_report["decision"],
            "goal_can_be_marked_complete": False,
            "summary": preflight_report["summary"],
        }, ensure_ascii=True, sort_keys=True))
        if args.require_preflight_ready and not preflight_report["summary"]["capture_inputs_ready"]:
            return 2
        return 0

    if args.capture_from_rpc:
        captured, capture_errors = capture_evidence_from_rpc(
            args.transaction_hash or "",
            args.destination_chain,
            args.settlement_id or "",
            args.rpc_url or "",
            str(evidence_input),
            args.collected_by,
        )
        if capture_errors or captured is None:
            print(json.dumps({
                "decision": "CAPTURE_BLOCKED",
                "goal_can_be_marked_complete": False,
                "errors": capture_errors,
            }, ensure_ascii=True, sort_keys=True))
            return 2
        if args.write_evidence:
            write_json(evidence_path, captured)
        else:
            print(json.dumps({
                "decision": "CAPTURE_READY_NOT_WRITTEN",
                "goal_can_be_marked_complete": False,
                "evidence": captured,
            }, ensure_ascii=True, sort_keys=True))
            return 0

    evidence_report, rpc_report, blocker_report = build_reports(evidence_path, args.rpc_url, str(evidence_input))
    write_json(root / args.output_evidence_json, evidence_report)
    write_json(root / args.output_rpc_json, rpc_report)
    write_json(root / args.output_blocker_json, blocker_report)

    summary = {
        "decision": blocker_report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": blocker_report["summary"],
    }
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))

    if args.require_ready and not blocker_report["summary"]["x0t_external_settlement_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
