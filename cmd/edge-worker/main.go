package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
)

type EncryptedPayload struct {
	Ciphertext []byte `json:"ciphertext"`
	Data       []byte `json:"data"`
	PeerID     string `json:"peer_id"`
}

func main() {
	serverURL := flag.String("server", "http://localhost:8010", "Control plane URL")
	flag.Parse()

	log.Println("🚀 x0tta6bl4 Go Edge Worker [PQC-EMULATED] - Starting...")

	// 1. Пакет имитации PQC
	payload := EncryptedPayload{
		Ciphertext: []byte("pqc-kem-768-encapsulation"),
		Data:       []byte("encrypted-gradients-weights-v3"),
		PeerID:     "local-pc-edge-pqc",
	}

	data, _ := json.Marshal(payload)
	updateURL := fmt.Sprintf("%s/api/v1/update", *serverURL)
	
	log.Printf("🔒 PQC ML-KEM container created. Sending to Aggregator...")
	
	resp, err := http.Post(updateURL, "application/json", bytes.NewBuffer(data))
	if err != nil {
		log.Fatalf("❌ Send failed: %v", err)
	}
	defer resp.Body.Close()

	var res map[string]string
	json.NewDecoder(resp.Body).Decode(&res)
	log.Printf("✅ Server Response: %v (Status: %d)", res, resp.StatusCode)
}
