package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"
)

func normalizeBindAddress(addr string, fallback string) string {
	trimmed := strings.TrimSpace(addr)
	if trimmed == "" {
		return fallback
	}
	if strings.HasPrefix(trimmed, ":") {
		return trimmed
	}
	if strings.Contains(trimmed, ":") {
		return trimmed
	}
	return ":" + trimmed
}

func main() {
	leaderElect := flag.Bool("leader-elect", true, "placeholder flag for compatibility")
	leaderElectionNamespace := flag.String("leader-elect-namespace", "", "placeholder flag for compatibility")
	metricsBindAddress := flag.String("metrics-bind-address", ":9090", "metrics bind address")
	healthProbeBindAddress := flag.String("health-probe-bind-address", ":8081", "health probe bind address")
	flag.Parse()

	metricsAddr := normalizeBindAddress(*metricsBindAddress, ":9090")
	probeAddr := normalizeBindAddress(*healthProbeBindAddress, ":8081")

	log.Printf(
		"starting mesh-operator fallback manager (leaderElect=%v, leaderElectionNamespace=%q, metrics=%q, health=%q)",
		*leaderElect,
		*leaderElectionNamespace,
		metricsAddr,
		probeAddr,
	)

	metricsMux := http.NewServeMux()
	metricsMux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = fmt.Fprint(w, "# HELP mesh_operator_fallback_up Fallback manager availability\n")
		_, _ = fmt.Fprint(w, "# TYPE mesh_operator_fallback_up gauge\n")
		_, _ = fmt.Fprint(w, "mesh_operator_fallback_up 1\n")
	})

	probeMux := http.NewServeMux()
	probeMux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = fmt.Fprintln(w, "ok")
	})
	probeMux.HandleFunc("/readyz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = fmt.Fprintln(w, "ok")
	})

	metricsServer := &http.Server{
		Addr:              metricsAddr,
		Handler:           metricsMux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	probeServer := &http.Server{
		Addr:              probeAddr,
		Handler:           probeMux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	errCh := make(chan error, 2)
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		log.Printf("metrics server listening on %s", metricsAddr)
		if err := metricsServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- fmt.Errorf("metrics server: %w", err)
		}
	}()

	go func() {
		defer wg.Done()
		log.Printf("probe server listening on %s", probeAddr)
		if err := probeServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- fmt.Errorf("probe server: %w", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigCh:
		log.Printf("shutdown signal received: %s", sig)
	case err := <-errCh:
		log.Printf("server error: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	_ = metricsServer.Shutdown(ctx)
	_ = probeServer.Shutdown(ctx)
	wg.Wait()
	log.Printf("fallback manager stopped")
}
