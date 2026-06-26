"""
Модуль нагрузочного тестирования

Предоставляет инструменты для проверки производительности и масштабируемости
системы при различных уровнях нагрузки.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LoadPattern(Enum):
    """Паттерны нагрузки"""

    CONSTANT = "constant"  # Постоянная нагрузка
    RAMP = "ramp"  # Линейный рост
    SPIKE = "spike"  # Всплеск нагрузки
    WAVE = "wave"  # Волновая нагрузка
    STRESS = "stress"  # Стресс-тест до отказа


@dataclass
class LoadTestConfig:
    """Конфигурация для нагрузочного теста"""

    name: str
    pattern: LoadPattern
    initial_load: int  # Начальное количество запросов
    max_load: int  # Максимальная нагрузка
    duration_seconds: float  # Длительность теста
    ramp_duration_seconds: float = 10.0  # Время увеличения нагрузки
    spike_magnitude: float = 2.0  # Множитель для всплесков


@dataclass
class RequestMetrics:
    """Метрики одного запроса"""

    request_id: str
    start_time: float
    end_time: float
    success: bool
    latency_ms: float
    error: Optional[str] = None


@dataclass
class LoadTestResults:
    """Результаты нагрузочного теста"""

    test_name: str
    pattern: LoadPattern
    total_requests: int
    successful_requests: int
    failed_requests: int
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    p50_latency_ms: float  # Медиана
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float  # Запросов в секунду
    test_duration_seconds: float
    error_rate: float


class LoadTestExecutor:
    """
    Исполняет нагрузочные тесты с различными паттернами нагрузки.
    """

    def __init__(self, max_concurrent_requests: int = 100):
        self.max_concurrent_requests = max_concurrent_requests
        self.request_metrics: List[RequestMetrics] = []
        self.test_results: List[LoadTestResults] = []

    async def run_test(
        self, config: LoadTestConfig, request_func: Callable[[int], Any]
    ) -> LoadTestResults:
        """
        Запустить нагрузочный тест с заданной конфигурацией.

        Args:
            config: Конфигурация теста
            request_func: Асинхронная функция для выполнения запроса

        Returns:
            Результаты теста
        """
        logger.info(
            f"🔥 Начало нагрузочного теста: {config.name} ({config.pattern.value})"
        )

        self.request_metrics = []
        test_start = time.time()
        request_counter = 0

        # Получить функцию для генерации нагрузки
        load_generator = self._get_load_generator(config)

        while time.time() - test_start < config.duration_seconds:
            current_load = load_generator(time.time() - test_start)

            # Создать задачи для текущей нагрузки
            tasks = []
            for _ in range(int(current_load)):
                request_counter += 1
                task = asyncio.create_task(
                    self._execute_request(request_counter, request_func)
                )
                tasks.append(task)

                # Ограничить одновременные запросы
                if len(tasks) >= self.max_concurrent_requests:
                    await asyncio.gather(*tasks)
                    tasks = []

            # Ожидать оставшиеся задачи
            if tasks:
                await asyncio.gather(*tasks)

            await asyncio.sleep(0.1)  # Небольшая задержка между итерациями

        test_duration = time.time() - test_start

        # Вычислить результаты
        results = self._calculate_results(config, test_duration, request_counter)
        self.test_results.append(results)

        logger.info(f"✅ Тест завершен: {results.test_name}")
        logger.info(
            f"   Успешных: {results.successful_requests}/{results.total_requests}"
        )
        logger.info(f"   Средняя задержка: {results.avg_latency_ms:.2f}ms")
        logger.info(f"   Пропускная способность: {results.throughput_rps:.2f} RPS")

        return results

    async def _execute_request(
        self, request_id: int, request_func: Callable
    ) -> RequestMetrics:
        """Выполнить один запрос и собрать метрики"""
        start_time = time.time()

        try:
            await request_func(request_id)
            end_time = time.time()

            metric = RequestMetrics(
                request_id=f"req_{request_id}",
                start_time=start_time,
                end_time=end_time,
                success=True,
                latency_ms=(end_time - start_time) * 1000,
            )
        except Exception as e:
            end_time = time.time()
            metric = RequestMetrics(
                request_id=f"req_{request_id}",
                start_time=start_time,
                end_time=end_time,
                success=False,
                latency_ms=(end_time - start_time) * 1000,
                error=str(e),
            )

        self.request_metrics.append(metric)
        return metric

    def _get_load_generator(self, config: LoadTestConfig):
        """Получить функцию-генератор нагрузки для паттерна"""

        if config.pattern == LoadPattern.CONSTANT:
            return lambda elapsed: config.initial_load

        elif config.pattern == LoadPattern.RAMP:

            def ramp_load(elapsed):
                progress = min(elapsed / config.ramp_duration_seconds, 1.0)
                return (
                    config.initial_load
                    + (config.max_load - config.initial_load) * progress
                )

            return ramp_load

        elif config.pattern == LoadPattern.SPIKE:

            def spike_load(elapsed):
                # Каждые 30 секунд создается всплеск
                cycle = elapsed % 30
                if 10 < cycle < 15:  # Всплеск в секундах 10-15
                    return config.max_load
                else:
                    return config.initial_load

            return spike_load

        elif config.pattern == LoadPattern.WAVE:

            def wave_load(elapsed):
                # Волновая нагрузка с периодом 20 секунд
                import math

                wave = math.sin((elapsed / 20.0) * 2 * math.pi)
                normalized_wave = (wave + 1) / 2  # Нормализовать в диапазон [0, 1]
                return (
                    config.initial_load
                    + (config.max_load - config.initial_load) * normalized_wave
                )

            return wave_load

        elif config.pattern == LoadPattern.STRESS:

            def stress_load(elapsed):
                # Линейный рост до отказа
                return config.initial_load + (elapsed / config.duration_seconds) * (
                    config.max_load - config.initial_load
                )

            return stress_load

        return lambda elapsed: config.initial_load

    def _calculate_results(
        self, config: LoadTestConfig, test_duration: float, total_requests: int
    ) -> LoadTestResults:
        """Вычислить результаты теста"""

        successful = [m for m in self.request_metrics if m.success]
        failed = [m for m in self.request_metrics if not m.success]

        latencies = [m.latency_ms for m in successful]

        if not latencies:
            latencies = [0]

        latencies_sorted = sorted(latencies)

        return LoadTestResults(
            test_name=config.name,
            pattern=config.pattern,
            total_requests=total_requests,
            successful_requests=len(successful),
            failed_requests=len(failed),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            avg_latency_ms=statistics.mean(latencies),
            p50_latency_ms=latencies_sorted[len(latencies_sorted) // 2],
            p95_latency_ms=latencies_sorted[int(len(latencies_sorted) * 0.95)],
            p99_latency_ms=latencies_sorted[int(len(latencies_sorted) * 0.99)],
            throughput_rps=total_requests / test_duration,
            test_duration_seconds=test_duration,
            error_rate=len(failed) / total_requests if total_requests > 0 else 0,
        )


class SystemPerformanceBenchmark:
    """
    Выполняет микробенчмарки для критических операций.
    """

    def __init__(self):
        self.benchmark_results: Dict[str, Dict[str, float]] = {}

    async def benchmark_operation(
        self, operation_name: str, operation_func: Callable, iterations: int = 1000
    ) -> Dict[str, float]:
        """
        Выполнить бенчмарк операции.

        Args:
            operation_name: Название операции
            operation_func: Асинхронная функция для бенчмарка
            iterations: Количество итераций

        Returns:
            Словарь с результатами: min, max, avg, p95, p99
        """
        logger.info(f"⏱️  Бенчмарк операции: {operation_name} ({iterations} итераций)")

        times = []

        for _ in range(iterations):
            start = time.time()
            try:
                await operation_func()
                duration = (time.time() - start) * 1000  # Преобразовать в миллисекунды
                times.append(duration)
            except Exception as e:
                logger.error(f"Ошибка при бенчмарке {operation_name}: {e}")

        times_sorted = sorted(times)

        results = {
            "min_ms": min(times) if times else 0,
            "max_ms": max(times) if times else 0,
            "avg_ms": statistics.mean(times) if times else 0,
            "p95_ms": times_sorted[int(len(times) * 0.95)] if times else 0,
            "p99_ms": times_sorted[int(len(times) * 0.99)] if times else 0,
            "iterations": iterations,
        }

        self.benchmark_results[operation_name] = results

        logger.info(f"   Среднее: {results['avg_ms']:.3f}ms")
        logger.info(f"   P95: {results['p95_ms']:.3f}ms")
        logger.info(f"   P99: {results['p99_ms']:.3f}ms")

        return results

    def get_benchmark_summary(self) -> Dict[str, Any]:
        """Получить сводку всех бенчмарков"""
        return {
            "total_benchmarks": len(self.benchmark_results),
            "benchmarks": self.benchmark_results,
        }


class SLOValidator:
    """
    Проверяет соответствие результатов требуемым Service Level Objectives (SLO).
    """

    def __init__(self):
        self.slo_definitions: Dict[str, Dict[str, float]] = {
            "api_response": {
                "p99_latency_ms": 100,  # P99 должен быть < 100ms
                "error_rate": 0.001,  # Ошибки < 0.1%
                "min_throughput_rps": 100,  # Минимум 100 RPS
            },
            "database": {
                "p99_latency_ms": 50,
                "error_rate": 0.0001,
                "min_throughput_rps": 1000,
            },
            "mesh_communication": {
                "p99_latency_ms": 200,
                "error_rate": 0.01,
                "min_throughput_rps": 50,
            },
        }

    def validate_results(
        self, results: LoadTestResults, slo_name: str = None
    ) -> Tuple[bool, List[str]]:
        """
        Проверить результаты против SLO.

        Returns:
            Кортеж (passed, violations)
        """
        if slo_name is None:
            slo_name = "api_response"

        slo = self.slo_definitions.get(slo_name)
        if not slo:
            return False, [f"SLO не найден: {slo_name}"]

        violations = []

        # Проверить P99 задержку
        if results.p99_latency_ms > slo["p99_latency_ms"]:
            violations.append(
                f"P99 задержка {results.p99_latency_ms:.2f}ms > {slo['p99_latency_ms']}ms"
            )

        # Проверить процент ошибок
        if results.error_rate > slo["error_rate"]:
            violations.append(
                f"Процент ошибок {results.error_rate:.4f} > {slo['error_rate']:.4f}"
            )

        # Проверить пропускную способность
        if results.throughput_rps < slo["min_throughput_rps"]:
            violations.append(
                f"Пропускная способность {results.throughput_rps:.2f} RPS < {slo['min_throughput_rps']} RPS"
            )

        passed = len(violations) == 0

        if passed:
            logger.info(f"✅ SLO выполнены: {slo_name}")
        else:
            logger.warning(f"⚠️  Нарушения SLO ({slo_name}):")
            for violation in violations:
                logger.warning(f"   - {violation}")

        return passed, violations

    def set_custom_slo(self, slo_name: str, slo_config: Dict[str, float]) -> None:
        """Установить пользовательское SLO"""
        self.slo_definitions[slo_name] = slo_config
        logger.info(f"Установлено пользовательское SLO: {slo_name}")


def compare_load_tests(
    results1: LoadTestResults, results2: LoadTestResults
) -> Dict[str, float]:
    """
    Сравнить результаты двух нагрузочных тестов.

    Returns:
        Словарь с процентами изменения метрик
    """
    return {
        "latency_change_percent": (
            (
                (results2.avg_latency_ms - results1.avg_latency_ms)
                / results1.avg_latency_ms
                * 100
            )
            if results1.avg_latency_ms > 0
            else 0
        ),
        "throughput_change_percent": (
            (
                (results2.throughput_rps - results1.throughput_rps)
                / results1.throughput_rps
                * 100
            )
            if results1.throughput_rps > 0
            else 0
        ),
        "error_rate_change_percent": (
            ((results2.error_rate - results1.error_rate) / results1.error_rate * 100)
            if results1.error_rate > 0
            else 0
        ),
    }

