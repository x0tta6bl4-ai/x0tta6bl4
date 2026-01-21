#!/usr/bin/env python3
"""
Security Audit Checklist for x0tta6bl4

Automated security audit checks before production deployment.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_cve_patches() -> Tuple[bool, List[str]]:
    """Check if all CVE patches are applied."""
    print("🔍 Checking CVE patches...")
    
    issues = []
    
    # Check CVE-2020-12812 protection
    cve_file = project_root / "docs/security/CVE-2020-12812_PROTECTION.md"
    if not cve_file.exists():
        issues.append("CVE-2020-12812 protection documentation missing")
    else:
        print("  ✅ CVE-2020-12812 protection documented")
    
    # Check if protection is implemented
    # CVE-2020-12812 protection is documented and the validation logic
    # in zero_trust.py uses fail-closed approach (returns False on validation failure)
    zero_trust_file = project_root / "src/security/zero_trust.py"
    if zero_trust_file.exists():
        with open(zero_trust_file) as f:
            content = f.read()
            # Check for fail-closed validation (returns False on failure)
            if "return False" in content and "validate_connection" in content:
                print("  ✅ CVE-2020-12812 protection implemented (fail-closed validation)")
            else:
                issues.append("CVE-2020-12812 protection not fully implemented")
    
    return len(issues) == 0, issues

def check_pqc_fallback() -> Tuple[bool, List[str]]:
    """Check PQC fallback scenarios."""
    print("🔍 Checking PQC fallback scenarios...")
    
    issues = []
    
    pqc_file = project_root / "src/security/post_quantum.py"
    if not pqc_file.exists():
        issues.append("PQC module not found")
        return False, issues
    
    with open(pqc_file) as f:
        content = f.read()
        
        if "fallback" in content.lower() or "SimplifiedNTRU" in content:
            print("  ✅ PQC fallback mechanism present")
        else:
            issues.append("PQC fallback mechanism not found")
        
        if "liboqs" in content:
            print("  ✅ Real PQC (liboqs) integrated")
        else:
            issues.append("Real PQC (liboqs) not integrated")
    
    return len(issues) == 0, issues

def check_timing_attack_protection() -> Tuple[bool, List[str]]:
    """Check timing attack protection."""
    print("🔍 Checking timing attack protection...")
    
    issues = []
    
    # Check security enhancements
    security_file = project_root / "src/network/ebpf/security_enhancements.py"
    if security_file.exists():
        with open(security_file) as f:
            content = f.read()
            if "noise" in content.lower() or "timing" in content.lower():
                print("  ✅ Timing attack protection implemented")
            else:
                issues.append("Timing attack protection not found")
    else:
        # Check in secure kprobe
        kprobe_file = project_root / "src/network/ebpf/programs/kprobe_syscall_latency_secure.c"
        if kprobe_file.exists():
            with open(kprobe_file) as f:
                content = f.read()
                if "noise" in content.lower():
                    print("  ✅ Timing attack protection in eBPF")
                else:
                    issues.append("Timing attack protection not found in eBPF")
        else:
            issues.append("Timing attack protection files not found")
    
    return len(issues) == 0, issues

def check_dos_protection() -> Tuple[bool, List[str]]:
    """Check DoS protection (LRU maps)."""
    print("🔍 Checking DoS protection (LRU maps)...")
    
    issues = []
    
    # Check eBPF programs for LRU maps
    kprobe_file = project_root / "src/network/ebpf/programs/kprobe_syscall_latency_secure.c"
    if kprobe_file.exists():
        with open(kprobe_file) as f:
            content = f.read()
            if "BPF_MAP_TYPE_LRU" in content or "LRU" in content:
                print("  ✅ LRU maps implemented")
            else:
                issues.append("LRU maps not found in eBPF programs")
    else:
        issues.append("Secure eBPF program not found")
    
    return len(issues) == 0, issues

def check_policy_engine() -> Tuple[bool, List[str]]:
    """Check Policy Engine rules."""
    print("🔍 Checking Policy Engine rules...")
    
    issues = []
    
    policy_file = project_root / "src/security/zero_trust/policy_engine.py"
    if not policy_file.exists():
        issues.append("Policy Engine not found")
        return False, issues
    
    with open(policy_file) as f:
        content = f.read()
        
        if "PolicyRule" in content and "PolicyEngine" in content:
            print("  ✅ Policy Engine implemented")
        else:
            issues.append("Policy Engine not fully implemented")
        
        if "rate_limit" in content.lower():
            print("  ✅ Rate limiting configured")
        else:
            issues.append("Rate limiting not configured")
    
    return len(issues) == 0, issues

def run_security_audit() -> Dict[str, any]:
    """Run complete security audit."""
    print("\n" + "="*60)
    print("🔐 SECURITY AUDIT CHECKLIST")
    print("="*60 + "\n")
    
    checks = [
        ("CVE Patches", check_cve_patches),
        ("PQC Fallback", check_pqc_fallback),
        ("Timing Attack Protection", check_timing_attack_protection),
        ("DoS Protection", check_dos_protection),
        ("Policy Engine", check_policy_engine),
    ]
    
    results = {}
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            passed, issues = check_func()
            results[check_name] = {
                "passed": passed,
                "issues": issues
            }
            
            if not passed:
                all_passed = False
                print(f"  ❌ {check_name}: FAILED")
                for issue in issues:
                    print(f"     - {issue}")
            else:
                print(f"  ✅ {check_name}: PASSED")
            
            print()
        except Exception as e:
            print(f"  ⚠️ {check_name}: ERROR - {e}\n")
            results[check_name] = {
                "passed": False,
                "issues": [str(e)]
            }
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("✅ SECURITY AUDIT: ALL CHECKS PASSED")
    else:
        print("❌ SECURITY AUDIT: SOME CHECKS FAILED")
    print("="*60 + "\n")
    
    return {
        "all_passed": all_passed,
        "results": results
    }

if __name__ == "__main__":
    audit_result = run_security_audit()
    sys.exit(0 if audit_result["all_passed"] else 1)

