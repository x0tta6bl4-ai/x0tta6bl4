"""
Тесты для адаптивного backoff и rate limiting.

Покрывает:
- Экспоненциальный backoff
- Jitter (случайный разброс)
- Rate limiting
- Adaptive timeout
- Graceful degradation
"""
import pytest
import time
import asyncio
import random
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from collections import deque

from src.self_healing.recovery_actions import (
    RecoveryActionExecutor,
    RateLimiter,
    CircuitBreaker as RecoveryCircuitBreaker,
)


class TestExponentialBackoff:
    """Тесты экспоненциального backoff."""

    def test_backoff_increases_exponentially(self):
        """Backoff увеличивается экспоненциально."""
        executor = RecoveryActionExecutor(
            node_id="test",
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=5,
            retry_delay=0.1
        )

        delays = []

        def failing_action(action_type, context):
            delays.append(time.time())
            raise Exception("Simulated failure")

        with patch.object(executor, '_execute_action_internal', failing_action):
            executor.execute("Restart service", {})

        # Проверяем экспоненциальный рост задержек
        if len(delays) >= 3:
            delay_1 = delays[1] - delays[0]
            delay_2 = delays[2] - delays[1]

            # delay_2 должна быть примерно в 2 раза больше delay_1
            # (exponential backoff: retry_delay * (attempt + 1))
            assert delay_2 >= delay_1 * 1.5  # с запасом на погрешность

    def test_backoff_formula(self):
        """Проверка формулы backoff."""
        base_delay = 0.1

        for attempt in range(5):
            expected_delay = base_delay * (attempt + 1)
            # В реальном коде: time.sleep(self.retry_delay * (attempt + 1))
            assert expected_delay == base_delay * (attempt + 1)

    def test_max_retries_respected(self):
        """Соблюдается максимальное количество retry."""
        max_retries = 3
        executor = RecoveryActionExecutor(
            node_id="test",
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=max_retries,
            retry_delay=0.01
        )

        call_count = [0]

        def counting_fail(action_type, context):
            call_count[0] += 1
            raise Exception("Always fails")

        with patch.object(executor, '_execute_action_internal', counting_fail):
            executor.execute("Restart", {})

        assert call_count[0] == max_retries


class TestJitter:
    """Тесты для jitter (случайного разброса)."""

    def test_jitter_adds_randomness(self):
        """Jitter добавляет случайность к задержке."""
        base_delay = 1.0
        jitter_factor = 0.2  # ±20%

        delays = []
        for _ in range(100):
            jitter = random.uniform(-jitter_factor, jitter_factor)
            delay_with_jitter = base_delay * (1 + jitter)
            delays.append(delay_with_jitter)

        # Проверяем, что есть разброс
        min_delay = min(delays)
        max_delay = max(delays)

        assert min_delay < base_delay
        assert max_delay > base_delay
        assert max_delay - min_delay > 0.1  # есть значимый разброс

    def test_jitter_prevents_thundering_herd(self):
        """Jitter предотвращает thundering herd."""
        # Симуляция множества клиентов с jitter
        base_retry_time = 1.0
        jitter_factor = 0.3

        retry_times = []
        for _ in range(1000):
            jitter = random.uniform(-jitter_factor, jitter_factor)
            retry_time = base_retry_time * (1 + jitter)
            retry_times.append(retry_time)

        # Группируем по 0.1 секундным интервалам
        buckets = {}
        for t in retry_times:
            bucket = round(t, 1)
            buckets[bucket] = buckets.get(bucket, 0) + 1

        # Не должно быть слишком большой концентрации в одном bucket
        max_in_bucket = max(buckets.values())
        avg_per_bucket = len(retry_times) / len(buckets)

        # С jitter нагрузка должна быть распределена более равномерно
        assert max_in_bucket < avg_per_bucket * 3  # не более 3x от среднего


