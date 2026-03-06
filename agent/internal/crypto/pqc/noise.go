package pqc

import (
	"bytes"
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"io"
	"time"

	"golang.org/x/crypto/hkdf"
)

const (
	noiseProtocolVersion      = 1
	DefaultPQCTimeout         = 5 * time.Second
	DefaultHandshakeBudgetP99 = 100 * time.Millisecond
	noiseSessionKeySize       = 32
	noiseContextLabel         = "x0tta6bl4-libp2p-noise-v1"
)

// HandshakeMode captures whether the session used hybrid PQC or degraded to
// classical X25519 because the PQC stage exceeded the timeout budget.
type HandshakeMode uint8

const (
	HandshakeModeInvalid HandshakeMode = iota
	HandshakeModeHybrid
	HandshakeModeClassicalFallback
)

func (m HandshakeMode) String() string {
	switch m {
	case HandshakeModeHybrid:
		return "hybrid"
	case HandshakeModeClassicalFallback:
		return "classical-fallback"
	default:
		return "invalid"
	}
}

// HybridIdentity is the long-lived PQC identity advertised during the Noise
// handshake extension.
type HybridIdentity struct {
	NodeID             string
	KEMAlgorithm       string
	KEMPublicKey       []byte
	KEMPrivateKey      []byte
	SignatureAlgorithm string
	SignPublicKey      []byte
	SignPrivateKey     []byte
}

// HybridNoiseConfig configures the libp2p Noise handshake extension.
type HybridNoiseConfig struct {
	NodeID                 string
	Identity               *HybridIdentity
	KEMBackend             KEMBackend
	SignerBackend          SignerBackend
	Clock                  func() time.Time
	PQCTimeout             time.Duration
	HandshakeBudget        time.Duration
	AllowClassicalFallback bool
}

// NoiseHandshakeInit is attached to the initiator's libp2p Noise payload.
type NoiseHandshakeInit struct {
	Version            uint8
	Mode               HandshakeMode
	NodeID             string
	TimestampUnix      int64
	Nonce              []byte
	ClassicalPublicKey []byte
	KEMPublicKey       []byte
	SignPublicKey      []byte
	KEMAlgorithm       string
	SignatureAlgorithm string
	Signature          []byte
}

// NoiseHandshakeResponse is attached to the responder's libp2p Noise payload.
type NoiseHandshakeResponse struct {
	Version            uint8
	Mode               HandshakeMode
	NodeID             string
	TimestampUnix      int64
	Nonce              []byte
	ClassicalPublicKey []byte
	KEMCiphertext      []byte
	SignPublicKey      []byte
	KEMAlgorithm       string
	SignatureAlgorithm string
	Signature          []byte
}

// NoiseSession represents the established session material.
type NoiseSession struct {
	PeerID              string
	Mode                HandshakeMode
	SharedKey           []byte
	HandshakeLatency    time.Duration
	TargetP99Met        bool
	PeerSignFingerprint string
	PeerKEMFingerprint  string
}

// InitiatorState carries initiator state between the first and second Noise
// messages.
type InitiatorState struct {
	startedAt     time.Time
	classicalPriv *ecdh.PrivateKey
	init          *NoiseHandshakeInit
}

// HybridNoiseTransport generates and validates the handshake payloads that can
// be embedded into libp2p Noise handshake messages.
type HybridNoiseTransport struct {
	cfg      HybridNoiseConfig
	identity HybridIdentity
	curve    ecdh.Curve
}

// NewHybridNoiseTransport creates a new libp2p Noise extension transport.
func NewHybridNoiseTransport(cfg HybridNoiseConfig) (*HybridNoiseTransport, error) {
	if cfg.KEMBackend == nil {
		cfg.KEMBackend = MLKEM768Backend{}
	}
	if cfg.SignerBackend == nil {
		cfg.SignerBackend = MLDSA65Backend{}
	}
	if cfg.Clock == nil {
		cfg.Clock = time.Now
	}
	if cfg.PQCTimeout <= 0 {
		cfg.PQCTimeout = DefaultPQCTimeout
	}
	if cfg.HandshakeBudget <= 0 {
		cfg.HandshakeBudget = DefaultHandshakeBudgetP99
	}
	if !cfg.AllowClassicalFallback {
		cfg.AllowClassicalFallback = true
	}

	identity, err := resolveHybridIdentity(cfg)
	if err != nil {
		return nil, err
	}

	return &HybridNoiseTransport{
		cfg:      cfg,
		identity: identity,
		curve:    ecdh.X25519(),
	}, nil
}

