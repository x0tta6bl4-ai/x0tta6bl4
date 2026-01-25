"""
Интеграция Prometheus метрик с MAPE-K циклом

Отслеживает:
- Длительность каждой фазы (Monitor, Analyze, Plan, Execute)
- Статус циклов (успешно, ошибка, частично)
- Обнаруженные аномалии
- Выполненные действия восстановления
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime

from src.monitoring.metrics import MetricsRegistry


class MAPEKMetricsCollector:
    """Сборщик метрик для MAPE-K цикла"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
        self._cycle_start_time: Optional[float] = None
        self._phase_start_times: Dict[str, float] = {}
    
    def start_cycle(self) -> None:
        """Начало MAPE-K цикла"""
        self._cycle_start_time = time.time()
    
    def start_phase(self, phase_name: str) -> None:
        """Начало фазы MAPE-K (monitor, analyze, plan, execute)"""
        self._phase_start_times[phase_name] = time.time()
    
    def end_phase(self, phase_name: str) -> None:
        """Конец фазы с записью метрики"""
        if phase_name not in self._phase_start_times:
            return
        
        duration = time.time() - self._phase_start_times[phase_name]
        self.metrics.mapek_cycle_duration.labels(phase=phase_name).observe(duration)
        del self._phase_start_times[phase_name]
    
    def record_cycle_completion(self, status: str = "success") -> None:
        """Запись завершения цикла (success, failed, partial)"""
        self.metrics.mapek_cycles_total.labels(status=status).inc()
        
        if self._cycle_start_time:
            duration = time.time() - self._cycle_start_time
            # Общее время цикла (сумма всех фаз)
            self.metrics.mapek_cycle_duration.labels(phase="total").observe(duration)
            self._cycle_start_time = None
    
    def record_anomaly(self, anomaly_type: str, severity: str = "medium") -> None:
        """Запись обнаруженной аномалии"""
        self.metrics.mapek_anomalies_detected.labels(
            anomaly_type=anomaly_type,
            severity=severity
        ).inc()
    
    def record_recovery_action(self, action_type: str, status: str = "success") -> None:
        """Запись выполненного действия восстановления"""
        self.metrics.mapek_recovery_actions.labels(
            action_type=action_type,
            status=status
        ).inc()
    
    def update_knowledge_base_size(self, size: int) -> None:
        """Обновить размер knowledge base"""
        self.metrics.mapek_knowledge_base_size.set(size)
    
    def update_metrics_cache_size(self, size_bytes: int) -> None:
        """Обновить размер кэша метрик"""
        self.metrics.mapek_metrics_cache_size.set(size_bytes)


class MLMetricsCollector:
    """Сборщик метрик для ML компонентов"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_graphsage_inference(self, duration: float, prediction_type: str = "normal") -> None:
        """Запись GraphSAGE инференса"""
        self.metrics.graphsage_inference_duration.observe(duration)
        self.metrics.graphsage_predictions_total.labels(prediction_type=prediction_type).inc()
    
    def update_graphsage_anomaly_score(self, node_id: str, score: float) -> None:
        """Обновить score аномалии для узла"""
        self.metrics.graphsage_anomaly_score.labels(node_id=node_id).set(score)
    
    def update_graphsage_accuracy(self, accuracy: float) -> None:
        """Обновить точность модели"""
        self.metrics.graphsage_model_accuracy.set(accuracy)
    
    def record_graphsage_training(self, duration: float, loss: float) -> None:
        """Запись обучения GraphSAGE"""
        self.metrics.graphsage_training_duration.observe(duration)
        self.metrics.graphsage_training_loss.set(loss)
    
    def record_rag_retrieval(self, duration: float, query_type: str, hit: bool) -> None:
        """Запись RAG retrieval операции"""
        self.metrics.rag_retrieval_duration.observe(duration)
        self.metrics.rag_retrieval_results.labels(
            query_type=query_type,
            hit="hit" if hit else "miss"
        ).inc()
    
    def update_rag_vector_similarity(self, similarity: float) -> None:
        """Обновить среднее сходство вектора"""
        self.metrics.rag_vector_similarity.set(similarity)
    
    def update_rag_index_size(self, vector_count: int) -> None:
        """Обновить размер RAG индекса"""
        self.metrics.rag_index_size.set(vector_count)
    
    def record_rag_generation(self, duration: float) -> None:
        """Запись генерации текста RAG"""
        self.metrics.rag_generation_duration.observe(duration)


class LedgerMetricsCollector:
    """Сборщик метрик для Distributed Ledger"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_ledger_entry(self, entry_type: str = "transaction") -> None:
        """Запись новой записи в ledger"""
        self.metrics.ledger_entries_total.labels(entry_type=entry_type).inc()
    
    def update_chain_length(self, length: int) -> None:
        """Обновить длину цепи"""
        self.metrics.ledger_chain_length.set(length)
    
    def record_sync(self, duration: float) -> None:
        """Запись синхронизации"""
        self.metrics.ledger_sync_duration.observe(duration)
    
    def record_consistency_failure(self, failure_type: str = "conflict") -> None:
        """Запись сбоя консистентности"""
        self.metrics.ledger_consistency_failures.labels(failure_type=failure_type).inc()


