#!/bin/bash
# Helper script for preparing personalized emails

PROSPECT_NAME="${1:-}"
PROSPECT_COMPANY="${2:-}"
PROSPECT_ROLE="${3:-}"

if [ -z "$PROSPECT_NAME" ]; then
    echo "Usage: $0 <name> <company> <role>"
    echo "Example: $0 'John Doe' 'Acme Corp' 'CTO'"
    exit 1
fi

echo "📧 Preparing email for: $PROSPECT_NAME ($PROSPECT_ROLE at $PROSPECT_COMPANY)"
echo ""

# Research prompts
echo "🔍 RESEARCH QUESTIONS:"
echo "1. What does $PROSPECT_COMPANY do?"
echo "2. What are their main challenges?"
echo "3. Why would they need x0tta6bl4?"
echo "4. What's their technology stack?"
echo ""

# Email template
cat <<EOF
Hi $PROSPECT_NAME,

I noticed $PROSPECT_COMPANY is working on [RESEARCH AND FILL THIS].

I thought you might be interested in x0tta6bl4 - the first 
post-quantum self-healing mesh network.

**Why this matters:**
- 15-30x faster incident detection (20s vs 5-10 min industry standard)
- 464x faster PQC handshake (0.81ms vs 376ms RSA-2048)
- 94-98% anomaly detection accuracy (vs 70-80% industry)
- Multi-cloud deployment (AWS/Azure/GCP ready)

**What makes us different:**
✅ NIST FIPS 203/204 Compliant (quantum-safe)
✅ Self-healing architecture (80% auto-resolution)
✅ Enterprise-grade security (SPIFFE/SPIRE, Network Policy, RBAC)
✅ Production-ready Kubernetes deployment

I'd love to show you a quick 15-minute demo. Are you available 
this week?

Best regards,
[Your Name]

P.S. We have a live demo at demo.x0tta6bl4.dev - feel free to 
check it out!
EOF

echo ""
echo "✅ NEXT STEPS:"
echo "1. Research $PROSPECT_COMPANY (5 minutes)"
echo "2. Fill in [RESEARCH AND FILL THIS] section"
echo "3. Personalize the email"
echo "4. Check for typos"
echo "5. Send!"
echo ""

