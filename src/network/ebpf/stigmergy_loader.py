"""
eBPF Loader for Stigmergy Routing.
Manages the lifecycle of the BPF program and performs 'pheromone evaporation'.
"""

import time
import asyncio
import logging
import os
from bcc import BPF

logger = logging.getLogger(__name__)

class StigmergyBPF:
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.bpf = None
        self.running = False
        
    def load(self):
        """Compile and load BPF program."""
        src_path = os.path.join(os.path.dirname(__file__), "stigmergy_kern.c")
        
        # BCC compiles C code on the fly
        # We need to adapt the C code slightly for BCC syntax if not using libbpf
        # Or we can write inline C for BCC. 
        # Let's use BCC's BPF() wrapper which handles most things.
        # Note: raw XDP code often needs slight tweaks for BCC vs libbpf.
        # Here we assume we can load the source file.
        
        try:
            self.bpf = BPF(src_file=src_path)
            fn = self.bpf.load_func("xdp_prog", BPF.XDP)
            self.bpf.attach_xdp(self.interface, fn, 0)
            logger.info(f"🐜 eBPF Stigmergy loaded on {self.interface}")
            self.running = True
        except Exception as e:
            logger.error(f"Failed to load eBPF: {e}")
            raise

    def unload(self):
        if self.bpf:
            self.bpf.remove_xdp(self.interface, 0)
            self.running = False
            logger.info("eBPF unloaded")

    async def evaporation_loop(self):
        """
        Periodically decay scores in the BPF map.
        Accessing BPF maps from user space is fast.
        """
        if not self.bpf:
            return

        pheromone_map = self.bpf.get_table("pheromone_map")
        
        while self.running:
            await asyncio.sleep(1.0) # 1 second tick
            
            # Iterate and decay
            # Note: Modifying map while iterating can be tricky in BPF, 
            # but from userspace it's generally safe-ish for updates.
            # We treat keys as read-only, update values.
            
            for key, leaf in pheromone_map.items():
                current_score = leaf.value
                new_score = int(current_score * 0.9) # 10% decay
                
                if new_score < 5:
                    # Prune dead paths to save map space
                    try:
                        del pheromone_map[key]
                    except:
                        pass
                else:
                    pheromone_map[key] = new_score
                    
    def get_stats(self):
        """Return current pheromone map for visualization."""
        if not self.bpf: 
            return {}
        
        stats = {}
        pheromone_map = self.bpf.get_table("pheromone_map")
        for k, v in pheromone_map.items():
            # Convert u32 IP to string
            ip = self._int_to_ip(k.value)
            stats[ip] = v.value
        return stats

    def _int_to_ip(self, ip_int):
        import socket
        import struct
        return socket.inet_ntoa(struct.pack("!I", ip_int))
