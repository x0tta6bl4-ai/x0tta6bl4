package sensor

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go NetworkSensor network_sensor.bpf.c -- -I/usr/include/x86_64-linux-gnu
