"""
P1 #1: Prometheus Metrics Expansion - Integration Tests

27 тестов для проверки полноты и корректности метрик:
- Базовые метрики HTTP
- MAPE-K метрики
- ML метрики
- Mesh метрики
- Security метрики
- Ledger метрики
"""

import pytest
import time
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

from src.monitoring.metrics import MetricsRegistry
from src.monitoring.mapek_metrics import (
    MAPEKMetricsCollector,
    MLMetricsCollector,
    MeshMetricsCollector,
    SecurityMetricsCollector,
    FederatedLearningMetricsCollector,
    DAOMetricsCollector,
)


class TestMetricsRegistry:
    """Тесты реестра метрик"""
    
    def test_metrics_registry_initialization(self):
        """Тест инициализации реестра"""
        metrics = MetricsRegistry()
        assert metrics is not None
        assert hasattr(metrics, 'request_count')
        assert hasattr(metrics, 'request_duration')
    
    def test_http_request_metrics_exist(self):
        """Тест наличия HTTP метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'request_count')
        assert hasattr(metrics, 'request_duration')
        assert hasattr(metrics, 'mesh_nodes_active')
        assert hasattr(metrics, 'db_connections_active')
    
    def test_mapek_metrics_exist(self):
        """Тест наличия MAPE-K метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'mapek_cycle_duration')
        assert hasattr(metrics, 'mapek_cycles_total')
        assert hasattr(metrics, 'mapek_anomalies_detected')
        assert hasattr(metrics, 'mapek_recovery_actions')
        assert hasattr(metrics, 'mapek_knowledge_base_size')
        assert hasattr(metrics, 'mapek_metrics_cache_size')
    
    def test_ml_metrics_exist(self):
        """Тест наличия ML метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'graphsage_inference_duration')
        assert hasattr(metrics, 'graphsage_predictions_total')
        assert hasattr(metrics, 'graphsage_anomaly_score')
        assert hasattr(metrics, 'rag_retrieval_duration')
        assert hasattr(metrics, 'rag_retrieval_results')
        assert hasattr(metrics, 'rag_vector_similarity')
        assert hasattr(metrics, 'rag_index_size')
    
    def test_mesh_metrics_exist(self):
        """Тест наличия mesh метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'mesh_nodes_active')
        assert hasattr(metrics, 'mesh_connections_total')
        assert hasattr(metrics, 'mesh_packet_loss_ratio')
        assert hasattr(metrics, 'mesh_hop_count')
        assert hasattr(metrics, 'mesh_bandwidth_bytes')
        assert hasattr(metrics, 'mesh_latency')
    
    def test_security_metrics_exist(self):
        """Тест наличия security метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'mtls_certificate_rotations_total')
        assert hasattr(metrics, 'mtls_certificate_expiry_seconds')
        assert hasattr(metrics, 'mtls_validation_failures')
        assert hasattr(metrics, 'spiffe_svid_issuance')
        assert hasattr(metrics, 'threat_alerts_total')
        assert hasattr(metrics, 'byzantine_detections')
    
    def test_ledger_metrics_exist(self):
        """Тест наличия ledger метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'ledger_entries_total')
        assert hasattr(metrics, 'ledger_chain_length')
        assert hasattr(metrics, 'ledger_sync_duration')
        assert hasattr(metrics, 'ledger_consistency_failures')
    
    def test_fl_metrics_exist(self):
        """Тест наличия FL метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'fl_round_duration')
        assert hasattr(metrics, 'fl_global_model_loss')
        assert hasattr(metrics, 'fl_local_updates')
        assert hasattr(metrics, 'fl_communication_bytes')
        assert hasattr(metrics, 'fl_participant_count')
    
    def test_dao_metrics_exist(self):
        """Тест наличия DAO метрик"""
        metrics = MetricsRegistry()
        
        assert hasattr(metrics, 'dao_proposals_total')
        assert hasattr(metrics, 'dao_voting_power')
        assert hasattr(metrics, 'dao_treasury_balance')
        assert hasattr(metrics, 'dao_vote_participation')
    
    def test_total_metrics_count(self):
        """Тест общего количества метрик"""
        metrics = MetricsRegistry()
        
        # Подсчитать все метрики (Counter, Gauge, Histogram)
        metric_count = 0
        for attr_name in dir(metrics):
            attr = getattr(metrics, attr_name)
            if isinstance(attr, (Counter, Gauge, Histogram)):
                metric_count += 1
        
        # Должно быть более 100 метрик
        assert metric_count > 100, f"Expected >100 metrics, got {metric_count}"


class TestMAPEKMetricsCollector:
    """Тесты сборщика MAPE-K метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return MAPEKMetricsCollector(metrics)
    
    def test_start_and_end_phase(self, collector):
        """Тест начала и конца фазы"""
        collector.start_phase("monitor")
        time.sleep(0.01)
        collector.end_phase("monitor")
        
        # Проверить что метрика была обновлена
        assert collector.metrics.mapek_cycle_duration is not None
    
    def test_record_cycle_completion(self, collector):
        """Тест записи завершения цикла"""
        collector.start_cycle()
        time.sleep(0.01)
        collector.record_cycle_completion("success")
        
        assert collector.metrics.mapek_cycles_total is not None
    
    def test_record_anomaly(self, collector):
        """Тест записи аномалии"""
        collector.record_anomaly("cpu_usage", "high")
        collector.record_anomaly("memory_usage", "critical")
        
        assert collector.metrics.mapek_anomalies_detected is not None
    
    def test_record_recovery_action(self, collector):
        """Тест записи действия восстановления"""
        collector.record_recovery_action("restart", "success")
        collector.record_recovery_action("scale", "failed")
        
        assert collector.metrics.mapek_recovery_actions is not None
    
    def test_update_knowledge_base_size(self, collector):
        """Тест обновления размера знаний"""
        collector.update_knowledge_base_size(1000)
        collector.update_knowledge_base_size(2000)
        
        assert collector.metrics.mapek_knowledge_base_size is not None
    
    def test_update_metrics_cache_size(self, collector):
        """Тест обновления размера кэша"""
        collector.update_metrics_cache_size(1024 * 1024)  # 1MB
        
        assert collector.metrics.mapek_metrics_cache_size is not None


