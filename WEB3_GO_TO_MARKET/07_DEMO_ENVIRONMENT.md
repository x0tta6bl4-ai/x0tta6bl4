# 🎬 DEMO ENVIRONMENT SETUP

**Для:** Client demos и sales calls  
**Статус:** ✅ Ready

---

## QUICK START

```bash
# 1. Start all services
cd /mnt/AC74CC2974CBF3DC
docker-compose up -d

# 2. Start Hardhat node (blockchain)
cd src/dao/contracts
npx hardhat node &

# 3. Start main API
cd /mnt/AC74CC2974CBF3DC
source .venv/bin/activate
python3 -m src.core.app

# 4. Verify
curl http://localhost:8080/health
```

---

## DEMO CHECKLIST

### Before Demo
- [ ] All services running
- [ ] Hardhat node running (blockchain)
- [ ] API responding on :8080
- [ ] Mesh network online (Yggdrasil)
- [ ] Test PQC handshake works
- [ ] Test blockchain interaction works
- [ ] Screen share tested
- [ ] Demo script reviewed

### During Demo
- [ ] Show mesh topology
- [ ] Demonstrate PQC handshake
- [ ] Show self-healing (kill node)
- [ ] Show blockchain (token balance, staking)
- [ ] Show governance (proposal creation)
- [ ] Answer questions

### After Demo
- [ ] Send follow-up email
- [ ] Share demo recording (if recorded)
- [ ] Update CRM tracker
- [ ] Schedule next steps

---

## DEMO SCRIPT POINTS

1. **Mesh Network** (2 min)
   - Show live topology
   - Demonstrate resilience

2. **Post-Quantum Crypto** (3 min)
   - ML-KEM-768 handshake
   - NIST compliance

3. **Self-Healing** (2 min)
   - Kill node
   - Auto-recovery

4. **Blockchain** (3 min)
   - Token contract
   - Governance proposal
   - Real transactions

5. **Integration** (2 min)
   - API examples
   - SDK usage

---

## TROUBLESHOOTING

### API not responding
```bash
docker ps  # Check containers
docker logs x0tta6bl4-control-plane-staging
```

### Blockchain not working
```bash
ps aux | grep hardhat
cd src/dao/contracts && npx hardhat node
```

### Mesh offline
```bash
sudo systemctl status yggdrasil
sudo systemctl start yggdrasil
```

---

**Last Updated:** 1 января 2026

