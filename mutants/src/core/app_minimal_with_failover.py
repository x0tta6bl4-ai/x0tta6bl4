"""
x0tta6bl4 Minimal App with Automatic Failover
Enhanced version with peer health monitoring and route recalculation.
"""
from __future__ import annotations

import asyncio
import logging
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

app = FastAPI(title="x0tta6bl4-minimal-failover", version="3.0.0", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0  # Seconds without beacon = dead peer
HEALTH_CHECK_INTERVAL = 5.0  # Check peer health every 5 seconds
ROUTE_RECALC_INTERVAL = 10.0  # Recalculate routes every 10 seconds

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: set = set()  # Track dead peers for route recalculation

# Background tasks
_health_check_task: Optional[asyncio.Task] = None
_route_recalc_task: Optional[asyncio.Task] = None
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

class RouteRequest(BaseModel):
    destination: str
    payload: str

# --- Background Tasks ---

async def x_health_check_loop__mutmut_orig():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_1():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while False:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_2():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = None
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_3():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = None
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_4():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(None):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_5():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = None
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_6():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get(None, 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_7():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", None)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_8():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get(0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_9():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", )
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_10():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("XXlast_seenXX", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_11():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("LAST_SEEN", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_12():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 1)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_13():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = None
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_14():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time + last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_15():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed >= PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_16():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_17():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(None)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_18():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(None)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_19():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(None)
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_20():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id not in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_21():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(None)
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_22():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(None)
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_23():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(None)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_24():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(None, exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_25():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=None)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_26():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_27():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", )
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_28():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=False)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_29():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.
    
    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)")
            
            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")
            
            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)")
                await recalculate_routes()
            
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
    'x_health_check_loop__mutmut_29': x_health_check_loop__mutmut_29
}

def health_check_loop(*args, **kwargs):
    result = _mutmut_trampoline(x_health_check_loop__mutmut_orig, x_health_check_loop__mutmut_mutants, args, kwargs)
    return result 

health_check_loop.__signature__ = _mutmut_signature(x_health_check_loop__mutmut_orig)
x_health_check_loop__mutmut_orig.__name__ = 'x_health_check_loop'

async def x_recalculate_routes__mutmut_orig():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_1():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info(None)
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_2():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("XX🧮 Recalculating routes...XX")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_3():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_4():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 RECALCULATING ROUTES...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_5():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = None
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_6():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(None, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_7():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, None)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_8():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_9():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, )
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_10():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = None
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_11():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(None)
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_12():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(None)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_13():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {'XX -> XX'.join(path)}")
    
    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")

