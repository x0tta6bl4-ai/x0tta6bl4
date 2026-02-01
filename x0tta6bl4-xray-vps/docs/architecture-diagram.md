# x0tta6bl4 Xray VPS Architecture

## System Overview

```mermaid
flowchart TB
    subgraph Internet["🌐 Internet"]
        WEB["Websites & Services"]
        CDN["CDN / Cloudflare"]
    end

    subgraph Client["👤 Client Devices"]
        FLCLASH["FlClashX / v2rayN / Nekoray"]
        BROWSERS["Browsers & Apps"]
    end

    subgraph VPS["🖥️ x0tta6bl4 VPS"]
        subgraph XRAY["Xray Core v25.1.30"]
            subgraph INBOUNDS["Inbound Protocols"]
                VLESS_R["VLESS-XTLS-Reality-Vision<br/>Port 443 (Primary)"]
                TROJAN["Trojan-XTLS-Reality<br/>Port 9443 (Fallback #1)"]
                VLESS_X["VLESS-splitHTTP<br/>Port 8443 (Fallback #2)"]
                SS["Shadowsocks 2022<br/>Port 8388 (Fallback #3)"]
                SHADOWTLS["ShadowTLS<br/>Port 8080 (Fallback #4)"]
            end

            subgraph ROUTING["Traffic Routing"]
                SNIFF["Traffic Sniffing<br/>HTTP/TLS/QUIC"]
                RULES["Routing Rules"]
                BLOCK["🚫 Block Ads & CN"]
            end

            subgraph OUTBOUNDS["Outbound Destinations"]
                DIRECT["📤 Direct"]
                WARP["☁️ WARP (Google/Netflix)"]
                BLOCKED["🚫 Blackhole"]
            end
        end

        subgraph SYSTEM["System Layer"]
            SYSCTL["TCP BBR Optimization"]
            FIREWALL["UFW/FirewallD"]
            CERTS["TLS Certificates"]
            LOGS["Logging & Monitoring"]
        end
    end

    %% Client connections
    FLCLASH -->|"VLESS + Reality<br/>XTLS Vision"| VLESS_R
    FLCLASH -->|"Trojan + Reality"| TROJAN
    FLCLASH -->|"VLESS + xHTTP"| VLESS_X
    FLCLASH -->|"SS 2022"| SS
    FLCLASH -->|"ShadowTLS"| SHADOWTLS

    %% Internal routing
    VLESS_R --> SNIFF
    TROJAN --> SNIFF
    VLESS_X --> SNIFF
    SS --> SNIFF
    SHADOWTLS --> SNIFF

    SNIFF --> RULES

    RULES -->|"Regular traffic"| DIRECT
    RULES -->|"Google/Netflix"| WARP
    RULES -->|"Ads/CN IPs"| BLOCKED

    DIRECT --> WEB
    WARP --> CDN
    CDN --> WEB
```

## Protocol Hierarchy

```mermaid
flowchart LR
    subgraph Priority["Connection Priority"]
        P1["1️⃣ VLESS-XTLS-Reality-Vision<br/>Speed: ⭐⭐⭐⭐⭐<br/>Security: ⭐⭐⭐⭐⭐<br/>Stealth: ⭐⭐⭐⭐⭐"]
        P2["2️⃣ Trojan-XTLS-Reality<br/>Speed: ⭐⭐⭐⭐⭐<br/>Security: ⭐⭐⭐⭐⭐<br/>Stealth: ⭐⭐⭐⭐"]
        P3["3️⃣ VLESS-splitHTTP<br/>Speed: ⭐⭐⭐⭐<br/>Security: ⭐⭐⭐⭐<br/>Stealth: ⭐⭐⭐⭐"]
        P4["4️⃣ Shadowsocks 2022<br/>Speed: ⭐⭐⭐⭐⭐<br/>Security: ⭐⭐⭐<br/>Stealth: ⭐⭐"]
        P5["5️⃣ ShadowTLS<br/>Speed: ⭐⭐⭐<br/>Security: ⭐⭐⭐⭐<br/>Stealth: ⭐⭐⭐⭐⭐"]
    end

    P1 -->|"Blocked?"| P2
    P2 -->|"Blocked?"| P3
    P3 -->|"Blocked?"| P4
    P4 -->|"Blocked?"| P5
```

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant C as Client (FlClashX)
    participant V as VPS (Xray)
    participant D as Destination
    participant W as WARP

    Note over C,W: VLESS-XTLS-Reality-Vision Flow

    C->>V: TLS 1.3 Handshake + Reality Auth
    Note right of V: XTLS Vision<br/>Zero-copy forwarding
    V->>V: Traffic Sniffing (SNI)
    
    alt Google/Netflix Traffic
        V->>W: Route via WARP
        W->>D: Cloudflare egress
    else Blocked Domain
        V->>V: Blackhole (drop)
    else Regular Traffic
        V->>D: Direct connection
    end

    D-->>V: Response
    V-->>C: Encrypted response
