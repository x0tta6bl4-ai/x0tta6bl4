# Next Sprint Plan: eBPF Observability Deep Dive

**Дата**: 23 декабря 2025  
**Статус**: Готов к выполнению  
**Приоритет**: P0 (последняя критическая задача)

---

## 🎯 Цель спринта

Реализовать eBPF observability для достижения заявленных метрик:
- MTTR < 2s (текущая цель: 1.8s)
- 94%+ anomaly detection accuracy
- Sub-millisecond telemetry без overhead

---

## 📋 План выполнения

### Фаза 1: Подготовка инфраструктуры (Дни 1-2)

#### 1.1 CO-RE eBPF Framework Setup
**Файлы**: `src/network/ebpf/loader.py`, `src/network/ebpf/validator.py`

**Задачи**:
- [ ] Интеграция libbpf-rs или python-bcc для CO-RE
- [ ] Настройка BTF (BPF Type Format) для portability
- [ ] Создание базового loader для eBPF программ
- [ ] Валидация eBPF bytecode перед загрузкой

**Критерии успеха**:
- Loader может загружать простые eBPF программы
- Валидация блокирует небезопасный bytecode
- BTF информация корректно парсится

---

#### 1.2 Kernel Requirements Check
**Файл**: `src/network/ebpf/requirements.py`

**Задачи**:
- [ ] Проверка версии kernel (>= 5.8 для CO-RE)
- [ ] Проверка наличия BTF в `/sys/kernel/btf/vmlinux`
- [ ] Проверка доступности eBPF features (XDP, kprobe, tracepoint)
- [ ] Fallback на legacy eBPF если CO-RE недоступен

**Критерии успеха**:
- Автоматическое определение возможностей kernel
- Graceful degradation на старых ядрах
- Чёткие сообщения об ошибках

---

### Фаза 2: XDP Hook для Packet Filtering (Дни 3-5)

#### 2.1 XDP Program для Mesh Traffic
**Файл**: `src/network/ebpf/hooks/xdp_hook.py`

**Задачи**:
- [ ] Реализация XDP program на C (или Rust с aya-rs)
- [ ] Фильтрация mesh пакетов по SPIFFE ID
- [ ] Подсчёт packet loss и latency на NIC уровне
- [ ] Интеграция с batman-adv routing decisions

**eBPF Program структура**:
```c
SEC("xdp")
int xdp_mesh_filter(struct xdp_md *ctx) {
    // Parse packet headers
    // Check SPIFFE ID
    // Update metrics
    // Return XDP_PASS or XDP_DROP
}
```

**Критерии успеха**:
- XDP program загружается и работает
- Packet loss измеряется на NIC уровне
- Latency tracking без overhead (<0.1ms)

---

#### 2.2 XDP Metrics Export
**Файл**: `src/network/ebpf/hooks/xdp_metrics.py`

**Задачи**:
- [ ] eBPF maps для хранения метрик
- [ ] Экспорт метрик в Prometheus
- [ ] Интеграция с MAPE-K Monitor phase

**Критерии успеха**:
- Метрики доступны в `/metrics` endpoint
- MAPE-K использует eBPF метрики для decisions
- Overhead < 1% CPU на 1Gbps трафике

---

### Фаза 3: kprobe для Syscall Latency (Дни 6-8)

#### 3.1 kprobe для Critical Syscalls
**Файл**: `src/network/ebpf/hooks/kprobe_hook.py`

**Задачи**:
- [ ] kprobe на `sys_connect`, `sys_sendto`, `sys_recvfrom`
- [ ] Измерение latency для mesh operations
- [ ] Детекция аномалий в syscall patterns

**eBPF Program структура**:
```c
SEC("kprobe/sys_connect")
int kprobe_sys_connect(struct pt_regs *ctx) {
    // Record timestamp
    // Store in map for latency calculation
}
```

**Критерии успеха**:
- Latency измеряется для всех mesh syscalls
- Anomaly detection на основе syscall patterns
- Overhead < 0.5% CPU

---

#### 3.2 Tracepoint Integration
**Файл**: `src/network/ebpf/hooks/tracepoint_hook.py`

**Задачи**:
- [ ] Tracepoint hooks для network events
- [ ] Интеграция с GraphSAGE anomaly detector
- [ ] Real-time alerting на аномалии

