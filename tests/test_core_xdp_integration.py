"""
Unit tests for CO-RE eBPF/XDP Integration Module
"""
import pytest
from pathlib import Path
from src.network.ebpf.core_xdp_integration import COREXDPProgramLoader, EBPFRingBufferReader


def test_core_xdp_program_loader_init(tmp_path):
    """Test loader initialization and local cache sync."""
    loader = COREXDPProgramLoader(cache_dir=tmp_path)
    assert loader.cache_dir == tmp_path
    assert (tmp_path / "x0tta6bl4_pulse.o").exists()


def test_core_xdp_load_and_attach(tmp_path):
    """Test loader loading and attachment behaviour."""
    loader = COREXDPProgramLoader(cache_dir=tmp_path)
    
    # Non-existent file should fail
    assert not loader.load_and_attach("eth0", Path("/tmp/nonexistent.o"))
    
    # Cache file should succeed
    stable_path = tmp_path / "x0tta6bl4_pulse.o"
    assert loader.load_and_attach("eth0", stable_path)


@pytest.mark.asyncio
async def test_apply_policy_from_ipfs_fallback(tmp_path):
    """Test IPFS download fallback to stable cache when client is missing."""
    loader = COREXDPProgramLoader(cache_dir=tmp_path)
    
    # Calling apply_policy_from_ipfs without client triggers fallback to stable cache
    success = await loader.apply_policy_from_ipfs("eth0", "QmFakeCID123")
    assert success
    assert loader.active_cids["eth0"] == "QmFakeCID123"


def test_ebpf_ring_buffer_reader():
    """Test Ring Buffer metrics polling."""
    reader = EBPFRingBufferReader()
    
    # Metrics should be empty if not running
    assert reader.poll_metrics() == {}
    
    reader.start_polling()
    metrics = reader.poll_metrics()
    assert metrics["packet_loss_percent"] == 0.2
    assert metrics["syscall_latency_p99_ms"] == 12.5
    assert metrics["ebpf_ringbuf_events_total"] == 1.0
    
    reader.stop_polling()
    assert reader.poll_metrics() == {}
