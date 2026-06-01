package main

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"testing"

	"github.com/x0tta6bl4/agent/internal/config"
)

func TestMeasuredAttestationDataFromConfigReadsFilesAsBase64(t *testing.T) {
	dir := t.TempDir()
	reportPath := filepath.Join(dir, "report.bin")
	quotePath := filepath.Join(dir, "quote.bin")
	signaturePath := filepath.Join(dir, "signature.bin")
	if err := os.WriteFile(reportPath, []byte("report-bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(quotePath, []byte("quote-bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(signaturePath, []byte("signature-bytes"), 0600); err != nil {
		t.Fatal(err)
	}

	cfg := config.DefaultConfig()
	cfg.RuntimeIdentityMeasuredAttestationProvider = "sgx"
	cfg.RuntimeIdentityMeasuredAttestationReportFile = reportPath
	cfg.RuntimeIdentityMeasuredAttestationQuoteFile = quotePath
	cfg.RuntimeIdentityMeasuredAttestationSignatureFile = signaturePath

	attestation, err := measuredAttestationDataFromConfig(cfg)
	if err != nil {
		t.Fatalf("measuredAttestationDataFromConfig: %v", err)
	}
	if attestation.Provider != "sgx" {
		t.Errorf("Provider = %s", attestation.Provider)
	}
	if attestation.ReportDataB64 != base64.StdEncoding.EncodeToString([]byte("report-bytes")) {
		t.Errorf("ReportDataB64 = %s", attestation.ReportDataB64)
	}
	if attestation.QuoteB64 != base64.StdEncoding.EncodeToString([]byte("quote-bytes")) {
		t.Errorf("QuoteB64 = %s", attestation.QuoteB64)
	}
	if attestation.SignatureB64 != base64.StdEncoding.EncodeToString([]byte("signature-bytes")) {
		t.Errorf("SignatureB64 = %s", attestation.SignatureB64)
	}
}

func TestMeasuredAttestationDataFromConfigUsesInlineReportData(t *testing.T) {
	cfg := config.DefaultConfig()
	cfg.RuntimeIdentityMeasuredAttestationProvider = "mock"
	cfg.RuntimeIdentityMeasuredAttestationReportData = "TRUSTED_X0T"

	attestation, err := measuredAttestationDataFromConfig(cfg)
	if err != nil {
		t.Fatalf("measuredAttestationDataFromConfig: %v", err)
	}
	if attestation.Provider != "mock" {
		t.Errorf("Provider = %s", attestation.Provider)
	}
	if attestation.ReportData != "TRUSTED_X0T" {
		t.Errorf("ReportData = %s", attestation.ReportData)
	}
}
