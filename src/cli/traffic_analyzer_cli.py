#!/usr/bin/env python3
"""
CLI для анализа и тестирования Traffic Shaping.
Позволяет проверить как выглядит трафик после шейпинга.
"""
import argparse
import sys

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.network.obfuscation.traffic_shaping import (TRAFFIC_PROFILES,
                                                     TrafficAnalyzer,
                                                     TrafficProfile,
                                                     TrafficShaper)


def cmd_list_profiles(args):
    """Показать все доступные профили."""
    print("\n📋 ДОСТУПНЫЕ ПРОФИЛИ TRAFFIC SHAPING\n")
    print("=" * 70)

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            print(f"\n  {profile.value}")
            print("    Описание: Без шейпинга (passthrough)")
            continue

        params = TRAFFIC_PROFILES[profile]
        print(f"\n  {profile.value}")
        print(f"    Название: {params.name}")
        print(
            f"    Размер пакетов: {params.min_packet_size}-{params.max_packet_size} байт"
        )
        print(f"    Типичные размеры: {params.typical_packet_sizes}")
        print(f"    Интервал: {params.min_interval_ms}-{params.max_interval_ms} мс")
        print(
            f"    Burst: вероятность={params.burst_probability}, размер={params.burst_size}"
        )
        print(f"    Паддинг до: {params.pad_to_size or 'переменный'}")

    print("\n" + "=" * 70)


def cmd_simulate(args):
    """Симулировать шейпинг трафика."""
    try:
        profile = TrafficProfile(args.profile)
    except ValueError:
        print(f"❌ Неизвестный профиль: {args.profile}")
        return 1

    shaper = TrafficShaper(profile)
    analyzer = TrafficAnalyzer()

    print("\n🔄 СИМУЛЯЦИЯ TRAFFIC SHAPING")
    print(f"   Профиль: {profile.value}")
    print(f"   Пакетов: {args.packets}")
    print(f"   Размер данных: {args.size} байт")
    print("=" * 70)

    # Генерируем тестовые данные
    test_data = bytes([i % 256 for i in range(args.size)])

    total_original = 0
    total_shaped = 0
    delays = []

    print(
        f"\n{'#':>4} | {'Оригинал':>10} | {'После':>10} | {'Паддинг':>10} | {'Задержка':>10}"
    )
    print("-" * 60)

    for i in range(args.packets):
        shaped = shaper.shape_packet(test_data)
        delay = shaper.get_send_delay()

        original_size = len(test_data)
        shaped_size = len(shaped)
        padding = shaped_size - original_size - 2  # -2 для length prefix

        total_original += original_size
        total_shaped += shaped_size
        delays.append(delay)

        analyzer.record_packet(shaped_size)

        if args.verbose or i < 10 or i == args.packets - 1:
            print(
                f"{i+1:>4} | {original_size:>10} | {shaped_size:>10} | {padding:>10} | {delay*1000:>8.2f}ms"
            )
        elif i == 10:
            print(f"{'...':>4} | {'...':>10} | {'...':>10} | {'...':>10} | {'...':>10}")

        # Проверяем roundtrip
        unshaped = shaper.unshape_packet(shaped)
        if unshaped != test_data:
            print(f"⚠️  ОШИБКА: данные повреждены на пакете {i+1}")

    # Статистика
    stats = analyzer.get_statistics()
    avg_delay = sum(delays) / len(delays) if delays else 0

    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА")
    print(f"   Всего оригинальных байт: {total_original}")
    print(f"   Всего после шейпинга: {total_shaped}")
    print(f"   Overhead: {(total_shaped - total_original) / total_original * 100:.1f}%")
    print(f"   Средний размер пакета: {stats['avg_size']:.0f} байт")
    print(f"   Средняя задержка: {avg_delay * 1000:.2f} мс")
    print(f"   Общее время передачи: {sum(delays):.2f} сек")
    print(
        f"   Эффективный throughput: {total_shaped / sum(delays) / 1024:.2f} KB/s"
        if sum(delays) > 0
        else ""
    )

    return 0


