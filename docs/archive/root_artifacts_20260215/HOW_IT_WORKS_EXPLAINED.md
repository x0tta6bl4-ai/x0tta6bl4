# 🔍 КАК ВСЕ РАБОТАЕТ: ПОДРОБНЫЕ ПРИМЕРЫ

**Документ:** Практические примеры взаимодействия компонентов  
**Дата:** 12 января 2026 г.  
**Версия:** 3.3.0

---

## 📖 ОГЛАВЛЕНИЕ

1. [Пример 1: Запрос к API](#пример-1-запрос-к-api)
2. [Пример 2: Обнаружение и восстановление из сбоя](#пример-2-обнаружение-и-восстановление-из-сбоя)
3. [Пример 3: Масштабирование под нагрузку](#пример-3-масштабирование-под-нагрузку)
4. [Пример 4: Безопасное взаимодействие узлов](#пример-4-безопасное-взаимодействие-узлов)
5. [Пример 5: Голосование DAO](#пример-5-голосование-dao)

---

## Пример 1: Запрос к API

### Сценарий
Приложение хочет получить статус сети.

### Поэтапное выполнение

#### Шаг 1: Клиент отправляет запрос
```python
# Client-side code
import requests
import json

url = "https://x0tta6bl4-api.local/api/network/status"
headers = {
    "Authorization": "Bearer <SVID_TOKEN>"
}

response = requests.get(url, headers=headers, verify=True)
data = response.json()
```

#### Шаг 2: API Gateway получает запрос
```
REQUEST ARRIVES:
GET /api/network/status
Host: x0tta6bl4-api.local
Authorization: Bearer eyJhbGc...
```

**FastAPI обработка:**
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer

app = FastAPI()
security = HTTPBearer()

@app.get("/api/network/status")
async def get_network_status(credentials: HTTPAuthCredentials = Depends(security)):
    # Шаг 1: Валидация токена
    token = credentials.credentials
    # → Использует Pydantic для проверки формата
    
    # Шаг 2: Аутентификация
    try:
        svid_data = spiffe_client.verify_token(token)
        # → Проверяет SVID подпись (ML-DSA-65)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid SVID")
    
    # Шаг 3: Авторизация (Zero-Trust)
    if not policy_engine.can_access(svid_data, "network", "read"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Шаг 4: Получение данных от MAPE-K
    network_status = await mape_k.get_network_status()
    
    # Шаг 5: Логирование в Ledger
    await ledger.log_action(
        actor=svid_data.service_name,
        action="GET_NETWORK_STATUS",
        resource="network",
        status="SUCCESS"
    )
    
    # Шаг 6: Отправка ответа
    return {
        "status": "healthy",
        "nodes": len(network_status.nodes),
        "latency_ms": network_status.avg_latency,
        "mesh_health": network_status.health_percentage
    }
```

#### Результат
```json
{
  "status": "healthy",
  "nodes": 5,
  "latency_ms": 12.3,
  "mesh_health": 98.5
}
```

**Что произошло:**
1. ✅ SPIFFE аутентифицировал клиента
2. ✅ Zero-Trust политика проверена
3. ✅ MAPE-K предоставил актуальные данные
4. ✅ Действие залогировано в Ledger
5. ✅ Ответ отправлен в зашифрованном виде

---

## Пример 2: Обнаружение и восстановление из сбоя

### Сценарий
Node-3 выходит из строя. Система должна обнаружить это и восстановиться.

### Временная шкала

**T=0ms: Начало цикла мониторинга**
```python
# monitoring.py
async def health_check_cycle():
    nodes = await network.get_all_nodes()
    
    for node in nodes:
        # Отправляем ping каждый 100ms
        try:
            response = await node.health_check(timeout=50)
            metrics.record_node_healthy(node.id)
        except TimeoutError:
            metrics.record_node_timeout(node.id)
```

**T=150ms: Обнаружение проблемы**
```python
# mape_k/monitor.py
class Monitor:
    async def analyze_metrics(self):
        # Анализируем последние метрики
        node_timeouts = metrics.get_recent_timeouts(window=200)
        
        if node_timeouts["node_3"] > 3:  # 3 consecutive timeouts
            # ПРОБЛЕМА ОБНАРУЖЕНА!
            problem = Problem(
                type="NodeDown",
                severity="HIGH",
                affected_node="node_3",
                timestamp=datetime.now()
            )
            await self.analysis_phase(problem)
```

**T=300ms: ANALYZE фаза**
```python
# mape_k/analysis.py
async def analyze_node_failure(node_id):
    # Используем ML для анализа
    
    # Сбор contexual информации
    logs = await ledger.get_node_logs(node_id, last_5_mins=True)
    metrics = await monitoring.get_metrics(node_id, window=5_min)
    network_graph = await network.get_topology()
    
    # ML анализ
    analysis = ml_model.analyze({
        "logs": logs,
        "metrics": metrics,
        "network_state": network_graph
    })
    
    result = {
        "probable_cause": "Hardware failure - disk timeout",
        "affected_services": ["payment_api", "notification_service"],
        "confidence": 0.95,
        "recovery_time_estimate": 45  # seconds
    }
    
    return result
```

**T=450ms: PLAN фаза**
```python
# mape_k/planning.py
async def plan_recovery(analysis_result):
    # Генерируем варианты восстановления
    
    options = [
        {
            "id": "option_1",
            "strategy": "restart_node_3",
            "estimated_downtime": 30,
            "success_rate": 0.7,
            "impact": "LOW"
        },
        {
            "id": "option_2",
            "strategy": "failover_to_node_5",
            "estimated_downtime": 10,
            "success_rate": 0.95,
            "impact": "MINIMAL"
        },
        {
            "id": "option_3",
            "strategy": "spin_up_new_node",
            "estimated_downtime": 60,
            "success_rate": 0.98,
            "impact": "NONE"
        }
    ]
    
    # ML выбирает оптимальный вариант
    best_option = ml_model.select_best_option(options, context=analysis_result)
    
    return best_option  # option_2 (failover)
```

**T=600ms: DAO Voting (Consensus)**
```python
# dao/voting.py
async def create_recovery_proposal(plan):
    proposal = Proposal(
        title=f"Recover from {plan['strategy']}",
        description=f"Failover node_3 to node_5",
        execution_plan=plan,
        voting_period=5000  # 5 seconds for emergency
    )
    
    # Отправляем предложение всем узлам
    votes = await distributed_voting.submit(proposal)
    
    # Ждем консенсуса (>66% голосов)
    if votes.consensus_reached():
        return True
    else:
        return False
```

**T=900ms: EXECUTE фаза**
```python
# mape_k/execution.py
async def execute_failover(plan):
    try:
        # 1. Остановить трафик на node_3
        await network.isolate_node("node_3")
        
        # 2. Перенаправить трафик на node_5
        await batman.update_routing({
            "node_3": "offline",
            "node_3_traffic": "node_5"
        })
        
        # 3. Обновить DNS (если используется)
        await dns_manager.update_records()
        
        # 4. Запустить новый pod в K8s
        await kubernetes.create_pod(
            name="node_6_replacement",
            image="x0tta6bl4:3.3.0"
        )
        
        # 5. Добавить новый node в сеть
        await mesh.register_node("node_6")
        
        result = {
            "status": "SUCCESS",
            "failover_time": 45,  # ms
            "services_recovered": 2,
            "data_loss": 0
        }
        
        return result
        
    except Exception as e:
        await self.rollback()
        raise
```

**T=1000ms: Проверка результата**
```python
# mape_k/monitor.py
async def verify_recovery():
    # Проверяем, восстановилась ли система
    
    status = await system.health_check()
    
    if status.all_nodes_healthy and status.all_services_up:
        # ВОССТАНОВЛЕНИЕ УСПЕШНО!
        return "RECOVERED"
    else:
        # Попробуем следующий вариант
        return "PARTIAL_RECOVERY"
```

**T=1100ms: KNOWLEDGE UPDATE**
```python
# mape_k/knowledge.py
async def update_knowledge_base(incident_report):
    # Запомнили как это был успешно разрешено
    
    experience = {
        "incident_type": "NodeDown",
        "root_cause": "Hardware failure",
        "solution": "Failover to node_5",
        "time_to_recover": 150,  # ms
        "success": True,
        "lessons_learned": [
            "Failover strategy is 95% effective",
            "Hardware failures can be detected via disk timeouts",
            "K8s rolling restart takes ~30 seconds"
        ]
    }
    
    # Обновляем ML модель
    ml_model.learn_from_incident(experience)
    
    # Сохраняем в Ledger
    await ledger.record_incident(incident_report)
```

### Итоговая схема временной шкалы

```
T=0ms     ████ MONITOR     → Detect timeout
T=150ms   ████ ANALYZE     → Root cause analysis
T=300ms   ████ PLAN        → Generate recovery options
T=450ms   ████ VOTE        → DAO consensus
T=600ms   ████ EXECUTE     → Failover & recover
T=1000ms  ████ VERIFY      → Confirm recovery
T=1100ms  ████ LEARN       → Update models
         ─────────────────────────────────
Total:   ~1.1 seconds      (Полное восстановление)
```

---

## Пример 3: Масштабирование под нагрузку

### Сценарий
Трафик быстро растет. Система должна автоматически добавить capacity.

### Процесс масштабирования

**Фаза 1: Обнаружение возросшей нагрузки**
```python
# monitoring/metrics.py
async def track_load():
    # Собираем метрики каждые 100ms
    
    current_load = {
        "cpu_usage": 75,  # %
        "memory_usage": 82,  # %
        "request_latency": 45,  # ms
        "error_rate": 0.2,  # %
        "queue_length": 450  # pending requests
    }
    
    # Проверяем пороги
    if current_load["cpu_usage"] > 70:
        alert("HIGH_CPU_USAGE", current_load)
    
    if current_load["queue_length"] > 400:
        alert("QUEUE_BUILDUP", current_load)
```

**Фаза 2: ML предсказание**
```python
# ml/capacity_predictor.py
async def predict_required_capacity():
    # Используем temporal model для предсказания
    
    historical_data = await db.get_load_history(last_hour=True)
    
    # Обучим модель на исторических данных
    trend = ml_model.analyze_trend(historical_data)
    
    if trend["peak_in_next_10min"] > 200_000_rps:
        # Запрос в пик выше нашей текущей capacity
        
        required_nodes = trend["peak_rps"] / avg_rps_per_node
        
        forecast = {
            "current_nodes": 5,
            "required_nodes": 8,
            "additional_needed": 3,
            "confidence": 0.92
        }
        
        return forecast
```

**Фаза 3: MAPE-K планирование**
```python
# mape_k/execution.py
async def plan_scaling():
    forecast = await ml_predictor.predict_required_capacity()
    
    plan = {
        "action": "scale_up",
        "target_replica_count": forecast["required_nodes"],
        "new_nodes": forecast["additional_needed"],
        "strategy": "rolling",
        "health_check_interval": 5  # seconds
    }
    
    return plan
```

**Фаза 4: DAO голосование**
```python
# dao/voting.py
async def vote_on_scaling(plan):
    # Все узлы голосуют
    proposal = Proposal(
        title="Scale to 8 nodes",
        description=f"Add {plan['new_nodes']} nodes to handle predicted peak",
        voting_power_required=0.66  # >66% должны согласиться
    )
    
    votes = await distributed_voting.submit(proposal)
    
    if votes.passed:
        return True
```

**Фаза 5: Запуск новых узлов**
```python
# deployment/kubernetes.py
async def scale_deployment(target_replicas):
    # Используем Kubernetes API
    
    deployment = await k8s.get_deployment("x0tta6bl4")
    
    # Обновляем желаемое количество реплик
    await k8s.patch_deployment(
        deployment,
        replicas=target_replicas,
        strategy="RollingUpdate",
        max_surge=1,
        max_unavailable=0
    )
    
    # Ждем пока все узлы будут здоровы
    for i in range(target_replicas):
        new_pod = await k8s.wait_for_pod_ready(timeout=60)
        
        # Регистрируем в сети
        await mesh.register_node(new_pod.name)
        
        # Обновляем Batman-adv роутинг
        await network.update_mesh_routes()
```

**Фаза 6: Мониторинг процесса**
```python
# monitoring/scaling_monitor.py
async def monitor_scaling_progress():
    while True:
        metrics = await monitoring.get_current_metrics()
        
        if metrics["cpu_usage"] < 60 and metrics["latency"] < 30:
            # Масштабирование успешно
            status = "SCALING_COMPLETE"
            break
        
        await asyncio.sleep(1)
    
    # Логируем результат
    await ledger.log_scaling_event({
        "start_time": start,
        "end_time": datetime.now(),
        "nodes_added": 3,
        "success": True,
        "final_metrics": metrics
    })
```

### Результат
```
BEFORE:
  Nodes: 5
  Request latency: 45ms
  CPU: 75%
  Error rate: 0.2%

⏳ Масштабирование (30 seconds)

AFTER:
  Nodes: 8
  Request latency: 18ms ✅
  CPU: 52%
  Error rate: 0.01% ✅
```

---

## Пример 4: Безопасное взаимодействие узлов

### Сценарий
Node-A хочет безопасно отправить конфигурацию Node-B.

### Процесс связи

**Шаг 1: Node-A готовит сообщение**
```python
# node_a/communication.py
from cryptography import PQC

message = {
    "type": "CONFIG_UPDATE",
    "config": {
        "policy": "deny_by_default",
        "max_connections": 10000
    },
    "timestamp": datetime.now().isoformat()
}

# Сериализуем в JSON
json_data = json.dumps(message).encode()

print("📤 Message to send:", json_data)
```

**Шаг 2: Получить SVID для обоих узлов**
```python
# node_a/identity.py
import spiffe

# Получить SVID для себя
my_svid = await spiffe_client.fetch_svid()
# SVID = {service: "node_a", ttl: 3600, cert: ...}

# Получить публичный ключ Node-B
peer_public_key = await spiffe_server.get_public_key("node_b")
```

**Шаг 3: Зашифровать с использованием PQC**
```python
# node_a/crypto.py
from liboqs import KeyEncapsulation, Signature

# Шифрование (ML-KEM-768)
encryptor = KeyEncapsulation("ML-KEM-768")
ciphertext, shared_secret = encryptor.encap(peer_public_key)

# Ключ шифрования
aes_key = KDF(shared_secret, "AES-256")

# Шифруем сообщение
encrypted_message = AES_256_GCM.encrypt(
    plaintext=json_data,
    key=aes_key,
    nonce=os.urandom(16)
)

# Подписываем (ML-DSA-65)
signer = Signature("ML-DSA-65")
signature = signer.sign(
    message=encrypted_message,
    private_key=my_svid.private_key
)

print("🔐 Message encrypted and signed")
```

**Шаг 4: Отправить по TLS 1.3 (mTLS)**
```python
# node_a/transport.py
import ssl
import asyncio

# Подготовить SSL контекст с mTLS
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

# Загрузить SVID сертификат (клиент)
ssl_context.load_cert_chain(
    certfile=my_svid.cert_path,
    keyfile=my_svid.key_path
)

# Доверять только SPIFFE CAs
ssl_context.load_verify_locations(cafile=spiffe_root_ca)

# Отправить с mTLS
async with asyncio.open_connection(
    "node_b.local",
    8443,
    ssl=ssl_context
) as (reader, writer):
    
    # Отправляем зашифрованное сообщение
    packet = {
        "ephemeral_public_key": ciphertext,  # ML-KEM-768
        "encrypted_data": encrypted_message,  # AES-256-GCM
        "signature": signature,  # ML-DSA-65
        "sender_svid": my_svid
    }
    
    writer.write(json.dumps(packet).encode())
    await writer.drain()
    
    print("📬 Message sent securely")
```

**Шаг 5: Node-B получает и верифицирует**
```python
# node_b/receive.py

async def handle_incoming_message(packet_data):
    packet = json.loads(packet_data)
    
    # 1️⃣ Верифицировать отправителя через SPIFFE
    sender_svid = packet["sender_svid"]
    if not await spiffe_server.verify_svid(sender_svid):
        raise SecurityError("Invalid SVID from sender")
    
    # 2️⃣ Верифицировать подпись (ML-DSA-65)
    verifier = Signature("ML-DSA-65")
    if not verifier.verify(
        message=packet["encrypted_data"],
        signature=packet["signature"],
        public_key=sender_svid.public_key
    ):
        raise SecurityError("Invalid signature")
    
    # 3️⃣ Декапсулировать ключ (ML-KEM-768)
    decapsulator = KeyEncapsulation("ML-KEM-768")
    shared_secret = decapsulator.decap(
        ciphertext=packet["ephemeral_public_key"],
        secret_key=my_private_key
    )
    
    # 4️⃣ Расшифровать сообщение (AES-256-GCM)
    aes_key = KDF(shared_secret, "AES-256")
    plaintext = AES_256_GCM.decrypt(
        ciphertext=packet["encrypted_data"],
        key=aes_key
    )
    
    message = json.loads(plaintext)
    
    # 5️⃣ Проверить политики доступа (Zero-Trust)
    if not await policy_engine.can_accept_from(sender_svid, "CONFIG_UPDATE"):
        raise SecurityError("Not authorized for CONFIG_UPDATE")
    
    # 6️⃣ Применить конфигурацию
    await config_manager.apply_config(message["config"])
    
    # 7️⃣ Залогировать в Ledger
    await ledger.log_security_event({
        "type": "CONFIG_UPDATE_RECEIVED",
        "from": sender_svid.service_name,
        "to": "node_b",
        "status": "SUCCESS",
        "timestamp": datetime.now()
    })
    
    print("✅ Message received, verified, and applied")
```

### Итоговая последовательность

```
┌────────────────────────────────────────────────────────┐
│                 SECURE COMMUNICATION                  │
├────────────────────────────────────────────────────────┤

Node A                                          Node B
  │                                               │
  ├─1. Prepare message                           │
  ├─2. Get SVIDs (auth)                          │
  ├─3. Encrypt (ML-KEM-768)                      │
  ├─4. Sign (ML-DSA-65)                          │
  │                                               │
  │─────── TLS 1.3 (mTLS) ──────────────────────►│
  │  Mutual certificate verification             │
  │  Forward secrecy (PFS)                       │
  │  AEAD encryption (ChaCha20)                  │
  │                                               │
  │                            ├─1. Verify SVID
  │                            ├─2. Verify signature (ML-DSA-65)
  │                            ├─3. Decap key (ML-KEM-768)
  │                            ├─4. Decrypt (AES-256-GCM)
  │                            ├─5. Check Zero-Trust policy
  │                            ├─6. Apply config
  │                            ├─7. Log to Ledger
  │                            │
  │◄───── ACK (Verified) ──────┤
  │
  └─ Message delivery: SECURE ✅
```

---

## Пример 5: Голосование DAO

### Сценарий
Сеть должна принять решение о новой политике.

### Процесс голосования

**Фаза 1: Создание предложения**
```python
# dao/proposals.py

proposal = Proposal(
    title="Increase max connections to 50000",
    description="""
    Current limit of 10000 connections causes bottleneck.
    Propose increase to 50000 with load balancing.
    Impact: 20% throughput improvement
    Risk: Medium (needs monitoring)
    """,
    voting_period=86400,  # 24 hours
    execution_delay=3600,  # 1 hour after vote
    min_participation=0.66,  # >66% must vote
    min_approval=0.75  # >75% must approve
)

# Отправляем на всех узлах
await distributed_voting_system.create_proposal(proposal)
```

**Фаза 2: Узлы голосуют**
```python
# dao/voting.py (Each node)

class VotingSystem:
    async def cast_vote(self, proposal_id, vote):
        """
        vote: {
            "choice": "YES" or "NO",
            "rationale": "Text explanation",
            "weight": 1.0  # Квадратичное голосование
        }
        """
        
        # Quadratic voting: cost = vote_weight^2
        voting_power = self.calculate_voting_power(node_id)
        vote_cost = vote["weight"] ** 2
        
        if vote_cost > voting_power:
            raise ValueError("Insufficient voting power")
        
        # Подписываем голос цифровой подписью
        signed_vote = self.sign_vote(vote)
        
        # Отправляем в ledger (неизменяемый журнал)
        await ledger.record_vote(
            proposal_id=proposal_id,
            voter=node_id,
            vote=signed_vote,
            timestamp=datetime.now()
        )
        
        # Объявляем результат
        await self.broadcast_vote(proposal_id, signed_vote)
```

**Фаза 3: Подсчет голосов**
```python
# dao/consensus.py

async def tally_votes(proposal_id):
    """
    Подсчитать голоса с quadratic voting
    """
    
    votes = await ledger.get_all_votes(proposal_id)
    
    yes_power = 0
    no_power = 0
    
    for vote in votes:
        # Верифицировать подпись
        if not verify_vote_signature(vote):
            continue
        
        # Подсчитать голос с учетом quadratic weighting
        power = calculate_quadratic_power(vote["weight"])
        
        if vote["choice"] == "YES":
            yes_power += power
        else:
            no_power += power
    
    total_power = yes_power + no_power
    yes_percentage = yes_power / total_power * 100
    
    result = {
        "yes_votes": yes_power,
        "no_votes": no_power,
        "participation": total_power / total_voting_power * 100,
        "yes_percentage": yes_percentage,
        "passed": yes_percentage >= 75 and participation >= 66
    }
    
    return result
```

**Фаза 4: Исполнение решения**
```python
# dao/execution.py

async def execute_proposal(proposal_id):
    """
    Исполнить решение сети
    """
    
    result = await tally_votes(proposal_id)
    proposal = await get_proposal(proposal_id)
    
    if not result["passed"]:
        await ledger.record_vote_result(
            proposal_id=proposal_id,
            status="REJECTED",
            votes=result
        )
        return
    
    # PROPOSAL PASSED!
    
    # Ждем execution_delay
    await asyncio.sleep(proposal.execution_delay)
    
    # Применяем изменение
    try:
        if proposal.type == "CONFIG_UPDATE":
            await config_manager.apply_config(proposal.new_config)
        
        elif proposal.type == "POLICY_UPDATE":
            await policy_engine.update_policies(proposal.policies)
        
        elif proposal.type == "RESOURCE_SCALING":
            await kubernetes.scale_deployment(proposal.target_replicas)
        
        await ledger.record_vote_result(
            proposal_id=proposal_id,
            status="EXECUTED",
            votes=result,
            execution_time=datetime.now()
        )
        
    except Exception as e:
        await ledger.record_vote_result(
            proposal_id=proposal_id,
            status="EXECUTION_FAILED",
            error=str(e)
        )
        raise
```

**Фаза 5: Мониторинг результатов**
```python
# monitoring/voting_monitor.py

async def monitor_proposal_impact(proposal_id):
    """
    Следить за тем, как изменение повлияло на систему
    """
    
    before_metrics = await monitoring.get_baseline_metrics()
    
    # Ждем после исполнения
    await asyncio.sleep(300)  # 5 minutes
    
    after_metrics = await monitoring.get_current_metrics()
    
    impact = {
        "throughput_improvement": (
            after_metrics["throughput"] - before_metrics["throughput"]
        ) / before_metrics["throughput"] * 100,
        
        "latency_change": (
            after_metrics["latency"] - before_metrics["latency"]
        ),
        
        "error_rate_change": (
            after_metrics["error_rate"] - before_metrics["error_rate"]
        ),
        
        "resource_utilization": after_metrics["cpu_usage"]
    }
    
    # Если результаты плохие, может быть rollback
    if impact["error_rate_change"] > 0.5:
        await create_rollback_proposal(proposal_id)
    
    return impact
```

### Пример голосования в действии

```
PROPOSAL: "Increase max connections to 50000"

Voting Period: 24 hours
─────────────────────────────

Node 1 (votes YES with weight 2.0)
Node 2 (votes YES with weight 1.0)
Node 3 (votes NO with weight 1.0)
Node 4 (votes YES with weight 3.0)
Node 5 (votes YES with weight 1.0)

Quadratic voting calculation:
  YES: 2² + 1² + 3² + 1² = 4 + 1 + 9 + 1 = 15 power
  NO:  1² = 1 power

Result:
  Total voting power: 16
  Participation: 100%
  YES percentage: 15/16 = 93.75%
  Passes threshold (75%)? ✅ YES
  
Status: PASSED ✅

Execution delay: 1 hour
Then: Apply configuration to all nodes

Impact monitoring: 
  ✅ Throughput: +18%
  ✅ Latency: -2ms
  ✅ Errors: 0 additional

Final status: EXECUTED SUCCESSFULLY ✅
```

---

## 🎯 Итоговая таблица взаимодействий

| Компонент | Инициирует | Взаимодействует с | Результат |
|-----------|-----------|-------------------|-----------|
| API | Клиент | Security, MAPE-K, DB | Ответ (JSON) |
| Monitoring | Timer | MAPE-K, Prometheus | Метрики |
| MAPE-K | Monitoring | ML, DAO, Network, DB | Решение |
| ML | MAPE-K | DB, History | Рекомендация |
| DAO | MAPE-K | Consensus, Ledger | Голоса |
| Consensus | DAO | Network, Ledger | Согласие |
| Network | Execution | All nodes | Трафик |
| Ledger | Everything | DB | Запись |
| Security | All | Crypto, SPIFFE | Проверка |

---

**Все примеры представлены с кодом для лучшего понимания.**

