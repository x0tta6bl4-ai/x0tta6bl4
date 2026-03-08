package test

import (
	"context"
	"strings"
	"testing"
	"time"

	"x0tta6bl4/edge/5g"
	"x0tta6bl4/ml/federated"
)

func TestFedAvgIntegration(t *testing.T) {
	cfg := federated.FederationConfig{
		RequiredPeers:  1,
		GradientLength: 10,
		Sigma:          0.1,
	}

	// Test with NoPrivacyEngine
	server := federated.NewFedAvgServer(cfg, make([]float32, 10), &federated.NoPrivacyEngine{})
	server.RegisterPeer("p1")

	err := server.ReceiveUpdate(context.Background(), "p1", make([]float32, 10))
	if err != nil {
		t.Fatalf("Aggregation failed: %v", err)
	}
}

func TestRealOpen5GSSignaling(t *testing.T) {
	cfg := edge5g.UPFConfig{
		AMFEndpoint: " 127.0.0.1:38412 ", // Стандартный порт NGAP
		UPFEndpoint: " 127.0.0.1:8805 ",  // Стандартный порт PFCP
		Timeout:     100 * time.Millisecond,
	}

	provider := edge5g.NewRealOpen5GSUPF(cfg)

	// Ожидаем transport failure, так как Open5GS не запущен.
	_, err := provider.EstablishSession(" UE-TEST ", " slice-premium ")
	if err == nil {
		t.Error("Expected error for unreachable AMF, but got success")
		return
	}
	if !strings.Contains(err.Error(), "transport failure") {
		t.Fatalf("expected transport failure semantics, got: %v", err)
	}
	t.Logf("Correctly detected unreachable core: %v", err)
}

func TestEBPFPolicyUpdate(t *testing.T) {
	enforcer := &edge5g.RealEBPFQoSEnforcer{}
	err := enforcer.EnforceSlicePolicy("slice-gold", 200)
	if err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Errorf("expected dry-run NOT VERIFIED error for unwired programmer, got: %v", err)
	}
}
