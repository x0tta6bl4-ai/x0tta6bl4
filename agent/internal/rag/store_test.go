package rag

import (
	"context"
	"os"
	"testing"
)

func TestVectorStore_SaveAndSearch(t *testing.T) {
	dbPath := "test_rag.db"
	defer os.Remove(dbPath)

	store, err := NewVectorStore(dbPath)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer store.Close()

	ctx := context.Background()
	chunk := Chunk{
		ID:          "test-1",
		Content:     "x0tta6bl4 is a self-healing mesh.",
		TenantID:    "tenant-alpha",
		SecurityTag: "spiffe://x0tta6bl4.mesh/agent/1",
		Embedding:   []float32{1.0, 0.0, 0.0},
	}

	if err := store.Save(ctx, chunk); err != nil {
		t.Fatalf("failed to save chunk: %v", err)
	}

	// Search with identical vector (should give score 1.0)
	results, err := store.SimilaritySearch(ctx, "tenant-alpha", []float32{1.0, 0.0, 0.0}, 1)
	if err != nil {
		t.Fatalf("search failed: %v", err)
	}

	if len(results) == 0 {
		t.Fatal("expected at least one result")
	}

	if results[0].Score < 0.99 {
		t.Errorf("expected high score for identical vector, got %f", results[0].Score)
	}

	if results[0].Content != chunk.Content {
		t.Errorf("content mismatch: got %s, want %s", results[0].Content, chunk.Content)
	}
}
