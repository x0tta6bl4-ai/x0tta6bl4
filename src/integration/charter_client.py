"""
Charter API Integration Client
Real-world API connection for policy management

Module: src/integration/charter_client.py
Purpose: Connect MAPE-K Execute component to real Charter system
"""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)


class PolicyStatus(str, Enum):
    """Charter policy status"""

    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    FAILED = "failed"


class CommitteeState(str, Enum):
    """Charter committee operational state"""

    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    RECOVERING = "recovering"


class RealCharterClient:
    """Real Charter API Client (Production)

    Connects to actual Charter system for policy management.
    Requires Charter server running on configurable port.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize Charter client

        Args:
            base_url: Charter API base URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = None
        self.is_connected = False

    async def connect(self) -> bool:
        """Establish connection to Charter"""
        try:
            if aiohttp is None:
                logger.warning("aiohttp not available, using mock client")
                return False

            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

            # Test connectivity
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    self.is_connected = True
                    logger.info(f"✅ Connected to Charter at {self.base_url}")
                    return True
                else:
                    logger.error(f"❌ Charter health check failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close connection to Charter"""
        if self.session:
            await self.session.close()
            self.is_connected = False
            logger.info("Disconnected from Charter")

    async def get_policies(self) -> List[Dict[str, Any]]:
        """Get all active policies"""
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return []

        try:
            async with self.session.get(f"{self.base_url}/api/v1/policies") as response:
                if response.status == 200:
                    policies = await response.json()
                    logger.info(f"📋 Retrieved {len(policies)} policies")
                    return policies
                else:
                    logger.error(f"Failed to get policies: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting policies: {e}")
            return []

    async def apply_policy(self, policy_config: Dict[str, Any]) -> bool:
        """Apply a policy to Charter

        Args:
            policy_config: Policy configuration to apply

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return False

        try:
            payload = {
                "policy": policy_config,
                "timestamp": datetime.now().isoformat(),
                "source": "mape_k_executor",
            }

            async with self.session.post(
                f"{self.base_url}/api/v1/policies/apply", json=payload
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"✅ Policy applied: {result.get('policy_id')}")
                    return True
                else:
                    logger.error(f"Failed to apply policy: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error applying policy: {e}")
            return False

    async def get_committee_state(self) -> Dict[str, Any]:
        """Get current committee state and metrics"""
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return {}

        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/committee/state"
            ) as response:
                if response.status == 200:
                    state = await response.json()
                    logger.info(f"📊 Committee state: {state.get('status')}")
                    return state
                else:
                    logger.error(f"Failed to get committee state: {response.status}")
                    return {}

        except Exception as e:
            logger.error(f"Error getting committee state: {e}")
            return {}

    async def get_violations(self) -> List[Dict[str, Any]]:
        """Get current policy violations"""
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return []

        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/violations"
            ) as response:
                if response.status == 200:
                    violations = await response.json()
                    logger.info(f"⚠️ Found {len(violations)} violations")
                    return violations
                else:
                    logger.error(f"Failed to get violations: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting violations: {e}")
            return []

    async def scale_committee(self, replicas: int) -> bool:
        """Scale committee nodes

        Args:
            replicas: Target number of committee replicas

        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return False

        try:
            payload = {"replicas": replicas}

            async with self.session.post(
                f"{self.base_url}/api/v1/committee/scale", json=payload
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"📈 Committee scaled to {replicas} replicas")
                    return True
                else:
                    logger.error(f"Failed to scale committee: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error scaling committee: {e}")
            return False

    async def restart_committee(self) -> bool:
        """Restart committee with graceful shutdown"""
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return False

        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/committee/restart",
                json={"graceful": True, "timeout": 30},
            ) as response:
                if response.status in [200, 201]:
                    logger.info("🔄 Committee restart initiated")
                    return True
                else:
                    logger.error(f"Failed to restart committee: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error restarting committee: {e}")
            return False

    async def validate_policy(self, policy_config: Dict[str, Any]) -> bool:
        """Validate policy before application

        Args:
            policy_config: Policy to validate

        Returns:
            True if policy is valid
        """
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return False

        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/policies/validate", json=policy_config
            ) as response:
                if response.status == 200:
                    logger.info("✅ Policy validation passed")
                    return True
                else:
                    logger.error(f"Policy validation failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error validating policy: {e}")
            return False

    async def rollback_policy(self, policy_id: str) -> bool:
        """Rollback to previous policy version

        Args:
            policy_id: ID of policy to rollback

        Returns:
            True if rollback successful
        """
        if not self.is_connected:
            logger.warning("Not connected to Charter")
            return False

        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/policies/{policy_id}/rollback"
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"🔙 Policy {policy_id} rolled back")
                    return True
                else:
                    logger.error(f"Failed to rollback policy: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error rolling back policy: {e}")
            return False