class CRDTMetricsCollector:
    """Сборщик метрик для CRDT синхронизации"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_crdt_operation(
        self,
        operation_type: str = "merge",
        status: str = "success",
        duration: float = 0.0
    ) -> None:
        """Запись операции CRDT"""
        self.metrics.crdt_sync_operations.labels(
            operation_type=operation_type,
            status=status
        ).inc()
        if duration > 0:
            self.metrics.crdt_sync_duration.observe(duration)
    
    def update_state_size(self, size_bytes: int) -> None:
        """Обновить размер состояния"""
        self.metrics.crdt_state_size.set(size_bytes)


class RaftMetricsCollector:
    """Сборщик метрик для Raft консенсуса"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_leader_change(self) -> None:
        """Запись смены лидера"""
        self.metrics.raft_leader_changes.inc()
    
    def record_log_replication(self, duration: float) -> None:
        """Запись репликации log"""
        self.metrics.raft_log_replication_duration.observe(duration)
    
    def update_followers_count(self, count: int) -> None:
        """Обновить количество followers"""
        self.metrics.raft_followers_count.set(count)
    
    def update_term(self, term: int) -> None:
        """Обновить текущий term"""
        self.metrics.raft_term_gauge.set(term)


class MeshMetricsCollector:
    """Сборщик метрик для mesh сети"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def update_active_nodes(self, count: int) -> None:
        """Обновить количество активных узлов"""
        self.metrics.mesh_nodes_active.set(count)
    
    def record_connection(self, connection_type: str = "direct") -> None:
        """Запись нового соединения"""
        self.metrics.mesh_connections_total.labels(connection_type=connection_type).inc()
    
    def update_packet_loss(self, loss_ratio: float) -> None:
        """Обновить коэффициент потери пакетов"""
        self.metrics.mesh_packet_loss_ratio.set(loss_ratio)
    
    def record_hop_count(self, hop_count: int) -> None:
        """Запись количества хопов в пути"""
        self.metrics.mesh_hop_count.observe(hop_count)
    
    def record_bandwidth(self, bytes_transferred: int, direction: str = "outbound") -> None:
        """Запись передачи данных"""
        self.metrics.mesh_bandwidth_bytes.labels(direction=direction).inc(bytes_transferred)
    
    def record_latency(self, latency_seconds: float) -> None:
        """Запись латентности"""
        self.metrics.mesh_latency.observe(latency_seconds)


class SecurityMetricsCollector:
    """Сборщик метрик для безопасности"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_threat_alert(self, threat_type: str, severity: str = "medium") -> None:
        """Запись alert о угрозе"""
        self.metrics.threat_alerts_total.labels(
            threat_type=threat_type,
            severity=severity
        ).inc()
    
    def update_suspect_nodes(self, count: int) -> None:
        """Обновить количество подозреваемых узлов"""
        self.metrics.suspect_nodes_count.set(count)
    
    def record_byzantine_detection(self, behavior_type: str = "unknown") -> None:
        """Запись обнаружения Byzantine поведения"""
        self.metrics.byzantine_detections.labels(behavior_type=behavior_type).inc()


class FederatedLearningMetricsCollector:
    """Сборщик метрик для Federated Learning"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_fl_round(self, duration: float, loss: float) -> None:
        """Запись раунда FL"""
        self.metrics.fl_round_duration.observe(duration)
        self.metrics.fl_global_model_loss.set(loss)
    
    def record_local_update(self, node_id: str) -> None:
        """Запись локального обновления"""
        self.metrics.fl_local_updates.labels(node_id=node_id).inc()
    
    def record_fl_communication(self, bytes_transferred: int, direction: str) -> None:
        """Запись коммуникации"""
        self.metrics.fl_communication_bytes.labels(direction=direction).inc(bytes_transferred)
    
    def update_participant_count(self, count: int) -> None:
        """Обновить количество участников"""
        self.metrics.fl_participant_count.set(count)


class DAOMetricsCollector:
    """Сборщик метрик для DAO Governance"""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
    
    def record_proposal(self, status: str = "active") -> None:
        """Запись предложения"""
        self.metrics.dao_proposals_total.labels(status=status).inc()
    
    def update_voting_power(self, power: float) -> None:
        """Обновить voting power"""
        self.metrics.dao_voting_power.set(power)
    
    def update_treasury_balance(self, balance: float) -> None:
        """Обновить баланс казны"""
        self.metrics.dao_treasury_balance.set(balance)
    
    def update_participation(self, ratio: float) -> None:
        """Обновить коэффициент участия"""
        self.metrics.dao_vote_participation.set(ratio)


def get_metrics_collectors() -> Dict[str, Any]:
    """Получить все сборщики метрик"""
    metrics = MetricsRegistry()
    
    return {
        "mapek": MAPEKMetricsCollector(metrics),
        "ml": MLMetricsCollector(metrics),
        "ledger": LedgerMetricsCollector(metrics),
        "crdt": CRDTMetricsCollector(metrics),
        "raft": RaftMetricsCollector(metrics),
        "mesh": MeshMetricsCollector(metrics),
        "security": SecurityMetricsCollector(metrics),
        "fl": FederatedLearningMetricsCollector(metrics),
        "dao": DAOMetricsCollector(metrics),
    }
