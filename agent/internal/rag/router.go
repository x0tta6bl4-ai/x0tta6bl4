package rag

import (
	"context"
	"fmt"
	"log"
)

// SearchResult represents a single hit from a shard.
type SearchResult struct {
	ChunkID  string
	Content  string
	Score    float32
	NodeID   string
	TenantID string
}

// MeshProvider defines the network capabilities required for RAG.
type MeshProvider interface {
	BroadcastQuery(ctx context.Context, tenantID string, query []float32) ([]SearchResult, error)
	GetPeers() []string
}

// ShardRouter manages federated search over the mesh.
type ShardRouter struct {
	LocalNodeID string
	Transport   MeshProvider
}

// NewShardRouter creates a router instance with a transport provider.
func NewShardRouter(nodeID string, transport MeshProvider) *ShardRouter {
	return &ShardRouter{
		LocalNodeID: nodeID,
		Transport:   transport,
	}
}

// Query broadcasts a search request to available shards using the mesh transport.
func (r *ShardRouter) Query(ctx context.Context, queryVector []float32, tenantID string) ([]SearchResult, error) {
	log.Printf("[RAG][ROUTER] federated query for tenant %s initiating from %s", tenantID, r.LocalNodeID)
	
	if r.Transport == nil {
		return nil, fmt.Errorf("no mesh transport available")
	}

	return r.Transport.BroadcastQuery(ctx, tenantID, queryVector)
}

// Distribute assigns a chunk to its primary home based on consistent hashing.
func (r *ShardRouter) Distribute(chunk Chunk) (string, error) {
	// Mock: returns the target node ID
	targetNode := fmt.Sprintf("node-%s", chunk.TenantID)
	return targetNode, nil
}
