# P0 Action Plan: Критические задачи для production readiness

**Дата:** 8 января 2026  
**Приоритет:** P0 (критические, блокируют production)  
**Целевой срок:** 4-6 недель до production readiness

---

## 🎯 Цель

Устранить критические пробелы, выявленные в независимом анализе, для перехода от beta к production.

---

## 📋 P0 Задачи (критические)

### 1. Payment Verification System

**Проблема:** Stub-реализация блокирует автоматическую монетизацию.

**Текущее состояние:**
- Файл: `src/sales/telegram_bot.py`
- Строки 185, 192: TODO - Integrate with TronScan/TON API
- Реализация: Ручная проверка платежей

**Требования:**

#### 1.1 TronScan API Integration

**Технические требования:**
- API Endpoint: `https://api.trongrid.io/v1/accounts/{address}/transactions`
- Поддержка USDT (TRC20) транзакций
- Верификация:
  - Сумма платежа
  - Адрес получателя
  - Order ID в memo field
  - Timestamp (не старше 24 часов)

**Реализация:**
```python
# src/sales/payment_verification.py

import requests
from typing import Optional, Dict
from datetime import datetime, timedelta

class TronScanVerifier:
    """TronScan API integration for USDT payment verification"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.trongrid.io/v1"
        self.timeout = 30  # seconds
        
    def verify_payment(
        self,
        wallet_address: str,
        expected_amount: float,
        order_id: str,
        amount_tolerance: float = 0.01
    ) -> Dict[str, any]:
        """
        Verify USDT payment via TronScan API.
        
        Args:
            wallet_address: Tron wallet address to check
            expected_amount: Expected payment amount in USDT
            order_id: Order ID to match in transaction memo
            amount_tolerance: Tolerance for amount matching (default 0.01 = 1%)
            
        Returns:
            Dict with verification result:
            {
                'verified': bool,
                'transaction_hash': str,
                'amount': float,
                'timestamp': int,
                'error': Optional[str]
            }
        """
        # Implementation here
        pass
```

**Оценка времени:** 1-2 недели (1 разработчик)

**Зависимости:**
- TronScan API access (регистрация, API key)
- Тестирование на testnet перед production

**Критерии успеха:**
- ✅ Автоматическая верификация USDT платежей
- ✅ Поддержка order ID в memo
- ✅ Обработка ошибок и retry logic
- ✅ Unit tests (coverage >90%)
- ✅ Integration tests с testnet

---

#### 1.2 TON API Integration

**Технические требования:**
- API Endpoint: `https://tonapi.io/v2/accounts/{address}/transactions`
- Поддержка TON и Jetton транзакций
- Верификация аналогична TronScan

**Реализация:**
```python
# src/sales/payment_verification.py

class TONVerifier:
    """TON API integration for TON payment verification"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://tonapi.io/v2"
        self.timeout = 30
        
    def verify_payment(
        self,
        wallet_address: str,
        expected_amount: float,
        order_id: str,
        amount_tolerance: float = 0.01
    ) -> Dict[str, any]:
        """Verify TON payment via TON API"""
        # Implementation here
        pass
```

**Оценка времени:** 1 неделя (1 разработчик)

**Критерии успеха:**
- ✅ Автоматическая верификация TON платежей
- ✅ Поддержка Jetton tokens
- ✅ Unit tests (coverage >90%)

---

#### 1.3 Integration с Telegram Bot

**Изменения в `src/sales/telegram_bot.py`:**
- Заменить ручную проверку на автоматическую
- Добавить retry logic для API calls
- Добавить error handling и logging
- Добавить webhook для real-time notifications

**Оценка времени:** 3-5 дней (1 разработчик)

**Критерии успеха:**
- ✅ Автоматическая обработка платежей
- ✅ Real-time уведомления пользователям
- ✅ Error handling и retry logic
- ✅ Integration tests

---

**Общая оценка времени:** 2-3 недели (1 разработчик)  
**Приоритет:** P0 (блокирует коммерциализацию)

---

### 2. Production Deployment

**Проблема:** Отсутствует production deployment (только staging).

**Текущее состояние:**
- Staging: Kubernetes (kind) на локальной машине
- Production: Не развернут

**Требования:**

#### 2.1 Cloud Provider Selection

**Варианты:**
- AWS (EKS) - рекомендуется для production
- GCP (GKE) - альтернатива
- Azure (AKS) - альтернатива

**Рекомендация:** AWS EKS (наиболее зрелая экосистема для Kubernetes)

---

#### 2.2 Infrastructure as Code

**Требования:**
- Terraform для infrastructure
- Helm charts для application deployment
- CI/CD pipeline для автоматического deployment

**Структура:**
```
infra/
  terraform/
    aws/
      eks/
        main.tf
        variables.tf
        outputs.tf
      networking/
        vpc.tf
        subnets.tf
      security/
        iam.tf
        security-groups.tf
  helm/
    x0tta6bl4/
      values-production.yaml
      templates/
        deployment.yaml
        service.yaml
        ingress.yaml
```

**Оценка времени:** 1 неделя (1 DevOps инженер)

**Критерии успеха:**
- ✅ Production cluster развернут
- ✅ Application deployed и работает
- ✅ Monitoring и logging настроены
- ✅ Backup и disaster recovery plan

---

#### 2.3 CI/CD Pipeline для Production

**Требования:**
- Автоматический deployment из GitLab CI
- Canary deployment для безопасных обновлений
- Rollback mechanism
- Health checks перед promotion

