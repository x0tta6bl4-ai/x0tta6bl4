#!/bin/bash
# x0tta6bl4 Phase 2: Infrastructure Consolidation
# Usage: bash scripts/phase2_infrastructure_consolidation.sh
set -e

echo "🚀 Starting Phase 2: Infrastructure Consolidation"

# 1. Create Phase 2 branch
if ! git branch | grep -q "phase-2-infrastructure-consolidation"; then
  git checkout -b phase-2-infrastructure-consolidation
else
  git checkout phase-2-infrastructure-consolidation
fi

# 2. Analyze infrastructure directories
echo -e "\n📊 Found infrastructure directories:"
find . -maxdepth 2 -type d -name "*infra*" | grep -v ".git" | grep -v "archive"

# 3. Create unified infra structure
echo -e "\n📁 Creating unified infra/ structure..."
mkdir -p infra/{terraform,k8s,docker,helm,networking,security}

# 4. Merge terraform (already in infra/)
echo "✅ Terraform already in infra/terraform/"

# 5. Merge networking configs from infrastructure/
if [ -d "x0tta6bl4_paradox_zone/infrastructure/development" ]; then
  cp -r x0tta6bl4_paradox_zone/infrastructure/development infra/networking/
  echo "✅ Merged infrastructure/development → infra/networking/development"
fi
if [ -d "x0tta6bl4_paradox_zone/infrastructure/mtls" ]; then
  cp -r x0tta6bl4_paradox_zone/infrastructure/mtls infra/security/
  echo "✅ Merged infrastructure/mtls → infra/security/mtls"
fi

# 6. Merge optimizations from infrastructure-optimizations/
if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations" ]; then
  # Batman-adv mesh networking
  if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations/batman-adv" ]; then
    cp -r x0tta6bl4_paradox_zone/infrastructure-optimizations/batman-adv infra/networking/
    echo "✅ Merged batman-adv → infra/networking/batman-adv"
  fi
  
  # SPIFFE/SPIRE mTLS
  if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations/spiffe-spire" ]; then
    cp -r x0tta6bl4_paradox_zone/infrastructure-optimizations/spiffe-spire infra/security/
    echo "✅ Merged spiffe-spire → infra/security/spiffe-spire"
  fi
  
  # mTLS optimization
  if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations/mtls-optimization" ]; then
    cp -r x0tta6bl4_paradox_zone/infrastructure-optimizations/mtls-optimization infra/security/
    echo "✅ Merged mtls-optimization → infra/security/mtls-optimization"
  fi
  
  # HNSW indexing
  if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations/hnsw-indexing" ]; then
    cp -r x0tta6bl4_paradox_zone/infrastructure-optimizations/hnsw-indexing infra/networking/
    echo "✅ Merged hnsw-indexing → infra/networking/hnsw-indexing"
  fi
  
  # Cilium eBPF
  if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations/cilium-ebpf" ]; then
    cp -r x0tta6bl4_paradox_zone/infrastructure-optimizations/cilium-ebpf infra/networking/
    echo "✅ Merged cilium-ebpf → infra/networking/cilium-ebpf"
  fi
  
  # DEPLOYMENT_GUIDE.md
  if [ -f "x0tta6bl4_paradox_zone/infrastructure-optimizations/DEPLOYMENT_GUIDE.md" ]; then
    cp x0tta6bl4_paradox_zone/infrastructure-optimizations/DEPLOYMENT_GUIDE.md infra/
    echo "✅ Copied DEPLOYMENT_GUIDE.md → infra/"
  fi
fi

# 7. Merge paradox_zone/infra/ if different from main infra/
if [ -d "x0tta6bl4_paradox_zone/infra" ]; then
  echo "⚠️  Found x0tta6bl4_paradox_zone/infra/ - checking for unique content..."
  # Only copy if contains unique files not in main infra/
  cp -rn x0tta6bl4_paradox_zone/infra/* infra/ 2>/dev/null || true
  echo "✅ Merged unique files from paradox_zone/infra/"
fi

# 8. Merge multi-region-infrastructure/
if [ -d "x0tta6bl4_paradox_zone/multi-region-infrastructure" ]; then
  cp -r x0tta6bl4_paradox_zone/multi-region-infrastructure infra/terraform/
  echo "✅ Merged multi-region-infrastructure → infra/terraform/multi-region"
fi

# 9. Archive old infrastructure directories
echo -e "\n📦 Archiving duplicate infrastructure directories..."
mkdir -p archive/legacy/infrastructure_old

if [ -d "x0tta6bl4_paradox_zone/infrastructure" ]; then
  mv x0tta6bl4_paradox_zone/infrastructure archive/legacy/infrastructure_old/
  echo "✅ Archived infrastructure/ → archive/legacy/"
fi

if [ -d "x0tta6bl4_paradox_zone/infrastructure-optimizations" ]; then
  mv x0tta6bl4_paradox_zone/infrastructure-optimizations archive/legacy/infrastructure_old/
  echo "✅ Archived infrastructure-optimizations/ → archive/legacy/"
fi

if [ -d "x0tta6bl4_paradox_zone/infra" ]; then
  mv x0tta6bl4_paradox_zone/infra archive/legacy/infrastructure_old/
  echo "✅ Archived paradox_zone/infra/ → archive/legacy/"
fi

if [ -d "x0tta6bl4_paradox_zone/multi-region-infrastructure" ]; then
  mv x0tta6bl4_paradox_zone/multi-region-infrastructure archive/legacy/infrastructure_old/
  echo "✅ Archived multi-region-infrastructure/ → archive/legacy/"
fi

# 10. Show new structure
echo -e "\n📁 New unified infra/ structure:"
tree -L 2 infra/ 2>/dev/null || find infra/ -maxdepth 2 -type d

# 11. Commit changes
echo -e "\n💾 Committing Phase 2 changes..."
git add .
git commit -m "Phase 2: Consolidated 5 duplicate infrastructure directories

- Merged infrastructure/ → infra/networking/ and infra/security/
- Merged infrastructure-optimizations/ → infra/networking/ and infra/security/
  - batman-adv (mesh networking)
  - spiffe-spire (mTLS identity)
  - mtls-optimization
  - hnsw-indexing (vector search)
  - cilium-ebpf (network observability)
- Merged multi-region-infrastructure/ → infra/terraform/
- Archived old directories → archive/legacy/infrastructure_old/

Result: Single unified infra/ with logical subdirectories"

echo -e "\n✅ Phase 2 completed successfully!"
echo "📊 Verify with: tree -L 3 infra/"
