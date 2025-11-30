"""
GraphSAGE Anomaly Detector - Observe Mode
Реализация observe mode для постепенной миграции к block mode
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

logger = logging.getLogger(__name__)


class DetectorMode(Enum):
    """Режимы работы детектора"""
    OBSERVE = "observe"  # Только логирование, без действий
    WARN = "warn"       # Логирование + алерты
    BLOCK = "block"     # Логирование + блокировка действий


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
        anomaly_score = self.detector.predict(graph_data)
        confidence = self.detector.get_confidence(graph_data)
        
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
    
    def _handle_warn_mode(self, event: AnomalyEvent):
        """Обработка в warn mode - логирование + алерты"""
        self._handle_observe_mode(event)
        
        # Отправить alert
        logger.warning(
            f"WARN: High-confidence anomaly on {event.node_id} "
            f"(score: {event.anomaly_score:.3f})"
        )
        
        # TODO: Интеграция с alerting system (Prometheus, PagerDuty, etc.)
        # self._send_alert(event)
    
    def _handle_block_mode(self, event: AnomalyEvent):
        """Обработка в block mode - логирование + блокировка"""
        self._handle_warn_mode(event)
        
        # Блокировать действие
        logger.error(
            f"BLOCK: Blocking action on {event.node_id} due to anomaly "
            f"(score: {event.anomaly_score:.3f})"
        )
        
        # TODO: Реализовать блокировку действий
        # self._block_action(event)
        event.action_taken = "blocked"
    
    def _extract_metrics(self, graph_data: Dict[str, Any]) -> Dict[str, float]:
        """Извлечь метрики из graph data"""
        return {
            'cpu_percent': graph_data.get('cpu_percent', 0.0),
            'memory_percent': graph_data.get('memory_percent', 0.0),
            'packet_loss': graph_data.get('packet_loss', 0.0),
            'latency_ms': graph_data.get('latency_ms', 0.0),
        }
    
    def _save_event_for_analysis(self, event: AnomalyEvent):
        """Сохранить событие для последующего анализа"""
        # TODO: Сохранить в базу данных или файл
        # Для сейчас просто логируем
        logger.debug(f"Event saved for analysis: {event.node_id}")
    
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