**Изменения в `.gitlab-ci.yml`:**
```yaml
deploy-production:
  stage: deploy
  script:
    - terraform apply -auto-approve
    - helm upgrade --install x0tta6bl4 ./helm/x0tta6bl4 -f values-production.yaml
    - ./scripts/health-check-production.sh
  only:
    - main
  when: manual
```

**Оценка времени:** 3-5 дней (1 DevOps инженер)

**Критерии успеха:**
- ✅ Автоматический deployment работает
- ✅ Canary deployment протестирован
- ✅ Rollback mechanism работает
- ✅ Health checks проходят

---

**Общая оценка времени:** 1-2 недели (1 DevOps инженер)  
**Приоритет:** P0 (блокирует production)

---

### 3. eBPF Observability

**Проблема:** Только документация, нет реальных eBPF программ.

**Текущее состояние:**
- Файл: `src/network/ebpf/loader.py`
- Строки 277, 394, 439: TODO - Implement actual eBPF programs
- Статус: Только заглушки и документация

**Требования:**

#### 3.1 eBPF Program: XDP Counter

**Цель:** Подсчет пакетов на уровне ядра для мониторинга трафика.

**Реализация:**
```c
// src/network/ebpf/programs/xdp_counter.c

#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} packet_count SEC(".maps");

SEC("xdp")
int xdp_counter_prog(struct xdp_md *ctx) {
    __u32 key = 0;
    __u64 *count = bpf_map_lookup_elem(&packet_count, &key);
    if (count) {
        (*count)++;
    }
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
```

**Оценка времени:** 1 неделя (1 разработчик с опытом eBPF)

**Критерии успеха:**
- ✅ eBPF программа компилируется
- ✅ Загружается в ядро через XDP
- ✅ Экспортирует метрики в Prometheus
- ✅ Unit tests для программы

---

#### 3.2 eBPF Program: TC Classifier

**Цель:** Классификация трафика на уровне ядра.

**Реализация:**
```c
// src/network/ebpf/programs/tc_classifier.c

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>

SEC("classifier")
int tc_classifier_prog(struct __sk_buff *skb) {
    // Packet classification logic
    return TC_ACT_OK;
}
```

**Оценка времени:** 1 неделя (1 разработчик)

**Критерии успеха:**
- ✅ Классификация трафика работает
- ✅ Метрики экспортируются
- ✅ Unit tests

---

#### 3.3 Integration с Loader

**Изменения в `src/network/ebpf/loader.py`:**
- Реализовать actual interface attachment (строка 277)
- Реализовать actual detachment (строка 394)
- Реализовать verification (строка 439)

**Оценка времени:** 1 неделя (1 разработчик)

**Критерии успеха:**
- ✅ eBPF программы загружаются автоматически
- ✅ Отсоединение работает корректно
- ✅ Verification проходит
- ✅ Integration tests

---

**Общая оценка времени:** 2-3 недели (1 разработчик с опытом eBPF)  
**Приоритет:** P0 (блокирует kernel-level мониторинг)

---

## 📊 Сводная таблица P0 задач

| Задача | Оценка времени | Приоритет | Блокирует | Статус |
|:-------|:---------------|:----------|:---------|:-------|
| **Payment Verification (TronScan)** | 1-2 недели | P0 | Коммерциализацию | ⏳ Не начато |
| **Payment Verification (TON)** | 1 неделя | P0 | Коммерциализацию | ⏳ Не начато |
| **Production Deployment (AWS)** | 1-2 недели | P0 | Production | ⏳ Не начато |
| **eBPF Observability** | 2-3 недели | P0 | Мониторинг | ⏳ Не начато |

**Общая оценка времени:** 4-6 недель (1-2 разработчика)

---

## 🎯 Критерии успеха для P0

### Payment Verification:
- ✅ Автоматическая верификация USDT и TON платежей
- ✅ Integration tests проходят
- ✅ Error handling и retry logic работают
- ✅ Real-time уведомления пользователям

### Production Deployment:
- ✅ Production cluster развернут и работает
- ✅ CI/CD pipeline для автоматического deployment
- ✅ Monitoring и logging настроены
- ✅ Backup и disaster recovery plan готов

### eBPF Observability:
- ✅ eBPF программы загружаются и работают
- ✅ Метрики экспортируются в Prometheus
- ✅ Integration tests проходят
- ✅ Документация обновлена

---

## 📅 Рекомендуемый timeline

### Недели 1-2 (Jan 8-21, 2026)
- 🔴 **Payment Verification (TronScan)** → 1-2 недели
- 🟡 Beta launch (2-3 клиента) с ручной проверкой платежей

### Недели 2-3 (Jan 15-28, 2026)
- 🔴 **Payment Verification (TON)** → 1 неделя
- 🔴 **Production Deployment (AWS)** → 1-2 недели (параллельно)

### Недели 4-6 (Jan 29 - Feb 18, 2026)
- 🔴 **eBPF Observability** → 2-3 недели
- 🟡 Тестирование и валидация всех P0 компонентов

### Февраль 2026
- ✅ Все P0 задачи завершены
- ✅ Production ready
- ✅ Готовность к коммерциализации

---

## 🚨 Риски и митигация

### Риск 1: Задержки в Payment Verification API
**Митигация:** Начать с TronScan (более простой API), затем TON

### Риск 2: Сложность eBPF разработки
**Митигация:** Начать с простых программ (XDP Counter), затем расширять

### Риск 3: Проблемы с Production Deployment
**Митигация:** Тестировать на staging перед production, использовать canary deployment

---

**Дата:** 8 января 2026  
**Статус:** ✅ P0 Action Plan готов  
**Следующий шаг:** Назначение ответственных и начало работы



