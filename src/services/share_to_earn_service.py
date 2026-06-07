import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Any

from src.coordination.events import get_event_bus
from src.dao.token_rewards import TokenRewards, REWARD_RATE_XOT_PER_PACKET
from src.services.reward_events import publish_reward_settlement_event
from src.services.service_event_identity import service_event_identity

# Configuration
STATUS_FILE = Path(".tmp/economy_state.json")
STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("share-to-earn")
_SERVICE_AGENT = "share-to-earn"
_UPSTREAM_EVENT_ID_LIMIT = 10
_MESH_REWARD_UPSTREAM_SOURCE_AGENTS = {
    "mesh-telemetry-collector",
    "mesh-yggdrasil-optimizer",
    "mesh-network-manager",
    "mesh-action-enforcer",
    "real-network-adapter",
    "yggdrasil-client",
    "mesh-vpn-bridge",
}
_UPSTREAM_CLAIM_GATE_KEYS = (
    "claim_gate",
    "healing_claim",
    "mesh_api_claim_gate",
    "mesh_action_claim_gate",
    "relay_reward_claim_gate",
)
_UPSTREAM_CROSS_PLANE_CLAIM_GATE_KEYS = ("cross_plane_claim_gate",)


def _hash_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _raw_string_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raw_values = [values]
    else:
        try:
            raw_values = list(values)
        except TypeError:
            raw_values = [values]
    return [str(value) for value in raw_values if str(value)]


def _event_bus_or_none(event_bus: Any = None, project_root: str = ".") -> Any:
    if event_bus is not None:
        return event_bus
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.debug("Share-to-Earn EventBus unavailable: %s", exc)
        return None


