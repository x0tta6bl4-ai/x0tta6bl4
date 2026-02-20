# LLM Module Documentation

## Overview

Модуль LLM (Large Language Model) для платформы x0tta6bl4 MaaS предоставляет унифицированный интерфейс для работы с различными LLM-провайдерами, интеграцию с ConsciousnessEngine и MAPE-K циклом, а также интеллектуальное кэширование и rate limiting.

**Версия:** 2.0.0  
**Последнее обновление:** 2026-02-20  
**Статус:** Production Ready (80%)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM Module Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ConsciousnessLLMIntegration                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │   System     │  │   Healing    │  │   Anomaly Prediction     │  │   │
│  │  │   Analysis   │  │   Decision   │  │   & Explanation          │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────────┐   │
│  │                            LLMGateway                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │   Failover   │  │    Load      │  │   Response Caching       │  │   │
│  │  │   Manager    │  │  Balancing   │  │   (Semantic Cache)       │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────────┐   │
│  │                         Provider Layer                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │  Ollama  │  │   vLLM   │  │  OpenAI  │  │  Local (llama)   │   │   │
│  │  │ Provider │  │ Provider │  │ Provider │  │    Provider      │   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Cross-Cutting Concerns                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │ Rate Limiter │  │   Semantic   │  │   Metrics & Logging      │  │   │
│  │  │ (Token Bucket│  │    Cache     │  │   (Prometheus)           │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Компоненты

### 1. LLMGateway

Центральный компонент для управления множественными LLM-провайдерами.

**Возможности:**
- Автоматический failover между провайдерами
- Load balancing (round-robin, least-latency, random)
- Унифицированный интерфейс для всех провайдеров
- Метрики и мониторинг

**Использование:**

```python
from src.llm import LLMGateway, LLMConfig, OllamaProvider, VLLMProvider

# Создание gateway
config = LLMConfig(
    default_provider=LLMProvider.OLLAMA,
    enable_cache=True,
    failover_enabled=True,
    load_balance_strategy="least_latency",
)
gateway = LLMGateway(config)

# Регистрация провайдеров
gateway.register_provider(OllamaProvider(model="llama3.2"))
gateway.register_provider(VLLMProvider(model="mixtral-8x7b"))

# Генерация текста
result = gateway.generate(
    prompt="Analyze system metrics",
    max_tokens=512,
    temperature=0.3,
)

# Chat completion
from src.llm import ChatMessage

messages = [
    ChatMessage(role="system", content="You are a helpful assistant."),
    ChatMessage(role="user", content="What is the system status?"),
]
response = gateway.chat(messages)
```

### 2. SemanticCache

Интеллектуальное кэширование ответов с поддержкой семантического сходства.

**Возможности:**
- Точное совпадение (fast path)
- Семантическое сходство через embeddings
- LRU eviction
- TTL-based expiration
- Thread-safe операции

**Использование:**

```python
from src.llm import SemanticCache

cache = SemanticCache(
    max_size=1000,
    ttl_seconds=3600,
    similarity_threshold=0.95,
    enable_semantic=True,
)

# Сохранение
cache.set(
    query="What is the CPU usage?",
    response="Current CPU usage is 45%",
    model="llama3.2",
    provider="ollama",
)

# Получение
entry = cache.get("What is the CPU usage?")
if entry:
    print(entry.response)

# Статистика
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

### 3. RateLimiter

Ограничение частоты запросов к API.

**Возможности:**
- Token bucket алгоритм
- Sliding window
- Fixed window
- Автоматический backoff
- Мульти-провайдерная поддержка

**Использование:**

```python
from src.llm import RateLimiter, RateLimitConfig, RateLimitStrategy

config = RateLimitConfig(
    requests_per_minute=60,
    tokens_per_minute=100000,
    burst_size=10,
    strategy=RateLimitStrategy.TOKEN_BUCKET,
)
limiter = RateLimiter(config)

# Acquire permission
if limiter.acquire(tokens=100, blocking=False):
    # Make API call
    pass
else:
    # Wait or handle rate limit
    wait_time = limiter.get_wait_time(tokens=100)
    print(f"Wait {wait_time:.2f}s before retry")
```

### 4. ConsciousnessLLMIntegration

Интеграция LLM с ConsciousnessEngine для принятия решений.

**Возможности:**
- Анализ состояния системы
- Генерация healing решений
- Предсказание аномалий
- Объяснение аномалий на естественном языке

**Использование:**

```python
from src.llm import ConsciousnessLLMIntegration, create_consciousness_integration

# Создание интеграции
integration = create_consciousness_integration(
    provider="ollama",
    model="llama3.2",
)

# Анализ системы
metrics = {
    "cpu_percent": 75.0,
    "memory_percent": 60.0,
    "latency_ms": 120.0,
    "packet_loss": 0.5,
}

analysis = integration.analyze_system_state(
    metrics=metrics,
    consciousness_state="CONTEMPLATIVE",
    phi_ratio=0.85,
)

print(f"Summary: {analysis.summary}")
print(f"Anomalies: {analysis.anomalies}")
print(f"Recommendations: {analysis.recommendations}")

# Генерация healing решения
decision = integration.generate_healing_decision(
    anomaly="High CPU usage detected",
    context=metrics,
    available_actions=["restart_service", "scale_up", "throttle_requests"],
)

print(f"Action: {decision.action}")
print(f"Risk: {decision.risk_level}")
print(f"Confidence: {decision.confidence}")
```

---

## Провайдеры

### OllamaProvider

Локальный LLM сервер Ollama.

```python
from src.llm import OllamaProvider, ProviderConfig

config = ProviderConfig(
    name="ollama",
    base_url="http://localhost:11434",
    model="llama3.2",
)
provider = OllamaProvider(config)

# Health check
if provider.health_check():
    result = provider.generate("Hello, world!")
```

### VLLMProvider

Высокопроизводительный vLLM сервер.

```python
from src.llm import VLLMProvider

provider = VLLMProvider(
    base_url="http://localhost:8000",
    model="mixtral-8x7b",
)

# Chat completion
messages = [ChatMessage(role="user", content="Hello")]
result = provider.chat(messages)
```

### OpenAICompatibleProvider

Универсальный провайдер для OpenAI-совместимых API.

```python
from src.llm import OpenAICompatibleProvider

provider = OpenAICompatibleProvider(
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    model="gpt-4",
)

# With embeddings
embedding = provider.embed("Hello world")
```

---

## Интеграция с MAPE-K

Модуль LLM интегрируется с MAPE-K циклом самовосстановления:

```
┌─────────────────────────────────────────────────────────────────┐
│                      MAPE-K Loop Integration                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │ MONITOR  │───►│ ANALYZE  │───►│   PLAN   │───►│ EXECUTE  │ │
│   │          │    │          │    │          │    │          │ │
│   │ Metrics  │    │ LLM      │    │ LLM      │    │ Actions  │ │
│   │ eBPF     │    │ Analysis │    │ Planning │    │ Recovery │ │
│   │ Mesh     │    │ Anomaly  │    │ Healing  │    │ Isolate  │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│         ▲                                            │         │
│         └────────────────────────────────────────────┘         │
│                          KNOWLEDGE                             │
│                    (LLM-powered Learning)                      │
└─────────────────────────────────────────────────────────────────┘
```

**Пример интеграции:**

```python
from src.core.mape_k import MAPEKLoop
from src.llm import ConsciousnessLLMIntegration

class LLMEnhancedMAPEK(MAPEKLoop):
    def __init__(self):
        super().__init__()
        self.llm = ConsciousnessLLMIntegration()
    
    def analyze(self, metrics):
        # Standard analysis
        anomalies = super().analyze(metrics)
        
        # LLM-enhanced analysis
        llm_analysis = self.llm.analyze_system_state(
            metrics=metrics,
            consciousness_state=self.consciousness.state.value,
            phi_ratio=self.consciousness.phi_ratio,
        )
        
        return {**anomalies, "llm_insights": llm_analysis}
    
    def plan(self, analysis):
        # LLM-generated healing plan
        decision = self.llm.generate_healing_decision(
            anomaly=analysis.get("primary_anomaly"),
            context=analysis,
            available_actions=self.get_available_actions(),
        )
        
        return {
            "action": decision.action,
            "target": decision.target,
            "parameters": decision.parameters,
            "confidence": decision.confidence,
        }
```

---

## Конфигурация

### Переменные окружения

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# vLLM
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=mixtral-8x7b

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Cache
LLM_CACHE_SIZE=1000
LLM_CACHE_TTL=3600

# Rate Limiting
LLM_RPM=60
LLM_TPM=100000
```

### YAML конфигурация

```yaml
llm:
  default_provider: ollama
  
  cache:
    enabled: true
    max_size: 1000
    ttl_seconds: 3600
    semantic_matching: true
    
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    tokens_per_minute: 100000
    strategy: token_bucket
    
  providers:
    - name: ollama
      type: ollama
      base_url: http://localhost:11434
      model: llama3.2
      default: true
      
    - name: vllm
      type: vllm
      base_url: http://localhost:8000
      model: mixtral-8x7b
      
    - name: openai
      type: openai
      api_key: ${OPENAI_API_KEY}
      model: gpt-4
```

---

## Метрики Prometheus

```
# Cache metrics
llm_cache_hits_total{provider="ollama"} 1234
llm_cache_misses_total{provider="ollama"} 56
llm_cache_hit_rate{provider="ollama"} 0.956

# Rate limiter metrics
llm_rate_limit_requests_total{provider="ollama"} 1290
llm_rate_limit_limited_total{provider="ollama"} 12
llm_rate_limit_current_backoff{provider="ollama"} 0.0

# Provider metrics
llm_provider_requests_total{provider="ollama"} 1290
llm_provider_errors_total{provider="ollama"} 3
llm_provider_latency_ms{provider="ollama"} 45.2
llm_provider_tokens_total{provider="ollama"} 128000

# Gateway metrics
llm_gateway_failovers_total 2
llm_gateway_active_providers 3
```

---

## API Endpoints

### GET /api/v1/llm/status

Статус LLM модуля.

**Response:**
```json
{
  "providers": {
    "ollama": {
      "status": "available",
      "total_requests": 1290,
      "success_rate": 0.997,
      "avg_latency_ms": 45.2
    }
  },
  "cache": {
    "size": 234,
    "hit_rate": 0.956
  },
  "rate_limits": {
    "ollama": {
      "available_requests": 45,
      "available_tokens": 85000
    }
  }
}
```

### POST /api/v1/llm/generate

Генерация текста.

**Request:**
```json
{
  "prompt": "Analyze system metrics",
  "provider": "ollama",
  "max_tokens": 512,
  "temperature": 0.3,
  "use_cache": true
}
```

**Response:**
```json
{
  "text": "Based on the metrics...",
  "model": "llama3.2",
  "provider": "ollama",
  "tokens_used": 128,
  "latency_ms": 45.2,
  "cached": false
}
```

### POST /api/v1/llm/chat

Chat completion.

**Request:**
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the system status?"}
  ],
  "provider": "ollama"
}
```

---

## Тестирование

```bash
# Unit tests
pytest tests/test_llm_gateway.py -v

