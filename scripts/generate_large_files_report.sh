#!/usr/bin/env bash
# Generate comprehensive report on large files in repository
set -euo pipefail

OUTPUT_DIR="reports/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "🔍 Generating large files report..."
echo "Output directory: $OUTPUT_DIR"

# 1. All files >1MB
echo "Scanning files >1MB..."
find . -type f -size +1M ! -path './.git/*' -exec du -h {} \; | \
  sort -hr > "$OUTPUT_DIR/files_over_1mb.txt"

# 2. All files >10MB
echo "Scanning files >10MB..."
find . -type f -size +10M ! -path './.git/*' -exec du -h {} \; | \
  sort -hr > "$OUTPUT_DIR/files_over_10mb.txt"

# 3. Virtual environments
echo "Scanning virtual environments..."
find . -type d \( -name 'venv' -o -name '.venv' -o -name 'venv_*' \) \
  ! -path './.git/*' -exec du -sh {} \; > "$OUTPUT_DIR/venv_sizes.txt"

# 4. Database files
echo "Scanning databases..."
find . -type f \( -name '*.db' -o -name '*.sqlite*' \) \
  ! -path './.git/*' -exec ls -lh {} \; > "$OUTPUT_DIR/database_files.txt"

# 5. Archives
echo "Scanning archives..."
find . -type f \( -name '*.tar.gz' -o -name '*.zip' -o -name '*.tgz' \) \
  ! -path './.git/*' -exec ls -lh {} \; > "$OUTPUT_DIR/archive_files.txt"

# 6. Summary statistics
echo "Generating summary..."
{
  cat <<EOF
# Repository Large Files Report
Generated: $(date)

## Top 20 Largest Files
```
EOF
  head -20 "$OUTPUT_DIR/files_over_1mb.txt"
  cat <<EOF
```

## Statistics
- Files >1MB: $(wc -l < "$OUTPUT_DIR/files_over_1mb.txt")
- Files >10MB: $(wc -l < "$OUTPUT_DIR/files_over_10mb.txt")
- Virtual environments found: $(wc -l < "$OUTPUT_DIR/venv_sizes.txt")
- Database files found: $(wc -l < "$OUTPUT_DIR/database_files.txt")
- Archive files found: $(wc -l < "$OUTPUT_DIR/archive_files.txt")

EOF
} > "$OUTPUT_DIR/SUMMARY.md"

echo "✅ Report generated in: $OUTPUT_DIR"
echo "📄 View summary: cat $OUTPUT_DIR/SUMMARY.md"
