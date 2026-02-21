"""
MaaS API Constants and Configuration.

Contains PQC segment profiles, plan aliases, and billing configuration.
"""

from typing import Any, Dict


# ---------------------------------------------------------------------------
# PQC Segment Profiles
# ---------------------------------------------------------------------------
# Maps device_class → recommended PQC algorithm pair.
# NIST-standardized: ML-KEM (FIPS 203) + ML-DSA (FIPS 204).
# Security levels: 1 (128-bit) | 3 (192-bit) | 5 (256-bit)

PQC_SEGMENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "sensor": {
        "kem": "ML-KEM-512",
        "sig": "ML-DSA-44",
        "security_level": 1,
        "rationale": "Battery/CPU constrained — balance security vs. performance",
    },
    "edge": {
        "kem": "ML-KEM-512",
        "sig": "ML-DSA-44",
        "security_level": 1,
        "rationale": "Low-power edge devices — performance-first",
    },
    "robot": {
        "kem": "ML-KEM-768",
        "sig": "ML-DSA-65",
        "security_level": 3,
        "rationale": "Industrial robots — high security, real-time safe",
    },
    "drone": {
        "kem": "ML-KEM-768",
        "sig": "ML-DSA-65",
        "security_level": 3,
        "rationale": "Autonomous drones — medium latency tolerance",
    },
    "gateway": {
        "kem": "ML-KEM-1024",
        "sig": "ML-DSA-87",
        "security_level": 5,
        "rationale": "Network gateways — maximum security, high-value targets",
    },
    "server": {
        "kem": "ML-KEM-1024",
        "sig": "ML-DSA-87",
        "security_level": 5,
        "rationale": "Control-plane servers — maximum security",
    },
}

# Default profile for unknown device classes
PQC_DEFAULT_PROFILE: Dict[str, Any] = {
    "kem": "ML-KEM-768",
    "sig": "ML-DSA-65",
    "security_level": 3,
    "rationale": "Default: standard security for unclassified devices",
}


def get_pqc_profile(device_class: str) -> Dict[str, Any]:
    """Get PQC profile for a device class."""
    return PQC_SEGMENT_PROFILES.get(device_class, PQC_DEFAULT_PROFILE)


# ---------------------------------------------------------------------------
# Plan Configuration
# ---------------------------------------------------------------------------

PLAN_ALIASES = {
    "free": "starter",
    "starter": "starter",
    "pro": "pro",
    "enterprise": "enterprise",
}

BILLING_WEBHOOK_EVENTS = {
    "plan.upgraded",
    "plan.downgraded",
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
    "subscription.deleted",
}

PLAN_REQUEST_LIMITS = {
    "starter": 10_000,
    "pro": 100_000,
    "enterprise": 1_000_000,
}


__all__ = [
    "PQC_SEGMENT_PROFILES",
    "PQC_DEFAULT_PROFILE",
    "get_pqc_profile",
    "PLAN_ALIASES",
    "BILLING_WEBHOOK_EVENTS",
    "PLAN_REQUEST_LIMITS",
]