class MockCharterClient:
    """Mock Charter Client (Development/Testing)

    Simulates Charter API for testing MAPE-K without real Charter.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize mock client"""
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.is_connected = False
        self.policies = {}
        self.violations = []
        self.committee_replicas = 3

    async def connect(self) -> bool:
        """Simulate connection"""
        logger.info(f"🔗 [MOCK] Connected to Charter at {self.base_url}")
        self.is_connected = True
        return True

    async def disconnect(self):
        """Simulate disconnection"""
        logger.info("[MOCK] Disconnected from Charter")
        self.is_connected = False

    async def get_policies(self) -> List[Dict[str, Any]]:
        """Return mock policies"""
        logger.info(f"[MOCK] Retrieved {len(self.policies)} policies")
        return list(self.policies.values())

    async def apply_policy(self, policy_config: Dict[str, Any]) -> bool:
        """Simulate policy application"""
        policy_id = f"policy_{len(self.policies)}"
        self.policies[policy_id] = policy_config
        logger.info(f"[MOCK] ✅ Policy applied: {policy_id}")
        return True

    async def get_committee_state(self) -> Dict[str, Any]:
        """Return mock committee state"""
        state = {
            "status": CommitteeState.NORMAL.value,
            "replicas": self.committee_replicas,
            "healthy_nodes": self.committee_replicas,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"[MOCK] 📊 Committee state: {state['status']}")
        return state

    async def get_violations(self) -> List[Dict[str, Any]]:
        """Return mock violations"""
        logger.info(f"[MOCK] ⚠️ Found {len(self.violations)} violations")
        return self.violations

    async def scale_committee(self, replicas: int) -> bool:
        """Simulate scaling"""
        self.committee_replicas = replicas
        logger.info(f"[MOCK] 📈 Committee scaled to {replicas} replicas")
        return True

    async def restart_committee(self) -> bool:
        """Simulate restart"""
        logger.info("[MOCK] 🔄 Committee restart initiated")
        return True

    async def validate_policy(self, policy_config: Dict[str, Any]) -> bool:
        """Simulate validation"""
        logger.info("[MOCK] ✅ Policy validation passed")
        return True

    async def rollback_policy(self, policy_id: str) -> bool:
        """Simulate rollback"""
        if policy_id in self.policies:
            del self.policies[policy_id]
        logger.info(f"[MOCK] 🔙 Policy {policy_id} rolled back")
        return True


def get_charter_client(use_mock: bool = True, **kwargs) -> any:
    """Factory function to get appropriate Charter client

    Args:
        use_mock: If True, return MockCharterClient, else RealCharterClient
        **kwargs: Arguments to pass to client constructor

    Returns:
        Charter client instance
    """
    if use_mock:
        logger.info("📝 Using MockCharterClient (testing mode)")
        return MockCharterClient(**kwargs)
    else:
        logger.info("🔌 Using RealCharterClient (production mode)")
        return RealCharterClient(**kwargs)


async def main():
    """Test Charter client"""

    # Test with mock client
    print("\n🧪 MOCK CLIENT TEST")
    print("=" * 60)

    client = MockCharterClient()

    await client.connect()

    # Get state
    state = await client.get_committee_state()
    print(f"✅ Committee state: {state['status']}")

    # Apply policy
    policy = {"name": "test_policy", "rules": [{"effect": "allow"}]}
    await client.apply_policy(policy)

    # Get policies
    policies = await client.get_policies()
    print(f"✅ Policies: {len(policies)}")

    # Scale
    await client.scale_committee(5)

    # Restart
    await client.restart_committee()

    await client.disconnect()

    print("\n✅ Mock client test complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