// Identity returns the current long-lived hybrid identity material.
func (t *HybridNoiseTransport) Identity() HybridIdentity {
	return cloneIdentity(t.identity)
}

// StartInitiatorHandshake generates the initiator payload to embed in the
// first libp2p Noise message.
func (t *HybridNoiseTransport) StartInitiatorHandshake() (*InitiatorState, *NoiseHandshakeInit, error) {
	classicalPriv, err := t.curve.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate X25519 initiator key: %w", err)
	}

	initMsg := &NoiseHandshakeInit{
		Version:            noiseProtocolVersion,
		Mode:               HandshakeModeHybrid,
		NodeID:             t.identity.NodeID,
		TimestampUnix:      t.cfg.Clock().Unix(),
		Nonce:              randomBytes(32),
		ClassicalPublicKey: classicalPriv.PublicKey().Bytes(),
		KEMPublicKey:       cloneBytes(t.identity.KEMPublicKey),
		SignPublicKey:      cloneBytes(t.identity.SignPublicKey),
		KEMAlgorithm:       t.identity.KEMAlgorithm,
		SignatureAlgorithm: t.identity.SignatureAlgorithm,
	}

	signable, err := initMsg.signableBytes()
	if err != nil {
		return nil, nil, err
	}

	signature, err := t.cfg.SignerBackend.Sign(t.identity.SignPrivateKey, signable)
	if err != nil {
		return nil, nil, fmt.Errorf("sign initiator payload: %w", err)
	}
	initMsg.Signature = signature

	return &InitiatorState{
		startedAt:     t.cfg.Clock(),
		classicalPriv: classicalPriv,
		init:          initMsg,
	}, initMsg, nil
}

// HandleResponderHandshake verifies the initiator payload, performs the PQC
// stage if it fits the timeout budget, and emits the responder payload.
func (t *HybridNoiseTransport) HandleResponderHandshake(
	ctx context.Context,
	initMsg *NoiseHandshakeInit,
) (*NoiseHandshakeResponse, *NoiseSession, error) {
	if initMsg == nil {
		return nil, nil, fmt.Errorf("initiator payload is required")
	}
	if ctx == nil {
		ctx = context.Background()
	}

	if err := t.verifyInit(initMsg); err != nil {
		return nil, nil, err
	}

	started := t.cfg.Clock()
	classicalPriv, err := t.curve.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate X25519 responder key: %w", err)
	}

	classicalSecret, err := t.classicalSecret(classicalPriv, initMsg.ClassicalPublicKey)
	if err != nil {
		return nil, nil, err
	}

	mode := HandshakeModeClassicalFallback
	var pqcSecret []byte
	var pqcCiphertext []byte

	if len(initMsg.KEMPublicKey) > 0 {
		pqcStart := t.cfg.Clock()
		ciphertext, sharedSecret, kemErr := t.cfg.KEMBackend.Encapsulate(initMsg.KEMPublicKey)
		switch {
		case kemErr == nil && !t.pqcBudgetExceeded(ctx, pqcStart):
			mode = HandshakeModeHybrid
			pqcCiphertext = ciphertext
			pqcSecret = sharedSecret
		case kemErr != nil && !t.cfg.AllowClassicalFallback:
			return nil, nil, fmt.Errorf("encapsulate PQC secret: %w", kemErr)
		case t.pqcBudgetExceeded(ctx, pqcStart) && !t.cfg.AllowClassicalFallback:
			return nil, nil, fmt.Errorf("pqc stage exceeded %s without fallback", t.cfg.PQCTimeout)
		}
	}

	respMsg := &NoiseHandshakeResponse{
		Version:            noiseProtocolVersion,
		Mode:               mode,
		NodeID:             t.identity.NodeID,
		TimestampUnix:      t.cfg.Clock().Unix(),
		Nonce:              randomBytes(32),
		ClassicalPublicKey: classicalPriv.PublicKey().Bytes(),
		KEMCiphertext:      pqcCiphertext,
		SignPublicKey:      cloneBytes(t.identity.SignPublicKey),
		KEMAlgorithm:       t.identity.KEMAlgorithm,
		SignatureAlgorithm: t.identity.SignatureAlgorithm,
	}

	transcript, err := handshakeTranscript(initMsg, respMsg)
	if err != nil {
		return nil, nil, err
	}

	signature, err := t.cfg.SignerBackend.Sign(t.identity.SignPrivateKey, transcript)
	if err != nil {
		return nil, nil, fmt.Errorf("sign responder payload: %w", err)
	}
	respMsg.Signature = signature

	sharedKey, err := deriveNoiseSessionKey(classicalSecret, pqcSecret, transcript)
	if err != nil {
		return nil, nil, err
	}

	latency := t.cfg.Clock().Sub(started)
	return respMsg, &NoiseSession{
		PeerID:              initMsg.NodeID,
		Mode:                mode,
		SharedKey:           sharedKey,
		HandshakeLatency:    latency,
		TargetP99Met:        latency <= t.cfg.HandshakeBudget,
		PeerSignFingerprint: keyFingerprint(initMsg.SignPublicKey),
		PeerKEMFingerprint:  keyFingerprint(initMsg.KEMPublicKey),
	}, nil
}

