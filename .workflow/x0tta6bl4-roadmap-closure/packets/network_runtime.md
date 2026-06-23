# Packet: network_runtime

## Objective

Verify the local eBPF pulse C change far enough to make the packet reviewable.

## Context

The release roadmap still separates local eBPF checks from live XDP attach and
PPS claims. This packet can compile the changed BPF program locally, but it
does not prove live attach, throughput, provider bypass, or production runtime
behavior.

## Files

- `src/network/ebpf/x0tta6bl4_pulse.bpf.c`

## Do

- Run a non-mutating `clang -target bpf` compile to `/tmp`.
- Preserve the no-production-claim boundary.

## Do Not

- Attach XDP to a real interface without explicit approval.
- Run destructive network or production commands.
- Treat compile success as live dataplane proof.

## Verification

- `clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c src/network/ebpf/x0tta6bl4_pulse.bpf.c -o /tmp/x0tta6bl4_pulse.bpf.o`
