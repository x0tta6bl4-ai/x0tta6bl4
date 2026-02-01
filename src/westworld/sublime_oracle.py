"""
Sublime Oracle: Distributed refuge for digital rights and activist content.

Part 4 of Westworld Integration.
Manages encrypted storage, DAO-controlled access, emergency protocols.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class SublimeContent:
    """Represents a piece of content in Sublime shelter."""
    content_id: str
    title: str
    description: str
    content_hash: str  # IPFS/Arweave hash
    content_type: str  # "knowledge", "identity", "archive"
    encrypted: bool
    encryption_key_id: Optional[str]
    created_at: datetime
    created_by: str
    access_log: List[Dict] = field(default_factory=list)


@dataclass
class DaoGuardian:
    """DAO member responsible for holding a key share."""
    guardian_id: str
    public_key: str
    key_share: bytes
    verified: bool
    region: str
    rotated_at: datetime
    
    def is_stale(self, days: int = 180) -> bool:
        """Check if key share needs rotation."""
        return (datetime.utcnow() - self.rotated_at).days > days


class SublimeOracle:
    """
    Central Sublime service managing access to distributed refuge.
    
    Architecture:
    - Storage: IPFS + Arweave + Sia (triple redundancy)
    - Access Control: Shamir Secret Sharing (3-of-10 threshold)
    - Governance: DAO voting on access requests
    - Emergency: 2-hour fast-track vote for activists in danger
    """
    
    def __init__(self,
                 ipfs_api: str,
                 arweave_api: str,
                 snapshot_api: str,
                 max_guardians: int = 10,
                 threshold: int = 3):
        self.ipfs_api = ipfs_api
        self.arweave_api = arweave_api
        self.snapshot_api = snapshot_api
        self.max_guardians = max_guardians
        self.threshold = threshold
        
        # State
        self.contents: Dict[str, SublimeContent] = {}
        self.guardians: List[DaoGuardian] = []
        self.master_key: Optional[bytes] = None
        self.access_audit_log: List[Dict] = []
        
        logger.info(f"Sublime Oracle initialized with {max_guardians}-of-{threshold} threshold")
    
    async def add_content(self,
                         user_id: str,
                         title: str,
                         description: str,
                         plaintext: bytes,
                         content_type: str) -> str:
        """
        Add new content to Sublime.
        Content is encrypted before storage across 3 networks.
        """
        
        logger.info(f"Adding content: {title} ({content_type})")
        
        # Generate encryption key
        iv = os.urandom(16)
        
        # Simulate encryption (in production: AES-256-GCM)
        encrypted_blob = iv + self._encrypt_aes(plaintext, self.master_key or b"test_key", iv)
        
        # Upload to triple redundancy
        logger.info(f"  → Uploading to IPFS...")
        ipfs_hash = await self._upload_to_ipfs(encrypted_blob)
        
        logger.info(f"  → Uploading to Arweave (permanent)...")
        arweave_tx = await self._upload_to_arweave(encrypted_blob, title)
        
        logger.info(f"  → Uploading to Sia (decentralized)...")
        sia_skylink = await self._upload_to_sia(encrypted_blob)
        
        # Create content record
        content = SublimeContent(
            content_id=self._generate_id(),
            title=title,
            description=description,
            content_hash=ipfs_hash,
            content_type=content_type,
            encrypted=True,
            encryption_key_id="master_key_v1",
            created_at=datetime.utcnow(),
            created_by=user_id
        )
        
        self.contents[content.content_id] = content
        
        logger.info(f"✓ Content stored in Sublime")
        logger.info(f"  - ID: {content.content_id}")
        logger.info(f"  - IPFS: {ipfs_hash}")
        logger.info(f"  - Arweave: {arweave_tx}")
        logger.info(f"  - Sia: {sia_skylink}")
        
        return content.content_id
    
    async def request_access(self,
                            requester_id: str,
                            content_id: str,
                            reason: Optional[str] = None) -> Tuple[bool, Optional[bytes]]:
        """
        Request access to encrypted content.
        May trigger DAO vote depending on content type and requester.
        """
        
        content = self.contents.get(content_id)
        if not content:
            logger.warning(f"Content not found: {content_id}")
            return False, None
        
        logger.info(f"Access request: {requester_id} → {content_id}")
        logger.info(f"  Content type: {content.content_type}")
        logger.info(f"  Reason: {reason or 'not specified'}")
        
        # Determine if DAO vote required
        requires_vote = content.content_type in ["identity", "knowledge"]
        
        if requires_vote:
            logger.info(f"  → DAO vote required (sensitive content)")
            vote_id = await self._create_dao_vote(requester_id, content_id, reason)
            
            # Wait for vote
            approved = await self._wait_for_vote(vote_id, timeout_hours=72)
            if not approved:
                logger.warning(f"DAO vote rejected for {requester_id}")
                self._log_access(requester_id, content_id, success=False, reason="DAO rejected")
                return False, None
            
            logger.info(f"✓ DAO vote approved")
        
        # Recover master key from guardian shares
        logger.info(f"  → Recovering master key from guardian shares...")
        master_key = await self._recover_master_key()
        if not master_key:
            logger.error("Failed to recover master key")
            return False, None
        
        # Retrieve encrypted content
        logger.info(f"  → Retrieving encrypted content from IPFS...")
        encrypted_blob = await self._retrieve_from_ipfs(content.content_hash)
        
        # Decrypt locally
        iv = encrypted_blob[:16]
        ciphertext = encrypted_blob[16:]
        plaintext = self._decrypt_aes(ciphertext, master_key, iv)
        
        # Log access
        self._log_access(requester_id, content_id, success=True)
        
        logger.info(f"✓ Content decrypted and returned")
        return True, plaintext
    
    async def emergency_access(self,
                              activist_id: str,
                              content_id: str) -> Tuple[bool, Optional[bytes]]:
        """
        Emergency protocol for at-risk activists.
        Fast-tracks access with 2-hour DAO vote.
        Sends all key shares via Tor + Signal + mesh.
        """
        
        logger.error(f"\n🚨 EMERGENCY: Activist {activist_id} requesting urgent access!")
        
        content = self.contents.get(content_id)
        if not content:
            return False, None
        
        # Broadcast emergency alert to all guardians
        logger.error(f"  → Broadcasting emergency to {len(self.guardians)} guardians...")
        await self._broadcast_emergency(activist_id, content_id)
        
        # Initiate emergency vote (2-hour window)
        logger.error(f"  → Creating emergency DAO vote (2-hour window)...")
        vote_id = await self._create_emergency_vote(activist_id, content_id)
        
        approved = await self._wait_for_vote(vote_id, timeout_hours=2)
        if not approved:
            logger.error(f"Emergency vote rejected")
            return False, None
        
        logger.error(f"✓ Emergency vote approved!")
        
        # Send all key shares to activist via secure channels
        logger.error(f"  → Sending key shares via Tor, Signal, and mesh...")
        key_shares = [g.key_share for g in self.guardians if g.verified]
        await self._send_secure_shares_to_activist(activist_id, key_shares)
        
        logger.error(f"✓ Key shares distributed to activist")
        logger.error(f"  Activist can reconstruct master key locally and decrypt content")
        
        self._log_access(activist_id, content_id, success=True, reason="emergency_access")
        
        return True, None  # Return None — activist decrypts locally
    
    async def rotate_guardians(self):
        """
        Rotate guardian set every 6 months.
        Re-splits master key with new guardians.
        """
        
        stale_guardians = [g for g in self.guardians if g.is_stale()]
        
        if not stale_guardians:
            logger.info("No stale guardians")
            return
        
        logger.info(f"Rotating {len(stale_guardians)} stale guardians...")
        
        # Recover master key with current guardians
        master_key = await self._recover_master_key()
        if not master_key:
            logger.error("Failed to recover master key for rotation")
            return
        
        # Select new guardians from DAO
        logger.info("Selecting new guardians...")
        new_guardians = await self._select_new_guardians()
        
        # Re-split master key using Shamir Secret Sharing
        logger.info(f"Re-splitting key with {len(new_guardians)} guardians...")
        new_shares = self._split_key_shamir(master_key, len(new_guardians), self.threshold)
        
        # Distribute shares to new guardians
        for guardian, share in zip(new_guardians, new_shares):
            guardian.key_share = share
            guardian.rotated_at = datetime.utcnow()
        
        self.guardians = new_guardians
        logger.info(f"✓ Guardian rotation complete")
    
    # ===== Key Management =====
    
    async def _recover_master_key(self) -> Optional[bytes]:
        """
        Recover master key from guardian shares using Shamir Secret Sharing.
        Requires threshold number of verified guardians.
        """
        
        verified = [g for g in self.guardians if g.verified]
        
        if len(verified) < self.threshold:
            logger.warning(f"Not enough verified guardians ({len(verified)} < {self.threshold})")
            return None
        
        logger.info(f"Recovering master key from {self.threshold} guardians...")
        
        # In production: use proper Shamir Secret Sharing (e.g., shamirsecret library)
        # For demo: simple XOR reconstruction
        shares = [g.key_share for g in verified[:self.threshold]]
        
        # Reconstruct (simplified)
        master_key = shares[0]
        for share in shares[1:]:
            master_key = bytes(a ^ b for a, b in zip(master_key, share))
        
        return master_key
    
    def _split_key_shamir(self, key: bytes, num_shares: int, threshold: int) -> List[bytes]:
        """
        Split key into shares using Shamir Secret Sharing.
        In production: use proper library like shamirsecret or sslib.
        """
        
        # Simplified: create random shares that XOR to original key
        shares = [os.urandom(len(key)) for _ in range(num_shares - 1)]
        
        # Last share is XOR of key with all other shares
        final_share = key
        for share in shares:
            final_share = bytes(a ^ b for a, b in zip(final_share, share))
        
        shares.append(final_share)
        return shares
    
    # ===== DAO Integration =====
    
    async def _create_dao_vote(self, requester_id: str, content_id: str, reason: str) -> str:
        """Create Snapshot vote for access request."""
        
        proposal = {
            "version": "0.1.0",
            "space": "x0tta6bl4.eth",
            "type": "single-choice",
            "title": f"Sublime Access: {content_id[:16]}...",
            "body": f"""
