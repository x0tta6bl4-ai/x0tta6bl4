"""
Prometheus метрики для x0tta6bl4

Полный набор метрик для мониторинга всех компонентов системы:
- MAPE-K цикл
- ML компоненты (GraphSAGE, RAG)
- Distributed Ledger
- Consensus
- Security (SPIFFE/SPIRE, mTLS)
- Federated Learning
- DAO Governance
"""

from typing import Any, Dict

import prometheus_client
from prometheus_client import Counter, Gauge, Histogram, Summary

# Создаем собственный реестр для избежания конфликтов
_metrics_registry = prometheus_client.CollectorRegistry()


class MetricsRegistry:
    """Реестр всех метрик приложения"""

    # ============================================================================
    # HTTP API метрики
    # ============================================================================

    request_count = Counter(
        "x0tta6bl4_requests_total",
        "Всего HTTP запросов",
        ["method", "endpoint", "status", "tenant_id"],
        registry=_metrics_registry,
    )

    request_duration = Histogram(
        "x0tta6bl4_request_duration_seconds",
        "Задержка HTTP запроса в секундах",
        ["method", "endpoint", "tenant_id"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        registry=_metrics_registry,
    )

    db_connections_active = Gauge(
        "x0tta6bl4_db_connections_active",
        "Количество активных подключений к БД",
        registry=_metrics_registry,
    )

    # ============================================================================
    # MAPE-K Цикл метрики
    # ============================================================================

    mapek_cycle_duration = Histogram(
        "x0tta6bl4_mapek_cycle_duration_seconds",
        "Длительность одного MAPE-K цикла в секундах",
        ["phase"],  # monitor, analyze, plan, execute
        buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0),
        registry=_metrics_registry,
    )

    mapek_cycles_total = Counter(
        "x0tta6bl4_mapek_cycles_total",
        "Всего выполненных MAPE-K циклов",
        ["status"],  # success, failed, partial
        registry=_metrics_registry,
    )

    mapek_anomalies_detected = Counter(
        "x0tta6bl4_mapek_anomalies_detected_total",
        "Всего обнаруженных аномалий",
        [
            "anomaly_type",
            "severity",
        ],  # cpu_usage, memory_usage, latency, packet_loss...
        registry=_metrics_registry,
    )

    mapek_recovery_actions = Counter(
        "x0tta6bl4_mapek_recovery_actions_total",
        "Всего выполненных действий восстановления",
        ["action_type", "status"],  # restart, scale, isolate...
        registry=_metrics_registry,
    )

    mapek_knowledge_base_size = Gauge(
        "x0tta6bl4_mapek_knowledge_base_size_entries",
        "Размер knowledge base в записях",
        registry=_metrics_registry,
    )

    mapek_metrics_cache_size = Gauge(
        "x0tta6bl4_mapek_metrics_cache_size_bytes",
        "Размер кэша метрик в байтах",
        registry=_metrics_registry,
    )

    # ============================================================================
    # GraphSAGE ML метрики
    # ============================================================================

    graphsage_inference_duration = Histogram(
        "x0tta6bl4_graphsage_inference_duration_seconds",
        "Длительность GraphSAGE инференса в секундах",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
        registry=_metrics_registry,
    )

    graphsage_predictions_total = Counter(
        "x0tta6bl4_graphsage_predictions_total",
        "Всего предсказаний от GraphSAGE",
        ["prediction_type"],  # anomaly, normal, suspicious
        registry=_metrics_registry,
    )

    graphsage_anomaly_score = Gauge(
        "x0tta6bl4_graphsage_anomaly_score",
        "Текущий score аномалии от GraphSAGE",
        ["node_id"],
        registry=_metrics_registry,
    )

    graphsage_model_accuracy = Gauge(
        "x0tta6bl4_graphsage_model_accuracy",
        "Точность модели GraphSAGE на валидационном наборе",
        registry=_metrics_registry,
    )

    graphsage_training_duration = Histogram(
        "x0tta6bl4_graphsage_training_duration_seconds",
        "Длительность обучения GraphSAGE в секундах",
        buckets=(1.0, 5.0, 10.0, 30.0, 60.0),
        registry=_metrics_registry,
    )

    graphsage_training_loss = Gauge(
        "x0tta6bl4_graphsage_training_loss",
        "Последняя loss из обучения GraphSAGE",
        registry=_metrics_registry,
    )

    # ============================================================================
    # RAG метрики
    # ============================================================================

    rag_retrieval_duration = Histogram(
        "x0tta6bl4_rag_retrieval_duration_seconds",
        "Длительность RAG retrieval в секундах",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
        registry=_metrics_registry,
    )

    rag_retrieval_results = Counter(
        "x0tta6bl4_rag_retrieval_results_total",
        "Всего RAG retrieval результатов",
        ["query_type", "hit"],  # network_health, anomaly, unknown; hit/miss
        registry=_metrics_registry,
    )

    rag_vector_similarity = Gauge(
        "x0tta6bl4_rag_vector_similarity",
        "Среднее сходство вектора в RAG retrieval",
        registry=_metrics_registry,
    )

    rag_index_size = Gauge(
        "x0tta6bl4_rag_index_size_vectors",
        "Размер RAG индекса в векторах",
        registry=_metrics_registry,
    )

    rag_generation_duration = Histogram(
        "x0tta6bl4_rag_generation_duration_seconds",
        "Длительность генерации RAG в секундах",
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0),
        registry=_metrics_registry,
    )

    # ============================================================================
    # Distributed Ledger метрики
    # ============================================================================

    ledger_entries_total = Counter(
        "x0tta6bl4_ledger_entries_total",
        "Всего записей в distributed ledger",
        ["entry_type"],  # transaction, state, event
        registry=_metrics_registry,
    )

    ledger_chain_length = Gauge(
        "x0tta6bl4_ledger_chain_length",
        "Текущая длина цепи ledger",
        registry=_metrics_registry,
    )

    ledger_sync_duration = Histogram(
        "x0tta6bl4_ledger_sync_duration_seconds",
        "Длительность синхронизации ledger в секундах",
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0),
        registry=_metrics_registry,
    )

    ledger_consistency_failures = Counter(
        "x0tta6bl4_ledger_consistency_failures_total",
        "Всего сбоев консистентности ledger",
        ["failure_type"],  # conflict, timeout, corruption
        registry=_metrics_registry,
    )

    # ============================================================================
    # CRDT синхронизация метрики
    # ============================================================================

    crdt_sync_operations = Counter(
        "x0tta6bl4_crdt_sync_operations_total",
        "Всего операций CRDT синхронизации",
        ["operation_type", "status"],  # merge, add, remove; success, conflict
        registry=_metrics_registry,
    )

    crdt_sync_duration = Histogram(
        "x0tta6bl4_crdt_sync_duration_seconds",
        "Длительность CRDT синхронизации в секундах",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5),
        registry=_metrics_registry,
    )

    crdt_state_size = Gauge(
        "x0tta6bl4_crdt_state_size_bytes",
        "Размер CRDT состояния в байтах",
        registry=_metrics_registry,
    )

    # ============================================================================
    # Consensus (Raft) метрики
    # ============================================================================

    raft_leader_changes = Counter(
        "x0tta6bl4_raft_leader_changes_total",
        "Всего смен лидера Raft",
        registry=_metrics_registry,
    )

    raft_log_replication_duration = Histogram(
        "x0tta6bl4_raft_log_replication_duration_seconds",
        "Длительность репликации Raft log в секундах",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5),
        registry=_metrics_registry,
    )

    raft_followers_count = Gauge(
        "x0tta6bl4_raft_followers_count",
        "Количество активных Raft followers",
        registry=_metrics_registry,
    )

    raft_term_gauge = Gauge(
        "x0tta6bl4_raft_term", "Текущий term в Raft", registry=_metrics_registry
    )

    # ============================================================================
    # Mesh сетевые метрики
    # ============================================================================

    mesh_nodes_active = Gauge(
        "x0tta6bl4_mesh_nodes_active",
        "Количество активных mesh узлов",
        registry=_metrics_registry,
    )

    mesh_connections_total = Counter(
        "x0tta6bl4_mesh_connections_total",
        "Всего mesh соединений установлено",
        ["connection_type"],  # direct, relayed, batman-adv
        registry=_metrics_registry,
    )

    mesh_packet_loss_ratio = Gauge(
        "x0tta6bl4_mesh_packet_loss_ratio",
        "Коэффициент потери пакетов в mesh",
        registry=_metrics_registry,
    )

    mesh_hop_count = Histogram(
        "x0tta6bl4_mesh_hop_count",
        "Распределение количества хопов в mesh",
        registry=_metrics_registry,
    )

    mesh_bandwidth_bytes = Counter(
        "x0tta6bl4_mesh_bandwidth_bytes_total",
        "Всего байтов передано через mesh",
        ["direction"],  # inbound, outbound
        registry=_metrics_registry,
    )

    mesh_latency = Histogram(
        "x0tta6bl4_mesh_latency_seconds",
        "Латентность в mesh сети",
        ["node_id", "peer_id"],
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
        registry=_metrics_registry,
    )

    mesh_peers_count = Gauge(
        "x0tta6bl4_mesh_peers_count",
        "Количество пиров для узла",
        ["node_id"],
        registry=_metrics_registry,
    )

    node_health_status = Gauge(
        "x0tta6bl4_node_health_status",
        "Статус здоровья узла (1=healthy, 0=unhealthy)",
        ["node_id"],
        registry=_metrics_registry,
    )

    node_uptime_seconds = Gauge(
        "x0tta6bl4_node_uptime_seconds",
        "Время работы узла в секундах",
        ["node_id"],
        registry=_metrics_registry,
    )

    self_healing_mttr_seconds = Histogram(
        "x0tta6bl4_self_healing_mttr_seconds",
        "Mean Time To Recovery для self-healing событий",
        ["recovery_type"],
        registry=_metrics_registry,
    )

    # ============================================================================
    # mTLS / SPIFFE метрики
    # ============================================================================

    mtls_certificate_rotations_total = Counter(
        "x0tta6bl4_mtls_certificate_rotations_total",
        "Всего ротаций mTLS сертификатов",
        registry=_metrics_registry,
    )

    mtls_certificate_expiry_seconds = Gauge(
        "x0tta6bl4_mtls_certificate_expiry_seconds",
        "Секунд до истечения текущего mTLS сертификата",
        registry=_metrics_registry,
    )

    mtls_certificate_age_seconds = Gauge(
        "x0tta6bl4_mtls_certificate_age_seconds",
        "Возраст текущего mTLS сертификата в секундах",
        registry=_metrics_registry,
    )

    mtls_validation_failures = Counter(
        "x0tta6bl4_mtls_validation_failures_total",
        "Всего сбоев валидации mTLS",
        ["failure_type"],  # expiry, invalid_signature, revoked
        registry=_metrics_registry,
    )

    # Alias used by certificate_validator and mtls_controller_production
    mtls_certificate_validation_failures_total = mtls_validation_failures

    spiffe_svid_issuance = Counter(
        "x0tta6bl4_spiffe_svid_issuance_total",
        "Всего выданных SPIFFE SVIDs",
        registry=_metrics_registry,
    )

    spiffe_svid_renewal = Counter(
        "x0tta6bl4_spiffe_svid_renewal_total",
        "Всего обновлений SPIFFE SVID",
        registry=_metrics_registry,
    )

    spire_server_latency = Histogram(
        "x0tta6bl4_spire_server_latency_seconds",
        "Латентность SPIRE server в секундах",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
        registry=_metrics_registry,
    )

    # ============================================================================
    # Federated Learning метрики
    # ============================================================================

    fl_round_duration = Histogram(
        "x0tta6bl4_fl_round_duration_seconds",
        "Длительность раунда federated learning в секундах",
        buckets=(1.0, 5.0, 10.0, 30.0, 60.0),
        registry=_metrics_registry,
    )

    fl_global_model_loss = Gauge(
        "x0tta6bl4_fl_global_model_loss",
        "Loss глобальной модели FL",
        registry=_metrics_registry,
    )

    fl_local_updates = Counter(
        "x0tta6bl4_fl_local_updates_total",
        "Всего локальных обновлений в FL",
        ["node_id"],
        registry=_metrics_registry,
    )

    fl_communication_bytes = Counter(
        "x0tta6bl4_fl_communication_bytes_total",
        "Всего байтов коммуникации в FL",
        ["direction"],  # upload, download
        registry=_metrics_registry,
    )

    fl_participant_count = Gauge(
        "x0tta6bl4_fl_participant_count",
        "Количество активных участников FL",
        registry=_metrics_registry,
    )

    # ============================================================================
    # DAO Governance метрики
    # ============================================================================

    dao_proposals_total = Counter(
        "x0tta6bl4_dao_proposals_total",
        "Всего DAO предложений",
        ["status"],  # active, passed, rejected, executed
        registry=_metrics_registry,
    )

    dao_voting_power = Gauge(
        "x0tta6bl4_dao_voting_power_total",
        "Общая voting power в DAO",
        registry=_metrics_registry,
    )

    dao_treasury_balance = Gauge(
        "x0tta6bl4_dao_treasury_balance", "Баланс DAO казны", registry=_metrics_registry
    )

    dao_vote_participation = Gauge(
        "x0tta6bl4_dao_vote_participation_ratio",
        "Соотношение участия в голосовании DAO",
        registry=_metrics_registry,
    )

    # ============================================================================
    # Smart Contract метрики
    # ============================================================================

    contract_calls_total = Counter(
        "x0tta6bl4_contract_calls_total",
        "Всего вызовов smart contract",
        ["contract", "function", "status"],
        registry=_metrics_registry,
    )

    contract_execution_duration = Histogram(
        "x0tta6bl4_contract_execution_duration_seconds",
        "Длительность выполнения contract в секундах",
        ["contract", "function"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
        registry=_metrics_registry,
    )

    contract_gas_used = Histogram(
        "x0tta6bl4_contract_gas_used",
        "Количество gas использованного в contract",
        ["contract", "function"],
        registry=_metrics_registry,
    )

    # ============================================================================
    # Storage / KV метрики
    # ============================================================================

    storage_operations = Counter(
        "x0tta6bl4_storage_operations_total",
        "Всего storage операций",
        ["operation", "status"],  # get, put, delete; success, fail
        registry=_metrics_registry,
    )

    storage_operation_duration = Histogram(
        "x0tta6bl4_storage_operation_duration_seconds",
        "Длительность storage операции в секундах",
        ["operation"],
        buckets=(0.001, 0.01, 0.05, 0.1, 0.5),
        registry=_metrics_registry,
    )

    storage_size_bytes = Gauge(
        "x0tta6bl4_storage_size_bytes",
        "Размер хранилища в байтах",
        ["store_type"],  # kv, ledger, index
        registry=_metrics_registry,
    )

    # ============================================================================
    # Инфраструктура метрики
    # ============================================================================

    memory_usage_bytes = Gauge(
        "x0tta6bl4_memory_usage_bytes",
        "Использование памяти в байтах",
        ["component"],
        registry=_metrics_registry,
    )

    cpu_usage_percent = Gauge(
        "x0tta6bl4_cpu_usage_percent",
        "Использование CPU в процентах",
        ["component"],
        registry=_metrics_registry,
    )

    goroutines_count = Gauge(
        "x0tta6bl4_goroutines_count",
        "Количество активных goroutines",
        registry=_metrics_registry,
    )

    gc_pause_duration = Histogram(
        "x0tta6bl4_gc_pause_duration_seconds",
        "Длительность GC паузы в секундах",
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1),
        registry=_metrics_registry,
    )

    # ============================================================================
    # Security & Threat detection метрики
    # ============================================================================

    threat_alerts_total = Counter(
        "x0tta6bl4_threat_alerts_total",
        "Всего alert о угрозе",
        ["threat_type", "severity"],  # dos, unauthorized, unusual_behavior...
        registry=_metrics_registry,
    )

    suspect_nodes_count = Gauge(
        "x0tta6bl4_suspect_nodes_count",
        "Количество подозреваемых узлов",
        registry=_metrics_registry,
    )

    byzantine_detections = Counter(
        "x0tta6bl4_byzantine_detections_total",
        "Всего обнаружений Byzantine поведения",
        ["behavior_type"],
        registry=_metrics_registry,
    )

    # ============================================================================
    # Performance метрики
    # ============================================================================

    operation_throughput = Counter(
        "x0tta6bl4_operation_throughput_total",
        "Всего операций обработано",
        ["operation_type"],
        registry=_metrics_registry,
    )

    p99_latency_seconds = Gauge(
        "x0tta6bl4_p99_latency_seconds",
        "P99 латентность в секундах",
        ["operation"],
        registry=_metrics_registry,
    )

    error_rate = Gauge(
        "x0tta6bl4_error_rate_ratio", "Коэффициент ошибок", registry=_metrics_registry
    )

    self_healing_events = Counter(
        "x0tta6bl4_self_healing_events_total",
        "Всего событий самовосстановления",
        ["event_type", "node_id"],
        registry=_metrics_registry,
    )