```

## Reality Protocol Handshake

```mermaid
sequenceDiagram
    participant C as Client
    participant P as Proxy Server
    participant T as Target (Microsoft.com)

    Note over C,T: Reality Handshake Process

    C->>C: Generate ephemeral X25519 key
    C->>P: Client Hello + Reality params
    
    P->>P: Validate client auth
    P->>T: Forward handshake (if needed)
    T-->>P: Target response
    
    P-->>C: Server Hello + Auth proof
    
    Note over C,P: Secure tunnel established
    C->>P: Encrypted traffic
    P->>T: Forward to destination
```

## Network Architecture

```mermaid
flowchart TB
    subgraph Network["Network Stack"]
        direction TB

        subgraph L7["Layer 7: Application"]
            HTTP["HTTP/2 / HTTP/3"]
            WS["WebSocket"]
            GRPC["gRPC"]
        end

        subgraph L4["Layer 4: Transport"]
            TCP["TCP Optimized (BBR)"]
            XHTTP["XHTTP / SplitHTTP"]
        end

        subgraph L3["Layer 3: Network"]
            IP["IP Routing"]
            WARP_WG["WARP WireGuard"]
        end

        subgraph L2["Layer 2: Security"]
            TLS["TLS 1.3"]
            REALITY["Reality Protocol"]
            XTLS["XTLS Vision"]
        end
    end

    HTTP --> XHTTP
    WS --> TCP
    GRPC --> TCP
    XHTTP --> IP
    TCP --> IP
    IP --> TLS
    TLS --> REALITY
    REALITY --> XTLS
    IP -.-> WARP_WG
```

## Failover Strategy

```mermaid
flowchart TD
    START["Client Connection Attempt"] --> TRY1{Try VLESS-Reality}
    
    TRY1 -->|Success| USE1["Use VLESS-Reality<br/>Best Performance"]
    TRY1 -->|Fail| TRY2{Try Trojan-Reality}
    
    TRY2 -->|Success| USE2["Use Trojan-Reality<br/>High Security"]
    TRY2 -->|Fail| TRY3{Try VLESS-xHTTP}
    
    TRY3 -->|Success| USE3["Use VLESS-xHTTP<br/>Fragmentation Support"]
    TRY3 -->|Fail| TRY4{Try Shadowsocks}
    
    TRY4 -->|Success| USE4["Use Shadowsocks<br/>Simple & Fast"]
    TRY4 -->|Fail| TRY5{Try ShadowTLS}
    
    TRY5 -->|Success| USE5["Use ShadowTLS<br/>Maximum Stealth"]
    TRY5 -->|Fail| ERROR["❌ All protocols failed"]

    USE1 --> MONITOR["Monitor Connection"]
    USE2 --> MONITOR
    USE3 --> MONITOR
    USE4 --> MONITOR
    USE5 --> MONITOR

    MONITOR -->|Degraded| TRY1
    MONITOR -->|Stable| MONITOR
```

## Security Layers

```mermaid
flowchart TB
    subgraph Security["Security Architecture"]
        direction TB

        S1["🔐 TLS 1.3 Encryption<br/>- AES-256-GCM<br/>- ChaCha20-Poly1305"]
        
        S2["🎭 Reality Protocol<br/>- X25519 Key Exchange<br/>- Short ID Authentication<br/>- SNI Spoofing"]
        
        S3["⚡ XTLS Vision<br/>- Zero-copy forwarding<br/>- Direct kernel bypass<br/>- Minimal overhead"]
        
        S4["🛡️ Traffic Obfuscation<br/>- Domain fronting<br/>- Packet fragmentation<br/>- Random padding"]
        
        S5["🚫 Access Control<br/>- UUID authentication<br/>- GeoIP blocking<br/>- Rate limiting"]
    end

    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
