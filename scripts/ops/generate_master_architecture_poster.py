#!/usr/bin/env python3
"""
x0tta6bl4 Master Architecture Poster & Diagrams Generator (EN & RU).

Generates:
1. docs/assets/x0tta6bl4_architecture_master.svg (English SVG Poster)
2. docs/assets/x0tta6bl4_architecture_master_ru.svg (Russian SVG Poster)
3. docs/assets/x0tta6bl4_full_architecture.mermaid (English Mermaid Diagram)
4. docs/assets/x0tta6bl4_full_architecture_ru.mermaid (Russian Mermaid Diagram)
5. docs/architecture/SYSTEM_ARCHITECTURE_MAP.md (English Sitemap document)
6. docs/ru/SYSTEM_ARCHITECTURE_MAP_RU.md (Russian Sitemap document)

Compliance: Web Application & Graphic Aesthetics Guidelines.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT / "docs" / "assets"
ARCH_DIR = ROOT / "docs" / "architecture"
RU_DIR = ROOT / "docs" / "ru"


def generate_master_poster() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ARCH_DIR.mkdir(parents=True, exist_ok=True)
    RU_DIR.mkdir(parents=True, exist_ok=True)

    print("🎨 Generating Master Architecture Assets (EN & RU) for x0tta6bl4...")

    # 1. Generate Full Mermaid Diagram (English)
    mermaid_file = ASSETS_DIR / "x0tta6bl4_full_architecture.mermaid"
    mermaid_content = """graph TB
    subgraph L11["Layer 11: Verification & Truth Matrix"]
        VM["VERIFICATION_MATRIX.md<br/>(3-Tier Taxonomy: ✅ VERIFIED / 🟡 LAB / ⚪ TARGET)"]
    end

    subgraph L10["Layer 10: 24/7 Autopilot Daemons"]
        AD["run_self_healing_autopilot_cycle.py"]
        CD["self_healing_code_daemon.py"]
    end

    subgraph L9["Layer 9: User Service & Telegram Interface"]
        TB["Telegram Bot (telegram_bot_simple.py)"]
        DB["SQLite WAL Database (database.py)"]
    end

    subgraph L8["Layer 8: Proxy & Stealth Dataplane"]
        XR["Xray VLESS + Reality (NL VPS 89.125.1.107)"]
        MSK["Relay Node (MSK VPS 84.54.47.103)"]
    end

    subgraph L7["Layer 7: Post-Quantum Messaging (x0tMQ)"]
        XMQ["x0tMQ Protocol (src/swarm/)"]
        FRAME["X0tMQMAPEKFrame (NIST ML-DSA-65 Signed)"]
    end

    subgraph L6["Layer 6: Self-Healing MAPE-K Engine"]
        MON["1. Monitor (MAPEKMonitor)"]
        GNN["2. Analyze (GraphSAGE GNN Anomaly Detector)"]
        PLN["3. Plan (Bio-Evo & DPI Healing Planner)"]
        EXE["4. Execute (MAPEKExecutor)"]
    end

    subgraph L5["Layer 5: Zero-Trust SPIRE Identity"]
        SPIRE["SPIRE Server + Workload API"]
        SVID["SVIDSigner & PQCSVIDRotator"]
    end

    subgraph L4["Layer 4: Post-Quantum Cryptography Core"]
        KEM["ML-KEM-768 (NIST FIPS 203 Key Exchange)"]
        DSA["ML-DSA-65 (NIST FIPS 204 Digital Signature)"]
    end

    subgraph L3["Layer 3: Kernel eBPF/XDP Dataplane"]
        XDP["eBPF/XDP Driver Hook (6.66 ns decision)"]
        RING["AF_XDP Ring Buffers & ebpf_to_x0tmq_bridge.py"]
    end

    subgraph L2["Layer 2: Multi-Region Mesh Topology"]
        P2P["Libp2p / WireGuard P2P Tunnels"]
        PBFT["PBFT Delphi Consensus"]
    end

    subgraph L1["Layer 1: Bare-Metal Hardware & NICs"]
        NIC["Physical 10Gbps NIC / Virtual Interface"]
    end

    TB --> DB
    TB --> XR
    XR <--> MSK
    NIC --> XDP
    XDP --> RING
    RING --> XMQ
    XMQ --> FRAME
    FRAME --> SPIRE
    SPIRE --> SVID
    SVID --> KEM
    KEM --> DSA
    DSA --> MON
    MON --> GNN
    GNN --> PLN
    PLN --> EXE
    EXE --> P2P
    P2P --> PBFT
    AD --> XR
    CD --> VM
