# 🌐 x0tta6bl4 Demo Access Information

**Дата:** 1 января 2026  
**Статус:** 🟢 **DEMO RUNNING**

---

## ✅ DEMO ЗАПУЩЕН

### Port-Forward Active

Port-forward запущен в фоновом режиме.

**Доступ к demo:**
- **URL:** http://localhost:8080
- **Status:** ✅ Running

---

## 🔗 ДОСТУП

### Локальный доступ

```bash
# Открыть в браузере
http://localhost:8080
```

### Проверка статуса

```bash
# Проверить, что port-forward работает
curl http://localhost:8080

# Или в браузере
open http://localhost:8080
```

---

## 📊 ТЕКУЩИЙ СТАТУС

### Deployment

```bash
# Проверить pods
kubectl get pods -l app=x0tta6bl4

# Проверить service
kubectl get svc x0tta6bl4

# Проверить deployment
kubectl get deployment x0tta6bl4-demo
```

### Логи

```bash
# Посмотреть логи
kubectl logs -l app=x0tta6bl4 --tail=50 -f
```

---

## 🎯 ДЛЯ ДЕМОНСТРАЦИИ

### Что показать клиентам:

1. **Live Demo:**
   - URL: http://localhost:8080
   - Показать работающую систему
   - Показать health checks

2. **Kubernetes Deployment:**
   ```bash
   kubectl get all -l app=x0tta6bl4
   ```

3. **Self-Healing:**
   - Показать автоматическое восстановление
   - Показать health checks

4. **Performance:**
   - Показать benchmark results
   - Показать метрики

---

## 🔧 УПРАВЛЕНИЕ

### Остановить port-forward

```bash
# Найти процесс
ps aux | grep "kubectl port-forward"

# Остановить
pkill -f "kubectl port-forward"
```

### Перезапустить port-forward

```bash
# Остановить текущий
pkill -f "kubectl port-forward"

# Запустить заново
kubectl port-forward svc/x0tta6bl4 8080:80
```

### Использовать другой порт

```bash
# Если 8080 занят
kubectl port-forward svc/x0tta6bl4 8081:80
# Тогда доступ: http://localhost:8081
```

---

## 📝 СЛЕДУЮЩИЕ ШАГИ

### 1. Настроить публичный доступ

Для публичного доступа (demo.x0tta6bl4.dev):

```bash
# Применить ingress
kubectl apply -f deployment/kubernetes/ingress.yaml

# Проверить
kubectl get ingress
```

### 2. Записать Demo Video

Использовать `DEMO_VIDEO_SCRIPT.md` для записи видео.

### 3. Начать Outreach

Использовать `SALES_EMAIL_TEMPLATE.md` для отправки emails.

---

## ✅ CHECKLIST

- [x] Demo environment deployed
- [x] Port-forward запущен
- [x] Доступ работает (http://localhost:8080)
- [ ] Публичный доступ настроен (опционально)
- [ ] Demo video записан
- [ ] Первые emails отправлены

---

**🎉 DEMO ДОСТУПЕН! 🚀**

*Откройте: http://localhost:8080*

