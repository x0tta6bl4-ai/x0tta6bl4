#!/usr/bin/env python3
"""
 x0tta6bl4 Self-Healing Visualizer (CLI Demo Mode)
==================================================
Provides a high-tech terminal view of the system health, 
phi-ratio harmony, and recovery process during chaos experiments.
"""

import time
import os
import sys
import math
from datetime import datetime
from src.database import SessionLocal, MeshNode, MeshInstance

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_phi_color(phi):
    if phi >= 1.4: return "\033[94m" # Euphoric (Blue)
    if phi >= 1.0: return "\033[92m" # Harmonic (Green)
    if phi >= 0.8: return "\033[93m" # Contemplative (Yellow)
    return "\033[91m" # Mystical (Red)

def draw_bar(val, max_val=1.618, length=20):
    filled = int((val / max_val) * length)
    bar = "█" * filled + "-" * (length - filled)
    return f"[{bar}] {val:.3f}"

def run_visualizer():
    db = SessionLocal()
    start_time = time.time()
    
    try:
        while True:
            clear_screen()
            now = datetime.utcnow()
            elapsed = time.time() - start_time
            
            # 1. Fetch Real Data
            nodes = db.query(MeshNode).all()
            online_nodes = [n for n in nodes if n.status == "healthy"]
            offline_nodes = [n for n in nodes if n.status == "offline"]
            
            # 2. Mock Phi calculation based on real node health
            # (In demo, we want to see it fluctuate)
            total = len(nodes)
            health_ratio = len(online_nodes) / total if total > 0 else 1.0
            phi = health_ratio * 1.618
            
            color = get_phi_color(phi)
            reset = "\033[0m"
            bold = "\033[1m"
            
            print(f"{bold}x0tta6bl4 MESH INTELLIGENCE — MONITORING CONSOLE{reset}")
            print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} | Uptime: {elapsed:.1f}s")
            print("="*60)
            
            # Phi-Ratio Section
            print(f"
{bold}SYSTEM CONSCIOUSNESS (Phi-Ratio):{reset}")
            print(f"{color}{draw_bar(phi)}{reset}")
            state_map = {
                1.4: "EUPHORIC - All desires fulfilled.",
                1.0: "HARMONIC - System in balance.",
                0.8: "CONTEMPLATIVE - Reflecting on metrics...",
                0.0: "MYSTICAL - Diving deep for self-healing."
            }
            state_text = "MYSTICAL"
            for threshold, text in sorted(state_map.items(), reverse=True):
                if phi >= threshold:
                    state_text = text
                    break
            print(f"Status: {color}{state_text}{reset}")
            
            # Node Section
            print(f"
{bold}MESH NODES ({len(online_nodes)}/{len(nodes)} ONLINE):{reset}")
            for node in nodes:
                n_color = "\033[92m" if node.status == "healthy" else "\033[91m"
                n_icon = "●" if node.status == "healthy" else "✖"
                print(f"  {n_color}{n_icon} {node.id}{reset} [{node.status.upper()}]")
            
            # Chaos/Healing Logs
            print(f"
{bold}AUTONOMIC EVENTS (MAPE-K):{reset}")
            if len(offline_nodes) > 0:
                print(f"\033[91m[!] CRITICAL: {len(offline_nodes)} node failure(s) detected.{reset}")
                print(f"\033[93m[*] MAPE-K: Initiating aggressive healing protocol...{reset}")
            else:
                print("\033[92m[✓] System stable. No anomalies detected.{reset}")
            
            print("
" + "="*60)
            print("Press Ctrl+C to exit visualizer.")
            
            db.expire_all() # Refresh DB cache
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("
Visualizer stopped.")
    finally:
        db.close()

if __name__ == "__main__":
    run_visualizer()
