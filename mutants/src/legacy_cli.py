"""x0tta6bl4 Command Line Interface."""
from __future__ import annotations

import sys
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


def x_main__mutmut_orig():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_1():
    """Main CLI entry point."""
    print(None)
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_2():
    """Main CLI entry point."""
    print("XXx0tta6bl4 v1.0.0XX")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_3():
    """Main CLI entry point."""
    print("X0TTA6BL4 V1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_4():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print(None)
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_5():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("XXUsage:XX")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_6():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_7():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("USAGE:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_8():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print(None)
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_9():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("XX  x0tta6bl4-server    Start FastAPI serverXX")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_10():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    start fastapi server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_11():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  X0TTA6BL4-SERVER    START FASTAPI SERVER")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_12():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print(None)
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_13():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("XX  x0tta6bl4-health    Check system healthXX")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_14():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_15():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  X0TTA6BL4-HEALTH    CHECK SYSTEM HEALTH")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_16():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print(None)
    return 0


def x_main__mutmut_17():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("XXFor more information, see: https://docs.x0tta6bl4.devXX")
    return 0


def x_main__mutmut_18():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("for more information, see: https://docs.x0tta6bl4.dev")
    return 0


def x_main__mutmut_19():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("FOR MORE INFORMATION, SEE: HTTPS://DOCS.X0TTA6BL4.DEV")
    return 0


def x_main__mutmut_20():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 1

x_main__mutmut_mutants : ClassVar[MutantDict] = {
'x_main__mutmut_1': x_main__mutmut_1, 
    'x_main__mutmut_2': x_main__mutmut_2, 
    'x_main__mutmut_3': x_main__mutmut_3, 
    'x_main__mutmut_4': x_main__mutmut_4, 
    'x_main__mutmut_5': x_main__mutmut_5, 
    'x_main__mutmut_6': x_main__mutmut_6, 
    'x_main__mutmut_7': x_main__mutmut_7, 
    'x_main__mutmut_8': x_main__mutmut_8, 
    'x_main__mutmut_9': x_main__mutmut_9, 
    'x_main__mutmut_10': x_main__mutmut_10, 
    'x_main__mutmut_11': x_main__mutmut_11, 
    'x_main__mutmut_12': x_main__mutmut_12, 
    'x_main__mutmut_13': x_main__mutmut_13, 
    'x_main__mutmut_14': x_main__mutmut_14, 
    'x_main__mutmut_15': x_main__mutmut_15, 
    'x_main__mutmut_16': x_main__mutmut_16, 
    'x_main__mutmut_17': x_main__mutmut_17, 
    'x_main__mutmut_18': x_main__mutmut_18, 
    'x_main__mutmut_19': x_main__mutmut_19, 
    'x_main__mutmut_20': x_main__mutmut_20
}

def main(*args, **kwargs):
    result = _mutmut_trampoline(x_main__mutmut_orig, x_main__mutmut_mutants, args, kwargs)
    return result 

main.__signature__ = _mutmut_signature(x_main__mutmut_orig)
x_main__mutmut_orig.__name__ = 'x_main'


if __name__ == "__main__":
    sys.exit(main())
