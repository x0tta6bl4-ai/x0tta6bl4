# Subprocess validation utilities
import subprocess
from typing import List, Optional

ALLOWED_COMMANDS = {
    'bpftool',
    'batctl',
    'yggdrasilctl',
    'ip',
    'tc',
    'which'
}
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

def x_validate_command__mutmut_orig(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_1(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd and not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_2(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_3(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_4(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError(None)
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_5(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("XXCommand must be a non-empty listXX")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_6(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_7(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("COMMAND MUST BE A NON-EMPTY LIST")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_8(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[1] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_9(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_10(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(None)
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_11(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[1]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_12(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[1] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_13(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] != 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_14(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'XXipXX':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_15(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'IP':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_16(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) <= 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_17(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 3:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_18(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError(None)
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_19(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("XXip command requires at least one subcommandXX")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_20(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("IP COMMAND REQUIRES AT LEAST ONE SUBCOMMAND")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_21(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = None
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_22(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'XXlinkXX', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_23(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'LINK', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_24(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'XXaddrXX', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_25(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'ADDR', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_26(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'XXrouteXX', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_27(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'ROUTE', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_28(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'XXnetnsXX'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_29(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'NETNS'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_30(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[2] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_31(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_32(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(None)
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_33(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[2]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_34(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[1] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_35(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] != 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_36(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'XXtcXX':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_37(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'TC':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_38(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) <= 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_39(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 3:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_40(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError(None)
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_41(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("XXtc command requires at least one subcommandXX")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_42(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("TC COMMAND REQUIRES AT LEAST ONE SUBCOMMAND")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_43(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = None
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_44(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'XXqdiscXX', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_45(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'QDISC', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_46(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'XXfilterXX', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_47(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'FILTER', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_48(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'XXclassXX'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_49(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'CLASS'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_50(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[2] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_51(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return True

def x_validate_command__mutmut_52(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(None)
    
    return True

def x_validate_command__mutmut_53(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[2]}")
    
    return True

def x_validate_command__mutmut_54(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")
    
    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    
    # Additional validation for specific commands
    if cmd[0] == 'ip':
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {'link', 'addr', 'route', 'netns'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")
    
    elif cmd[0] == 'tc':
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {'qdisc', 'filter', 'class'}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")
    
    return False

x_validate_command__mutmut_mutants : ClassVar[MutantDict] = {
'x_validate_command__mutmut_1': x_validate_command__mutmut_1, 
    'x_validate_command__mutmut_2': x_validate_command__mutmut_2, 
    'x_validate_command__mutmut_3': x_validate_command__mutmut_3, 
    'x_validate_command__mutmut_4': x_validate_command__mutmut_4, 
    'x_validate_command__mutmut_5': x_validate_command__mutmut_5, 
    'x_validate_command__mutmut_6': x_validate_command__mutmut_6, 
    'x_validate_command__mutmut_7': x_validate_command__mutmut_7, 
    'x_validate_command__mutmut_8': x_validate_command__mutmut_8, 
    'x_validate_command__mutmut_9': x_validate_command__mutmut_9, 
    'x_validate_command__mutmut_10': x_validate_command__mutmut_10, 
    'x_validate_command__mutmut_11': x_validate_command__mutmut_11, 
    'x_validate_command__mutmut_12': x_validate_command__mutmut_12, 
    'x_validate_command__mutmut_13': x_validate_command__mutmut_13, 
    'x_validate_command__mutmut_14': x_validate_command__mutmut_14, 
    'x_validate_command__mutmut_15': x_validate_command__mutmut_15, 
    'x_validate_command__mutmut_16': x_validate_command__mutmut_16, 
    'x_validate_command__mutmut_17': x_validate_command__mutmut_17, 
    'x_validate_command__mutmut_18': x_validate_command__mutmut_18, 
    'x_validate_command__mutmut_19': x_validate_command__mutmut_19, 
    'x_validate_command__mutmut_20': x_validate_command__mutmut_20, 
    'x_validate_command__mutmut_21': x_validate_command__mutmut_21, 
    'x_validate_command__mutmut_22': x_validate_command__mutmut_22, 
    'x_validate_command__mutmut_23': x_validate_command__mutmut_23, 
    'x_validate_command__mutmut_24': x_validate_command__mutmut_24, 
    'x_validate_command__mutmut_25': x_validate_command__mutmut_25, 
    'x_validate_command__mutmut_26': x_validate_command__mutmut_26, 
    'x_validate_command__mutmut_27': x_validate_command__mutmut_27, 
    'x_validate_command__mutmut_28': x_validate_command__mutmut_28, 
    'x_validate_command__mutmut_29': x_validate_command__mutmut_29, 
    'x_validate_command__mutmut_30': x_validate_command__mutmut_30, 
    'x_validate_command__mutmut_31': x_validate_command__mutmut_31, 
    'x_validate_command__mutmut_32': x_validate_command__mutmut_32, 
    'x_validate_command__mutmut_33': x_validate_command__mutmut_33, 
    'x_validate_command__mutmut_34': x_validate_command__mutmut_34, 
    'x_validate_command__mutmut_35': x_validate_command__mutmut_35, 
    'x_validate_command__mutmut_36': x_validate_command__mutmut_36, 
    'x_validate_command__mutmut_37': x_validate_command__mutmut_37, 
    'x_validate_command__mutmut_38': x_validate_command__mutmut_38, 
    'x_validate_command__mutmut_39': x_validate_command__mutmut_39, 
    'x_validate_command__mutmut_40': x_validate_command__mutmut_40, 
    'x_validate_command__mutmut_41': x_validate_command__mutmut_41, 
    'x_validate_command__mutmut_42': x_validate_command__mutmut_42, 
    'x_validate_command__mutmut_43': x_validate_command__mutmut_43, 
    'x_validate_command__mutmut_44': x_validate_command__mutmut_44, 
    'x_validate_command__mutmut_45': x_validate_command__mutmut_45, 
    'x_validate_command__mutmut_46': x_validate_command__mutmut_46, 
    'x_validate_command__mutmut_47': x_validate_command__mutmut_47, 
    'x_validate_command__mutmut_48': x_validate_command__mutmut_48, 
    'x_validate_command__mutmut_49': x_validate_command__mutmut_49, 
    'x_validate_command__mutmut_50': x_validate_command__mutmut_50, 
    'x_validate_command__mutmut_51': x_validate_command__mutmut_51, 
    'x_validate_command__mutmut_52': x_validate_command__mutmut_52, 
    'x_validate_command__mutmut_53': x_validate_command__mutmut_53, 
    'x_validate_command__mutmut_54': x_validate_command__mutmut_54
}

def validate_command(*args, **kwargs):
    result = _mutmut_trampoline(x_validate_command__mutmut_orig, x_validate_command__mutmut_mutants, args, kwargs)
    return result 

validate_command.__signature__ = _mutmut_signature(x_validate_command__mutmut_orig)
x_validate_command__mutmut_orig.__name__ = 'x_validate_command'

def x_validate_arguments__mutmut_orig(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_1(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[2:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_2(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = None
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_3(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = ['XX;XX', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_4(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', 'XX&XX', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_5(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', 'XX|XX', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_6(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', 'XX`XX', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_7(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', 'XX$XX', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_8(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', 'XX(XX', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_9(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', 'XX)XX', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_10(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', 'XX<XX', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_11(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', 'XX>XX', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_12(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', 'XX\nXX', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_13(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', 'XX\rXX']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_14(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(None):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_15(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char not in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_16(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(None) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return True

def x_validate_arguments__mutmut_17(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(None)
    
    return True

def x_validate_arguments__mutmut_18(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.
    
    Args:
        cmd: Command list to validate
        
    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")
    
    return False

x_validate_arguments__mutmut_mutants : ClassVar[MutantDict] = {
'x_validate_arguments__mutmut_1': x_validate_arguments__mutmut_1, 
    'x_validate_arguments__mutmut_2': x_validate_arguments__mutmut_2, 
    'x_validate_arguments__mutmut_3': x_validate_arguments__mutmut_3, 
    'x_validate_arguments__mutmut_4': x_validate_arguments__mutmut_4, 
    'x_validate_arguments__mutmut_5': x_validate_arguments__mutmut_5, 
    'x_validate_arguments__mutmut_6': x_validate_arguments__mutmut_6, 
    'x_validate_arguments__mutmut_7': x_validate_arguments__mutmut_7, 
    'x_validate_arguments__mutmut_8': x_validate_arguments__mutmut_8, 
    'x_validate_arguments__mutmut_9': x_validate_arguments__mutmut_9, 
    'x_validate_arguments__mutmut_10': x_validate_arguments__mutmut_10, 
    'x_validate_arguments__mutmut_11': x_validate_arguments__mutmut_11, 
    'x_validate_arguments__mutmut_12': x_validate_arguments__mutmut_12, 
    'x_validate_arguments__mutmut_13': x_validate_arguments__mutmut_13, 
    'x_validate_arguments__mutmut_14': x_validate_arguments__mutmut_14, 
    'x_validate_arguments__mutmut_15': x_validate_arguments__mutmut_15, 
    'x_validate_arguments__mutmut_16': x_validate_arguments__mutmut_16, 
    'x_validate_arguments__mutmut_17': x_validate_arguments__mutmut_17, 
    'x_validate_arguments__mutmut_18': x_validate_arguments__mutmut_18
}

def validate_arguments(*args, **kwargs):
    result = _mutmut_trampoline(x_validate_arguments__mutmut_orig, x_validate_arguments__mutmut_mutants, args, kwargs)
    return result 

validate_arguments.__signature__ = _mutmut_signature(x_validate_arguments__mutmut_orig)
x_validate_arguments__mutmut_orig.__name__ = 'x_validate_arguments'

def x_safe_run__mutmut_orig(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(cmd)
    return subprocess.run(cmd, **kwargs)

def x_safe_run__mutmut_1(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(None)
    validate_arguments(cmd)
    return subprocess.run(cmd, **kwargs)

def x_safe_run__mutmut_2(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(None)
    return subprocess.run(cmd, **kwargs)

def x_safe_run__mutmut_3(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(cmd)
    return subprocess.run(None, **kwargs)

def x_safe_run__mutmut_4(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(cmd)
    return subprocess.run(**kwargs)

def x_safe_run__mutmut_5(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.
    
    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(cmd)
    return subprocess.run(cmd, )

x_safe_run__mutmut_mutants : ClassVar[MutantDict] = {
'x_safe_run__mutmut_1': x_safe_run__mutmut_1, 
    'x_safe_run__mutmut_2': x_safe_run__mutmut_2, 
    'x_safe_run__mutmut_3': x_safe_run__mutmut_3, 
    'x_safe_run__mutmut_4': x_safe_run__mutmut_4, 
    'x_safe_run__mutmut_5': x_safe_run__mutmut_5
}

def safe_run(*args, **kwargs):
    result = _mutmut_trampoline(x_safe_run__mutmut_orig, x_safe_run__mutmut_mutants, args, kwargs)
    return result 

safe_run.__signature__ = _mutmut_signature(x_safe_run__mutmut_orig)
x_safe_run__mutmut_orig.__name__ = 'x_safe_run'
