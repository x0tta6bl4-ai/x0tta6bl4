#!/usr/bin/env python3
"""
x0tta6bl4 VPN GUI - Native Implementation (Pro Version)
======================================================

Features:
- Full Tunneling / P2P Modes
- Kill Switch & IPv6 Protection
- Real-time stats
- Professional dark UI
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import asyncio
import base64
import os
import sys
import time

# Ensure project root is in path
sys.path.insert(0, "/mnt/projects")

from src.client.engine import QuantumShieldEngine

# Constants
ACCENT_COLOR = "#00f2ff"
BG_DARK = "#0a0a0c"
CARD_BG = "#16161a"
TEXT_COLOR = "#ffffff"
TEXT_GRAY = "#a0a0a8"
SUCCESS_COLOR = "#4ade80"
ERROR_COLOR = "#ff4444"

class QuantumShieldGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("x0tta6bl4 | Pro VPN")
        self.root.geometry("420x620")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(False, False)

        # VPN State
        self.engine = None
        self.is_connected = False
        self.is_starting = False

        # Variables
        self.mode = tk.StringVar(value="corporate")
        self.full_tunnel = tk.BooleanVar(value=True)
        self.kill_switch = tk.BooleanVar(value=True)

        # Load configuration
        self.key = os.getenv("VPN_ENCRYPTION_KEY", "VMYlEF9wQr47XZb4x+V1J57SWj4/bdNLVXWquSXaCyM=")
        self.server = os.getenv("VPN_SERVER", "89.125.1.107")
        self.port = int(os.getenv("VPN_PORT", "4433"))

        self._setup_styles()
        self._build_ui()
        self._update_loop()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_COLOR, font=("Inter", 10))
        style.configure("Header.TLabel", font=("Inter", 18, "bold"), foreground=ACCENT_COLOR)
        style.configure("Stat.TLabel", background=CARD_BG, font=("Inter", 9), foreground=TEXT_GRAY)
        style.configure("Value.TLabel", background=CARD_BG, font=("Inter", 14, "bold"), foreground=TEXT_COLOR)

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root, padding=25)
        header.pack(fill="x")
        ttk.Label(header, text="⚡ Quantum Shield PRO", style="Header.TLabel").pack(side="left")

        # Power Button / Canvas
        self.canvas = tk.Canvas(self.root, width=220, height=220, bg=BG_DARK, highlightthickness=0)
        self.canvas.pack(pady=5)
        self.outer_ring = self.canvas.create_oval(20, 20, 200, 200, outline=CARD_BG, width=5)
        self.glow = self.canvas.create_oval(40, 40, 180, 180, fill=BG_DARK, outline="")

        self.power_btn = tk.Button(
            self.root, text="CONNECT", font=("Inter", 14, "bold"),
            bg=BG_DARK, fg=TEXT_GRAY, activebackground=BG_DARK, activeforeground=ACCENT_COLOR,
            bd=0, cursor="hand2", command=self.toggle_vpn
        )
        self.canvas.create_window(110, 110, window=self.power_btn)

        # Stats
        stats = ttk.Frame(self.root, style="Card.TFrame", padding=20)
        stats.pack(fill="x", padx=35, pady=10)
        self._add_stat(stats, "STATUS", "Disconnected", 0, 0, "status_label")
        self._add_stat(stats, "UPTIME", "0s", 0, 1, "uptime_label")
        self._add_stat(stats, "TRAFFIC", "0 KB", 1, 0, "traffic_label")
        self._add_stat(stats, "TRANSPORT", "Ghost Pulse", 1, 1, "trans_label")

        # Config Options
        opts = ttk.Frame(self.root, padding=(35, 10))
        opts.pack(fill="x")

        tk.Checkbutton(opts, text="Full Tunnel (Safe)", variable=self.full_tunnel, **self._check_style()).pack(anchor="w")
        tk.Checkbutton(opts, text="Kill Switch (No Leaks)", variable=self.kill_switch, **self._check_style()).pack(anchor="w")

        # Mode Selection
        mode_frame = ttk.Frame(opts)
        mode_frame.pack(fill="x", pady=10)
        ttk.Label(mode_frame, text="Mode:", font=("Inter", 9)).pack(side="left")
        for t, v in [("Corporate", "corporate"), ("Whitelist", "whitelist")]:
            tk.Radiobutton(mode_frame, text=t, variable=self.mode, value=v,
                          selectcolor="#000", **self._check_style()).pack(side="left", padx=5)

    def _check_style(self):
        return {"bg": BG_DARK, "fg": TEXT_GRAY, "activebackground": BG_DARK,
                "activeforeground": ACCENT_COLOR, "font": ("Inter", 9), "bd": 0}

    def _add_stat(self, parent, label, value, row, col, attr):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)
        ttk.Label(f, text=label, style="Stat.TLabel").pack(anchor="w")
        v = ttk.Label(f, text=value, style="Value.TLabel")
        v.pack(anchor="w")
        setattr(self, attr, v)

    def toggle_vpn(self):
        if not self.is_connected and not self.is_starting:
            self.start_vpn()
        elif self.is_connected:
            self.stop_vpn()

    def start_vpn(self):
        self.is_starting = True
        self.power_btn.config(text="WAITING...", state="disabled")
        self.status_label.config(text="Hardening...", foreground=ACCENT_COLOR)

        try:
            key_bytes = base64.b64decode(self.key)
            self.engine = QuantumShieldEngine(
                key_bytes, self.server, self.port,
                mode=self.mode.get(),
                full_tunnel=self.full_tunnel.get(),
                kill_switch=self.kill_switch.get()
            )
            self.engine.set_status_callback(self._on_status)

            def run():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.engine.start())
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Connection Error", str(e)))
                finally:
                    self.root.after(0, self._on_dis)

            threading.Thread(target=run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Setup Error", str(e))
            self._on_dis()

    def _on_status(self, s):
        self.root.after(0, lambda: self.status_label.config(text=s))
        if s == "Protected":
            self.root.after(0, self._on_con)

    def _on_con(self):
        self.is_connected = True
        self.is_starting = False
        self.power_btn.config(text="DISCONNECT", state="normal", fg=SUCCESS_COLOR)
        self.status_label.config(foreground=SUCCESS_COLOR)
        self.canvas.itemconfig(self.glow, fill=ACCENT_COLOR, stipple="gray25")

    def stop_vpn(self):
        if self.engine: self.engine.stop()
        self._on_dis()

    def _on_dis(self):
        self.is_connected = False
        self.is_starting = False
        self.power_btn.config(text="CONNECT", state="normal", fg=TEXT_GRAY)
        self.status_label.config(text="Disconnected", foreground=ERROR_COLOR)
        self.canvas.itemconfig(self.outer_ring, outline=CARD_BG)
        self.canvas.itemconfig(self.glow, fill=BG_DARK)

    def _update_loop(self):
        if self.is_connected and self.engine:
            stats = self.engine.get_stats()
            self.uptime_label.config(text=f"{stats['uptime_sec']}s")
            self.traffic_label.config(text=f"{stats['sent_kb'] + stats['received_kb']} KB")
            color = SUCCESS_COLOR if (int(time.time()*2)%2) else ACCENT_COLOR
            self.canvas.itemconfig(self.outer_ring, outline=color)
        self.root.after(1000, self._update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = QuantumShieldGUI(root)
    root.mainloop()

