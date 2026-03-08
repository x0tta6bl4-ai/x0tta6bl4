package main

import (
	"errors"
	"net"
	"strings"
	"testing"
	"time"

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

func TestRunPropagatesResolveFailure(t *testing.T) {
	originalResolve := resolveSCTPAddr
	defer func() { resolveSCTPAddr = originalResolve }()

	resolveSCTPAddr = func(network, address string) (*sctp.SCTPAddr, error) {
		return nil, errors.New("resolve blocked in test")
	}

	err := run(runConfig{mode: "dial", target: "127.0.0.1:38412"})
	if err == nil || !strings.Contains(err.Error(), "failed to resolve addr") {
		t.Fatalf("expected resolve failure semantics, got %v", err)
	}
}

func TestRunListenUsesInjectedDependencies(t *testing.T) {
	originalResolve := resolveSCTPAddr
	originalListen := listenSCTP
	defer func() {
		resolveSCTPAddr = originalResolve
		listenSCTP = originalListen
	}()

	var gotListenNetwork string
	var gotListenAddr *sctp.SCTPAddr
	resolveSCTPAddr = func(network, address string) (*sctp.SCTPAddr, error) {
		return &sctp.SCTPAddr{IPAddrs: []net.IPAddr{{IP: net.ParseIP("127.0.0.1")}}, Port: 38412}, nil
	}
	listenSCTP = func(network string, addr *sctp.SCTPAddr) (sctpListener, error) {
		gotListenNetwork = network
		gotListenAddr = addr
		return &stubSCTPListener{conn: stubConn{remote: "127.0.0.1:49999"}}, nil
	}

	if err := run(runConfig{mode: "listen", target: "127.0.0.1:38412"}); err != nil {
		t.Fatalf("expected listen success, got %v", err)
	}
	if gotListenNetwork != "sctp" || gotListenAddr == nil || gotListenAddr.Port != 38412 {
		t.Fatalf("unexpected listen call: network=%q addr=%+v", gotListenNetwork, gotListenAddr)
	}
}

func TestRunListenPropagatesListenFailure(t *testing.T) {
	originalResolve := resolveSCTPAddr
	originalListen := listenSCTP
	defer func() {
		resolveSCTPAddr = originalResolve
		listenSCTP = originalListen
	}()

	resolveSCTPAddr = func(network, address string) (*sctp.SCTPAddr, error) {
		return &sctp.SCTPAddr{IPAddrs: []net.IPAddr{{IP: net.ParseIP("127.0.0.1")}}, Port: 38412}, nil
	}
	listenSCTP = func(network string, addr *sctp.SCTPAddr) (sctpListener, error) {
		return nil, errors.New("listen blocked in test")
	}

	err := run(runConfig{mode: "listen", target: "127.0.0.1:38412"})
	if err == nil || !strings.Contains(err.Error(), "failed to listen") {
		t.Fatalf("expected listen failure semantics, got %v", err)
	}
}

func TestRunListenPropagatesAcceptFailure(t *testing.T) {
	originalResolve := resolveSCTPAddr
	originalListen := listenSCTP
	defer func() {
		resolveSCTPAddr = originalResolve
		listenSCTP = originalListen
	}()

	resolveSCTPAddr = func(network, address string) (*sctp.SCTPAddr, error) {
		return &sctp.SCTPAddr{IPAddrs: []net.IPAddr{{IP: net.ParseIP("127.0.0.1")}}, Port: 38412}, nil
	}
	listenSCTP = func(network string, addr *sctp.SCTPAddr) (sctpListener, error) {
		return &stubSCTPListener{err: errors.New("accept blocked in test")}, nil
	}

	err := run(runConfig{mode: "listen", target: "127.0.0.1:38412"})
	if err == nil || !strings.Contains(err.Error(), "accept error") {
		t.Fatalf("expected accept failure semantics, got %v", err)
	}
}

type stubSCTPListener struct {
	conn net.Conn
	err  error
}

func (s *stubSCTPListener) Accept() (net.Conn, error) {
	if s.err != nil {
		return nil, s.err
	}
	return s.conn, nil
}

func (s *stubSCTPListener) Close() error { return nil }

type stubConn struct {
	remote string
}

func (c stubConn) Read([]byte) (int, error)         { return 0, nil }
func (c stubConn) Write([]byte) (int, error)        { return 0, nil }
func (c stubConn) Close() error                     { return nil }
func (c stubConn) LocalAddr() net.Addr              { return stubAddr("127.0.0.1:38412") }
func (c stubConn) RemoteAddr() net.Addr             { return stubAddr(c.remote) }
func (c stubConn) SetDeadline(time.Time) error      { return nil }
func (c stubConn) SetReadDeadline(time.Time) error  { return nil }
func (c stubConn) SetWriteDeadline(time.Time) error { return nil }

type stubAddr string

func (a stubAddr) Network() string { return "sctp" }
func (a stubAddr) String() string  { return string(a) }
