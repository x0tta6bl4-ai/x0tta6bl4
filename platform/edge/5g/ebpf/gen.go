package ebpf

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go -target amd64 qos qos_enforcer.c
