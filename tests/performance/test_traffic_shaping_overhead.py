"""
Бенчмарк производительности Traffic Shaping.
Измеряет overhead для каждого профиля трафика.
"""

import statistics
import sys
import time
from typing import Dict, List

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.network.obfuscation.traffic_shaping import (TRAFFIC_PROFILES,
                                                     TrafficAnalyzer,
                                                     TrafficProfile,
                                                     TrafficShaper)


def benchmark_shaping(profile: TrafficProfile, iterations: int = 10000) -> Dict:
    """Бенчмарк шейпинга для одного профиля."""
    shaper = TrafficShaper(profile)

    # Тестовые данные разных размеров
    test_data_small = b"x" * 50
    test_data_medium = b"x" * 500
    test_data_large = b"x" * 1400

    results = {
        "profile": profile.value,
        "iterations": iterations,
        "small_50b": {},
        "medium_500b": {},
        "large_1400b": {},
    }

    for name, data in [
        ("small_50b", test_data_small),
        ("medium_500b", test_data_medium),
        ("large_1400b", test_data_large),
    ]:
        # Замер shape_packet
        shape_times = []
        shaped_sizes = []

        for _ in range(iterations):
            start = time.perf_counter()
            shaped = shaper.shape_packet(data)
            elapsed = time.perf_counter() - start
            shape_times.append(elapsed)
            shaped_sizes.append(len(shaped))

        # Замер unshape_packet
        unshape_times = []
        shaped_sample = shaper.shape_packet(data)

        for _ in range(iterations):
            start = time.perf_counter()
            _ = shaper.unshape_packet(shaped_sample)
            elapsed = time.perf_counter() - start
            unshape_times.append(elapsed)

        results[name] = {
            "shape_avg_ms": statistics.mean(shape_times) * 1000,
            "shape_p99_ms": sorted(shape_times)[int(iterations * 0.99)] * 1000,
            "unshape_avg_ms": statistics.mean(unshape_times) * 1000,
            "unshape_p99_ms": sorted(unshape_times)[int(iterations * 0.99)] * 1000,
            "original_size": len(data),
            "shaped_size": int(statistics.mean(shaped_sizes)),
            "padding_overhead": int(statistics.mean(shaped_sizes)) - len(data),
            "overhead_percent": (int(statistics.mean(shaped_sizes)) - len(data))
            / len(data)
            * 100,
        }

    return results


def benchmark_delay_generation(
    profile: TrafficProfile, iterations: int = 10000
) -> Dict:
    """Бенчмарк генерации задержек."""
    shaper = TrafficShaper(profile)

    delays = []
    gen_times = []

    for _ in range(iterations):
        start = time.perf_counter()
        delay = shaper.get_send_delay()
        elapsed = time.perf_counter() - start
        delays.append(delay)
        gen_times.append(elapsed)

    return {
        "profile": profile.value,
        "delay_avg_ms": statistics.mean(delays) * 1000,
        "delay_min_ms": min(delays) * 1000,
        "delay_max_ms": max(delays) * 1000,
        "delay_stdev_ms": statistics.stdev(delays) * 1000 if len(delays) > 1 else 0,
        "generation_time_avg_us": statistics.mean(gen_times) * 1_000_000,
    }


def benchmark_analyzer(iterations: int = 10000) -> Dict:
    """Бенчмарк TrafficAnalyzer."""
    analyzer = TrafficAnalyzer()

    # Замер record_packet
    record_times = []
    for i in range(iterations):
        size = 100 + (i % 1000)
        start = time.perf_counter()
        analyzer.record_packet(size)
        elapsed = time.perf_counter() - start
        record_times.append(elapsed)

    # Замер get_statistics
    stats_times = []
    for _ in range(1000):
        start = time.perf_counter()
        _ = analyzer.get_statistics()
        elapsed = time.perf_counter() - start
        stats_times.append(elapsed)

    return {
        "record_packet_avg_us": statistics.mean(record_times) * 1_000_000,
        "record_packet_p99_us": sorted(record_times)[int(len(record_times) * 0.99)]
        * 1_000_000,
        "get_statistics_avg_us": statistics.mean(stats_times) * 1_000_000,
        "packets_tracked": iterations,
    }


