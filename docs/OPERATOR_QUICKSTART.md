# 🚀 x0tta6bl4 Node Operator Quickstart

Join the world's first autonomous, post-quantum, self-healing Mesh-as-a-Service network. Earn **X0T** tokens by providing resilient transport and bypassing DPI.

---

## 🛠 One-Command Join (Docker)

Run the following command to launch a lightweight mesh node on any Linux/Mac/Windows machine:

```bash
docker run -d \
  --name x0t-agent \
  --restart always \
  --network host \
  -e NODE_ID="your-unique-node-name" \
  -e API_URL="https://api.x0tta6bl4.ai" \
  -e JOIN_TOKEN="demo-public-token" \
  x0tta6bl4/x0t-agent:latest
```

---

## 💎 Rewards & Economics

By running a node, you participate in the **x0tta6bl4 DAO**.
* **Token Address (Base Sepolia):** `0xe1F4709A2Cf3F85D88731E4859416cCAdc06190C`
* **Base Rate:** 0.0001 X0T per successfully routed packet.
* **Uptime Bonus:** Additional rewards for 99.9% availability, verified by MAPE-K causal proofs.

---

## 🔒 Security Posture

* **Post-Quantum:** All node-to-node traffic is encrypted using NIST-standard Kyber/Dilithium.
* **Censorship Resistance:** Built-in **Ghost Pulse** eBPF module obfuscates traffic to bypass Deep Packet Inspection (DPI).
* **Zero Trust:** Node identity is managed via SPIFFE/SPIRE with mandatory hardware attestation.

---

## 📊 Monitoring Your Node

Once running, you can verify your node's status via our decentralized dashboard:
`https://dashboard.x0tta6bl4.ai/node/<your-node-id>`

---

## 📜 Full Documentation

For advanced configuration (eBPF tuning, manual Go binary build, PQC key rotation), visit the [Full Operator Handoff](docs/architecture/OPERATOR_HANDOFF.md).

*Built with cryptographic honesty. Verified by machines, not marketing.*
