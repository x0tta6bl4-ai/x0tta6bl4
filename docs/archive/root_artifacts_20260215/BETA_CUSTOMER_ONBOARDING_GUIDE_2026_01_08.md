# Beta Customer Onboarding Guide
**Дата:** 2026-01-08  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Для:** Первый Beta Customer

---

## 🎯 Welcome to x0tta6bl4 Beta!

Спасибо, что присоединились к нашей beta программе! Этот документ поможет вам начать работу с x0tta6bl4.

---

## 📋 Pre-Onboarding Checklist

### Before You Start
- [ ] Review this guide
- [ ] Ensure you have network access to the staging environment
- [ ] Prepare your use case and requirements
- [ ] Schedule onboarding call (if not already scheduled)

---

## 🔐 Access Information

### Service Endpoint
- **Service URL:** `http://192.168.0.101:30913` 
- **Примечание:** `192.168.0.101` - это локальный IP-адрес машины, на которой запущен кластер.
- **Health Check:** `http://192.168.0.101:30913/health`
- **Metrics:** `http://192.168.0.101:30913/metrics`

### Authentication
- **Method:** Basic Authentication
- **Username:** `customer1`
- **Password:** `SjBUmS+bLKyoj0mf`

---

## 🚀 Quick Start

### 1. Health Check
```bash
curl --user "customer1:SjBUmS+bLKyoj0mf" http://[NODE_IP]:30913/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "3.4.0-fixed2",
  "timestamp": "..."
}
```

### 2. Basic API Call
```bash
# Example API call (adjust based on your API)
curl --user "customer1:SjBUmS+bLKyoj0mf" -X GET http://[NODE_IP]:30913/api/v1/status
```

### 3. Monitor Metrics
```bash
curl --user "customer1:SjBUmS+bLKyoj0mf" http://[NODE_IP]:30913/metrics
```

---

## 📊 Monitoring & Support

### Monitoring Dashboard
- **Prometheus:** (Access via port-forward)
  ```bash
  kubectl port-forward -n monitoring svc/prometheus 9090:9090
  # Open http://localhost:9090
  ```

- **Alertmanager:** (Access via port-forward)
  ```bash
  kubectl port-forward -n monitoring svc/alertmanager 9093:9093
  # Open http://localhost:9093
  ```

### Support Channels
- **Telegram Alerts:** @x0tta6bl4_allert_bot
- **Email:** support@x0tta6bl4.com (if configured)
- **On-Call:** See `docs/team/ON_CALL_ROTATION.md`

### Response Times
- **SEV-1 (Critical):** 5 minutes
- **SEV-2 (High):** 15 minutes
- **SEV-3 (Medium):** 1 hour
- **SEV-4 (Low):** 4 hours

---

## 🔧 Configuration

### Environment Variables
Key configuration options (if applicable):
- `X0TTA6BL4_PRODUCTION`: Set to `false` for staging
- `OQS_DISABLE_AUTO_INSTALL`: Set to `1` for staging
- Other environment-specific variables

### Network Configuration
- **Post-Quantum Cryptography:** ML-KEM-768, ML-DSA-65 enabled
- **Zero Trust:** SPIFFE/SPIRE configured
- **Self-Healing:** MAPE-K cycles active

---

## 📚 Documentation

### Key Documents
- `README.md` - Project overview
- `QUICK_START.md` - Quick start guide
- `TROUBLESHOOTING_QUICK_REFERENCE_2026_01_07.md` - Troubleshooting
- `PRODUCTION_RUNBOOKS_2026_01_07.md` - Operational procedures

### API Documentation
- API endpoints: (To be documented)
- Authentication: (To be documented)
- Rate limits: (To be documented)

---

## 🧪 Testing

### Test Scenarios
1. **Basic Connectivity**
   - Health check
   - API endpoint access
   - Metrics collection

2. **Post-Quantum Cryptography**
   - PQC handshake
   - Key exchange
   - Message encryption

3. **Self-Healing**
   - Pod failure recovery
   - Network partition handling
   - Resource exhaustion recovery

4. **Performance**
   - Response time
   - Throughput
   - Resource usage

---

## 📝 Feedback Collection

### Weekly Check-ins
- **Schedule:** Weekly (or as needed)
- **Format:** Email or call
- **Topics:**
  - Usage patterns
  - Issues encountered
  - Feature requests
  - Performance feedback

### Feedback Channels
- **Email:** feedback@x0tta6bl4.com (if configured)
- **Telegram:** @x0tta6bl4_allert_bot (for urgent issues)
- **Support Ticket:** (If system is set up)

---

## ⚠️ Known Limitations (Beta)

### Current Limitations
- **Scale:** Limited to beta testing load
- **Features:** Some features may be in development
- **Support:** High-touch support during beta
- **SLA:** Best effort (not production SLA)

### Planned Improvements
- Production-grade SLA
- Additional features
- Performance optimizations
- Enhanced monitoring

---

## 🚨 Troubleshooting

### Common Issues

#### Service Unavailable
```bash
# Check pod status
kubectl get pods -n x0tta6bl4-staging

# Check service
kubectl get svc -n x0tta6bl4-staging

# Check logs
kubectl logs -n x0tta6bl4-staging [pod-name]
```

#### High Latency
- Check network connectivity
- Review metrics in Prometheus
- Check for resource constraints

#### Authentication Issues
- Verify credentials
- Check token expiration
- Review authentication logs

### Getting Help
1. Check `TROUBLESHOOTING_QUICK_REFERENCE_2026_01_07.md`
2. Contact support via Telegram or email
3. Escalate if issue is critical (SEV-1/2)

---

## 📅 Onboarding Timeline

### Week 1
- **Day 1:** Initial setup and access
- **Day 2-3:** Testing and exploration
- **Day 4-5:** Feedback collection
- **Day 7:** First check-in call

### Week 2+
- **Weekly:** Check-in calls
- **Ongoing:** Support and feedback
- **As needed:** Issue resolution

---

## ✅ Success Criteria

### For Beta Customer
- [ ] Successfully access the service
- [ ] Complete basic test scenarios
- [ ] Provide initial feedback
- [ ] Report any issues encountered

### For x0tta6bl4 Team
- [ ] Customer successfully onboarded
- [ ] All access issues resolved
- [ ] Monitoring active
- [ ] Support channels established

---

## 📞 Contact Information

### Support
- **Primary:** Telegram @x0tta6bl4_allert_bot
- **Email:** support@x0tta6bl4.com (if configured)
- **On-Call:** See `docs/team/ON_CALL_ROTATION.md`

### Escalation
- **Team Lead:** For technical issues
- **CTO:** For critical decisions

---

## 🎉 Next Steps

1. **Review this guide**
2. **Schedule onboarding call** (if not already scheduled)
3. **Receive access credentials**
4. **Start testing**
5. **Provide feedback**

---

**Welcome to x0tta6bl4 Beta!** 🚀

**Last Updated:** 2026-01-08  
**Version:** 1.0  
**Status:** Ready for Beta Customer Onboarding