"""
    mermaid_file.write_text(mermaid_content, encoding="utf-8")
    print(f"  ✓ Generated: {mermaid_file}")

    # 1b. Generate Full Mermaid Diagram (Russian)
    mermaid_ru_file = ASSETS_DIR / "x0tta6bl4_full_architecture_ru.mermaid"
    mermaid_ru_content = """graph TB
    subgraph L11["Слой 11: Единая Матрица Доказательств"]
        VM["VERIFICATION_MATRIX.md<br/>(3 Уровня: ✅ VERIFIED / 🟡 LAB / ⚪ TARGET)"]
    end

    subgraph L10["Слой 10: Фоновые Автопилоты 24/7"]
        AD["run_self_healing_autopilot_cycle.py (Сеть)"]
        CD["self_healing_code_daemon.py (Код)"]
    end

    subgraph L9["Слой 9: Сервис Пользователей и Telegram-Бот"]
        TB["Telegram-бот (telegram_bot_simple.py)"]
        DB["База данных SQLite WAL (database.py)"]
    end

    subgraph L8["L8: Скрытый Прокси-Транспорт"]
        XR["Шлюз Нидерланды (NL VPS 89.125.1.107 — VLESS+Reality)"]
        MSK["Релей Москва (MSK VPS 84.54.47.103 — 40мс)"]
    end

    subgraph L7["Слой 7: Постквантовые Сообщения x0tMQ"]
        XMQ["Протокол x0tMQ (src/swarm/)"]
        FRAME["Кадр X0tMQMAPEKFrame (Подпись ML-DSA-65)"]
    end

    subgraph L6["Слой 6: Самовосстанавливаемый Движок MAPE-K"]
        MON["1. Мониторинг (MAPEKMonitor)"]
        GNN["2. Анализ Аномалий (GraphSAGE GNN)"]
        PLN["3. Планирование (Bio-Evo & DPI Planner)"]
        EXE["4. Исполнение Перемаршрутизации (MAPEKExecutor)"]
    end

    subgraph L5["Слой 5: Zero-Trust Идентичность SPIRE"]
        SPIRE["SPIRE Server + Workload API"]
        SVID["SVIDSigner & Авторотатор PQCSVIDRotator"]
    end

    subgraph L4["Слой 4: Постквантовая Криптография (PQC)"]
        KEM["ML-KEM-768 (NIST FIPS 203 Обмен Ключами)"]
        DSA["ML-DSA-65 (NIST FIPS 204 Цифровая Подпись)"]
    end

    subgraph L3["Слой 3: Ядро Linux eBPF/XDP"]
        XDP["Драйверный Хук eBPF/XDP (6.66 нс/оп)"]
        RING["Буфер Кольца AF_XDP & Мост ebpf_to_x0tmq_bridge.py"]
    end

    subgraph L2["Слой 2: Распределенная Топология Mesh"]
        P2P["P2P Туннели Libp2p / WireGuard"]
        PBFT["Консенсус PBFT Delphi"]
    end

    subgraph L1["Слой 1: Сетевые Карты и Оборудование"]
        NIC["Физическая Сетевая Карта / Виртуальный Интерфейс"]
    end

    TB --> DB
    TB --> XR
    XR <--> MSK
    NIC --> XDP
    XDP --> RING
    RING --> XMQ
    XMQ --> FRAME
    FRAME --> SPIRE
    SPIRE --> SVID
    SVID --> KEM
    KEM --> DSA
    DSA --> MON
    MON --> GNN
    GNN --> PLN
    PLN --> EXE
    EXE --> P2P
    P2P --> PBFT
    AD --> XR
    CD --> VM
