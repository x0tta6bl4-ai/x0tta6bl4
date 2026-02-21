"""
SPIFFE/SPIRE Identity Management Module

SPIFFE (Secure Production Identity Framework for Everyone) provides
cryptographic identity for workloads in dynamic environments.

Components:
- Workload API: SVIDs (SPIFFE Verifiable Identity Documents)
- Agent: Node attestation and workload registration
- Controller: SPIRE server interaction and policy management

References:
- https://spiffe.io/
- https://github.com/spiffe/spire
"""

from .agent import AttestationStrategy, SPIREAgentManager, WorkloadEntry
from .controller import SPIFFEController

__version__ = "0.1.0"
__all__ = [
    "SPIFFEController",
    "SPIREAgentManager",
    "AttestationStrategy",
    "WorkloadEntry",
]