async def x_recalculate_routes__mutmut_14():
    """
    MAPE-K Plan: Recalculate routes after topology changes.
    
    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes
    
    logger.info("🧮 Recalculating routes...")
    
    # Clear route cache
    routes.clear()
    
    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")
    
    logger.info(None)

x_recalculate_routes__mutmut_mutants : ClassVar[MutantDict] = {
'x_recalculate_routes__mutmut_1': x_recalculate_routes__mutmut_1, 
    'x_recalculate_routes__mutmut_2': x_recalculate_routes__mutmut_2, 
    'x_recalculate_routes__mutmut_3': x_recalculate_routes__mutmut_3, 
    'x_recalculate_routes__mutmut_4': x_recalculate_routes__mutmut_4, 
    'x_recalculate_routes__mutmut_5': x_recalculate_routes__mutmut_5, 
    'x_recalculate_routes__mutmut_6': x_recalculate_routes__mutmut_6, 
    'x_recalculate_routes__mutmut_7': x_recalculate_routes__mutmut_7, 
    'x_recalculate_routes__mutmut_8': x_recalculate_routes__mutmut_8, 
    'x_recalculate_routes__mutmut_9': x_recalculate_routes__mutmut_9, 
    'x_recalculate_routes__mutmut_10': x_recalculate_routes__mutmut_10, 
    'x_recalculate_routes__mutmut_11': x_recalculate_routes__mutmut_11, 
    'x_recalculate_routes__mutmut_12': x_recalculate_routes__mutmut_12, 
    'x_recalculate_routes__mutmut_13': x_recalculate_routes__mutmut_13, 
    'x_recalculate_routes__mutmut_14': x_recalculate_routes__mutmut_14
}

def recalculate_routes(*args, **kwargs):
    result = _mutmut_trampoline(x_recalculate_routes__mutmut_orig, x_recalculate_routes__mutmut_mutants, args, kwargs)
    return result 

recalculate_routes.__signature__ = _mutmut_signature(x_recalculate_routes__mutmut_orig)
x_recalculate_routes__mutmut_orig.__name__ = 'x_recalculate_routes'

def x_compute_shortest_path__mutmut_orig(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_1(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source != destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_2(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = None
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_3(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(None)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_4(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id not in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_5(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            break
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_6(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = None
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_7(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get(None, [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_8(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", None)
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_9(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get([])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_10(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", )
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_11(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("XXneighborsXX", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_12(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("NEIGHBORS", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_13(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers or neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_14(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_15(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor == source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_16(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(None)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_17(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source not in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_18(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get(None, []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_19(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", None):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_20(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get([]):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_21(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", ):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_22(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("XXneighborsXX", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_23(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("NEIGHBORS", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_24(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_25(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(None)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_26(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = None
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_27(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 1}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_28(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = None
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_29(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = None
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_30(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) & {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_31(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(None) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_32(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = None
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_33(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(None, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_34(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=None)
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_35(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_36(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, )
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_37(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: None)
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_38(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(None, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_39(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, None))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_40(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_41(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, ))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_42(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float(None)))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_43(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('XXinfXX')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_44(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('INF')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_45(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current != destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_46(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = None
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_47(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = None
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_48(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_49(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(None)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_50(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = None
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_51(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(None)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_52(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(None)
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_53(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(None))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_54(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(None)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_55(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = None
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_56(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(None, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_57(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, None)
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_58(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_59(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, )
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_60(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float(None))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_61(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('XXinfXX'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_62(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('INF'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_63(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(None, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_64(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, None):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_65(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get([]):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_66(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, ):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_67(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor not in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_68(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = None  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_69(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist - 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_70(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 2  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_71(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt <= distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_72(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(None, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_73(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, None):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_74(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_75(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, ):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_76(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float(None)):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_77(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('XXinfXX')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_78(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('INF')):
                    distances[neighbor] = alt
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_79(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = None
                    previous[neighbor] = current
    
    # No path found
    return None

def x_compute_shortest_path__mutmut_80(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.
    
    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]
    
    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue
        
        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)
    
    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)
    
    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}
    
    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float('inf')))
        
        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))
        
        unvisited.remove(current)
        current_dist = distances.get(current, float('inf'))
        
        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float('inf')):
                    distances[neighbor] = alt
                    previous[neighbor] = None
    
    # No path found
    return None

x_compute_shortest_path__mutmut_mutants : ClassVar[MutantDict] = {
'x_compute_shortest_path__mutmut_1': x_compute_shortest_path__mutmut_1, 
    'x_compute_shortest_path__mutmut_2': x_compute_shortest_path__mutmut_2, 
    'x_compute_shortest_path__mutmut_3': x_compute_shortest_path__mutmut_3, 
    'x_compute_shortest_path__mutmut_4': x_compute_shortest_path__mutmut_4, 
    'x_compute_shortest_path__mutmut_5': x_compute_shortest_path__mutmut_5, 
    'x_compute_shortest_path__mutmut_6': x_compute_shortest_path__mutmut_6, 
    'x_compute_shortest_path__mutmut_7': x_compute_shortest_path__mutmut_7, 
    'x_compute_shortest_path__mutmut_8': x_compute_shortest_path__mutmut_8, 
    'x_compute_shortest_path__mutmut_9': x_compute_shortest_path__mutmut_9, 
    'x_compute_shortest_path__mutmut_10': x_compute_shortest_path__mutmut_10, 
    'x_compute_shortest_path__mutmut_11': x_compute_shortest_path__mutmut_11, 
    'x_compute_shortest_path__mutmut_12': x_compute_shortest_path__mutmut_12, 
    'x_compute_shortest_path__mutmut_13': x_compute_shortest_path__mutmut_13, 
    'x_compute_shortest_path__mutmut_14': x_compute_shortest_path__mutmut_14, 
    'x_compute_shortest_path__mutmut_15': x_compute_shortest_path__mutmut_15, 
    'x_compute_shortest_path__mutmut_16': x_compute_shortest_path__mutmut_16, 
    'x_compute_shortest_path__mutmut_17': x_compute_shortest_path__mutmut_17, 
    'x_compute_shortest_path__mutmut_18': x_compute_shortest_path__mutmut_18, 
    'x_compute_shortest_path__mutmut_19': x_compute_shortest_path__mutmut_19, 
    'x_compute_shortest_path__mutmut_20': x_compute_shortest_path__mutmut_20, 
    'x_compute_shortest_path__mutmut_21': x_compute_shortest_path__mutmut_21, 
    'x_compute_shortest_path__mutmut_22': x_compute_shortest_path__mutmut_22, 
    'x_compute_shortest_path__mutmut_23': x_compute_shortest_path__mutmut_23, 
    'x_compute_shortest_path__mutmut_24': x_compute_shortest_path__mutmut_24, 
    'x_compute_shortest_path__mutmut_25': x_compute_shortest_path__mutmut_25, 
    'x_compute_shortest_path__mutmut_26': x_compute_shortest_path__mutmut_26, 
    'x_compute_shortest_path__mutmut_27': x_compute_shortest_path__mutmut_27, 
    'x_compute_shortest_path__mutmut_28': x_compute_shortest_path__mutmut_28, 
    'x_compute_shortest_path__mutmut_29': x_compute_shortest_path__mutmut_29, 
    'x_compute_shortest_path__mutmut_30': x_compute_shortest_path__mutmut_30, 
    'x_compute_shortest_path__mutmut_31': x_compute_shortest_path__mutmut_31, 
    'x_compute_shortest_path__mutmut_32': x_compute_shortest_path__mutmut_32, 
    'x_compute_shortest_path__mutmut_33': x_compute_shortest_path__mutmut_33, 
    'x_compute_shortest_path__mutmut_34': x_compute_shortest_path__mutmut_34, 
    'x_compute_shortest_path__mutmut_35': x_compute_shortest_path__mutmut_35, 
    'x_compute_shortest_path__mutmut_36': x_compute_shortest_path__mutmut_36, 
    'x_compute_shortest_path__mutmut_37': x_compute_shortest_path__mutmut_37, 
    'x_compute_shortest_path__mutmut_38': x_compute_shortest_path__mutmut_38, 
    'x_compute_shortest_path__mutmut_39': x_compute_shortest_path__mutmut_39, 
    'x_compute_shortest_path__mutmut_40': x_compute_shortest_path__mutmut_40, 
    'x_compute_shortest_path__mutmut_41': x_compute_shortest_path__mutmut_41, 
    'x_compute_shortest_path__mutmut_42': x_compute_shortest_path__mutmut_42, 
    'x_compute_shortest_path__mutmut_43': x_compute_shortest_path__mutmut_43, 
    'x_compute_shortest_path__mutmut_44': x_compute_shortest_path__mutmut_44, 
    'x_compute_shortest_path__mutmut_45': x_compute_shortest_path__mutmut_45, 
    'x_compute_shortest_path__mutmut_46': x_compute_shortest_path__mutmut_46, 
    'x_compute_shortest_path__mutmut_47': x_compute_shortest_path__mutmut_47, 
    'x_compute_shortest_path__mutmut_48': x_compute_shortest_path__mutmut_48, 
    'x_compute_shortest_path__mutmut_49': x_compute_shortest_path__mutmut_49, 
    'x_compute_shortest_path__mutmut_50': x_compute_shortest_path__mutmut_50, 
    'x_compute_shortest_path__mutmut_51': x_compute_shortest_path__mutmut_51, 
    'x_compute_shortest_path__mutmut_52': x_compute_shortest_path__mutmut_52, 
    'x_compute_shortest_path__mutmut_53': x_compute_shortest_path__mutmut_53, 
    'x_compute_shortest_path__mutmut_54': x_compute_shortest_path__mutmut_54, 
    'x_compute_shortest_path__mutmut_55': x_compute_shortest_path__mutmut_55, 
    'x_compute_shortest_path__mutmut_56': x_compute_shortest_path__mutmut_56, 
    'x_compute_shortest_path__mutmut_57': x_compute_shortest_path__mutmut_57, 
    'x_compute_shortest_path__mutmut_58': x_compute_shortest_path__mutmut_58, 
    'x_compute_shortest_path__mutmut_59': x_compute_shortest_path__mutmut_59, 
    'x_compute_shortest_path__mutmut_60': x_compute_shortest_path__mutmut_60, 
    'x_compute_shortest_path__mutmut_61': x_compute_shortest_path__mutmut_61, 
    'x_compute_shortest_path__mutmut_62': x_compute_shortest_path__mutmut_62, 
    'x_compute_shortest_path__mutmut_63': x_compute_shortest_path__mutmut_63, 
    'x_compute_shortest_path__mutmut_64': x_compute_shortest_path__mutmut_64, 
    'x_compute_shortest_path__mutmut_65': x_compute_shortest_path__mutmut_65, 
    'x_compute_shortest_path__mutmut_66': x_compute_shortest_path__mutmut_66, 
    'x_compute_shortest_path__mutmut_67': x_compute_shortest_path__mutmut_67, 
    'x_compute_shortest_path__mutmut_68': x_compute_shortest_path__mutmut_68, 
    'x_compute_shortest_path__mutmut_69': x_compute_shortest_path__mutmut_69, 
    'x_compute_shortest_path__mutmut_70': x_compute_shortest_path__mutmut_70, 
    'x_compute_shortest_path__mutmut_71': x_compute_shortest_path__mutmut_71, 
    'x_compute_shortest_path__mutmut_72': x_compute_shortest_path__mutmut_72, 
    'x_compute_shortest_path__mutmut_73': x_compute_shortest_path__mutmut_73, 
    'x_compute_shortest_path__mutmut_74': x_compute_shortest_path__mutmut_74, 
    'x_compute_shortest_path__mutmut_75': x_compute_shortest_path__mutmut_75, 
    'x_compute_shortest_path__mutmut_76': x_compute_shortest_path__mutmut_76, 
    'x_compute_shortest_path__mutmut_77': x_compute_shortest_path__mutmut_77, 
    'x_compute_shortest_path__mutmut_78': x_compute_shortest_path__mutmut_78, 
    'x_compute_shortest_path__mutmut_79': x_compute_shortest_path__mutmut_79, 
    'x_compute_shortest_path__mutmut_80': x_compute_shortest_path__mutmut_80
}

def compute_shortest_path(*args, **kwargs):
    result = _mutmut_trampoline(x_compute_shortest_path__mutmut_orig, x_compute_shortest_path__mutmut_mutants, args, kwargs)
    return result 

compute_shortest_path.__signature__ = _mutmut_signature(x_compute_shortest_path__mutmut_orig)
x_compute_shortest_path__mutmut_orig.__name__ = 'x_compute_shortest_path'

async def x_periodic_route_recalc__mutmut_orig():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=True)

async def x_periodic_route_recalc__mutmut_1():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while False:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=True)

async def x_periodic_route_recalc__mutmut_2():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(None)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=True)

async def x_periodic_route_recalc__mutmut_3():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(None, exc_info=True)

async def x_periodic_route_recalc__mutmut_4():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=None)

async def x_periodic_route_recalc__mutmut_5():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(exc_info=True)

async def x_periodic_route_recalc__mutmut_6():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", )

async def x_periodic_route_recalc__mutmut_7():
    """
    Periodic route recalculation (even without failures).
    
    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=False)