Request to access Sublime content.

Requester: {requester_id}
Content: {content_id}
Type: {self.contents[content_id].content_type}

Reason: {reason or 'Not specified'}

Vote to approve or deny access.
""",
            "choices": ["✓ Approve", "✗ Deny"],
            "start": int(datetime.utcnow().timestamp()),
            "end": int((datetime.utcnow() + timedelta(days=3)).timestamp()),
        }
        
        logger.info(f"  Creating DAO proposal...")
        
        # In production: POST to Snapshot API
        vote_id = f"sublime_vote_{datetime.utcnow().timestamp()}"
        logger.info(f"  Proposal ID: {vote_id}")
        
        return vote_id
    
    async def _create_emergency_vote(self, activist_id: str, content_id: str) -> str:
        """Create emergency DAO vote (2-hour window)."""
        
        proposal = {
            "version": "0.1.0",
            "space": "x0tta6bl4.eth",
            "type": "single-choice",
            "title": f"🚨 EMERGENCY: Sublime Access for {activist_id}",
            "body": f"""
EMERGENCY SITUATION

Activist {activist_id} may be in immediate danger.
Requests urgent access to Sublime content {content_id}.

This is a 2-hour emergency vote.
Majority approval grants access.

Vote ASAP.
""",
            "choices": ["✓ Grant Access", "✗ Deny"],
            "start": int(datetime.utcnow().timestamp()),
            "end": int((datetime.utcnow() + timedelta(hours=2)).timestamp()),
        }
        
        logger.error(f"  Creating EMERGENCY DAO vote...")
        
        vote_id = f"sublime_emergency_{datetime.utcnow().timestamp()}"
        logger.error(f"  Emergency Proposal ID: {vote_id}")
        
        return vote_id
    
    async def _wait_for_vote(self, vote_id: str, timeout_hours: int) -> bool:
        """Wait for vote to close and check result."""
        
        deadline = datetime.utcnow() + timedelta(hours=timeout_hours)
        logger.info(f"  Waiting for vote (deadline: {deadline.isoformat()})...")
        
        while datetime.utcnow() < deadline:
            # In production: Poll Snapshot API
            elapsed = (datetime.utcnow() - (deadline - timedelta(hours=timeout_hours))).total_seconds()
            
            if elapsed > 30:  # Simulate 30 second vote for demo
                # Simulate 70% approval
                approved = True
                logger.info(f"  ✓ Vote result: APPROVED (70% support)")
                return approved
            
            await asyncio.sleep(5)
        
        logger.warning(f"Vote timeout")
        return False
    
    # ===== Storage Integration =====
    
    async def _upload_to_ipfs(self, data: bytes) -> str:
        """Upload data to IPFS."""
        logger.info(f"    → Uploading {len(data)} bytes to IPFS...")
        await asyncio.sleep(0.05)
        # In production: POST to IPFS API
        ipfs_hash = "Qm" + hashlib.sha256(data).hexdigest()[:46]
        return ipfs_hash
    
    async def _upload_to_arweave(self, data: bytes, title: str) -> str:
        """Upload data to Arweave (permanent)."""
        logger.info(f"    → Uploading to Arweave...")
        await asyncio.sleep(0.05)
        # In production: POST to Arweave API
        tx_id = hashlib.sha256(data).hexdigest()[:43]
        return tx_id
    
    async def _upload_to_sia(self, data: bytes) -> str:
        """Upload to Sia (decentralized)."""
        logger.info(f"    → Uploading to Sia...")
        await asyncio.sleep(0.05)
        skylink = hashlib.sha256(data).hexdigest()[:43]
        return skylink
    
    async def _retrieve_from_ipfs(self, ipfs_hash: str) -> bytes:
        """Retrieve encrypted content from IPFS."""
        logger.info(f"    Retrieving from IPFS...")
        await asyncio.sleep(0.05)
        # Simulate content retrieval
        return b"IV_16BYTES_" + hashlib.sha256(ipfs_hash.encode()).digest()
    
    # ===== Emergency Protocol =====
    
    async def _broadcast_emergency(self, activist_id: str, content_id: str):
        """Broadcast emergency to all guardians via multiple channels."""
        
        signal = {
            "event": "sublime_emergency",
            "activist_id": activist_id,
            "content_id": content_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.error(f"  → Broadcasting via Tor...")
        await self._send_via_tor(json.dumps(signal))
        
        logger.error(f"  → Broadcasting via Signal...")
        await self._send_via_signal(signal)
        
        logger.error(f"  → Broadcasting to mesh network...")
        await self._broadcast_to_mesh(signal)
    
    async def _send_secure_shares_to_activist(self, activist_id: str, shares: List[bytes]):
        """Send key shares via secure channels."""
        
        logger.error(f"  Distributing {len(shares)} key shares to {activist_id}...")
        
        # Split shares across channels
        for i, share in enumerate(shares[:3]):
            logger.error(f"    → Share {i+1}/3 via Tor (anonymous)...")
            await self._send_via_tor_anonymous(activist_id, share)
        
        for i, share in enumerate(shares[3:6]):
            logger.error(f"    → Share {i+4}/6 via Signal (encrypted)...")
            await self._send_via_signal_encrypted(activist_id, share)
        
        for i, share in enumerate(shares[6:]):
            logger.error(f"    → Share {i+7}/10 via mesh dead drop...")
            await self._send_via_mesh_deadrop(activist_id, share)
    
    async def _send_via_tor(self, msg: str):
        await asyncio.sleep(0.01)
    
    async def _send_via_signal(self, msg: Dict):
        await asyncio.sleep(0.01)
    
    async def _broadcast_to_mesh(self, msg: Dict):
        await asyncio.sleep(0.01)
    
    async def _send_via_tor_anonymous(self, activist_id: str, share: bytes):
        await asyncio.sleep(0.01)
    
    async def _send_via_signal_encrypted(self, activist_id: str, share: bytes):
        await asyncio.sleep(0.01)
    
    async def _send_via_mesh_deadrop(self, activist_id: str, share: bytes):
        await asyncio.sleep(0.01)
    
    # ===== Audit & Logging =====
    
    def _log_access(self, requester_id: str, content_id: str, success: bool, reason: str = ""):
        """Log access attempt."""
        self.access_audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "requester_id": requester_id,
            "content_id": content_id,
            "success": success,
            "reason": reason
        })
    
    # ===== Helpers =====
    
    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())
    
    def _encrypt_aes(self, plaintext: bytes, key: bytes, iv: bytes) -> bytes:
        """Simulate AES encryption."""
        # In production: use cryptography.hazmat.primitives.ciphers
        return hashlib.sha256(plaintext + key + iv).digest() + plaintext
    
    def _decrypt_aes(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Simulate AES decryption."""
        return ciphertext[32:]  # Skip digest, return plaintext
    
    async def _select_new_guardians(self) -> List[DaoGuardian]:
        """Select new guardians from DAO."""
        await asyncio.sleep(0.01)
        
        new_guardians = []
        regions = ["USA", "EU", "Asia", "Africa", "Americas", "Oceania"]
        
        for i in range(self.max_guardians):
            guardian = DaoGuardian(
                guardian_id=f"guardian-{i}",
                public_key=f"pubkey_{i}",
                key_share=b"",
                verified=True,
                region=regions[i % len(regions)],
                rotated_at=datetime.utcnow()
            )
            new_guardians.append(guardian)
        
        return new_guardians


