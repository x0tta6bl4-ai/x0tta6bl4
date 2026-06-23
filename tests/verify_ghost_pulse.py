import asyncio
import base64
import os
import sys
import logging

import pytest

# Ensure src is in path
sys.path.append(os.getcwd())

from src.network.transport.ghost_pulse_transport import GhostPulseTransport


@pytest.mark.asyncio
async def test_ghost_pulse_logic():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test-ghost-pulse")

    # Setup
    key = os.urandom(32)
    transport = GhostPulseTransport(key, mode="corporate", pulse_seed=123)

    # Test data
    original = b"Mesh heartbeat 2026-06-06"

    # Wrap/Unwrap
    wrapped = transport.wrap_packet(original)
    logger.info(f"Wrapped packet size: {len(wrapped)}")

    unwrapped = transport.unwrap_packet(wrapped)
    assert unwrapped == original, "Payload mismatch"
    logger.info("✅ Encryption/SRTP mimicry cycle OK")

    # Test Pulse Timing
    logger.info("Testing Pulse timing (5 packets)...")
    start = asyncio.get_event_loop().time()
    for i in range(5):
        t0 = asyncio.get_event_loop().time()
        await transport.wait_for_pulse()
        t1 = asyncio.get_event_loop().time()
        logger.info(f"Packet {i} delay: {t1 - t0:.4f}s")

    total_time = asyncio.get_event_loop().time() - start
    logger.info(f"Total time for 5 pulses: {total_time:.4f}s")
    assert total_time > 0, "Timing should be non-zero"

    logger.info("✅ Ghost Pulse Transport verification: PASS")

if __name__ == "__main__":
    asyncio.run(test_ghost_pulse_logic())