"""
    mermaid_ru_file.write_text(mermaid_ru_content, encoding="utf-8")
    print(f"  ✓ Generated: {mermaid_ru_file}")

    # 2. Generate Master SVG Poster (English)
    svg_file = ASSETS_DIR / "x0tta6bl4_architecture_master.svg"
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 850" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="850" fill="url(#bgGrad)"/>
  <rect x="15" y="15" width="1170" height="820" rx="16" fill="none" stroke="#1e293b" stroke-width="2"/>

  <text x="600" y="55" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="26" font-weight="bold" text-anchor="middle" letter-spacing="1">
    x0tta6bl4 — MASTER ARCHITECTURE MAP
  </text>
  <text x="600" y="82" fill="#94a3b8" font-family="sans-serif" font-size="14" text-anchor="middle">
    Autonomous Self-Healing Mesh · Post-Quantum Cryptography (NIST ML-KEM / ML-DSA) · eBPF/XDP Kernel Dataplane
  </text>

  <rect x="50" y="110" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="75" y="140" fill="#38bdf8" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 1: USER SERVICE &amp; TELEGRAM INTERFACE</text>
  <rect x="75" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="230" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Telegram Bot (telegram_bot_simple.py)</text>
  <rect x="405" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="560" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">SQLite WAL Database (database.py)</text>
  <rect x="735" y="152" width="390" height="36" rx="6" fill="#0f172a" stroke="#38bdf8"/>
  <text x="930" y="175" fill="#38bdf8" font-family="sans-serif" font-size="12" text-anchor="middle">VLESS+Reality Subscriptions (check_bot_user_chains PASS)</text>

  <rect x="50" y="220" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#818cf8" stroke-width="1.5"/>
  <text x="75" y="250" fill="#818cf8" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 2: STEALTH PROXY &amp; MESH TUNNELS</text>
  <rect x="75" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">NL Gateway (VPS 89.125.1.107 — Xray / SPIRE)</text>
  <rect x="445" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">MSK Relay (VPS 84.54.47.103 — Active 40ms)</text>
  <rect x="815" y="262" width="310" height="36" rx="6" fill="#0f172a" stroke="#818cf8"/>
  <text x="970" y="285" fill="#818cf8" font-family="sans-serif" font-size="12" text-anchor="middle">Anti-Censorship RST Detector</text>

  <rect x="50" y="330" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#c084fc" stroke-width="1.5"/>
  <text x="75" y="360" fill="#c084fc" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 3: POST-QUANTUM CRYPTO &amp; ZERO-TRUST IDENTITY</text>
  <rect x="75" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">NIST ML-KEM-768 &amp; ML-DSA-65 (liboqs)</text>
  <rect x="445" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">SPIRE Workload API &amp; JWT-SVID</text>
  <rect x="815" y="372" width="310" height="36" rx="6" fill="#0f172a" stroke="#c084fc"/>
  <text x="970" y="395" fill="#c084fc" font-family="sans-serif" font-size="12" text-anchor="middle">PQCSVIDRotator (Auto Key Rotation)</text>

  <rect x="50" y="440" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#4ade80" stroke-width="1.5"/>
  <text x="75" y="470" fill="#4ade80" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 4: x0tMQ MESSAGING &amp; eBPF/XDP KERNEL DATAPLANE</text>
  <rect x="75" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">eBPF/XDP Driver Hook (6.66 ns decision, 0 B/op)</text>
  <rect x="445" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">x0tMQ PQC Messaging Frame (Magic 0x5830544D)</text>
  <rect x="815" y="482" width="310" height="36" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="970" y="505" fill="#4ade80" font-family="sans-serif" font-size="12" text-anchor="middle">ebpf_to_x0tmq_bridge.py (VERIFIED)</text>

  <rect x="50" y="550" width="1100" height="110" rx="10" fill="url(#cardGrad)" stroke="#fbbf24" stroke-width="1.5"/>
  <text x="75" y="580" fill="#fbbf24" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 5: AUTONOMOUS MAPE-K SELF-HEALING ENGINE</text>
  <rect x="75" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="200" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">1. Monitor</text>
  <text x="200" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKMonitor &amp; RingBuffers</text>
  
  <rect x="345" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="470" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">2. Analyze</text>
  <text x="470" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">GraphSAGE GNN Anomaly Detector</text>
  
  <rect x="615" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="740" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">3. Plan</text>
  <text x="740" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">Bio-Evo &amp; DPI Healing Planner</text>

  <rect x="885" y="595" width="240" height="48" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="1005" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">4. Execute</text>
  <text x="1005" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKExecutor (Auto Reroute)</text>

  <rect x="50" y="675" width="1100" height="135" rx="10" fill="#020617" stroke="#334155" stroke-width="1"/>
  <text x="75" y="705" fill="#f8fafc" font-family="sans-serif" font-size="14" font-weight="bold">SINGLE SOURCE OF TRUTH — 3-TIER STATUS TAXONOMY</text>
  
  <rect x="75" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="90" y="745" fill="#4ade80" font-family="sans-serif" font-size="13" font-weight="bold">✅ VERIFIED</text>
  <text x="90" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Automated test passing (Exit Code 0 &amp; Artifact)</text>
  <text x="90" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">PQC, eBPF Simulator, x0tMQ Bridge, Rotator</text>

  <rect x="430" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="445" y="745" fill="#fbbf24" font-family="sans-serif" font-size="13" font-weight="bold">🟡 VALIDATED IN LAB</text>
  <text x="445" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Tested on integration testbed / NL &amp; MSK VPS</text>
  <text x="445" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">Autonomous Loop, Ghost Bot Chains, SPIRE</text>

  <rect x="785" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#94a3b8"/>
  <text x="800" y="745" fill="#94a3b8" font-family="sans-serif" font-size="13" font-weight="bold">⚪ TARGET</text>
  <text x="800" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Engineering hypothesis planned for future testing</text>
  <text x="800" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">1M+ PPS Physical NIC, 100+ Node Deployment</text>
</svg>
"""
    svg_file.write_text(svg_content, encoding="utf-8")
    print(f"  ✓ Generated: {svg_file}")

    # 2b. Generate Master SVG Poster (Russian)
    svg_ru_file = ASSETS_DIR / "x0tta6bl4_architecture_master_ru.svg"
    svg_ru_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 850" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="850" fill="url(#bgGrad)"/>
  <rect x="15" y="15" width="1170" height="820" rx="16" fill="none" stroke="#1e293b" stroke-width="2"/>

  <!-- Title Header RU -->
  <text x="600" y="55" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="26" font-weight="bold" text-anchor="middle" letter-spacing="1">
    x0tta6bl4 — ГЛАВНАЯ КАРТА АРХИТЕКТУРЫ ПЛАТФОРМЫ
  </text>
  <text x="600" y="82" fill="#94a3b8" font-family="sans-serif" font-size="14" text-anchor="middle">
    Автономная самовосстанавливающаяся Mesh-сеть · Постквантовая криптография (NIST ML-KEM / ML-DSA) · Фильтрация в ядре eBPF/XDP
  </text>

  <!-- Layer 1: User & Interface RU -->
  <rect x="50" y="110" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="75" y="140" fill="#38bdf8" font-family="sans-serif" font-size="15" font-weight="bold">СЛОЙ 1: СЕРВИС ПОЛЬЗОВАТЕЛЕЙ И TELEGRAM-БОТ</text>
  <rect x="75" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="230" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Telegram-бот (telegram_bot_simple.py)</text>
  <rect x="405" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="560" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">База данных SQLite WAL (database.py)</text>
  <rect x="735" y="152" width="390" height="36" rx="6" fill="#0f172a" stroke="#38bdf8"/>
  <text x="930" y="175" fill="#38bdf8" font-family="sans-serif" font-size="12" text-anchor="middle">Выдача подписок VLESS+Reality (check_bot_user_chains PASS)</text>

  <!-- Layer 2: Transport & Proxy RU -->
  <rect x="50" y="220" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#818cf8" stroke-width="1.5"/>
  <text x="75" y="250" fill="#818cf8" font-family="sans-serif" font-size="15" font-weight="bold">СЛОЙ 2: СКРЫТЫЙ ПРОКСИ И MESH-ТУННЕЛИ</text>
  <rect x="75" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Шлюз Нидерланды (NL VPS 89.125.1.107 — Xray / SPIRE)</text>
  <rect x="445" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Релей Москва (MSK VPS 84.54.47.103 — Активен 40мс)</text>
  <rect x="815" y="262" width="310" height="36" rx="6" fill="#0f172a" stroke="#818cf8"/>
  <text x="970" y="285" fill="#818cf8" font-family="sans-serif" font-size="12" text-anchor="middle">Детектор сбросов ТСПУ (Anti-Censorship)</text>

  <!-- Layer 3: PQC & SPIRE Identity RU -->
  <rect x="50" y="330" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#c084fc" stroke-width="1.5"/>
  <text x="75" y="360" fill="#c084fc" font-family="sans-serif" font-size="15" font-weight="bold">СЛОЙ 3: ПОСТКВАНТОВАЯ КРИПТОГРАФИЯ И ZERO-TRUST ИДЕНТИЧНОСТЬ</text>
  <rect x="75" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">NIST ML-KEM-768 &amp; ML-DSA-65 (liboqs)</text>
  <rect x="445" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">SPIRE Workload API &amp; JWT-SVID</text>
  <rect x="815" y="372" width="310" height="36" rx="6" fill="#0f172a" stroke="#c084fc"/>
  <text x="970" y="395" fill="#c084fc" font-family="sans-serif" font-size="12" text-anchor="middle">PQCSVIDRotator (Авторотация ключей)</text>

  <!-- Layer 4: x0tMQ & eBPF Kernel RU -->
  <rect x="50" y="440" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#4ade80" stroke-width="1.5"/>
  <text x="75" y="470" fill="#4ade80" font-family="sans-serif" font-size="15" font-weight="bold">СЛОЙ 4: ПОСТКВАНТОВЫЙ ТРАНСПОРТ x0tMQ И eBPF/XDP В ЯДРЕ</text>
  <rect x="75" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">eBPF/XDP Драйверный хук (6.66 нс/оп, 0 B/op)</text>
  <rect x="445" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Кадр x0tMQ PQC (Магия 0x5830544D)</text>
  <rect x="815" y="482" width="310" height="36" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="970" y="505" fill="#4ade80" font-family="sans-serif" font-size="12" text-anchor="middle">ebpf_to_x0tmq_bridge.py (VERIFIED)</text>

  <!-- Layer 5: MAPE-K Self-Healing Engine RU -->
  <rect x="50" y="550" width="1100" height="110" rx="10" fill="url(#cardGrad)" stroke="#fbbf24" stroke-width="1.5"/>
  <text x="75" y="580" fill="#fbbf24" font-family="sans-serif" font-size="15" font-weight="bold">СЛОЙ 5: АВТОНОМНЫЙ ДВИЖОК САМОВОССТАНОВЛЕНИЯ MAPE-K</text>
  <rect x="75" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="200" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">1. Мониторинг</text>
  <text x="200" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKMonitor &amp; RingBuffers</text>
  
  <rect x="345" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="470" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">2. Анализ ИИ</text>
  <text x="470" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">GraphSAGE GNN Anomaly Detector</text>
  
  <rect x="615" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="740" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">3. План</text>
  <text x="740" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">Планировщик Bio-Evo &amp; DPI</text>

  <rect x="885" y="595" width="240" height="48" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="1005" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">4. Исполнение</text>
  <text x="1005" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKExecutor (Автоперемаршрутизация)</text>

  <!-- Layer 6: Status Taxonomy Footer RU -->
  <rect x="50" y="675" width="1100" height="135" rx="10" fill="#020617" stroke="#334155" stroke-width="1"/>
  <text x="75" y="705" fill="#f8fafc" font-family="sans-serif" font-size="14" font-weight="bold">ЕДИНЫЙ ИСТОЧНИК ПРАВДЫ — 3-УРОВНЕВАЯ ТАКСОНОМИЯ СТАТУСОВ</text>
  
  <rect x="75" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="90" y="745" fill="#4ade80" font-family="sans-serif" font-size="13" font-weight="bold">✅ VERIFIED (ПОДТВЕРЖДЕНО)</text>
  <text x="90" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Автотест с тихим выходом (Exit Code 0 и артефакт)</text>
  <text x="90" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">PQC, eBPF Симулятор, Мост x0tMQ, Ротатор ключей</text>

  <rect x="430" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="445" y="745" fill="#fbbf24" font-family="sans-serif" font-size="13" font-weight="bold">🟡 VALIDATED IN LAB (ЛАБОРАТОРИЯ)</text>
  <text x="445" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Проверено на тестовом стенде / VPS Нидерландов и Москвы</text>
  <text x="445" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">Автономная петля, Бот Telegram, SPIRE mTLS</text>

  <rect x="785" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#94a3b8"/>
  <text x="800" y="745" fill="#94a3b8" font-family="sans-serif" font-size="13" font-weight="bold">⚪ TARGET (ЦЕЛЕВАЯ ГИПОТЕЗА)</text>
  <text x="800" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Инженерная гипотеза, планируемая к тестированию</text>
  <text x="800" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">1M+ PPS на физической NIC, Деплой 100+ нод</text>
</svg>
"""
    svg_ru_file.write_text(svg_ru_content, encoding="utf-8")
    print(f"  ✓ Generated: {svg_ru_file}")

    # 3. Generate Architecture Sitemap Document (English)
    doc_file = ARCH_DIR / "SYSTEM_ARCHITECTURE_MAP.md"
    doc_content = """# x0tta6bl4 — System Architecture Sitemap

> 📖 **Single Source of Truth:** See [`VERIFICATION_MATRIX.md`](../verification/VERIFICATION_MATRIX.md) for reproducible proof links across all subsystems.

---

## 🎨 Visual Architecture Poster

![x0tta6bl4 Master Architecture Map](../assets/x0tta6bl4_architecture_master.svg)

---

## 🏛️ Subsystem Map & Proof Links

| Layer | Component | File Path | Status | Verification Proof |
|:---|:---|:---|:---:|:---|
| **L1** | **User Interface (Telegram Bot)** | [`telegram_bot_simple.py`](../../telegram_bot_simple.py) | `🟡 VALIDATED IN LAB` | `python3 services/nl-server/ghost-access/check_bot_user_chains.py` |
| **L1** | **SQLite WAL Database** | [`database.py`](../../database.py) | `🟡 VALIDATED IN LAB` | `check_bot_user_chains.py` |
| **L2** | **Stealth Proxy (VLESS+Reality)** | [`src/services/vpn_config_generator.py`](../../src/services/vpn_config_generator.py) | `✅ VERIFIED` | `pytest tests/unit/server/test_ghost_server_unit.py` |
| **L2** | **Anti-Censorship RST Detector** | [`src/anti_censorship/tspu_rst_detector.py`](../../src/anti_censorship/tspu_rst_detector.py) | `✅ VERIFIED` | `pytest tests/unit/anti_censorship/test_tspu_rst_detector_unit.py` |
| **L3** | **Post-Quantum Crypto (PQC)** | [`src/security/pqc/`](../../src/security/pqc/) | `✅ VERIFIED` | `python3 -c "import src.security.pqc as pqc; print(pqc.is_liboqs_available())"` |
| **L3** | **PQC SVID Certificate Rotator** | [`src/security/pqc_svid_rotator.py`](../../src/security/pqc_svid_rotator.py) | `✅ VERIFIED` | `pytest tests/unit/security/test_pqc_svid_rotator_unit.py` |
| **L4** | **x0tMQ PQC Transport Bridge** | [`src/self_healing/x0tmq_mapek_bridge.py`](../../src/self_healing/x0tmq_mapek_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/self_healing/test_x0tmq_mapek_bridge_unit.py` |
| **L4** | **eBPF to x0tMQ Pipeline** | [`src/network/ebpf/ebpf_to_x0tmq_bridge.py`](../../src/network/ebpf/ebpf_to_x0tmq_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/network/ebpf/test_ebpf_to_x0tmq_bridge_unit.py` |
| **L5** | **GraphSAGE GNN Anomaly Detector** | [`src/ml/graphsage_x0tmq_integrator.py`](../../src/ml/graphsage_x0tmq_integrator.py) | `✅ VERIFIED` | `pytest tests/unit/ml/test_graphsage_x0tmq_integrator_unit.py` |
| **L5** | **MAPE-K Autonomous Loop** | [`src/self_healing/mape_k/manager.py`](../../src/self_healing/mape_k/manager.py) | `🟡 VALIDATED IN LAB` | `pytest tests/test_mapek_ai_contracts_e2e.py` |
"""
    doc_file.write_text(doc_content, encoding="utf-8")
    print(f"  ✓ Generated: {doc_file}")

    # 3b. Generate Architecture Sitemap Document (Russian)
    doc_ru_file = RU_DIR / "SYSTEM_ARCHITECTURE_MAP_RU.md"
    doc_ru_content = """# x0tta6bl4 — Главная Карта Архитектуры (Русская версия)

> 📖 **Единый источник правды:** См. [`VERIFICATION_MATRIX.md`](../verification/VERIFICATION_MATRIX.md) для воспроизводимых команд проверки по всем подсистемам.

---

## 🎨 Наглядный Архитектурный Плакат

![x0tta6bl4 Главная Карта Архитектуры](../assets/x0tta6bl4_architecture_master_ru.svg)

---

## 🏛️ Карта Подсистем и Доказательства

| Уровень | Компонент | Исходный Файл | Статус | Доказательство Проверки |
|:---|:---|:---|:---:|:---|
| **Слой 1** | **Интерфейс Пользователей (Telegram-бот)** | [`telegram_bot_simple.py`](../../telegram_bot_simple.py) | `🟡 VALIDATED IN LAB` | `python3 services/nl-server/ghost-access/check_bot_user_chains.py` |
| **Слой 1** | **База Данных SQLite WAL** | [`database.py`](../../database.py) | `🟡 VALIDATED IN LAB` | `check_bot_user_chains.py` |
| **Слой 2** | **Скрытый Прокси (VLESS+Reality)** | [`src/services/vpn_config_generator.py`](../../src/services/vpn_config_generator.py) | `✅ VERIFIED` | `pytest tests/unit/server/test_ghost_server_unit.py` |
| **Слой 2** | **Детектор Сбросов ТСПУ (RST Detector)** | [`src/anti_censorship/tspu_rst_detector.py`](../../src/anti_censorship/tspu_rst_detector.py) | `✅ VERIFIED` | `pytest tests/unit/anti_censorship/test_tspu_rst_detector_unit.py` |
| **Слой 3** | **Постквантовая Криптография (PQC)** | [`src/security/pqc/`](../../src/security/pqc/) | `✅ VERIFIED` | `python3 -c "import src.security.pqc as pqc; print(pqc.is_liboqs_available())"` |
| **Слой 3** | **Авторотатор PQC SVID Ключей** | [`src/security/pqc_svid_rotator.py`](../../src/security/pqc_svid_rotator.py) | `✅ VERIFIED` | `pytest tests/unit/security/test_pqc_svid_rotator_unit.py` |
| **Слой 4** | **Мост Постквантового Транспорта x0tMQ** | [`src/self_healing/x0tmq_mapek_bridge.py`](../../src/self_healing/x0tmq_mapek_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/self_healing/test_x0tmq_mapek_bridge_unit.py` |
| **Слой 4** | **Конвейер eBPF -> x0tMQ PQC** | [`src/network/ebpf/ebpf_to_x0tmq_bridge.py`](../../src/network/ebpf/ebpf_to_x0tmq_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/network/ebpf/test_ebpf_to_x0tmq_bridge_unit.py` |
| **Слой 5** | **ИИ-Детектор Аномалий GraphSAGE GNN** | [`src/ml/graphsage_x0tmq_integrator.py`](../../src/ml/graphsage_x0tmq_integrator.py) | `✅ VERIFIED` | `pytest tests/unit/ml/test_graphsage_x0tmq_integrator_unit.py` |
| **Слой 5** | **Автономная Петля MAPE-K** | [`src/self_healing/mape_k/manager.py`](../../src/self_healing/mape_k/manager.py) | `🟡 VALIDATED IN LAB` | `pytest tests/test_mapek_ai_contracts_e2e.py` |
"""
    doc_ru_file.write_text(doc_ru_content, encoding="utf-8")
    print(f"  ✓ Generated: {doc_ru_file}")

    print("✅ All Master Architecture Assets (EN & RU) generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(generate_master_poster())
