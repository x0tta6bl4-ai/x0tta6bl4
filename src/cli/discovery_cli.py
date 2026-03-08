#!/usr/bin/env python3
"""
CLI для Mesh Discovery.
Обнаружение узлов в локальной сети.
"""
import argparse
import asyncio
import signal
import sys
import uuid

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.network.discovery import MeshDiscovery, PeerInfo


async def run_discovery(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"

    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht,
    )

    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
        services = ", ".join(peer.services)
        print(f"🟢 НАЙДЕН: {peer.node_id}")
        print(f"   Адреса: {addrs}")
        print(f"   Сервисы: {services}")
        print()

    @discovery.on_peer_lost
    async def on_lost(peer: PeerInfo):
        print(f"🔴 ПОТЕРЯН: {peer.node_id}")
        print()

    await discovery.start()

    print("=" * 60)
    print("🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")

    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)

            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(
                        f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}"
                    )
                print()

    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def scan_network(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"

    discovery = MeshDiscovery(
        node_id=node_id, service_port=args.port, enable_multicast=True, enable_dht=False
    )

    found_peers = []

    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)

    await discovery.start()

    print(f"🔍 Сканирование сети ({args.timeout} сек)...")

    await asyncio.sleep(args.timeout)

    await discovery.stop()

    print("\n" + "=" * 60)
    print("📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)

    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")

        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(peer.services)
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Mesh Discovery CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument(
        "--services", default="mesh", help="Сервисы (через запятую)"
    )
    run_parser.add_argument(
        "--no-multicast", action="store_true", help="Отключить multicast"
    )
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument(
        "--interval", type=float, default=10, help="Интервал статистики"
    )
    run_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Подробный вывод"
    )

    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument(
        "--timeout", type=float, default=5, help="Таймаут сканирования"
    )
    scan_parser.add_argument("--port", type=int, default=5000, help="Порт")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Обработка Ctrl+C
    loop = asyncio.new_event_loop()

    def signal_handler():
        for task in asyncio.all_tasks(loop):
            task.cancel()

    try:
        if args.command == "run":
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
