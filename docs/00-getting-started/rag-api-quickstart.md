# Быстрый старт RAG API для x0tta6bl4_paradox_zone

## 📋 Содержание

1. [Подготовка окружения](#подготовка-окружения)
2. [Запуск сервиса](#запуск-сервиса)
3. [Проверка работы](#проверка-работы)
4. [Запуск тестов](#запуск-тестов)
5. [Docker развёртывание](#docker-развёртывание)
6. [Устранение проблем](#устранение-проблем)

---

## 🚀 Подготовка окружения

### Вариант 1: Через скрипт (рекомендуется)

```bash
# Перейти в подпроект
cd /mnt/AC74CC2974CBF3DC/x0tta6bl4_paradox_zone

# Сделать скрипт исполняемым
chmod +x run_rag.sh quick_test.sh

# Запустить (автоматически создаст venv и установит зависимости)
./run_rag.sh
```

### Вариант 2: Через Makefile

```bash
cd /mnt/AC74CC2974CBF3DC/x0tta6bl4_paradox_zone

# Показать все команды
make help

# Установить окружение
make setup

# Запустить сервис
make run
```

### Вариант 3: Вручную

```bash
cd /mnt/AC74CC2974CBF3DC/x0tta6bl4_paradox_zone

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Обновить pip
pip install --upgrade pip setuptools wheel

# Установить зависимости
pip install -e ".[dev,ml,monitoring]"
```

---

## 🏃 Запуск сервиса

### Через скрипт

```bash
# Запуск на порту 8000 с реальной моделью
./run_rag.sh

# Запуск на другом порту
./run_rag.sh 8010

# Запуск с mock embedder (офлайн режим)
./run_rag.sh 8000 mock
```

### Через Makefile

```bash
# Обычный запуск
make run

# С mock embedder
make run-mock

# С hot-reload (для разработки)
make run-reload
```

### Через uvicorn

```bash
# Базовый запуск
uvicorn src.rag_api.main:app --host 0.0.0.0 --port 8000

# С hot-reload
uvicorn src.rag_api.main:app --host 0.0.0.0 --port 8000 --reload

# С mock embedder
USE_MOCK_EMBEDDER=true uvicorn src.rag_api.main:app --host 0.0.0.0 --port 8000
```

---

## ✅ Проверка работы

### Health check

```bash
# Простая проверка
curl http://localhost:8000/health

# С форматированием
curl -s http://localhost:8000/health | jq .

# Ожидаемый ответ:
# {"status": "healthy"}
```

### Тестовый запрос к RAG

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is x0tta6bl4?",
    "top_k": 3,
    "filters": {}
  }' | jq .
```

### Проверка метрик (если добавлен /metrics endpoint)

```bash
# Все метрики
curl http://localhost:8000/metrics

# Конкретные метрики
curl -s http://localhost:8000/metrics | grep rag_query
```

### API документация

Откройте в браузере:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🧪 Запуск тестов

### Через скрипт (рекомендуется)

```bash
# Все критические тесты
./quick_test.sh

# Только RAG тесты
./quick_test.sh rag

# Только PQC тесты
./quick_test.sh pqc

# Smoke test (быстрая проверка)
./quick_test.sh smoke
```

### Через Makefile

```bash
# Все тесты
make test

# Быстрые критические тесты
make test-quick

# RAG тесты
make test-rag

# PQC тесты
make test-pqc

# С coverage отчётом
make test-coverage
```

### Через pytest напрямую

```bash
# Активировать venv
source .venv/bin/activate

# Все тесты
pytest tests/ -v

# Конкретный тест
pytest tests/test_rag_ingestion_pipeline.py -v

# С фильтром
pytest tests/ -v -k "rag or mape"

# С максимальным выводом
pytest tests/ -v --tb=long
```

---

## 🐳 Docker развёртывание

### Вариант 1: Docker Compose (рекомендуется)

```bash
# Запуск всего стека (RAG API + Prometheus + Grafana)
docker-compose -f docker-compose.rag.yml up -d

# Просмотр логов
docker-compose -f docker-compose.rag.yml logs -f rag-api

# Остановка
docker-compose -f docker-compose.rag.yml down

# Полная очистка (включая volumes)
docker-compose -f docker-compose.rag.yml down -v
```

После запуска доступны:
- **RAG API**: http://localhost:8000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### Вариант 2: Простой Docker

```bash
# Сборка образа
docker build -t x0tta6bl4-rag:latest -f Dockerfile.rag .

# Запуск
docker run -d --name rag-api -p 8000:8000 x0tta6bl4-rag:latest

# Логи
docker logs -f rag-api

# Остановка
docker stop rag-api && docker rm rag-api
```

### Вариант 3: Через Makefile

```bash
# Сборка образа
make docker

# Запуск
make docker-run

# Остановка
make docker-stop

# Docker Compose
make docker-compose
```

---

## 🔧 Устранение проблем

### Проблема: Модель не загружается

**Симптомы**: Ошибки при загрузке SentenceTransformer, долгое ожидание

**Решение 1**: Использовать mock embedder
```bash
USE_MOCK_EMBEDDER=true ./run_rag.sh
```

**Решение 2**: Предзагрузить модель
```bash
python3 << 'EOF'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"Model cached: {model.cache_folder}")
EOF
```

**Решение 3**: Установить кастомный кэш
```bash
export SENTENCE_TRANSFORMERS_HOME=/path/to/cache
export HF_HOME=/path/to/cache
```

---

### Проблема: Порт занят

**Симптомы**: `Address already in use`

**Решение**: Найти и остановить процесс
```bash
# Найти процесс
lsof -i :8000

# Остановить
kill -9 <PID>

# Или запустить на другом порту
./run_rag.sh 8010
```

---

### Проблема: Импорты не работают

**Симптомы**: `ModuleNotFoundError`

**Решение 1**: Установить в editable режиме
```bash
pip install -e .
```

**Решение 2**: Установить PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

### Проблема: Конфликт зависимостей

**Симптомы**: Ошибки при `pip install`

**Решение**: Пересоздать окружение
```bash
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,ml,monitoring]"
```

---

### Проблема: Тесты падают

**Симптомы**: `pytest` показывает ошибки

**Диагностика**: Запустить с полным выводом
```bash
pytest tests/test_failing.py -v --tb=long
```

**Решение**: Проверить зависимости
```bash
pip list | grep -E "pytest|fastapi|sentence"
```

---

## 📊 Полезные команды

### Проверка статуса сервиса

```bash
# Health check с повтором
watch -n 5 'curl -s http://localhost:8000/health | jq .'

# Статистика запросов
curl -s http://localhost:8000/metrics | grep rag_query_total
```

### Мониторинг логов

```bash
# Если запущен через systemd
journalctl -u rag-api -f

# Если запущен в foreground
# Логи уже в терминале

# Docker
docker logs -f rag-api
```

### Бенчмарк производительности

```bash
# Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Hey (modern alternative)
hey -n 1000 -c 10 http://localhost:8000/health

# wrk
wrk -t4 -c100 -d30s http://localhost:8000/health
```

---

## 🎯 Чек-лист полной валидации

- [ ] Виртуальное окружение создано и активировано
- [ ] Все зависимости установлены без ошибок
- [ ] Сервер запускается без exceptions
- [ ] `GET /health` возвращает 200
- [ ] `POST /query` принимает запросы и возвращает результаты
- [ ] Метрики экспортируются (если добавлен `/metrics`)
- [ ] MAPE-K тесты проходят
- [ ] RAG тесты проходят
- [ ] PQC тесты проходят
- [ ] Docker образ собирается
- [ ] Docker Compose стартует все сервисы

---

## 📚 Дополнительная документация

- **API Reference**: http://localhost:8000/docs
- **Prometheus Queries**: См. `prometheus.yml`
- **Architecture**: См. основной README проекта
- **Development Guide**: См. `CONTRIBUTING.md`

---

## 🆘 Поддержка

Если проблема не решается:

1. Проверьте логи: `docker logs rag-api` или в терминале
2. Запустите диагностику: `./quick_test.sh smoke`
3. Проверьте зависимости: `pip list`
4. Создайте issue с полным выводом ошибки

---

**🎉 Готово! Сервис должен работать.**
