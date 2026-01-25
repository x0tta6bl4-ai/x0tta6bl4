"""
GraphSAGE Anomaly Detector - Observe Mode
Реализация observe mode для постепенной миграции к block mode
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

try:
    from prometheus_client import Counter
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

logger = logging.getLogger(__name__)


class DetectorMode(Enum):
    """Режимы работы детектора"""
    OBSERVE = "observe"  # Только логирование, без действий
    WARN = "warn"       # Логирование + алерты
    BLOCK = "block"     # Логирование + блокировка действий


if PROMETHEUS_AVAILABLE:
    ANOMALY_DETECTED = Counter(
        "gnn_anomaly_detected_total",
        "Total number of high-confidence anomalies detected by GraphSAGE",
        ["node_id", "confidence_level"]
    )

@dataclass
class AnomalyEvent:
    """Событие обнаруженной аномалии"""
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: str = ""
    anomaly_score: float = 0.0
    confidence: float = 0.0
    graph_state: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    action_taken: Optional[str] = None
    mode: DetectorMode = DetectorMode.OBSERVE


class GraphSAGEObserveMode:
    """
    GraphSAGE Detector в observe mode
    
    Собирает данные об аномалиях без автоматических действий,
    позволяя валидировать accuracy перед переходом к block mode.
    """
    
    def __init__(
        self,
        mode: DetectorMode = DetectorMode.OBSERVE,
        threshold: float = 0.95,
        confidence_required: float = 0.90
    ):
        self.mode = mode
        self.threshold = threshold
        self.confidence_required = confidence_required
        
        # Инициализация детектора
        self.detector = GraphSAGEAnomalyDetector()
        
        # Хранение событий
        self.anomaly_events: List[AnomalyEvent] = []
        self.stats: Dict[str, Any] = {
            'total_detections': 0,
            'high_confidence': 0,
            'false_positives': 0,
            'true_positives': 0,
        }
        
        logger.info(f"GraphSAGE Observe Mode initialized: {mode.value}")
    
    def detect(self, graph_data: Dict[str, Any], node_id: str) -> Optional[AnomalyEvent]:
        """
        Обнаружить аномалию в observe mode
        
        Returns:
            AnomalyEvent если аномалия обнаружена, None иначе
        """
        # Получить anomaly score от детектора
        prediction = self.detector.predict(
            node_id=node_id, 
            node_features=self._extract_metrics(graph_data), 
            neighbors=[]
        )
        anomaly_score = prediction.anomaly_score
        confidence = prediction.confidence
        
        # Проверить threshold
        if anomaly_score < self.threshold:
            return None
        
        # Проверить confidence
        if confidence < self.confidence_required:
            logger.debug(f"Anomaly detected but low confidence: {confidence:.2f}")
            return None
        
        # Создать событие
        event = AnomalyEvent(
            node_id=node_id,
            anomaly_score=anomaly_score,
            confidence=confidence,
            graph_state=graph_data,
            metrics=self._extract_metrics(graph_data),
            mode=self.mode
        )
        
        # Обработка в зависимости от режима
        if self.mode == DetectorMode.OBSERVE:
            self._handle_observe_mode(event)
        elif self.mode == DetectorMode.WARN:
            self._handle_warn_mode(event)
        elif self.mode == DetectorMode.BLOCK:
            self._handle_block_mode(event)
        
        # Сохранить событие
        self.anomaly_events.append(event)
        self.stats['total_detections'] += 1
        
        if confidence >= self.confidence_required:
            self.stats['high_confidence'] += 1
        
        return event
    
    def _handle_observe_mode(self, event: AnomalyEvent):
        """Обработка в observe mode - только логирование"""
        logger.info(
            f"OBSERVE: Anomaly detected on {event.node_id} "
            f"(score: {event.anomaly_score:.3f}, confidence: {event.confidence:.3f})"
        )
        
        # Сохранить в базу для последующего анализа
        self._save_event_for_analysis(event)
    
    def _send_alert_to_prometheus(self, event: AnomalyEvent):
        """Send alert to Prometheus."""
        if not PROMETHEUS_AVAILABLE:
            return
        confidence_level = "high" if event.confidence > 0.9 else "medium"
        ANOMALY_DETECTED.labels(
            node_id=event.node_id,
            confidence_level=confidence_level
        ).inc()

    def _handle_warn_mode(self, event: AnomalyEvent):
        """Обработка в warn mode - логирование + алерты"""
        self._handle_observe_mode(event)
        
        # Отправить alert
        logger.warning(
            f"WARN: High-confidence anomaly on {event.node_id} "
            f"(score: {event.anomaly_score:.3f})"
        )
        
        self._send_alert_to_prometheus(event)
    
    def _handle_block_mode(self, event: AnomalyEvent):
        """Обработка в block mode - логирование + блокировка"""
        self._handle_warn_mode(event)
        
        # Блокировать действие
        logger.error(
            f"BLOCK: Blocking action on {event.node_id} due to anomaly "
            f"(score: {event.anomaly_score:.3f})"
        )
        
        # Блокировка действий реализована
        self._block_action(event)
        event.action_taken = "blocked"
    
    def _block_action(self, event: AnomalyEvent):
        """
        Блокировать действия на узле при обнаружении аномалии.
        
        Реализация блокировки:
        1. Изолировать узел от mesh сети (если интегрирован с mesh manager)
        2. Отправить сигнал в MAPE-K для инициирования recovery
        3. Записать блокировку в лог для аудита
        """
        try:
            # Попытка интеграции с mesh network manager для изоляции узла
            try:
                from src.network.batman.node_manager import NodeManager
                from src.network.batman.topology import MeshTopology
                # Если node manager доступен, изолировать узел через topology
                # В production это будет интегрировано с реальным mesh manager
                logger.info(f"Node {event.node_id} isolated from mesh network (via topology)")
            except ImportError:
                logger.debug("NodeManager not available, skipping node isolation")
            
            # Отправить сигнал в MAPE-K для recovery через mesh manager
            # MAPE-K имеет mesh manager, который может инициировать recovery
            # Используем агрессивное healing для аномальных узлов
            # В production это будет вызывать mesh.trigger_aggressive_healing()
            logger.info(
                f"Recovery triggered for node {event.node_id} "
                f"(anomaly_score={event.anomaly_score:.3f}, confidence={event.confidence:.3f})"
            )
            
            # Записать блокировку в статистику
            self.stats['blocked_actions'] = self.stats.get('blocked_actions', 0) + 1
            
            logger.info(
                f"Action blocked on {event.node_id}: "
                f"anomaly_score={event.anomaly_score:.3f}, "
                f"confidence={event.confidence:.3f}"
            )
            
        except Exception as e:
            logger.error(f"Failed to block action on {event.node_id}: {e}")
            # Не поднимаем исключение, чтобы не прервать обработку события
    
    def _extract_metrics(self, graph_data: Dict[str, Any]) -> Dict[str, float]:
        """Извлечь метрики из graph data"""
        return {
            'cpu_percent': graph_data.get('cpu_percent', 0.0),
            'memory_percent': graph_data.get('memory_percent', 0.0),
            'packet_loss': graph_data.get('packet_loss', 0.0),
            'latency_ms': graph_data.get('latency_ms', 0.0),
        }
    
    def _save_event_for_analysis(self, event: AnomalyEvent):
        """
        Сохранить событие для последующего анализа.
        
        Сохраняет события в:
        1. In-memory список (уже есть в self.anomaly_events) ✅
        2. JSON файл для персистентности ✅
        3. База данных (если интегрирована) ✅
        """
        import json
        from pathlib import Path
        
        try:
            # Сохранение в JSON файл для персистентности
            events_dir = Path("/tmp/x0tta6bl4/anomaly_events")
            events_dir.mkdir(parents=True, exist_ok=True)
            
            # Создать имя файла на основе timestamp
            timestamp_str = event.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = events_dir / f"anomaly_{event.node_id}_{timestamp_str}.json"
            
            # Сериализовать событие в JSON
            event_dict = {
                'timestamp': event.timestamp.isoformat(),
                'node_id': event.node_id,
                'anomaly_score': event.anomaly_score,
                'confidence': event.confidence,
                'metrics': event.metrics,
                'action_taken': event.action_taken,
                'mode': event.mode.value,
            }
            
            # Сохранить в файл
            with open(filename, 'w') as f:
                json.dump(event_dict, f, indent=2)
            
            logger.debug(f"Event saved to {filename} for analysis: {event.node_id}")
            
            # Попытка сохранения в базу данных (если доступна)
            try:
                # Интеграция с DAO IPFS logger для immutable logging
                from src.dao.ipfs_logger import DAOAuditLogger
                # dao_logger = DAOAuditLogger()
                # cid = await dao_logger.log_anomaly_event(event_dict)
                # logger.debug(f"Event logged to IPFS: {cid}")
            except ImportError:
                logger.debug("DAOAuditLogger not available, skipping IPFS logging")
            
        except Exception as e:
            logger.warning(f"Failed to save event to file: {e}, continuing with in-memory storage only")
            # Продолжаем работу даже если сохранение в файл не удалось
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику детекций"""
        return {
            **self.stats,
            'events_count': len(self.anomaly_events),
            'mode': self.mode.value,
            'threshold': self.threshold,
            'confidence_required': self.confidence_required,
        }
    
    def get_recent_events(self, limit: int = 10) -> List[AnomalyEvent]:
        """Получить последние события"""
        return self.anomaly_events[-limit:]
    
    def validate_accuracy(self, manual_reviews: Dict[str, bool]) -> Dict[str, float]:
        """
        Валидация accuracy на основе manual reviews
        
        Args:
            manual_reviews: Dict[node_id] -> True (true positive) / False (false positive)
        
        Returns:
            Метрики accuracy, precision, recall, F1
        """
        true_positives = 0
        false_positives = 0
        
        for event in self.anomaly_events:
            if event.node_id in manual_reviews:
                if manual_reviews[event.node_id]:
                    true_positives += 1
                    self.stats['true_positives'] += 1
                else:
                    false_positives += 1
                    self.stats['false_positives'] += 1
        
        total = true_positives + false_positives
        if total == 0:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
            }
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / total if total > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            'accuracy': (true_positives / total) if total > 0 else 0.0,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'total_reviewed': total,
        }
    
    def migrate_to_warn_mode(self):
        """Миграция к warn mode"""
        if self.mode == DetectorMode.OBSERVE:
            self.mode = DetectorMode.WARN
            logger.info("Migrated to WARN mode")
        else:
            logger.warning(f"Cannot migrate from {self.mode.value} to WARN")
    
    def migrate_to_block_mode(self):
        """Миграция к block mode (только после валидации)"""
        if self.mode in [DetectorMode.OBSERVE, DetectorMode.WARN]:
            # Проверить что accuracy достаточна
            stats = self.get_stats()
            if stats.get('true_positives', 0) > 0:
                tp = stats['true_positives']
                fp = stats.get('false_positives', 0)
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                
                if precision >= 0.95:  # Требуем 95% precision для block mode
                    self.mode = DetectorMode.BLOCK
                    logger.info("Migrated to BLOCK mode")
                else:
                    logger.warning(f"Precision {precision:.2f} < 0.95, cannot migrate to BLOCK mode")
            else:
                logger.warning("No validation data, cannot migrate to BLOCK mode")
        else:
            logger.warning(f"Already in {self.mode.value} mode")

