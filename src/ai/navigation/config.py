"""
Configuration for the AI Navigation System.
Defines the workflow context and interest areas for the Visionary Feed.
"""

# Workflow Context: What matters for x0tta6bl4
PROJECT_CONTEXT = {
    "core_technologies": [
        "Post-Quantum Cryptography (ML-KEM, ML-DSA, Kyber, Dilithium)",
        "Self-healing networks & MAPE-K loops",
        "eBPF & XDP for high-performance networking",
        "Zero-Trust Architecture (SPIFFE/SPIRE)",
        "DAO Governance & Tokenomics",
        "Multi-hop Mesh Routing (SOCKS5 chaining)"
    ],
    "keywords": [
        "ai", "ml", "artificial intelligence",
        "pqc", "kyber", "dilithium", "ml-kem", "ml-dsa", "nist", 
        "mesh", "mape-k", "self-healing", "ebpf", "xdp", "spiffe", "spire", 
        "dao", "tokenomics", "zero-trust", "multi-hop",
        "ai security", "decentralized ai", "depin", "privacy-preserving",
        "confidential computing", "hardware acceleration", "gpu", "inference",
        "llm", "transformer", "generative ai", "rag", "agent",
        "vulnerability", "exploit", "zero-day", "encryption", "surveillance",
        "privacy", "anonymity", "sovereignty"
    ],
    "sources": [
        "https://hnrss.org/frontpage?q=AI",
        "https://hnrss.org/frontpage?q=Cryptography",
        "https://feeds.feedburner.com/TheHackersNews",
        "https://arxiv.org/rss/cs.AI",
        "https://arxiv.org/rss/cs.CR",
        "https://www.schneier.com/blog/index.rdf"
    ],
    "strategic_goals": [
        "Transition from B2C VPN to B2B DeepTech Platform",
        "Achieving 100k nodes in the mesh network",
        "Integration with mobile platforms (iOS/Android)",
        "Compliance with NIST and international security standards"
    ],
    "noise_filters": [
        "Generic LLM 'jailbreak' prompts (unless architectural)",
        "Non-technical AI hype (marketing fluff)",
        "Crypto-currency price speculation (unless DAO-related)",
        "General-purpose consumer hardware news"
    ]
}

# Classification Criteria
CRITERIA = {
    "GARBAGE": "Low info density, pure marketing, or irrelevant to project context.",
    "BENCHMARK": "New records, SOTA improvements in core technologies, general progress.",
    "BUSINESS": "Competitor moves, new regulations (NIST), monetization opportunities, SDK launches."
}

# Sources (Placeholders for real APIs)
SOURCES = [
    "https://arxiv.org/list/cs.CR/recent",  # Cryptography and Security
    "https://hnrss.org/frontpage",          # Hacker News
    "https://www.nist.gov/news-events/news" # NIST news
]
