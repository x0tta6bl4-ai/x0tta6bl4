# 📋 План Staging Deployment: Недели 2-3 (Jan 8-21, 2026)

**Дата создания:** 2026-01-04  
**Статус:** 🟢 ACTIVE  
**K8s Platform:** kind (local) ✅  
**Цель:** Развернуть x0tta6bl4 v3.4 в staging, решить все P0 issues, валидировать метрики

---

## 📊 Обзор Плана

| Неделя | Период | Основные Задачи | Milestones |
|--------|--------|-----------------|------------|
| **Неделя 2** | Jan 8-14 | Staging Deployment + Payment Verification | Cluster setup, App deployed, Monitoring ready |
| **Неделя 3** | Jan 15-21 | P0 Issues + Validation | All P0 complete, Metrics validated |

---

## 🗓️ Неделя 2: Staging Deployment + Payment Verification (Jan 8-14)

### **День 1-2 (Jan 8-9): Cluster Setup & Application Deployment**

#### **Milestone 1.1: Kubernetes Cluster Setup**
- [ ] **Prerequisites Check:**
  - [ ] kind установлен и работает
  - [ ] kubectl настроен и подключён к cluster
  - [ ] helm установлен (версия 3.x+)
  - [ ] Docker работает и доступен
  - [ ] Достаточно ресурсов (CPU, RAM, disk)

- [ ] **Create Staging Cluster:**
  ```bash
  # Создать новый kind cluster для staging (если нужен отдельный)
  kind create cluster --name x0tta6bl4-staging-deploy --config kind-staging-config.yaml
  
  # Или использовать существующий x0tta6bl4-staging
  kubectl config use-context kind-x0tta6bl4-staging
  ```

- [ ] **Verify Cluster:**
  ```bash
  kubectl cluster-info
  kubectl get nodes
  kubectl get pods -A
  ```

#### **Milestone 1.2: Application Deployment**
- [ ] **Build Docker Images:**
  ```bash
  docker build -t x0tta6bl4:3.4.0 -f Dockerfile .
  docker tag x0tta6bl4:3.4.0 localhost:5000/x0tta6bl4:3.4.0
  ```

- [ ] **Deploy using Helm:**
  ```bash
  helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
    --namespace x0tta6bl4-staging \
    --create-namespace \
    --set image.tag=3.4.0 \
    --set environment=staging \
    -f helm/values-staging.yaml
  ```

- [ ] **Verify Deployment:**
  ```bash
  kubectl get pods -n x0tta6bl4-staging
  kubectl get services -n x0tta6bl4-staging
  kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 --tail=50
  ```

**Критерии успеха:**
- ✅ Все pods в статусе Running
- ✅ Services доступны
- ✅ Health endpoint отвечает: `curl http://localhost:8080/health`

---

### **День 3-4 (Jan 10-11): Monitoring Stack**

#### **Milestone 1.3: Prometheus + Grafana Setup**
- [ ] **Deploy Prometheus:**
  ```bash
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace
  ```

- [ ] **Configure ServiceMonitors:**
  - [ ] Создать ServiceMonitor для x0tta6bl4 metrics
  - [ ] Настроить scrape configs
  - [ ] Проверить сбор метрик

- [ ] **Access Grafana:**
  ```bash
  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
  # Открыть http://localhost:3000
  # Логин: admin / admin (изменить при первом входе)
  ```

- [ ] **Create Dashboards:**
  - [ ] System metrics (CPU, Memory, Load)
  - [ ] Application metrics (PQC, Anomaly, GraphSAGE)
  - [ ] Network metrics (Mesh, Latency, Throughput)
  - [ ] Health checks dashboard

**Критерии успеха:**
- ✅ Prometheus собирает метрики от всех компонентов
- ✅ Grafana dashboards отображают данные
- ✅ Alerts настроены и работают

---

### **День 5-7 (Jan 12-14): Payment Verification Implementation**

#### **Milestone 1.4: Payment Verification (P0, Deadline Jan 15)**
- [ ] **Создать структуру:**
  ```bash
  mkdir -p src/payment
  touch src/payment/verifier.py
  touch src/payment/blockchain_apis.py
  touch tests/payment/test_verifier.py
  ```

- [ ] **Реализовать Payment Verifier:**
  ```python
  # src/payment/verifier.py
  async def verify_payment(
      payment_hash: str,
      amount: float,
      currency: str,
      destination_wallet: str
  ) -> PaymentVerificationResult:
      """
      Verify USDT (ERC-20/TRC-20) or TON payments
      
      Steps:
      1. Check blockchain explorer API (TronScan, Etherscan, TON API)
      2. Validate transaction hash exists
      3. Confirm amount matches
      4. Verify destination wallet
      5. Check transaction status (confirmed)
      6. Return verification result
      """
  ```

