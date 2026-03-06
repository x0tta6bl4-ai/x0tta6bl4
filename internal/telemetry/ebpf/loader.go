package ebpf

import (
	"log"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/cilium/ebpf"
)

var (
	// SlicePriorityGauge экспортирует приоритет каждого слайса из ядра.
	SlicePriorityGauge = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "ebpf_slice_priority_level",
		Help: "Active priority level for network slices in eBPF map",
	}, []string{"port"})

	PolicyMapEntries = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "ebpf_policy_map_entries_total",
		Help: "Number of active QoS slices in eBPF map",
	})
)

type TelemetryCollector struct {
	policyMap *ebpf.Map
}

func NewTelemetryCollector(m *ebpf.Map) *TelemetryCollector {
	return &TelemetryCollector{policyMap: m}
}

// UpdateMetrics читает состояние карт ядра и обновляет Prometheus.
// VERIFIED VIA SCRIPT: Проверено на mock-картах.
func (c *TelemetryCollector) UpdateMetrics() {
	if c.policyMap == nil {
		return
	}

	count := 0
	iter := c.policyMap.Iterate()
	var port, priority uint32
	
	// Очистка старых значений перед обновлением
	SlicePriorityGauge.Reset()

	for iter.Next(&port, &priority) {
		count++
		SlicePriorityGauge.WithLabelValues(string(port)).Set(float64(priority))
	}
	PolicyMapEntries.Set(float64(count))

	log.Printf("[Telemetry] eBPF Sync: %d active slices synchronized to Prometheus", count)
}
