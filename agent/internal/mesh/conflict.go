package mesh

import (
	"fmt"
	"log/slog"
	"net"
	"sync"
	"time"
)

// ConflictResolver handles duplicate peer detection and resolution.
type ConflictResolver struct {
	mu     sync.RWMutex
	logger *slog.Logger

	// peerSources tracks which discovery source reported each peer.
	// peerID → source ("mdns", "udp", "inject")
	peerSources map[string]string

	// peerHistory tracks address history for each peer.
	// peerID → list of {addr, timestamp, source}
	peerHistory map[string][]PeerRecord
}

// PeerRecord is a historical record of a peer's address.
type PeerRecord struct {
	Addr      *net.UDPAddr
	Timestamp time.Time
	Source    string
}

// NewConflictResolver creates a new conflict resolver.
func NewConflictResolver() *ConflictResolver {
	return &ConflictResolver{
		peerSources: make(map[string]string),
		peerHistory: make(map[string][]PeerRecord),
		logger:      slog.Default().With("component", "conflict-resolver"),
	}
}

// ResolvePeer checks for conflicts and returns the resolved peer info.
// Returns: resolved address, whether this is an update, and any conflict info.
func (cr *ConflictResolver) ResolvePeer(peerID string, newAddr *net.UDPAddr, source string) (resolvedAddr *net.UDPAddr, isUpdate bool, conflict string) {
	cr.mu.Lock()
	defer cr.mu.Unlock()

	existing, exists := cr.peerSources[peerID]

	if !exists {
		// New peer — no conflict
		cr.peerSources[peerID] = source
		cr.peerHistory[peerID] = append(cr.peerHistory[peerID], PeerRecord{
			Addr:      newAddr,
			Timestamp: time.Now(),
			Source:    source,
		})
		return newAddr, false, ""
	}

	// Peer already known — check for address change
	lastRecord := cr.peerHistory[peerID][len(cr.peerHistory[peerID])-1]
	if lastRecord.Addr.IP.Equal(newAddr.IP) && lastRecord.Addr.Port == newAddr.Port {
		// Same address — just update timestamp
		cr.peerHistory[peerID] = append(cr.peerHistory[peerID], PeerRecord{
			Addr:      newAddr,
			Timestamp: time.Now(),
			Source:    source,
		})
		return newAddr, false, ""
	}

	// Address changed — conflict detected
	conflictInfo := fmt.Sprintf("address changed: %s:%d → %s:%d (source: %s, previous: %s)",
		lastRecord.Addr.IP, lastRecord.Addr.Port,
		newAddr.IP, newAddr.Port,
		source, existing)

	cr.logger.Warn("peer address conflict",
		"node_id", peerID,
		"old_addr", lastRecord.Addr,
		"new_addr", newAddr,
		"source", source,
	)

	// Resolution strategy: most recent address wins
	cr.peerSources[peerID] = source
	cr.peerHistory[peerID] = append(cr.peerHistory[peerID], PeerRecord{
		Addr:      newAddr,
		Timestamp: time.Now(),
		Source:    source,
	})

	// Keep history bounded (last 10 records)
	if len(cr.peerHistory[peerID]) > 10 {
		cr.peerHistory[peerID] = cr.peerHistory[peerID][len(cr.peerHistory[peerID])-10:]
	}

	return newAddr, true, conflictInfo
}

// RemovePeer cleans up conflict resolver state for a peer.
func (cr *ConflictResolver) RemovePeer(peerID string) {
	cr.mu.Lock()
	defer cr.mu.Unlock()
	delete(cr.peerSources, peerID)
	delete(cr.peerHistory, peerID)
}

// GetHistory returns the address history for a peer.
func (cr *ConflictResolver) GetHistory(peerID string) []PeerRecord {
	cr.mu.RLock()
	defer cr.mu.RUnlock()
	return cr.peerHistory[peerID]
}

// GetSource returns the discovery source for a peer.
func (cr *ConflictResolver) GetSource(peerID string) string {
	cr.mu.RLock()
	defer cr.mu.RUnlock()
	return cr.peerSources[peerID]
}
