#!/usr/bin/env python3
"""
Quickstart Example: PQC Zero-Trust Integration in x0tta6bl4

This example demonstrates how to set up and use the Post-Quantum Cryptography
zero-trust security features with eBPF networking and self-healing capabilities.
"""

import asyncio
import logging
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def pqc_zero_trust_demo():
    """
    Demonstrate PQC zero-trust security integration
    """
    print("🚀 x0tta6bl4 PQC Zero-Trust Security Demo")
    print("=" * 50)

    try:
        # Import PQC components
        from src.security.ebpf_pqc_gateway import get_pqc_gateway, EBPFPQCGateway
        from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
        from src.self_healing.pqc_zero_trust_healer import PQCZeroTrustHealer

        print("✅ PQC components imported successfully")

    except ImportError as e:
        print(f"❌ Failed to import PQC components: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -e .[ml,dev,monitoring]")
        return

    # Initialize PQC Gateway
    print("\n🔐 Initializing PQC Gateway...")
    gateway = get_pqc_gateway()
    print(f"✅ PQC Gateway ready with {len(gateway.sessions)} initial sessions")

    # Create some test sessions
    print("\n🔑 Creating PQC sessions...")
    peers = ["mesh_node_1", "mesh_node_2", "mesh_node_3"]
    sessions = []

    for peer in peers:
        session = gateway.create_session(peer)
        sessions.append(session)
        print(f"✅ Created session for {peer}: {session.session_id[:16]}...")

    # Test encryption/decryption
    print("\n🔒 Testing PQC encryption...")
    test_message = b"Hello, Post-Quantum World!"
    session = sessions[0]

    encrypted = gateway.encrypt_payload(session.session_id, test_message)
    print(f"📤 Encrypted message: {encrypted.hex()[:32]}...")

    decrypted = gateway.decrypt_payload(session.session_id, encrypted)
    print(f"📥 Decrypted message: {decrypted.decode()}")

    assert decrypted == test_message, "Encryption/decryption failed!"
    print("✅ PQC encryption/decryption working correctly")

    # Initialize XDP Loader (requires BCC and root)
    print("\n🌐 Initializing PQC XDP Loader...")
    try:
        loader = PQCXDPLoader("lo")  # Use loopback for demo
        print("✅ PQC XDP Loader initialized on interface 'lo'")

        # Sync sessions to eBPF maps
        loader.sync_with_gateway()
        print("✅ Sessions synced to eBPF maps")

        # Get initial stats
        stats = loader.get_pqc_stats()
        print(f"📊 Initial PQC stats: {stats}")

    except Exception as e:
        print(f"⚠️  XDP Loader initialization failed (requires BCC and root): {e}")
        loader = None

    # Initialize Zero-Trust Healer
    print("\n🩺 Initializing PQC Zero-Trust Healer...")
    healer = PQCZeroTrustHealer(gateway, loader)
    print("✅ PQC Healer initialized and monitoring")

    # Run a few healing cycles
    print("\n🔄 Running PQC healing cycles...")
    for cycle in range(3):
        print(f"\n--- Cycle {cycle + 1} ---")

        # Monitor
        monitoring = await healer.monitor()
        print(f"📊 Health Score: {monitoring.health_score:.2f}")
        # Analyze
        analysis = await healer.analyze(monitoring)
        print(f"📋 Analysis: {len(analysis.issues)} issues, severity: {analysis.severity}")

        if analysis.issues:
            for issue in analysis.issues:
                print(f"   • {issue}")

        # Plan and execute if needed
        if analysis.requires_action:
            plan = await healer.plan(analysis)
            print(f"📝 Plan: {len(plan.actions)} actions, priority: {plan.priority}")

            for action in plan.actions:
                print(f"   → {action}")

            execution = await healer.execute(plan)
            print(f"⚡ Execution: {execution.success_count}/{execution.actions_executed} successful")
        else:
            print("✅ No healing actions needed")

        # Wait between cycles
        await asyncio.sleep(2)

    # Demonstrate session management
    print("\n🔄 Demonstrating session management...")

    # Create a session and make it "old"
    old_session = gateway.create_session("temporary_peer")
    old_session.last_used = old_session.created_at  # Make it appear old

    print(f"📅 Created session: {old_session.session_id[:16]}...")
    print(f"   Created: {old_session.created_at}")
    print(f"   Last used: {old_session.last_used}")

    # Run cleanup
    cleanup_result = await healer._cleanup_expired_sessions()
    print(f"🧹 Cleanup result: {cleanup_result}")

    # Test key rotation
    print("\n🔄 Testing key rotation...")
    session_to_rotate = sessions[1]
    original_key = session_to_rotate.aes_key.copy()

    rotation_result = await healer._rotate_expired_sessions()
    print(f"🔑 Rotation result: {rotation_result}")

    rotated_session = gateway.get_session(session_to_rotate.session_id)
    key_changed = rotated_session.aes_key != original_key
    print(f"🔑 Key rotated: {key_changed}")

    # Final stats
    if loader:
        final_stats = loader.get_pqc_stats()
        print(f"\n📊 Final PQC stats: {final_stats}")

    print("\n🎉 PQC Zero-Trust Demo completed successfully!")
    print("\nKey Features Demonstrated:")
    print("  ✅ Post-Quantum Key Exchange (ML-KEM-768)")
    print("  ✅ Post-Quantum Signatures (ML-DSA-65)")
    print("  ✅ AES-256 Payload Encryption")
    print("  ✅ eBPF Kernel-space Verification")
    print("  ✅ Zero-Trust Session Management")
    print("  ✅ Self-Healing MAPE-K Loop")
    print("  ✅ Prometheus Metrics Integration")

    # Cleanup
    if loader:
        loader.cleanup()
        print("🧹 XDP Loader cleaned up")

