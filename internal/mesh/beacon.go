package mesh

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
)

const BeaconProtocolID = "/x0tta6bl4/beacon/1.0.0"

type BeaconMetrics struct {
	PeerID    string  `json:"peer_id"`
	RSSI      float64 `json:"rssi"`
	SNR       float64 `json:"snr"`
	Timestamp int64   `json:"timestamp"`
}

type BeaconService struct {
	host     host.Host
	interval time.Duration
	metrics  map[peer.ID]*BeaconMetrics
	mu       sync.RWMutex
}

func NewBeaconService(h host.Host, interval time.Duration) *BeaconService {
	bs := &BeaconService{
		host:     h,
		interval: interval,
		metrics:  make(map[peer.ID]*BeaconMetrics),
	}
	h.SetStreamHandler(BeaconProtocolID, bs.handleBeaconStream)
	return bs
}

func (bs *BeaconService) Start(ctx context.Context) {
	ticker := time.NewTicker(bs.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			bs.broadcastBeacons(ctx)
		}
	}
}

func (bs *BeaconService) broadcastBeacons(ctx context.Context) {
	for _, p := range bs.host.Network().Peers() {
		go bs.sendBeacon(ctx, p)
	}
}

func (bs *BeaconService) sendBeacon(ctx context.Context, p peer.ID) {
	s, err := bs.host.NewStream(ctx, p, BeaconProtocolID)
	if err != nil {
		return // Peer unreachable
	}
	defer s.Close()

	// Simulate hardware RSSI/SNR polling
	metric := BeaconMetrics{
		PeerID:    bs.host.ID().String(),
		RSSI:      -55.0,
		SNR:       25.0,
		Timestamp: time.Now().Unix(),
	}

	encoder := json.NewEncoder(s)
	if err := encoder.Encode(metric); err != nil {
		log.Printf("Failed to encode beacon: %v", err)
	}
}

func (bs *BeaconService) handleBeaconStream(s network.Stream) {
	defer s.Close()
	var metric BeaconMetrics
	if err := json.NewDecoder(s).Decode(&metric); err != nil {
		log.Printf("Failed to decode beacon: %v", err)
		return
	}

	bs.mu.Lock()
	bs.metrics[s.Conn().RemotePeer()] = &metric
	bs.mu.Unlock()
}

func (bs *BeaconService) GetMetrics() map[peer.ID]*BeaconMetrics {
	bs.mu.RLock()
	defer bs.mu.RUnlock()

	copyMetrics := make(map[peer.ID]*BeaconMetrics)
	for k, v := range bs.metrics {
		copyMetrics[k] = v
	}
	return copyMetrics
}
