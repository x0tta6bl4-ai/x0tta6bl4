# 👥 TEAM TRAINING GUIDE - x0tta6bl4 v3.0.0

**Дата:** 27 декабря 2025  
**Версия:** 3.0.0  
**Статус:** ✅ **PRODUCTION LIVE**

---

## 🎯 ЦЕЛЬ ОБУЧЕНИЯ

Обучить команду работе с x0tta6bl4 v3.0.0 в production:
- Мониторинг системы
- Troubleshooting
- Emergency procedures
- Best practices

---

## 📋 ПРОГРАММА ОБУЧЕНИЯ

### 1. Система Overview (30 мин)

#### Архитектура
- x0tta6bl4 v3.0.0 компоненты
- VPN интеграция
- Мониторинг (Prometheus/Grafana)
- Nginx reverse proxy

#### Production Environment
- VPS: 89.125.1.107
- Порты и сервисы
- Ресурсы (RAM, Disk, CPU)

### 2. Мониторинг (30 мин)

#### Health Checks
```bash
# Health endpoint
curl http://89.125.1.107/health

# Metrics
curl http://89.125.1.107/metrics

# Container status
ssh root@89.125.1.107 'docker ps | grep x0t-node'
```

#### Prometheus/Grafana
- Доступ к Grafana: http://89.125.1.107:3000
- Prometheus: http://89.125.1.107:9091
- Key metrics to watch

### 3. Troubleshooting (30 мин)

#### Common Issues
1. **Health endpoint не отвечает**
   - Проверить container: `docker ps`
   - Проверить логи: `docker logs x0t-node -f`
   - Перезапустить: `docker restart x0t-node`

2. **VPN не работает**
   - Проверить X-UI: `systemctl status x-ui`
   - Проверить порты: `netstat -tulpn | grep 39829`
   - Перезапустить: `systemctl restart x-ui`

3. **Высокое использование ресурсов**
   - Проверить процессы: `docker stats x0t-node`
   - Проверить логи на ошибки
   - Оптимизировать если нужно

### 4. Emergency Procedures (30 мин)

#### Rollback
```bash
# Если нужно откатиться
ssh root@89.125.1.107
docker stop x0t-node
docker run -d --name x0t-node-restored <backup-image>
```

#### Backup
```bash
# Создать backup
docker commit x0t-node x0t-node-backup-$(date +%Y%m%d)
```

#### Restart Services
```bash
# Restart x0tta6bl4
docker restart x0t-node

# Restart VPN
systemctl restart x-ui

# Restart Nginx
systemctl restart nginx
```

---

## 🔧 ИНСТРУМЕНТЫ

### Monitoring Scripts
```bash
# Production monitoring
./scripts/monitor_production.sh 89.125.1.107 root

# Collect metrics
./scripts/collect_baseline_metrics.sh 89.125.1.107 root

# Performance analysis
./scripts/analyze_performance.sh
```

### Quick Commands
```bash
# Health check
curl http://89.125.1.107/health

# View logs
ssh root@89.125.1.107 'docker logs x0t-node -f'

# Container stats
ssh root@89.125.1.107 'docker stats x0t-node'

# System resources
ssh root@89.125.1.107 'free -h && df -h'
```

---

## 📊 KEY METRICS TO WATCH

### Health
- Health endpoint: `{"status":"ok"}`
- Response time: < 100ms

### Resources
- Memory: < 500MB (container)
- CPU: < 50% average
- Disk: < 80% used

### Performance
- Error rate: < 0.1%
- Uptime: > 99.9%
- Response time: < 200ms (p95)

---

## 🚨 ALERT THRESHOLDS

### Critical
- Health endpoint down
- Container stopped
- VPN down
- Disk > 90%

### Warning
- Memory > 80%
- CPU > 70%
- Error rate > 1%
- Response time > 500ms

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### Documentation
- `VPS_DEPLOYMENT_COMPLETE.md` - Deployment guide
- `NEXT_STEPS.md` - Next steps
- `PRODUCTION_LAUNCH_COMPLETE.md` - Launch status
- `PERFORMANCE_BASELINE_REPORT.md` - Baseline metrics

### Scripts
- `scripts/monitor_production.sh` - Monitoring
- `scripts/collect_baseline_metrics.sh` - Metrics collection
- `scripts/analyze_performance.sh` - Performance analysis

---

## ✅ TRAINING CHECKLIST

- [ ] System overview understood
- [ ] Monitoring tools familiar
- [ ] Troubleshooting procedures known
- [ ] Emergency procedures practiced
- [ ] Key metrics identified
- [ ] Alert thresholds understood

---

**Дата:** 27 декабря 2025  
**Статус:** ✅ **READY FOR TRAINING**

