# Yandex Integration Modules

Интеграционные модули для Yandex open source проектов с поддержкой постквантовой криптографии (PQC).

## Модули

### 1. YDB PQC Adapter
**Целевой репозиторий:** github.com/yandex/ydb

Постквантовый TLS адаптер для YDB кластеров с ML-KEM-768 обменом ключами и ML-DSA-65 подписями.

```python
from src.integration.yandex.ydb_pqc_adapter import YDBPQCAdapter, PQCConfig

adapter = YDBPQCAdapter(config=PQCConfig(mode=PQCMode.HYBRID_X25519_ML_KEM))
adapter.initialize_node()
```

**Функции:**
- ML-KEM-768 обмен ключами для межузловых соединений
- ML-DSA-65 подписи для аттестации узлов
- Гибридный X25519+ML-KEM для обратной совместимости
- Кэширование рукопожатий для производительности

### 2. Perfator eBPF Collector
**Целевой репозиторий:** github.com/yandex/perforator

eBPF сборщик данных профилирования для Perforator с XDP программами и Prometheus экспортёром.

```python
from src.integration.yandex.perforator_ebpf_collector import PerfatorEBpfCollector, EbpfConfig

collector = PerfatorEBpfCollector(config=EbpfConfig(mode=PerfMode.ALL))
collector.start()
```

**Функции:**
- XDP программа для пакетного мониторинга
- Kprobes для анализа планировщика
- BPF карты для flame graph данных
- Prometheus экспорт метрик

### 3. Odyssey PQC TLS
**Целевой репозиторий:** github.com/yandex/odyssey

Постквантовый TLS для PostgreSQL соединений через Odyssey.

```python
from src.integration.yandex.odyssey_pqc_tls import OdysseyPQCTLS, OdysseyPQCConfig

odyssey = OdysseyPQCTLS(config=OdysseyPQCConfig(mode=OdysseyPQCMode.HYBRID_X25519_ML_KEM))
odyssey.initialize_server()
```

**Функции:**
- ML-KEM-768 обмен ключами для клиент-серверных рукопожатий
- Мультиплексирование соединений
- Кэширование PQC сессий
- Генерация конфигурации Odyssey

## Установка

```bash
# Зависимости для всех модулей
pip install liboqs-python

# Дополнительные зависимости
pip install ydb  # Для YDB адаптера
pip install bcc prometheus-client  # Для eBPF сборщика
```

## Требования

- Python 3.8+
- Linux ядро 5.10+ (для eBPF модуля)
- liboqs-python
- root привилегии (для eBPF модуля)

## Структура файлов

```
src/integration/yandex/
├── README.md                          # Этот файл
├── ydb_pqc_adapter/
│   ├── ydb_pqc_adapter.py            # Основной модуль
│   ├── README.md                      # Документация
│   ├── test_ydb_pqc_adapter.py       # Тесты
│   └── benchmark_ydb_pqc_adapter.py  # Бенчмарки
├── perforator_ebpf_collector/
│   ├── perforator_ebpf_collector.py  # Основной модуль
│   ├── README.md                      # Документация
│   ├── test_perforator_ebpf_collector.py  # Тесты
│   └── benchmark_perforator_ebpf_collector.py  # Бенчмарки
└── odyssey_pqc_tls/
    ├── odyssey_pqc_tls.py            # Основной модуль
    ├── README.md                      # Документация
    ├── test_odyssey_pqc_tls.py       # Тесты
    └── benchmark_odyssey_pqc_tls.py  # Бенчмарки
```

## Лицензия

Apache License 2.0

## Контрибьюция

1. Fork репозиторий
2. Создайте ветку для фичи
3. Внесите изменения
4. Добавьте тесты
5. Запустите бенчмарки
6. Отправьте PR

## Связь

- Issues: github.com/x0tta6bl4/post-quantum-mesh/issues
- Docs: github.com/x0tta6bl4/post-quantum-mesh/tree/main/docs
