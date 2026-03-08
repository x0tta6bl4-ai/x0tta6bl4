package rag

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"math"

	_ "github.com/mattn/go-sqlite3"
)

// VectorStore manages local RAG shards using SQLite.
type VectorStore struct {
	db *sql.DB
}

// NewVectorStore initializes a new local shard store.
func NewVectorStore(dbPath string) (*VectorStore, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Create table for chunks
	schema := `
	CREATE TABLE IF NOT EXISTS rag_chunks (
		id TEXT PRIMARY KEY,
		tenant_id TEXT,
		security_tag TEXT,
		content TEXT,
		metadata TEXT,
		embedding BLOB
	);
	CREATE INDEX IF NOT EXISTS idx_rag_tenant ON rag_chunks(tenant_id);
	`
	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	return &VectorStore{db: db}, nil
}

// Save stores a chunk in the local shard.
func (s *VectorStore) Save(ctx context.Context, chunk Chunk) error {
	metadataJSON, _ := json.Marshal(chunk.Metadata)
	embeddingJSON, _ := json.Marshal(chunk.Embedding)

	query := `INSERT OR REPLACE INTO rag_chunks (id, tenant_id, security_tag, content, metadata, embedding) VALUES (?, ?, ?, ?, ?, ?)`
	_, err := s.db.ExecContext(ctx, query, chunk.ID, chunk.TenantID, chunk.SecurityTag, chunk.Content, string(metadataJSON), embeddingJSON)
	return err
}

// SimilaritySearch performs local ANN search via cosine similarity.
func (s *VectorStore) SimilaritySearch(ctx context.Context, tenantID string, queryVector []float32, topK int) ([]SearchResult, error) {
	rows, err := s.db.QueryContext(ctx, "SELECT id, content, tenant_id, embedding FROM rag_chunks WHERE tenant_id = ?", tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var id, content, tid string
		var embeddingBLOB []byte
		if err := rows.Scan(&id, &content, &tid, &embeddingBLOB); err != nil {
			continue
		}

		var chunkVector []float32
		if err := json.Unmarshal(embeddingBLOB, &chunkVector); err != nil {
			continue
		}

		score := cosineSimilarity(queryVector, chunkVector)
		results = append(results, SearchResult{
			ChunkID:  id,
			Content:  content,
			Score:    score,
			TenantID: tid,
			NodeID:   "local",
		})
	}

	// Sort and limit logic omitted for brevity in scaffold, returning all local hits
	return results, nil
}

func cosineSimilarity(a, b []float32) float32 {
	if len(a) != len(b) {
		return 0
	}
	var dotProduct, normA, normB float64
	for i := range a {
		dotProduct += float64(a[i] * b[i])
		normA += float64(a[i] * a[i])
		normB += float64(b[i] * b[i])
	}
	if normA == 0 || normB == 0 {
		return 0
	}
	return float32(dotProduct / (math.Sqrt(normA) * math.Sqrt(normB)))
}

func (s *VectorStore) Close() error {
	return s.db.Close()
}