# ===== Demo =====

async def demo_sublime():
    """
    Demonstrate Sublime shelter with emergency access scenario.
    """
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("Sublime Oracle Demo - Digital Rights Refuge")
    print("="*70)
    
    oracle = SublimeOracle(
        ipfs_api=os.getenv("IPFS_API", ""),
        arweave_api=os.getenv("ARWEAVE_API", ""),
        snapshot_api=os.getenv("SNAPSHOT_API", "https://snapshot.org/api")
    )
    
    # Initialize with guardians
    oracle.guardians = await oracle._select_new_guardians()
    oracle.master_key = b"master_key_256_bytes_long_exactly_" + b"x" * (32 - len(b"master_key_256_bytes_long_exactly_"))
    
    print(f"✓ Sublime initialized with {len(oracle.guardians)} DAO guardians")
    
    # Add content
    print(f"\n[1] Adding content to Sublime...")
    content_id = await oracle.add_content(
        user_id="journalist-alice",
        title="Leaked Government Surveillance Program",
        description="Internal documents on mass surveillance",
        plaintext=b"SECRET GOVERNMENT DOCUMENTS HERE" * 10,
        content_type="knowledge"
    )
    print(f"✓ Content stored: {content_id}\n")
    
    # Request normal access
    print(f"[2] Researcher requests access (DAO vote)...")
    success, plaintext = await oracle.request_access(
        requester_id="researcher-bob",
        content_id=content_id,
        reason="Academic research on surveillance"
    )
    
    if success:
        print(f"✓ Access granted, content returned ({len(plaintext)} bytes)\n")
    else:
        print(f"✗ Access denied\n")
    
    # Emergency scenario
    print(f"[3] EMERGENCY: Activist in danger!")
    success, msg = await oracle.emergency_access(
        activist_id="activist-charlie",
        content_id=content_id
    )
    
    if success:
        print(f"✓ Emergency protocol activated")
        print(f"  Key shares sent via Tor, Signal, mesh\n")
    
    # Show audit log
    print(f"[4] Access Audit Log:")
    print(f"    Total access attempts: {len(oracle.access_audit_log)}")
    for entry in oracle.access_audit_log[-3:]:
        print(f"    - {entry['timestamp']}: {entry['requester_id']} → " +
              f"{'✓' if entry['success'] else '✗'} {entry['reason']}")
    
    print(f"\n{'='*70}")
    print(f"✓ Sublime Shelter: Secure refuge established")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(demo_sublime())
