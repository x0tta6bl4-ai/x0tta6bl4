all: generate

generate:
	go run github.com/cilium/ebpf/cmd/bpf2go -type latency_map LatencyTracker latency_tracker.bpf.c
	go run github.com/cilium/ebpf/cmd/bpf2go -type conn_map ConnectionTracker connection_tracker.bpf.c
	go run github.com/cilium/ebpf/cmd/bpf2go -type bandwidth_map BandwidthMonitor bandwidth_monitor.bpf.c
