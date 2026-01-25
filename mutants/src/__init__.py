"""x0tta6bl4 Core Package

Decentralized self-healing mesh network with Zero Trust security.
"""

__version__ = "1.0.0"
__author__ = "x0tta6bl4 Team"

# Import core modules immediately
from . import core, security, network, monitoring
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

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def x___getattr____mutmut_orig(name):
    if name == "ml":
        from . import ml
        return ml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def x___getattr____mutmut_1(name):
    if name != "ml":
        from . import ml
        return ml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def x___getattr____mutmut_2(name):
    if name == "XXmlXX":
        from . import ml
        return ml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def x___getattr____mutmut_3(name):
    if name == "ML":
        from . import ml
        return ml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def x___getattr____mutmut_4(name):
    if name == "ml":
        from . import ml
        return ml
    raise AttributeError(None)

x___getattr____mutmut_mutants : ClassVar[MutantDict] = {
'x___getattr____mutmut_1': x___getattr____mutmut_1, 
    'x___getattr____mutmut_2': x___getattr____mutmut_2, 
    'x___getattr____mutmut_3': x___getattr____mutmut_3, 
    'x___getattr____mutmut_4': x___getattr____mutmut_4
}

def __getattr__(*args, **kwargs):
    result = _mutmut_trampoline(x___getattr____mutmut_orig, x___getattr____mutmut_mutants, args, kwargs)
    return result 

__getattr__.__signature__ = _mutmut_signature(x___getattr____mutmut_orig)
x___getattr____mutmut_orig.__name__ = 'x___getattr__'

__all__ = ["core", "security", "network", "ml", "monitoring"]
