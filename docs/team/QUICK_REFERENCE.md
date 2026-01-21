# ⚡ QUICK REFERENCE - x0tta6bl4 v3.0.0

**Production VPS:** 89.125.1.107

---

## 🔗 URLS

```
Main:        http://89.125.1.107
Health:      http://89.125.1.107/health
Metrics:     http://89.125.1.107/metrics
Grafana:     http://89.125.1.107:3000
Prometheus:  http://89.125.1.107:9091
VPN Panel:   http://89.125.1.107:628
```

---

## 🔧 QUICK COMMANDS

### Health Check
```bash
curl http://89.125.1.107/health
```

### Container Status
```bash
ssh root@89.125.1.107 'docker ps | grep x0t-node'
```

### View Logs
```bash
ssh root@89.125.1.107 'docker logs x0t-node -f'
```

### Restart Services
```bash
# x0tta6bl4
ssh root@89.125.1.107 'docker restart x0t-node'

# VPN
ssh root@89.125.1.107 'systemctl restart x-ui'

# Nginx
ssh root@89.125.1.107 'systemctl restart nginx'
```

### System Resources
```bash
ssh root@89.125.1.107 'free -h && df -h'
```

---

## 🚨 EMERGENCY

### Health Down
```bash
ssh root@89.125.1.107 'docker restart x0t-node'
```

### VPN Down
```bash
ssh root@89.125.1.107 'systemctl restart x-ui'
```

### High Memory
```bash
ssh root@89.125.1.107 'docker stats x0t-node'
# If needed: docker restart x0t-node
```

---

## 📊 MONITORING

### Run Monitoring
```bash
./scripts/monitor_production.sh 89.125.1.107 root
```

### Collect Metrics
```bash
./scripts/collect_baseline_metrics.sh 89.125.1.107 root
```

---

**Дата:** 27 декабря 2025