def cmd_compare(args):
    """Сравнить профили."""
    print("\n⚖️  СРАВНЕНИЕ ПРОФИЛЕЙ TRAFFIC SHAPING\n")

    test_sizes = [64, 256, 512, 1024, 1400]

    print(f"{'Профиль':<20} | ", end="")
    for size in test_sizes:
        print(f"{size}B -> ", end="")
    print()
    print("-" * 100)

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue

        shaper = TrafficShaper(profile)
        print(f"{profile.value:<20} | ", end="")

        for size in test_sizes:
            data = bytes(size)
            shaped = shaper.shape_packet(data)
            print(f"{len(shaped):>4}B   ", end="")

        print()

    print("\n" + "-" * 100)
    print("\n📈 ЗАДЕРЖКИ (среднее за 100 итераций):\n")

    print(
        f"{'Профиль':<20} | {'Мин':<10} | {'Макс':<10} | {'Среднее':<10} | {'Burst':<10}"
    )
    print("-" * 70)

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue

        shaper = TrafficShaper(profile)
        delays = [shaper.get_send_delay() * 1000 for _ in range(100)]

        print(
            f"{profile.value:<20} | {min(delays):<10.1f} | {max(delays):<10.1f} | {sum(delays)/len(delays):<10.1f} | {TRAFFIC_PROFILES[profile].burst_probability:<10.0%}"
        )

    return 0


def cmd_detect(args):
    """Анализ файла с захваченными размерами пакетов для определения профиля."""
    print("\n🔍 ДЕТЕКТОР ПРОФИЛЯ ТРАФИКА")
    print("   (Определяет какому профилю соответствует трафик)\n")

    # Читаем размеры из stdin или файла
    if args.file:
        with open(args.file) as f:
            sizes = [int(line.strip()) for line in f if line.strip().isdigit()]
    else:
        print("Введите размеры пакетов (по одному на строку, Ctrl+D для завершения):")
        sizes = []
        try:
            for line in sys.stdin:
                if line.strip().isdigit():
                    sizes.append(int(line.strip()))
        except EOFError:
            pass

    if not sizes:
        print("❌ Нет данных для анализа")
        return 1

    print(f"\nАнализируем {len(sizes)} пакетов...\n")

    # Анализ
    avg_size = sum(sizes) / len(sizes)
    min_size = min(sizes)
    max_size = max(sizes)

    # Подсчёт совпадений с профилями
    scores = {}

    for profile in TrafficProfile:
        if profile == TrafficProfile.NONE:
            continue

        params = TRAFFIC_PROFILES[profile]
        score = 0

        # Проверяем попадание в диапазон
        in_range = sum(
            1 for s in sizes if params.min_packet_size <= s <= params.max_packet_size
        )
        score += in_range / len(sizes) * 50

        # Проверяем типичные размеры
        typical_matches = sum(1 for s in sizes if s in params.typical_packet_sizes)
        score += typical_matches / len(sizes) * 30

        # Проверяем pad_to_size
        if params.pad_to_size:
            pad_matches = sum(
                1
                for s in sizes
                if s == params.pad_to_size or s == params.pad_to_size + 2
            )
            score += pad_matches / len(sizes) * 20

        scores[profile] = score

    # Сортируем по score
    sorted_profiles = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА:\n")
    print(f"   Всего пакетов: {len(sizes)}")
    print(f"   Размер: min={min_size}, max={max_size}, avg={avg_size:.0f}")
    print()

    print("🎯 ВЕРОЯТНЫЕ ПРОФИЛИ:\n")
    for profile, score in sorted_profiles[:3]:
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"   {profile.value:<20} [{bar}] {score:.1f}%")

    best_profile = sorted_profiles[0][0]
    print(f"\n✅ Наиболее вероятный профиль: {best_profile.value}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="CLI для анализа Traffic Shaping x0tta6bl4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Показать все профили
  %(prog)s list

  # Симулировать video_streaming с 100 пакетами
  %(prog)s simulate -p video_streaming -n 100

  # Сравнить все профили
  %(prog)s compare

  # Определить профиль по размерам пакетов
  %(prog)s detect -f packet_sizes.txt
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # list
    list_parser = subparsers.add_parser("list", help="Показать все профили")
    list_parser.set_defaults(func=cmd_list_profiles)

    # simulate
    sim_parser = subparsers.add_parser("simulate", help="Симулировать шейпинг")
    sim_parser.add_argument(
        "-p",
        "--profile",
        required=True,
        choices=[p.value for p in TrafficProfile],
        help="Профиль трафика",
    )
    sim_parser.add_argument(
        "-n", "--packets", type=int, default=20, help="Количество пакетов (default: 20)"
    )
    sim_parser.add_argument(
        "-s",
        "--size",
        type=int,
        default=256,
        help="Размер данных в байтах (default: 256)",
    )
    sim_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Показать все пакеты"
    )
    sim_parser.set_defaults(func=cmd_simulate)

    # compare
    cmp_parser = subparsers.add_parser("compare", help="Сравнить профили")
    cmp_parser.set_defaults(func=cmd_compare)

    # detect
    det_parser = subparsers.add_parser("detect", help="Определить профиль по трафику")
    det_parser.add_argument("-f", "--file", help="Файл с размерами пакетов")
    det_parser.set_defaults(func=cmd_detect)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
