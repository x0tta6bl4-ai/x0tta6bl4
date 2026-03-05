"""
Бенчмарк латентности UDP транспорта.
Измеряет RTT, jitter, throughput для разных профилей.
"""

import asyncio
import statistics
import sys
import time
from typing import Dict

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.network.transport.udp_shaped import (ShapedUDPTransport)


async def benchmark_packet_processing(iterations: int = 10000) -> Dict:
    """Бенчмарк обработки пакетов (без сети)."""

    results = {}

    profiles = ["none", "gaming", "voice_call", "video_streaming"]

    for profile in profiles:
        transport = ShapedUDPTransport(
            traffic_profile=profile, obfuscation="xor", obfuscation_key="bench-key"
        )

        test_data = b"benchmark payload data" * 5  # ~110 bytes

        # Замер prepare
        prepare_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            transport._prepare_packet(test_data)
            elapsed = time.perf_counter() - start
            prepare_times.append(elapsed)

        # Замер unpack
        sample_packet = transport._prepare_packet(test_data)
        unpack_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            _ = transport._unpack_packet(sample_packet)
            elapsed = time.perf_counter() - start
            unpack_times.append(elapsed)

        results[profile] = {
            "prepare_avg_us": statistics.mean(prepare_times) * 1_000_000,
            "prepare_p99_us": sorted(prepare_times)[int(iterations * 0.99)] * 1_000_000,
            "unpack_avg_us": statistics.mean(unpack_times) * 1_000_000,
            "unpack_p99_us": sorted(unpack_times)[int(iterations * 0.99)] * 1_000_000,
            "total_avg_us": (
                statistics.mean(prepare_times) + statistics.mean(unpack_times)
            )
            * 1_000_000,
            "packet_size": len(sample_packet),
        }

    return results


