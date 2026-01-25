"""
x0tta6bl4 Minimal App with Byzantine Protection
Enhanced version with Signed Gossip and Quorum Validation.
"""
from __future__ import annotations

import asyncio
import logging
import time
import json
import random
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

# Try to import Byzantine protection
try:
    from src.network.byzantine.mesh_byzantine_protection import MeshByzantineProtection
    from src.network.byzantine.signed_gossip import MessageType
    BYZANTINE_AVAILABLE = True
except ImportError as e:
    BYZANTINE_AVAILABLE = False
    logger.warning(f"⚠️ Byzantine protection not available: {e}")

app = FastAPI(title="x0tta6bl4-minimal-byzantine", version="3.0.0", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0
HEALTH_CHECK_INTERVAL = 5.0
TOTAL_NODES = 10  # Total nodes in network (for quorum calculation)

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: Set[str] = set()
validated_failures: Set[str] = set()  # Nodes validated as failed by quorum

# Byzantine Protection
byzantine_protection: Optional[MeshByzantineProtection] = None

if BYZANTINE_AVAILABLE:
    try:
        byzantine_protection = MeshByzantineProtection(node_id, total_nodes=TOTAL_NODES)
        logger.info("✅ Byzantine protection enabled")
    except Exception as e:
        logger.error(f"🔴 Failed to initialize Byzantine protection: {e}")
        BYZANTINE_AVAILABLE = False
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result

# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []
    signature: Optional[str] = None  # Hex-encoded signature
    public_key: Optional[str] = None  # Hex-encoded public key

class RouteRequest(BaseModel):
    destination: str
    payload: str

class NodeFailureReport(BaseModel):
    failed_node: str
    evidence: Dict[str, Any]
    signature: str  # Signature of the report

# --- Background Tasks ---

async def x_health_check_loop__mutmut_orig():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_1():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while False:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_2():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = None
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_3():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = None
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_4():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(None):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_5():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection or byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_6():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(None):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_7():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(None)
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_8():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    break
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_9():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = None
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_10():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get(None, 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_11():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", None)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_12():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get(0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_13():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", )
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_14():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("XXlast_seenXX", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_15():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("LAST_SEEN", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_16():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 1)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_17():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = None
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_18():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time + last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_19():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed >= PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_20():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers or peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_21():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_22():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_23():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(None)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_24():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(None)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_25():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(None)
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_26():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = None
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_27():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "XXlatencyXX": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_28():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "LATENCY": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_29():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float(None),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_30():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('XXinfXX'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_31():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('INF'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_32():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "XXpacket_lossXX": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_33():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "PACKET_LOSS": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_34():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 2.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_35():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "XXlast_seenXX": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_36():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "LAST_SEEN": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_37():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "XXelapsedXX": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_38():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "ELAPSED": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_39():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = None
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_40():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(None, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_41():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, None)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_42():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_43():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, )
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_44():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                None
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_45():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id not in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_46():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(None)
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_47():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(None)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_48():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(None, exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_49():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=None)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_50():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_51():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", )
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_52():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=False)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_53():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(peer_id):
                    logger.warning(f"⚠️ Peer {peer_id} is quarantined - skipping health check")
                    continue
                
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
                        
                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float('inf'),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed
                            }
                            event = byzantine_protection.report_node_failure(peer_id, evidence)
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(None)

x_health_check_loop__mutmut_mutants : ClassVar[MutantDict] = {
'x_health_check_loop__mutmut_1': x_health_check_loop__mutmut_1, 
    'x_health_check_loop__mutmut_2': x_health_check_loop__mutmut_2, 
    'x_health_check_loop__mutmut_3': x_health_check_loop__mutmut_3, 
    'x_health_check_loop__mutmut_4': x_health_check_loop__mutmut_4, 
    'x_health_check_loop__mutmut_5': x_health_check_loop__mutmut_5, 
    'x_health_check_loop__mutmut_6': x_health_check_loop__mutmut_6, 
    'x_health_check_loop__mutmut_7': x_health_check_loop__mutmut_7, 
    'x_health_check_loop__mutmut_8': x_health_check_loop__mutmut_8, 
    'x_health_check_loop__mutmut_9': x_health_check_loop__mutmut_9, 
    'x_health_check_loop__mutmut_10': x_health_check_loop__mutmut_10, 
    'x_health_check_loop__mutmut_11': x_health_check_loop__mutmut_11, 
    'x_health_check_loop__mutmut_12': x_health_check_loop__mutmut_12, 
    'x_health_check_loop__mutmut_13': x_health_check_loop__mutmut_13, 
    'x_health_check_loop__mutmut_14': x_health_check_loop__mutmut_14, 
    'x_health_check_loop__mutmut_15': x_health_check_loop__mutmut_15, 
    'x_health_check_loop__mutmut_16': x_health_check_loop__mutmut_16, 
    'x_health_check_loop__mutmut_17': x_health_check_loop__mutmut_17, 
    'x_health_check_loop__mutmut_18': x_health_check_loop__mutmut_18, 
    'x_health_check_loop__mutmut_19': x_health_check_loop__mutmut_19, 
    'x_health_check_loop__mutmut_20': x_health_check_loop__mutmut_20, 
    'x_health_check_loop__mutmut_21': x_health_check_loop__mutmut_21, 
    'x_health_check_loop__mutmut_22': x_health_check_loop__mutmut_22, 
    'x_health_check_loop__mutmut_23': x_health_check_loop__mutmut_23, 
    'x_health_check_loop__mutmut_24': x_health_check_loop__mutmut_24, 
    'x_health_check_loop__mutmut_25': x_health_check_loop__mutmut_25, 
    'x_health_check_loop__mutmut_26': x_health_check_loop__mutmut_26, 
    'x_health_check_loop__mutmut_27': x_health_check_loop__mutmut_27, 
    'x_health_check_loop__mutmut_28': x_health_check_loop__mutmut_28, 
    'x_health_check_loop__mutmut_29': x_health_check_loop__mutmut_29, 
    'x_health_check_loop__mutmut_30': x_health_check_loop__mutmut_30, 
    'x_health_check_loop__mutmut_31': x_health_check_loop__mutmut_31, 
    'x_health_check_loop__mutmut_32': x_health_check_loop__mutmut_32, 
    'x_health_check_loop__mutmut_33': x_health_check_loop__mutmut_33, 
    'x_health_check_loop__mutmut_34': x_health_check_loop__mutmut_34, 
    'x_health_check_loop__mutmut_35': x_health_check_loop__mutmut_35, 
    'x_health_check_loop__mutmut_36': x_health_check_loop__mutmut_36, 
    'x_health_check_loop__mutmut_37': x_health_check_loop__mutmut_37, 
    'x_health_check_loop__mutmut_38': x_health_check_loop__mutmut_38, 
    'x_health_check_loop__mutmut_39': x_health_check_loop__mutmut_39, 
    'x_health_check_loop__mutmut_40': x_health_check_loop__mutmut_40, 
    'x_health_check_loop__mutmut_41': x_health_check_loop__mutmut_41, 
    'x_health_check_loop__mutmut_42': x_health_check_loop__mutmut_42, 
    'x_health_check_loop__mutmut_43': x_health_check_loop__mutmut_43, 
    'x_health_check_loop__mutmut_44': x_health_check_loop__mutmut_44, 
    'x_health_check_loop__mutmut_45': x_health_check_loop__mutmut_45, 
    'x_health_check_loop__mutmut_46': x_health_check_loop__mutmut_46, 
    'x_health_check_loop__mutmut_47': x_health_check_loop__mutmut_47, 
    'x_health_check_loop__mutmut_48': x_health_check_loop__mutmut_48, 
    'x_health_check_loop__mutmut_49': x_health_check_loop__mutmut_49, 
    'x_health_check_loop__mutmut_50': x_health_check_loop__mutmut_50, 
    'x_health_check_loop__mutmut_51': x_health_check_loop__mutmut_51, 
    'x_health_check_loop__mutmut_52': x_health_check_loop__mutmut_52, 
    'x_health_check_loop__mutmut_53': x_health_check_loop__mutmut_53
}

def health_check_loop(*args, **kwargs):
    result = _mutmut_trampoline(x_health_check_loop__mutmut_orig, x_health_check_loop__mutmut_mutants, args, kwargs)
    return result 

health_check_loop.__signature__ = _mutmut_signature(x_health_check_loop__mutmut_orig)
x_health_check_loop__mutmut_orig.__name__ = 'x_health_check_loop'

# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "node_id": node_id,
        "byzantine_protection": BYZANTINE_AVAILABLE,
        "peers_count": len(peers),
        "validated_failures": list(validated_failures)
    }

