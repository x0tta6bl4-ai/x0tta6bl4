package security

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

const (
	DefaultReverifyInterval = 10 * time.Minute
	DefaultAuditRetention   = 365 * 24 * time.Hour
)

// Permission represents the minimum capability granted to a peer.
type Permission string

const (
	PermissionTopologyRead  Permission = "topology.read"
	PermissionTopologyWrite Permission = "topology.write"
	PermissionRelay         Permission = "mesh.relay"
	PermissionMetricsRead   Permission = "metrics.read"
)

// FirewallRule is compiled into eBPF-compatible peer isolation rules.
type FirewallRule struct {
	PeerID    string   `json:"peer_id"`
	Action    string   `json:"action"`
	Direction string   `json:"direction"`
	Protocol  string   `json:"protocol"`
	CIDRs     []string `json:"cidrs"`
	Ports     []uint16 `json:"ports"`
}

// EBPFFilterManager applies peer-specific micro-segmentation rules.
type EBPFFilterManager interface {
	ApplyPeerRules(ctx context.Context, peerID string, rules []FirewallRule) error
}

// MemoryFilterManager is a deterministic in-memory backend for tests and
// environments where the kernel eBPF loader sits behind another process.
type MemoryFilterManager struct {
	mu    sync.RWMutex
	rules map[string][]FirewallRule
}

func NewMemoryFilterManager() *MemoryFilterManager {
	return &MemoryFilterManager{rules: make(map[string][]FirewallRule)}
}

func (m *MemoryFilterManager) ApplyPeerRules(_ context.Context, peerID string, rules []FirewallRule) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	cloned := make([]FirewallRule, 0, len(rules))
	for _, rule := range rules {
		cloned = append(cloned, FirewallRule{
			PeerID:    rule.PeerID,
			Action:    rule.Action,
			Direction: rule.Direction,
			Protocol:  rule.Protocol,
			CIDRs:     append([]string(nil), rule.CIDRs...),
			Ports:     append([]uint16(nil), rule.Ports...),
		})
	}
	m.rules[peerID] = cloned
	return nil
}

func (m *MemoryFilterManager) RulesForPeer(peerID string) []FirewallRule {
	m.mu.RLock()
	defer m.mu.RUnlock()

	rules := m.rules[peerID]
	cloned := make([]FirewallRule, 0, len(rules))
	for _, rule := range rules {
		cloned = append(cloned, FirewallRule{
			PeerID:    rule.PeerID,
			Action:    rule.Action,
			Direction: rule.Direction,
			Protocol:  rule.Protocol,
			CIDRs:     append([]string(nil), rule.CIDRs...),
			Ports:     append([]uint16(nil), rule.Ports...),
		})
	}
	return cloned
}

// PeerPolicy describes the least-privilege contract for one mesh peer.
type PeerPolicy struct {
	PeerID              string
	AllowedSignatures   []string
	AllowedKEMKeys      []string
	Permissions         []Permission
	AllowedCIDRs        []string
	AllowedPorts        []uint16
	ReverifyEvery       time.Duration
	LastAuthenticatedAt time.Time
}

// Decision captures the result of a handshake or access-control evaluation.
type Decision struct {
	Allowed            bool
	Reason             string
	ReverifyRequired   bool
	NextReverifyAt     time.Time
	GrantedPermissions []Permission
}

// AuditTrailConfig controls the tamper-evident JSONL audit sink.
type AuditTrailConfig struct {
	Directory string
	Retention time.Duration
	Clock     func() time.Time
}

// AuditEvent is one append-only log record.
type AuditEvent struct {
	Sequence     uint64         `json:"sequence"`
	Timestamp    string         `json:"timestamp"`
	Category     string         `json:"category"`
	PeerID       string         `json:"peer_id"`
	Decision     string         `json:"decision"`
	Details      map[string]any `json:"details,omitempty"`
	PreviousHash string         `json:"previous_hash"`
	EntryHash    string         `json:"entry_hash"`
}

// TamperEvidentAuditTrail writes append-only hash-chained JSONL records.
type TamperEvidentAuditTrail struct {
	mu       sync.Mutex
	cfg      AuditTrailConfig
	sequence uint64
	lastHash string
}

