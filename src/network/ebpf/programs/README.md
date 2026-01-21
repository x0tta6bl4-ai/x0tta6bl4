# x0tta6bl4 eBPF Programs

This directory contains eBPF programs for mesh network observability.

## Programs

### xdp_counter.c
**Purpose**: Count packets by protocol (TCP, UDP, ICMP, Other)  
**Type**: XDP (eXpress Data Path)  
**Features**:
- Per-CPU counters for zero-overhead
- Protocol classification
- Ring buffer output (optional)

**Compilation**:
```bash
make xdp_counter.o
# Or manually:
clang -O2 -g -target bpf -c xdp_counter.c -o xdp_counter.o
```

**Loading**:
```python
from src.network.ebpf.loader import EBPFLoader, EBPFProgramType

loader = EBPFLoader()
program_id = loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
loader.attach_to_interface(program_id, "eth0")
```

## Requirements

### Build Tools
- `clang >= 10` (for eBPF compilation)
- `llvm >= 10`
- Linux kernel headers (`linux-headers-$(uname -r)`)

### Runtime
- Kernel >= 5.8 (for CO-RE support)
- BTF available (`/sys/kernel/btf/vmlinux`)
- `bpftool` (for program loading)
- `ip` command (for XDP attachment)

## Compilation

### Using Makefile
```bash
cd src/network/ebpf/programs
make all          # Compile all programs
make xdp_counter.o  # Compile specific program
make clean        # Clean object files
make verify       # Verify compiled programs
```

### Manual Compilation
```bash
# Basic (no CO-RE)
clang -O2 -target bpf -c xdp_counter.c -o xdp_counter.o

# With CO-RE support (recommended)
clang -O2 -g -target bpf -c xdp_counter.c -o xdp_counter.o
```

## Testing

### Load and Attach
```python
from src.network.ebpf.loader import EBPFLoader, EBPFProgramType

loader = EBPFLoader()
program_id = loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
loader.attach_to_interface(program_id, "eth0", mode="native")
```

### Check Status
```bash
# Check if XDP is attached
ip link show dev eth0

# View program info
bpftool prog show

# View maps
bpftool map show
```

### Read Counters
```python
from src.network.ebpf.map_reader import EBPFMapReader, read_packet_counters

# Read packet counters
counters = read_packet_counters("packet_counters")
print(counters)  # {'TCP': 1234, 'UDP': 5678, ...}

# Or use the reader directly
reader = EBPFMapReader()
all_maps = reader.list_maps()
map_data = reader.read_map(map_name="packet_counters")
```

Or using bpftool CLI:
```bash
bpftool map dump name packet_counters
```

## Troubleshooting

### "clang: error: unsupported target 'bpf'"
**Solution**: Install clang >= 10 or use `-target bpf` with full path to bpf target

### "BTF not available"
**Solution**: Kernel >= 5.8 required. Check: `ls /sys/kernel/btf/vmlinux`

### "XDP attachment failed"
**Solution**: 
- Check interface exists: `ip link show`
- Check driver support: `ethtool -k eth0 | grep xdp`
- Try generic mode: `mode="generic"`

## Next Programs

- `kprobe_syscall_latency.c` - Syscall latency tracking
- `tc_classifier.c` - Traffic control classifier
- `tracepoint_net.c` - Network tracepoint hooks
