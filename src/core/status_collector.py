"""
Status collector for /status endpoint
Собирает реальные данные о состоянии системы для API
"""

import psutil
import time
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Собирает метрики системы (CPU, память, диск, сеть)"""
    
    def __init__(self):
        self.start_time = time.time()
        self._last_net_io = psutil.net_io_counters()
        self._last_net_io_time = time.time()
    
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def get_disk_metrics(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def get_network_metrics(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def get_process_count(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def get_uptime_seconds(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() - self.start_time, 2)


class MeshNetworkMetrics:
    """Метрики mesh сети"""
    
    def __init__(self):
        self.peer_count = 0
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def update_from_batman_adv(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0


class StatusData:
    """Агрегирует все данные о статусе системы"""
    
    def __init__(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }


# Глобальный экземпляр
_status_data: Optional[StatusData] = None


def get_status_data() -> StatusData:
    """Получить глобальный объект статуса"""
    global _status_data
    if _status_data is None:
        _status_data = StatusData()
    return _status_data


def get_current_status() -> Dict[str, Any]:
    """Получить текущий статус системы"""
    return get_status_data().get_status()
