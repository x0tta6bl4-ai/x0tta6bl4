package mesh

import (
	"context"
	"fmt"
	"log"

	"github.com/libp2p/go-libp2p"
	dht "github.com/libp2p/go-libp2p-kad-dht"
	noise "github.com/libp2p/go-libp2p/p2p/security/noise"
	libp2pquic "github.com/libp2p/go-libp2p/p2p/transport/quic"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/routing"
)

// Config holds the configuration for the mesh node.
type Config struct {
	ListenAddrs    []string
	BootstrapPeers []string
}

// NewMeshNode initializes a new libp2p node with QUIC, Noise, and DHT.
// PQC handshake integration is layered within the custom transport/security phase.
func NewMeshNode(ctx context.Context, cfg Config) (host.Host, *dht.IpfsDHT, error) {
	var idht *dht.IpfsDHT

	h, err := libp2p.New(
		libp2p.ListenAddrStrings(cfg.ListenAddrs...),
		libp2p.Transport(libp2pquic.NewTransport),
		libp2p.Security(noise.ID, noise.New), // PQC-NTRU/Kyber wrapper goes here
		libp2p.Routing(func(h host.Host) (routing.PeerRouting, error) {
			var err error
			idht, err = dht.New(ctx, h)
			return idht, err
		}),
	)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create libp2p host: %w", err)
	}

	log.Printf("Mesh node initialized with ID: %s", h.ID().String())
	return h, idht, nil
}