// FinishInitiatorHandshake verifies the responder payload and derives the
// session key using the initiator's private material.
func (t *HybridNoiseTransport) FinishInitiatorHandshake(
	ctx context.Context,
	state *InitiatorState,
	respMsg *NoiseHandshakeResponse,
) (*NoiseSession, error) {
	if state == nil || state.init == nil || state.classicalPriv == nil {
		return nil, fmt.Errorf("initiator state is incomplete")
	}
	if respMsg == nil {
		return nil, fmt.Errorf("responder payload is required")
	}
	if ctx == nil {
		ctx = context.Background()
	}

	transcript, err := handshakeTranscript(state.init, respMsg)
	if err != nil {
		return nil, err
	}
	if !t.cfg.SignerBackend.Verify(respMsg.SignPublicKey, transcript, respMsg.Signature) {
		return nil, fmt.Errorf("invalid responder ML-DSA signature")
	}

	classicalSecret, err := t.classicalSecret(state.classicalPriv, respMsg.ClassicalPublicKey)
	if err != nil {
		return nil, err
	}

	var pqcSecret []byte
	if respMsg.Mode == HandshakeModeHybrid {
		if len(respMsg.KEMCiphertext) == 0 {
			return nil, fmt.Errorf("hybrid responder payload missing ML-KEM ciphertext")
		}
		pqcSecret, err = t.cfg.KEMBackend.Decapsulate(t.identity.KEMPrivateKey, respMsg.KEMCiphertext)
		if err != nil {
			return nil, fmt.Errorf("decapsulate responder ML-KEM ciphertext: %w", err)
		}
	}

	sharedKey, err := deriveNoiseSessionKey(classicalSecret, pqcSecret, transcript)
	if err != nil {
		return nil, err
	}

	latency := t.cfg.Clock().Sub(state.startedAt)
	return &NoiseSession{
		PeerID:              respMsg.NodeID,
		Mode:                respMsg.Mode,
		SharedKey:           sharedKey,
		HandshakeLatency:    latency,
		TargetP99Met:        latency <= t.cfg.HandshakeBudget,
		PeerSignFingerprint: keyFingerprint(respMsg.SignPublicKey),
		PeerKEMFingerprint:  "",
	}, nil
}

func (m *NoiseHandshakeInit) MarshalBinary() ([]byte, error) {
	return encodeHandshakeFrame(
		m.Version,
		byte(m.Mode),
		m.NodeID,
		m.TimestampUnix,
		m.Nonce,
		m.ClassicalPublicKey,
		m.KEMPublicKey,
		m.SignPublicKey,
		m.KEMAlgorithm,
		m.SignatureAlgorithm,
		m.Signature,
	)
}

func (m *NoiseHandshakeInit) signableBytes() ([]byte, error) {
	return encodeHandshakeFrame(
		m.Version,
		byte(m.Mode),
		m.NodeID,
		m.TimestampUnix,
		m.Nonce,
		m.ClassicalPublicKey,
		m.KEMPublicKey,
		m.SignPublicKey,
		m.KEMAlgorithm,
		m.SignatureAlgorithm,
		nil,
	)
}

