#!/usr/bin/python3
import time

from bcc import BPF

# 1. Load BPF program
cflags = ["-I/usr/src/linux-headers-6.14.0-37-generic/include"]
b = BPF(src_file="src/network/ebpf/programs/xdp_counter.c", cflags=cflags)

# 2. Attach to interface
device = "lo"
b.attach_xdp(device, fn=b.load_func("xdp_counter_prog", BPF.XDP))

# 3. Read map
packet_count = b.get_table("packet_count")
prev_count = 0
print("Printing packet counts, hit CTRL+C to stop")
while True:
    try:
        current_count = packet_count[0].value
        if current_count != prev_count:
            print(f"Packet count on {device}: {current_count}")
            prev_count = current_count
        time.sleep(1)
    except KeyboardInterrupt:
        print("Detaching XDP program...")
        break

# 4. Detach
b.remove_xdp(device)