def print_results(results: Dict):
    """Красивый вывод результатов."""
    print(f"\n{'='*60}")
    print(f"Профиль: {results['profile']}")
    print(f"{'='*60}")

    for size_key in ["small_50b", "medium_500b", "large_1400b"]:
        if size_key not in results:
            continue
        r = results[size_key]
        print(f"\n  {size_key}:")
        print(
            f"    Shape:   avg={r['shape_avg_ms']:.4f}ms, p99={r['shape_p99_ms']:.4f}ms"
        )
        print(
            f"    Unshape: avg={r['unshape_avg_ms']:.4f}ms, p99={r['unshape_p99_ms']:.4f}ms"
        )
        print(
            f"    Размер:  {r['original_size']}B -> {r['shaped_size']}B (+{r['padding_overhead']}B, {r['overhead_percent']:.1f}%)"
        )


def main():
    print("=" * 70)
    print("БЕНЧМАРК TRAFFIC SHAPING - x0tta6bl4")
    print("=" * 70)
    print(f"Тестируем {len(TrafficProfile)} профилей...")

    iterations = 10000
    all_results = {}

    # Бенчмарк каждого профиля
    for profile in TrafficProfile:
        print(f"\nТестирую профиль: {profile.value}...")
        results = benchmark_shaping(profile, iterations)
        all_results[profile.value] = results
        print_results(results)

    # Бенчмарк задержек
    print("\n" + "=" * 70)
    print("БЕНЧМАРК ГЕНЕРАЦИИ ЗАДЕРЖЕК")
    print("=" * 70)

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue
        delay_results = benchmark_delay_generation(profile)
        print(f"\n{profile.value}:")
        print(f"  Средняя задержка: {delay_results['delay_avg_ms']:.2f}ms")
        print(
            f"  Диапазон: {delay_results['delay_min_ms']:.2f}ms - {delay_results['delay_max_ms']:.2f}ms"
        )
        print(f"  Время генерации: {delay_results['generation_time_avg_us']:.2f}μs")

    # Бенчмарк анализатора
    print("\n" + "=" * 70)
    print("БЕНЧМАРК TRAFFIC ANALYZER")
    print("=" * 70)

    analyzer_results = benchmark_analyzer()
    print(
        f"\n  record_packet: avg={analyzer_results['record_packet_avg_us']:.2f}μs, p99={analyzer_results['record_packet_p99_us']:.2f}μs"
    )
    print(f"  get_statistics: avg={analyzer_results['get_statistics_avg_us']:.2f}μs")
    print(f"  Пакетов отслежено: {analyzer_results['packets_tracked']}")

    # Сводка
    print("\n" + "=" * 70)
    print("СВОДКА ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 70)

    print("\n┌─────────────────────┬────────────┬────────────┬──────────────┐")
    print("│ Профиль             │ Shape (ms) │ Overhead % │ Задержка (ms)│")
    print("├─────────────────────┼────────────┼────────────┼──────────────┤")

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue
        r = all_results[profile.value]["medium_500b"]
        delay = benchmark_delay_generation(profile, 1000)
        print(
            f"│ {profile.value:19} │ {r['shape_avg_ms']:10.4f} │ {r['overhead_percent']:10.1f} │ {delay['delay_avg_ms']:12.2f} │"
        )

    print("└─────────────────────┴────────────┴────────────┴──────────────┘")

    # Рекомендации
    print("\n" + "=" * 70)
    print("РЕКОМЕНДАЦИИ ПО ВЫБОРУ ПРОФИЛЯ")
    print("=" * 70)
    print(
        """
  • video_streaming - Лучший для обхода DPI, высокий throughput
  • voice_call      - Минимальный overhead, регулярный timing
  • web_browsing    - Гибкий, подходит для общего использования
  • file_download   - Максимальный throughput, большие burst
  • gaming          - Минимальная латентность, маленькие пакеты
    """
    )


if __name__ == "__main__":
    main()