// ParseNoiseHandshakeInit parses the initiator payload received from libp2p.
func ParseNoiseHandshakeInit(data []byte) (*NoiseHandshakeInit, error) {
	frame, err := decodeHandshakeFrame(data)
	if err != nil {
		return nil, err
	}

	return &NoiseHandshakeInit{
		Version:            frame.version,
		Mode:               HandshakeMode(frame.mode),
		NodeID:             frame.nodeID,
		TimestampUnix:      frame.timestampUnix,
		Nonce:              frame.nonce,
		ClassicalPublicKey: frame.classicalKey,
		KEMPublicKey:       frame.kemPayload,
		SignPublicKey:      frame.signPublicKey,
		KEMAlgorithm:       frame.kemAlgorithm,
		SignatureAlgorithm: frame.signatureAlgorithm,
		Signature:          frame.signature,
	}, nil
}

func (m *NoiseHandshakeResponse) MarshalBinary() ([]byte, error) {
	return encodeHandshakeFrame(
		m.Version,
		byte(m.Mode),
		m.NodeID,
		m.TimestampUnix,
		m.Nonce,
		m.ClassicalPublicKey,
		m.KEMCiphertext,
		m.SignPublicKey,
		m.KEMAlgorithm,
		m.SignatureAlgorithm,
		m.Signature,
	)
}

func (m *NoiseHandshakeResponse) signableBytes() ([]byte, error) {
	return encodeHandshakeFrame(
		m.Version,
		byte(m.Mode),
		m.NodeID,
		m.TimestampUnix,
		m.Nonce,
		m.ClassicalPublicKey,
		m.KEMCiphertext,
		m.SignPublicKey,
		m.KEMAlgorithm,
		m.SignatureAlgorithm,
		nil,
	)
}

// ParseNoiseHandshakeResponse parses the responder payload received from libp2p.
func ParseNoiseHandshakeResponse(data []byte) (*NoiseHandshakeResponse, error) {
	frame, err := decodeHandshakeFrame(data)
	if err != nil {
		return nil, err
	}

	return &NoiseHandshakeResponse{
		Version:            frame.version,
		Mode:               HandshakeMode(frame.mode),
		NodeID:             frame.nodeID,
		TimestampUnix:      frame.timestampUnix,
		Nonce:              frame.nonce,
		ClassicalPublicKey: frame.classicalKey,
		KEMCiphertext:      frame.kemPayload,
		SignPublicKey:      frame.signPublicKey,
		KEMAlgorithm:       frame.kemAlgorithm,
		SignatureAlgorithm: frame.signatureAlgorithm,
		Signature:          frame.signature,
	}, nil
}

func (t *HybridNoiseTransport) verifyInit(initMsg *NoiseHandshakeInit) error {
	if initMsg.Version != noiseProtocolVersion {
		return fmt.Errorf("unsupported initiator protocol version: %d", initMsg.Version)
	}
	signable, err := initMsg.signableBytes()
	if err != nil {
		return err
	}
	if !t.cfg.SignerBackend.Verify(initMsg.SignPublicKey, signable, initMsg.Signature) {
		return fmt.Errorf("invalid initiator ML-DSA signature")
	}
	return nil
}

func (t *HybridNoiseTransport) pqcBudgetExceeded(ctx context.Context, started time.Time) bool {
	if ctx.Err() != nil {
		return true
	}
	return t.cfg.Clock().Sub(started) > t.cfg.PQCTimeout
}

func (t *HybridNoiseTransport) classicalSecret(localPriv *ecdh.PrivateKey, peerPubBytes []byte) ([]byte, error) {
	peerPub, err := t.curve.NewPublicKey(peerPubBytes)
	if err != nil {
		return nil, fmt.Errorf("parse X25519 peer key: %w", err)
	}

	secret, err := localPriv.ECDH(peerPub)
	if err != nil {
		return nil, fmt.Errorf("derive X25519 secret: %w", err)
	}
	return secret, nil
}

