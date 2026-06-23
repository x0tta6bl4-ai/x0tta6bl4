# CI Keyless Signing Artifact — 2026-06-15

## Status: PARTIAL

### What Exists

1. **GitHub Actions Workflow** — `.github/workflows/ebpf-release-signing.yml`
   - Triggers on push to `main` and `release/rc1`
   - Has `id-token: write` permission for OIDC
   - Signs artifacts keylessly via Rekor
   - Creates provenance bundle

2. **Previous CI Keyless Run** — 2026-03-12 (commit `b017c24cd`)
   - 7 artifacts signed keylessly
   - Certificates issued by `sigstore.dev / sigstore-intermediate`
   - Certificate identity: `x0tta6bl4-ai/x0tta6bl4/.github/workflows/ebpf-release-signing.yml@refs/heads/release/rc1`
   - Provenance bundle at `docs/release/provenance/`

3. **Local Key Signing** — Verified 2026-06-15
   - All 7 artifacts signed with local key pair
   - Local verification passed
   - Status: `security/sbom/out/local-key-signing-status.txt`

### What's Missing

1. **Fresh CI Keyless Run** — The previous run was March 12, 2026
   - Artifacts have been modified since then
   - Signatures no longer match current content
   - Need a new CI run with current release-bound artifacts

2. **Rekor Transparency Log Entry** — Cannot verify locally
   - Requires `SIGSTORE_ID_TOKEN` (GitHub Actions OIDC)
   - Requires network access to `tuf-repo-cdn.sigstore.dev`
   - Proxy issues prevent local Rekor verification

### Verification Attempts

| Artifact | Local Key | CI Keyless | Rekor |
|----------|-----------|------------|-------|
| RC1_MANIFEST.json | PASS | cert exists, sig mismatch | blocked by proxy |
| RC1_RELEASE_NOTES.md | PASS | cert exists, sig mismatch | blocked by proxy |
| RC1_STATUS_PAGE.md | PASS | cert exists, sig mismatch | blocked by proxy |
| RC1_INTEGRITY_NOTE.md | PASS | cert exists, sig mismatch | blocked by proxy |
| agent.cdx.json | PASS | cert exists, sig mismatch | blocked by proxy |
| repo.cdx.json | PASS | cert exists, sig mismatch | blocked by proxy |
| repo.spdx.json | PASS | cert exists, sig mismatch | blocked by proxy |

### Sig Mismatch Root Cause

The CI keyless run signed `RC1_MANIFEST.json` at commit `b017c24cd`. The manifest content hash at that commit matches the current hash (`ca7b3d7aba...`), but cosign v2.4.1 reports "invalid signature when validating ASN.1 encoded signature". This suggests:
- Version mismatch between CI cosign and local cosign
- Or signature format incompatibility
- Or the `.sig` files in provenance/ were overwritten by local-key run

### How to Close This Blocker

1. **Trigger a fresh CI run**:
   ```bash
   git push origin HEAD:release/rc1
   # Or manually trigger the workflow via GitHub Actions UI
   ```

2. **Verify the new provenance bundle**:
   ```bash
   security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native
   ```

3. **Confirm Rekor inclusion**:
   - Check GitHub Actions logs for Rekor upload
   - Verify with `rekor-cli search --email <oidc-email>`

### Artifacts

- Workflow: `.github/workflows/ebpf-release-signing.yml`
- Previous provenance: `docs/release/provenance/`
- Local signing status: `security/sbom/out/local-key-signing-status.txt`
- This document: `docs/verification/ci-keyless-signing-20260615T105500Z/README.md`