@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon with Byzantine protection.
    
    Все beacon'ы должны быть подписаны PQC подписями.
    """
    global peers, dead_peers
    
    # Check Byzantine protection
    if byzantine_protection:
        # Check if sender is quarantined
        if byzantine_protection.is_node_quarantined(req.node_id):
            logger.warning(f"⚠️ Beacon from quarantined node {req.node_id} - rejecting")
            raise HTTPException(
                status_code=403,
                detail=f"Node {req.node_id} is quarantined"
            )
        
        # Check if we should accept message from this node
        if not byzantine_protection.should_accept_message(req.node_id):
            logger.warning(f"⚠️ Beacon from low-reputation node {req.node_id} - rejecting")
            raise HTTPException(
                status_code=403,
                detail=f"Node {req.node_id} has low reputation"
            )
        
        # Verify signature if provided
        if req.signature and req.public_key:
            try:
                from src.network.byzantine.signed_gossip import SignedMessage
                
                # Create SignedMessage from request
                message = SignedMessage(
                    msg_type=MessageType.BEACON,
                    sender=req.node_id,
                    timestamp=req.timestamp,
                    nonce=int(time.time() * 1000000),  # Approximate
                    epoch=0,  # Default epoch
                    payload={"neighbors": req.neighbors or []},
                    signature=bytes.fromhex(req.signature),
                    public_key=bytes.fromhex(req.public_key)
                )
                
                # Verify message
                is_valid, error = byzantine_protection.verify_beacon(message)
                if not is_valid:
                    logger.warning(f"❌ Invalid beacon signature from {req.node_id}: {error}")
                    raise HTTPException(
                        status_code=403,
                        detail=f"Invalid beacon signature: {error}"
                    )
                
                logger.debug(f"✅ Verified beacon signature from {req.node_id}")
            except Exception as e:
                logger.error(f"Failed to verify beacon signature: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Beacon signature verification failed: {e}"
                )
    
    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED")
    
    # Register/update peer
    peers[req.node_id] = {
        "last_seen": time.time(),
        "neighbors": req.neighbors or []
    }
    
    beacons_received.append({
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time(),
        "byzantine_protected": BYZANTINE_AVAILABLE
    })
    
    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "byzantine_protected": BYZANTINE_AVAILABLE
    }

@app.post("/mesh/report-failure")
async def report_node_failure(report: NodeFailureReport):
    """
    Report node failure (requires quorum validation).
    
    Критические события (node failure) требуют кворумной валидации.
    """
    if not byzantine_protection:
        raise HTTPException(
            status_code=503,
            detail="Byzantine protection not available"
        )
    
    # Report failure
    event = byzantine_protection.report_node_failure(
        report.failed_node,
        report.evidence
    )
    
    # Validate with our signature
    signature = bytes.fromhex(report.signature)
    is_validated = byzantine_protection.validate_node_failure(event, signature)
    
    if is_validated:
        validated_failures.add(report.failed_node)
        logger.warning(f"🔴 Node {report.failed_node} validated as FAILED by quorum")
    
    return {
        "event_id": f"{event.event_type.value}:{event.target}:{int(event.timestamp)}",
        "quorum_reached": is_validated,
        "signatures_count": len(event.signatures),
        "quorum_needed": byzantine_protection.quorum_validator.quorum_size
    }

@app.get("/mesh/byzantine/stats")
async def get_byzantine_stats():
    """Get Byzantine protection statistics."""
    if not byzantine_protection:
        raise HTTPException(
            status_code=503,
            detail="Byzantine protection not available"
        )
    
    return byzantine_protection.get_protection_stats()

@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with Byzantine status."""
    current_time = time.time()
    peer_status = {}
    
    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT
        
        reputation = None
        is_quarantined = False
        if byzantine_protection:
            reputation = byzantine_protection.get_node_reputation(peer_id)
            is_quarantined = byzantine_protection.is_node_quarantined(peer_id)
        
        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", []),
            "reputation": reputation,
            "is_quarantined": is_quarantined,
            "is_validated_failure": peer_id in validated_failures
        }
    
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers),
        "validated_failures": list(validated_failures),
        "byzantine_protection": BYZANTINE_AVAILABLE
    }

