package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type EncryptedPayload struct {
	Ciphertext []byte `json:"ciphertext"`
	Data       []byte `json:"data"`
	PeerID     string `json:"peer_id"`
}

func updateHandler(w http.ResponseWriter, r *http.Request) {
	var p EncryptedPayload
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, "Bad request", 400)
		return
	}

	log.Printf("[PQC-AGGREGATOR] Received PQC package from %s", p.PeerID)
	log.Printf("[PQC-AGGREGATOR] ML-KEM Token: %s", string(p.Ciphertext))

	w.WriteHeader(202)
	json.NewEncoder(w).Encode(map[string]string{"status": "pqc_aggregated"})
}

func main() {
	http.HandleFunc("/api/v1/update", updateHandler)
	log.Println("🚀 PQC Aggregator starting on :8010...")
	http.ListenAndServe(":8010", nil)
}