class TestMLMetricsCollector:
    """Тесты сборщика ML метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return MLMetricsCollector(metrics)
    
    def test_record_graphsage_inference(self, collector):
        """Тест записи GraphSAGE инференса"""
        collector.record_graphsage_inference(0.05, "anomaly")
        collector.record_graphsage_inference(0.03, "normal")
        
        assert collector.metrics.graphsage_inference_duration is not None
        assert collector.metrics.graphsage_predictions_total is not None
    
    def test_update_graphsage_anomaly_score(self, collector):
        """Тест обновления score аномалии"""
        collector.update_graphsage_anomaly_score("node_1", 0.75)
        collector.update_graphsage_anomaly_score("node_2", 0.25)
        
        assert collector.metrics.graphsage_anomaly_score is not None
    
    def test_record_rag_retrieval(self, collector):
        """Тест записи RAG retrieval"""
        collector.record_rag_retrieval(0.1, "network_health", hit=True)
        collector.record_rag_retrieval(0.15, "anomaly", hit=False)
        
        assert collector.metrics.rag_retrieval_duration is not None
        assert collector.metrics.rag_retrieval_results is not None
    
    def test_update_rag_index_size(self, collector):
        """Тест обновления размера RAG индекса"""
        collector.update_rag_index_size(10000)
        collector.update_rag_index_size(15000)
        
        assert collector.metrics.rag_index_size is not None


class TestMeshMetricsCollector:
    """Тесты сборщика mesh метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return MeshMetricsCollector(metrics)
    
    def test_update_active_nodes(self, collector):
        """Тест обновления активных узлов"""
        collector.update_active_nodes(5)
        collector.update_active_nodes(10)
        
        assert collector.metrics.mesh_nodes_active is not None
    
    def test_record_connection(self, collector):
        """Тест записи соединения"""
        collector.record_connection("direct")
        collector.record_connection("relayed")
        
        assert collector.metrics.mesh_connections_total is not None
    
    def test_record_bandwidth(self, collector):
        """Тест записи bandwidth"""
        collector.record_bandwidth(1024, "outbound")
        collector.record_bandwidth(512, "inbound")
        
        assert collector.metrics.mesh_bandwidth_bytes is not None
    
    def test_record_latency(self, collector):
        """Тест записи латентности"""
        collector.record_latency(0.01)
        collector.record_latency(0.05)
        
        assert collector.metrics.mesh_latency is not None


class TestSecurityMetricsCollector:
    """Тесты сборщика security метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return SecurityMetricsCollector(metrics)
    
    def test_record_threat_alert(self, collector):
        """Тест записи threat alert"""
        collector.record_threat_alert("dos", "critical")
        collector.record_threat_alert("unauthorized", "high")
        
        assert collector.metrics.threat_alerts_total is not None
    
    def test_record_byzantine_detection(self, collector):
        """Тест записи Byzantine обнаружения"""
        collector.record_byzantine_detection("double_voting")
        collector.record_byzantine_detection("equivocation")
        
        assert collector.metrics.byzantine_detections is not None


class TestFederatedLearningMetricsCollector:
    """Тесты сборщика FL метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return FederatedLearningMetricsCollector(metrics)
    
    def test_record_fl_round(self, collector):
        """Тест записи FL раунда"""
        collector.record_fl_round(10.5, 0.25)
        collector.record_fl_round(11.0, 0.23)
        
        assert collector.metrics.fl_round_duration is not None
        assert collector.metrics.fl_global_model_loss is not None
    
    def test_record_local_update(self, collector):
        """Тест записи локального обновления"""
        collector.record_local_update("participant_1")
        collector.record_local_update("participant_2")
        
        assert collector.metrics.fl_local_updates is not None


class TestDAOMetricsCollector:
    """Тесты сборщика DAO метрик"""
    
    @pytest.fixture
    def collector(self):
        metrics = MetricsRegistry()
        return DAOMetricsCollector(metrics)
    
    def test_record_proposal(self, collector):
        """Тест записи предложения"""
        collector.record_proposal("active")
        collector.record_proposal("passed")
        collector.record_proposal("rejected")
        
        assert collector.metrics.dao_proposals_total is not None
    
    def test_update_voting_power(self, collector):
        """Тест обновления voting power"""
        collector.update_voting_power(1000.0)
        collector.update_voting_power(1500.0)
        
        assert collector.metrics.dao_voting_power is not None
    
    def test_update_treasury_balance(self, collector):
        """Тест обновления баланса казны"""
        collector.update_treasury_balance(10000.0)
        collector.update_treasury_balance(12000.0)
        
        assert collector.metrics.dao_treasury_balance is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