// PolicyEngineConfig wires together continuous auth, eBPF micro-segmentation,
// and the audit sink.
type PolicyEngineConfig struct {
	Clock            func() time.Time
	ReverifyInterval time.Duration
	Filters          EBPFFilterManager
	AuditTrail       *TamperEvidentAuditTrail
}

// PolicyEngine enforces continuous authentication and least-privilege rules.
type PolicyEngine struct {
	mu       sync.RWMutex
	cfg      PolicyEngineConfig
	policies map[string]PeerPolicy
}

func NewTamperEvidentAuditTrail(cfg AuditTrailConfig) (*TamperEvidentAuditTrail, error) {
	if cfg.Directory == "" {
		return nil, fmt.Errorf("audit directory is required")
	}
	if cfg.Clock == nil {
		cfg.Clock = time.Now
	}
	if cfg.Retention <= 0 {
		cfg.Retention = DefaultAuditRetention
	}
	if err := os.MkdirAll(cfg.Directory, 0o755); err != nil {
		return nil, fmt.Errorf("create audit directory: %w", err)
	}

	sequence, lastHash, err := loadAuditState(cfg.Directory)
	if err != nil {
		return nil, err
	}

	return &TamperEvidentAuditTrail{
		cfg:      cfg,
		sequence: sequence,
		lastHash: lastHash,
	}, nil
}

func (t *TamperEvidentAuditTrail) Append(category, peerID, decision string, details map[string]any) (AuditEvent, error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := t.cfg.Clock().UTC()
	t.sequence++
	record := AuditEvent{
		Sequence:     t.sequence,
		Timestamp:    now.Format(time.RFC3339Nano),
		Category:     category,
		PeerID:       peerID,
		Decision:     decision,
		Details:      details,
		PreviousHash: t.lastHash,
	}

	record.EntryHash = t.hashRecord(record)

	line, err := json.Marshal(record)
	if err != nil {
		return AuditEvent{}, fmt.Errorf("marshal audit record: %w", err)
	}

	path := t.auditFilePath(now)
	file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return AuditEvent{}, fmt.Errorf("open audit log: %w", err)
	}
	defer file.Close()

	if _, err := file.Write(append(line, '\n')); err != nil {
		return AuditEvent{}, fmt.Errorf("write audit log: %w", err)
	}

	t.lastHash = record.EntryHash
	if err := t.enforceRetention(now); err != nil {
		return AuditEvent{}, err
	}
	return record, nil
}

func (t *TamperEvidentAuditTrail) auditFilePath(ts time.Time) string {
	return filepath.Join(t.cfg.Directory, fmt.Sprintf("audit-%s.jsonl", ts.Format("2006-01-02")))
}

func (t *TamperEvidentAuditTrail) enforceRetention(now time.Time) error {
	pattern := filepath.Join(t.cfg.Directory, "audit-*.jsonl")
	files, err := filepath.Glob(pattern)
	if err != nil {
		return fmt.Errorf("list audit files: %w", err)
	}

	cutoff := now.Add(-t.cfg.Retention)
	for _, file := range files {
		base := filepath.Base(file)
		datePart := strings.TrimSuffix(strings.TrimPrefix(base, "audit-"), ".jsonl")
		fileTime, err := time.Parse("2006-01-02", datePart)
		if err != nil {
			continue
		}
		if fileTime.Before(cutoff) {
			if err := os.Remove(file); err != nil {
				return fmt.Errorf("remove expired audit file %s: %w", file, err)
			}
		}
	}
	return nil
}

