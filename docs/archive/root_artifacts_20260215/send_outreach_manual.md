# 📧 Руководство по отправке Outreach Emails (Ручной режим)

## Быстрый старт

### Шаг 1: Откройте Gmail
Перейдите на https://mail.google.com и войдите в аккаунт.

### Шаг 2: Отправьте 5 emails

Ниже готовые шаблоны для копирования:

---

#### Email #1: Proton (Andy Yen)

**To:** `andy.yen@proton.ch`  
**Subject:** `Post-Quantum Mesh for Proton's 100M+ Users`

```
Hi Andy,

Proton protects 100M+ users (CERN roots align with x0tta6bl4's self-healing architecture). 
As quantum computers threaten current encryption (PGP/WireGuard), I built x0tta6bl4 — 
the first production-ready mesh network with NIST-standard post-quantum cryptography (ML-KEM-768).

Key benefits for Proton:
- Quantum-safe encryption (protected for 50+ years)
- Self-healing architecture (MTTR <3 minutes)
- NIST FIPS 203/204 compliant

Would you be open to a 15-minute demo call this week?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net
```

---

#### Email #2: EFF (Cindy Cohn)

**To:** `cindy@eff.org`  
**Subject:** `Uncensorable Mesh for EFF Activists`

```
Hi Cindy,

EFF fights surveillance and censorship. I built x0tta6bl4 — a PQC self-healing mesh network 
that gives activists blackout-proof communications, even during internet shutdowns.

Key features:
- Traffic obfuscation (looks like HTTPS)
- Self-healing (survives node failures, MTTR <3 minutes)
- Post-quantum crypto (NIST FIPS 203/204)
- DAO governance (decentralized control)

I'd love to show you how it works. 15-minute demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net
```

---

#### Email #3: Mullvad VPN (Jan Jonsson)

**To:** `jan@mullvad.net`  
**Subject:** `Quantum-Safe Tunnel Mesh for Mullvad`

```
Hi Jan,

Mullvad leads privacy with no-logs VPN. As WireGuard quantum vulnerability discussions continue, 
I built x0tta6bl4 — a quantum-safe mesh network with NIST-standard post-quantum cryptography.

Key benefits:
- ML-KEM-768 encryption (NIST FIPS 203)
- Self-healing architecture (MTTR <3 minutes)
- Mesh networking (no single point of failure)

Interested in a demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net
```

---

#### Email #4: Access Now (Brett Solomon)

**To:** `brett@accessnow.org`  
**Subject:** `Unblockable Mesh for #KeepItOn Campaign`

```
Hi Brett,

Access Now fights internet shutdowns in 50+ countries (#KeepItOn). I built x0tta6bl4 — 
a mesh network that's impossible to block, even during blackouts.

Key features:
- Traffic obfuscation (looks like HTTPS)
- Self-healing (survives node failures)
- Post-quantum crypto (future-proof)
- Works even when ISPs are blocked

I'd love to show you how it works. 15-minute demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net
```

---

#### Email #5: Signal Foundation (Meredith Whittaker)

**To:** `meredith@signal.org`  
**Subject:** `Self-Healing Mesh Backend for Signal`

```
Hi Meredith,

Signal sets the privacy standard for 100M+ users. As you explore mesh extensions and PQC migration, 
I built x0tta6bl4 — a self-healing mesh network with NIST-standard post-quantum cryptography.

Key benefits:
- ML-KEM-768 encryption (NIST FIPS 203)
- Self-healing architecture (MTTR <3 minutes)
- Mesh networking (decentralized backend)
- DAO governance (community control)

Would you be open to a 15-minute demo call?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net
```

---

## ⚙️ Настройки отправки

### Для каждого email:
1. ✅ **BCC:** Добавьте себя в скрытую копию для отслеживания
2. ✅ **Signature:** Убедитесь, что подпись не дублируется
3. ✅ **Проверка:** Перечитайте перед отправкой

---

## ⏰ Лучшее время отправки

| Компания | Часовой пояс | Лучшее время (местное) | Лучшее время (CET) |
|----------|--------------|------------------------|-------------------|
| Proton | CET (Швейцария) | 9:00-11:00 | 9:00-11:00 |
| EFF | PST (США) | 9:00-11:00 | 18:00-20:00 |
| Mullvad | CET (Швеция) | 9:00-11:00 | 9:00-11:00 |
| Access Now | CET (Бельгия) | 9:00-11:00 | 9:00-11:00 |
| Signal | PST (США) | 9:00-11:00 | 18:00-20:00 |

---

## 📊 Обновление CRM

После отправки каждого email, обновите [`crm_outreach_tracking.csv`](crm_outreach_tracking.csv):

1. Откройте CSV файл
2. Найдите строку с компанией
3. Обновите поля:
   - `Status`: "Sent"
   - `Date Sent`: текущая дата (YYYY-MM-DD)

---

## 🔔 Follow-up напоминания

Установите напоминания на **5 февраля 2026** (через 5 дней):

- Если нет ответа → отправьте follow-up
- Максимум 2 follow-ups
- Если нет ответа после 2-го follow-up → move on

### Follow-up template:
```
Subject: Re: [Original Subject]

Hi [Name],

Just following up on my email from last week about x0tta6bl4's post-quantum 
mesh network. Would love to show you a quick 15-minute demo if you're interested.

Best,
[Your Name]
```

---

## ✅ Чеклист после отправки

- [ ] Proton email отправлен
- [ ] EFF email отправлен
- [ ] Mullvad VPN email отправлен
- [ ] Access Now email отправлен
- [ ] Signal Foundation email отправлен
- [ ] CRM обновлен (все 5 записей)
- [ ] Напоминания на follow-up установлены
- [ ] Gmail labels/tags настроены для отслеживания

---

## 📈 Ожидаемые метрики

| Метрика | Ожидание |
|---------|----------|
| Открываемость | 40-50% |
| Ответы | 10-20% (1-2 ответа) |
| Demo calls | 0-1 |

---

**Готово к отправке!** 🚀
