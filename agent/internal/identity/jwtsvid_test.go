package identity

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestFetchJWTSVIDFromFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "jwt-svid.token")
	if err := os.WriteFile(path, []byte(" jwt-token \n"), 0600); err != nil {
		t.Fatal(err)
	}

	token, err := FetchJWTSVIDFromFile(path)
	if err != nil {
		t.Fatalf("FetchJWTSVIDFromFile: %v", err)
	}
	if token != "jwt-token" {
		t.Errorf("token = %q", token)
	}
}

func TestFetchJWTSVIDWithFetcher_WorkloadAPISource(t *testing.T) {
	var gotAudience string
	var gotAddr string
	fetcher := func(ctx context.Context, audience string, addr string) (string, error) {
		gotAudience = audience
		gotAddr = addr
		return "workload-api-token", nil
	}

	token, err := FetchJWTSVIDWithFetcher(context.Background(), JWTSVIDConfig{
		Source:          SourceWorkloadAPI,
		Audience:        "maas-audience",
		WorkloadAPIAddr: "unix:///run/spire/sockets/agent.sock",
	}, fetcher)
	if err != nil {
		t.Fatalf("FetchJWTSVIDWithFetcher: %v", err)
	}
	if token != "workload-api-token" {
		t.Errorf("token = %q", token)
	}
	if gotAudience != "maas-audience" {
		t.Errorf("audience = %q", gotAudience)
	}
	if gotAddr != "unix:///run/spire/sockets/agent.sock" {
		t.Errorf("addr = %q", gotAddr)
	}
}

func TestFetchJWTSVIDWithFetcher_AutoFallsBackToFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "jwt-svid.token")
	if err := os.WriteFile(path, []byte("file-token"), 0600); err != nil {
		t.Fatal(err)
	}
	fetcher := func(ctx context.Context, audience string, addr string) (string, error) {
		return "", errors.New("spire unavailable")
	}

	token, err := FetchJWTSVIDWithFetcher(context.Background(), JWTSVIDConfig{
		Source:          SourceAuto,
		WorkloadAPIAddr: "unix:///missing.sock",
		FilePath:        path,
	}, fetcher)
	if err != nil {
		t.Fatalf("FetchJWTSVIDWithFetcher: %v", err)
	}
	if token != "file-token" {
		t.Errorf("token = %q", token)
	}
}

func TestFetchJWTSVIDWithFetcher_AutoRequiresConfiguredSource(t *testing.T) {
	t.Setenv("SPIFFE_ENDPOINT_SOCKET", "")

	_, err := FetchJWTSVIDWithFetcher(context.Background(), JWTSVIDConfig{
		Source: SourceAuto,
	}, func(ctx context.Context, audience string, addr string) (string, error) {
		return "unexpected", nil
	})
	if err == nil {
		t.Fatal("expected error without Workload API address or file fallback")
	}
}
