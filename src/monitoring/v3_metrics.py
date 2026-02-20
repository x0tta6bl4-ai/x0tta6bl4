"""
Monitoring Metrics for V3.0 Components
======================================

Prometheus метрики для мониторинга компонентов v3.0.
"""

import logging
from typing import Any, Dict

from prometheus_client import Counter, Gauge, Histogram, Info

from src.version import __version__

logger = logging.getLogger(__name__)

# Метрики GraphSAGE
graphsage_analysis_total = Counter(
    "graphsage_analysis_total",
    "Total number of GraphSAGE analyses",
    ["failure_type", "severity"],
)

graphsage_analysis_duration = Histogram(
    "graphsage_analysis_duration_seconds",
    "Time spent on GraphSAGE analysis",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0],
)

graphsage_confidence = Histogram(
    "graphsage_confidence",
    "GraphSAGE analysis confidence",
    buckets=[0.5, 0.7, 0.8, 0.9, 0.95, 1.0],
)

# Метрики Stego-Mesh
stego_encode_total = Counter(
    "stego_encode_total", "Total number of stego-mesh encodings", ["protocol"]
)

stego_decode_total = Counter(
    "stego_decode_total", "Total number of stego-mesh decodings", ["protocol"]
)

stego_packet_size = Histogram(
    "stego_packet_size_bytes",
    "Size of stego-mesh packets",
    ["protocol"],
    buckets=[100, 500, 1000, 5000, 10000],
)

stego_overhead = Histogram(
    "stego_overhead_bytes", "Overhead of stego-mesh encoding", ["protocol"]
)

# Метрики Digital Twins
chaos_test_total = Counter(
    "chaos_test_total", "Total number of chaos tests", ["scenario", "success"]
)

chaos_recovery_time = Histogram(
    "chaos_recovery_time_seconds",
    "Time to recover from chaos scenario",
    ["scenario"],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

digital_twins_nodes = Gauge(
    "digital_twins_nodes_total", "Total number of digital twin nodes"
)

# Метрики Federated Learning
fl_round_total = Counter("fl_round_total", "Total number of federated learning rounds")

fl_privacy_budget = Gauge(
    "fl_privacy_budget_epsilon",
    "Current privacy budget (epsilon) for federated learning",
)

fl_model_accuracy = Gauge("fl_model_accuracy", "Federated learning model accuracy")

# Метрики Audit Trail
audit_record_total = Counter(
    "audit_record_total", "Total number of audit records", ["record_type"]
)

audit_trail_size = Gauge(
    "audit_trail_size_total", "Total number of records in audit trail"
)

audit_ipfs_enabled = Gauge(
    "audit_ipfs_enabled",
    "Whether IPFS is enabled for audit trail (1=enabled, 0=disabled)",
)

audit_ethereum_enabled = Gauge(
    "audit_ethereum_enabled",
    "Whether Ethereum is enabled for audit trail (1=enabled, 0=disabled)",
)

# Информация о версии
v3_info = Info("v3_components", "Information about V3.0 components")


class V3MetricsCollector:
    """
    Коллектор метрик для компонентов v3.0.
    """

    def __init__(self):
        """Инициализация коллектора"""
        v3_info.info(
            {
                "version": __version__,
                "components": "graphsage,stego_mesh,digital_twins,federated_learning,audit_trail",
            }
        )
        logger.info("V3.0 metrics collector initialized")

    def record_graphsage_analysis(
        self, failure_type: str, severity: str, confidence: float, duration: float
    ):
        """Запись метрик GraphSAGE анализа"""
        graphsage_analysis_total.labels(
            failure_type=failure_type, severity=severity
        ).inc()
        graphsage_analysis_duration.observe(duration)
        graphsage_confidence.observe(confidence)

    def record_stego_encode(self, protocol: str, original_size: int, encoded_size: int):
        """Запись метрик Stego-Mesh кодирования"""
        stego_encode_total.labels(protocol=protocol).inc()
        stego_packet_size.labels(protocol=protocol).observe(encoded_size)
        stego_overhead.labels(protocol=protocol).observe(encoded_size - original_size)

    def record_stego_decode(self, protocol: str):
        """Запись метрик Stego-Mesh декодирования"""
        stego_decode_total.labels(protocol=protocol).inc()

    def record_chaos_test(self, scenario: str, success: bool, recovery_time: float):
        """Запись метрик chaos-теста"""
        chaos_test_total.labels(scenario=scenario, success=str(success).lower()).inc()
        chaos_recovery_time.labels(scenario=scenario).observe(recovery_time)

    def set_digital_twins_nodes(self, count: int):
        """Установка количества узлов Digital Twins"""
        digital_twins_nodes.set(count)

    def record_fl_round(self, epsilon: float, accuracy: float):
        """Запись метрик Federated Learning"""
        fl_round_total.inc()
        fl_privacy_budget.set(epsilon)
        fl_model_accuracy.set(accuracy)

    def record_audit_record(self, record_type: str):
        """Запись метрик Audit Trail"""
        audit_record_total.labels(record_type=record_type).inc()

    def set_audit_trail_size(self, size: int):
        """Установка размера аудит-трейла"""
        audit_trail_size.set(size)

    def set_audit_ipfs_enabled(self, enabled: bool):
        """Установка статуса IPFS"""
        audit_ipfs_enabled.set(1 if enabled else 0)

    def set_audit_ethereum_enabled(self, enabled: bool):
        """Установка статуса Ethereum"""
        audit_ethereum_enabled.set(1 if enabled else 0)


# Глобальный экземпляр коллектора
metrics_collector = V3MetricsCollector()