@app.get("/mesh/status")
async def get_status():
    """Get mesh status with Byzantine protection info."""
    stats = {}
    if byzantine_protection:
        stats = byzantine_protection.get_protection_stats()
    
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "validated_failures_count": len(validated_failures),
        "beacons_received": len(beacons_received),
        "byzantine_protection": {
            "enabled": BYZANTINE_AVAILABLE,
            "stats": stats
        }
    }

@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """Route a message to destination (excluding validated failures)."""
    if req.destination == node_id:
        return {
            "status": "delivered",
            "hops": 0,
            "latency_ms": 0
        }
    
    # Don't route to validated failures
    if req.destination in validated_failures:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is validated as FAILED by quorum"
        }
    
    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead"
        }
    
    if req.destination in peers:
        latency = random.uniform(10, 50)
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": latency,
            "path": [node_id, req.destination]
        }
    
    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}"
    }

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with Byzantine stats."""
    import os
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_bytes = mem_info.rss
    except:
        memory_bytes = 0
    
    current_time = time.time()
    alive_peers = sum(
        1 for p in peers.values()
        if (current_time - p.get("last_seen", 0)) < PEER_TIMEOUT
    )
    
    metrics_str = f"""# HELP mesh_peers_count Number of known peers
# TYPE mesh_peers_count gauge
mesh_peers_count {len(peers)}

# HELP mesh_dead_peers_count Number of dead peers
# TYPE mesh_dead_peers_count gauge
mesh_dead_peers_count {len(dead_peers)}

# HELP mesh_validated_failures_count Number of validated failures
# TYPE mesh_validated_failures_count gauge
mesh_validated_failures_count {len(validated_failures)}

# HELP mesh_byzantine_protection_enabled Byzantine protection enabled (1=yes, 0=no)
# TYPE mesh_byzantine_protection_enabled gauge
mesh_byzantine_protection_enabled {1 if BYZANTINE_AVAILABLE else 0}

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str

@app.on_event("startup")
async def startup():
    """Start background tasks."""
    global node_id
    import os
    
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with Byzantine protection started as {node_id}")
    
    if BYZANTINE_AVAILABLE:
        logger.info("🛡️ Byzantine protection enabled (Signed Gossip + Quorum Validation)")
    else:
        logger.warning("⚠️ Byzantine protection disabled")
    
    # Start background tasks
    asyncio.create_task(health_check_loop())
    logger.info("✅ Background tasks started: health_check")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

