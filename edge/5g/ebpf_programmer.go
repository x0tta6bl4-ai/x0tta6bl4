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

func validateEBPFPriority(priority int) error {
	if priority < 0 || priority > 255 {
		return fmt.Errorf("invalid priority %d: must be within eBPF range 0-255", priority)
	}
	return nil
}

func parseSliceIDPort(sliceID string) (uint32, error) {
	trimmed := strings.TrimSpace(sliceID)
	if trimmed == "" {
		return 0, fmt.Errorf("invalid slice ID %q: must be a numeric UDP port for real eBPF enforcer", sliceID)
	}

	port64, err := strconv.ParseUint(trimmed, 10, 16)
	if err != nil || port64 == 0 {
		return 0, fmt.Errorf("invalid slice ID %q: must be a numeric UDP port for real eBPF enforcer", sliceID)
	}
	return uint32(port64), nil
}

// NewEBPFPolicyProgrammer loads a pinned eBPF map for policy programming.
func NewEBPFPolicyProgrammer(mapPath string) (*EBPFPolicyProgrammer, error) {
	trimmedPath := strings.TrimSpace(mapPath)
	if trimmedPath == "" {
		return nil, fmt.Errorf("ebpf map path required")
	}

	m, err := ebpf.LoadPinnedMap(trimmedPath, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to load pinned slice_policy_map at %s: %w", trimmedPath, err)
	}
	return &EBPFPolicyProgrammer{MapPath: trimmedPath, ebpfMap: m}, nil
}

// Apply updates the eBPF map with the new policy.
// It expects SliceID to be a numeric string representing the target UDP port.
func (p *EBPFPolicyProgrammer) Apply(update PolicyUpdate) error {
	if p.ebpfMap == nil {
		return fmt.Errorf("ebpf map not initialized")
	}

	// The current eBPF enforcer uses UDP port as a proxy for Slice ID.
	port, err := parseSliceIDPort(update.SliceID)
	if err != nil {
		return err
	}
	if err := validateEBPFPriority(update.Priority); err != nil {
		return err
	}
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