func deriveNoiseSessionKey(classicalSecret, pqcSecret, transcript []byte) ([]byte, error) {
	inputKeyMaterial := make([]byte, 0, len(classicalSecret)+len(pqcSecret)+1)
	inputKeyMaterial = append(inputKeyMaterial, classicalSecret...)
	inputKeyMaterial = append(inputKeyMaterial, pqcSecret...)
	if len(pqcSecret) == 0 {
		inputKeyMaterial = append(inputKeyMaterial, byte(HandshakeModeClassicalFallback))
	} else {
		inputKeyMaterial = append(inputKeyMaterial, byte(HandshakeModeHybrid))
	}

	derived := make([]byte, noiseSessionKeySize)
	reader := hkdf.New(sha256.New, inputKeyMaterial, transcript, []byte(noiseContextLabel))
	if _, err := io.ReadFull(reader, derived); err != nil {
		return nil, fmt.Errorf("derive session key: %w", err)
	}
	return derived, nil
}

func handshakeTranscript(initMsg *NoiseHandshakeInit, respMsg *NoiseHandshakeResponse) ([]byte, error) {
	initSignable, err := initMsg.signableBytes()
	if err != nil {
		return nil, err
	}
	respSignable, err := respMsg.signableBytes()
	if err != nil {
		return nil, err
	}

	initDigest := sha256.Sum256(initSignable)
	buf := bytes.NewBuffer(make([]byte, 0, len(initDigest)+len(respSignable)))
	buf.Write(initDigest[:])
	buf.Write(respSignable)
	transcriptDigest := sha256.Sum256(buf.Bytes())
	return transcriptDigest[:], nil
}

func resolveHybridIdentity(cfg HybridNoiseConfig) (HybridIdentity, error) {
	if cfg.Identity != nil {
		identity := cloneIdentity(*cfg.Identity)
		if identity.NodeID == "" {
			identity.NodeID = cfg.NodeID
		}
		if identity.NodeID == "" {
			return HybridIdentity{}, fmt.Errorf("node id is required")
		}
		if len(identity.KEMPublicKey) == 0 || len(identity.KEMPrivateKey) == 0 {
			return HybridIdentity{}, fmt.Errorf("hybrid identity missing ML-KEM key material")
		}
		if len(identity.SignPublicKey) == 0 || len(identity.SignPrivateKey) == 0 {
			return HybridIdentity{}, fmt.Errorf("hybrid identity missing ML-DSA key material")
		}
		if identity.KEMAlgorithm == "" {
			identity.KEMAlgorithm = cfg.KEMBackend.Algorithm()
		}
		if identity.SignatureAlgorithm == "" {
			identity.SignatureAlgorithm = cfg.SignerBackend.Algorithm()
		}
		return identity, nil
	}

	if cfg.NodeID == "" {
		return HybridIdentity{}, fmt.Errorf("node id is required")
	}

	kemPublic, kemPrivate, err := cfg.KEMBackend.GenerateKeyPair()
	if err != nil {
		return HybridIdentity{}, err
	}
	signPublic, signPrivate, err := cfg.SignerBackend.GenerateKeyPair()
	if err != nil {
		return HybridIdentity{}, err
	}

	return HybridIdentity{
		NodeID:             cfg.NodeID,
		KEMAlgorithm:       cfg.KEMBackend.Algorithm(),
		KEMPublicKey:       kemPublic,
		KEMPrivateKey:      kemPrivate,
		SignatureAlgorithm: cfg.SignerBackend.Algorithm(),
		SignPublicKey:      signPublic,
		SignPrivateKey:     signPrivate,
	}, nil
}

type handshakeFrame struct {
	version            uint8
	mode               uint8
	nodeID             string
	timestampUnix      int64
	nonce              []byte
	classicalKey       []byte
	kemPayload         []byte
	signPublicKey      []byte
	kemAlgorithm       string
	signatureAlgorithm string
	signature          []byte
}

