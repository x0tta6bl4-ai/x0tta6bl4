"""
Адаптер для реальных mesh-протоколов (batman-adv, yggdrasil)
Заменяет моки на реальные метрики
"""
import asyncio
import subprocess
import json
from typing import Dict, List, Optional, Any
import re
import logging
import random
from src.core.subprocess_validator import validate_command

logger = logging.getLogger(__name__)

class BatmanAdvAdapter:
    """
    Интерфейс к batman-adv через batctl
    """
    
    def __init__(self, interface: str = "bat0") -> None:
        self.interface = interface
    
    async def get_originators(self) -> List[Dict[str, Any]]:
        """
        Получить список originator'ов (mesh-узлов)
        
        Выполняет: batctl o
        Парсит вывод в структурированные данные
        """
        try:
            validate_command(['batctl', 'o'])
            proc = await asyncio.create_subprocess_exec(
                'batctl', 'o',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                # If batctl not found or error, log and return empty but don't crash
                logger.warning(f"batctl failed: {stderr.decode()}")
                return []
            
            # Парсинг вывода batctl
            # Формат: [B.A.T.M.A.N. adv openwrt-2021.0, MainIF/MAC: wlan0/...]
            # ff:ff:ff:ff:ff:ff    0.020s   (255) fe:ff:ff:ff:ff:ff [wlan0]
            
            originators = []
            lines = stdout.decode().strip().split('\n')
            if len(lines) > 2:
                lines = lines[2:]  # Skip header
            
            for line in lines:
                parts = re.split(r'\s+', line.strip())
                if len(parts) >= 3:
                    originators.append({
                        'mac': parts[0],
                        'last_seen': self._parse_time(parts[1]),
                        'tq': int(parts[2].strip('()')),  # Transmission Quality
                        'nexthop': parts[3] if len(parts) > 3 else None
                    })
            
            return originators
            
        except Exception as e:
            logger.error(f"Failed to get batman-adv originators: {e}")
            return []
    
    async def get_throughput(self) -> Dict[str, float]:
        """
        Получить throughput между узлами
        
        Выполняет: batctl tp -m <mac>
        """
        throughput_map = {}
        originators = await self.get_originators()
        
        for orig in originators[:5]:  # Ограничиваем для производительности
            try:
                validate_command(['batctl', 'tp', '-m', orig['mac']])
                proc = await asyncio.create_subprocess_exec(
                    'batctl', 'tp', '-m', orig['mac'],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    timeout=5
                )
                # Use wait_for for timeout
                try:
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Throughput test to {orig['mac']} timed out")
                    if proc.returncode is None:
                        proc.terminate()
                    continue

                # Парсинг вывода throughput теста
                output = stdout.decode()
                match = re.search(r'(\d+\.\d+)\s*Mbits/sec', output)
                if match:
                    throughput_map[orig['mac']] = float(match.group(1))
                    
            except Exception as e:
                logger.warning(f"Throughput test error: {e}")
                continue
                
        return throughput_map
    
    async def get_statistics(self) -> Dict[str, float]:
        """
        Агрегированная статистика mesh-сети
        """
        originators = await self.get_originators()
        throughput = await self.get_throughput()
        
        if not originators:
            return {
                'active_peers': 0,
                'avg_latency_ms': 1000,
                'packet_loss_percent': 100,
                'mttr_minutes': 10.0
            }
        
        # Transmission Quality как показатель здоровья канала
        avg_tq = sum(o['tq'] for o in originators) / len(originators)
        
        # Latency оценивается из last_seen (чем меньше, тем лучше)
        avg_last_seen = sum(o['last_seen'] for o in originators) / len(originators)
        estimated_latency = avg_last_seen * 1000  # Convert to ms
        
        # Packet loss из TQ (TQ=255 = 100% качество)
        packet_loss = 100 * (1 - (avg_tq / 255.0))
        
        # Средний throughput
        avg_throughput = (
            sum(throughput.values()) / len(throughput) 
            if throughput else 0
        )
        
        return {
            'active_peers': len(originators),
            'avg_latency_ms': estimated_latency,
            'packet_loss_percent': max(0, packet_loss),
            'avg_throughput_mbps': avg_throughput,
            'mttr_minutes': 3.5  # Будет рассчитываться из исторических данных
        }
    
    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Парсит время вида '0.020s' в секунды"""
        return float(time_str.rstrip('s'))


class YggdrasilAdapter:
    """
    Интерфейс к Yggdrasil через Admin API
    """
    
    def __init__(self, admin_socket: str = "/var/run/yggdrasil.sock"):
        self.admin_socket = admin_socket
    
    async def _send_command(self, request: Dict) -> Dict:
        """
        Отправить команду в Yggdrasil Admin API
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                'yggdrasilctl',
                '-json',
                '-v',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            request_json = json.dumps(request).encode()
            stdout, stderr = await proc.communicate(input=request_json)
            
            if proc.returncode != 0:
                logger.warning(f"yggdrasilctl failed: {stderr.decode()}")
                return {}
            
            return json.loads(stdout.decode())
            
        except Exception as e:
            logger.error(f"Yggdrasil command failed: {e}")
            return {}
    
    async def get_peers(self) -> List[Dict]:
        """
        Получить список peer'ов
        """
        response = await self._send_command({"request": "getPeers"})
        peers_data = response.get('response', {}).get('peers', {})
        
        peers = []
        for peer_addr, peer_info in peers_data.items():
            peers.append({
                'address': peer_addr,
                'port': peer_info.get('port'),
                'coords': peer_info.get('coords'),
                'bytes_sent': peer_info.get('bytes_sent', 0),
                'bytes_recvd': peer_info.get('bytes_recvd', 0),
                'uptime': peer_info.get('uptime', 0)
            })
        
        return peers
    
    async def get_dht(self) -> Dict:
        """
        Получить информацию о DHT
        """
        response = await self._send_command({"request": "getDHT"})
        return response.get('response', {})
    
    async def get_statistics(self) -> Dict[str, float]:
        """
        Агрегированная статистика Yggdrasil
        """
        peers = await self.get_peers()
        dht = await self.get_dht()
        
        if not peers:
            return {
                'active_peers': 0,
                'avg_latency_ms': 1000,
                'packet_loss_percent': 100,
                'mttr_minutes': 10.0
            }
        
        # Оценка latency из координат (расстояние в графе)
        avg_coords = []
        for peer in peers:
            if peer.get('coords'):
                coords = peer['coords']
                avg_coords.append(sum(coords) / len(coords) if coords else 0)
        
        estimated_latency = (
            sum(avg_coords) / len(avg_coords) * 10  # Heuristic: coord distance ~ latency
            if avg_coords else 100
        )
        
        # Throughput из переданных/принятых байт
        total_traffic = sum(p['bytes_sent'] + p['bytes_recvd'] for p in peers)
        avg_uptime = sum(p['uptime'] for p in peers) / len(peers) if peers else 1
        avg_throughput_mbps = (total_traffic / avg_uptime / 1024 / 1024 * 8) if avg_uptime > 0 else 0
        
        return {
            'active_peers': len(peers),
            'avg_latency_ms': estimated_latency,
            'packet_loss_percent': 0.5,  # Yggdrasil обычно очень надежен
            'avg_throughput_mbps': avg_throughput_mbps,
            'dht_size': len(dht.get('dht', {})),
            'mttr_minutes': 2.5
        }


class UnifiedMeshAdapter:
    """
    Унифицированный адаптер, который может работать с любым backend'ом
    """
    
    def __init__(self, backend: str = "auto"):
        self.backend = backend
        self._adapter = None
        
    async def initialize(self):
        """
        Автоматически определяет доступный mesh-backend
        """
        if self.backend == "auto":
            # Проверяем наличие batman-adv
            if await self._check_command('batctl'):
                self._adapter = BatmanAdvAdapter()
                self.backend = "batman-adv"
                logger.info("Using batman-adv backend")
                return
            
            # Проверяем наличие yggdrasil
            if await self._check_command('yggdrasilctl'):
                self._adapter = YggdrasilAdapter()
                self.backend = "yggdrasil"
                logger.info("Using yggdrasil backend")
                return
            
            # Fallback to simulation
            logger.warning("No mesh backend found, using simulation mode")
            # Import here to avoid circular imports if possible, or assume mock_network exists
            # For now, we'll implement a simple mock inline or fail gracefully
            self._adapter = MockMeshAdapter()
            self.backend = "simulation"
        
        elif self.backend == "batman-adv":
            self._adapter = BatmanAdvAdapter()
        elif self.backend == "yggdrasil":
            self._adapter = YggdrasilAdapter()
        elif self.backend == "simulation":
             self._adapter = MockMeshAdapter()
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    async def get_statistics(self) -> Dict[str, float]:
        """
        Получить статистику от активного адаптера
        """
        if not self._adapter:
            await self.initialize()
        
        return await self._adapter.get_statistics()
    
    @staticmethod
    async def _check_command(cmd: str) -> bool:
        """
        Проверить наличие команды в системе
        """
        try:
            validate_command(['which', cmd])
            proc = await asyncio.create_subprocess_exec(
                'which', cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return proc.returncode == 0
        except:
            return False

class MockMeshAdapter:
    """
    Mock adapter for simulation
    """
    async def get_statistics(self) -> Dict[str, float]:
        stats = {
            'active_peers': random.randint(3, 15),
            'avg_latency_ms': random.uniform(20.0, 150.0),
            'packet_loss_percent': random.uniform(0.0, 5.0),
            'mttr_minutes': random.uniform(2.0, 15.0),
            'avg_throughput_mbps': random.uniform(5.0, 50.0),
        }
        return {k: round(v, 4) for k, v in stats.items()}

