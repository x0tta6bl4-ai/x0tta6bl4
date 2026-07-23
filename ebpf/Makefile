all: generate

generate:
	GOPACKAGE=main go run github.com/cilium/ebpf/cmd/bpf2go -cflags "-I/usr/include -I/usr/include/x86_64-linux-gnu" -target amd64 LatencyTracker latency_tracker.bpf.c
	GOPACKAGE=main go run github.com/cilium/ebpf/cmd/bpf2go -cflags "-I/usr/include -I/usr/include/x86_64-linux-gnu" -target amd64 ConnectionTracker connection_tracker.bpf.c
	GOPACKAGE=main go run github.com/cilium/ebpf/cmd/bpf2go -cflags "-I/usr/include -I/usr/include/x86_64-linux-gnu" -target amd64 BandwidthMonitor bandwidth_monitor.bpf.c