func (t *TamperEvidentAuditTrail) hashRecord(record AuditEvent) string {
	payload := struct {
		Sequence     uint64         `json:"sequence"`
		Timestamp    string         `json:"timestamp"`
		Category     string         `json:"category"`
		PeerID       string         `json:"peer_id"`
		Decision     string         `json:"decision"`
		Details      map[string]any `json:"details,omitempty"`
		PreviousHash string         `json:"previous_hash"`
	}{
		Sequence:     record.Sequence,
		Timestamp:    record.Timestamp,
		Category:     record.Category,
		PeerID:       record.PeerID,
		Decision:     record.Decision,
		Details:      record.Details,
		PreviousHash: record.PreviousHash,
	}
	body, _ := json.Marshal(payload)
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

func NewPolicyEngine(cfg PolicyEngineConfig) (*PolicyEngine, error) {
	if cfg.Clock == nil {
		cfg.Clock = time.Now
	}
	if cfg.ReverifyInterval <= 0 {
		cfg.ReverifyInterval = DefaultReverifyInterval
	}
	if cfg.Filters == nil {
		cfg.Filters = NewMemoryFilterManager()
	}
	if cfg.AuditTrail == nil {
		trail, err := NewTamperEvidentAuditTrail(AuditTrailConfig{
			Directory: filepath.Join(os.TempDir(), "x0tta6bl4-audit"),
		})
		if err != nil {
			return nil, err
		}
		cfg.AuditTrail = trail
	}

	return &PolicyEngine{
		cfg:      cfg,
		policies: make(map[string]PeerPolicy),
	}, nil
}

func (e *PolicyEngine) UpsertPeerPolicy(ctx context.Context, policy PeerPolicy) error {
	if policy.PeerID == "" {
		return fmt.Errorf("peer id is required")
	}
	if policy.ReverifyEvery <= 0 {
		policy.ReverifyEvery = e.cfg.ReverifyInterval
	}
	if len(policy.Permissions) == 0 {
		policy.Permissions = []Permission{PermissionTopologyRead}
	}

	e.mu.Lock()
	e.policies[policy.PeerID] = clonePolicy(policy)
	e.mu.Unlock()

	rules := compileFirewallRules(policy)
	if err := e.cfg.Filters.ApplyPeerRules(ctx, policy.PeerID, rules); err != nil {
		return err
	}
	_, err := e.cfg.AuditTrail.Append("policy.upsert", policy.PeerID, "allow", map[string]any{
		"permissions": policy.Permissions,
		"cidrs":       policy.AllowedCIDRs,
		"ports":       policy.AllowedPorts,
	})
	return err
}

func (e *PolicyEngine) AuthorizeHandshake(peerID, signFingerprint, kemFingerprint string) (Decision, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	policy, ok := e.policies[peerID]
	if !ok {
		decision := Decision{Allowed: false, Reason: "unknown peer", ReverifyRequired: true}
		_, err := e.cfg.AuditTrail.Append("handshake", peerID, "deny", map[string]any{
			"reason": "unknown peer",
		})
		return decision, err
	}

	if len(policy.AllowedSignatures) > 0 && !containsString(policy.AllowedSignatures, signFingerprint) {
		decision := Decision{Allowed: false, Reason: "signing fingerprint rejected", ReverifyRequired: true}
		_, err := e.cfg.AuditTrail.Append("handshake", peerID, "deny", map[string]any{
			"reason":           decision.Reason,
			"sign_fingerprint": signFingerprint,
		})
		return decision, err
	}
	if len(policy.AllowedKEMKeys) > 0 && !containsString(policy.AllowedKEMKeys, kemFingerprint) {
		decision := Decision{Allowed: false, Reason: "KEM fingerprint rejected", ReverifyRequired: true}
		_, err := e.cfg.AuditTrail.Append("handshake", peerID, "deny", map[string]any{
			"reason":          decision.Reason,
			"kem_fingerprint": kemFingerprint,
		})
		return decision, err
	}

	now := e.cfg.Clock()
	policy.LastAuthenticatedAt = now
	e.policies[peerID] = policy

	decision := Decision{
		Allowed:            true,
		Reason:             "peer authenticated",
		ReverifyRequired:   false,
		NextReverifyAt:     now.Add(policy.ReverifyEvery),
		GrantedPermissions: append([]Permission(nil), policy.Permissions...),
	}
	_, err := e.cfg.AuditTrail.Append("handshake", peerID, "allow", map[string]any{
		"sign_fingerprint": signFingerprint,
		"kem_fingerprint":  kemFingerprint,
		"reverify_at":      decision.NextReverifyAt.Format(time.RFC3339),
	})
	return decision, err
}

func (e *PolicyEngine) AuthorizeAction(peerID string, permission Permission) (Decision, error) {
	e.mu.RLock()
	policy, ok := e.policies[peerID]
	e.mu.RUnlock()

	if !ok {
		decision := Decision{Allowed: false, Reason: "unknown peer", ReverifyRequired: true}
		_, err := e.cfg.AuditTrail.Append("policy.decision", peerID, "deny", map[string]any{
			"reason":     decision.Reason,
			"permission": permission,
		})
		return decision, err
	}

	now := e.cfg.Clock()
	if policy.LastAuthenticatedAt.IsZero() || now.Sub(policy.LastAuthenticatedAt) >= policy.ReverifyEvery {
		decision := Decision{
			Allowed:          false,
			Reason:           "continuous authentication required",
			ReverifyRequired: true,
		}
		_, err := e.cfg.AuditTrail.Append("policy.decision", peerID, "deny", map[string]any{
			"reason":     decision.Reason,
			"permission": permission,
		})
		return decision, err
	}

	if !containsPermission(policy.Permissions, permission) {
		decision := Decision{
			Allowed:          false,
			Reason:           "least-privilege policy denied action",
			ReverifyRequired: false,
			NextReverifyAt:   policy.LastAuthenticatedAt.Add(policy.ReverifyEvery),
		}
		_, err := e.cfg.AuditTrail.Append("policy.decision", peerID, "deny", map[string]any{
			"reason":     decision.Reason,
			"permission": permission,
		})
		return decision, err
	}

	decision := Decision{
		Allowed:            true,
		Reason:             "permission granted",
		ReverifyRequired:   false,
		NextReverifyAt:     policy.LastAuthenticatedAt.Add(policy.ReverifyEvery),
		GrantedPermissions: append([]Permission(nil), policy.Permissions...),
	}
	_, err := e.cfg.AuditTrail.Append("policy.decision", peerID, "allow", map[string]any{
		"permission": permission,
		"reverify":   decision.NextReverifyAt.Format(time.RFC3339),
	})
	return decision, err
}

func compileFirewallRules(policy PeerPolicy) []FirewallRule {
	return []FirewallRule{
		{
			PeerID:    policy.PeerID,
			Action:    "allow",
			Direction: "egress",
			Protocol:  "tcp",
			CIDRs:     append([]string(nil), policy.AllowedCIDRs...),
			Ports:     append([]uint16(nil), policy.AllowedPorts...),
		},
		{
			PeerID:    policy.PeerID,
			Action:    "allow",
			Direction: "ingress",
			Protocol:  "tcp",
			CIDRs:     append([]string(nil), policy.AllowedCIDRs...),
			Ports:     append([]uint16(nil), policy.AllowedPorts...),
		},
	}
}

func loadAuditState(dir string) (uint64, string, error) {
	pattern := filepath.Join(dir, "audit-*.jsonl")
	files, err := filepath.Glob(pattern)
	if err != nil {
		return 0, "", fmt.Errorf("list audit files: %w", err)
	}
	if len(files) == 0 {
		return 0, "", nil
	}

	sort.Strings(files)
	lastFile := files[len(files)-1]
	file, err := os.Open(lastFile)
	if err != nil {
		return 0, "", fmt.Errorf("open audit file: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var lastLine string
	for scanner.Scan() {
		lastLine = scanner.Text()
	}
	if err := scanner.Err(); err != nil {
		return 0, "", fmt.Errorf("scan audit file: %w", err)
	}
	if lastLine == "" {
		return 0, "", nil
	}

	var event AuditEvent
	if err := json.Unmarshal([]byte(lastLine), &event); err != nil {
		return 0, "", fmt.Errorf("decode audit event: %w", err)
	}
	return event.Sequence, event.EntryHash, nil
}

func clonePolicy(policy PeerPolicy) PeerPolicy {
	return PeerPolicy{
		PeerID:              policy.PeerID,
		AllowedSignatures:   append([]string(nil), policy.AllowedSignatures...),
		AllowedKEMKeys:      append([]string(nil), policy.AllowedKEMKeys...),
		Permissions:         append([]Permission(nil), policy.Permissions...),
		AllowedCIDRs:        append([]string(nil), policy.AllowedCIDRs...),
		AllowedPorts:        append([]uint16(nil), policy.AllowedPorts...),
		ReverifyEvery:       policy.ReverifyEvery,
		LastAuthenticatedAt: policy.LastAuthenticatedAt,
	}
}

func containsString(values []string, candidate string) bool {
	for _, value := range values {
		if value == candidate {
			return true
		}
	}
	return false
}

func containsPermission(values []Permission, candidate Permission) bool {
	for _, value := range values {
		if value == candidate {
			return true
		}
	}
	return false
}
