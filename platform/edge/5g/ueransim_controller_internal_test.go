package edge5g

import (
	"os/exec"
	"strings"
	"testing"
	"time"
)

func TestMeasureLatencyRejectsEmptyInputs(t *testing.T) {
	controller := &UERANSIMController{}

	if _, err := controller.MeasureLatency("", "8.8.8.8"); err == nil || !strings.Contains(err.Error(), "interface name required") {
		t.Fatalf("expected missing interface rejection, got %v", err)
	}
	if _, err := controller.MeasureLatency("uesimtun0", ""); err == nil || !strings.Contains(err.Error(), "target IP required") {
		t.Fatalf("expected missing target rejection, got %v", err)
	}
}

func TestMeasureLatencyTrimsInputsBeforeInvokingPing(t *testing.T) {
	originalExecCommand := execCommand
	defer func() { execCommand = originalExecCommand }()

	var capturedName string
	var capturedArgs []string
	execCommand = func(name string, args ...string) *exec.Cmd {
		capturedName = name
		capturedArgs = append([]string(nil), args...)
		return exec.Command("bash", "-lc", "printf '64 bytes from 8.8.8.8: icmp_seq=1 ttl=64 time=12.34 ms\\n'")
	}

	controller := &UERANSIMController{}
	latency, err := controller.MeasureLatency("  uesimtun0  ", " 8.8.8.8 ")
	if err != nil {
		t.Fatalf("expected mocked ping success, got %v", err)
	}
	if capturedName != "ping" {
		t.Fatalf("expected ping command, got %s", capturedName)
	}
	expectedArgs := []string{"-I", "uesimtun0", "-c", "1", "-W", "1", "8.8.8.8"}
	if len(capturedArgs) != len(expectedArgs) {
		t.Fatalf("unexpected arg count: got %v want %v", capturedArgs, expectedArgs)
	}
	for i, arg := range expectedArgs {
		if capturedArgs[i] != arg {
			t.Fatalf("unexpected ping args: got %v want %v", capturedArgs, expectedArgs)
		}
	}
	if latency != 12*time.Millisecond+340*time.Microsecond {
		t.Fatalf("unexpected parsed latency: got %v", latency)
	}
}

func TestMeasureLatencyRejectsUnparseablePingOutput(t *testing.T) {
	originalExecCommand := execCommand
	defer func() { execCommand = originalExecCommand }()

	execCommand = func(name string, args ...string) *exec.Cmd {
		return exec.Command("bash", "-lc", "printf 'ping output without latency\\n'")
	}

	controller := &UERANSIMController{}
	if _, err := controller.MeasureLatency("uesimtun0", "8.8.8.8"); err == nil || !strings.Contains(err.Error(), "could not parse latency") {
		t.Fatalf("expected parse failure, got %v", err)
	}
}
