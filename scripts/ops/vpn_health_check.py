#!/usr/bin/env python3
"""
x0tta6bl4 VPN Health Diagnostics Tool.
Runs comprehensive parallel checks across Athlon PC, NL VPS, and Moscow VDS.
"""

import sys
import subprocess
import concurrent.futures
import json
import socket
from datetime import datetime

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

NL_IP = "89.125.1.107"
MSK_IP = "84.54.47.103"


def run_local(cmd: list[str]) -> tuple[int, str]:
    """Runs a local shell command safely."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return res.returncode, res.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def run_remote(host: str, cmd: str) -> tuple[int, str]:
    """Runs a remote command over SSH with strict timeouts."""
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes",
        f"root@{host}",
        cmd
    ]
    return run_local(ssh_cmd)


def check_ping(ip: str) -> str:
    """Checks ping latency to a host."""
    code, out = run_local(["ping", "-c", "2", "-W", "2", ip])
    if code != 0:
        return f"{RED}Unreachable{RESET}"
    # Parse latency
    try:
        for line in out.splitlines():
            if "rtt min/avg/max" in line:
                avg = line.split("/")[4]
                return f"{GREEN}Online{RESET} ({avg} ms)"
    except Exception:
        pass
    return f"{GREEN}Online{RESET}"


def check_local() -> dict:
    """Runs checks on the local Athlon PC."""
    results = {}
    
    # 1. Check Gateway Ping
    results["gateway_ping"] = check_ping("192.168.100.1")
    
    # 2. Check sing-box process
    code, out = run_local(["pgrep", "-f", "sing-box"])
    results["singbox_process"] = f"{GREEN}Running (PID {out}){RESET}" if code == 0 else f"{RED}Not running{RESET}"
    
    # 3. Check singbox_tun MTU
    code, out = run_local(["ip", "link", "show", "singbox_tun"])
    if code == 0 and "mtu" in out:
        try:
            mtu = out.split("mtu")[1].split()[0]
            color = GREEN if mtu == "1360" else YELLOW
            results["tun_mtu"] = f"{color}{mtu}{RESET} (Recommended: 1360)"
        except Exception:
            results["tun_mtu"] = f"{YELLOW}Unknown{RESET}"
    else:
        results["tun_mtu"] = f"{RED}Interface singbox_tun not found{RESET}"
        
    # 4. Check eBPF XDP on enp8s0
    code, out = run_local(["ip", "link", "show", "enp8s0"])
    if code == 0 and "xdp" in out:
        try:
            prog_id = out.split("prog/xdp id")[1].split()[0]
            results["ebpf_xdp"] = f"{GREEN}Loaded (ID {prog_id}){RESET}"
        except Exception:
            results["ebpf_xdp"] = f"{GREEN}Loaded{RESET}"
    else:
        results["ebpf_xdp"] = f"{YELLOW}No XDP program bound{RESET}"
        
    # 5. Check Bypass Rules
    code, out = run_local(["ip", "rule", "show"])
    rules = out.splitlines()
    has_nl = any(NL_IP in r and "lookup main" in r for r in rules)
    has_msk = any(MSK_IP in r and "lookup main" in r for r in rules)
    
    results["rule_nl_bypass"] = f"{GREEN}Present{RESET}" if has_nl else f"{RED}Missing{RESET}"
    results["rule_msk_bypass"] = f"{GREEN}Present{RESET}" if has_msk else f"{RED}Missing{RESET}"
    
    return results


def check_nl() -> dict:
    """Runs checks on the NL VPS."""
    results = {}
    
    # 1. Ping Check
    results["ping"] = check_ping(NL_IP)
    
    # SSH Check
    code, _ = run_remote(NL_IP, "echo 1")
    if code != 0:
        results["ssh"] = f"{RED}SSH connection failed{RESET}"
        return results
    results["ssh"] = f"{GREEN}OK{RESET}"
    
    # 2. Services Check
    services = ["x-ui", "nginx", "wg-quick@x0tctrl", "ghost-vpn", "x0t-agent"]
    for s in services:
        c, out = run_remote(NL_IP, f"systemctl is-active {s}")
        results[s] = f"{GREEN}active{RESET}" if out == "active" else f"{RED}{out}{RESET}"
        
    # 3. Nginx resets check (last hour)
    c, out = run_remote(NL_IP, "grep -c 'Connection reset by peer' /var/log/nginx/error.log || echo 0")
    try:
        resets = int(out)
        color = GREEN if resets < 50 else (YELLOW if resets < 200 else RED)
        results["nginx_resets"] = f"{color}{resets} resets{RESET} in log"
    except Exception:
        results["nginx_resets"] = f"{YELLOW}Unknown{RESET}"
        
    # 4. WireGuard active peers
    c, out = run_remote(NL_IP, "wg show x0tctrl peers | wc -l")
    try:
        peers = int(out)
        results["wg_peers"] = f"{GREEN}{peers} active peers{RESET}"
    except Exception:
        results["wg_peers"] = f"{YELLOW}Unknown{RESET}"
        
    return results


def check_msk() -> dict:
    """Runs checks on the Moscow VDS."""
    results = {}
    
    # 1. Ping Check
    results["ping"] = check_ping(MSK_IP)
    
    # SSH Check
    code, _ = run_remote(MSK_IP, "echo 1")
    if code != 0:
        results["ssh"] = f"{RED}SSH connection failed{RESET}"
        return results
    results["ssh"] = f"{GREEN}OK{RESET}"
    
    # 2. Services Check
    services = ["xray", "fail2ban"]
    for s in services:
        c, out = run_remote(MSK_IP, f"systemctl is-active {s}")
        results[s] = f"{GREEN}active{RESET}" if out == "active" else f"{RED}{out}{RESET}"
        
    # 3. Fail2ban status
    c, out = run_remote(MSK_IP, "fail2ban-client status sshd | grep -i 'banned'")
    results["fail2ban_bans"] = f"{GREEN}{out.strip()}{RESET}" if c == 0 else f"{YELLOW}Unavailable{RESET}"
    
    # 4. Check DNS & QUIC rules in xray config
    c, out = run_remote(MSK_IP, "cat /usr/local/etc/xray/config.json")
    if c == 0:
        try:
            cfg = json.loads(out)
            has_dns = "dns" in cfg
            rules = cfg.get("routing", {}).get("rules", [])
            has_quic_block = any(r.get("port") == 443 and r.get("network") == "udp" and r.get("outboundTag") == "block" for r in rules)
            results["xray_dns"] = f"{GREEN}Configured{RESET}" if has_dns else f"{YELLOW}Missing{RESET}"
            results["quic_block"] = f"{GREEN}Active{RESET}" if has_quic_block else f"{YELLOW}Inactive{RESET}"
        except Exception:
            results["xray_dns"] = f"{RED}Config parse error{RESET}"
            results["quic_block"] = f"{RED}Config parse error{RESET}"
    else:
        results["xray_dns"] = f"{RED}Config not found{RESET}"
        results["quic_block"] = f"{RED}Config not found{RESET}"
        
    return results


def main():
    print(f"\n{BOLD}{CYAN}=== x0tta6bl4 VPN NETWORK HEALTH CHECK ==={RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_local = executor.submit(check_local)
        future_nl = executor.submit(check_nl)
        future_msk = executor.submit(check_msk)
        
        # Gather results
        local_res = future_local.result()
        nl_res = future_nl.result()
        msk_res = future_msk.result()
        
    # 1. Print Local Results
    print(f"{BOLD}[🖥️ LOCAL ATHLON PC]{RESET}")
    print(f"  Gateway ping (192.168.100.1):  {local_res.get('gateway_ping')}")
    print(f"  sing-box process status:       {local_res.get('singbox_process')}")
    print(f"  TUN interface MTU:             {local_res.get('tun_mtu')}")
    print(f"  eBPF XDP status (enp8s0):      {local_res.get('ebpf_xdp')}")
    print(f"  NL VPS IP bypass rule (8999):  {local_res.get('rule_nl_bypass')}")
    print(f"  MSK VDS IP bypass rule (8998): {local_res.get('rule_msk_bypass')}")
    print()
    
    # 2. Print NL VPS Results
    print(f"{BOLD}[🌐 NETHERLANDS HUB ({NL_IP})]{RESET}")
    print(f"  Ping latency:                  {nl_res.get('ping')}")
    print(f"  SSH management access:         {nl_res.get('ssh')}")
    if nl_res.get("ssh") == f"{GREEN}OK{RESET}":
        print(f"  x-ui panel service:            {nl_res.get('x-ui')}")
        print(f"  Nginx SNI Router:              {nl_res.get('nginx')}")
        print(f"  WireGuard Mesh interface:      {nl_res.get('wg-quick@x0tctrl')}")
        print(f"  FirstParty VPN Agent:          {nl_res.get('x0t-agent')}")
        print(f"  Ghost VPN v2.0 (Stego):        {nl_res.get('ghost-vpn')}")
        print(f"  WireGuard active peer count:   {nl_res.get('wg_peers')}")
        print(f"  Nginx stream error counters:   {nl_res.get('nginx_resets')}")
    print()
    
    # 3. Print Moscow VDS Results
    print(f"{BOLD}[🇷🇺 MOSCOW ENTRY NODE ({MSK_IP})]{RESET}")
    print(f"  Ping latency:                  {msk_res.get('ping')}")
    print(f"  SSH management access:         {msk_res.get('ssh')}")
    if msk_res.get("ssh") == f"{GREEN}OK{RESET}":
        print(f"  xray service (VLESS Reality):  {msk_res.get('xray')}")
        print(f"  fail2ban service (sshd):       {msk_res.get('fail2ban')}")
        print(f"  fail2ban active bans:          {msk_res.get('fail2ban_bans')}")
        print(f"  Reality DNS over Tunnel:       {msk_res.get('xray_dns')}")
        print(f"  UDP/443 QUIC blocking rule:    {msk_res.get('quic_block')}")
    print()
    print(f"{BOLD}{CYAN}=== END OF DIAGNOSTICS ==={RESET}\n")


if __name__ == "__main__":
    main()
