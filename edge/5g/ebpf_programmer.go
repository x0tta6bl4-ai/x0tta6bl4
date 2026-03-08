package edge5g

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/cilium/ebpf"
)

// EBPFPolicyProgrammer implements PolicyProgrammer by writing to a pinned eBPF map.
type EBPFPolicyProgrammer struct {
	MapPath string
	ebpfMap *ebpf.Map
}

// NewEBPFPolicyProgrammer loads a pinned eBPF map for policy programming.
func NewEBPFPolicyProgrammer(mapPath string) (*EBPFPolicyProgrammer, error) {
	m, err := ebpf.LoadPinnedMap(mapPath, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to load pinned slice_policy_map at %s: %w", mapPath, err)
	}
	return &EBPFPolicyProgrammer{MapPath: mapPath, ebpfMap: m}, nil
}

// Apply updates the eBPF map with the new policy.
// It expects SliceID to be a numeric string representing the target UDP port.
func (p *EBPFPolicyProgrammer) Apply(update PolicyUpdate) error {
	if p.ebpfMap == nil {
		return fmt.Errorf("ebpf map not initialized")
	}

	// The current eBPF enforcer uses UDP port as a proxy for Slice ID.
	port64, err := strconv.ParseUint(strings.TrimSpace(update.SliceID), 10, 32)
	if err != nil {
		// Fallback for non-numeric SliceIDs in tests/simulations if needed,
		// but for real hardware enforcer, we require a port.
		return fmt.Errorf("invalid slice ID %q: must be a numeric UDP port for real eBPF enforcer", update.SliceID)
	}

	port := uint32(port64)
	priority := uint32(update.Priority)

	if err := p.ebpfMap.Put(&port, &priority); err != nil {
		return fmt.Errorf("failed to update eBPF map: %w", err)
	}

	return nil
}

// NewRealEBPFQoSEnforcer creates a real eBPF QoSEnforcer using the pinned map at mapPath.
func NewRealEBPFQoSEnforcer(mapPath string) (*RealEBPFQoSEnforcer, error) {
	prog, err := NewEBPFPolicyProgrammer(mapPath)
	if err != nil {
		return nil, err
	}
	return &RealEBPFQoSEnforcer{Programmer: prog}, nil
}

// Close releases the eBPF map handle.
func (p *EBPFPolicyProgrammer) Close() error {
	if p.ebpfMap != nil {
		return p.ebpfMap.Close()
	}
	return nil
}