- [ ] **Интегрировать Blockchain APIs:**
  - [ ] TronScan API для USDT-TRC20
  - [ ] Etherscan API для USDT-ERC20
  - [ ] TON API для TON payments
  - [ ] Error handling и retry logic
  - [ ] Rate limiting

- [ ] **Тесты:**
  - [ ] Unit tests для verifier
  - [ ] Integration tests с mock APIs
  - [ ] Test coverage > 80%

- [ ] **Документация:**
  - [ ] API documentation
  - [ ] Usage examples
  - [ ] Configuration guide

**Критерии успеха:**
- ✅ Payment Verification работает для USDT (TRC-20, ERC-20)
- ✅ Payment Verification работает для TON
- ✅ Тесты проходят (coverage > 80%)
- ✅ Интегрировано в sales/telegram_bot.py
- ✅ Deadline: Jan 15 ✅

---

## 🗓️ Неделя 3: P0 Issues + Validation (Jan 15-21)

### **День 1-2 (Jan 15-16): Payment Verification Completion + Health Checks**

#### **Milestone 2.1: Payment Verification Finalization**
- [ ] **Завершить Payment Verification:**
  - [ ] Финальное тестирование
  - [ ] Интеграция в production flow
  - [ ] Документация обновлена
  - [ ] ✅ **Deadline Jan 15: COMPLETE**

#### **Milestone 2.2: Health Checks All Components**
- [ ] **Layer 1: Mesh Network**
  - [ ] Проверить beacon signaling
  - [ ] Проверить routing (GraphSAGE)
  - [ ] Проверить anomaly detection
  - [ ] Проверить mesh convergence

- [ ] **Layer 2: Security**
  - [ ] Проверить PQC handshake
  - [ ] Проверить SPIFFE/SPIRE
  - [ ] Проверить mTLS
  - [ ] Проверить certificate rotation

- [ ] **Layer 3: Self-Healing**
  - [ ] Проверить MAPE-K циклы
  - [ ] Проверить MTTD/MTTR
  - [ ] Проверить recovery actions

- [ ] **Layer 4: Distributed Data**
  - [ ] Проверить CRDT sync
  - [ ] Проверить IPFS (если используется)
  - [ ] Проверить Slot-Sync

- [ ] **Layer 5: AI/ML**
  - [ ] Проверить GraphSAGE inference
  - [ ] Проверить Federated Learning
  - [ ] Проверить RAG pipeline

- [ ] **Layer 6: Hybrid Search**
  - [ ] Проверить BM25 + Vector search
  - [ ] Проверить query latency

**Критерии успеха:**
- ✅ Все компоненты Layer 1-6 работают
- ✅ Health endpoints отвечают 200 OK
- ✅ Нет критических ошибок в логах

---

### **День 3-4 (Jan 17-18): eBPF Observability**

#### **Milestone 2.3: eBPF Observability (P0, Deadline Jan 18)**
- [ ] **Создать структуру:**
  ```bash
  mkdir -p src/observability/ebpf
  touch src/observability/ebpf_loader.py
  touch src/observability/ebpf_programs/trace_network.c
  touch tests/observability/test_ebpf.py
  ```

- [ ] **Реализовать eBPF Loader:**
  ```python
  # src/observability/ebpf_loader.py
  def load_ebpf_program(program_name: str) -> BPFProgram:
      """
      Load eBPF kernel module and attach to hooks
      
      Steps:
      1. Compile eBPF source (.c) using clang/llvm
      2. Load into kernel using bpf syscall
      3. Attach to uprobe/kprobe/tracepoint
      4. Stream metrics to userspace via perf_buffer
      5. Export metrics to Prometheus
      """
  ```

- [ ] **Создать eBPF Programs:**
  - [ ] Network tracing (packet latency, throughput)
  - [ ] System calls tracing (syscall latency)
  - [ ] Function tracing (key functions performance)

- [ ] **Интеграция:**
  - [ ] Интеграция с Prometheus
  - [ ] Интеграция с Grafana dashboards
  - [ ] Error handling и fallback

- [ ] **Тесты:**
  - [ ] Unit tests для loader
  - [ ] Integration tests (если возможно)
  - [ ] Test coverage > 70%

**Критерии успеха:**
- ✅ eBPF programs загружаются в kernel
- ✅ Metrics собираются и экспортируются
- ✅ Grafana dashboards показывают eBPF metrics
- ✅ Deadline: Jan 18 ✅

