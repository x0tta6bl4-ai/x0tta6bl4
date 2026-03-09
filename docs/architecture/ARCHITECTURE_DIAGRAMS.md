# x0tta6bl4 Architecture Diagrams

The project uses Mermaid.js for architecture visualizations. You can render these blocks on GitHub or any compatible markdown viewer.

## 1. High-Level MaaS Architecture

```mermaid
graph TD
    subgraph Control Plane [x0tta6bl4 Control Plane (SaaS)]
        API[FastAPI Gateway]
        DB[(PostgreSQL)]
        Redis[(Redis Telemetry)]
        VAULT[HashiCorp Vault]
        SPIRE[SPIRE Server]
        
        API --> DB
        API --> Redis
        API --> VAULT
    end

    subgraph Tenant A [Customer Mesh A]
        NodeA1[Edge Node 1]
        NodeA2[Relay Node 2]
        NodeA3[Exit Node 3]
        
        NodeA1 <-->|PQC WireGuard/SOCKS5| NodeA2
        NodeA2 <-->|PQC WireGuard/SOCKS5| NodeA3
    end

    subgraph Tenant B [Customer Mesh B]
        NodeB1[Edge Node 1]
    end

    SPIRE -->|Issues SVIDs| NodeA1
    SPIRE -->|Issues SVIDs| NodeA2
    SPIRE -->|Issues SVIDs| NodeA3
    SPIRE -->|Issues SVIDs| NodeB1

    NodeA1 -.->|Heartbeats & Telemetry| API
    NodeA2 -.->|Heartbeats & Telemetry| API
    NodeB1 -.->|Heartbeats & Telemetry| API
```

## 2. Supply Chain & Attestation Flow

```mermaid
sequenceDiagram
    participant CI as CI/CD Pipeline
    participant Registry as MaaS SBOM Registry
    participant Node as Edge Node
    participant Validator as API Policy Engine

    CI->>CI: Build Binary
    CI->>CI: Generate CycloneDX SBOM
    CI->>CI: Sign SBOM (ML-DSA-65)
    CI->>Registry: Publish Signed SBOM & Hash
    
    Node->>Node: Boot & Generate Local Hash
    Node->>Validator: POST /verify-binary (Local Hash)
    Validator->>Registry: Lookup Authorized Hash
    
    alt Hash Matches
        Validator-->>Node: OK (Issue mTLS Cert)
    else Hash Mismatch
        Validator-->>Node: DENY (Mark COMPROMISED)
    end
```

## 3. MAPE-K Self-Healing Loop

```mermaid
stateDiagram-v2
    [*] --> Monitor
    
    Monitor --> Analyze : Ping Loss / Latency > 150ms
    Monitor --> Analyze : Proxy Unhealthy
    
    Analyze --> Plan : Identify faulty node/route
    Analyze --> Monitor : Transient issue (Ignore)
    
    Plan --> Execute : Generate new routing table
    Plan --> Execute : Trigger script (heal_now.py)
    
    Execute --> Monitor : Restart daemon / Reconnect
```

## 4. B2B Billing & Quota Lifecycle

```mermaid
graph LR
    User[Tenant Admin] -->|Subscribe| Stripe[Stripe / Crypto Checkout]
    Stripe -->|Webhook| Webhook[Webhook Handler]
    Webhook --> DB[(Users & Quotas)]
    
    User -->|Deploy Mesh| Deploy[Deploy API]
    Deploy --> QuotaCheck{Check Nodes < Limit?}
    
    QuotaCheck -->|Yes| Provision[Provision Resources]
    QuotaCheck -->|No| Reject[403 Quota Exceeded]
    
    Stripe -->|Payment Failed x3| Webhook
    Webhook --> Downgrade[Set Plan=Free]
    Downgrade --> Suspend[Suspend Active Meshes]
```