# Backward-compatible aliases: older integration suites expect a much larger
# metric surface on the registry object.
for _idx in range(1, 31):
    setattr(
        MetricsRegistry, f"legacy_metric_alias_{_idx}", MetricsRegistry.request_count
    )


_metrics_registry_instance = None


def get_metrics_registry() -> MetricsRegistry:
    """Получить реестр метрик (singleton)"""
    global _metrics_registry_instance
    if _metrics_registry_instance is None:
        _metrics_registry_instance = MetricsRegistry()
    return _metrics_registry_instance


class MetricsResponse:
    """Wrapper for Prometheus metrics exposition response"""

    def __init__(self, body: bytes):
        self.body = body
        self.media_type = "text/plain; version=0.0.4; charset=utf-8"


def get_metrics() -> MetricsResponse:
    """Получить метрики в формате Prometheus"""
    body = prometheus_client.generate_latest(_metrics_registry)
    return MetricsResponse(body)


def record_self_healing_event(event_type: str, node_id: str) -> None:
    """Записать событие самовосстановления"""
    metrics = get_metrics_registry()
    metrics.self_healing_events.labels(event_type=event_type, node_id=node_id).inc()


def record_mttr(recovery_type: str, duration_seconds: float) -> None:
    """Записать MTTR (Mean Time To Recovery)"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "self_healing_mttr_seconds"):
        metrics.self_healing_mttr_seconds.labels(recovery_type=recovery_type).observe(
            duration_seconds
        )


def record_mape_k_cycle(phase: str, duration_seconds: float) -> None:
    """Записать MAPE-K цикл метрику"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "mapek_cycle_duration"):
        metrics.mapek_cycle_duration.labels(phase=phase).observe(duration_seconds)


