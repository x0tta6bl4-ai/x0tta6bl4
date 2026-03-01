# План развития eBPF/Python интеграции x0tta6bl4

**Дата:** 10 января 2026  
**Версия:** 3.1.0  
**Статус:** ✅ Базовая интеграция завершена, планирование следующих шагов

---

## 📊 Текущее состояние

### Завершённые компоненты

| Модуль | Файл | Статус | Описание |
|--------|------|--------|----------|
| **EBPFLoader** | `loader.py` | ✅ Готов | Загрузка, подключение, отключение eBPF программ |
| **BCC Probes** | `bcc_probes.py` | ✅ Готов | Мониторинг латентности и очередей |
| **Mesh Integration** | `mesh_integration.py` | ✅ Готов | Интеграция с batman-adv топологией |
| **Anomaly Detector** | `ebpf_anomaly_detector.py` | ✅ Готов | MAPE-K интеграция для самовосстановления |
| **Cilium Integration** | `cilium_integration.py` | ✅ Готов | Hubble-like flow observability |
| **Metrics Exporter** | `metrics_exporter.py` | ✅ Готов | Экспорт в Prometheus |
| **Ring Buffer Reader** | `ringbuf_reader.py` | ✅ Готов | Чтение событий из ring buffer |
| **Dynamic Fallback** | `dynamic_fallback.py` | ✅ Готов | Автоматическое переключение маршрутов |
| **MAPE-K Integration** | `mape_k_integration.py` | ✅ Готов | Интеграция с MAPE-K циклом |

### XDP/eBPF программы (C)

| Программа | Файл | Статус | Описание |
|-----------|------|--------|----------|
| **XDP Mesh Filter** | `xdp_mesh_filter.c` | ✅ Готов | Фильтрация и маршрутизация mesh пакетов |
| **XDP Counter** | `xdp_counter.c` | ✅ Готов | Подсчёт пакетов по протоколам |
| **TC Classifier** | `tc_classifier.c` | ✅ Готов | Traffic Control классификатор |
| **Tracepoint Net** | `tracepoint_net.c` | ✅ Готов | Трейсинг сетевых событий |
| **Syscall Latency** | `kprobe_syscall_latency.c` | ✅ Готов | Измерение латентности syscall |
| **PQC Verify** | `xdp_pqc_verify.c` | ✅ Готов | Верификация PQC подписей |

---

## 🎯 Следующие шаги разработки

### Приоритет 1: Критические улучшения

#### 1.1 Создать единый оркестратор (`ebpf_orchestrator.py`) ✅ Выполнено
**Цель:** Объединить все компоненты в единую точку входа

```python
# Планируемый API:
orchestrator = EBPFOrchestrator(interface="eth0")
orchestrator.start()  # Запуск всех компонентов
orchestrator.get_status()  # Статус всех подсистем
orchestrator.stop()  # Корректное завершение
```

**Компоненты для интеграции:**
- EBPFLoader
- MeshNetworkProbes
- EBPFMetricsExporter
- CiliumLikeIntegration
- DynamicFallbackController
- EBPFMAPEKIntegration

#### 1.2 Добавить unit-тесты для EBPFLoader ✅ Выполнено
**Цель:** Покрытие тестами новых методов

```
tests/
├── test_ebpf_loader.py
│   ├── test_get_stats()
│   ├── test_update_routes()
│   ├── test_cleanup()
│   └── test_load_programs()
```

### Приоритет 2: Улучшения надёжности

#### 2.1 Улучшить обработку ошибок в metrics_exporter.py ✅ Выполнено
- Добавить retry логику для bpftool команд
- Graceful degradation при недоступности Prometheus
- Логирование метрик в файл как fallback

#### 2.2 Добавить health checks ✅ Выполнено
- Периодическая проверка состояния eBPF программ
- Автоматический перезапуск при сбоях
- Алерты в MAPE-K при критических ошибках

### Приоритет 3: Новая функциональность

#### 3.1 CLI для управления eBPF (`ebpf_cli.py`) ✅ Выполнено
```bash
# Планируемые команды:
x0tta6bl4-ebpf status          # Статус всех программ
x0tta6bl4-ebpf load <program>  # Загрузить программу
x0tta6bl4-ebpf attach <iface>  # Подключить к интерфейсу
x0tta6bl4-ebpf stats           # Показать статистику
x0tta6bl4-ebpf flows           # Показать flows (Hubble-like)
```

#### 3.2 Grafana дашборд для eBPF метрик (✅ Выполнено)
- Визуализация packet counters
- Графики латентности
- Flow observability
- Алерты на аномалии

---

## 📐 Архитектура интеграции

```
┌─────────────────────────────────────────────────────────────┐
│                    EBPFOrchestrator                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ EBPFLoader  │  │ BCC Probes  │  │ Metrics Exporter    │  │
│  │             │  │             │  │                     │  │
│  │ - load      │  │ - latency   │  │ - Prometheus        │  │
│  │ - attach    │  │ - congestion│  │ - Grafana           │  │
│  │ - detach    │  │             │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴──────────┐  │
│  │                    eBPF Maps                           │  │
│  │  packet_stats | mesh_routes | latency_hist | flows     │  │
│  └────────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────┴───────────────────────────┐  │
│  │                 XDP/TC Programs                        │  │
│  │  xdp_mesh_filter | xdp_counter | tc_classifier        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Network Interface                         │
│                         eth0                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Технические детали реализации

### EBPFOrchestrator - планируемая структура

```python
class EBPFOrchestrator:
    """Единая точка управления eBPF подсистемой."""
    
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.loader = EBPFLoader()
        self.probes = MeshNetworkProbes(interface)
        self.metrics = EBPFMetricsExporter()
        self.cilium = CiliumLikeIntegration(interface)
        self.fallback = DynamicFallbackController()
        self.mapek = EBPFMAPEKIntegration(self.metrics)
        
    async def start(self):
        """Запуск всех компонентов."""
        # 1. Загрузить eBPF программы
        # 2. Подключить к интерфейсу
        # 3. Запустить мониторинг
        # 4. Запустить экспорт метрик
        
    async def stop(self):
        """Корректное завершение."""
        # 1. Остановить мониторинг
        # 2. Отключить программы
        # 3. Очистить ресурсы
        
    def get_status(self) -> Dict[str, Any]:
        """Получить статус всех подсистем."""
        return {
            'loader': self.loader.list_loaded_programs(),
            'probes': self.probes.get_current_metrics(),
            'flows': self.cilium.get_flow_metrics(),
            'fallback': self.fallback.get_fallback_status()
        }
```

---

## 📅 Roadmap

| Фаза | Задачи | Срок |
|------|--------|------|
| **Фаза 1** | EBPFOrchestrator + Unit тесты | 1-2 дня |
| **Фаза 2** | CLI + Health checks | 2-3 дня |
| **Фаза 3** | Grafana дашборд | 1 день |
| **Фаза 4** | Документация + примеры | 1 день |

---

## ✅ Готово к реализации

Следующий шаг: **Создание EBPFOrchestrator** - единого модуля для управления всей eBPF подсистемой.

Переключиться в режим Code для реализации?
