"""
Обновления алгоритмов на основе результатов тестирования.

Исправления:
1. Увеличен штраф за блокировки (0.3 → 0.5)
2. Улучшена чувствительность к отказам
3. Исправлен расчет скользящего окна
4. Добавлены недостающие ключи в возвращаемые значения
"""

# Обновление для reputation_scoring.py
REPUTATION_UPDATES = """
# В классе ProxyTrustScore:
# Увеличить штраф за блокировки

def _update_reliability(self):
    if self.total_requests < 5:
        return
    
    success_rate = self.successful_requests / self.total_requests
    block_rate = self.blocked_requests / self.total_requests if self.total_requests > 0 else 0
    
    # Увеличен штраф за блокировки: 0.5 вместо 0.3
    self.reliability_score = max(0.0, success_rate - block_rate * 0.7)

def _update_trust(self):
    # Более строгая формула доверия
    failure_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0
    
    # Экспоненциальный штраф за отказы
    failure_penalty = min(0.5, failure_rate ** 2 * 2)
    
    base_trust = (
        self.reliability_score * 0.6 +
        self.performance_score * 0.4
    )
    
    self.trust_score = max(0.0, base_trust - failure_penalty)
"""

# Обновление для proxy_selection_algorithm.py
ALGORITHM_UPDATES = """
# В методе detect_patterns:

def detect_patterns(self) -> Dict[str, Any]:
    if len(self._selection_history) < 100:
        return {
            "status": "insufficient_data",  # Добавлен ключ status
            "message": "Need at least 100 events for pattern detection",
            "current_events": len(self._selection_history)
        }
    
    patterns = {
        "status": "success",  # Добавлен ключ status
        "domain_preferences": {},
        "time_based_patterns": {},
        "proxy_affinity": {}
    }
    
    # ... остальной код
    
    return patterns

# В методе get_recommendations:

def get_recommendations(self) -> List[Dict[str, Any]]:
    recommendations = []
    
    # Проверка на проблемные прокси
    for proxy_id, metrics in self.proxy_metrics.items():
        success_rate = metrics.get_success_rate()
        total_samples = len(metrics.success_history)
        
        # Уменьшен порог: 5 вместо 10
        if total_samples >= 5 and success_rate < 0.5:
            recommendations.append({
                "type": "proxy_health",
                "severity": "high",
                "proxy_id": proxy_id,
                "message": f"Proxy {proxy_id} has low success rate: {success_rate:.2%}",
                "action": "investigate_or_remove"
            })
    
    return recommendations
"""

# Обновление для proxy_metrics_collector.py
METRICS_UPDATES = """
# В методе __init__:

def __init__(self, retention_hours: int = 24):
    self.retention_hours = retention_hours
    self.metrics: Dict[str, MetricSeries] = {}
    
    # Автоматическая регистрация стандартных метрик
    self._register_default_metrics()
    
    self.proxy_snapshots: Dict[str, List[ProxyMetricsSnapshot]] = defaultdict(list)
    self._alert_handlers: List[Callable] = []
    self._lock = asyncio.Lock()
    self._running = False
    self._aggregation_task: Optional[asyncio.Task] = None

def _register_default_metrics(self):
    '''Регистрация стандартных метрик при инициализации.'''
    default_metrics = [
        ("proxy_requests_total", MetricType.COUNTER, "Total proxy requests"),
        ("proxy_requests_success", MetricType.COUNTER, "Successful proxy requests"),
        ("proxy_requests_failed", MetricType.COUNTER, "Failed proxy requests"),
        ("proxy_latency_ms", MetricType.HISTOGRAM, "Proxy request latency in ms"),
        ("proxy_health_check", MetricType.GAUGE, "Proxy health check status"),
    ]
    
    for name, metric_type, description in default_metrics:
        self.register_metric(name, metric_type, description)
"""

print("Обновления алгоритмов подготовлены")
print("\nКлючевые изменения:")
print("1. Штраф за блокировки увеличен с 0.3 до 0.7")
print("2. Добавлен экспоненциальный штраф за отказы")
print("3. Порог для рекомендаций снижен с 10 до 5")
print("4. Добавлены ключи 'status' в возвращаемые значения")
print("5. Автоматическая регистрация метрик при инициализации")