def _first_mapping(payload: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _latest_mesh_reward_upstream_evidence(
    *,
    event_bus: Any = None,
    project_root: str = ".",
) -> dict[str, Any]:
    bus = _event_bus_or_none(event_bus, project_root)
    if bus is None or not hasattr(bus, "get_event_history"):
        return {
            "status": "event_bus_unavailable",
            "event_ids": [],
            "source_agents": [],
            "events_total": 0,
            "event_ids_limit": _UPSTREAM_EVENT_ID_LIMIT,
            "claim_gate": {},
            "cross_plane_claim_gate": {},
            "claim_gate_present": False,
            "cross_plane_claim_gate_present": False,
            "payloads_redacted": True,
        }

    try:
        events = bus.get_event_history(
            source_agents=set(_MESH_REWARD_UPSTREAM_SOURCE_AGENTS),
            limit=_UPSTREAM_EVENT_ID_LIMIT,
        )
    except Exception as exc:
        logger.debug("Share-to-Earn mesh upstream evidence lookup failed: %s", exc)
        return {
            "status": "event_bus_lookup_failed",
            "event_ids": [],
            "source_agents": [],
            "events_total": 0,
            "event_ids_limit": _UPSTREAM_EVENT_ID_LIMIT,
            "claim_gate": {},
            "cross_plane_claim_gate": {},
            "claim_gate_present": False,
            "cross_plane_claim_gate_present": False,
            "payloads_redacted": True,
        }

    event_ids = [event.event_id for event in events if getattr(event, "event_id", "")]
    source_agents = sorted(
        {
            str(getattr(event, "source_agent", ""))
            for event in events
            if str(getattr(event, "source_agent", ""))
        }
    )
    claim_gate: dict[str, Any] = {}
    cross_plane_claim_gate: dict[str, Any] = {}
    for event in reversed(events):
        payload = getattr(event, "data", {})
        if not claim_gate:
            claim_gate = _first_mapping(payload, _UPSTREAM_CLAIM_GATE_KEYS)
        if not cross_plane_claim_gate:
            cross_plane_claim_gate = _first_mapping(
                payload,
                _UPSTREAM_CROSS_PLANE_CLAIM_GATE_KEYS,
            )
        if claim_gate and cross_plane_claim_gate:
            break
    return {
        "status": "linked" if event_ids else "missing",
        "event_ids": event_ids[-_UPSTREAM_EVENT_ID_LIMIT:],
        "source_agents": source_agents,
        "events_total": len(event_ids),
        "event_ids_limit": _UPSTREAM_EVENT_ID_LIMIT,
        "claim_gate": claim_gate,
        "cross_plane_claim_gate": cross_plane_claim_gate,
        "claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "payloads_redacted": True,
    }


def _merge_reward_upstream_evidence(
    *,
    upstream_event_ids: Any = None,
    upstream_source_agents: Any = None,
    mesh_evidence: dict[str, Any],
) -> dict[str, list[str]]:
    event_ids = _raw_string_values(upstream_event_ids)
    event_ids.extend(_raw_string_values(mesh_evidence.get("event_ids")))
    source_agents = _raw_string_values(upstream_source_agents)
    source_agents.extend(_raw_string_values(mesh_evidence.get("source_agents")))
    return {
        "event_ids": event_ids[-_UPSTREAM_EVENT_ID_LIMIT:],
        "source_agents": sorted(set(source_agents)),
    }


def _configured_node_address(reward_identity: dict) -> str:
    node_address = os.getenv("GHOST_WALLET_ADDRESS") or reward_identity.get("wallet_address")
    if not node_address:
        raise RuntimeError(
            "Share-to-Earn wallet address is required. Set GHOST_WALLET_ADDRESS "
            "or SHARE_TO_EARN_WALLET_ADDRESS."
        )
    return str(node_address)


def _configured_user_id() -> int:
    raw_user_id = os.getenv("GHOST_USER_ID")
    if not raw_user_id:
        raise RuntimeError("GHOST_USER_ID is required for referral accounting")
    try:
        user_id = int(raw_user_id)
    except ValueError as exc:
        raise RuntimeError("GHOST_USER_ID must be an integer") from exc
    if user_id <= 0:
        raise RuntimeError("GHOST_USER_ID must be a positive integer")
    return user_id


def referral_count_for_user(user_id: int, db_path: str) -> int:
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM referrals WHERE referrer_user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            return int(row["count"] if row else 0)
    except sqlite3.Error as exc:
        logger.warning("Referral lookup failed for user_id=%s: %s", user_id, exc)
        return 0


def publish_share_to_earn_reward_event(
    *,
    node_id: str,
    node_address: str,
    amount: Decimal,
    packets: int,
    simulation_enabled: bool,
    status: str,
    evidence_metadata: Any = None,
    upstream_event_ids: Any = None,
    upstream_source_agents: Any = None,
    event_bus: Any = None,
    project_root: str = ".",
):
    """Record local share-to-earn accounting without claiming payout settlement."""
    if amount <= Decimal("0"):
        return None

    identity = service_event_identity(service_name=_SERVICE_AGENT)
    mesh_upstream_evidence = _latest_mesh_reward_upstream_evidence(
        event_bus=event_bus,
        project_root=project_root,
    )
    merged_upstream = _merge_reward_upstream_evidence(
        upstream_event_ids=upstream_event_ids,
        upstream_source_agents=upstream_source_agents,
        mesh_evidence=mesh_upstream_evidence,
    )
    reward_metadata = dict(evidence_metadata or {}) if isinstance(evidence_metadata, dict) else {}
    reward_metadata.update(
        {
            "component": "services.share_to_earn_service",
            "calculator": "share_to_earn.local_accounting",
            "simulation_enabled": simulation_enabled,
            "status": status,
            "packets": packets,
            "amount_xot": str(amount),
            "node_address_hash": _hash_value(node_address),
            "status_file_path_hash": _hash_value(STATUS_FILE),
            "mesh_upstream_evidence": {
                "status": mesh_upstream_evidence["status"],
                "source_agents": mesh_upstream_evidence["source_agents"],
                "events_total": mesh_upstream_evidence["events_total"],
                "event_ids_limit": mesh_upstream_evidence["event_ids_limit"],
                "claim_gate_present": mesh_upstream_evidence["claim_gate_present"],
                "cross_plane_claim_gate_present": (
                    mesh_upstream_evidence["cross_plane_claim_gate_present"]
                ),
                "event_ids_redacted": True,
                "payloads_redacted": True,
            },
        }
    )
    return publish_reward_settlement_event(
        transition="recorded",
        source_agent=_SERVICE_AGENT,
        node_address=node_address,
        node_id=node_id,
        spiffe_id=identity["spiffe_id"],
        did=identity["did"],
        wallet_address=identity["wallet_address"] or node_address,
        packets=packets,
        amount=str(amount),
        status=status,
        submitted_transaction=False,
        simulated=simulation_enabled,
        settlement_recorded=False,
        local_accounting_recorded=True,
        transaction_hash="",
        upstream_event_ids=merged_upstream["event_ids"],
        upstream_source_agents=merged_upstream["source_agents"],
        upstream_claim_gate=mesh_upstream_evidence["claim_gate"],
        upstream_cross_plane_claim_gate=mesh_upstream_evidence[
            "cross_plane_claim_gate"
        ],
        reason="share_to_earn_local_accounting",
        evidence_metadata=reward_metadata,
        event_bus=event_bus,
        project_root=project_root,
    )


async def main():
    logger.info("🚀 Starting Share-to-Earn Service...")

    # Configuration from environment
    rpc_url = os.getenv("RPC_URL", "https://sepolia.base.org")
    contract_addr = os.getenv("X0T_CONTRACT_ADDRESS", "0x" + "0" * 40)
    payout_threshold = Decimal(os.getenv("PAYOUT_THRESHOLD", "1.0"))
    node_id = os.getenv("NODE_ID", "local-partisan-node")
    reward_identity = service_event_identity(service_name=_SERVICE_AGENT)
    node_address = _configured_node_address(reward_identity)
    user_id = _configured_user_id()

    # Initialize rewards system
    rewards = TokenRewards(
        contract_address=contract_addr,
        rpc_url=rpc_url,
        source_agent=_SERVICE_AGENT,
        node_id=node_id,
        spiffe_id=reward_identity["spiffe_id"],
        did=reward_identity["did"],
        wallet_address=reward_identity["wallet_address"] or node_address,
    )

    logger.info(f"💰 Wallet: {node_address} | Threshold: {payout_threshold} X0T")

    last_tx_bytes = 0

    # Read initial bytes to calculate delta
    try:
        with open("/sys/class/net/eth0/statistics/tx_bytes", "r") as f:
            last_tx_bytes = int(f.read().strip())
    except Exception:
        logger.warning("Could not read eth0 tx_bytes, will use mesh_stats.json")

    while True:
        # Honest Mode: No simulation allowed

        # 1. Read real relayed packets (empirical delta)
        relayed_now = 0
        try:
            with open("/sys/class/net/eth0/statistics/tx_bytes", "r") as f:
                current_tx_bytes = int(f.read().strip())
                delta_bytes = current_tx_bytes - last_tx_bytes
                if delta_bytes > 0:
                    # Estimate packets assuming avg 1500 bytes per packet
                    relayed_now = int(delta_bytes / 1500)
                last_tx_bytes = current_tx_bytes
        except Exception:
            # Fallback to mesh_stats if eth0 is unavailable
            try:
                with open(".tmp/mesh_stats.json", "r") as f:
                    mesh_stats = json.load(f)
                    relayed_now = mesh_stats.get("relayed_packets_last_minute", 0)
            except Exception:
                pass

        # 2. Check for Multiplier (Viral Logic)
        multiplier = 1.0
        db_path = os.getenv("GHOST_ACCESS_DB_PATH", "x0tta6bl4_clean.db")
        ref_count = referral_count_for_user(user_id, db_path)
        if ref_count >= 3:
            multiplier = 2.0

        # 3. Exit Node Bonus Removed in Honest Mode (No VPN components)
        is_exit = False
        exit_reward = Decimal("0")

        # 4. Process real reward with GasGuard (On-Chain Settlement)
        # Apply multiplier and add exit reward
        effective_packets = int(relayed_now * multiplier)

        if effective_packets > 0 or exit_reward > 0:
            # If exit reward is significant, we convert it back to equivalent packets for the token rewards engine,
            # or just rely on TokenRewards API. For now we use the basic method.
            total_xot_value = (Decimal(effective_packets) * REWARD_RATE_XOT_PER_PACKET) + exit_reward
            equivalent_packets = int(total_xot_value / REWARD_RATE_XOT_PER_PACKET)

            logger.info(f"⚡ Processing empirical reward for {equivalent_packets} equivalent packets.")
            settlement_result = rewards.reward_relay(node_address, equivalent_packets)
            status = settlement_result.get("status", "error")
        else:
            status = "IDLE (No traffic relayed)"

        # 5. Update economy state
        state = {
            "node_id": node_id,
            "wallet_address": node_address,
            "balance": str(rewards.get_blockchain_balance()),
            "daily_earnings": str(rewards.get_daily_earnings(node_address)),
            "multiplier": str(multiplier),
            "referrals": int(ref_count),
            "is_exit_node": is_exit,
            "exit_bonus_today": str(exit_reward) if is_exit else "0",
            "evidence_status": "EMPIRICAL_TELEMETRY",
            "pending_payout": str(rewards.pending_rewards),
            "monthly_projection": str(rewards.get_monthly_projection(node_address)),
            "total_packets_relayed": float(rewards.total_distributed / REWARD_RATE_XOT_PER_PACKET),
            "last_update": datetime.now().isoformat(),
            "status": status,
        }

        with open(STATUS_FILE, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(
            "Economy state updated: status=%s balance=%s today=%s",
            state["status"],
            state["balance"],
            state["daily_earnings"],
        )

        # Wait for next accounting cycle
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped.")
