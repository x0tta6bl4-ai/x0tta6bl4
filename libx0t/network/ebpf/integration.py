"""
Интеграция eBPF Explainer с реальными eBPF programs
"""

import logging
from typing import Any, Dict, List, Optional

from .explainer import EBPFEvent, EBPFEventType, EBPFExplainer

logger = logging.getLogger(__name__)


class EBPFProgramIntegration:
    """
    Интеграция eBPF Explainer с реальными eBPF programs

    Собирает события от eBPF programs и объясняет их
    """

    def __init__(self, ebpf_programs: Optional[List[Dict[str, Any]]] = None):
        self.ebpf_programs = ebpf_programs or []
        self.explainer = EBPFExplainer()
        self.event_history: List[EBPFEvent] = []

        logger.info("eBPF Program Integration initialized")

    def register_ebpf_program(
        self, program_id: str, program_type: str, metrics_callback=None
    ):
        """Зарегистрировать eBPF program для мониторинга"""
        program = {
            "id": program_id,
            "type": program_type,
            "metrics_callback": metrics_callback,
            "events": [],
        }
        self.ebpf_programs.append(program)
        logger.info(f"eBPF program {program_id} registered")

    def collect_events(self, program_id: str) -> List[EBPFEvent]:
        """Собрать события от eBPF program"""
        program = next((p for p in self.ebpf_programs if p["id"] == program_id), None)
        if not program:
            logger.warning(f"Program {program_id} not found")
            return []

        events = []

        # Если есть callback, использовать его
        if program.get("metrics_callback"):
            try:
                metrics = program["metrics_callback"]()
                # Преобразовать метрики в события
                for metric in metrics:
                    event = self._metric_to_event(metric, program_id)
                    if event:
                        events.append(event)
                        # Объяснить событие
                        explanation = self.explainer.explain_event(event)
                        logger.debug(f"Event explained: {explanation}")
            except Exception as e:
                logger.error(f"Error collecting events from {program_id}: {e}")

        # Сохранить в историю
        self.event_history.extend(events)

        return events

    def _metric_to_event(
        self, metric: Dict[str, Any], program_id: str
    ) -> Optional[EBPFEvent]:
        """Преобразовать метрику в EBPFEvent"""
        import time

        event_type_str = metric.get("event_type", "packet_drop")
        try:
            event_type = EBPFEventType[event_type_str.upper()]
        except KeyError:
            logger.warning(f"Unknown event type: {event_type_str}")
            return None

        event = EBPFEvent(
            event_type=event_type,
            timestamp=time.time(),
            node_id=metric.get("node_id", "unknown"),
            program_id=program_id,
            details=metric,
        )

        return event

    def explain_program_performance(self, program_id: str) -> str:
        """Объяснить performance eBPF program"""
        program = next((p for p in self.ebpf_programs if p["id"] == program_id), None)
        if not program:
            return f"Program {program_id} not found"

        # Собрать метрики
        if program.get("metrics_callback"):
            try:
                metrics = program["metrics_callback"]()
                # Преобразовать в формат для explainer
                performance_metrics = {
                    "cpu_percent": metrics.get("cpu_percent", 0.0),
                    "memory_bytes": metrics.get("memory_bytes", 0),
                    "packets_processed": metrics.get("packets_processed", 0),
                    "packet_drops": metrics.get("packet_drops", 0),
                }

                return self.explainer.explain_performance(performance_metrics)
            except Exception as e:
                logger.error(f"Error explaining performance: {e}")
                return f"Error: {e}"

        return "No metrics available"

    def get_all_explanations(self) -> Dict[str, List[str]]:
        """Получить все объяснения для всех программ"""
        explanations = {}

        for program in self.ebpf_programs:
            program_id = program["id"]
            events = self.collect_events(program_id)
            explanations[program_id] = [
                self.explainer.explain_event(event) for event in events
            ]

        return explanations
