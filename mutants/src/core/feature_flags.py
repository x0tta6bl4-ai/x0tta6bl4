"""
Feature Flags для управления версиями приложения.

Позволяет консолидировать все версии app в один с feature flags.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


class FeatureFlags:
    """
    Feature Flags для x0tta6bl4.
    
    Управляет включением/выключением функций через environment variables.
    """
    
    # Byzantine Protection
    BYZANTINE_PROTECTION = os.getenv("X0TTA6BL4_BYZANTINE", "false").lower() == "true"
    
    # Failover
    FAILOVER_ENABLED = os.getenv("X0TTA6BL4_FAILOVER", "false").lower() == "true"
    
    # PQC Beacons
    PQC_BEACONS = os.getenv("X0TTA6BL4_PQC_BEACONS", "false").lower() == "true"
    
    # Minimal Mode
    MINIMAL_MODE = os.getenv("X0TTA6BL4_MINIMAL", "false").lower() == "true"
    
    # GraphSAGE
    GRAPHSAGE_ENABLED = os.getenv("X0TTA6BL4_GRAPHSAGE", "true").lower() == "true"
    
    # SPIFFE/mTLS - REQUIRED in production for Zero Trust
    # In production, SPIFFE is mandatory (can be disabled only explicitly)
    _production_mode = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"
    SPIFFE_ENABLED = os.getenv("X0TTA6BL4_SPIFFE", "true" if _production_mode else "true").lower() == "true"
    
    # eBPF Observability
    EBPF_ENABLED = os.getenv("X0TTA6BL4_EBPF", "true").lower() == "true"
    
    # Federated Learning
    FL_ENABLED = os.getenv("X0TTA6BL4_FL", "true").lower() == "true"
    
    # DAO Governance
    DAO_ENABLED = os.getenv("X0TTA6BL4_DAO", "true").lower() == "true"
    
    @classmethod
    def get_all_flags(cls) -> Dict[str, bool]:
        """Get all feature flags as dict."""
        return {
            "byzantine_protection": cls.BYZANTINE_PROTECTION,
            "failover_enabled": cls.FAILOVER_ENABLED,
            "pqc_beacons": cls.PQC_BEACONS,
            "minimal_mode": cls.MINIMAL_MODE,
            "graphsage_enabled": cls.GRAPHSAGE_ENABLED,
            "spiffe_enabled": cls.SPIFFE_ENABLED,
            "ebpf_enabled": cls.EBPF_ENABLED,
            "fl_enabled": cls.FL_ENABLED,
            "dao_enabled": cls.DAO_ENABLED,
        }
    
    @classmethod
    def log_status(cls):
        """Log current feature flags status."""
        flags = cls.get_all_flags()
        enabled = [k for k, v in flags.items() if v]
        disabled = [k for k, v in flags.items() if not v]
        
        logger.info(f"Feature Flags - Enabled: {', '.join(enabled) if enabled else 'none'}")
        logger.info(f"Feature Flags - Disabled: {', '.join(disabled) if disabled else 'none'}")

