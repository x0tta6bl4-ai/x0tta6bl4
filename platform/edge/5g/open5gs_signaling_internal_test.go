package edge5g

import (
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/ishidawataru/sctp"
)

func TestSCTPInitMsgForTimeoutDefaultsAndClamps(t *testing.T) {
	defaultOpts := sctpInitMsgForTimeout(0)
	if defaultOpts.NumOstreams != sctp.SCTP_MAX_STREAM {
		t.Fatalf("expected max output streams by default, got %d", defaultOpts.NumOstreams)
	}
	if defaultOpts.MaxInitTimeout != 1000 {
		t.Fatalf("expected default SCTP init timeout 1000ms, got %d", defaultOpts.MaxInitTimeout)
	}

	custom := sctpInitMsgForTimeout(250 * time.Millisecond)
	if custom.MaxInitTimeout != 250 {
		t.Fatalf("expected custom SCTP init timeout 250ms, got %d", custom.MaxInitTimeout)
	}

	clamped := sctpInitMsgForTimeout(90 * time.Second)
	if clamped.MaxInitTimeout != ^uint16(0) {
		t.Fatalf("expected clamped SCTP init timeout %d, got %d", ^uint16(0), clamped.MaxInitTimeout)
	}
}

func TestOpen5GSSignalingEstablishNGAPUsesTimeoutAwareDialOptions(t *testing.T) {
	originalDial := dialSCTPExt
	defer func() { dialSCTPExt = originalDial }()

	var gotNetwork string
	var gotAddr *sctp.SCTPAddr
	var gotInit sctp.InitMsg
	dialSCTPExt = func(network string, laddr, raddr *sctp.SCTPAddr, options sctp.InitMsg) (*sctp.SCTPConn, error) {
		gotNetwork = network
		gotAddr = raddr
		gotInit = options
		return nil, errors.New("dial blocked in test")
	}

	signaling := &Open5GSSignaling{
		AMFAddr: "127.0.0.1:38412",
		Timeout: 250 * time.Millisecond,
	}

	err := signaling.EstablishNGAP("ue1")
	if err == nil || !strings.Contains(err.Error(), "SCTP transport failure") {
		t.Fatalf("expected SCTP transport failure semantics, got %v", err)
	}
	if gotNetwork != "sctp" {
		t.Fatalf("expected sctp network, got %q", gotNetwork)
	}
	if gotAddr == nil || gotAddr.Port != 38412 {
		t.Fatalf("expected SCTP dial to target port 38412, got %+v", gotAddr)
	}
	if gotInit.NumOstreams != sctp.SCTP_MAX_STREAM || gotInit.MaxInitTimeout != 250 {
		t.Fatalf("unexpected SCTP init options: %+v", gotInit)
	}
}