x_periodic_route_recalc__mutmut_mutants : ClassVar[MutantDict] = {
'x_periodic_route_recalc__mutmut_1': x_periodic_route_recalc__mutmut_1, 
    'x_periodic_route_recalc__mutmut_2': x_periodic_route_recalc__mutmut_2, 
    'x_periodic_route_recalc__mutmut_3': x_periodic_route_recalc__mutmut_3, 
    'x_periodic_route_recalc__mutmut_4': x_periodic_route_recalc__mutmut_4, 
    'x_periodic_route_recalc__mutmut_5': x_periodic_route_recalc__mutmut_5, 
    'x_periodic_route_recalc__mutmut_6': x_periodic_route_recalc__mutmut_6, 
    'x_periodic_route_recalc__mutmut_7': x_periodic_route_recalc__mutmut_7
}

def periodic_route_recalc(*args, **kwargs):
    result = _mutmut_trampoline(x_periodic_route_recalc__mutmut_orig, x_periodic_route_recalc__mutmut_mutants, args, kwargs)
    return result 

periodic_route_recalc.__signature__ = _mutmut_signature(x_periodic_route_recalc__mutmut_orig)
x_periodic_route_recalc__mutmut_orig.__name__ = 'x_periodic_route_recalc'

# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "node_id": node_id,
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "routes_count": len(routes)
    }

