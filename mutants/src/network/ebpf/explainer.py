"""
eBPF Event Explainer
Объясняет eBPF события простым языком для non-kernel developers
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EBPFEventType(Enum):
    """Типы eBPF событий"""
    PACKET_DROP = "packet_drop"
    PACKET_RETRANSMIT = "packet_retransmit"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"
    HIGH_CPU_USAGE = "high_cpu_usage"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    PROGRAM_LOADED = "program_loaded"
    PROGRAM_UNLOADED = "program_unloaded"


@dataclass
class EBPFEvent:
    """eBPF событие"""
    event_type: EBPFEventType
    timestamp: float
    node_id: str
    program_id: str
    details: Dict[str, Any]
    human_readable: str = ""


class EBPFExplainer:
    """
    Объясняет eBPF события простым языком
    
    Преобразует технические eBPF события в понятные объяснения
    для людей без глубоких знаний kernel programming.
    """
    
    def __init__(self):
        self.explanations: Dict[EBPFEventType, str] = {
            EBPFEventType.PACKET_DROP: (
                "Пакет был отброшен eBPF программой. "
                "Это может происходить из-за: превышения лимитов, "
                "security правил, или проблем с сетью."
            ),
            EBPFEventType.PACKET_RETRANSMIT: (
                "Пакет был отправлен повторно. "
                "Обычно это означает что первый пакет был потерян "
                "или не получил подтверждение."
            ),
            EBPFEventType.CONNECTION_ESTABLISHED: (
                "Новое сетевое соединение установлено. "
                "eBPF программа отслеживает это для мониторинга активности."
            ),
            EBPFEventType.CONNECTION_CLOSED: (
                "Сетевое соединение закрыто. "
                "Это нормальное событие при завершении коммуникации."
            ),
            EBPFEventType.HIGH_CPU_USAGE: (
                "eBPF программа потребляет много CPU. "
                "Это может указывать на высокую нагрузку или "
                "неоптимальную реализацию программы."
            ),
            EBPFEventType.HIGH_MEMORY_USAGE: (
                "eBPF программа потребляет много памяти. "
                "Проверьте размер eBPF maps и количество данных."
            ),
            EBPFEventType.PROGRAM_LOADED: (
                "eBPF программа загружена в kernel. "
                "Программа теперь активна и обрабатывает события."
            ),
            EBPFEventType.PROGRAM_UNLOADED: (
                "eBPF программа выгружена из kernel. "
                "Программа больше не обрабатывает события."
            ),
        }
        
        self.troubleshooting_tips: Dict[EBPFEventType, List[str]] = {
            EBPFEventType.PACKET_DROP: [
                "Проверьте network connectivity",
                "Проверьте firewall rules",
                "Проверьте eBPF program logic",
            ],
            EBPFEventType.HIGH_CPU_USAGE: [
                "Оптимизируйте eBPF program",
                "Уменьшите frequency обработки",
                "Используйте более эффективные data structures",
            ],
            EBPFEventType.HIGH_MEMORY_USAGE: [
                "Уменьшите размер eBPF maps",
                "Очистите старые данные",
                "Используйте более компактные структуры данных",
            ],
        }
    
    def explain_event(self, event: EBPFEvent) -> str:
        """
        Генерирует human-readable объяснение события
        
        Returns:
            Понятное объяснение события
        """
        base_explanation = self.explanations.get(
            event.event_type,
            f"eBPF событие типа {event.event_type.value}"
        )
        
        # Добавить детали из event.details
        details_str = self._format_details(event.details)
        
        explanation = f"{base_explanation}\n\nДетали: {details_str}"
        
        # Добавить troubleshooting tips если есть
        if event.event_type in self.troubleshooting_tips:
            tips = self.troubleshooting_tips[event.event_type]
            explanation += f"\n\nРекомендации:\n"
            for tip in tips:
                explanation += f"  - {tip}\n"
        
        event.human_readable = explanation
        return explanation
    
    def _format_details(self, details: Dict[str, Any]) -> str:
        """Форматировать детали события"""
        parts = []
        
        if 'packet_count' in details:
            parts.append(f"Пакетов: {details['packet_count']}")
        
        if 'cpu_percent' in details:
            parts.append(f"CPU: {details['cpu_percent']:.1f}%")
        
        if 'memory_bytes' in details:
            memory_mb = details['memory_bytes'] / (1024 * 1024)
            parts.append(f"Память: {memory_mb:.1f} MB")
        
        if 'latency_ms' in details:
            parts.append(f"Задержка: {details['latency_ms']:.1f}ms")
        
        return ", ".join(parts) if parts else "Нет дополнительных деталей"
    
    def explain_performance(self, metrics: Dict[str, float]) -> str:
        """
        Объясняет performance метрики
        
        Args:
            metrics: Словарь с метриками (cpu_percent, memory_bytes, etc.)
        
        Returns:
            Понятное объяснение performance
        """
        explanation = "Performance анализ eBPF программ:\n\n"
        
        if 'cpu_percent' in metrics:
            cpu = metrics['cpu_percent']
            if cpu < 2.0:
                explanation += f"✅ CPU usage: {cpu:.1f}% (отлично, <2%)\n"
            elif cpu < 5.0:
                explanation += f"⚠️  CPU usage: {cpu:.1f}% (приемлемо, но можно оптимизировать)\n"
            else:
                explanation += f"❌ CPU usage: {cpu:.1f}% (высокое, требуется оптимизация)\n"
        
        if 'memory_bytes' in metrics:
            memory_mb = metrics['memory_bytes'] / (1024 * 1024)
            if memory_mb < 100:
                explanation += f"✅ Memory usage: {memory_mb:.1f} MB (отлично)\n"
            elif memory_mb < 500:
                explanation += f"⚠️  Memory usage: {memory_mb:.1f} MB (приемлемо)\n"
            else:
                explanation += f"❌ Memory usage: {memory_mb:.1f} MB (высокое)\n"
        
        if 'packets_processed' in metrics:
            explanation += f"📊 Packets processed: {metrics['packets_processed']:,}\n"
        
        if 'packet_drops' in metrics:
            drops = metrics['packet_drops']
            if drops > 0:
                explanation += f"⚠️  Packet drops: {drops:,} (требует внимания)\n"
        
        return explanation
    
    def explain_bottleneck(self, analysis: Dict[str, Any]) -> str:
        """
        Объясняет bottleneck в eBPF программах
        
        Args:
            analysis: Результат анализа bottleneck
        
        Returns:
            Понятное объяснение bottleneck
        """
        bottleneck_type = analysis.get('type', 'unknown')
        severity = analysis.get('severity', 'medium')
        location = analysis.get('location', 'unknown')
        
        explanation = f"Bottleneck обнаружен:\n\n"
        explanation += f"Тип: {bottleneck_type}\n"
        explanation += f"Местоположение: {location}\n"
        explanation += f"Серьезность: {severity}\n\n"
        
        if bottleneck_type == 'cpu':
            explanation += (
                "eBPF программа потребляет слишком много CPU. "
                "Рекомендуется оптимизировать логику программы или "
                "уменьшить частоту обработки событий."
            )
        elif bottleneck_type == 'memory':
            explanation += (
                "eBPF программа потребляет слишком много памяти. "
                "Рекомендуется уменьшить размер eBPF maps или "
                "использовать более компактные структуры данных."
            )
        elif bottleneck_type == 'network':
            explanation += (
                "Проблема в сетевом слое. "
                "Рекомендуется проверить connectivity и network configuration."
            )
        
        return explanation

