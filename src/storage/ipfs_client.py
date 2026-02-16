"""
IPFS Client for x0tta6bl4 Knowledge Storage
===========================================

Provides IPFS integration for distributed knowledge storage.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import IPFS client
try:
    import ipfshttpclient

    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    logger.warning(
        "⚠️ ipfshttpclient not available. Install with: pip install ipfshttpclient"
    )


class IPFSClient:
    """
    IPFS client for storing and retrieving knowledge entries.

    Features:
    - Store incidents, MAPE-K states, recovery plans
    - Retrieve by CID
    - Pin important entries
    - Manage hot/warm/cold storage
    """

    def __init__(self, ipfs_api_url: str = "/ip4/127.0.0.1/tcp/5001"):
        """
        Initialize IPFS client.

        Args:
            ipfs_api_url: IPFS API endpoint (default: local daemon)
        """
        self.ipfs_api_url = ipfs_api_url
        self.client = None

        if IPFS_AVAILABLE:
            try:
                self.client = ipfshttpclient.connect(ipfs_api_url)
                logger.info(f"✅ Connected to IPFS daemon at {ipfs_api_url}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect to IPFS: {e}. Using mock mode.")
                self.client = None
        else:
            logger.warning("⚠️ IPFS client not available. Using mock mode.")

    async def add(self, data: str, pin: bool = True) -> str:
        """
        Add data to IPFS.

        Args:
            data: Data to store (JSON string or bytes)
            pin: Whether to pin the data

        Returns:
            CID (Content Identifier)
        """
        if not self.client:
            # Mock mode: return fake CID
            import hashlib

            cid = "Qm" + hashlib.sha256(data.encode()).hexdigest()[:44]
            logger.debug(f"Mock IPFS: Stored data → {cid}")
            return cid

        try:
            # Add data to IPFS
            result = (
                self.client.add_json(data)
                if isinstance(data, (dict, list))
                else self.client.add_str(data)
            )

            if isinstance(result, dict):
                cid = result.get("Hash") or result.get("cid") or str(result)
            else:
                cid = str(result)

            # Pin if requested
            if pin:
                await self.pin(cid)

            logger.info(f"📦 Stored in IPFS: {cid}")
            return cid

        except Exception as e:
            logger.error(f"❌ Failed to add to IPFS: {e}")
            # Fallback to mock
            import hashlib

            cid = "Qm" + hashlib.sha256(str(data).encode()).hexdigest()[:44]
            return cid

    async def get(self, cid: str) -> Optional[str]:
        """
        Retrieve data from IPFS by CID.

        Args:
            cid: Content Identifier

        Returns:
            Data as string, or None if not found
        """
        if not self.client:
            logger.debug(f"Mock IPFS: Retrieving {cid}")
            return None

        try:
            data = self.client.cat(cid)
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            logger.debug(f"📥 Retrieved from IPFS: {cid}")
            return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve from IPFS {cid}: {e}")
            return None

    async def pin(self, cid: str) -> bool:
        """
        Pin data in IPFS (keep it available).

        Args:
            cid: Content Identifier

        Returns:
            True if pinned successfully
        """
        if not self.client:
            return True  # Mock: always succeed

        try:
            self.client.pin.add(cid)
            logger.debug(f"📌 Pinned: {cid}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to pin {cid}: {e}")
            return False

    async def unpin(self, cid: str) -> bool:
        """
        Unpin data from IPFS.

        Args:
            cid: Content Identifier

        Returns:
            True if unpinned successfully
        """
        if not self.client:
            return True

        try:
            self.client.pin.rm(cid)
            logger.debug(f"📌 Unpinned: {cid}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to unpin {cid}: {e}")
            return False

    def is_available(self) -> bool:
        """Check if IPFS client is available."""
        return self.client is not None


class MockIPFSClient:
    """Mock IPFS client for testing/development."""

    def __init__(self):
        self.storage: Dict[str, str] = {}
        logger.info("🔧 Using Mock IPFS client")

    async def add(self, data: str, pin: bool = True) -> str:
        import hashlib

        cid = "Qm" + hashlib.sha256(data.encode()).hexdigest()[:44]
        self.storage[cid] = data
        logger.debug(f"Mock IPFS: Stored → {cid}")
        return cid

    async def get(self, cid: str) -> Optional[str]:
        return self.storage.get(cid)

    async def pin(self, cid: str) -> bool:
        return True

    async def unpin(self, cid: str) -> bool:
        return True

    def is_available(self) -> bool:
        return True
