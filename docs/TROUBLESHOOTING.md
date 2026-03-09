# x0tta6bl4 Troubleshooting Guide

## 1. Network & eBPF Issues

### 1.1 eBPF Loader Fails to Attach (`-EEXIST` or `exit status 2`)
**Symptoms:** 
- The `ebpf/prod/loader` fails with "Error: XDP program already attached."
- High packet loss immediately after service restart.

**Cause:** 
The XDP program is pinned in the BPF filesystem (`/sys/fs/bpf/x0tta6bl4-prod`) and still attached to the NIC.

**Resolution:**
1. Detach from interface:
   ```bash
   sudo ip link set dev <interface> xdp off
   ```
2. Remove old BPF pins:
   ```bash
   sudo rm -rf /sys/fs/bpf/x0tta6bl4-prod
   ```
3. Restart the eBPF loader or systemd service.

### 1.2 Low Throughput / PPS (Packet Per Second)
**Symptoms:**
- The benchmark (`ebpf/prod/benchmark-harness.sh`) reports less than 1.0M PPS.
- Heavy latency under load.

**Cause:**
Your Network Interface Card (NIC) driver does not support Native XDP (e.g., Realtek `r8169`). Generic XDP is slow and falls back to standard kernel processing.

**Resolution:**
- Check driver with `ethtool -i <interface>`.
- Use an Intel (ixgbe/i40e) or Mellanox (mlx5_core) NIC for production nodes to unlock 5M-8M PPS.

---

## 2. API & Control Plane

### 2.1 Connection Refused / 404 on API Gateway
**Symptoms:**
- The Dashboard UI fails to load.
- Services log "Connection refused" when hitting `http://localhost:8000`.

**Cause:**
- The port configuration changed, or mTLS is blocking requests.
- `importlib` failed silently in `app.py` due to missing dependencies.

**Resolution:**
- Check logs: `docker logs x0tta6bl4-control-plane`.
- If a router failed to load, you'll see a `CRITICAL: Failed to import required MaaS router`. Ensure `bcrypt`, `liboqs`, and other dependencies are installed.
- Ensure the production stack is using port `8010` (updated in Docker Compose).

### 2.2 Redis Connection Failed
**Symptoms:**
- API response: "Redis connection failed. Falling back to memory."
- Mesh telemetry is resetting on API restarts.

**Cause:**
Redis container is not running or port 6379 is blocked.

**Resolution:**
- Ensure `redis` service in `docker-compose.production.yml` is healthy.
- Check `REDIS_URL` in your `.env`.

---

## 3. Cryptography & Security

### 3.1 PQC Token Signer in Fallback Mode
**Symptoms:**
- Log states: `⚠️ PQC-подпись токенов в режиме ожидания (fallback active).`
- Nodes complain about missing ML-DSA-65 signatures.

**Cause:**
`liboqs-python` is missing, or the C-library is outdated (version mismatch).

**Resolution:**
- Verify liboqs version (must match `0.14.0` or `0.15.0`).
- Check host OS: `sudo apt install liboqs-dev`.

### 3.2 Forgot Admin Password
**Symptoms:**
- Cannot login to the dashboard.

**Resolution:**
Run the secure rescue script from the project root:
```bash
python3 reset_admin_password.py
```
This uses bcrypt to securely overwrite the stored hash.

---

## 4. Supply Chain & SBOM

### 4.1 Node marked as COMPROMISED
**Symptoms:**
- Dashboard marks a node with a red "MISMATCH" or "COMPROMISED" label.

**Cause:**
The node's binary hash does not match the signed SBOM in the registry.

**Resolution:**
- Reinstall the agent on the target node.
- If this is a new version deployment, generate a new SBOM using `scripts/demo/seed_supply_chain.py` (for demo) or your CI/CD pipeline, and register it via the Supply Chain API.