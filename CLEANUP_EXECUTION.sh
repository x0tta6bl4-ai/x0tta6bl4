#!/bin/bash

echo "╔════════════════════════════════════════════════════╗"
echo "║        🔧 x0tta6bl4 CLEANUP EXECUTION START        ║"
echo "╚════════════════════════════════════════════════════╝"

echo ""
echo "📊 PHASE 1: STORAGE ANALYSIS"
echo "════════════════════════════════════════════════════"
echo ""
echo "Before cleanup:"
df -h /mnt/AC74CC2974CBF3DC | tail -1

echo ""
echo "Total workspace size:"
du -sh /mnt/AC74CC2974CBF3DC

echo ""
echo "📦 PHASE 2: REMOVE MASSIVE ARCHIVE (161 GB)"
echo "════════════════════════════════════════════════════"
echo ""
echo "🗑️ Deleting archive/snapshots/x0tta6bl4_foundation_2025-10-29.tar.gz..."

if [ -f "/mnt/AC74CC2974CBF3DC/archive/snapshots/x0tta6bl4_foundation_2025-10-29.tar.gz" ]; then
    rm -f /mnt/AC74CC2974CBF3DC/archive/snapshots/x0tta6bl4_foundation_2025-10-29.tar.gz
    if [ $? -eq 0 ]; then
        echo "✅ Archive deleted successfully"
    else
        echo "❌ Failed to delete archive"
    fi
else
    echo "ℹ️ Archive file not found"
fi

echo ""
echo "📦 PHASE 3: REMOVE VIRTUAL ENVIRONMENTS"
echo "════════════════════════════════════════════════════"
echo ""
echo "🔍 Finding virtual environments..."

# Find all venv directories
VENV_COUNT=$(find /mnt/AC74CC2974CBF3DC -type d \( -name "venv" -o -name ".venv" -o -name "ENV" \) 2>/dev/null | wc -l)
VENV_SIZE=$(du -sh $(find /mnt/AC74CC2974CBF3DC -type d \( -name "venv" -o -name ".venv" \) 2>/dev/null) 2>/dev/null | tail -1 | awk '{print $1}')

if [ "$VENV_COUNT" -gt 0 ]; then
    echo "Found $VENV_COUNT virtual environments"
    echo "Total size: $VENV_SIZE"
    echo ""
    echo "🗑️ Removing virtual environments..."
    find /mnt/AC74CC2974CBF3DC -type d \( -name "venv" -o -name ".venv" -o -name "ENV" \) -exec rm -rf {} + 2>/dev/null
    echo "✅ Virtual environments removed"
else
    echo "ℹ️ No virtual environments found"
fi

echo ""
echo "📦 PHASE 4: CLEAN PYTHON CACHES"
echo "════════════════════════════════════════════════════"
echo ""
echo "🗑️ Removing __pycache__ directories..."

PYCACHE_COUNT=$(find /mnt/AC74CC2974CBF3DC -type d -name "__pycache__" 2>/dev/null | wc -l)
echo "Found $PYCACHE_COUNT __pycache__ directories"

find /mnt/AC74CC2974CBF3DC -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "✅ __pycache__ removed"

echo ""
echo "🗑️ Removing .pytest_cache directories..."
PYTEST_COUNT=$(find /mnt/AC74CC2974CBF3DC -type d -name ".pytest_cache" 2>/dev/null | wc -l)
echo "Found $PYTEST_COUNT .pytest_cache directories"

find /mnt/AC74CC2974CBF3DC -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
echo "✅ .pytest_cache removed"

echo ""
echo "🗑️ Removing .mypy_cache directories..."
find /mnt/AC74CC2974CBF3DC -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null
echo "✅ .mypy_cache removed"

echo ""
echo "📦 PHASE 5: CLEAN BUILD ARTIFACTS"
echo "════════════════════════════════════════════════════"
echo ""
echo "🗑️ Removing build/, dist/, *.egg-info..."

find /mnt/AC74CC2974CBF3DC -type d -name "build" -o -name "dist" -o -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
echo "✅ Build artifacts removed"

echo ""
echo "📊 PHASE 6: STORAGE ANALYSIS AFTER CLEANUP"
echo "════════════════════════════════════════════════════"
echo ""
echo "After cleanup:"
df -h /mnt/AC74CC2974CBF3DC | tail -1

echo ""
echo "Total workspace size now:"
du -sh /mnt/AC74CC2974CBF3DC

echo ""
echo "📈 Storage Summary:"
echo "════════════════════════════════════════════════════"

BEFORE_USED=389
BEFORE_FREE=77
AFTER_USED=$(df /mnt/AC74CC2974CBF3DC | tail -1 | awk '{print $3}')
AFTER_FREE=$(df /mnt/AC74CC2974CBF3DC | tail -1 | awk '{print $4}')

echo "Before: Used=${BEFORE_USED}G, Free=${BEFORE_FREE}G"
echo "After:  Used=${AFTER_USED}K, Free=${AFTER_FREE}K"

echo ""
echo "✅ CLEANUP COMPLETE!"
echo "════════════════════════════════════════════════════"
echo ""