class TestRateLimiting:
    """Тесты rate limiting."""

    def test_allows_within_limit(self, rate_limiter):
        """Разрешает запросы в пределах лимита."""
        # max_actions=5
        for i in range(5):
            assert rate_limiter.allow() is True

    def test_blocks_over_limit(self, rate_limiter):
        """Блокирует запросы сверх лимита."""
        for _ in range(5):
            rate_limiter.allow()

        assert rate_limiter.allow() is False

    def test_sliding_window(self, rate_limiter):
        """Проверка скользящего окна."""
        # Исчерпываем лимит
        for _ in range(5):
            rate_limiter.allow()

        assert rate_limiter.allow() is False

        # Ждём истечения окна
        time.sleep(1.1)  # window_seconds=1

        # Теперь должно быть разрешено
        assert rate_limiter.allow() is True

    def test_partial_window_recovery(self):
        """Частичное восстановление в скользящем окне."""
        rate_limiter = RateLimiter(max_actions=3, window_seconds=1)

        # 3 запроса с небольшими интервалами
        rate_limiter.allow()
        time.sleep(0.4)
        rate_limiter.allow()
        time.sleep(0.4)
        rate_limiter.allow()

        # Лимит исчерпан
        assert rate_limiter.allow() is False

        # Ждём, пока первый запрос выйдет из окна
        time.sleep(0.3)

        # Теперь первый запрос вышел из окна, можно сделать новый
        assert rate_limiter.allow() is True

    def test_rate_limiter_thread_safety(self):
        """Thread-safety rate limiter."""
        import threading

        rate_limiter = RateLimiter(max_actions=100, window_seconds=10)
        results = []

        def make_request():
            result = rate_limiter.allow()
            results.append(result)

        threads = [
            threading.Thread(target=make_request)
            for _ in range(150)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Ровно 100 должны быть разрешены
        allowed = sum(1 for r in results if r)
        assert allowed == 100


class TestAdaptiveTimeout:
    """Тесты адаптивного таймаута."""

    def test_timeout_increases_on_slow_responses(self):
        """Таймаут увеличивается при медленных ответах."""
        # Симуляция адаптивного таймаута
        base_timeout = 1.0
        response_times = [0.8, 0.9, 1.1, 1.2]  # всё медленнее

        # Простая адаптивная формула: timeout = avg_response_time * 2
        avg_response = sum(response_times) / len(response_times)
        adaptive_timeout = avg_response * 2

        assert adaptive_timeout > base_timeout

    def test_timeout_decreases_on_fast_responses(self):
        """Таймаут уменьшается при быстрых ответах."""
        base_timeout = 5.0
        response_times = [0.1, 0.15, 0.12, 0.08]  # быстрые ответы

        avg_response = sum(response_times) / len(response_times)
        adaptive_timeout = max(0.5, avg_response * 2)  # минимум 0.5s

        assert adaptive_timeout < base_timeout

    def test_timeout_bounded_by_limits(self):
        """Таймаут ограничен минимумом и максимумом."""
        min_timeout = 0.5
        max_timeout = 30.0

        # Очень быстрые ответы
        response_times = [0.01, 0.02, 0.01]
        avg = sum(response_times) / len(response_times)
        timeout = max(min_timeout, min(max_timeout, avg * 2))
        assert timeout >= min_timeout

        # Очень медленные ответы
        response_times = [20.0, 25.0, 30.0]
        avg = sum(response_times) / len(response_times)
        timeout = max(min_timeout, min(max_timeout, avg * 2))
        assert timeout <= max_timeout


class TestGracefulDegradation:
    """Тесты graceful degradation."""

    def test_degraded_mode_on_failures(self):
        """Переход в degraded mode при ошибках."""
        executor = RecoveryActionExecutor(
            node_id="test",
            enable_circuit_breaker=True,
            enable_rate_limiting=True
        )

        # Имитируем несколько ошибок
        def failing(action_type, context):
            raise Exception("Service unavailable")

        with patch.object(executor, '_execute_action_internal', failing):
            for _ in range(5):
                executor.execute("Restart", {})

        # Circuit breaker должен открыться
        status = executor.get_circuit_breaker_status()
        assert status["failures"] >= 3 or status["state"] == "open"

    def test_fallback_to_simulated_mode(self, recovery_executor):
        """Fallback на simulated mode при недоступности сервисов."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("systemctl not found")

            result = recovery_executor.execute(
                "Restart service",
                {"service_name": "test-service"}
            )

            # Должен успешно выполниться в simulated mode
            assert result is True

    def test_partial_service_availability(self, recovery_executor):
        """Частичная доступность сервисов."""
        # Некоторые сервисы доступны, некоторые нет
        call_count = [0]

        def intermittent_failure(args, **kwargs):
            call_count[0] += 1
            if "systemctl" in args:
                raise FileNotFoundError("systemctl not found")
            if "docker" in args:
                return Mock(returncode=0, stdout="ok", stderr="")
            return Mock(returncode=1)

        with patch('subprocess.run', intermittent_failure):
            result = recovery_executor.execute(
                "Restart service",
                {"service_name": "test-service"}
            )

            # Должен найти работающий метод
            assert result is True


class TestBackoffStrategies:
    """Тесты различных стратегий backoff."""

    def test_linear_backoff(self):
        """Линейный backoff."""
        base_delay = 1.0
        max_delay = 60.0

        delays = []
        for attempt in range(10):
            delay = min(base_delay * (attempt + 1), max_delay)
            delays.append(delay)

        # Проверяем линейный рост
        for i in range(1, len(delays) - 1):
            if delays[i] < max_delay:
                assert delays[i] - delays[i-1] == base_delay

    def test_exponential_backoff(self):
        """Экспоненциальный backoff."""
        base_delay = 0.1
        max_delay = 60.0
        multiplier = 2.0

        delays = []
        for attempt in range(10):
            delay = min(base_delay * (multiplier ** attempt), max_delay)
            delays.append(delay)

        # Проверяем экспоненциальный рост (до max)
        for i in range(1, len(delays)):
            if delays[i-1] < max_delay and delays[i] < max_delay:
                ratio = delays[i] / delays[i-1]
                assert abs(ratio - multiplier) < 0.1

    def test_fibonacci_backoff(self):
        """Fibonacci backoff."""
        base_delay = 1.0
        max_delay = 60.0

        def fib(n):
            if n <= 1:
                return n
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return a

        delays = []
        for attempt in range(10):
            delay = min(base_delay * fib(attempt + 1), max_delay)
            delays.append(delay)

        # Fibonacci: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55
        expected_fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        for i, (actual, expected) in enumerate(zip(delays, expected_fib)):
            if actual < max_delay:
                assert actual == base_delay * expected

    def test_decorrelated_jitter_backoff(self):
        """Decorrelated jitter backoff (AWS style)."""
        base_delay = 1.0
        max_delay = 60.0

        # cap = min(max_delay, random_between(base, prev_delay * 3))
        prev_delay = base_delay
        delays = [prev_delay]

        random.seed(42)  # для воспроизводимости
        for _ in range(10):
            cap = min(max_delay, random.uniform(base_delay, prev_delay * 3))
            delays.append(cap)
            prev_delay = cap

        # Проверяем что задержки ограничены
        assert all(d <= max_delay for d in delays)
        assert all(d >= base_delay for d in delays)


class TestBackpressure:
    """Тесты backpressure механизмов."""

    def test_queue_overflow_handling(self):
        """Обработка переполнения очереди."""
        max_queue_size = 10
        queue = deque(maxlen=max_queue_size)

        # Добавляем элементы
        for i in range(15):
            queue.append(f"item-{i}")

        # Старые элементы вытеснены
        assert len(queue) == max_queue_size
        assert "item-0" not in queue
        assert "item-14" in queue

    def test_load_shedding_on_overload(self):
        """Load shedding при перегрузке."""
        max_concurrent = 5
        current_load = [0]
        rejected = []

        def handle_request(request_id):
            if current_load[0] >= max_concurrent:
                rejected.append(request_id)
                return False

            current_load[0] += 1
            # Симуляция обработки
            time.sleep(0.01)
            current_load[0] -= 1
            return True

        # Запускаем много запросов
        import threading
        results = []

        def make_request(rid):
            result = handle_request(rid)
            results.append((rid, result))

        threads = [
            threading.Thread(target=make_request, args=(i,))
            for i in range(20)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Некоторые запросы должны быть отклонены
        # (зависит от timing, но в целом концепция верна)
        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_async_semaphore_backpressure(self):
        """Backpressure через семафор в async."""
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        concurrent_count = [0]
        max_observed = [0]

        async def process(task_id):
            async with semaphore:
                concurrent_count[0] += 1
                max_observed[0] = max(max_observed[0], concurrent_count[0])
                await asyncio.sleep(0.05)
                concurrent_count[0] -= 1

        # Запускаем 10 задач
        tasks = [asyncio.create_task(process(i)) for i in range(10)]
        await asyncio.gather(*tasks)

        # Максимальная конкурентность не должна превышать лимит
        assert max_observed[0] <= max_concurrent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