# Integration tests
pytest tests/test_llm_gateway.py -v -k "Integration"

# Coverage
pytest tests/test_llm_gateway.py --cov=src/llm --cov-report=html
```

---

## Best Practices

1. **Всегда используйте кэширование** для повторяющихся запросов
2. **Настройте rate limiting** для предотвращения превышения лимитов API
3. **Используйте failover** для критических операций
4. **Мониторьте метрики** через Prometheus
5. **Тестируйте с mock провайдерами** в development

---

## Troubleshooting

### Ollama недоступен

```bash
# Проверка статуса
curl http://localhost:11434/api/tags

# Запуск Ollama
ollama serve
```

### Высокий latency

1. Проверьте размер модели
2. Уменьшите `max_tokens`
3. Включите кэширование
4. Используйте более быстрый провайдер

### Rate limit exceeded

1. Увеличьте `requests_per_minute` в конфигурации
2. Включите `blocking=True` для ожидания
3. Используйте failover на другой провайдер

---

## Changelog

### v2.0.0 (2026-02-20)
- Добавлен Multi-Provider LLM Gateway
- Реализован Semantic Cache с embedding similarity
- Добавлен Token Bucket Rate Limiter
- Интеграция с ConsciousnessEngine
- Интеграция с MAPE-K loop
- OpenAI-compatible provider
- vLLM provider
- Ollama provider
- Полное покрытие тестами

### v1.0.0 (2025-12-01)
- Базовая интеграция LocalLLM
- Простой generate/chat интерфейс
