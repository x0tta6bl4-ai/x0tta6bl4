package edge5g

import (
	"fmt"
	"runtime"

	"github.com/cilium/ebpf"
)

type BPFStats struct {
	Total     uint64
	Passed    uint64
	Dropped   uint64
	Forwarded uint64
}

type QoSMonitor interface {
	GetPacketStats() (BPFStats, error)
	GetEstimatedLatencyMs(ueID string) int64
}

type EBPFQoSMonitor struct {
	MapPath string
	ebpfMap *ebpf.Map
}

func NewEBPFQoSMonitor(mapPath string) (*EBPFQoSMonitor, error) {
	m, err := ebpf.LoadPinnedMap(mapPath, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to load pinned packet_stats map at %s: %w", mapPath, err)
	}
	return &EBPFQoSMonitor{MapPath: mapPath, ebpfMap: m}, nil
}

func (m *EBPFQoSMonitor) GetPacketStats() (BPFStats, error) {
	var stats BPFStats
	if m.ebpfMap == nil {
		return stats, fmt.Errorf("ebpf map not initialized")
	}

	numCPUs := runtime.NumCPU()
	
	// Read TOTAL (key 0)
	var totalKey uint32 = 0
	totalVals := make([]uint64, numCPUs)
	if err := m.ebpfMap.Lookup(&totalKey, &totalVals); err == nil {
		for _, v := range totalVals { stats.Total += v }
	}

	// Read PASSED (key 1)
	var passedKey uint32 = 1
	passedVals := make([]uint64, numCPUs)
	if err := m.ebpfMap.Lookup(&passedKey, &passedVals); err == nil {
		for _, v := range passedVals { stats.Passed += v }
	}

	// Read DROPPED (key 2)
	var droppedKey uint32 = 2
	droppedVals := make([]uint64, numCPUs)
	if err := m.ebpfMap.Lookup(&droppedKey, &droppedVals); err == nil {
		for _, v := range droppedVals { stats.Dropped += v }
	}

	// Read FORWARDED (key 3)
	var fwdKey uint32 = 3
	fwdVals := make([]uint64, numCPUs)
	if err := m.ebpfMap.Lookup(&fwdKey, &fwdVals); err == nil {
		for _, v := range fwdVals { stats.Forwarded += v }
	}

	return stats, nil
}

func (m *EBPFQoSMonitor) GetEstimatedLatencyMs(ueID string) int64 {
	// Baseline derived from packet stats activity (simulated bridging logic)
	stats, err := m.GetPacketStats()
	if err != nil || stats.Total == 0 {
		return 25 // fallback baseline
	}
	
	// Heuristic: latency increases slightly under heavy drop rates
	dropRatio := float64(stats.Dropped) / float64(stats.Total)
	return int64(15 + (dropRatio * 100))
}

type MockQoSMonitor struct{}

func (m *MockQoSMonitor) GetPacketStats() (BPFStats, error) {
	return BPFStats{Total: 1000, Passed: 900, Dropped: 10, Forwarded: 90}, nil
}

func (m *MockQoSMonitor) GetEstimatedLatencyMs(ueID string) int64 {
	return 25
}