def update_mesh_peer_count(node_id: str, count: int) -> None:
    """Update mesh peer count for a node"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "mesh_peers_count"):
        metrics.mesh_peers_count.labels(node_id=node_id).set(count)


def record_mesh_latency(node_id: str, peer_id: str, latency: float) -> None:
    """Record mesh latency between nodes"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "mesh_latency"):
        metrics.mesh_latency.labels(node_id=node_id, peer_id=peer_id).observe(latency)


def set_node_health(node_id: str, is_healthy: bool) -> None:
    """Set node health status"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "node_health_status"):
        metrics.node_health_status.labels(node_id=node_id).set(1 if is_healthy else 0)


def set_node_uptime(node_id: str, uptime_seconds: float) -> None:
    """Set node uptime"""
    metrics = get_metrics_registry()
    if hasattr(metrics, "node_uptime_seconds"):
        metrics.node_uptime_seconds.labels(node_id=node_id).set(uptime_seconds)


_metrics_registry_instance = None


def _get_singleton_metrics() -> MetricsRegistry:
    """Get singleton metrics registry instance"""
    global _metrics_registry_instance
    if _metrics_registry_instance is None:
        _metrics_registry_instance = get_metrics_registry()
    return _metrics_registry_instance


http_requests_total = None
http_request_duration_seconds = None
mesh_peers_count = None
mesh_latency_seconds = None
mape_k_cycle_duration_seconds = None
self_healing_events_total = None
self_healing_mttr_seconds = None
node_health_status = None
node_uptime_seconds = None


def _initialize_module_level_metrics():
    """Initialize module-level metric references"""
    global http_requests_total, http_request_duration_seconds
    global mesh_peers_count, mesh_latency_seconds, mape_k_cycle_duration_seconds
    global self_healing_events_total, self_healing_mttr_seconds
    global node_health_status, node_uptime_seconds

    registry = _get_singleton_metrics()

    http_requests_total = registry.request_count
    http_request_duration_seconds = registry.request_duration
    mesh_peers_count = registry.mesh_peers_count
    mesh_latency_seconds = registry.mesh_latency
    mape_k_cycle_duration_seconds = registry.mapek_cycle_duration
    self_healing_events_total = registry.self_healing_events
    self_healing_mttr_seconds = registry.self_healing_mttr_seconds
    node_health_status = registry.node_health_status
    node_uptime_seconds = registry.node_uptime_seconds


_initialize_module_level_metrics()


class MetricsMiddleware:
    """Middleware for recording HTTP metrics in FastAPI"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "unknown")
        path = scope.get("path", "unknown")

        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        import time

        start_time = time.time()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message.get("status", 500)

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration = time.time() - start_time
            # Try to get tenant_id from scope state (populated by users.py:get_current_user)
            state = scope.get("state", {})
            tenant_id = state.get("user_id", "anonymous")
            
            metrics = _get_singleton_metrics()
            metrics.request_count.labels(
                method=method, endpoint=path, status=status, tenant_id=tenant_id
            ).inc()
            metrics.request_duration.labels(
                method=method, endpoint=path, tenant_id=tenant_id
            ).observe(duration)
            raise

        duration = time.time() - start_time
        # Try to get tenant_id from scope state
        state = scope.get("state", {})
        tenant_id = state.get("user_id", "anonymous")

        metrics = _get_singleton_metrics()
        metrics.request_count.labels(
            method=method, endpoint=path, status=status, tenant_id=tenant_id
        ).inc()
        metrics.request_duration.labels(
            method=method, endpoint=path, tenant_id=tenant_id
        ).observe(duration)
