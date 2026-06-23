// Package ebpf provides eBPF map integration for PQC session keys.
// It writes session keys from the Go PQC tunnel manager into eBPF maps
// for kernel-space fast-path lookup.
package ebpf

import (
	"encoding/binary"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/cilium/ebpf"
)

const (
	maxPeerIDLen = 64
	keySize      = 32 // AES-256 session key
)

// PQCKeyEntry is the value stored in the eBPF pqc_keys map.
// Must match the C struct pqc_value_t exactly.
type PQCKeyEntry struct {
	SessionKey    [keySize]byte
	LastUpdatedNS uint64
	Flags         uint32
	HitCount      uint32
}

// PQCKeyMap provides read/write access to the eBPF PQC session key map.
type PQCKeyMap struct {
	mu     sync.RWMutex
	mapObj *ebpf.Map
	logger *slog.Logger
}

// NewPQCKeyMap creates a new PQC key map wrapper.
// The map must already be loaded (e.g., via bpf2go or bpftool).
func NewPQCKeyMap(m *ebpf.Map) *PQCKeyMap {
	return &PQCKeyMap{
		mapObj: m,
		logger: slog.Default().With("component", "ebpf-pqc-map"),
	}
}

// NewPQCKeyMapFromPath loads a pinned eBPF map from bpffs.
func NewPQCKeyMapFromPath(path string) (*PQCKeyMap, error) {
	m, err := ebpf.LoadPinnedMap(path, nil)
	if err != nil {
		return nil, fmt.Errorf("load pinned PQC key map: %w", err)
	}
	return NewPQCKeyMap(m), nil
}

// StoreSessionKey writes a session key to the eBPF map for a given peer.
func (m *PQCKeyMap) StoreSessionKey(peerID string, sessionKey []byte) error {
	if len(sessionKey) != keySize {
		return fmt.Errorf("session key must be %d bytes, got %d", keySize, len(sessionKey))
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	key, err := peerIDToKey(peerID)
	if err != nil {
		return err
	}

	var value PQCKeyEntry
	copy(value.SessionKey[:], sessionKey)
	value.LastUpdatedNS = uint64(time.Now().UnixNano())
	value.Flags = 1 // active

	if err := m.mapObj.Put(key, value); err != nil {
		return fmt.Errorf("store session key for %s: %w", peerID, err)
	}

	m.logger.Debug("session key stored in eBPF", "peer", peerID)
	return nil
}

// LookupSessionKey reads a session key from the eBPF map.
func (m *PQCKeyMap) LookupSessionKey(peerID string) ([]byte, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	key, err := peerIDToKey(peerID)
	if err != nil {
		return nil, err
	}

	var value PQCKeyEntry
	if err := m.mapObj.Lookup(key, &value); err != nil {
		return nil, fmt.Errorf("lookup session key for %s: %w", peerID, err)
	}

	result := make([]byte, keySize)
	copy(result, value.SessionKey[:])
	return result, nil
}

// RemoveSessionKey deletes a session key from the eBPF map.
func (m *PQCKeyMap) RemoveSessionKey(peerID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	key, err := peerIDToKey(peerID)
	if err != nil {
		return err
	}

	if err := m.mapObj.Delete(key); err != nil {
		return fmt.Errorf("delete session key for %s: %w", peerID, err)
	}

	m.logger.Debug("session key removed from eBPF", "peer", peerID)
	return nil
}

// GetStats reads packet statistics from the pkt_stats eBPF map.
func (m *PQCKeyMap) GetStats() (total, passed, dropped, keyHits uint64, err error) {
	statsMap, err := ebpf.NewMap(&ebpf.MapSpec{
		Type:       ebpf.PerCPUArray,
		KeySize:    4,
		ValueSize:  8,
		MaxEntries: 4,
	})
	if err != nil {
		// If we can't access stats, return zeros
		return 0, 0, 0, 0, nil
	}
	defer statsMap.Close()

	for i := uint32(0); i < 4; i++ {
		var vals []uint64
		if err := statsMap.Lookup(i, &vals); err != nil {
			continue
		}
		var sum uint64
		for _, v := range vals {
			sum += v
		}
		switch i {
		case 0:
			total = sum
		case 1:
			passed = sum
		case 2:
			dropped = sum
		case 3:
			keyHits = sum
		}
	}
	return
}

// SyncFromTunnelManager copies all active sessions from a SessionProvider
// into the eBPF map. Call this periodically or after handshake completion.
func (m *PQCKeyMap) SyncFromTunnelManager(sessions []PeerSession) error {
	for _, s := range sessions {
		if len(s.SessionKey) == keySize {
			if err := m.StoreSessionKey(s.PeerID, s.SessionKey); err != nil {
				m.logger.Warn("failed to sync session to eBPF", "peer", s.PeerID, "error", err)
			}
		}
	}
	return nil
}

// PeerSession represents a PQC session for eBPF sync.
type PeerSession struct {
	PeerID     string
	SessionKey []byte
}

// peerIDToKey converts a peer ID string to an eBPF map key.
func peerIDToKey(peerID string) ([maxPeerIDLen]byte, error) {
	var key [maxPeerIDLen]byte
	peerBytes := []byte(peerID)
	if len(peerBytes) > maxPeerIDLen {
		return key, fmt.Errorf("peer ID too long: %d > %d", len(peerBytes), maxPeerIDLen)
	}
	copy(key[:], peerBytes)
	return key, nil
}

// IPToKey converts a 4-byte IP address to an eBPF map key.
// This is used when the XDP program indexes by IP, not by peer ID.
func IPToKey(ip []byte) [maxPeerIDLen]byte {
	var key [maxPeerIDLen]byte
	copy(key[:4], ip)
	return key
}

// KeyToUint32 extracts a uint32 IP from the first 4 bytes of a key.
func KeyToUint32(key [maxPeerIDLen]byte) uint32 {
	return binary.BigEndian.Uint32(key[:4])
}
