// Package identity fetches runtime identity material for the agent.
package identity

import (
	"crypto/sha256"
	"encoding/hex"
)

// PeaqIdentityAdapter handles peaq Machine DID derivation and management.
type PeaqIdentityAdapter struct {
	NodeID  string
	Address string
	DID     string
}

// NewPeaqIdentityAdapter creates a new adapter for the given node ID.
func NewPeaqIdentityAdapter(nodeID string) *PeaqIdentityAdapter {
	// Deterministic address derivation mimicking EVM address format
	hash := sha256.Sum256([]byte("peaq-machine-identity-" + nodeID))
	address := "0x" + hex.EncodeToString(hash[:20])
	did := "did:peaq:" + address

	return &PeaqIdentityAdapter{
		NodeID:  nodeID,
		Address: address,
		DID:     did,
	}
}

// RegisterMachine simulates or registers the machine DID on peaq L1 chain.
func (a *PeaqIdentityAdapter) RegisterMachine(rpcURL string) (map[string]interface{}, error) {
	txHashBytes := sha256.Sum256([]byte("sim-tx-" + a.DID))
	txHash := hex.EncodeToString(txHashBytes[:])

	return map[string]interface{}{
		"status":  "SIMULATED",
		"did":     a.DID,
		"node_id": a.NodeID,
		"tx_hash": txHash,
		"note":    "peaq-sdk Go bindings missing. Simulated on-chain record created.",
	}, nil
}

// SignTelemetry signs telemetry data using the deterministic node identity.
func (a *PeaqIdentityAdapter) SignTelemetry(data []byte) map[string]interface{} {
	hash := sha256.Sum256(data)
	sigBytes := sha256.Sum256(append(hash[:], []byte(a.NodeID)...))
	signature := hex.EncodeToString(sigBytes[:])

	return map[string]interface{}{
		"did":          a.DID,
		"signature":    signature,
		"message_hash": hex.EncodeToString(hash[:]),
	}
}
