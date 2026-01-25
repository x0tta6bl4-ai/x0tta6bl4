#!/usr/bin/env python3
"""
CLI для Mesh Discovery.
Обнаружение узлов в локальной сети.
"""
import argparse
import asyncio
import sys
import uuid
import signal

sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.network.discovery import MeshDiscovery, PeerInfo
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


async def x_run_discovery__mutmut_orig(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_1(args):
    """Запустить discovery."""
    node_id = None
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_2(args):
    """Запустить discovery."""
    node_id = args.node_id and f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_3(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:9]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_4(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = None
    
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_5(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=None,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_6(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=None,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_7(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=None,
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_8(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=None,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_9(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=None
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_10(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_11(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_12(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_13(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_14(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_15(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(None) if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_16(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split("XX,XX") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_17(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["XXmeshXX"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_18(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["MESH"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_19(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_20(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_21(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    
    print(None)
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_22(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    
    print("=" / 60)
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_23(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    
    print("XX=XX" * 60)
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_24(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    
    print("=" * 61)
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_25(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_26(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_27(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" / 60)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_28(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("XX=XX" * 60)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_29(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 61)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_30(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_31(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_32(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_33(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'XX✅XX' if not args.no_multicast else '❌'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_34(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if args.no_multicast else '❌'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_35(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else 'XX❌XX'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_36(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(None)
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_37(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'XX✅XX' if not args.no_dht else '❌'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_38(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if args.no_dht else '❌'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_39(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else 'XX❌XX'}")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_40(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print(None)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_41(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" / 60)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_42(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("XX=XX" * 60)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_43(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 61)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_44(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print(None)
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_45(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print("XX\nОжидание пиров... (Ctrl+C для выхода)\nXX")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_46(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print("\nожидание пиров... (ctrl+c для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_47(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print("\nОЖИДАНИЕ ПИРОВ... (CTRL+C ДЛЯ ВЫХОДА)\n")
    
    # Периодический вывод статистики
    try:
        while True:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_48(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
    print("=" * 60)
    print(f"   Node ID:    {node_id}")
    print(f"   Port:       {args.port}")
    print(f"   Multicast:  {'✅' if not args.no_multicast else '❌'}")
    print(f"   DHT:        {'✅' if not args.no_dht else '❌'}")
    print("=" * 60)
    print("\nОжидание пиров... (Ctrl+C для выхода)\n")
    
    # Периодический вывод статистики
    try:
        while False:
            await asyncio.sleep(args.interval)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_49(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
            await asyncio.sleep(None)
            
            peers = discovery.get_peers()
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_50(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
            
            peers = None
            if args.verbose:
                print(f"📊 Известно пиров: {len(peers)}")
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_51(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                print(None)
                for peer in peers:
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_52(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(None)
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_53(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[1] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_54(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else 'XX?XX'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ Discovery остановлен")


async def x_run_discovery__mutmut_55(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print(None)


async def x_run_discovery__mutmut_56(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("XX\n✅ Discovery остановленXX")


async def x_run_discovery__mutmut_57(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ discovery остановлен")


async def x_run_discovery__mutmut_58(args):
    """Запустить discovery."""
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        services=args.services.split(",") if args.services else ["mesh"],
        enable_multicast=not args.no_multicast,
        enable_dht=not args.no_dht
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
    print(f"🔍 MESH DISCOVERY")
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
                    print(f"   - {peer.node_id} @ {peer.addresses[0] if peer.addresses else '?'}")
                print()
                
    except asyncio.CancelledError:
        pass
    finally:
        await discovery.stop()
        print("\n✅ DISCOVERY ОСТАНОВЛЕН")

x_run_discovery__mutmut_mutants : ClassVar[MutantDict] = {
'x_run_discovery__mutmut_1': x_run_discovery__mutmut_1, 
    'x_run_discovery__mutmut_2': x_run_discovery__mutmut_2, 
    'x_run_discovery__mutmut_3': x_run_discovery__mutmut_3, 
    'x_run_discovery__mutmut_4': x_run_discovery__mutmut_4, 
    'x_run_discovery__mutmut_5': x_run_discovery__mutmut_5, 
    'x_run_discovery__mutmut_6': x_run_discovery__mutmut_6, 
    'x_run_discovery__mutmut_7': x_run_discovery__mutmut_7, 
    'x_run_discovery__mutmut_8': x_run_discovery__mutmut_8, 
    'x_run_discovery__mutmut_9': x_run_discovery__mutmut_9, 
    'x_run_discovery__mutmut_10': x_run_discovery__mutmut_10, 
    'x_run_discovery__mutmut_11': x_run_discovery__mutmut_11, 
    'x_run_discovery__mutmut_12': x_run_discovery__mutmut_12, 
    'x_run_discovery__mutmut_13': x_run_discovery__mutmut_13, 
    'x_run_discovery__mutmut_14': x_run_discovery__mutmut_14, 
    'x_run_discovery__mutmut_15': x_run_discovery__mutmut_15, 
    'x_run_discovery__mutmut_16': x_run_discovery__mutmut_16, 
    'x_run_discovery__mutmut_17': x_run_discovery__mutmut_17, 
    'x_run_discovery__mutmut_18': x_run_discovery__mutmut_18, 
    'x_run_discovery__mutmut_19': x_run_discovery__mutmut_19, 
    'x_run_discovery__mutmut_20': x_run_discovery__mutmut_20, 
    'x_run_discovery__mutmut_21': x_run_discovery__mutmut_21, 
    'x_run_discovery__mutmut_22': x_run_discovery__mutmut_22, 
    'x_run_discovery__mutmut_23': x_run_discovery__mutmut_23, 
    'x_run_discovery__mutmut_24': x_run_discovery__mutmut_24, 
    'x_run_discovery__mutmut_25': x_run_discovery__mutmut_25, 
    'x_run_discovery__mutmut_26': x_run_discovery__mutmut_26, 
    'x_run_discovery__mutmut_27': x_run_discovery__mutmut_27, 
    'x_run_discovery__mutmut_28': x_run_discovery__mutmut_28, 
    'x_run_discovery__mutmut_29': x_run_discovery__mutmut_29, 
    'x_run_discovery__mutmut_30': x_run_discovery__mutmut_30, 
    'x_run_discovery__mutmut_31': x_run_discovery__mutmut_31, 
    'x_run_discovery__mutmut_32': x_run_discovery__mutmut_32, 
    'x_run_discovery__mutmut_33': x_run_discovery__mutmut_33, 
    'x_run_discovery__mutmut_34': x_run_discovery__mutmut_34, 
    'x_run_discovery__mutmut_35': x_run_discovery__mutmut_35, 
    'x_run_discovery__mutmut_36': x_run_discovery__mutmut_36, 
    'x_run_discovery__mutmut_37': x_run_discovery__mutmut_37, 
    'x_run_discovery__mutmut_38': x_run_discovery__mutmut_38, 
    'x_run_discovery__mutmut_39': x_run_discovery__mutmut_39, 
    'x_run_discovery__mutmut_40': x_run_discovery__mutmut_40, 
    'x_run_discovery__mutmut_41': x_run_discovery__mutmut_41, 
    'x_run_discovery__mutmut_42': x_run_discovery__mutmut_42, 
    'x_run_discovery__mutmut_43': x_run_discovery__mutmut_43, 
    'x_run_discovery__mutmut_44': x_run_discovery__mutmut_44, 
    'x_run_discovery__mutmut_45': x_run_discovery__mutmut_45, 
    'x_run_discovery__mutmut_46': x_run_discovery__mutmut_46, 
    'x_run_discovery__mutmut_47': x_run_discovery__mutmut_47, 
    'x_run_discovery__mutmut_48': x_run_discovery__mutmut_48, 
    'x_run_discovery__mutmut_49': x_run_discovery__mutmut_49, 
    'x_run_discovery__mutmut_50': x_run_discovery__mutmut_50, 
    'x_run_discovery__mutmut_51': x_run_discovery__mutmut_51, 
    'x_run_discovery__mutmut_52': x_run_discovery__mutmut_52, 
    'x_run_discovery__mutmut_53': x_run_discovery__mutmut_53, 
    'x_run_discovery__mutmut_54': x_run_discovery__mutmut_54, 
    'x_run_discovery__mutmut_55': x_run_discovery__mutmut_55, 
    'x_run_discovery__mutmut_56': x_run_discovery__mutmut_56, 
    'x_run_discovery__mutmut_57': x_run_discovery__mutmut_57, 
    'x_run_discovery__mutmut_58': x_run_discovery__mutmut_58
}

def run_discovery(*args, **kwargs):
    result = _mutmut_trampoline(x_run_discovery__mutmut_orig, x_run_discovery__mutmut_mutants, args, kwargs)
    return result 

run_discovery.__signature__ = _mutmut_signature(x_run_discovery__mutmut_orig)
x_run_discovery__mutmut_orig.__name__ = 'x_run_discovery'


async def x_scan_network__mutmut_orig(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_1(args):
    """Одноразовое сканирование сети."""
    node_id = None
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_2(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:9]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_3(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = None
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_4(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=None,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_5(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=None,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_6(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=None,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_7(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=None
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_8(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_9(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_10(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_11(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_12(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=False,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_13(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=True
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_14(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = None
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_15(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(None)
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_16(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(None)
    
    await discovery.stop()
    
    print("\n" + "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_17(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print(None)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_18(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" - "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_19(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("XX\nXX" + "=" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_20(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "=" / 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_21(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "XX=XX" * 60)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_22(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
    )
    
    found_peers = []
    
    @discovery.on_peer_discovered
    async def on_found(peer: PeerInfo):
        found_peers.append(peer)
    
    await discovery.start()
    
    print(f"🔍 Сканирование сети ({args.timeout} сек)...")
    
    await asyncio.sleep(args.timeout)
    
    await discovery.stop()
    
    print("\n" + "=" * 61)
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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


async def x_scan_network__mutmut_23(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(None)
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


async def x_scan_network__mutmut_24(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print(None)
    
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


async def x_scan_network__mutmut_25(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" / 60)
    
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


async def x_scan_network__mutmut_26(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("XX=XX" * 60)
    
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


async def x_scan_network__mutmut_27(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 61)
    
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


async def x_scan_network__mutmut_28(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(None)
        
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


async def x_scan_network__mutmut_29(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(None, 1):
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


async def x_scan_network__mutmut_30(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, None):
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


async def x_scan_network__mutmut_31(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(1):
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


async def x_scan_network__mutmut_32(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, ):
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


async def x_scan_network__mutmut_33(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 2):
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


async def x_scan_network__mutmut_34(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = None
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


async def x_scan_network__mutmut_35(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(None)
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


async def x_scan_network__mutmut_36(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = "XX, XX".join(f"{ip}:{port}" for ip, port in peer.addresses)
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


async def x_scan_network__mutmut_37(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = None
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_38(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(None)
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_39(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = "XX, XX".join(peer.services)
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_40(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(peer.services)
            print(None)
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_41(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(peer.services)
            print(f"{i}. {peer.node_id}")
            print(None)
            print(f"   Сервисы: {services}")
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_42(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(peer.services)
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(None)
            print(f"   Версия:  {peer.version}")
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_43(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("=" * 60)
    
    if found_peers:
        print(f"\nНайдено узлов: {len(found_peers)}\n")
        
        for i, peer in enumerate(found_peers, 1):
            addrs = ", ".join(f"{ip}:{port}" for ip, port in peer.addresses)
            services = ", ".join(peer.services)
            print(f"{i}. {peer.node_id}")
            print(f"   Адреса:  {addrs}")
            print(f"   Сервисы: {services}")
            print(None)
            print()
    else:
        print("\n❌ Узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_44(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print(None)
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_45(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("XX\n❌ Узлы не найденыXX")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_46(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("\n❌ узлы не найдены")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_47(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("\n❌ УЗЛЫ НЕ НАЙДЕНЫ")
        print("   Убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_48(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print(None)
    
    print("=" * 60)


async def x_scan_network__mutmut_49(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("XX   Убедитесь что другие узлы запущены в той же сетиXX")
    
    print("=" * 60)


async def x_scan_network__mutmut_50(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("   убедитесь что другие узлы запущены в той же сети")
    
    print("=" * 60)


async def x_scan_network__mutmut_51(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
        print("   УБЕДИТЕСЬ ЧТО ДРУГИЕ УЗЛЫ ЗАПУЩЕНЫ В ТОЙ ЖЕ СЕТИ")
    
    print("=" * 60)


async def x_scan_network__mutmut_52(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
    
    print(None)


async def x_scan_network__mutmut_53(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
    
    print("=" / 60)


async def x_scan_network__mutmut_54(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
    
    print("XX=XX" * 60)


async def x_scan_network__mutmut_55(args):
    """Одноразовое сканирование сети."""
    node_id = f"scanner-{uuid.uuid4().hex[:8]}"
    
    discovery = MeshDiscovery(
        node_id=node_id,
        service_port=args.port,
        enable_multicast=True,
        enable_dht=False
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
    print(f"📋 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
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
    
    print("=" * 61)

x_scan_network__mutmut_mutants : ClassVar[MutantDict] = {
'x_scan_network__mutmut_1': x_scan_network__mutmut_1, 
    'x_scan_network__mutmut_2': x_scan_network__mutmut_2, 
    'x_scan_network__mutmut_3': x_scan_network__mutmut_3, 
    'x_scan_network__mutmut_4': x_scan_network__mutmut_4, 
    'x_scan_network__mutmut_5': x_scan_network__mutmut_5, 
    'x_scan_network__mutmut_6': x_scan_network__mutmut_6, 
    'x_scan_network__mutmut_7': x_scan_network__mutmut_7, 
    'x_scan_network__mutmut_8': x_scan_network__mutmut_8, 
    'x_scan_network__mutmut_9': x_scan_network__mutmut_9, 
    'x_scan_network__mutmut_10': x_scan_network__mutmut_10, 
    'x_scan_network__mutmut_11': x_scan_network__mutmut_11, 
    'x_scan_network__mutmut_12': x_scan_network__mutmut_12, 
    'x_scan_network__mutmut_13': x_scan_network__mutmut_13, 
    'x_scan_network__mutmut_14': x_scan_network__mutmut_14, 
    'x_scan_network__mutmut_15': x_scan_network__mutmut_15, 
    'x_scan_network__mutmut_16': x_scan_network__mutmut_16, 
    'x_scan_network__mutmut_17': x_scan_network__mutmut_17, 
    'x_scan_network__mutmut_18': x_scan_network__mutmut_18, 
    'x_scan_network__mutmut_19': x_scan_network__mutmut_19, 
    'x_scan_network__mutmut_20': x_scan_network__mutmut_20, 
    'x_scan_network__mutmut_21': x_scan_network__mutmut_21, 
    'x_scan_network__mutmut_22': x_scan_network__mutmut_22, 
    'x_scan_network__mutmut_23': x_scan_network__mutmut_23, 
    'x_scan_network__mutmut_24': x_scan_network__mutmut_24, 
    'x_scan_network__mutmut_25': x_scan_network__mutmut_25, 
    'x_scan_network__mutmut_26': x_scan_network__mutmut_26, 
    'x_scan_network__mutmut_27': x_scan_network__mutmut_27, 
    'x_scan_network__mutmut_28': x_scan_network__mutmut_28, 
    'x_scan_network__mutmut_29': x_scan_network__mutmut_29, 
    'x_scan_network__mutmut_30': x_scan_network__mutmut_30, 
    'x_scan_network__mutmut_31': x_scan_network__mutmut_31, 
    'x_scan_network__mutmut_32': x_scan_network__mutmut_32, 
    'x_scan_network__mutmut_33': x_scan_network__mutmut_33, 
    'x_scan_network__mutmut_34': x_scan_network__mutmut_34, 
    'x_scan_network__mutmut_35': x_scan_network__mutmut_35, 
    'x_scan_network__mutmut_36': x_scan_network__mutmut_36, 
    'x_scan_network__mutmut_37': x_scan_network__mutmut_37, 
    'x_scan_network__mutmut_38': x_scan_network__mutmut_38, 
    'x_scan_network__mutmut_39': x_scan_network__mutmut_39, 
    'x_scan_network__mutmut_40': x_scan_network__mutmut_40, 
    'x_scan_network__mutmut_41': x_scan_network__mutmut_41, 
    'x_scan_network__mutmut_42': x_scan_network__mutmut_42, 
    'x_scan_network__mutmut_43': x_scan_network__mutmut_43, 
    'x_scan_network__mutmut_44': x_scan_network__mutmut_44, 
    'x_scan_network__mutmut_45': x_scan_network__mutmut_45, 
    'x_scan_network__mutmut_46': x_scan_network__mutmut_46, 
    'x_scan_network__mutmut_47': x_scan_network__mutmut_47, 
    'x_scan_network__mutmut_48': x_scan_network__mutmut_48, 
    'x_scan_network__mutmut_49': x_scan_network__mutmut_49, 
    'x_scan_network__mutmut_50': x_scan_network__mutmut_50, 
    'x_scan_network__mutmut_51': x_scan_network__mutmut_51, 
    'x_scan_network__mutmut_52': x_scan_network__mutmut_52, 
    'x_scan_network__mutmut_53': x_scan_network__mutmut_53, 
    'x_scan_network__mutmut_54': x_scan_network__mutmut_54, 
    'x_scan_network__mutmut_55': x_scan_network__mutmut_55
}

def scan_network(*args, **kwargs):
    result = _mutmut_trampoline(x_scan_network__mutmut_orig, x_scan_network__mutmut_mutants, args, kwargs)
    return result 

scan_network.__signature__ = _mutmut_signature(x_scan_network__mutmut_orig)
x_scan_network__mutmut_orig.__name__ = 'x_scan_network'


def x_main__mutmut_orig():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_1():
    parser = None
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_2():
    parser = argparse.ArgumentParser(
        description=None,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_3():
    parser = argparse.ArgumentParser(
        description="Mesh Discovery CLI",
        formatter_class=None,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_4():
    parser = argparse.ArgumentParser(
        description="Mesh Discovery CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=None
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_5():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_6():
    parser = argparse.ArgumentParser(
        description="Mesh Discovery CLI",
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_7():
    parser = argparse.ArgumentParser(
        description="Mesh Discovery CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_8():
    parser = argparse.ArgumentParser(
        description="XXMesh Discovery CLIXX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_9():
    parser = argparse.ArgumentParser(
        description="mesh discovery cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_10():
    parser = argparse.ArgumentParser(
        description="MESH DISCOVERY CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Запустить discovery daemon
  %(prog)s run --port 5000

  # Сканировать сеть
  %(prog)s scan --timeout 10

  # Discovery с кастомным ID
  %(prog)s run --node-id my-node-001 --services mesh,relay
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_11():
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
        """
    )
    
    subparsers = None
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_12():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest=None, help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_13():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help=None)
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_14():
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
        """
    )
    
    subparsers = parser.add_subparsers(help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_15():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", )
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_16():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="XXcommandXX", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_17():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="COMMAND", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_18():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="XXКомандаXX")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_19():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_20():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="КОМАНДА")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_21():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = None
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_22():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser(None, help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_23():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help=None)
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_24():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser(help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_25():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", )
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_26():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("XXrunXX", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_27():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("RUN", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_28():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="XXЗапустить discoveryXX")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_29():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_30():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="ЗАПУСТИТЬ DISCOVERY")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_31():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument(None, help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_32():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help=None)
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_33():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument(help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_34():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", )
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_35():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("XX--node-idXX", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_36():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--NODE-ID", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_37():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="XXID узла (авто если не указан)XX")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_38():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="id узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_39():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID УЗЛА (АВТО ЕСЛИ НЕ УКАЗАН)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_40():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument(None, type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_41():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=None, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_42():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=None, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_43():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help=None)
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_44():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument(type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_45():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_46():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_47():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, )
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_48():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("XX--portXX", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_49():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--PORT", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_50():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5001, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_51():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="XXПорт сервисаXX")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_52():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_53():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="ПОРТ СЕРВИСА")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_54():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument(None, default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_55():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default=None, help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_56():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help=None)
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_57():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument(default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_58():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_59():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", )
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_60():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("XX--servicesXX", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_61():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--SERVICES", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_62():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="XXmeshXX", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_63():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="MESH", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_64():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="XXСервисы (через запятую)XX")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_65():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_66():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="СЕРВИСЫ (ЧЕРЕЗ ЗАПЯТУЮ)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_67():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument(None, action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_68():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action=None, help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_69():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help=None)
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_70():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument(action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_71():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_72():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", )
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_73():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("XX--no-multicastXX", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_74():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--NO-MULTICAST", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_75():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="XXstore_trueXX", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_76():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="STORE_TRUE", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_77():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="XXОтключить multicastXX")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_78():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_79():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="ОТКЛЮЧИТЬ MULTICAST")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_80():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument(None, action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_81():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action=None, help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_82():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help=None)
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_83():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument(action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_84():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_85():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", )
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_86():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("XX--no-dhtXX", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_87():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--NO-DHT", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_88():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="XXstore_trueXX", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_89():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="STORE_TRUE", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_90():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="XXОтключить DHTXX")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_91():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="отключить dht")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_92():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="ОТКЛЮЧИТЬ DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_93():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument(None, type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_94():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=None, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_95():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=None, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_96():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help=None)
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_97():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument(type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_98():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_99():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_100():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, )
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_101():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("XX--intervalXX", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_102():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--INTERVAL", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_103():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=11, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_104():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="XXИнтервал статистикиXX")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_105():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_106():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="ИНТЕРВАЛ СТАТИСТИКИ")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_107():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument(None, "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_108():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", None, action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_109():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action=None, help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_110():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help=None)
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_111():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_112():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_113():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_114():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", )
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_115():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("XX-vXX", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_116():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-V", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_117():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "XX--verboseXX", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_118():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--VERBOSE", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_119():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="XXstore_trueXX", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_120():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="STORE_TRUE", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_121():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="XXПодробный выводXX")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_122():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_123():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="ПОДРОБНЫЙ ВЫВОД")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_124():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = None
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_125():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser(None, help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_126():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help=None)
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_127():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser(help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_128():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", )
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_129():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("XXscanXX", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_130():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("SCAN", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_131():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="XXСканировать сетьXX")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_132():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_133():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="СКАНИРОВАТЬ СЕТЬ")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_134():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument(None, type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_135():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=None, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_136():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=None, help="Таймаут сканирования")
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


def x_main__mutmut_137():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help=None)
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


def x_main__mutmut_138():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument(type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_139():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", default=5, help="Таймаут сканирования")
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


def x_main__mutmut_140():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, help="Таймаут сканирования")
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


def x_main__mutmut_141():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, )
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


def x_main__mutmut_142():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("XX--timeoutXX", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_143():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--TIMEOUT", type=float, default=5, help="Таймаут сканирования")
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


def x_main__mutmut_144():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=6, help="Таймаут сканирования")
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


def x_main__mutmut_145():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="XXТаймаут сканированияXX")
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


def x_main__mutmut_146():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="таймаут сканирования")
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


def x_main__mutmut_147():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="ТАЙМАУТ СКАНИРОВАНИЯ")
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


def x_main__mutmut_148():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument(None, type=int, default=5000, help="Порт")
    
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


def x_main__mutmut_149():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=None, default=5000, help="Порт")
    
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


def x_main__mutmut_150():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=None, help="Порт")
    
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


def x_main__mutmut_151():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help=None)
    
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


def x_main__mutmut_152():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument(type=int, default=5000, help="Порт")
    
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


def x_main__mutmut_153():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", default=5000, help="Порт")
    
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


def x_main__mutmut_154():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, help="Порт")
    
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


def x_main__mutmut_155():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, )
    
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


def x_main__mutmut_156():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("XX--portXX", type=int, default=5000, help="Порт")
    
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


def x_main__mutmut_157():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--PORT", type=int, default=5000, help="Порт")
    
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


def x_main__mutmut_158():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5001, help="Порт")
    
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


def x_main__mutmut_159():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="XXПортXX")
    
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


def x_main__mutmut_160():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="порт")
    
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


def x_main__mutmut_161():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="ПОРТ")
    
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


def x_main__mutmut_162():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="Порт")
    
    args = None
    
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


def x_main__mutmut_163():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="Порт")
    
    args = parser.parse_args()
    
    if args.command:
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


def x_main__mutmut_164():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="Порт")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Обработка Ctrl+C
    loop = None
    
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


def x_main__mutmut_165():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
    scan_parser.add_argument("--port", type=int, default=5000, help="Порт")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Обработка Ctrl+C
    loop = asyncio.new_event_loop()
    
    def signal_handler():
        for task in asyncio.all_tasks(None):
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


def x_main__mutmut_166():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        if args.command != "run":
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_167():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        if args.command == "XXrunXX":
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_168():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        if args.command == "RUN":
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_169():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(None, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_170():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal.SIGINT, None)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_171():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_172():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal.SIGINT, )
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_173():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(None, signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_174():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal.SIGTERM, None)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_175():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal_handler)
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_176():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.add_signal_handler(signal.SIGTERM, )
            loop.run_until_complete(run_discovery(args))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_177():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.run_until_complete(None)
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_178():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.run_until_complete(run_discovery(None))
        elif args.command == "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_179():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        elif args.command != "scan":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_180():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        elif args.command == "XXscanXX":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_181():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
        elif args.command == "SCAN":
            loop.run_until_complete(scan_network(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_182():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.run_until_complete(None)
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


def x_main__mutmut_183():
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
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # run
    run_parser = subparsers.add_parser("run", help="Запустить discovery")
    run_parser.add_argument("--node-id", help="ID узла (авто если не указан)")
    run_parser.add_argument("--port", type=int, default=5000, help="Порт сервиса")
    run_parser.add_argument("--services", default="mesh", help="Сервисы (через запятую)")
    run_parser.add_argument("--no-multicast", action="store_true", help="Отключить multicast")
    run_parser.add_argument("--no-dht", action="store_true", help="Отключить DHT")
    run_parser.add_argument("--interval", type=float, default=10, help="Интервал статистики")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Сканировать сеть")
    scan_parser.add_argument("--timeout", type=float, default=5, help="Таймаут сканирования")
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
            loop.run_until_complete(scan_network(None))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

x_main__mutmut_mutants : ClassVar[MutantDict] = {
'x_main__mutmut_1': x_main__mutmut_1, 
    'x_main__mutmut_2': x_main__mutmut_2, 
    'x_main__mutmut_3': x_main__mutmut_3, 
    'x_main__mutmut_4': x_main__mutmut_4, 
    'x_main__mutmut_5': x_main__mutmut_5, 
    'x_main__mutmut_6': x_main__mutmut_6, 
    'x_main__mutmut_7': x_main__mutmut_7, 
    'x_main__mutmut_8': x_main__mutmut_8, 
    'x_main__mutmut_9': x_main__mutmut_9, 
    'x_main__mutmut_10': x_main__mutmut_10, 
    'x_main__mutmut_11': x_main__mutmut_11, 
    'x_main__mutmut_12': x_main__mutmut_12, 
    'x_main__mutmut_13': x_main__mutmut_13, 
    'x_main__mutmut_14': x_main__mutmut_14, 
    'x_main__mutmut_15': x_main__mutmut_15, 
    'x_main__mutmut_16': x_main__mutmut_16, 
    'x_main__mutmut_17': x_main__mutmut_17, 
    'x_main__mutmut_18': x_main__mutmut_18, 
    'x_main__mutmut_19': x_main__mutmut_19, 
    'x_main__mutmut_20': x_main__mutmut_20, 
    'x_main__mutmut_21': x_main__mutmut_21, 
    'x_main__mutmut_22': x_main__mutmut_22, 
    'x_main__mutmut_23': x_main__mutmut_23, 
    'x_main__mutmut_24': x_main__mutmut_24, 
    'x_main__mutmut_25': x_main__mutmut_25, 
    'x_main__mutmut_26': x_main__mutmut_26, 
    'x_main__mutmut_27': x_main__mutmut_27, 
    'x_main__mutmut_28': x_main__mutmut_28, 
    'x_main__mutmut_29': x_main__mutmut_29, 
    'x_main__mutmut_30': x_main__mutmut_30, 
    'x_main__mutmut_31': x_main__mutmut_31, 
    'x_main__mutmut_32': x_main__mutmut_32, 
    'x_main__mutmut_33': x_main__mutmut_33, 
    'x_main__mutmut_34': x_main__mutmut_34, 
    'x_main__mutmut_35': x_main__mutmut_35, 
    'x_main__mutmut_36': x_main__mutmut_36, 
    'x_main__mutmut_37': x_main__mutmut_37, 
    'x_main__mutmut_38': x_main__mutmut_38, 
    'x_main__mutmut_39': x_main__mutmut_39, 
    'x_main__mutmut_40': x_main__mutmut_40, 
    'x_main__mutmut_41': x_main__mutmut_41, 
    'x_main__mutmut_42': x_main__mutmut_42, 
    'x_main__mutmut_43': x_main__mutmut_43, 
    'x_main__mutmut_44': x_main__mutmut_44, 
    'x_main__mutmut_45': x_main__mutmut_45, 
    'x_main__mutmut_46': x_main__mutmut_46, 
    'x_main__mutmut_47': x_main__mutmut_47, 
    'x_main__mutmut_48': x_main__mutmut_48, 
    'x_main__mutmut_49': x_main__mutmut_49, 
    'x_main__mutmut_50': x_main__mutmut_50, 
    'x_main__mutmut_51': x_main__mutmut_51, 
    'x_main__mutmut_52': x_main__mutmut_52, 
    'x_main__mutmut_53': x_main__mutmut_53, 
    'x_main__mutmut_54': x_main__mutmut_54, 
    'x_main__mutmut_55': x_main__mutmut_55, 
    'x_main__mutmut_56': x_main__mutmut_56, 
    'x_main__mutmut_57': x_main__mutmut_57, 
    'x_main__mutmut_58': x_main__mutmut_58, 
    'x_main__mutmut_59': x_main__mutmut_59, 
    'x_main__mutmut_60': x_main__mutmut_60, 
    'x_main__mutmut_61': x_main__mutmut_61, 
    'x_main__mutmut_62': x_main__mutmut_62, 
    'x_main__mutmut_63': x_main__mutmut_63, 
    'x_main__mutmut_64': x_main__mutmut_64, 
    'x_main__mutmut_65': x_main__mutmut_65, 
    'x_main__mutmut_66': x_main__mutmut_66, 
    'x_main__mutmut_67': x_main__mutmut_67, 
    'x_main__mutmut_68': x_main__mutmut_68, 
    'x_main__mutmut_69': x_main__mutmut_69, 
    'x_main__mutmut_70': x_main__mutmut_70, 
    'x_main__mutmut_71': x_main__mutmut_71, 
    'x_main__mutmut_72': x_main__mutmut_72, 
    'x_main__mutmut_73': x_main__mutmut_73, 
    'x_main__mutmut_74': x_main__mutmut_74, 
    'x_main__mutmut_75': x_main__mutmut_75, 
    'x_main__mutmut_76': x_main__mutmut_76, 
    'x_main__mutmut_77': x_main__mutmut_77, 
    'x_main__mutmut_78': x_main__mutmut_78, 
    'x_main__mutmut_79': x_main__mutmut_79, 
    'x_main__mutmut_80': x_main__mutmut_80, 
    'x_main__mutmut_81': x_main__mutmut_81, 
    'x_main__mutmut_82': x_main__mutmut_82, 
    'x_main__mutmut_83': x_main__mutmut_83, 
    'x_main__mutmut_84': x_main__mutmut_84, 
    'x_main__mutmut_85': x_main__mutmut_85, 
    'x_main__mutmut_86': x_main__mutmut_86, 
    'x_main__mutmut_87': x_main__mutmut_87, 
    'x_main__mutmut_88': x_main__mutmut_88, 
    'x_main__mutmut_89': x_main__mutmut_89, 
    'x_main__mutmut_90': x_main__mutmut_90, 
    'x_main__mutmut_91': x_main__mutmut_91, 
    'x_main__mutmut_92': x_main__mutmut_92, 
    'x_main__mutmut_93': x_main__mutmut_93, 
    'x_main__mutmut_94': x_main__mutmut_94, 
    'x_main__mutmut_95': x_main__mutmut_95, 
    'x_main__mutmut_96': x_main__mutmut_96, 
    'x_main__mutmut_97': x_main__mutmut_97, 
    'x_main__mutmut_98': x_main__mutmut_98, 
    'x_main__mutmut_99': x_main__mutmut_99, 
    'x_main__mutmut_100': x_main__mutmut_100, 
    'x_main__mutmut_101': x_main__mutmut_101, 
    'x_main__mutmut_102': x_main__mutmut_102, 
    'x_main__mutmut_103': x_main__mutmut_103, 
    'x_main__mutmut_104': x_main__mutmut_104, 
    'x_main__mutmut_105': x_main__mutmut_105, 
    'x_main__mutmut_106': x_main__mutmut_106, 
    'x_main__mutmut_107': x_main__mutmut_107, 
    'x_main__mutmut_108': x_main__mutmut_108, 
    'x_main__mutmut_109': x_main__mutmut_109, 
    'x_main__mutmut_110': x_main__mutmut_110, 
    'x_main__mutmut_111': x_main__mutmut_111, 
    'x_main__mutmut_112': x_main__mutmut_112, 
    'x_main__mutmut_113': x_main__mutmut_113, 
    'x_main__mutmut_114': x_main__mutmut_114, 
    'x_main__mutmut_115': x_main__mutmut_115, 
    'x_main__mutmut_116': x_main__mutmut_116, 
    'x_main__mutmut_117': x_main__mutmut_117, 
    'x_main__mutmut_118': x_main__mutmut_118, 
    'x_main__mutmut_119': x_main__mutmut_119, 
    'x_main__mutmut_120': x_main__mutmut_120, 
    'x_main__mutmut_121': x_main__mutmut_121, 
    'x_main__mutmut_122': x_main__mutmut_122, 
    'x_main__mutmut_123': x_main__mutmut_123, 
    'x_main__mutmut_124': x_main__mutmut_124, 
    'x_main__mutmut_125': x_main__mutmut_125, 
    'x_main__mutmut_126': x_main__mutmut_126, 
    'x_main__mutmut_127': x_main__mutmut_127, 
    'x_main__mutmut_128': x_main__mutmut_128, 
    'x_main__mutmut_129': x_main__mutmut_129, 
    'x_main__mutmut_130': x_main__mutmut_130, 
    'x_main__mutmut_131': x_main__mutmut_131, 
    'x_main__mutmut_132': x_main__mutmut_132, 
    'x_main__mutmut_133': x_main__mutmut_133, 
    'x_main__mutmut_134': x_main__mutmut_134, 
    'x_main__mutmut_135': x_main__mutmut_135, 
    'x_main__mutmut_136': x_main__mutmut_136, 
    'x_main__mutmut_137': x_main__mutmut_137, 
    'x_main__mutmut_138': x_main__mutmut_138, 
    'x_main__mutmut_139': x_main__mutmut_139, 
    'x_main__mutmut_140': x_main__mutmut_140, 
    'x_main__mutmut_141': x_main__mutmut_141, 
    'x_main__mutmut_142': x_main__mutmut_142, 
    'x_main__mutmut_143': x_main__mutmut_143, 
    'x_main__mutmut_144': x_main__mutmut_144, 
    'x_main__mutmut_145': x_main__mutmut_145, 
    'x_main__mutmut_146': x_main__mutmut_146, 
    'x_main__mutmut_147': x_main__mutmut_147, 
    'x_main__mutmut_148': x_main__mutmut_148, 
    'x_main__mutmut_149': x_main__mutmut_149, 
    'x_main__mutmut_150': x_main__mutmut_150, 
    'x_main__mutmut_151': x_main__mutmut_151, 
    'x_main__mutmut_152': x_main__mutmut_152, 
    'x_main__mutmut_153': x_main__mutmut_153, 
    'x_main__mutmut_154': x_main__mutmut_154, 
    'x_main__mutmut_155': x_main__mutmut_155, 
    'x_main__mutmut_156': x_main__mutmut_156, 
    'x_main__mutmut_157': x_main__mutmut_157, 
    'x_main__mutmut_158': x_main__mutmut_158, 
    'x_main__mutmut_159': x_main__mutmut_159, 
    'x_main__mutmut_160': x_main__mutmut_160, 
    'x_main__mutmut_161': x_main__mutmut_161, 
    'x_main__mutmut_162': x_main__mutmut_162, 
    'x_main__mutmut_163': x_main__mutmut_163, 
    'x_main__mutmut_164': x_main__mutmut_164, 
    'x_main__mutmut_165': x_main__mutmut_165, 
    'x_main__mutmut_166': x_main__mutmut_166, 
    'x_main__mutmut_167': x_main__mutmut_167, 
    'x_main__mutmut_168': x_main__mutmut_168, 
    'x_main__mutmut_169': x_main__mutmut_169, 
    'x_main__mutmut_170': x_main__mutmut_170, 
    'x_main__mutmut_171': x_main__mutmut_171, 
    'x_main__mutmut_172': x_main__mutmut_172, 
    'x_main__mutmut_173': x_main__mutmut_173, 
    'x_main__mutmut_174': x_main__mutmut_174, 
    'x_main__mutmut_175': x_main__mutmut_175, 
    'x_main__mutmut_176': x_main__mutmut_176, 
    'x_main__mutmut_177': x_main__mutmut_177, 
    'x_main__mutmut_178': x_main__mutmut_178, 
    'x_main__mutmut_179': x_main__mutmut_179, 
    'x_main__mutmut_180': x_main__mutmut_180, 
    'x_main__mutmut_181': x_main__mutmut_181, 
    'x_main__mutmut_182': x_main__mutmut_182, 
    'x_main__mutmut_183': x_main__mutmut_183
}

def main(*args, **kwargs):
    result = _mutmut_trampoline(x_main__mutmut_orig, x_main__mutmut_mutants, args, kwargs)
    return result 

main.__signature__ = _mutmut_signature(x_main__mutmut_orig)
x_main__mutmut_orig.__name__ = 'x_main'


if __name__ == "__main__":
    main()
