# 🎬 WEB3 DEMO SCRIPT

**Продолжительность:** 15 минут  
**Цель:** Показать value → Закрыть на следующий шаг  
**Формат:** Screen share + talking

---

## PRE-DEMO CHECKLIST

```
□ Research компанию (website, blog, twitter) — 10 мин
□ Найти недавние новости о них — 5 мин
□ Подготовить персонализированные примеры — 5 мин
□ Проверить demo environment работает — 5 мин
□ Тест screen share — 2 мин
□ Подготовить pricing options — 2 мин
□ Включить запись (с разрешения) — 1 мин
```

---

## DEMO STRUCTURE

### INTRO (0-2 мин)

```
"Thanks for taking the time, [Name]. Before I dive in, I want to make sure 
I show you the most relevant parts. Quick question:

What's your biggest infrastructure concern right now — 
is it security, reliability, or scaling?"

[LISTEN — adjust demo based on answer]

"Perfect. Let me show you exactly how x0tta6bl4 addresses [their concern]."
```

**Цель:** Понять их приоритет, персонализировать demo.

---

### PROBLEM SETUP (2-3 мин)

```
"So here's the challenge most Web3 teams face:

[If Linux Infrastructure/DevOps]:
Your Linux servers use standard BGP/routing. When one node fails,
recovery takes 2-3 hours. x0tta6bl4 reduces this to 3-5 seconds
using eBPF-based self-healing mesh.

[If L2/DeFi]:
Your sequencer/oracle nodes communicate over standard TLS. 
When quantum computers mature — and NIST says 5-10 years — 
that's vulnerable. And migration then will be painful.

[If Infrastructure]:
Your customers trust you with their most critical operations.
But your node-to-node communication is only as secure as today's crypto.

[If DAO]:
True decentralization means no single point of failure.
But most infra still has central dependencies.

x0tta6bl4 solves this today, not when it's an emergency."
```

---

### LIVE DEMO (3-10 мин)

#### Part 1: Mesh Network (2 мин)

```
[Screen: Terminal or Dashboard]

"Let me show you a live mesh network. These are 5 nodes running right now.

[Show topology visualization]

Notice there's no central server. Each node can reach any other node 
through multiple paths. If one goes down..."

[Kill a node]

"...traffic automatically reroutes. No manual intervention.
That's self-healing in action."
```

#### Part 2: Post-Quantum Crypto (3 мин)

```
[Screen: Terminal showing handshake]

"Now the key part — post-quantum security. Watch this handshake:

[Run PQC handshake demo]

See that? ML-KEM-768 — that's NIST's new standard, FIPS 203.
This key exchange is quantum-resistant TODAY.

Even if someone records this traffic now and decrypts it 
with a quantum computer in 10 years — they get nothing.

[If technical audience]:
We support ML-KEM-768 for key encapsulation, ML-DSA-65 for signatures.
Full NIST FIPS 203/204 compliance."
```

#### Part 3: Self-Healing (2 мин)

```
[Screen: Monitoring dashboard]

"Let me show you the self-healing system.

[Trigger an anomaly]

See that alert? The system detected it in [X] seconds — that's MTTD.
Now watch the automatic response...

[Show recovery]

Recovered in under 3 minutes. No human touched anything.
This is MAPE-K — Monitor, Analyze, Plan, Execute, Knowledge.
ML-powered, getting smarter over time."
```

#### Part 4: Integration (3 мин)

```
[Screen: Code/API]

"Integration is straightforward. Here's how you'd connect:

[Show simple code example]

```python
from x0tta6bl4 import MeshClient

client = MeshClient(
    node_id="your-node",
    pqc_enabled=True,
    auto_heal=True
)

# That's it. You're quantum-safe.
await client.connect()
```

We have SDKs for Python, Node.js, Go. 
Documentation is comprehensive — you can have a POC running in a day."
```

---

### RELEVANCE TO THEM (10-12 мин)

```
"Now let me connect this to [Company] specifically.

[If L2]:
Your sequencer communicates with thousands of nodes. 
With x0tta6bl4, all that communication is quantum-safe.
When competitors start worrying about Q-day, you're already protected.

[If DeFi]:
Your oracle feeds and keeper bots are critical. 
One compromised message could mean millions lost.
Quantum-safe channels eliminate that future risk.

[If Infrastructure]:
You could offer this to your customers as a feature.
'Quantum-ready infrastructure' becomes a differentiator.

[If DAO]:
Your governance is decentralized. 
Your infrastructure should be too.
Mesh + DAO-native governance integration = perfect fit."
```

---

### PRICING & NEXT STEPS (12-15 мин)

```
"Let me talk about how we work with teams like yours.

We have three tiers:

• Starter — $500/month — up to 10 nodes
  Good for POC or small deployment

• Professional — $2,000/month — up to 50 nodes  
  Most teams start here

• Enterprise — $5,000+/month — unlimited, custom SLA
  For production at scale

For [Company], I'd suggest [Tier] because [reason].

[Pause — let them react]

What would make sense as a next step? 
We could do a technical deep-dive with your team, 
or I can send a proposal for a pilot?"
```

---

### HANDLING OBJECTIONS

| Objection | Response |
|-----------|----------|
| "Too expensive" | "What's your budget? We have flexible options. Also, what's the cost of a security incident?" |
| "Need to think about it" | "Totally understand. What specifically? I can clarify now or send more info." |
| "Not the right time" | "When would be better? I'll set a reminder to follow up." |
| "Need to talk to team" | "Who else should be involved? I'm happy to do another call with them." |
| "Already have solution" | "What are you using? How does it handle post-quantum?" |
| "Is PQC really necessary now?" | "NIST says quantum computers will break current crypto by 2030-2035. Migration takes time. Starting now is prudent." |

---

### CLOSING

```
"Great talking with you, [Name]. 

To summarize what we discussed:
• [Key point 1 they cared about]
• [Key point 2 they cared about]
• [Next step agreed upon]

I'll send [follow-up item] by [time].

Any other questions before we wrap?"

[After call — send follow-up email within 2 hours]
```

---

## POST-DEMO FOLLOW-UP EMAIL

```
Subject: x0tta6bl4 demo follow-up + [next step]

Hi [Name],

Great speaking with you today. As promised:

**Key points we covered:**
• [Point 1]
• [Point 2]
• [Point 3]

**Next step:** [What you agreed on]

**Resources:**
• Demo recording: [link if recorded]
• Documentation: [link]
• Technical specs: [link]

I'll [next action] by [date]. Let me know if you need anything else.

[Your name]
```

---

## DEMO ENVIRONMENT SETUP

### Before Demo Day

```bash
# 1. Start demo environment
docker-compose -f docker-compose.demo.yml up -d

# 2. Verify all nodes running
curl http://localhost:8080/health

# 3. Check mesh topology
curl http://localhost:8080/mesh/topology

# 4. Test PQC handshake
python -m src.security.pqc.demo_handshake

# 5. Open monitoring dashboard
open http://localhost:3000/d/mesh-dashboard
```

### Demo Commands Cheatsheet

```bash
# Show mesh topology
GET /mesh/topology

# Trigger node failure (for self-healing demo)
POST /debug/kill-node/node-3

# Show PQC handshake
python scripts/demo_pqc_handshake.py

# Show metrics
GET /metrics
```

---

## 🎯 SUCCESS METRICS

| Metric | Target |
|--------|--------|
| Demo completion rate | 90%+ |
| "Interested" at end | 70%+ |
| Next step scheduled | 50%+ |
| Proposal requested | 30%+ |

---

**Practice this script 3 times before first real demo!**

