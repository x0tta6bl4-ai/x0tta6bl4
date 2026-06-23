package ebpf

import (
	"bytes"
	"testing"
)

func TestPeerIDToKey(t *testing.T) {
	tests := []struct {
		name    string
		peerID  string
		wantErr bool
	}{
		{"normal", "node-123", false},
		{"empty", "", false},
		{"max_length", "a" + string(make([]byte, 63)), false},
		{"too_long", string(make([]byte, 65)), true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key, err := peerIDToKey(tt.peerID)
			if (err != nil) != tt.wantErr {
				t.Errorf("peerIDToKey() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr {
				// Verify key contains the peer ID
				if len(key) != maxPeerIDLen {
					t.Errorf("key length = %d, want %d", len(key), maxPeerIDLen)
				}
				// First bytes should match peer ID
				peerBytes := []byte(tt.peerID)
				if !bytes.HasPrefix(key[:], peerBytes) {
					t.Errorf("key prefix mismatch")
				}
			}
		})
	}
}

func TestIPToKey(t *testing.T) {
	ip := []byte{192, 168, 1, 100}
	key := IPToKey(ip)

	if key[0] != 192 || key[1] != 168 || key[2] != 1 || key[3] != 100 {
		t.Errorf("IPToKey() = %v, want [192,168,1,100,...]", key[:4])
	}
}

func TestKeyToUint32(t *testing.T) {
	key := IPToKey([]byte{10, 0, 0, 1})
	val := KeyToUint32(key)

	expected := uint32(10<<24 | 0<<16 | 0<<8 | 1)
	if val != expected {
		t.Errorf("KeyToUint32() = %d, want %d", val, expected)
	}
}

func TestPQCKeyEntrySize(t *testing.T) {
	// Verify PQCKeyEntry matches expected layout
	var entry PQCKeyEntry
	if len(entry.SessionKey) != 32 {
		t.Errorf("SessionKey size = %d, want 32", len(entry.SessionKey))
	}
}