```

## Client Compatibility Matrix

```mermaid
flowchart LR
    subgraph Clients["Client Applications"]
        FLCLASH["FlClashX<br/>macOS/iOS"]
        V2RAYN["v2rayN<br/>Windows"]
        NEKORAY["Nekoray<br/>Windows/Linux"]
        SHADOWROCKET["Shadowrocket<br/>iOS"]
        STREISAND["Streisand<br/>iOS"]
        V2RAYNG["v2rayNG<br/>Android"]
    end

    subgraph Protocols["Supported Protocols"]
        P1["VLESS-Reality"]
        P2["Trojan-Reality"]
        P3["VLESS-xHTTP"]
        P4["Shadowsocks"]
        P5["ShadowTLS"]
    end

    FLCLASH --> P1
    FLCLASH --> P2
    FLCLASH --> P3
    FLCLASH --> P4

    V2RAYN --> P1
    V2RAYN --> P2
    V2RAYN --> P3
    V2RAYN --> P4

    NEKORAY --> P1
    NEKORAY --> P2
    NEKORAY --> P3
    NEKORAY --> P4

    SHADOWROCKET --> P1
    SHADOWROCKET --> P2
    SHADOWROCKET --> P3
    SHADOWROCKET --> P4

    STREISAND --> P1
    STREISAND --> P2
    STREISAND --> P5

    V2RAYNG --> P1
    V2RAYNG --> P2
    V2RAYNG --> P3
    V2RAYNG --> P4
```

## Deployment Topology

```mermaid
flowchart TB
    subgraph Global["Global Infrastructure"]
        subgraph EU["Europe Region"]
            VPS_EU["x0tta6bl4 VPS<br/>Amsterdam/London"]
        end

        subgraph US["US Region"]
            VPS_US["x0tta6bl4 VPS<br/>New York/LA"]
        end

        subgraph ASIA["Asia Region"]
            VPS_ASIA["x0tta6bl4 VPS<br/>Singapore/Tokyo"]
        end
    end

    subgraph CDN["Cloudflare WARP"]
        CF1["Edge Node 1"]
        CF2["Edge Node 2"]
        CF3["Edge Node 3"]
    end

    subgraph Destinations["Target Destinations"]
        GOOGLE["Google Services"]
        NETFLIX["Netflix/Streaming"]
        WEB["General Web"]
    end

    VPS_EU --> CF1
    VPS_US --> CF2
    VPS_ASIA --> CF3

    CF1 --> GOOGLE
    CF2 --> NETFLIX
    CF3 --> WEB

    VPS_EU -.-> WEB
    VPS_US -.-> WEB
    VPS_ASIA -.-> WEB
```

## Monitoring & Logging

```mermaid
flowchart TB
    subgraph Monitoring["Monitoring Stack"]
        subgraph Metrics["Metrics Collection"]
            XRAY_API["Xray API<br/>Port 10085"]
            STATS["Traffic Statistics"]
            CONN["Connection Metrics"]
        end

        subgraph Logs["Log Aggregation"]
            ACCESS["Access Logs<br/>/var/log/xray/access.log"]
            ERROR["Error Logs<br/>/var/log/xray/error.log"]
        end

        subgraph Health["Health Checks"]
            VALIDATE["Validation Script"]
            ALERTS["Alert Manager"]
        end
    end

    XRAY_API --> STATS
    XRAY_API --> CONN
    STATS --> VALIDATE
    CONN --> VALIDATE
    ACCESS --> VALIDATE
    ERROR --> ALERTS
    VALIDATE --> ALERTS
```

## File Structure

```mermaid
flowchart LR
    subgraph Files["Project Structure"]
        ROOT["/x0tta6bl4-xray-vps/"]
        
        SCRIPTS["scripts/"]
        CONFIGS["configs/"]
        DOCS["docs/"]
        CLIENTS["clients/"]
        DEPLOY["deploy/"]
    end

    ROOT --> SCRIPTS
    ROOT --> CONFIGS
    ROOT --> DOCS
    ROOT --> CLIENTS
    ROOT --> DEPLOY

    SCRIPTS --> INSTALL["install-xray.sh"]
    SCRIPTS --> VALIDATE["validate-installation.sh"]
    SCRIPTS --> BACKUP["backup-config.sh"]

    CONFIGS --> SERVER["server-config.json"]
    CONFIGS --> ROUTING["routing-rules.json"]

    CLIENTS --> FLCLASH["flclashx-configs/"]
    CLIENTS --> V2RAY["v2ray-configs/"]

    DEPLOY --> ROLLBACK["rollback.sh"]
    DEPLOY --> HEALTH["health-check.sh"]
```
