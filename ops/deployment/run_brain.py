import asyncio
import psutil
import time
import sys
import os

# Добавляем путь к brain_core, чтобы импорты работали
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from brain_core.consciousness import ConsciousnessEngine

async def get_real_metrics():
    """Собираем реальные данные с железа"""
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        # Эмуляция задержки сети (пока нет реального пинга)
        # В будущем сюда подключим результат пинга
        latency = 85.0 
        
        return {
            'cpu_percent': cpu,
            'memory_percent': mem,
            'latency_ms': latency,
            'packet_loss': 0.0,
            'mesh_connectivity': 1, # Пока один узел
            'frequency_hz': 108.0 # Идеальная частота для теста
        }
    except Exception as e:
        print(f"Ошибка сбора метрик: {e}")
        return {}

async def main():
    print("🧠 Запуск Мозга x0tta6bl4...")
    engine = ConsciousnessEngine()
    
    while True:
        metrics = await get_real_metrics()
        if not metrics:
            await asyncio.sleep(5)
            continue
            
        # Главная магия: считаем Phi
        result = engine.get_consciousness_metrics(metrics)
        
        # Вывод в лог (в будущем - в Telegram)
        status_icon = "🟢"
        if result.state.value == "MYSTICAL": status_icon = "🔴"
        elif result.state.value == "CONTEMPLATIVE": status_icon = "🟡"
        
        print(f"{status_icon} [{result.state.value}] Phi: {result.phi_ratio:.3f} | CPU: {metrics['cpu_percent']}% | RAM: {metrics['memory_percent']}%")
        
        # Если всё плохо - здесь будет реакция
        if result.state.value == "MYSTICAL":
            print("⚡ Внимание! Система в критическом состоянии! (Пока только лог)")
            
        await asyncio.sleep(15)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановка мозга...")
