#!/usr/bin/env python3
import os
import sys
import json
import re

# Expected baseline data for RC1
EXPECTED_COMMIT = "b9896312d7d84a6b5398bdc142cd125465432f09"
EXPECTED_PPS_RX = "49"
EXPECTED_PPS_TX = "142k"

# Files to check
FILES_TO_CHECK = [
    "RC1_MANIFEST.json",
    "README.md",
    "docs/release/RC1_STATUS_PAGE.md",
    "docs/release/RC1_RELEASE_NOTES.md",
    "docs/release/RC1_INTEGRITY_NOTE.md",
    "docs/verification/v1.1-hardening-status.md",
    "docs/v1.1/VERIFICATION-MATRIX.md",
    "docs/verification/validation_bundle_v1.md"
]

def check_file_content(path, pattern, label):
    if not os.path.exists(path):
        print(f"❌ Missing file: {path}")
        return False
    
    with open(path, 'r') as f:
        content = f.read()
        if not re.search(pattern, content):
            print(f"❌ {label} not found in {path}")
            return False
    return True

def run_consistency_check():
    all_passed = True
    print(f"🔍 Starting RC1 Consistency Gate (Target Commit: {EXPECTED_COMMIT})")
    print("=================================================================")

    # Check Commit ID in core release files
    for f in ["RC1_MANIFEST.json", "docs/release/RC1_STATUS_PAGE.md", "docs/release/RC1_RELEASE_NOTES.md"]:
        if not check_file_content(f, EXPECTED_COMMIT, f"Commit ID {EXPECTED_COMMIT}"):
            all_passed = False

    # Check PPS Baseline in all relevant docs
    pps_pattern = f"{EXPECTED_PPS_RX}.*RX|{EXPECTED_PPS_TX}|142,000"
    for f in FILES_TO_CHECK:
        if not check_file_content(f, pps_pattern, "PPS Baseline (142k/49)"):
            all_passed = False

    if all_passed:
        print("\n✅ Consistency Gate: PASSED. Release is synchronized.")
        sys.exit(0)
    else:
        print("\n❌ Consistency Gate: FAILED. Please sync release documents.")
        sys.exit(1)

if __name__ == "__main__":
    run_consistency_check()
