// Package identity fetches runtime identity material for the agent.
package identity

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spiffe/go-spiffe/v2/svid/jwtsvid"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
)

const (
	DefaultJWTSVIDAudience = "x0tta6bl4-maas"
	DefaultFetchTimeout    = 5 * time.Second

	SourceAuto        = "auto"
	SourceFile        = "file"
	SourceWorkloadAPI = "workload_api"
)

// JWTSVIDConfig controls where the agent gets a live JWT-SVID.
type JWTSVIDConfig struct {
	Source          string
	Audience        string
	FilePath        string
	WorkloadAPIAddr string
	Timeout         time.Duration
}

// WorkloadAPIFetcher makes Workload API access testable without a live SPIRE agent.
type WorkloadAPIFetcher func(ctx context.Context, audience string, addr string) (string, error)

// FetchJWTSVID returns a JWT-SVID from the configured source.
func FetchJWTSVID(ctx context.Context, cfg JWTSVIDConfig) (string, error) {
	return FetchJWTSVIDWithFetcher(ctx, cfg, FetchJWTSVIDFromWorkloadAPI)
}

// FetchJWTSVIDWithFetcher returns a JWT-SVID using an injectable Workload API fetcher.
func FetchJWTSVIDWithFetcher(ctx context.Context, cfg JWTSVIDConfig, fetcher WorkloadAPIFetcher) (string, error) {
	source := normalizeSource(cfg.Source)
	audience := normalizeAudience(cfg.Audience)

	switch source {
	case SourceFile:
		return FetchJWTSVIDFromFile(cfg.FilePath)
	case SourceWorkloadAPI:
		return fetcher(ctx, audience, cfg.WorkloadAPIAddr)
	case SourceAuto:
		if cfg.WorkloadAPIAddr != "" || os.Getenv(workloadapi.SocketEnv) != "" {
			token, err := fetcher(ctx, audience, cfg.WorkloadAPIAddr)
			if err == nil {
				return token, nil
			}
			if strings.TrimSpace(cfg.FilePath) == "" {
				return "", fmt.Errorf("fetch JWT-SVID from Workload API: %w", err)
			}
		}
		if strings.TrimSpace(cfg.FilePath) != "" {
			return FetchJWTSVIDFromFile(cfg.FilePath)
		}
		return "", fmt.Errorf("JWT-SVID source auto requires %s, runtime_identity_workload_api_addr, or runtime_identity_jwt_svid_file", workloadapi.SocketEnv)
	default:
		return "", fmt.Errorf("invalid JWT-SVID source: %s", source)
	}
}

// FetchJWTSVIDFromFile reads a JWT-SVID token from a local file.
func FetchJWTSVIDFromFile(path string) (string, error) {
	normalized := strings.TrimSpace(path)
	if normalized == "" {
		return "", fmt.Errorf("runtime_identity_jwt_svid_file is not configured")
	}
	raw, err := os.ReadFile(normalized)
	if err != nil {
		return "", err
	}
	token := strings.TrimSpace(string(raw))
	if token == "" {
		return "", fmt.Errorf("runtime_identity_jwt_svid_file is empty")
	}
	return token, nil
}

// FetchJWTSVIDFromWorkloadAPI fetches a live JWT-SVID from the SPIFFE Workload API.
func FetchJWTSVIDFromWorkloadAPI(ctx context.Context, audience string, addr string) (string, error) {
	timeoutCtx, cancel := context.WithTimeout(ctx, DefaultFetchTimeout)
	defer cancel()

	options := []workloadapi.ClientOption{}
	if normalizedAddr := strings.TrimSpace(addr); normalizedAddr != "" {
		options = append(options, workloadapi.WithAddr(normalizedAddr))
	}

	svid, err := workloadapi.FetchJWTSVID(
		timeoutCtx,
		jwtsvid.Params{Audience: normalizeAudience(audience)},
		options...,
	)
	if err != nil {
		return "", err
	}
	token := strings.TrimSpace(svid.Marshal())
	if token == "" {
		return "", fmt.Errorf("SPIFFE Workload API returned empty JWT-SVID")
	}
	return token, nil
}

func normalizeAudience(value string) string {
	normalized := strings.TrimSpace(value)
	if normalized == "" {
		return DefaultJWTSVIDAudience
	}
	return normalized
}

func normalizeSource(value string) string {
	normalized := strings.ToLower(strings.TrimSpace(value))
	if normalized == "" {
		return SourceAuto
	}
	return normalized
}
