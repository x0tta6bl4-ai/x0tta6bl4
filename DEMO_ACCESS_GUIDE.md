# 🌐 x0tta6bl4 Demo: Access Guide

**Дата:** 31 декабря 2025  
**Статус:** 🟢 **DEMO RUNNING**

---

## ✅ ТЕКУЩИЙ СТАТУС

### Deployment

```
✅ Pod: Running (1/1)
✅ Service: Active
✅ Health Endpoint: Working
```

---

## 🌐 ДОСТУП

### Health Check (РАБОТАЕТ ✅)

```bash
curl http://localhost:8080/health
```

**Ответ:**
```json
{
  "status": "ok",
  "version": "3.0.0"
}
```

### Root Endpoint

Если root endpoint не работает через service port-forward, используйте прямой port-forward на pod:

```bash
# Получить имя pod
POD_NAME=$(kubectl get pods -l app=x0tta6bl4 -o jsonpath='{.items[0].metadata.name}')

# Port-forward напрямую на pod
kubectl port-forward pod/$POD_NAME 8080:8080
```

---

## 🔧 АЛЬТЕРНАТИВНЫЕ СПОСОБЫ ДОСТУПА

### Вариант 1: Port-forward на Service

```bash
kubectl port-forward svc/x0tta6bl4 8080:80
```

### Вариант 2: Port-forward на Pod (прямой доступ)

```bash
# Получить pod name
POD=$(kubectl get pods -l app=x0tta6bl4 -o jsonpath='{.items[0].metadata.name}')

# Port-forward
kubectl port-forward pod/$POD 8080:8080
```

### Вариант 3: NodePort Service (для публичного доступа)

```bash
# Изменить service на NodePort
kubectl patch svc x0tta6bl4 -p '{"spec":{"type":"NodePort"}}'

# Получить порт
kubectl get svc x0tta6bl4
```

---

## 📊 ПРОВЕРКА

### Команды:

```bash
# Проверить pods
kubectl get pods -l app=x0tta6bl4

# Проверить service
kubectl get svc x0tta6bl4

# Проверить endpoints
kubectl get endpoints x0tta6bl4

# Проверить логи
kubectl logs -l app=x0tta6bl4 --tail=50

# Проверить health
curl http://localhost:8080/health
```

---

## 🎯 ДЛЯ ДЕМОНСТРАЦИИ

### Что показать:

1. **Health Check:**
   - http://localhost:8080/health ✅
   - Показывает что система работает

2. **Kubernetes:**
   ```bash
   kubectl get all -l app=x0tta6bl4
   ```

3. **Логи:**
   ```bash
   kubectl logs -l app=x0tta6bl4 --tail=50
   ```

---

## ✅ ГОТОВО!

**Demo environment работает!**

**Health endpoint доступен:** http://localhost:8080/health

**Следующий шаг:** Продолжить коммерциализацию!

