import asyncio

from src.dao.token import MeshToken
from src.network.batman.node_manager import NodeManager


async def test_dao_rewards():
    print("🧪 Testing DAO Rewards System...")

    # 1. Setup
    token = MeshToken()
    manager = NodeManager(mesh_id="test_mesh", local_node_id="gateway_1")
    manager.set_token(token)

    # 2. Test Deployment Reward
    print("\n[Case 1] Node Registration Reward")
    node_id = "node_alpha"
    manager.register_node(
        node_id=node_id,
        mac_address="00:11:22:33:44:55",
        ip_address="10.0.0.2",
        spiffe_id="spiffe://x0tta6bl4/node/alpha",
    )

    balance = token.balance_of(node_id)
    print(f"Node {node_id} balance: {balance} X0T")
    assert balance == 50.0, f"Expected 50.0, got {balance}"
    print("✅ Deployment reward successful!")

    # 3. Test Epoch Rewards (Uptime)
    print("\n[Case 2] Uptime Epoch Rewards")
    # Simulate stakers
    token.mint(node_id, 1000)
    token.stake(node_id, 500)

    # Bypass epoch duration check for testing
    token.last_epoch_time = 0

    # Run a health monitor cycle manually or trigger reward distribution
    uptimes = {node_id: 1.0}
    rewards = token.distribute_epoch_rewards(uptimes)

    new_balance = token.balance_of(node_id)
    print(f"Node {node_id} balance after reward: {new_balance} X0T")
    print(f"Distributed rewards this epoch: {rewards}")
    assert len(rewards) > 0, "No rewards distributed"
    print("✅ Uptime rewards successful!")

    print("\n🚀 All DAO Reward tests PASSED!")


if __name__ == "__main__":
    asyncio.run(test_dao_rewards())
