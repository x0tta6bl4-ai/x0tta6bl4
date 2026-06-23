from __future__ import annotations

import warnings


def test_core_mapek_loop_reexports_mesh_recovery_orchestrator() -> None:
    from src.mesh.recovery_orchestrator import (
        MeshRecoveryOrchestrator as CanonicalMeshRecoveryOrchestrator,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from src.core.mape_k_loop import MeshRecoveryOrchestrator

    assert MeshRecoveryOrchestrator is CanonicalMeshRecoveryOrchestrator