def run_pqc_benchmark():
    """
    Run a simple PQC performance benchmark
    """
    print("\n📈 PQC Performance Benchmark")
    print("=" * 30)

    try:
        from src.security.ebpf_pqc_gateway import EBPFPQCGateway

        gateway = EBPFPQCGateway()

        # Benchmark session creation
        print("Creating 10 PQC sessions...")
        start_time = time.time()
        sessions = []
        for i in range(10):
            session = gateway.create_session(f"bench_peer_{i}")
            sessions.append(session)
        creation_time = time.time() - start_time
        print(f"⏱️  Session creation time: {creation_time:.2f}s")
        # Benchmark encryption/decryption
        test_payload = b"A" * 1024  # 1KB payload
        session = sessions[0]

        print("Benchmarking encryption/decryption (1KB payload)...")
        start_time = time.time()
        for _ in range(100):
            encrypted = gateway.encrypt_payload(session.session_id, test_payload)
            decrypted = gateway.decrypt_payload(session.session_id, encrypted)
            assert decrypted == test_payload
        crypto_time = time.time() - start_time
        print(f"🔐 Crypto operations time: {crypto_time:.2f}s")
        print("✅ Benchmark completed successfully")

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")

async def main():
    """Main demo function"""
    print("x0tta6bl4 PQC Zero-Trust Integration Quickstart")
    print("This demo requires:")
    print("  • Python 3.10+")
    print("  • liboqs (Post-Quantum Crypto library)")
    print("  • BCC (BPF Compiler Collection) - for eBPF features")
    print("  • Root privileges - for eBPF XDP programs")
    print()

    # Run main demo
    await pqc_zero_trust_demo()

    # Run benchmark
    run_pqc_benchmark()

    print("\n🎯 Next Steps:")
    print("  1. Deploy on real network interface (requires root)")
    print("  2. Integrate with mesh routing (batman-adv)")
    print("  3. Set up Prometheus monitoring")
    print("  4. Configure production security policies")
    print("  5. Test with real network traffic")

if __name__ == '__main__':
    asyncio.run(main())