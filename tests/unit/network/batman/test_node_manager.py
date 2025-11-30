from datetime import datetime, timedelta
from src.network.batman.node_manager import NodeManager, NodeMetrics


def test_register_attest_failure():
    nm = NodeManager(mesh_id='mesh1', local_node_id='n-local')
    # Force attestation failure by passing invalid spiffe_id (None)
    nm.attestation_strategy = nm.attestation_strategy.SPIFFE
    assert nm.register_node('n1', 'aa:bb', '10.0.0.1', spiffe_id=None) is False


def test_register_and_metrics_cycle():
    nm = NodeManager(mesh_id='m', local_node_id='n-local')
    assert nm.register_node('n1', 'aa:bb', '10.0.0.1', spiffe_id='spiffe://mesh/node/n1') is True
    assert nm.update_heartbeat('n1') is True
    metrics = NodeMetrics(cpu_percent=10, memory_percent=20, network_sent_bytes=100, network_recv_bytes=200, packet_loss_percent=0.5, latency_to_gateway_ms=50, timestamp=datetime.utcnow())
    assert nm.update_metrics('n1', metrics) is True
    status = nm.get_node_status('n1')
    assert status['status'] == 'online'
    # degrade
    bad = NodeMetrics(cpu_percent=95, memory_percent=90, network_sent_bytes=100, network_recv_bytes=200, packet_loss_percent=10, latency_to_gateway_ms=800, timestamp=datetime.utcnow())
    nm.update_metrics('n1', bad)
    assert nm.get_node_status('n1')['status'] == 'degraded'


def test_deregister_node():
    nm = NodeManager(mesh_id='m', local_node_id='n-local')
    nm.register_node('n2', 'aa:cc', '10.0.0.2', spiffe_id='spiffe://mesh/node/n2')
    assert nm.deregister_node('n2') is True
    assert nm.get_node_status('n2') is None
    assert nm.deregister_node('n2') is False


def test_get_online_nodes():
    nm = NodeManager(mesh_id='m', local_node_id='n-local')
    nm.register_node('a', 'm1', '10.0.0.3', spiffe_id='spiffe://mesh/node/a')
    nm.register_node('b', 'm2', '10.0.0.4', spiffe_id='spiffe://mesh/node/b')
    # make b degraded by metrics
    bad = NodeMetrics(cpu_percent=95, memory_percent=90, network_sent_bytes=0, network_recv_bytes=0, packet_loss_percent=10, latency_to_gateway_ms=800, timestamp=datetime.utcnow())
    nm.update_metrics('b', bad)
    online = nm.get_online_nodes()
    assert 'a' in online and 'b' not in online


def test_register_with_cert_integration():
    """Test registration with optional certificate"""
    nm = NodeManager(mesh_id='m', local_node_id='n-local')
    # Passing a dummy cert should not crash the system, and since parsing fails, 
    # it should fallback to basic checks which pass if spiffe_id matches
    assert nm.register_node('n3', 'aa:dd', '10.0.0.3', 
                           spiffe_id='spiffe://mesh/node/n3',
                           cert_pem=b"-----BEGIN CERTIFICATE-----\nMOCK\n-----END CERTIFICATE-----") is True
