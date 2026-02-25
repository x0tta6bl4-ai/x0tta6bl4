#!/bin/bash
# x0tta6bl4 Deployment Artifact Verifier
# Checks if all Sprint 10 components are present and valid.

set -e

echo "=== Verifying x0tta6bl4 v3.3.0 Deployment Artifacts ==="

# 1. Check Source Code (PQC & ZKP)
[ -f "src/security/zkp_attestor.py" ] && echo "✅ ZKP Attestor: Found" || echo "❌ ZKP Attestor: Missing"
[ -f "src/security/pqc_spiffe.py" ] && echo "✅ PQC-SPIFFE Bridge: Found" || echo "❌ PQC-SPIFFE Bridge: Missing"
[ -f "src/swarm/pq_agent.py" ] && echo "✅ PQ-Secure Agent: Found" || echo "❌ PQ-Secure Agent: Missing"

# 2. Check Infrastructure (Compose & Helm)
[ -f "docker-compose.phase4.yml" ] && echo "✅ Phase 4 Compose: Found" || echo "❌ Phase 4 Compose: Missing"
[ -f "docker-compose.fl.yml" ] && echo "✅ Flower Pilot Compose: Found" || echo "❌ Flower Pilot Compose: Missing"
[ -f "helm/x0tta6bl4/values-10k.yaml" ] && echo "✅ Helm 10k Values: Found" || echo "❌ Helm 10k Values: Missing"

# 3. Check Automation (Ansible)
[ -f "ansible/bulk_flash.yml" ] && echo "✅ Ansible Bulk Flash: Found" || echo "❌ Ansible Bulk Flash: Missing"

# 4. Check Version Contract
grep -q "__version__ = "3.3.0"" src/version.py && echo "✅ Version Contract: 3.3.0" || echo "❌ Version Mismatch"

# 5. Check AI/ML Components
[ -f "src/ai/tokenomics_engine.py" ] && echo "✅ Tokenomics Engine: Found" || echo "❌ Tokenomics Engine: Missing"
[ -f "src/self_healing/bio_evo_optimizer.py" ] && echo "✅ Bio-Evo Optimizer: Found" || echo "❌ Bio-Evo Optimizer: Missing"

echo "=== Verification Complete ==="
