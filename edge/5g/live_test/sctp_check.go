package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/ishidawataru/sctp"
)

type runConfig struct {
	mode   string
	target string
}

var (
	resolveSCTPAddr = sctp.ResolveSCTPAddr
	listenSCTP      = sctp.ListenSCTP
	dialSCTP        = sctp.DialSCTP
)

func parseConfig(args []string) (runConfig, error) {
	fs := flag.NewFlagSet("sctp_check", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)

	mode := fs.String("mode", "dial", "mode: dial or listen")
	target := fs.String("target", "127.0.0.1:38412", "SCTP target address")

	if err := fs.Parse(args); err != nil {
		return runConfig{}, err
	}

	cfg := runConfig{
		mode:   strings.ToLower(strings.TrimSpace(*mode)),
		target: strings.TrimSpace(*target),
	}
	if cfg.mode == "" {
		cfg.mode = "dial"
	}
	if cfg.target == "" {
		return runConfig{}, fmt.Errorf("target address required")
	}
	switch cfg.mode {
	case "dial", "listen":
	default:
		return runConfig{}, fmt.Errorf("unsupported mode %q", cfg.mode)
	}
	return cfg, nil
}

func run(cfg runConfig) error {
	addr, err := resolveSCTPAddr("sctp", cfg.target)
	if err != nil {
		return fmt.Errorf("failed to resolve addr: %w", err)
	}

	switch cfg.mode {
	case "listen":
		ln, err := listenSCTP("sctp", addr)
		if err != nil {
			return fmt.Errorf("failed to listen: %w", err)
		}
		defer ln.Close()

		log.Printf("[SERVER] SCTP Listener started on %s", addr)
		conn, err := ln.Accept()
		if err != nil {
			return fmt.Errorf("accept error: %w", err)
		}
		defer conn.Close()

		log.Printf("[SERVER] Accepted connection from %s", conn.RemoteAddr())
		return nil

	case "dial":
		log.Printf("[CLIENT] Dialing SCTP %s...", addr)
		conn, err := dialSCTP("sctp", nil, addr)
		if err != nil {
			return fmt.Errorf("dial failed: %w", err)
		}
		defer conn.Close()

		log.Printf("[CLIENT] Successfully connected to %s", addr)
		return nil
	}

	return fmt.Errorf("unsupported mode %q", cfg.mode)
}

func main() {
	cfg, err := parseConfig(os.Args[1:])
	if err != nil {
		log.Fatal(err)
	}
	if err := run(cfg); err != nil {
		log.Fatal(err)
	}
}
