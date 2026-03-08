package edge5g

import "testing"

func TestValidateEBPFPriorityAcceptsRange(t *testing.T) {
	for _, priority := range []int{0, 1, 255} {
		if err := validateEBPFPriority(priority); err != nil {
			t.Fatalf("expected priority %d to be valid, got %v", priority, err)
		}
	}
}

func TestValidateEBPFPriorityRejectsOutOfRangeValues(t *testing.T) {
	for _, priority := range []int{-1, 256, 1000} {
		if err := validateEBPFPriority(priority); err == nil {
			t.Fatalf("expected priority %d to fail", priority)
		}
	}
}

func TestParseSliceIDPortTrimsAndValidatesUDPPortRange(t *testing.T) {
	port, err := parseSliceIDPort(" 8805 ")
	if err != nil {
		t.Fatalf("expected valid trimmed port, got %v", err)
	}
	if port != 8805 {
		t.Fatalf("expected parsed port 8805, got %d", port)
	}
}

func TestParseSliceIDPortRejectsInvalidValues(t *testing.T) {
	for _, sliceID := range []string{"", " ", "abc", "0", "65536", "-1"} {
		if _, err := parseSliceIDPort(sliceID); err == nil {
			t.Fatalf("expected invalid slice ID %q to fail", sliceID)
		}
	}
}

func TestNewEBPFPolicyProgrammerRejectsEmptyMapPath(t *testing.T) {
	if _, err := NewEBPFPolicyProgrammer("   "); err == nil {
		t.Fatal("expected empty eBPF map path to fail")
	}
}
