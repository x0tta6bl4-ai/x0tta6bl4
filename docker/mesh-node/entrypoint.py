#!/usr/bin/env python3
"""
Entrypoint для Docker контейнера mesh node.
Конфигурируется через переменные окружения.
"""
import asyncio
import os
import sys
import signal
import logging

sys.path.insert(0, '/app')

from src.network.mesh_node import MeshNode, MeshNodeConfig

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('mesh-node')


def get_config() -> MeshNodeConfig:
    """Получить конфигурацию из ENV."""
    
    # Bootstrap nodes из ENV (формат: host1:port1,host2:port2)
    bootstrap_env = os.getenv('BOOTSTRAP_NODES', '')
    bootstrap_nodes = []
    if bootstrap_env:
        for node in bootstrap_env.split(','):
            if ':' in node:
                host, port = node.rsplit(':', 1)
                bootstrap_nodes.append((host.strip(), int(port)))
    
    # Services
    services = os.getenv('SERVICES', 'mesh').split(',')
    
    return MeshNodeConfig(
        node_id=os.getenv('NODE_ID'),
        port=int(os.getenv('PORT', '5000')),
        enable_discovery=os.getenv('ENABLE_DISCOVERY', 'true').lower() == 'true',
        enable_multicast=os.getenv('ENABLE_MULTICAST', 'true').lower() == 'true',
        bootstrap_nodes=bootstrap_nodes,
        obfuscation=os.getenv('OBFUSCATION', 'none'),
        obfuscation_key=os.getenv('OBFUSCATION_KEY', 'x0tta6bl4'),
        traffic_profile=os.getenv('TRAFFIC_PROFILE', 'none'),
        services=services
    )


async def main():
    """Главная функция."""
    config = get_config()
    
    logger.info("=" * 60)
    logger.info("x0tta6bl4 MESH NODE")
    logger.info("=" * 60)
    logger.info(f"Node ID:         {config.node_id}")
    logger.info(f"Port:            {config.port}")
    logger.info(f"Services:        {config.services}")
    logger.info(f"Obfuscation:     {config.obfuscation}")
    logger.info(f"Traffic Profile: {config.traffic_profile}")
    logger.info(f"Discovery:       {config.enable_discovery}")
    logger.info(f"Multicast:       {config.enable_multicast}")
    if config.bootstrap_nodes:
        logger.info(f"Bootstrap:       {config.bootstrap_nodes}")
    logger.info("=" * 60)
    
    node = MeshNode(config)
    
    # Callbacks
    @node.on_peer_discovered
    async def on_peer(peer):
        logger.info(f"🟢 Пир найден: {peer.node_id} @ {peer.addresses}")
    
    @node.on_peer_lost
    async def on_lost(peer):
        logger.info(f"🔴 Пир потерян: {peer.node_id}")
    
    @node.on_message
    async def on_message(data, peer, address):
        peer_id = peer.node_id if peer else str(address)
        logger.info(f"📨 Сообщение от {peer_id}: {data[:100]}")
        
        # Echo response
        if peer:
            await node.send_to_peer(peer.node_id, b"ACK:" + data[:50])
    
    # Graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Получен сигнал завершения...")
        shutdown_event.set()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await node.start()
    
    # Периодический статус
    async def status_loop():
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                stats = node.get_stats()
                logger.info(
                    f"📊 Пиров: {stats['peers_count']}, "
                    f"TX: {stats['messages_sent']}, "
                    f"RX: {stats['messages_received']}, "
                    f"Bytes TX: {stats['bytes_sent']}, "
                    f"Bytes RX: {stats['bytes_received']}"
                )
    
    status_task = asyncio.create_task(status_loop())
    
    # Ждём сигнала
    await shutdown_event.wait()
    
    # Cleanup
    status_task.cancel()
    await node.stop()
    
    logger.info("✅ Node остановлен")


if __name__ == '__main__':
    asyncio.run(main())
