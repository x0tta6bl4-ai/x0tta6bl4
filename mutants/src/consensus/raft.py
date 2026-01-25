"""
Raft Consensus Algorithm (P1)
Scaffold for distributed consensus in x0tta6bl4 mesh
"""
from typing import Dict, List, Optional
import logging

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

class RaftNode:
    def xǁRaftNodeǁ__init____mutmut_orig(self, node_id: str):
        self.node_id = node_id
        self.state = 'follower'
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_1(self, node_id: str):
        self.node_id = None
        self.state = 'follower'
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_2(self, node_id: str):
        self.node_id = node_id
        self.state = None
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_3(self, node_id: str):
        self.node_id = node_id
        self.state = 'XXfollowerXX'
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_4(self, node_id: str):
        self.node_id = node_id
        self.state = 'FOLLOWER'
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_5(self, node_id: str):
        self.node_id = node_id
        self.state = 'follower'
        self.term = None
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_6(self, node_id: str):
        self.node_id = node_id
        self.state = 'follower'
        self.term = 1
        self.voted_for = None
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_7(self, node_id: str):
        self.node_id = node_id
        self.state = 'follower'
        self.term = 0
        self.voted_for = ""
        self.log: List[Dict] = []
    def xǁRaftNodeǁ__init____mutmut_8(self, node_id: str):
        self.node_id = node_id
        self.state = 'follower'
        self.term = 0
        self.voted_for = None
        self.log: List[Dict] = None
    
    xǁRaftNodeǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ__init____mutmut_1': xǁRaftNodeǁ__init____mutmut_1, 
        'xǁRaftNodeǁ__init____mutmut_2': xǁRaftNodeǁ__init____mutmut_2, 
        'xǁRaftNodeǁ__init____mutmut_3': xǁRaftNodeǁ__init____mutmut_3, 
        'xǁRaftNodeǁ__init____mutmut_4': xǁRaftNodeǁ__init____mutmut_4, 
        'xǁRaftNodeǁ__init____mutmut_5': xǁRaftNodeǁ__init____mutmut_5, 
        'xǁRaftNodeǁ__init____mutmut_6': xǁRaftNodeǁ__init____mutmut_6, 
        'xǁRaftNodeǁ__init____mutmut_7': xǁRaftNodeǁ__init____mutmut_7, 
        'xǁRaftNodeǁ__init____mutmut_8': xǁRaftNodeǁ__init____mutmut_8
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁRaftNodeǁ__init____mutmut_orig)
    xǁRaftNodeǁ__init____mutmut_orig.__name__ = 'xǁRaftNodeǁ__init__'
    def xǁRaftNodeǁbecome_leader__mutmut_orig(self):
        self.state = 'leader'
        logger.info(f"Node {self.node_id} became leader")
    def xǁRaftNodeǁbecome_leader__mutmut_1(self):
        self.state = None
        logger.info(f"Node {self.node_id} became leader")
    def xǁRaftNodeǁbecome_leader__mutmut_2(self):
        self.state = 'XXleaderXX'
        logger.info(f"Node {self.node_id} became leader")
    def xǁRaftNodeǁbecome_leader__mutmut_3(self):
        self.state = 'LEADER'
        logger.info(f"Node {self.node_id} became leader")
    def xǁRaftNodeǁbecome_leader__mutmut_4(self):
        self.state = 'leader'
        logger.info(None)
    
    xǁRaftNodeǁbecome_leader__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁbecome_leader__mutmut_1': xǁRaftNodeǁbecome_leader__mutmut_1, 
        'xǁRaftNodeǁbecome_leader__mutmut_2': xǁRaftNodeǁbecome_leader__mutmut_2, 
        'xǁRaftNodeǁbecome_leader__mutmut_3': xǁRaftNodeǁbecome_leader__mutmut_3, 
        'xǁRaftNodeǁbecome_leader__mutmut_4': xǁRaftNodeǁbecome_leader__mutmut_4
    }
    
    def become_leader(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁbecome_leader__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁbecome_leader__mutmut_mutants"), args, kwargs, self)
        return result 
    
    become_leader.__signature__ = _mutmut_signature(xǁRaftNodeǁbecome_leader__mutmut_orig)
    xǁRaftNodeǁbecome_leader__mutmut_orig.__name__ = 'xǁRaftNodeǁbecome_leader'
    def xǁRaftNodeǁbecome_follower__mutmut_orig(self):
        self.state = 'follower'
        logger.info(f"Node {self.node_id} became follower")
    def xǁRaftNodeǁbecome_follower__mutmut_1(self):
        self.state = None
        logger.info(f"Node {self.node_id} became follower")
    def xǁRaftNodeǁbecome_follower__mutmut_2(self):
        self.state = 'XXfollowerXX'
        logger.info(f"Node {self.node_id} became follower")
    def xǁRaftNodeǁbecome_follower__mutmut_3(self):
        self.state = 'FOLLOWER'
        logger.info(f"Node {self.node_id} became follower")
    def xǁRaftNodeǁbecome_follower__mutmut_4(self):
        self.state = 'follower'
        logger.info(None)
    
    xǁRaftNodeǁbecome_follower__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁbecome_follower__mutmut_1': xǁRaftNodeǁbecome_follower__mutmut_1, 
        'xǁRaftNodeǁbecome_follower__mutmut_2': xǁRaftNodeǁbecome_follower__mutmut_2, 
        'xǁRaftNodeǁbecome_follower__mutmut_3': xǁRaftNodeǁbecome_follower__mutmut_3, 
        'xǁRaftNodeǁbecome_follower__mutmut_4': xǁRaftNodeǁbecome_follower__mutmut_4
    }
    
    def become_follower(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁbecome_follower__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁbecome_follower__mutmut_mutants"), args, kwargs, self)
        return result 
    
    become_follower.__signature__ = _mutmut_signature(xǁRaftNodeǁbecome_follower__mutmut_orig)
    xǁRaftNodeǁbecome_follower__mutmut_orig.__name__ = 'xǁRaftNodeǁbecome_follower'
    def xǁRaftNodeǁappend_entry__mutmut_orig(self, entry: Dict):
        self.log.append(entry)
        logger.info(f"Node {self.node_id} appended entry: {entry}")
    def xǁRaftNodeǁappend_entry__mutmut_1(self, entry: Dict):
        self.log.append(None)
        logger.info(f"Node {self.node_id} appended entry: {entry}")
    def xǁRaftNodeǁappend_entry__mutmut_2(self, entry: Dict):
        self.log.append(entry)
        logger.info(None)
    
    xǁRaftNodeǁappend_entry__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁappend_entry__mutmut_1': xǁRaftNodeǁappend_entry__mutmut_1, 
        'xǁRaftNodeǁappend_entry__mutmut_2': xǁRaftNodeǁappend_entry__mutmut_2
    }
    
    def append_entry(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁappend_entry__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁappend_entry__mutmut_mutants"), args, kwargs, self)
        return result 
    
    append_entry.__signature__ = _mutmut_signature(xǁRaftNodeǁappend_entry__mutmut_orig)
    xǁRaftNodeǁappend_entry__mutmut_orig.__name__ = 'xǁRaftNodeǁappend_entry'
