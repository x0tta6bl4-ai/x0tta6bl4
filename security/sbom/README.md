# SBOM Verification

This directory contains the reproducible verification path for the v1.1 SBOM hardening slice.

## Local developer path

Generate and gate SBOM artifacts without GitLab:

```bash
security/sbom/run-local-sbom-check.sh full --tool-mode docker
```

If the Docker-backed Grype scanner stalls, set an explicit timeout for the gate
path:

```bash
SBOM_GRYPE_TIMEOUT_SEC=60 security/sbom/run-local-sbom-check.sh gate --tool-mode docker
```

This produces:

- `security/sbom/out/agent.cdx.json`
- `security/sbom/out/repo.cdx.json`
- `security/sbom/out/repo.spdx.json`
- `security/sbom/out/*.grype.json`

Mock local signing is available, but it is not a keyless Sigstore verification:

```bash
security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker
```

What mock mode proves:

- SBOM artifacts can be signed as blobs
- Signatures can be verified locally with a generated public key

What mock mode does not prove:

- OIDC-backed keyless identity issuance
- Rekor upload or transparency-log inclusion

## CI path

GitLab uses the same scripts in native mode:

- [gitlab-ci-sbom.yml](/mnt/projects/security/sbom/gitlab-ci-sbom.yml)

CI-only real signing path:

```bash
security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native
```

Required CI inputs:

- `SIGSTORE_ID_TOKEN`
- native `cosign`
- native `rekor-cli`

## Verification states

- `VERIFIED HERE`: YAML parsing and script syntax, plus any local runs captured in [v1.1-hardening-status.md](/mnt/projects/docs/verification/v1.1-hardening-status.md)
- `VERIFIED VIA SCRIPT/CI`: reproducible generation/gating/signing flows designed for GitLab runners or Docker-enabled dev hosts
- `NOT VERIFIED YET`: any claim requiring a real OIDC token, Rekor response, or external network access that has not been exercised in this environment
