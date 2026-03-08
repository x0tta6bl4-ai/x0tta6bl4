#!/usr/bin/env python3
import os
import sys
import subprocess

def populate_mac_tables(iface_name, target_ip, next_hop_mac):
    print(f"🔧 Populating MAC tables for {iface_name} -> {target_ip} ({next_hop_mac})")
    
    # 1. Get interface index
    try:
        with open(f"/sys/class/net/{iface_name}/ifindex", "r") as f:
            ifindex = int(f.read().strip())
    except Exception as e:
        print(f"❌ Error getting ifindex: {e}")
        return

    # 2. Get local MAC address
    try:
        with open(f"/sys/class/net/{iface_name}/address", "r") as f:
            local_mac = f.read().strip().replace(":", "")
    except Exception as e:
        print(f"❌ Error getting local MAC: {e}")
        return

    print(f"  Interface: {iface_name} (index: {ifindex}, MAC: {local_mac})")

    # 3. Use bpftool to populate maps (if programs are loaded)
    # This is a template for the operator
    print("\n📝 Run these commands to populate the maps:")
    print(f"# Set egress port mapping")
    print(f"bpftool map update name mesh_forwarding_routes key hex {target_ip} value {ifindex:08x}")
    print(f"# Set next-hop destination MAC")
    print(f"bpftool map update name neigh_mac_table key hex {target_ip} value {next_hop_mac.replace(':', '')}")
    print(f"# Set local source MAC for egress")
    print(f"bpftool map update name src_mac_table key {ifindex} value hex {local_mac}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 populate_mac_tables.py <iface> <target_ip_hex> <next_hop_mac>")
        print("Example: python3 populate_mac_tables.py eth0 c0a80101 00:11:22:33:44:55")
        sys.exit(1)
    
    populate_mac_tables(sys.argv[1], sys.argv[2], sys.argv[3])
