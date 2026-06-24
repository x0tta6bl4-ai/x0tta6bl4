"""
Marketing Assets Generator for x0tta6bl4
=========================================

Generates SVG previews of the Quantum Shield app for Product Hunt.
"""

def generate_connected_svg():
    svg = """
    <svg width="400" height="700" viewBox="0 0 400 700" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="400" height="700" rx="40" fill="#050505"/>
        <rect x="20" y="20" width="360" height="660" rx="30" stroke="#1F1F1F" stroke-width="2"/>
        
        <!-- Header -->
        <rect x="40" y="60" width="40" height="40" rx="10" fill="#10B981"/>
        <text x="95" y="88" fill="white" font-family="Arial" font-size="20" font-weight="bold">Quantum Shield</text>
        
        <!-- Connection Circle -->
        <circle cx="200" cy="300" r="90" stroke="#10B981" stroke-width="4" stroke-dasharray="10 5"/>
        <circle cx="200" cy="300" r="70" fill="#10B981" fill-opacity="0.1"/>
        <text x="200" y="310" text-anchor="middle" fill="#10B981" font-family="Arial" font-size="14" font-weight="bold">CONNECTED</text>
        
        <!-- Stats -->
        <rect x="40" y="450" width="150" height="70" rx="15" fill="#1F1F1F"/>
        <text x="55" y="475" fill="#71717A" font-family="Arial" font-size="10">PROTECTION</text>
        <text x="55" y="500" fill="#10B981" font-family="Arial" font-size="14" font-weight="bold">PQC + ZKP</text>
        
        <rect x="210" y="450" width="150" height="70" rx="15" fill="#1F1F1F"/>
        <text x="225" y="475" fill="#71717A" font-family="Arial" font-size="10">PROTOCOL</text>
        <text x="225" y="500" fill="#60A5FA" font-family="Arial" font-size="14" font-weight="bold">GHOST v2</text>
        
        <!-- Location -->
        <rect x="40" y="540" width="320" height="80" rx="20" fill="#1F1F1F" fill-opacity="0.5"/>
        <text x="60" y="575" fill="white" font-family="Arial" font-size="16" font-weight="bold">United States</text>
        <text x="60" y="595" fill="#71717A" font-family="Arial" font-size="10">LATENCY: 45ms</text>
        
        <text x="200" y="670" text-anchor="middle" fill="#3F3F46" font-family="Arial" font-size="8">POWERED BY X0TTA6BL4 MESH</text>
    </svg>
    """
    with open("marketing/app_connected.svg", "w") as f:
        f.write(svg)


def generate_ph_launch_card_svg():
    svg = """
    <svg width="1200" height="630" viewBox="0 0 1200 630" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1200" y2="630" gradientUnits="userSpaceOnUse">
                <stop stop-color="#0B1220"/>
                <stop offset="1" stop-color="#1A2A4A"/>
            </linearGradient>
            <linearGradient id="accent" x1="80" y1="80" x2="1120" y2="550" gradientUnits="userSpaceOnUse">
                <stop stop-color="#22C55E"/>
                <stop offset="1" stop-color="#38BDF8"/>
            </linearGradient>
        </defs>

        <rect width="1200" height="630" fill="url(#bg)"/>

        <rect x="70" y="70" width="1060" height="490" rx="32" fill="#0F172A" fill-opacity="0.72" stroke="#1E293B" stroke-width="2"/>

        <text x="110" y="148" fill="#93C5FD" font-family="Arial" font-size="28" font-weight="700">x0tta6bl4</text>
        <text x="110" y="205" fill="#FFFFFF" font-family="Arial" font-size="52" font-weight="700">MaaS v3.4.0</text>
        <text x="110" y="250" fill="#CBD5E1" font-family="Arial" font-size="28">Self-Healing Post-Quantum Mesh-as-a-Service</text>

        <rect x="110" y="292" width="460" height="56" rx="14" fill="#0B2338" stroke="#134E4A"/>
        <text x="130" y="328" fill="#A7F3D0" font-family="Arial" font-size="24" font-weight="700">ML-KEM-768 + ML-DSA-65</text>

        <rect x="110" y="364" width="350" height="56" rx="14" fill="#0B2338" stroke="#1D4ED8"/>
        <text x="130" y="400" fill="#BFDBFE" font-family="Arial" font-size="24" font-weight="700">DAO CLI on Base Sepolia</text>

        <rect x="110" y="436" width="300" height="56" rx="14" fill="#0B2338" stroke="#334155"/>
        <text x="130" y="472" fill="#E2E8F0" font-family="Arial" font-size="24" font-weight="700">MAPE-K Recovery Loops</text>

        <rect x="110" y="508" width="350" height="56" rx="14" fill="#0B2338" stroke="#4F46E5"/>
        <text x="130" y="544" fill="#C7D2FE" font-family="Arial" font-size="24" font-weight="700">eBPF Data Plane Ops</text>

        <circle cx="885" cy="318" r="152" stroke="url(#accent)" stroke-width="3" stroke-dasharray="10 8"/>
        <circle cx="885" cy="318" r="118" fill="#16A34A" fill-opacity="0.14"/>
        <text x="885" y="300" text-anchor="middle" fill="#86EFAC" font-family="Arial" font-size="22" font-weight="700">LAUNCH READY</text>
        <text x="885" y="332" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="30" font-weight="700">Product Hunt</text>

        <rect x="775" y="390" width="220" height="58" rx="12" fill="#082F49" stroke="#0EA5E9"/>
        <text x="885" y="426" text-anchor="middle" fill="#7DD3FC" font-family="Arial" font-size="24" font-weight="700">chain_id=84532</text>

        <text x="110" y="540" fill="#94A3B8" font-family="Arial" font-size="20">docs/marketing/product_hunt_launch/PH_ASSETS_MAAS_2026.md</text>
    </svg>
    """
    with open("marketing/ph_launch_card.svg", "w") as f:
        f.write(svg)

if __name__ == "__main__":
    generate_connected_svg()
    generate_ph_launch_card_svg()
    print("✅ Marketing assets generated:")
    print("  - marketing/app_connected.svg")
    print("  - marketing/ph_launch_card.svg")