@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon from another node.
    
    MAPE-K Monitor: Updates peer health status.
    """
    global peers, dead_peers
    
    beacon = {
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time()
    }
    beacons_received.append(beacon)
    
    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED from dead state")
        # Trigger route recalculation
        await recalculate_routes()
    
    # Register/update peer
    peers[req.node_id] = {
        "last_seen": time.time(),
        "neighbors": req.neighbors or []
    }
    
    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "was_dead": req.node_id in dead_peers
    }

@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with health status."""
    current_time = time.time()
    peer_status = {}
    
    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT
        
        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", [])
        }
    
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers)
    }

@app.get("/mesh/status")
async def get_status():
    """Get mesh status with failover metrics."""
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "beacons_received": len(beacons_received),
        "routes_count": len(routes),
        "uptime": time.time(),
        "failover_enabled": True
    }

@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """
    Route a message to destination with automatic failover.
    
    MAPE-K Execute: Uses updated routes after failures.
    """
    if req.destination == node_id:
        return {
            "status": "delivered",
            "hops": 0,
            "latency_ms": 0
        }
    
    # Check if destination is dead
    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead",
            "dead_peers": list(dead_peers)
        }
    
    # Use cached route if available
    if req.destination in routes:
        path = routes[req.destination]
        latency = random.uniform(10, 50) * len(path)
        return {
            "status": "delivered",
            "hops": len(path) - 1,
            "latency_ms": latency,
            "path": path
        }
    
    # Compute route on-the-fly
    path = compute_shortest_path(node_id, req.destination)
    if path:
        routes[req.destination] = path  # Cache it
        latency = random.uniform(10, 50) * len(path)
        return {
            "status": "delivered",
            "hops": len(path) - 1,
            "latency_ms": latency,
            "path": path
        }
    
    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}",
        "dead_peers": list(dead_peers)
    }

