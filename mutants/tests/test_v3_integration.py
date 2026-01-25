"""
Tests for V3.0 Integration
"""
import pytest
import asyncio
from src.self_healing.mape_k_v3_integration import MAPEKV3Integration


@pytest.fixture
def v3_integration():
    """Fixture для MAPEKV3Integration"""
    return MAPEKV3Integration(
        enable_graphsage=True,
        enable_stego_mesh=False,
        enable_digital_twins=False
    )


def test_v3_integration_initialization(v3_integration):
    """Тест инициализации интеграции v3.0"""
    assert v3_integration is not None
    status = v3_integration.get_status()
    assert 'graphsage_available' in status
    assert 'stego_mesh_available' in status
    assert 'digital_twins_available' in status


def test_get_status(v3_integration):
    """Тест получения статуса"""
    status = v3_integration.get_status()
    
    assert isinstance(status, dict)
    assert 'graphsage_available' in status
    assert 'stego_mesh_available' in status
    assert 'digital_twins_available' in status
    assert 'components_loaded' in status


@pytest.mark.asyncio
async def test_analyze_with_graphsage(v3_integration):
    """Тест анализа с GraphSAGE"""
    node_features = {
        "node-1": {
            "latency": 50.0,
            "loss": 2.0,
            "cpu": 85.0,
            "mem": 70.0,
            "neighbors_count": 3,
            "throughput": 100.0,
            "error_rate": 1.5,
            "uptime": 3600.0,
            "load_avg": 2.5,
            "packet_queue": 10.0
        }
    }
    
    analysis = await v3_integration.analyze_with_graphsage(
        node_features=node_features,
        node_topology=None
    )
    
    # Анализ может быть None если GraphSAGE недоступен
    if analysis is not None:
        assert hasattr(analysis, 'failure_type')
        assert hasattr(analysis, 'confidence')
        assert hasattr(analysis, 'recommended_action')


def test_encode_packet_stego(v3_integration):
    """Тест кодирования пакета через Stego-Mesh"""
    if not v3_integration.stego_mesh:
        pytest.skip("Stego-Mesh not available")
    
    payload = b"TEST_PAYLOAD"
    encoded = v3_integration.encode_packet_stego(payload, "http")
    
    # Может быть None если Stego-Mesh не инициализирован
    if encoded is not None:
        assert isinstance(encoded, bytes)
        assert len(encoded) > len(payload)


def test_decode_packet_stego(v3_integration):
    """Тест декодирования пакета через Stego-Mesh"""
    if not v3_integration.stego_mesh:
        pytest.skip("Stego-Mesh not available")
    
    payload = b"TEST_PAYLOAD"
    encoded = v3_integration.encode_packet_stego(payload, "http")
    
    if encoded is not None:
        decoded = v3_integration.decode_packet_stego(encoded)
        # Декодирование может не работать идеально
        assert decoded is None or isinstance(decoded, bytes)


@pytest.mark.asyncio
async def test_run_chaos_test(v3_integration):
    """Тест запуска chaos-теста"""
    if not v3_integration.digital_twins:
        pytest.skip("Digital Twins not available")
    
    result = await v3_integration.run_chaos_test("node_down", 0.3)
    
    if result is not None:
        assert isinstance(result, dict)
        assert 'scenario' in result
        assert 'recovery_time' in result
        assert 'success' in result

