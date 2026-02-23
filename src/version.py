"""
x0tta6bl4 Version Contract
==========================

Centralized version management for the entire project.

This module provides a single source of truth for version information
across all components: API, runtime, Docker images, tests, and documentation.

Version Policy (Option B):
- API reports project release version
- Single version for all components
- Semantic versioning: MAJOR.MINOR.PATCH

Usage:
    >>> from src.version import __version__, get_version_info
    >>> print(__version__)
    '3.2.1'
    >>> info = get_version_info()
    >>> print(info['api_version'])
    '3.2.1'
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


# =============================================================================
# SINGLE SOURCE OF TRUTH
# =============================================================================

# Major.Minor.Patch - Semantic Versioning
# Update this for each release
__version__ = "3.3.0"

# Build metadata (optional, for CI/CD)
__build__ = os.getenv("X0TTA6BL4_BUILD", "")

# Git commit hash (optional, for debugging)
__commit__ = os.getenv("GIT_COMMIT", "")

# Release channel: stable, beta, alpha
__channel__ = os.getenv("X0TTA6BL4_CHANNEL", "stable")

# Full version with metadata
__full_version__ = __version__
if __build__:
    __full_version__ = f"{__version__}+{__build__}"
if __channel__ != "stable":
    __full_version__ = f"{__version__}-{__channel__}"


# =============================================================================
# VERSION INFO
# =============================================================================

@dataclass
class VersionInfo:
    """Structured version information."""
    
    version: str
    major: int
    minor: int
    patch: int
    channel: str
    build: str
    commit: str
    
    @property
    def api_version(self) -> str:
        """Version for API responses."""
        return self.version
    
    @property
    def docker_tag(self) -> str:
        """Version for Docker image tags."""
        if self.channel == "stable":
            return self.version
        return f"{self.version}-{self.channel}"
    
    @property
    def user_agent(self) -> str:
        """User-Agent string for HTTP clients."""
        return f"x0tta6bl4/{self.full_version}"
    
    @property
    def full_version(self) -> str:
        """Full version with metadata."""
        result = self.version
        if self.build:
            result = f"{result}+{self.build}"
        if self.channel != "stable":
            result = f"{result}-{self.channel}"
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "channel": self.channel,
            "build": self.build,
            "commit": self.commit,
            "api_version": self.api_version,
            "docker_tag": self.docker_tag,
            "user_agent": self.user_agent,
            "full_version": self.full_version,
        }


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string into components."""
    # Remove build metadata and channel
    base = version_str.split("+")[0].split("-")[0]
    parts = base.split(".")
    
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    
    return major, minor, patch


def get_version_info() -> VersionInfo:
    """Get structured version information."""
    major, minor, patch = parse_version(__version__)
    
    return VersionInfo(
        version=__version__,
        major=major,
        minor=minor,
        patch=patch,
        channel=__channel__,
        build=__build__,
        commit=__commit__,
    )


def get_version() -> str:
    """Get the current version string."""
    return __version__


def get_api_version() -> str:
    """Get version for API responses."""
    return __version__


def get_docker_tag() -> str:
    """Get version for Docker image tags."""
    return get_version_info().docker_tag


def get_user_agent() -> str:
    """Get User-Agent string for HTTP clients."""
    return get_version_info().user_agent


# =============================================================================
# COMPATIBILITY CHECKS
# =============================================================================

def is_compatible(required_version: str) -> bool:
    """
    Check if current version is compatible with required version.
    
    Uses semantic versioning:
    - MAJOR version must match
    - MINOR version must be >= required
    """
    current = get_version_info()
    req_major, req_minor, req_patch = parse_version(required_version)
    
    # Major version must match
    if current.major != req_major:
        return False
    
    # Minor version must be >= required
    if current.minor < req_minor:
        return False
    
    # If minor matches, patch must be >= required
    if current.minor == req_minor and current.patch < req_patch:
        return False
    
    return True


def check_min_version(min_version: str) -> None:
    """
    Check that current version meets minimum requirement.
    
    Raises:
        RuntimeError: If version requirement not met
    """
    if not is_compatible(min_version):
        current = get_version_info()
        raise RuntimeError(
            f"Version {min_version} required, but running {current.version}"
        )


# =============================================================================
# HEALTH CHECK INTEGRATION
# =============================================================================

def get_health_info() -> Dict[str, Any]:
    """Get version info for health check endpoints."""
    info = get_version_info()
    return {
        "version": info.version,
        "full_version": info.full_version,
        "channel": info.channel,
        "build": info.build,
        "commit": info.commit,
        "timestamp": datetime.utcnow().isoformat(),
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Version constants
    "__version__",
    "__build__",
    "__commit__",
    "__channel__",
    "__full_version__",
    # Functions
    "get_version",
    "get_version_info",
    "get_api_version",
    "get_docker_tag",
    "get_user_agent",
    "get_health_info",
    "is_compatible",
    "check_min_version",
    "parse_version",
    # Classes
    "VersionInfo",
]


# =============================================================================
# INITIALIZATION LOG
# =============================================================================

# Log version on import (for debugging)
import logging
logger = logging.getLogger(__name__)
logger.debug(f"x0tta6bl4 version {__full_version__} loaded")
