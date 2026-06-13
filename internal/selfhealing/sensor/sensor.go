package sensor

import (
	"context"
	"log"
	"net"
	"time"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/rlimit"
	"x0tta6bl4/internal/selfhealing/actuator"
)

// NetworkSensor monitors network anomalies using eBPF.
type NetworkSensor struct {
	iface     string
	objects   NetworkSensorObjects
	link      link.Link
	threshold uint64
	exec      *actuator.Executor
	brain     actuator.AILogic
}

func NewNetworkSensor(iface string, threshold uint64, exec *actuator.Executor, brain actuator.AILogic) (*NetworkSensor, error) {
	// Allow the current process to lock memory for eBPF resources.
	if err := rlimit.RemoveMemlock(); err != nil {
		return nil, err
	}

	// Load pre-compiled programs and maps into the kernel.
	objs := NetworkSensorObjects{}
	if err := LoadNetworkSensorObjects(&objs, nil); err != nil {
		return nil, err
	}

	// Look up the network interface by name.
	ifaceIdx, err := net.InterfaceByName(iface)
	if err != nil {
		objs.Close()
		return nil, err
	}

	// Attach the program.
	l, err := link.AttachXDP(link.XDPOptions{
		Program:   objs.XdpRstSensor,
		Interface: ifaceIdx.Index,
	})
	if err != nil {
		objs.Close()
		return nil, err
	}

	return &NetworkSensor{
		iface:     iface,
		objects:   objs,
		link:      l,
		threshold: threshold,
		exec:      exec,
		brain:     brain,
	}, nil
}

func (s *NetworkSensor) StartPolling(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("[Sensor] Started polling on %s (Threshold: %d RSTs)\n", s.iface, s.threshold)

	var lastCount uint64
	for range ticker.C {
		var currentCount uint64
		// PERCPU_ARRAY map returns a slice of values, one for each CPU.
		var cpuCounts []uint64
		if err := s.objects.RstCount.Lookup(uint32(0), &cpuCounts); err != nil {
			log.Printf("[Sensor] Map lookup failed: %v\n", err)
			continue
		}

		for _, c := range cpuCounts {
			currentCount += c
		}

		diff := currentCount - lastCount
		if diff > s.threshold {
			log.Printf("[Sensor] ANOMALY DETECTED: %d TCP RSTs in %v. Triggering AI diagnosis...\n", diff, interval)
			s.triggerHealing(diff)
		}
		lastCount = currentCount
	}
}

func (s *NetworkSensor) triggerHealing(rstCount uint64) {
	// 1. Collect system dump
	// In a real scenario, we would use real logs/metrics.
	dump := actuator.SystemDump{
		NodeID:          "nl-edge-01",
		Timestamp:       time.Now().Format(time.RFC3339),
		FailedComponent: "network-stack",
		JournalLogs:     []string{"eBPF: High TCP RST count detected"},
		Metrics: map[string]string{
			"tcp_rst_count": string(rstCount),
			"interface":     s.iface,
		},
	}

	// 2. Request analysis and apply plan
	// We run this in a background goroutine to not block the sensor polling
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()

		plan, err := s.brain.AnalyzeState(ctx, dump)
		if err != nil {
			log.Printf("[Sensor] AI analysis failed: %v\n", err)
			return
		}
		if err := s.exec.ApplyPlan(plan); err != nil {
			log.Printf("[Sensor] Actuator failed to apply plan: %v\n", err)
		}
	}()
}

func (s *NetworkSensor) Close() {
	s.link.Close()
	s.objects.Close()
}