**Критерии успеха**:
- Tracepoints работают стабильно
- GraphSAGE получает eBPF telemetry
- Alerts отправляются в <100ms

---

### Фаза 4: Интеграция и тестирование (Дни 9-10)

#### 4.1 MAPE-K Integration
**Файл**: `src/core/mape_k_loop.py`

**Задачи**:
- [ ] Интеграция eBPF метрик в Monitor phase
- [ ] Использование eBPF данных для anomaly detection
- [ ] Автоматическое recovery на основе eBPF alerts

**Критерии успеха**:
- MAPE-K использует eBPF метрики
- MTTR < 2s на основе eBPF telemetry
- 94%+ detection accuracy

---

#### 4.2 Performance Benchmarks
**Файл**: `tests/performance/test_ebpf_overhead.py`

**Задачи**:
- [ ] Измерение CPU overhead
- [ ] Измерение memory overhead
- [ ] Latency impact на mesh operations
- [ ] Сравнение с/без eBPF

**Критерии успеха**:
- CPU overhead < 2%
- Memory overhead < 50MB
- Latency impact < 0.5ms
- Все метрики в пределах заявленных

---

#### 4.3 CI/CD Integration
**Файл**: `.github/workflows/ebpf-tests.yml`

**Задачи**:
- [ ] Автоматические тесты eBPF программ
- [ ] Проверка BTF compatibility
- [ ] Performance regression tests

**Критерии успеха**:
- Все тесты проходят в CI
- Performance benchmarks в CI
- Автоматическое обнаружение регрессий

---

## 🛠 Технический стек

### Обязательные зависимости
- **libbpf** или **python-bcc** для eBPF
- **BTF** (BPF Type Format) для CO-RE
- **Kernel >= 5.8** для CO-RE support
- **clang >= 10** для компиляции eBPF программ

### Опциональные зависимости
- **aya-rs** (Rust eBPF framework) - альтернатива
- **bpftrace** для быстрого прототипирования
- **perf** для profiling

---

## 📊 Метрики успеха

### Технические метрики
- ✅ eBPF программы загружаются без ошибок
- ✅ XDP hook работает на production traffic
- ✅ kprobe измеряет syscall latency
- ✅ CPU overhead < 2%
- ✅ Memory overhead < 50MB
- ✅ Latency impact < 0.5ms

### Бизнес метрики
- ✅ MTTR < 2s (цель: 1.8s)
- ✅ Anomaly detection accuracy 94%+
- ✅ Zero false positives на production
- ✅ Sub-millisecond telemetry

---

## ⚠️ Риски и митигация

### Риск 1: Kernel compatibility
**Митигация**: 
- Fallback на legacy eBPF для старых ядер
- Graceful degradation без eBPF
- Чёткие требования в документации

### Риск 2: Performance overhead
**Митигация**:
- Тщательное профилирование
- Оптимизация hot paths
- Возможность отключения eBPF

### Риск 3: Security concerns
**Митигация**:
- Валидация bytecode перед загрузкой
- Sandboxing eBPF программ
- Security audit перед production

---

## 🚀 Быстрый старт

### День 1: Setup
```bash
# Проверить kernel version
uname -r  # >= 5.8

# Проверить BTF
ls /sys/kernel/btf/vmlinux

# Установить зависимости
pip install bcc-python  # или libbpf-rs
```

### День 2: Первый XDP hook
```bash
# Создать простой XDP program
# Загрузить через loader
python src/network/ebpf/loader.py load xdp_hook.o
```

---

## 📝 Документация

### Создать документы
- [ ] `docs/ebpf/ARCHITECTURE.md` - архитектура eBPF observability
- [ ] `docs/ebpf/DEVELOPMENT.md` - руководство для разработчиков
- [ ] `docs/ebpf/TROUBLESHOOTING.md` - решение проблем
- [ ] `docs/ebpf/PERFORMANCE.md` - метрики производительности

---

## ✅ Exit Criteria

Перед пометкой как "Production-ready":

- [ ] Все eBPF программы загружаются и работают
- [ ] Тесты проходят (>80% coverage)
- [ ] Performance benchmarks в пределах заявленных
- [ ] Документация обновлена
- [ ] CI/CD интеграция работает
- [ ] Security review пройден

---

**Оценка времени**: 10 дней  
**Сложность**: Высокая  
**Приоритет**: P0 (критический)

---

**Готов начать спринт?** 🚀

