package main

import (
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func serveUDP(addr string, stop <-chan struct{}) {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		log.Printf("udp resolve error on %s: %v", addr, err)
		return
	}
	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		log.Printf("udp listen error on %s: %v", addr, err)
		return
	}
	defer conn.Close()

	buf := make([]byte, 2048)
	for {
		select {
		case <-stop:
			return
		default:
			_ = conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			n, remote, readErr := conn.ReadFromUDP(buf)
			if readErr != nil {
				if ne, ok := readErr.(net.Error); ok && ne.Timeout() {
					continue
				}
				continue
			}
			if n > 0 {
				_, _ = conn.WriteToUDP([]byte("ACK"), remote)
			}
		}
	}
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ready\n"))
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = w.Write([]byte("# HELP mesh_node_fallback_up Fallback mesh node availability\n"))
		_, _ = w.Write([]byte("# TYPE mesh_node_fallback_up gauge\n"))
		_, _ = w.Write([]byte("mesh_node_fallback_up 1\n"))
	})

	server := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	stopUDP := make(chan struct{})
	go serveUDP(":5000", stopUDP)
	go serveUDP(":7777", stopUDP)

	go func() {
		log.Printf("mesh-node fallback manager listening on :8080")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("http server error: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	close(stopUDP)
	_ = server.Close()
}