async def benchmark_loopback_rtt(packets: int = 1000) -> Dict:
    """Бенчмарк RTT через loopback."""

    results = {}
    profiles = ["none", "gaming", "voice_call"]

    for profile in profiles:
        received_times: Dict[int, float] = {}
        sent_times: Dict[int, float] = {}

        transport = ShapedUDPTransport(
            local_port=0,
            traffic_profile=profile,
            obfuscation="xor",
            obfuscation_key="rtt-test",
        )

        @transport.on_receive
        async def handler(data: bytes, address):
            seq = int.from_bytes(data[:4], "big")
            received_times[seq] = time.perf_counter()

        await transport.start()
        local_addr = ("127.0.0.1", transport.local_port)

        # Отправляем пакеты
        for i in range(packets):
            payload = i.to_bytes(4, "big") + b"x" * 100
            sent_times[i] = time.perf_counter()
            await transport.send_to(payload, local_addr)

            # Небольшая пауза чтобы не перегрузить
            if i % 100 == 0:
                await asyncio.sleep(0.01)

        # Ждём все пакеты
        await asyncio.sleep(0.5)

        await transport.stop()

        # Вычисляем RTT
        rtts = []
        for seq in sent_times:
            if seq in received_times:
                rtt = (received_times[seq] - sent_times[seq]) * 1000  # ms
                rtts.append(rtt)

        if rtts:
            results[profile] = {
                "packets_sent": packets,
                "packets_received": len(rtts),
                "packet_loss_percent": (1 - len(rtts) / packets) * 100,
                "rtt_avg_ms": statistics.mean(rtts),
                "rtt_min_ms": min(rtts),
                "rtt_max_ms": max(rtts),
                "rtt_p50_ms": sorted(rtts)[len(rtts) // 2],
                "rtt_p99_ms": (
                    sorted(rtts)[int(len(rtts) * 0.99)]
                    if len(rtts) > 100
                    else max(rtts)
                ),
                "jitter_ms": statistics.stdev(rtts) if len(rtts) > 1 else 0,
            }
        else:
            results[profile] = {"error": "no packets received"}

    return results


async def benchmark_throughput(duration_seconds: float = 2.0) -> Dict:
    """Бенчмарк throughput."""

    results = {}

    for profile in ["none", "gaming", "file_download"]:
        received_bytes = 0
        received_packets = 0

        transport = ShapedUDPTransport(
            local_port=0,
            traffic_profile=profile,
            obfuscation="none",  # Без обфускации для чистого throughput
        )

        @transport.on_receive
        async def handler(data: bytes, address):
            nonlocal received_bytes, received_packets
            received_bytes += len(data)
            received_packets += 1

        await transport.start()
        local_addr = ("127.0.0.1", transport.local_port)

        # Отправляем максимально быстро
        payload = b"x" * 1200  # ~MTU size
        start_time = time.perf_counter()
        sent_packets = 0
        sent_bytes = 0

        while time.perf_counter() - start_time < duration_seconds:
            await transport.send_to(payload, local_addr)
            sent_packets += 1
            sent_bytes += len(payload)

            # Yield чтобы receiver мог работать
            if sent_packets % 100 == 0:
                await asyncio.sleep(0)

        elapsed = time.perf_counter() - start_time

        # Ждём последние пакеты
        await asyncio.sleep(0.2)

        await transport.stop()

        results[profile] = {
            "duration_seconds": elapsed,
            "sent_packets": sent_packets,
            "sent_bytes": sent_bytes,
            "received_packets": received_packets,
            "received_bytes": received_bytes,
            "throughput_pps": sent_packets / elapsed,
            "throughput_mbps": (sent_bytes * 8) / elapsed / 1_000_000,
            "packet_loss_percent": (
                (1 - received_packets / sent_packets) * 100 if sent_packets > 0 else 0
            ),
        }

    return results


def print_processing_results(results: Dict):
    """Вывод результатов обработки пакетов."""
    print("\n" + "=" * 70)
    print("📦 ОБРАБОТКА ПАКЕТОВ (prepare + unpack)")
    print("=" * 70)

    print(
        f"\n{'Профиль':<20} {'Prepare (μs)':<15} {'Unpack (μs)':<15} {'Total (μs)':<15} {'Размер':<10}"
    )
    print("-" * 70)

    for profile, r in results.items():
        print(
            f"{profile:<20} {r['prepare_avg_us']:<15.2f} {r['unpack_avg_us']:<15.2f} {r['total_avg_us']:<15.2f} {r['packet_size']:<10}"
        )


def print_rtt_results(results: Dict):
    """Вывод результатов RTT."""
    print("\n" + "=" * 70)
    print("🏓 LOOPBACK RTT (Round-Trip Time)")
    print("=" * 70)

    print(
        f"\n{'Профиль':<15} {'RTT avg':<12} {'RTT p50':<12} {'RTT p99':<12} {'Jitter':<12} {'Loss':<10}"
    )
    print("-" * 70)

    for profile, r in results.items():
        if "error" in r:
            print(f"{profile:<15} ERROR: {r['error']}")
        else:
            print(
                f"{profile:<15} {r['rtt_avg_ms']:<12.3f} {r['rtt_p50_ms']:<12.3f} {r['rtt_p99_ms']:<12.3f} {r['jitter_ms']:<12.3f} {r['packet_loss_percent']:<10.1f}%"
            )


def print_throughput_results(results: Dict):
    """Вывод результатов throughput."""
    print("\n" + "=" * 70)
    print("🚀 THROUGHPUT")
    print("=" * 70)

    print(
        f"\n{'Профиль':<15} {'PPS':<15} {'Mbps':<12} {'Отправлено':<15} {'Получено':<15} {'Loss':<10}"
    )
    print("-" * 70)

    for profile, r in results.items():
        print(
            f"{profile:<15} {r['throughput_pps']:<15.0f} {r['throughput_mbps']:<12.2f} {r['sent_packets']:<15} {r['received_packets']:<15} {r['packet_loss_percent']:<10.1f}%"
        )


async def main():
    print("=" * 70)
    print("🎮 БЕНЧМАРК UDP ТРАНСПОРТА - x0tta6bl4")
    print("   Оптимизирован для low-latency gaming/VoIP")
    print("=" * 70)

    # 1. Обработка пакетов
    print("\n⏳ Тестирую обработку пакетов...")
    processing_results = await benchmark_packet_processing(10000)
    print_processing_results(processing_results)

    # 2. RTT
    print("\n⏳ Тестирую RTT через loopback...")
    rtt_results = await benchmark_loopback_rtt(500)
    print_rtt_results(rtt_results)

    # 3. Throughput
    print("\n⏳ Тестирую throughput...")
    throughput_results = await benchmark_throughput(2.0)
    print_throughput_results(throughput_results)

    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)

    gaming_proc = processing_results.get("gaming", {})
    gaming_rtt = rtt_results.get("gaming", {})

    print(
        f"""
    Gaming профиль:
    ├── Обработка пакета: {gaming_proc.get('total_avg_us', 0):.1f} μs
    ├── RTT (loopback): {gaming_rtt.get('rtt_avg_ms', 0):.3f} ms
    ├── Jitter: {gaming_rtt.get('jitter_ms', 0):.3f} ms
    └── Подходит для: FPS, MOBA, Racing
    
    Рекомендации:
    • gaming - для игр (10-33ms интервал)
    • voice_call - для VoIP (строго 20ms)
    • video_streaming - для стриминга (bursts)
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
