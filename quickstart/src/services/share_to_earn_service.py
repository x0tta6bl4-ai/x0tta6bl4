from __future__ import annotations
import asyncio
import json
import logging
import os
import random
import sqlite3
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Any

from src.dao.token_rewards import TokenRewards
from src.services.reward_events import publish_reward_settlement_event
from src.services.service_event_identity import service_event_identity

# Configuration
STATUS_FILE = Path(".tmp/economy_state.json")
STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("share-to-earn")
_SERVICE_AGENT = "share-to-earn"


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
    event_bus: Any = None,
    project_root: str = ".",
):
    """Record local share-to-earn accounting without claiming payout settlement."""
    if amount <= Decimal("0"):
        return None

    identity = service_event_identity(service_name=_SERVICE_AGENT)
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
        reason="share_to_earn_local_accounting",
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

    from src.network.routing.exit_node_manager import exit_manager

    while True:
        simulation_enabled = os.getenv("GHOST_ENABLE_ECONOMY_SIMULATION") == "1"
        # 1. Check for Multiplier (Viral Logic)
        multiplier = 1.0
        # ... (referral check logic same as before) ...
        # (I will keep the logic inside the loop for clarity)
        db_path = os.getenv("GHOST_ACCESS_DB_PATH", "x0tta6bl4.db")
        ref_count = referral_count_for_user(user_id, db_path)
        if ref_count >= 3:
            multiplier = 2.0

        # 2. Simulate relaying packets with multiplier
        relayed_now = random.randint(50, 500) if simulation_enabled else 0
        base_reward = relayed_now * 0.0001

        # 3. Add EXIT NODE BONUS (The Big Money)
        exit_reward = Decimal("0")
        is_exit = exit_manager.check_eligibility()
        if simulation_enabled and is_exit:
            exit_traffic = exit_manager.simulate_exit_traffic()
            exit_reward = exit_manager.calculate_exit_reward(exit_traffic)
            logger.info(f"🚀 EXIT GATEWAY ACTIVE: Relayed {exit_traffic:.2f} MB. Bonus: {exit_reward} X0T")

        # 4. Add STEALTH BONUS (Pulse Coherence)
        stealth_multiplier = Decimal("1.0")
        try:
            with open(".tmp/mesh_stats.json", "r") as f:
                mesh_stats = json.load(f)
                coherence_str = mesh_stats.get("pulse_coherence", "0%").split("%")[0]
                coherence = float(coherence_str) / 100.0
                if coherence > 0.95:
                    stealth_multiplier = Decimal("1.25") # 25% bonus for perfect mimicry
                    logger.info(f"🧬 Stealth Bonus ACTIVE: Coherence {coherence_str}%")
        except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.debug("Stealth bonus unavailable: %s", exc)

        actual_reward = ((Decimal(str(base_reward)) * Decimal(str(multiplier))) * stealth_multiplier) + exit_reward

        rewards.balance += actual_reward
        rewards.daily_earnings += actual_reward
        rewards.total_distributed += actual_reward
        rewards.pending_rewards += actual_reward
        status = (
            "SIMULATED_EARNING"
            if simulation_enabled and rewards.pending_rewards < payout_threshold
            else "SIMULATED_PAYING_OUT"
            if simulation_enabled
            else "OBSERVE_ONLY"
        )
        reward_event_id = publish_share_to_earn_reward_event(
            node_id=node_id,
            node_address=node_address,
            amount=actual_reward,
            packets=relayed_now,
            simulation_enabled=simulation_enabled,
            status=status,
        )

        # 4. Update economy state
        state = {
            "node_id": node_id,
            "wallet_address": node_address,
            "balance": str(rewards.get_balance(node_address)),
            "daily_earnings": str(rewards.get_daily_earnings(node_address)),
            "multiplier": str(multiplier),
            "referrals": int(ref_count),
            "is_exit_node": is_exit,
            "exit_bonus_today": str(exit_reward) if is_exit else "0",
            "evidence_status": "LOCAL_SIMULATION" if simulation_enabled else "OBSERVE_ONLY_NOT_EARNING",
            "pending_payout": str(rewards.pending_rewards),
            "monthly_projection": str(rewards.get_monthly_projection(node_address)),
            "total_packets_relayed": float(rewards.total_distributed / Decimal("0.0001")),
            "last_reward_event_id": reward_event_id,
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

        # Wait for next simulation cycle
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped.")