func encodeHandshakeFrame(
	version uint8,
	mode byte,
	nodeID string,
	timestampUnix int64,
	nonce []byte,
	classicalKey []byte,
	kemPayload []byte,
	signPublicKey []byte,
	kemAlgorithm string,
	signatureAlgorithm string,
	signature []byte,
) ([]byte, error) {
	buf := new(bytes.Buffer)
	buf.WriteByte(version)
	buf.WriteByte(mode)
	if err := binary.Write(buf, binary.BigEndian, timestampUnix); err != nil {
		return nil, fmt.Errorf("encode timestamp: %w", err)
	}

	if err := writeStringField(buf, nodeID); err != nil {
		return nil, err
	}
	for _, field := range [][]byte{nonce, classicalKey, kemPayload, signPublicKey, signature} {
		if err := writeBytesField(buf, field); err != nil {
			return nil, err
		}
	}
	if err := writeStringField(buf, kemAlgorithm); err != nil {
		return nil, err
	}
	if err := writeStringField(buf, signatureAlgorithm); err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}

func decodeHandshakeFrame(data []byte) (*handshakeFrame, error) {
	reader := bytes.NewReader(data)
	frame := &handshakeFrame{}

	version, err := reader.ReadByte()
	if err != nil {
		return nil, fmt.Errorf("read protocol version: %w", err)
	}
	mode, err := reader.ReadByte()
	if err != nil {
		return nil, fmt.Errorf("read handshake mode: %w", err)
	}
	frame.version = version
	frame.mode = mode

	if err := binary.Read(reader, binary.BigEndian, &frame.timestampUnix); err != nil {
		return nil, fmt.Errorf("read timestamp: %w", err)
	}

	if frame.nodeID, err = readStringField(reader); err != nil {
		return nil, err
	}
	if frame.nonce, err = readBytesField(reader); err != nil {
		return nil, err
	}
	if frame.classicalKey, err = readBytesField(reader); err != nil {
		return nil, err
	}
	if frame.kemPayload, err = readBytesField(reader); err != nil {
		return nil, err
	}
	if frame.signPublicKey, err = readBytesField(reader); err != nil {
		return nil, err
	}
	if frame.signature, err = readBytesField(reader); err != nil {
		return nil, err
	}
	if frame.kemAlgorithm, err = readStringField(reader); err != nil {
		return nil, err
	}
	if frame.signatureAlgorithm, err = readStringField(reader); err != nil {
		return nil, err
	}

	if reader.Len() != 0 {
		return nil, fmt.Errorf("unexpected trailing bytes in handshake frame")
	}
	return frame, nil
}

func writeStringField(buf *bytes.Buffer, value string) error {
	return writeBytesField(buf, []byte(value))
}

func writeBytesField(buf *bytes.Buffer, value []byte) error {
	if len(value) > 0xffff {
		return fmt.Errorf("field too large: %d bytes", len(value))
	}
	if err := binary.Write(buf, binary.BigEndian, uint16(len(value))); err != nil {
		return fmt.Errorf("encode field length: %w", err)
	}
	if len(value) > 0 {
		if _, err := buf.Write(value); err != nil {
			return fmt.Errorf("encode field value: %w", err)
		}
	}
	return nil
}

func readStringField(reader *bytes.Reader) (string, error) {
	data, err := readBytesField(reader)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func readBytesField(reader *bytes.Reader) ([]byte, error) {
	var length uint16
	if err := binary.Read(reader, binary.BigEndian, &length); err != nil {
		return nil, fmt.Errorf("read field length: %w", err)
	}

	value := make([]byte, length)
	if _, err := io.ReadFull(reader, value); err != nil {
		return nil, fmt.Errorf("read field value: %w", err)
	}
	return value, nil
}

func randomBytes(size int) []byte {
	buf := make([]byte, size)
	if _, err := io.ReadFull(rand.Reader, buf); err != nil {
		panic(err)
	}
	return buf
}

func cloneIdentity(identity HybridIdentity) HybridIdentity {
	return HybridIdentity{
		NodeID:             identity.NodeID,
		KEMAlgorithm:       identity.KEMAlgorithm,
		KEMPublicKey:       cloneBytes(identity.KEMPublicKey),
		KEMPrivateKey:      cloneBytes(identity.KEMPrivateKey),
		SignatureAlgorithm: identity.SignatureAlgorithm,
		SignPublicKey:      cloneBytes(identity.SignPublicKey),
		SignPrivateKey:     cloneBytes(identity.SignPrivateKey),
	}
}

func cloneBytes(value []byte) []byte {
	if len(value) == 0 {
		return nil
	}
	out := make([]byte, len(value))
	copy(out, value)
	return out
}