---

### **День 5-7 (Jan 19-21): GraphSAGE Causal Analysis + Validation**

#### **Milestone 2.4: GraphSAGE Causal Analysis (P0, Deadline Jan 22)**
- [ ] **Enhancement существующего кода:**
  ```python
  # src/ml/graphsage_causal.py
  def detect_root_cause(
      anomaly_node: str,
      graph: NetworkX.Graph,
      historical_data: Dict
  ) -> List[CausalFactor]:
      """
      Find root causes using causal inference
      
      Steps:
      1. Build causal graph from network topology
      2. Run backdoor criterion (Pearl's do-calculus)
      3. Identify confounders and mediators
      4. Calculate causal effect estimates
      5. Return ordered list of likely causes with confidence scores
      """
  ```

- [ ] **Интеграция:**
  - [ ] Интеграция с GraphSAGE anomaly detection
  - [ ] Интеграция с MAPE-K циклом
  - [ ] API endpoint для root cause analysis

- [ ] **Тесты:**
  - [ ] Unit tests для causal analysis
  - [ ] Integration tests с GraphSAGE
  - [ ] Test coverage > 75%

- [ ] **Документация:**
  - [ ] Causal inference methodology
  - [ ] Usage examples
  - [ ] Performance benchmarks

**Критерии успеха:**
- ✅ Causal analysis работает для anomaly detection
- ✅ Root causes идентифицируются с confidence scores
- ✅ Интегрировано в self-healing pipeline
- ✅ Deadline: Jan 22 ✅

#### **Milestone 2.5: Metrics Validation in Staging**
- [ ] **Валидация метрик:**
  ```bash
  # Запустить validation скрипты
  python scripts/validate_metrics_staging.py
  ```

- [ ] **Сравнить с целевыми значениями:**
  - [ ] PQC Handshake: < 2ms p95 (текущее: 0.81ms ✅)
  - [ ] Anomaly Detection: ≥ 94% (текущее: 96% ✅)
  - [ ] GraphSAGE Accuracy: ≥ 96% (текущее: 97% ✅)
  - [ ] MTTD: < 20s (текущее: 18.5s ✅)
  - [ ] MTTR: < 3min (текущее: 2.75min ✅)

- [ ] **Smoke Tests:**
  - [ ] Critical paths работают
  - [ ] Error handling работает
  - [ ] Recovery mechanisms работают

- [ ] **Документация результатов:**
  - [ ] Создать validation report
  - [ ] Обновить CONTINUITY.md с результатами
  - [ ] Обновить benchmarks/results/

**Критерии успеха:**
- ✅ Все метрики соответствуют целевым значениям
- ✅ Smoke tests проходят
- ✅ Validation report создан
- ✅ CONTINUITY.md обновлён

---

## 📊 Итоговые Критерии Успеха Недель 2-3

### **Неделя 2 (Jan 8-14):**
- ✅ Kubernetes cluster настроен и работает
- ✅ x0tta6bl4 v3.4 развернут в staging
- ✅ Monitoring stack (Prometheus, Grafana) работает
- ✅ Payment Verification реализация начата (50%+ готово)

### **Неделя 3 (Jan 15-21):**
- ✅ Payment Verification завершён (deadline Jan 15) ✅
- ✅ eBPF Observability завершён (deadline Jan 18) ✅
- ✅ GraphSAGE Causal Analysis завершён (deadline Jan 22) ✅
- ✅ Все компоненты Layer 1-6 проверены
- ✅ Метрики валидированы в staging environment
- ✅ Smoke tests пройдены

---

## 🚨 Риски и Митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Kind cluster нестабилен | Средняя | Высокое | Иметь backup план (minikube) |
| Payment APIs недоступны | Низкая | Среднее | Mock APIs для тестирования |
| eBPF требует kernel 5.8+ | Средняя | Высокое | Проверить kernel версию заранее |
| Недостаточно времени на P0 | Высокая | Критическое | Приоритизировать, начать раньше |

---

## 📝 Ежедневные Чеклисты

### **Каждый день (Jan 8-21):**
- [ ] Проверить статус pods: `kubectl get pods -n x0tta6bl4-staging`
- [ ] Проверить логи: `kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 --tail=50`
- [ ] Проверить метрики в Grafana
- [ ] Обновить прогресс в CONTINUITY.md
- [ ] Commit изменений в git

---

**Версия:** 1.0  
**Создано:** Jan 4, 23:45 CET  
**Статус:** 🟢 ACTIVE  
**K8s Platform:** kind (local) ✅

