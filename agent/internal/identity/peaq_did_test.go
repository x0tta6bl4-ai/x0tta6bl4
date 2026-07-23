package identity

import (
	"testing"
)

func TestPeaqIdentityAdapter(t *testing.T) {
	nodeID := "node-test-123"
	adapter := NewPeaqIdentityAdapter(nodeID)

	if adapter.NodeID != nodeID {
		t.Errorf("expected NodeID %s, got %s", nodeID, adapter.NodeID)
	}

	expectedPrefix := "did:peaq:0x"
	if len(adapter.DID) < len(expectedPrefix) || adapter.DID[:len(expectedPrefix)] != expectedPrefix {
		t.Errorf("expected DID to start with %s, got %s", expectedPrefix, adapter.DID)
	}

	if len(adapter.Address) != 42 || adapter.Address[:2] != "0x" {
		t.Errorf("expected Address to be EVM hex address, got %s", adapter.Address)
	}
}

func TestPeaqIdentityAdapter_RegisterMachine(t *testing.T) {
	adapter := NewPeaqIdentityAdapter("node-test-123")
	res, err := adapter.RegisterMachine("http://localhost:8545")
	if err != nil {
		t.Fatalf("RegisterMachine failed: %v", err)
	}

	if res["status"] != "SIMULATED" {
		t.Errorf("expected status SIMULATED, got %v", res["status"])
	}

	if res["did"] != adapter.DID {
		t.Errorf("expected did %s, got %v", adapter.DID, res["did"])
	}

	if res["node_id"] != adapter.NodeID {
		t.Errorf("expected node_id %s, got %v", adapter.NodeID, res["node_id"])
	}

	if len(res["tx_hash"].(string)) != 64 {
		t.Errorf("expected 64-character tx_hash hex, got %v", res["tx_hash"])
	}
}

func TestPeaqIdentityAdapter_SignTelemetry(t *testing.T) {
	adapter := NewPeaqIdentityAdapter("node-test-123")
	telemetryData := []byte("some telemetry payload")
	res := adapter.SignTelemetry(telemetryData)

	if res["did"] != adapter.DID {
		t.Errorf("expected did %s, got %v", adapter.DID, res["did"])
	}

	if len(res["signature"].(string)) != 64 {
		t.Errorf("expected signature hex string, got %v", res["signature"])
	}

	if len(res["message_hash"].(string)) != 64 {
		t.Errorf("expected message_hash hex string, got %v", res["message_hash"])
	}
}
