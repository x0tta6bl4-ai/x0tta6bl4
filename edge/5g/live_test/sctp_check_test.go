package main

import (
	"errors"
	"net"
	"strings"
	"testing"

	"github.com/ishidawataru/sctp"
)

func TestParseConfigDefaults(t *testing.T) {
	cfg, err := parseConfig(nil)
	if err != nil {
		t.Fatalf("expected default config, got %v", err)
	}
	if cfg.mode != "dial" || cfg.target != "127.0.0.1:38412" {
		t.Fatalf("unexpected defaults: %+v", cfg)
	}
}

func TestParseConfigNormalizesWhitespace(t *testing.T) {
	cfg, err := parseConfig([]string{"-mode", " LISTEN ", "-target", " 127.0.0.1:39000 "})
	if err != nil {
		t.Fatalf("expected normalized config, got %v", err)
	}
	if cfg.mode != "listen" || cfg.target != "127.0.0.1:39000" {
		t.Fatalf("unexpected normalized config: %+v", cfg)
	}
}

func TestParseConfigRejectsInvalidInputs(t *testing.T) {
	if _, err := parseConfig([]string{"-mode", "invalid"}); err == nil || !strings.Contains(err.Error(), "unsupported mode") {
		t.Fatalf("expected invalid mode rejection, got %v", err)
	}
	if _, err := parseConfig([]string{"-target", "   "}); err == nil || !strings.Contains(err.Error(), "target address required") {
		t.Fatalf("expected empty target rejection, got %v", err)
	}
}

func TestRunDialUsesInjectedDependencies(t *testing.T) {
	originalResolve := resolveSCTPAddr
	originalDial := dialSCTP
	defer func() {
		resolveSCTPAddr = originalResolve
		dialSCTP = originalDial
	}()

	var gotResolveNetwork, gotResolveTarget string
	var gotDialNetwork string
	var gotDialAddr *sctp.SCTPAddr

	resolveSCTPAddr = func(network, address string) (*sctp.SCTPAddr, error) {
		gotResolveNetwork = network
		gotResolveTarget = address
		return &sctp.SCTPAddr{IPAddrs: []net.IPAddr{{IP: net.ParseIP("127.0.0.1")}}, Port: 38412}, nil
	}
	dialSCTP = func(network string, laddr, raddr *sctp.SCTPAddr) (*sctp.SCTPConn, error) {
		gotDialNetwork = network
		gotDialAddr = raddr
		return nil, errors.New("dial blocked in test")
	}

	err := run(runConfig{mode: "dial", target: "127.0.0.1:38412"})
	if err == nil || !strings.Contains(err.Error(), "dial failed") {
		t.Fatalf("expected dial failure semantics, got %v", err)
	}
	if gotResolveNetwork != "sctp" || gotResolveTarget != "127.0.0.1:38412" {
		t.Fatalf("unexpected resolve call: network=%q target=%q", gotResolveNetwork, gotResolveTarget)
	}
	if gotDialNetwork != "sctp" || gotDialAddr == nil || gotDialAddr.Port != 38412 {
		t.Fatalf("unexpected dial call: network=%q addr=%+v", gotDialNetwork, gotDialAddr)
	}
}