@app.get("/mesh/route/{destination}")
async def get_route(destination: str):
    """Get route to destination (with failover support)."""
    if destination in dead_peers:
        raise HTTPException(
            status_code=503,
            detail=f"Destination {destination} is dead"
        )
    
    if destination == node_id:
        return {"path": [node_id], "hops": 0}
    
    # Use cached route
    if destination in routes:
        return {
            "path": routes[destination],
            "hops": len(routes[destination]) - 1
        }
    
    # Compute route
    path = compute_shortest_path(node_id, destination)
    if path:
        routes[destination] = path
        return {
            "path": path,
            "hops": len(path) - 1
        }
    
    raise HTTPException(status_code=404, detail=f"No route to {destination}")

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with failover stats."""
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

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP mesh_routes_count Number of cached routes
# TYPE mesh_routes_count gauge
mesh_routes_count {len(routes)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str

@app.on_event("startup")
async def startup():
    """Start background tasks."""
    global _health_check_task, _route_recalc_task, node_id
    import os
    
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with failover started as {node_id}")
    
    # Start background tasks
    _health_check_task = asyncio.create_task(health_check_loop())
    _route_recalc_task = asyncio.create_task(periodic_route_recalc())
    
    logger.info("✅ Background tasks started: health_check, route_recalc")

@app.on_event("shutdown")
async def shutdown():
    """Stop background tasks."""
    global _health_check_task, _route_recalc_task
    
    if _health_check_task:
        _health_check_task.cancel()
    if _route_recalc_task:
        _route_recalc_task.cancel()
    
    logger.info("🛑 Background tasks stopped")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

