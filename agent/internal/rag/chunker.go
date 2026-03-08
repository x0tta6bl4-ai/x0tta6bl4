package rag

import (
	"fmt"
	"regexp"
	"strings"
)

var sentenceRegex = regexp.MustCompile(`[^.!?]+[.!?]+`)

// Chunk represents a semantic slice of data with security attributes.
type Chunk struct {
	ID          string
	Content     string
	TenantID    string
	SecurityTag string // SPIFFE ID or role-based tag
	Metadata    map[string]string
	Embedding   []float32
}

// Chunker handles semantic text slicing for RAG.
type Chunker struct {
	WindowSize int // max words per chunk
	Overlap    int
}

// NewChunker creates a chunker with default 512/50 tokens.
func NewChunker() *Chunker {
	return &Chunker{
		WindowSize: 512,
		Overlap:    50,
	}
}

// Process slices text into semantic chunks using sentence boundaries.
func (c *Chunker) Process(text string, tenantID string, securityTag string) ([]Chunk, error) {
	if text == "" {
		return nil, fmt.Errorf("empty text")
	}

	// Step 1: Extract sentences
	sentences := sentenceRegex.FindAllString(text, -1)
	if len(sentences) == 0 {
		// Fallback to simple split if regex fails
		sentences = []string{text}
	}

	var chunks []Chunk
	var currentBatch []string
	currentWordCount := 0

	for _, sentence := range sentences {
		words := strings.Fields(sentence)
		
		// If adding this sentence exceeds window size and batch is not empty, flush it
		if currentWordCount+len(words) > c.WindowSize && len(currentBatch) > 0 {
			content := strings.Join(currentBatch, " ")
			chunks = append(chunks, Chunk{
				ID:          fmt.Sprintf("chk-%s-%d", tenantID, len(chunks)),
				Content:     content,
				TenantID:    tenantID,
				SecurityTag: securityTag,
				Metadata:    make(map[string]string),
			})
			
			// Simple overlap: keep last few words
			overlapStart := len(currentBatch) - c.Overlap
			if overlapStart < 0 {
				overlapStart = 0
			}
			currentBatch = currentBatch[overlapStart:]
			currentWordCount = len(strings.Fields(strings.Join(currentBatch, " ")))
		}

		currentBatch = append(currentBatch, sentence)
		currentWordCount += len(words)
	}

	// Final flush
	if len(currentBatch) > 0 {
		chunks = append(chunks, Chunk{
			ID:          fmt.Sprintf("chk-%s-%d", tenantID, len(chunks)),
			Content:     strings.Join(currentBatch, " "),
			TenantID:    tenantID,
			SecurityTag: securityTag,
			Metadata:    make(map[string]string),
		})
	}

	return chunks, nil
}
